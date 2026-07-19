"""Cache-first FastAPI implementation of the frozen VentureIntelligence API."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
# Vercel imports this module as ``main`` when ``backend/`` is the service
# root. Make the shared repository package importable in that execution mode.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # Package import locally; direct module import in the Vercel service.
    from .llm.wrapper import LLMWrapper
except ImportError:  # pragma: no cover - exercised by Vercel's entrypoint loader
    from llm.wrapper import LLMWrapper

from ai_service import pipeline as product_pipeline  # noqa: E402 - import follows Vercel path bootstrap
from ai_service import sourcing_orchestration  # noqa: E402 - import follows Vercel path bootstrap


load_dotenv(ROOT / ".env")

# A Render container mounts a persistent disk at /data. Vercel functions have
# an ephemeral, writable /tmp directory, so each cold start begins from the
# reviewed cache rather than attempting to write into the read-only deployment
# bundle. Local development continues to use the ignored database next to this
# module.
PERSISTENT_DATABASE_PATH = Path("/data/venture_intelligence.db")
VERCEL_DATABASE_PATH = Path("/tmp/venture_intelligence.db")
if os.getenv("VERCEL") == "1":
    DATABASE_PATH = VERCEL_DATABASE_PATH
elif PERSISTENT_DATABASE_PATH.parent.is_dir():
    DATABASE_PATH = PERSISTENT_DATABASE_PATH
else:
    DATABASE_PATH = Path(__file__).with_name("venture_intelligence.db")
# The Neon integration normally creates DATABASE_URL. The other names keep the
# deployment compatible with the standard Vercel Postgres/Neon integrations
# without requiring a second, manually copied secret.
POSTGRES_DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or os.getenv("POSTGRES_URL_NON_POOLING")
    or os.getenv("NEON_DATABASE_URL")
)
CACHE_PATH = Path(__file__).parent / "fetchers" / "scan_cache.json"
DEFAULT_THESIS = {
    "sectors": ["AI infrastructure"],
    "stage": "pre-seed",
    "geo": ["Europe"],
    "check_size": 100000,
    "risk_appetite": "medium",
}
ALLOWED_ORIGINS = {"github", "hn", "web", "inbound", "synthetic"}
logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:10]}"


def normalized_name(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold())


def canonical_public_url(value: str) -> str:
    """Collapse display/tracking variants without changing the cited page."""

    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return value.strip()
    hostname = (parsed.hostname or "").casefold()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if not hostname:
        return value.strip()
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/") or "/"
    return f"{(parsed.scheme or 'https').casefold()}://{hostname}{path}"


def _name_tokens(value: str) -> set[str]:
    ignored = {"dr", "mr", "mrs", "ms", "prof", "founder", "cofounder"}
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 1 and token not in ignored}


def _mentions_person(value: str, person_name: str) -> bool:
    ignored = {"dr", "mr", "mrs", "ms", "prof", "founder", "cofounder"}
    ordered_person_tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", person_name.casefold())
        if len(token) > 1 and token not in ignored
    ]
    person_tokens = set(ordered_person_tokens)
    value_tokens = _name_tokens(value)
    return bool(person_tokens) and (
        person_tokens <= value_tokens
        or (len(ordered_person_tokens) >= 2 and ordered_person_tokens[0] in value_tokens)
    )


def _personal_profile_url(value: str) -> bool:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").casefold()
    path = parsed.path.casefold()
    return hostname.endswith("linkedin.com") and (path.startswith("/in/") or path.startswith("/posts/"))


def _profile_url_matches_person(value: str, person_name: str) -> bool:
    path_tokens = _name_tokens(urlparse(value).path.replace("-", " "))
    person_tokens = _name_tokens(person_name)
    if not person_tokens:
        return False
    # LinkedIn slugs normally retain the first name and surname; requiring the
    # surname plus one additional token avoids cross-linking cofounders.
    surname = list(_name_tokens(person_name.split()[-1]))
    return bool(surname and surname[0] in path_tokens and len(person_tokens & path_tokens) >= min(2, len(person_tokens)))


def live_evidence_for_founder(
    evidence: list[dict[str, Any]],
    founder_name: str,
    founder_names: list[str],
    company_name: str,
) -> list[dict[str, Any]]:
    """Attribute person-specific observations without cloning cofounder data."""

    if len(founder_names) <= 1:
        return evidence
    retained: list[dict[str, Any]] = []
    personal_types = {"technical_founder", "execution"}
    for item in evidence:
        claim = str(item.get("claim") or "")
        source_url = str(item.get("source_url") or "")
        signal_type = str(item.get("signal_type") or "")
        mentioned = [name for name in founder_names if _mentions_person(claim, name)]
        if mentioned:
            if any(normalized_name(name) == normalized_name(founder_name) for name in mentioned):
                retained.append(item)
            continue
        if _personal_profile_url(source_url):
            if _profile_url_matches_person(source_url, founder_name):
                retained.append(item)
            continue
        if signal_type in personal_types and not _mentions_person(claim, company_name):
            # Pronoun-only career statements cannot safely be copied to every
            # member of a multi-founder team.
            continue
        retained.append(item)
    return retained


def dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def loads(value: str | None, default: Any) -> Any:
    return json.loads(value) if value else default


def live_signal_source(url: str) -> str:
    hostname = (urlparse(url).hostname or "").casefold()
    if hostname == "github.com" or hostname.endswith(".github.com"):
        return "github"
    if hostname == "news.ycombinator.com" or hostname.endswith(".ycombinator.com"):
        return "hn"
    if hostname.endswith("arxiv.org"):
        return "paper"
    if hostname.endswith("devpost.com") or hostname.endswith("mlh.io"):
        return "hackathon"
    return "web"


def live_profile_origin(sources: set[str]) -> str:
    if "github" in sources:
        return "github"
    if "hn" in sources:
        return "hn"
    return "web"


def founder_score_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep diligence evidence broad while scoring only founder-relevant research."""

    excluded_application_types = {"founder_identity", "professional_profile", "product", "funding", "market"}
    retained: list[dict[str, Any]] = []
    seen_application_pages: set[str] = set()
    for signal in signals:
        text = str(signal.get("text") or "")
        match = re.match(r"Application research \[([^]|]+)(?:\|[^]]+)?\]:", text)
        if match:
            if match.group(1) in excluded_application_types:
                continue
            page = str(signal.get("url") or signal.get("signal_id") or "")
            if page in seen_application_pages:
                continue
            seen_application_pages.add(page)
        retained.append(signal)
    return retained


def parse_ts(value: str, fallback: datetime | None = None) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return fallback or datetime.now(timezone.utc)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def postgres_sql(statement: str) -> str:
    """Translate this module's DB-API SQLite placeholders for psycopg."""

    # psycopg treats every percent sign in a parameterized query as part of its
    # placeholder syntax. Escape SQL LIKE wildcards before translating the
    # SQLite-style question-mark placeholders used throughout Store.
    return statement.replace("%", "%%").replace("?", "%s")


class PostgresConnection:
    """Small adapter that lets the frozen Store queries run on Neon unchanged."""

    def __init__(self, connection: Any) -> None:
        self.raw = connection

    def execute(self, statement: str, parameters: tuple[Any, ...] = ()) -> Any:
        return self.raw.execute(postgres_sql(statement), parameters)

    def executemany(self, statement: str, parameters: list[tuple[Any, ...]]) -> Any:
        return self.raw.executemany(postgres_sql(statement), parameters)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        self.raw.close()


class Store:
    def __init__(self, path: Path | None = None, database_url: str | None = POSTGRES_DATABASE_URL) -> None:
        # An explicit path always means local SQLite. This keeps the test suite
        # and local demo self-contained even if a shell happens to export a
        # DATABASE_URL. The deployed Store() uses Neon automatically.
        self.path = path or DATABASE_PATH
        self.database_url = database_url if path is None else None
        self.initialize()
        self.deduplicate_live_signals()
        self.seed_cache()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if self.database_url:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:  # pragma: no cover - guarded by deployment requirements
                raise RuntimeError("PostgreSQL is configured but psycopg is not installed.") from exc
            connection: Any = PostgresConnection(
                psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=10)
            )
        else:
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as db:
            if self.database_url:
                for statement in (
                    """
                    CREATE TABLE IF NOT EXISTS thesis (
                      singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                      payload TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS founders (
                      founder_id TEXT PRIMARY KEY,
                      normalized_name TEXT UNIQUE NOT NULL,
                      name TEXT NOT NULL,
                      headline TEXT,
                      location TEXT,
                      origin TEXT NOT NULL,
                      bio TEXT,
                      created_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS signals (
                      signal_id TEXT PRIMARY KEY,
                      founder_id TEXT NOT NULL REFERENCES founders(founder_id),
                      ts TEXT NOT NULL,
                      source TEXT NOT NULL,
                      text TEXT NOT NULL,
                      url TEXT
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS score_history (
                      id BIGSERIAL PRIMARY KEY,
                      founder_id TEXT NOT NULL REFERENCES founders(founder_id),
                      ts TEXT NOT NULL,
                      score REAL NOT NULL,
                      band INTEGER NOT NULL,
                      trend TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS applications (
                      application_id TEXT PRIMARY KEY,
                      founder_id TEXT NOT NULL REFERENCES founders(founder_id),
                      company_name TEXT NOT NULL,
                      deck_text TEXT NOT NULL,
                      status TEXT NOT NULL,
                      axes_json TEXT,
                      diligence_json TEXT,
                      memo_json TEXT,
                      adversarial_json TEXT,
                      decision_brief_json TEXT,
                      created_at TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS claims (
                      claim_id TEXT PRIMARY KEY,
                      application_id TEXT NOT NULL REFERENCES applications(application_id),
                      type TEXT NOT NULL,
                      text TEXT NOT NULL,
                      source_span TEXT
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS audit (
                      audit_id TEXT PRIMARY KEY,
                      founder_id TEXT,
                      application_id TEXT,
                      ts TEXT NOT NULL,
                      stage TEXT NOT NULL,
                      actor TEXT NOT NULL,
                      action TEXT NOT NULL,
                      detail TEXT NOT NULL
                    )
                    """,
                    """
                    CREATE TABLE IF NOT EXISTS rag_chunks (
                      chunk_id TEXT PRIMARY KEY,
                      founder_id TEXT NOT NULL REFERENCES founders(founder_id),
                      founder_name TEXT NOT NULL,
                      source_type TEXT NOT NULL,
                      source_id TEXT NOT NULL,
                      label TEXT NOT NULL,
                      url TEXT,
                      content TEXT NOT NULL,
                      content_hash TEXT NOT NULL,
                      embedding_json TEXT,
                      updated_at TEXT NOT NULL
                    )
                    """,
                    "CREATE INDEX IF NOT EXISTS idx_rag_chunks_founder_id ON rag_chunks(founder_id)",
                ):
                    db.execute(statement)
            else:
                db.executescript(
                    """
                    PRAGMA foreign_keys = ON;
                    CREATE TABLE IF NOT EXISTS thesis (
                      singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                      payload TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS founders (
                      founder_id TEXT PRIMARY KEY,
                      normalized_name TEXT UNIQUE NOT NULL,
                      name TEXT NOT NULL,
                      headline TEXT,
                      location TEXT,
                      origin TEXT NOT NULL,
                      bio TEXT,
                      created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS signals (
                      signal_id TEXT PRIMARY KEY,
                      founder_id TEXT NOT NULL,
                      ts TEXT NOT NULL,
                      source TEXT NOT NULL,
                      text TEXT NOT NULL,
                      url TEXT,
                      FOREIGN KEY(founder_id) REFERENCES founders(founder_id)
                    );
                    CREATE TABLE IF NOT EXISTS score_history (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      founder_id TEXT NOT NULL,
                      ts TEXT NOT NULL,
                      score REAL NOT NULL,
                      band INTEGER NOT NULL,
                      trend TEXT NOT NULL,
                      FOREIGN KEY(founder_id) REFERENCES founders(founder_id)
                    );
                    CREATE TABLE IF NOT EXISTS applications (
                      application_id TEXT PRIMARY KEY,
                      founder_id TEXT NOT NULL,
                      company_name TEXT NOT NULL,
                      deck_text TEXT NOT NULL,
                      status TEXT NOT NULL,
                      axes_json TEXT,
                      diligence_json TEXT,
                      memo_json TEXT,
                      adversarial_json TEXT,
                      decision_brief_json TEXT,
                      created_at TEXT NOT NULL,
                      FOREIGN KEY(founder_id) REFERENCES founders(founder_id)
                    );
                    CREATE TABLE IF NOT EXISTS claims (
                      claim_id TEXT PRIMARY KEY,
                      application_id TEXT NOT NULL,
                      type TEXT NOT NULL,
                      text TEXT NOT NULL,
                      source_span TEXT,
                      FOREIGN KEY(application_id) REFERENCES applications(application_id)
                    );
                    CREATE TABLE IF NOT EXISTS audit (
                      audit_id TEXT PRIMARY KEY,
                      founder_id TEXT,
                      application_id TEXT,
                      ts TEXT NOT NULL,
                      stage TEXT NOT NULL,
                      actor TEXT NOT NULL,
                      action TEXT NOT NULL,
                      detail TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS rag_chunks (
                      chunk_id TEXT PRIMARY KEY,
                      founder_id TEXT NOT NULL,
                      founder_name TEXT NOT NULL,
                      source_type TEXT NOT NULL,
                      source_id TEXT NOT NULL,
                      label TEXT NOT NULL,
                      url TEXT,
                      content TEXT NOT NULL,
                      content_hash TEXT NOT NULL,
                      embedding_json TEXT,
                      updated_at TEXT NOT NULL,
                      FOREIGN KEY(founder_id) REFERENCES founders(founder_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_rag_chunks_founder_id ON rag_chunks(founder_id);
                    """
                )
            existing = db.execute("SELECT payload FROM thesis WHERE singleton = 1").fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO thesis(singleton, payload, updated_at) VALUES(1, ?, ?) ON CONFLICT (singleton) DO NOTHING",
                    (dumps(DEFAULT_THESIS), now_iso()),
                )

    def get_thesis(self) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute("SELECT payload FROM thesis WHERE singleton = 1").fetchone()
        return loads(row["payload"] if row else None, DEFAULT_THESIS)

    def set_thesis(self, thesis: dict[str, Any]) -> None:
        if thesis.get("check_size") != 100000:
            raise HTTPException(422, "check_size must be 100000.")
        if thesis.get("risk_appetite") not in {"low", "medium", "high"}:
            raise HTTPException(422, "risk_appetite must be low, medium, or high.")
        for field in ("sectors", "geo"):
            if not isinstance(thesis.get(field), list) or not all(isinstance(item, str) for item in thesis[field]):
                raise HTTPException(422, f"{field} must be a string array.")
        if not isinstance(thesis.get("stage"), str) or not thesis["stage"].strip():
            raise HTTPException(422, "stage is required.")
        with self.connection() as db:
            db.execute(
                "UPDATE thesis SET payload = ?, updated_at = ? WHERE singleton = 1",
                (dumps(thesis), now_iso()),
            )

    def seed_cache(self) -> tuple[int, int]:
        cache = loads(CACHE_PATH.read_text(encoding="utf-8"), {"founders": []})
        new_founders = 0
        new_signals = 0
        with self.connection() as db:
            for record in cache.get("founders", []):
                name = str(record["name"])
                key = normalized_name(name)
                founder = db.execute("SELECT founder_id FROM founders WHERE normalized_name = ?", (key,)).fetchone()
                if founder is None:
                    founder_id = stable_id("fndr", key)
                    db.execute(
                        "INSERT INTO founders VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            founder_id,
                            key,
                            name,
                            record.get("headline"),
                            record.get("location"),
                            record.get("origin") if record.get("origin") in ALLOWED_ORIGINS else "synthetic",
                            record.get("bio"),
                            now_iso(),
                        ),
                    )
                    new_founders += 1
                else:
                    founder_id = founder["founder_id"]
                for signal in record.get("signals", []):
                    signal_id = str(signal["signal_id"])
                    exists = db.execute("SELECT 1 FROM signals WHERE signal_id = ?", (signal_id,)).fetchone()
                    if exists is None:
                        db.execute(
                            "INSERT INTO signals VALUES(?, ?, ?, ?, ?, ?)",
                            (signal_id, founder_id, signal["ts"], signal["source"], signal["text"], signal.get("url")),
                        )
                        new_signals += 1
                self._record_score(db, founder_id, cache.get("generated_at") or now_iso())
                self._audit(db, founder_id, None, "ingest", "system", "loaded_cached_signals", "Loaded reviewed cache signals.")
        return new_founders, new_signals

    def ingest_live_discovery(
        self,
        sourcing_result: dict[str, Any],
        discovery_batch_id: str | None = None,
    ) -> tuple[int, int]:
        """Promote source-backed, reviewable live leads into product Memory.

        The sourcing workflow has already ranked evidence coverage. This layer
        keeps both fully covered candidates and source-backed leads that need
        human review, while rejecting positive public VC-funding exclusions.
        It stores at most twelve deduplicated signals per candidate and never
        treats an absence of funding evidence as proof of no funding.
        """

        discovery = sourcing_result.get("discovery") if isinstance(sourcing_result.get("discovery"), dict) else {}
        ranking = sourcing_result.get("ranking") if isinstance(sourcing_result.get("ranking"), dict) else {}
        evidence_by_candidate: dict[str, list[dict[str, Any]]] = {}
        for evidence in discovery.get("evidence", []):
            if isinstance(evidence, dict) and evidence.get("candidate_id") and evidence.get("source_url") and evidence.get("claim"):
                evidence_by_candidate.setdefault(str(evidence["candidate_id"]), []).append(evidence)

        batch_id = discovery_batch_id or stable_id("scan", now_iso(), uuid.uuid4().hex)
        batch_ts = now_iso()
        batch_started_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        new_founders = 0
        new_signals = 0
        with self.connection() as db:
            for candidate in ranking.get("ranked_candidates", []):
                # Different user theses do not necessarily contain the
                # challenge's original Europe + AI-infrastructure signal set.
                # Preserve cited lower-coverage leads for human review; only a
                # positive funding conflict is excluded from Memory.
                if not isinstance(candidate, dict) or candidate.get("status") not in {"candidate", "needs_review"}:
                    continue
                candidate_id = str(candidate.get("candidate_id") or "")
                founder_names = [str(name).strip() for name in candidate.get("founder_names", []) if str(name).strip()]
                candidate_evidence = evidence_by_candidate.get(candidate_id, [])
                if not founder_names or not candidate_evidence:
                    continue

                deduplicated: list[dict[str, Any]] = []
                # A single page can support one observation of each signal
                # type. Repeatedly matching different sentences on that same
                # page must not inflate the deterministic Founder Score.
                seen_source_types: set[tuple[str, str]] = set()
                seen_claims: set[tuple[str, str]] = set()
                for evidence in candidate_evidence:
                    source_type_key = (
                        str(evidence.get("signal_type") or ""),
                        canonical_public_url(str(evidence.get("source_url") or "")),
                    )
                    claim_key = (
                        canonical_public_url(str(evidence.get("source_url") or "")),
                        re.sub(r"\s+", " ", str(evidence.get("claim") or "")).strip().casefold(),
                    )
                    if source_type_key in seen_source_types or claim_key in seen_claims:
                        continue
                    seen_source_types.add(source_type_key)
                    seen_claims.add(claim_key)
                    deduplicated.append(evidence)
                    if len(deduplicated) == 12:
                        break
                for founder_name in founder_names:
                    founder_evidence = live_evidence_for_founder(
                        deduplicated,
                        founder_name,
                        founder_names,
                        str(candidate.get("company_name") or ""),
                    )
                    acquisition_sources = {live_signal_source(str(item["source_url"])) for item in founder_evidence}
                    profile_origin = live_profile_origin(acquisition_sources)
                    key = normalized_name(founder_name)
                    founder = db.execute("SELECT founder_id, origin FROM founders WHERE normalized_name = ?", (key,)).fetchone()
                    if founder is None:
                        founder_id = stable_id("fndr", key)
                        db.execute(
                            "INSERT INTO founders VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                founder_id,
                                key,
                                founder_name,
                                f"Technical public-web lead linked to {candidate.get('company_name') or 'an unverified company'}.",
                                None,
                                profile_origin,
                                "Live-sourced public-web lead. Every displayed signal links to its source; identity, traction, and funding status require human review.",
                                batch_ts,
                            ),
                        )
                        new_founders += 1
                    else:
                        founder_id = founder["founder_id"]
                        if founder["origin"] == "synthetic":
                            db.execute(
                                "UPDATE founders SET origin = ?, bio = ? WHERE founder_id = ?",
                                (
                                    profile_origin,
                                    "Live public-web signals were added. Identity, traction, and funding status require human review.",
                                    founder_id,
                                ),
                            )

                    # A re-scan refreshes the active, source-backed evidence
                    # from URLs it crawled successfully. It does not preserve
                    # stale keyword matches from a prior crawl of that page.
                    # Clear every URL from this candidate before inserting the
                    # founder-attributed subset. This also repairs records from
                    # older builds that cloned all cofounder evidence.
                    refreshed_urls = sorted({canonical_public_url(str(item["source_url"])) for item in deduplicated})
                    placeholders = ", ".join("?" for _ in refreshed_urls)
                    db.execute(
                        f"DELETE FROM signals WHERE founder_id = ? AND text LIKE 'Live %' AND url IN ({placeholders})",
                        (founder_id, *refreshed_urls),
                    )

                    for evidence in founder_evidence:
                        source_url = canonical_public_url(str(evidence["source_url"]))
                        signal_id = stable_id("sig", "live", founder_id, evidence.get("evidence_id"), source_url)
                        exists = db.execute("SELECT 1 FROM signals WHERE signal_id = ?", (signal_id,)).fetchone()
                        if exists is not None:
                            continue
                        signal_type = str(evidence.get("signal_type") or "public-web").replace("_", " ")
                        db.execute(
                            "INSERT INTO signals VALUES(?, ?, ?, ?, ?, ?)",
                            (
                                signal_id,
                                founder_id,
                                str(evidence.get("captured_at") or now_iso()),
                                live_signal_source(source_url),
                                f"Live {signal_type}: {str(evidence['claim']).strip()}",
                                source_url,
                            ),
                        )
                        new_signals += 1
                    self._record_score(db, founder_id, batch_ts)
                    self._audit(
                        db,
                        founder_id,
                        None,
                        "ingest",
                        "live-sourcing",
                        "ingested_public_web_signals",
                        dumps(
                            {
                                "batch_id": batch_id,
                                "batch_started_at": batch_started_at,
                                "company_name": str(candidate.get("company_name") or ""),
                                "stored_signals": len(founder_evidence),
                            }
                        ),
                    )
        return new_founders, new_signals

    def deduplicate_live_signals(self) -> int:
        """Remove legacy duplicate live signals that share one source and claim.

        A crawler page may contain one passage that matches several broad signal
        categories. The original importer stored each category separately, so a
        founder profile could render the same source text multiple times. Keep
        the most useful category for that passage and refresh the score after
        removing the redundant records.
        """

        def claim_key(row: Any) -> tuple[str, str] | None:
            text = str(row["text"] or "")
            if not text.startswith("Live ") or ":" not in text:
                return None
            claim = text.split(":", 1)[1]
            return (canonical_public_url(str(row["url"] or "")), re.sub(r"\s+", " ", claim).strip().casefold())

        def priority(row: Any) -> tuple[int, str]:
            text = str(row["text"] or "").casefold()
            category = text.split(":", 1)[0]
            ranks = {
                "live technical founder": 0,
                "live execution": 1,
                "live product traction": 2,
                "live ai infrastructure": 3,
            }
            return (ranks.get(category, 99), str(row["signal_id"]))

        with self.connection() as db:
            founder_rows = db.execute("SELECT founder_id, name FROM founders").fetchall()
            founder_names = {str(row["founder_id"]): str(row["name"]) for row in founder_rows}
            rows = db.execute(
                "SELECT signal_id, founder_id, text, url FROM signals WHERE text LIKE 'Live %' AND url IS NOT NULL"
            ).fetchall()
            named_people_by_url: dict[str, set[str]] = {}
            for row in rows:
                text = str(row["text"] or "")
                url = canonical_public_url(str(row["url"] or ""))
                named_people_by_url.setdefault(url, set()).update(
                    founder_id
                    for founder_id, name in founder_names.items()
                    if _mentions_person(text, name)
                )

            removed_by_founder: dict[str, int] = {}
            removed_signal_ids: set[str] = set()
            for row in rows:
                founder_id = str(row["founder_id"])
                signal_id = str(row["signal_id"])
                text = str(row["text"] or "")
                category = text.split(":", 1)[0].casefold()
                named_ids = named_people_by_url.get(canonical_public_url(str(row["url"] or "")), set())
                explicitly_named_here = {
                    other_id
                    for other_id, other_name in founder_names.items()
                    if _mentions_person(text, other_name)
                }
                wrong_explicit_person = bool(explicitly_named_here) and founder_id not in explicitly_named_here
                personal_owner_mismatch = _personal_profile_url(str(row["url"] or "")) and not _profile_url_matches_person(
                    str(row["url"] or ""), founder_names.get(founder_id, "")
                )
                ambiguous_person_signal = (
                    category in {"live technical founder", "live execution"}
                    and bool(named_ids)
                    and founder_id not in named_ids
                )
                if wrong_explicit_person or personal_owner_mismatch or ambiguous_person_signal:
                    db.execute("DELETE FROM signals WHERE signal_id = ?", (signal_id,))
                    removed_signal_ids.add(signal_id)
                    removed_by_founder[founder_id] = removed_by_founder.get(founder_id, 0) + 1

            grouped: dict[tuple[str, str, str], list[Any]] = {}
            for row in rows:
                if str(row["signal_id"]) in removed_signal_ids:
                    continue
                key = claim_key(row)
                if key is not None:
                    grouped.setdefault((str(row["founder_id"]), *key), []).append(row)
            for records in grouped.values():
                for duplicate in sorted(records, key=priority)[1:]:
                    db.execute("DELETE FROM signals WHERE signal_id = ?", (duplicate["signal_id"],))
                    founder_id = str(duplicate["founder_id"])
                    removed_by_founder[founder_id] = removed_by_founder.get(founder_id, 0) + 1

            if removed_by_founder:
                snapshot_ts = now_iso()
                for founder_id, removed in removed_by_founder.items():
                    self._record_score(db, founder_id, snapshot_ts)
                    self._audit(
                        db,
                        founder_id,
                        None,
                        "ingest",
                        "system",
                        "deduplicated_live_signals",
                        f"Removed {removed} duplicate or cross-founder live signal record(s).",
                    )
        return sum(removed_by_founder.values())

    def _signals(self, db: Any, founder_id: str) -> list[dict[str, Any]]:
        rows = db.execute(
            "SELECT signal_id, ts, source, text, url FROM signals WHERE founder_id = ? ORDER BY ts DESC",
            (founder_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _record_score(self, db: Any, founder_id: str, snapshot_ts: str) -> dict[str, Any]:
        signals = founder_score_signals(self._signals(db, founder_id))
        snapshot = parse_ts(snapshot_ts)
        source_diversity = len({str(signal["source"]).strip().casefold() for signal in signals})
        recent = sum(1 for signal in signals if snapshot - timedelta(days=30) <= parse_ts(signal["ts"]) <= snapshot)
        count = len({signal["signal_id"] for signal in signals})
        score = max(0, min(100, 35 + 8 * source_diversity + 4 * recent + 2 * count))
        band = math.floor(max(5, min(30, 60 / math.sqrt(count + 1))))
        previous = db.execute(
            "SELECT score FROM score_history WHERE founder_id = ? ORDER BY id DESC LIMIT 1", (founder_id,)
        ).fetchone()
        delta = score - float(previous["score"]) if previous else 0
        trend = "up" if delta >= 3 else "down" if delta <= -3 else "flat"
        last = db.execute(
            "SELECT score, band FROM score_history WHERE founder_id = ? ORDER BY id DESC LIMIT 1", (founder_id,)
        ).fetchone()
        if last is None or last["score"] != score or last["band"] != band:
            db.execute(
                "INSERT INTO score_history(founder_id, ts, score, band, trend) VALUES(?, ?, ?, ?, ?)",
                (founder_id, snapshot_ts, score, band, trend),
            )
        return {"score": score, "band": band, "trend": trend}

    def score(self, founder_id: str) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute(
                "SELECT score, band, trend FROM score_history WHERE founder_id = ? ORDER BY id DESC LIMIT 1", (founder_id,)
            ).fetchone()
            if row is None:
                return self._record_score(db, founder_id, now_iso())
            return dict(row)

    def dashboard(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            latest_batch_id: str | None = None
            latest_batch_founders: set[str] = set()
            live_audits = db.execute(
                "SELECT founder_id, detail FROM audit WHERE action = 'ingested_public_web_signals' ORDER BY ts DESC LIMIT 500"
            ).fetchall()
            parsed_audits: list[tuple[str, str, str]] = []
            for audit in live_audits:
                try:
                    detail = json.loads(str(audit["detail"] or ""))
                except (TypeError, json.JSONDecodeError):
                    continue
                batch_id = str(detail.get("batch_id") or "") if isinstance(detail, dict) else ""
                if not batch_id:
                    continue
                batch_started_at = str(detail.get("batch_started_at") or "")
                parsed_audits.append((str(audit["founder_id"] or ""), batch_id, batch_started_at))
            if parsed_audits:
                latest_batch_id = max(parsed_audits, key=lambda item: item[2])[1]
            if latest_batch_id:
                latest_batch_founders = {
                    founder_id for founder_id, batch_id, _ in parsed_audits if batch_id == latest_batch_id
                }
            founders = db.execute("SELECT * FROM founders ORDER BY name").fetchall()
            output = []
            for founder in founders:
                score = self._record_score(db, founder["founder_id"], now_iso())
                top_signals = self._signals(db, founder["founder_id"])[:2]
                open_app = db.execute(
                    "SELECT 1 FROM applications WHERE founder_id = ? AND status = 'open' LIMIT 1", (founder["founder_id"],)
                ).fetchone()
                output.append(
                    {
                        "founder_id": founder["founder_id"],
                        "name": founder["name"],
                        "origin": founder["origin"],
                        "founder_score": score["score"],
                        "band": score["band"],
                        "trend": score["trend"],
                        "top_signals": [signal["text"] for signal in top_signals],
                        "has_open_app": bool(open_app),
                        "is_new": founder["founder_id"] in latest_batch_founders,
                    }
                )
        return sorted(output, key=lambda item: item["founder_score"], reverse=True)

    def founder_search_context(self, founder_id: str) -> list[str]:
        """Return company names linked to a founder without changing Profile."""

        with self.connection() as db:
            rows = db.execute(
                "SELECT DISTINCT company_name FROM applications WHERE founder_id = ?",
                (founder_id,),
            ).fetchall()
        return [str(row["company_name"]) for row in rows if str(row["company_name"] or "").strip()]

    def find_founder(self, founder_id: str) -> Any:
        with self.connection() as db:
            founder = db.execute("SELECT * FROM founders WHERE founder_id = ?", (founder_id,)).fetchone()
        if founder is None:
            raise HTTPException(404, "Founder not found.")
        return founder

    def founder_profile(self, founder_id: str) -> dict[str, Any]:
        founder = self.find_founder(founder_id)
        with self.connection() as db:
            signals = self._signals(db, founder_id)
            history = [
                {"ts": row["ts"], "score": row["score"], "band": row["band"]}
                for row in db.execute(
                    "SELECT ts, score, band FROM score_history WHERE founder_id = ? ORDER BY id", (founder_id,)
                ).fetchall()
            ]
            applications = [
                row["application_id"]
                for row in db.execute(
                    "SELECT application_id FROM applications WHERE founder_id = ? ORDER BY created_at DESC", (founder_id,)
                ).fetchall()
            ]
        return {
            "profile": {
                "founder_id": founder["founder_id"],
                "name": founder["name"],
                "headline": founder["headline"],
                "location": founder["location"],
                "origin": founder["origin"],
                "bio": founder["bio"],
            },
            "signals": signals,
            "score_history": history,
            "applications": applications,
        }

    @staticmethod
    def _rag_content(value: Any) -> str:
        if isinstance(value, str):
            return re.sub(r"\s+", " ", value).strip()[:2400]
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(", ", ": "))[:2400]

    def _build_rag_chunks(self, db: Any, founder_id: str) -> list[dict[str, Any]]:
        founder = db.execute("SELECT * FROM founders WHERE founder_id = ?", (founder_id,)).fetchone()
        if founder is None:
            raise HTTPException(404, "Founder not found.")
        founder_name = str(founder["name"])
        chunks: list[dict[str, Any]] = []

        def add(source_type: str, source_id: str, label: str, value: Any, url: str | None = None) -> None:
            content = self._rag_content(value)
            if not content:
                return
            chunks.append(
                {
                    "chunk_id": stable_id("rag", founder_id, source_type, source_id, label),
                    "founder_id": founder_id,
                    "founder_name": founder_name,
                    "source_type": source_type,
                    "source_id": source_id,
                    "label": label,
                    "url": url,
                    "content": content,
                    "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                }
            )

        add(
            "profile",
            founder_id,
            "Founder profile",
            {
                "name": founder_name,
                "headline": founder["headline"],
                "location": founder["location"],
                "origin": founder["origin"],
                "bio": founder["bio"],
            },
        )
        for signal in db.execute(
            "SELECT signal_id, ts, source, text, url FROM signals WHERE founder_id = ? ORDER BY ts DESC",
            (founder_id,),
        ).fetchall():
            add(
                "evidence",
                str(signal["signal_id"]),
                f"Evidence · {signal['source']}",
                {"captured_at": signal["ts"], "source": signal["source"], "claim": signal["text"]},
                signal["url"],
            )

        applications = db.execute(
            "SELECT * FROM applications WHERE founder_id = ? ORDER BY created_at DESC", (founder_id,)
        ).fetchall()
        for application in applications:
            application_id = str(application["application_id"])
            company_name = str(application["company_name"])
            add(
                "application",
                application_id,
                f"Application · {company_name}",
                {"company": company_name, "status": application["status"], "created_at": application["created_at"]},
            )
            for claim in db.execute(
                "SELECT claim_id, type, text, source_span FROM claims WHERE application_id = ?", (application_id,)
            ).fetchall():
                add(
                    "claim",
                    str(claim["claim_id"]),
                    f"Submitted claim · {company_name}",
                    {"type": claim["type"], "claim": claim["text"], "source_span": claim["source_span"]},
                )
            structured_fields = (
                ("screening", "axes_json", "Screening axes"),
                ("diligence", "diligence_json", "Truth-gap diligence"),
                ("memo", "memo_json", "Investment memo"),
                ("adversary", "adversarial_json", "Devil's advocate report"),
                ("decision_brief", "decision_brief_json", "Decision brief"),
            )
            for source_type, column, label in structured_fields:
                parsed = loads(application[column], None)
                if parsed is not None:
                    add(source_type, application_id, f"{label} · {company_name}", parsed)
        return chunks

    def sync_rag_chunks(self, founder_id: str | None = None) -> list[dict[str, Any]]:
        """Upsert current Memory chunks while retaining unchanged embeddings."""

        with self.connection() as db:
            if founder_id:
                founder_ids = [founder_id]
            else:
                founder_ids = [str(row["founder_id"]) for row in db.execute("SELECT founder_id FROM founders").fetchall()]
            for current_founder_id in founder_ids:
                chunks = self._build_rag_chunks(db, current_founder_id)
                current_ids = {str(chunk["chunk_id"]) for chunk in chunks}
                existing = {
                    str(row["chunk_id"]): row
                    for row in db.execute(
                        """SELECT chunk_id, founder_name, source_type, source_id, label, url,
                                  content_hash, embedding_json
                           FROM rag_chunks WHERE founder_id = ?""",
                        (current_founder_id,),
                    ).fetchall()
                }
                for chunk in chunks:
                    previous = existing.get(str(chunk["chunk_id"]))
                    unchanged = previous is not None and all(
                        previous[field] == chunk[field]
                        for field in ("founder_name", "source_type", "source_id", "label", "url", "content_hash")
                    )
                    if unchanged:
                        continue
                    embedding_json = (
                        previous["embedding_json"]
                        if previous is not None and previous["content_hash"] == chunk["content_hash"]
                        else None
                    )
                    db.execute(
                        """INSERT INTO rag_chunks(
                             chunk_id, founder_id, founder_name, source_type, source_id, label, url,
                             content, content_hash, embedding_json, updated_at
                           ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT (chunk_id) DO UPDATE SET
                             founder_name = excluded.founder_name,
                             source_type = excluded.source_type,
                             source_id = excluded.source_id,
                             label = excluded.label,
                             url = excluded.url,
                             content = excluded.content,
                             content_hash = excluded.content_hash,
                             embedding_json = excluded.embedding_json,
                             updated_at = excluded.updated_at""",
                        (
                            chunk["chunk_id"], chunk["founder_id"], chunk["founder_name"],
                            chunk["source_type"], chunk["source_id"], chunk["label"], chunk["url"],
                            chunk["content"], chunk["content_hash"], embedding_json, now_iso(),
                        ),
                    )
                stale_ids = set(existing) - current_ids
                for stale_id in stale_ids:
                    db.execute("DELETE FROM rag_chunks WHERE chunk_id = ?", (stale_id,))
            if not founder_ids:
                return []
            if founder_id:
                rows = db.execute(
                    "SELECT * FROM rag_chunks WHERE founder_id = ? ORDER BY founder_name, source_type, label",
                    (founder_id,),
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM rag_chunks ORDER BY founder_name, source_type, label").fetchall()
        return [dict(row) for row in rows]

    def save_rag_embeddings(self, updates: dict[str, list[float]]) -> None:
        if not updates:
            return
        with self.connection() as db:
            updated_at = now_iso()
            db.executemany(
                "UPDATE rag_chunks SET embedding_json = ?, updated_at = ? WHERE chunk_id = ?",
                [(dumps(embedding), updated_at, chunk_id) for chunk_id, embedding in updates.items()],
            )

    def resolve_or_create_founder(self, name: str) -> str:
        key = normalized_name(name)
        with self.connection() as db:
            row = db.execute("SELECT founder_id FROM founders WHERE normalized_name = ?", (key,)).fetchone()
            if row:
                return row["founder_id"]
            founder_id = stable_id("fndr", key)
            db.execute(
                "INSERT INTO founders VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (founder_id, key, name, None, None, "inbound", "Founder introduced via an inbound application.", now_iso()),
            )
            self._record_score(db, founder_id, now_iso())
            self._audit(db, founder_id, None, "ingest", "system", "created_inbound_founder", "Created a founder record from deck identity.")
        return founder_id

    def create_application(self, company_name: str, deck_text: str, extracted: dict[str, Any]) -> dict[str, Any]:
        founder_id = self.resolve_or_create_founder(str(extracted["founder_name"]))
        application_id = stable_id("app", company_name, founder_id, deck_text)
        claims = extracted.get("claims", [])
        if any(
            not isinstance(claim, dict)
            or (claim.get("source_span") is not None and claim.get("source_span") not in deck_text)
            for claim in claims
        ):
            raise HTTPException(422, "Every non-null claim source_span must exactly quote the deck text.")
        with self.connection() as db:
            existing = db.execute("SELECT application_id FROM applications WHERE application_id = ?", (application_id,)).fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO applications VALUES(?, ?, ?, ?, 'open', NULL, NULL, NULL, NULL, NULL, ?)",
                    (application_id, founder_id, company_name, deck_text, now_iso()),
                )
                for claim in claims:
                    db.execute(
                        """
                        INSERT INTO claims(claim_id, application_id, type, text, source_span)
                        VALUES(?, ?, ?, ?, ?)
                        ON CONFLICT (claim_id) DO UPDATE SET
                          application_id = excluded.application_id,
                          type = excluded.type,
                          text = excluded.text,
                          source_span = excluded.source_span
                        """,
                        (claim["claim_id"], application_id, claim["type"], claim["text"], claim["source_span"]),
                    )
                self._audit(db, founder_id, application_id, "extract", "system", "extracted_claims", f"Extracted {len(claims)} typed deck claims.")
        return {"application_id": application_id, "founder_id": founder_id, "claims": claims}

    def ingest_application_research(self, application_id: str, research: dict[str, Any]) -> tuple[int, int]:
        """Store bounded public-web observations against the application's resolved founder."""

        app = self.application_row(application_id)
        observations = research.get("observations") if isinstance(research.get("observations"), list) else []
        inserted = 0
        with self.connection() as db:
            for observation in observations[:10]:
                if not isinstance(observation, dict):
                    continue
                source_url = canonical_public_url(str(observation.get("source_url") or "").strip())
                evidence_type = str(observation.get("evidence_type") or "").strip()
                source_relationship = str(observation.get("source_relationship") or "unknown").strip()
                claim = re.sub(r"\s+", " ", str(observation.get("claim") or "")).strip()
                if not source_url or not evidence_type or not claim:
                    continue
                signal_id = stable_id("sig", "application-research", app["founder_id"], source_url, evidence_type)
                # Repeated web searches may paraphrase the same fact. One URL
                # contributes at most one Memory record per evidence type.
                db.execute(
                    "DELETE FROM signals WHERE founder_id = ? AND url = ? AND text LIKE ? AND signal_id != ?",
                    (app["founder_id"], source_url, f"Application research [{evidence_type}%", signal_id),
                )
                exists = db.execute("SELECT 1 FROM signals WHERE signal_id = ?", (signal_id,)).fetchone()
                crawl_note = "crawl-confirmed" if observation.get("crawl_verified") is True else "search-cited; crawl review pending"
                signal_text = f"Application research [{evidence_type}|{source_relationship}]: {claim} ({crawl_note})"
                if exists is None:
                    db.execute(
                        "INSERT INTO signals VALUES(?, ?, ?, ?, ?, ?)",
                        (signal_id, app["founder_id"], now_iso(), live_signal_source(source_url), signal_text, source_url),
                    )
                    inserted += 1
                else:
                    db.execute(
                        "UPDATE signals SET ts = ?, source = ?, text = ? WHERE signal_id = ?",
                        (now_iso(), live_signal_source(source_url), signal_text, signal_id),
                    )
            self._record_score(db, app["founder_id"], now_iso())
            limitations = research.get("limitations") if isinstance(research.get("limitations"), list) else []
            self._audit(
                db,
                app["founder_id"],
                application_id,
                "research",
                "live-web",
                "researched_inbound_application",
                f"Retained {inserted} new URL-cited public-web observations; {len(limitations)} limitation(s).",
            )
        return inserted, len(observations)

    def application_row(self, application_id: str) -> Any:
        with self.connection() as db:
            row = db.execute("SELECT * FROM applications WHERE application_id = ?", (application_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Application not found.")
        return row

    def claims(self, application_id: str) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT claim_id, type, text, source_span FROM claims WHERE application_id = ?", (application_id,)).fetchall()
        return [dict(row) for row in rows]

    def application(self, application_id: str) -> dict[str, Any]:
        app = self.application_row(application_id)
        application_claims = self.claims(application_id)
        axes = loads(app["axes_json"], None)
        diligence = loads(app["diligence_json"], None)
        memo = loads(app["memo_json"], None)
        adversarial = loads(app["adversarial_json"], None)
        decision_brief = loads(app["decision_brief_json"], None)
        evidence_ids: set[str] = set()
        if diligence:
            for claim in diligence.get("claims", []):
                evidence_ids.update(claim.get("evidence", []))
        if adversarial:
            for objection in adversarial.get("objections", []):
                evidence_ids.update(objection.get("evidence") or [])
        with self.connection() as db:
            founder_signals = self._signals(db, app["founder_id"])
            evidence = [
                dict(row)
                for row in db.execute(
                    f"SELECT signal_id, ts, source, text, url FROM signals WHERE signal_id IN ({','.join('?' for _ in evidence_ids)})",
                    tuple(sorted(evidence_ids)),
                ).fetchall()
            ] if evidence_ids else []
        # Research evidence is reviewable immediately after screening, before
        # the diligence judge selects claim-specific evidence IDs.
        evidence_by_id = {str(item["signal_id"]): item for item in evidence}
        evidence_by_id.update(
            {
                str(signal["signal_id"]): signal
                for signal in founder_signals
                if str(signal.get("text") or "").startswith("Application research [")
            }
        )
        evidence = list(evidence_by_id.values())
        if isinstance(diligence, dict):
            diligence = product_pipeline.normalize_diligence_result(
                diligence,
                application_claims,
                founder_signals,
            )
        if isinstance(axes, dict):
            founder_score = self.score(app["founder_id"])
            axes = dict(axes)
            axes["founder"] = product_pipeline.founder_axis_from_evidence(
                float(founder_score["score"]),
                int(founder_score["band"]),
                str(founder_score["trend"]),
                founder_score_signals(founder_signals),
            )
        return {
            "application_id": app["application_id"],
            "founder_id": app["founder_id"],
            "company_name": app["company_name"],
            "status": app["status"],
            "claims": application_claims,
            "axes": axes,
            "diligence": diligence,
            "memo": memo,
            "adversarial": adversarial,
            "validator_report": validator_report(adversarial, founder_signals) if isinstance(adversarial, dict) else None,
            "decision_brief": decision_brief,
            "evidence": evidence,
        }

    def update_stage(self, application_id: str, column: str, value: dict[str, Any], stage: str, detail: str) -> None:
        if column not in {"axes_json", "diligence_json", "memo_json", "adversarial_json", "decision_brief_json"}:
            raise ValueError("Invalid stage column.")
        app = self.application_row(application_id)
        with self.connection() as db:
            db.execute(f"UPDATE applications SET {column} = ? WHERE application_id = ?", (dumps(value), application_id))
            self._audit(db, app["founder_id"], application_id, stage, "system", f"completed_{stage}", detail)

    def decision(self, application_id: str, action: str, approver: str) -> dict[str, Any]:
        app = self.application_row(application_id)
        if action not in {"approve", "reject"} or not approver.strip():
            raise HTTPException(422, "action and approver are required.")
        status = "approved" if action == "approve" else "rejected"
        audit_id = stable_id("audit", application_id, status, approver, now_iso())
        with self.connection() as db:
            db.execute("UPDATE applications SET status = ? WHERE application_id = ?", (status, application_id))
            self._audit(db, app["founder_id"], application_id, "decision", approver, status, "Human decision recorded.", audit_id)
        return {"status": status, "audit_id": audit_id}

    def _audit(
        self,
        db: Any,
        founder_id: str | None,
        application_id: str | None,
        stage: str,
        actor: str,
        action: str,
        detail: str,
        audit_id: str | None = None,
    ) -> None:
        db.execute(
            "INSERT INTO audit VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (
                audit_id or stable_id("audit", founder_id, application_id, stage, action, now_iso(), uuid.uuid4().hex),
                founder_id,
                application_id,
                now_iso(),
                stage,
                actor,
                action,
                detail,
            ),
        )

    def audit(self, founder_id: str | None) -> list[dict[str, Any]]:
        with self.connection() as db:
            if founder_id:
                rows = db.execute(
                    "SELECT ts, stage, actor, action, detail FROM audit WHERE founder_id = ? ORDER BY ts DESC", (founder_id,)
                ).fetchall()
            else:
                rows = db.execute("SELECT ts, stage, actor, action, detail FROM audit ORDER BY ts DESC").fetchall()
        return [dict(row) for row in rows]

    def queue(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT application_id, company_name, memo_json FROM applications WHERE status = 'open' AND memo_json IS NOT NULL ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "application_id": row["application_id"],
                "company": row["company_name"],
                "recommendation": loads(row["memo_json"], {})["recommendation"],
                "memo_id": loads(row["memo_json"], {})["memo_id"],
            }
            for row in rows
        ]

    def metrics(self) -> dict[str, Any]:
        with self.connection() as db:
            sourced = db.execute("SELECT COUNT(*) AS count FROM founders").fetchone()["count"]
            screened = db.execute("SELECT COUNT(*) AS count FROM applications WHERE axes_json IS NOT NULL").fetchone()["count"]
            diligenced = db.execute("SELECT COUNT(*) AS count FROM applications WHERE diligence_json IS NOT NULL").fetchone()["count"]
            decided = db.execute("SELECT COUNT(*) AS count FROM applications WHERE status IN ('approved', 'rejected')").fetchone()["count"]
            rows = db.execute(
                """
                SELECT MIN(ingested.ts) AS first_signal, MAX(a.ts) AS decided_at
                FROM applications app
                JOIN audit ingested ON ingested.founder_id = app.founder_id AND ingested.stage = 'ingest'
                JOIN audit a ON a.application_id = app.application_id AND a.stage = 'decision'
                GROUP BY app.application_id
                """
            ).fetchall()
        durations = [(parse_ts(row["decided_at"]) - parse_ts(row["first_signal"])).total_seconds() / 60 for row in rows]
        durations.sort()
        median = None if not durations else round(durations[len(durations) // 2] if len(durations) % 2 else (durations[len(durations)//2-1] + durations[len(durations)//2]) / 2, 1)
        return {"signal_to_decision_min": median, "funnel": {"sourced": sourced, "screened": screened, "diligenced": diligenced, "decided": decided}}


def decision_brief(diligence: dict[str, Any], memo: dict[str, Any], adversarial: dict[str, Any]) -> dict[str, Any]:
    claim_ids = {claim["claim_id"] for claim in diligence.get("claims", [])}
    based_on = set(memo.get("recommendation", {}).get("based_on", []))
    contested: list[dict[str, Any]] = []
    verified_attacks = 0
    for objection_i, objection in enumerate(adversarial.get("objections", [])):
        verification = objection.get("verification")
        if verification == "verified":
            verified_attacks += 1
        for claim_id in dict.fromkeys(objection.get("targets", [])):
            if claim_id not in claim_ids:
                continue
            if verification == "verified" and claim_id in based_on:
                severity = "red"
            elif verification == "verified":
                severity = "yellow"
            elif verification == "unverified" and claim_id in based_on:
                severity = "yellow"
            else:
                severity = "dim"
            contested.append({"claim_id": claim_id, "objection_i": objection_i, "severity": severity})
    counts = {severity: sum(1 for item in contested if item["severity"] == severity) for severity in ("red", "yellow", "dim")}
    return {
        "summary": f"Decision Brief: {counts['red']} red, {counts['yellow']} yellow, {counts['dim']} dim contested pairs; human review required.",
        "contested": contested,
        "stats": {"claims": len(diligence.get("claims", [])), "contested": len(contested), "verified_attacks": verified_attacks},
    }


def validator_report(adversarial: dict[str, Any], signals: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Expose the verifier pass as a distinct, human-readable report."""

    findings = []
    signal_map = {
        str(item.get("signal_id")): item
        for item in (signals or [])
        if isinstance(item, dict) and item.get("signal_id")
    }
    for index, objection in enumerate(adversarial.get("objections", [])):
        if not isinstance(objection, dict):
            continue
        status = str(objection.get("verification") or "unverified")
        evidence = [str(item) for item in (objection.get("evidence") or []) if item]
        evidence_details = [
            re.sub(r"\s+", " ", str(signal_map[item].get("text") or "")).strip()
            for item in evidence
            if item in signal_map
        ]
        if status == "verified":
            explanation = (
                f"Verified against {len(evidence)} resolved Memory record(s). "
                + (f"Cited facts: {'; '.join(evidence_details[:2])}" if evidence_details else "The cited records are valid and relevant to the objection.")
            )
        elif status == "unverified":
            explanation = "The validator could not confirm this objection from the cited Memory evidence; treat it as an open diligence question, not a fact."
        else:
            explanation = "This is an explicit risk hypothesis with no validating Memory evidence. It must not be treated as fact, but should be tested before investing."
        findings.append(
            {
                "objection_i": index,
                "status": status,
                "targets": [str(item) for item in objection.get("targets", []) if item],
                "evidence": evidence,
                "explanation": explanation,
            }
        )
    counts = {
        status: sum(1 for finding in findings if finding["status"] == status)
        for status in ("verified", "unverified", "n/a")
    }
    return {
        "summary": (
            f"Validator Report: {counts['verified']} verified, {counts['unverified']} unverified, "
            f"{counts['n/a']} speculation findings. Verification does not make an investment decision."
        ),
        "findings": findings,
        "stats": counts,
    }


SEARCH_TOKEN_GROUPS: dict[str, set[str]] = {
    "ai": {"ai", "ml", "nlp", "llm", "model", "inference", "machine", "language"},
    "technical": {"technical", "engineer", "engineering", "developer", "github", "code", "cto", "researcher"},
    "infrastructure": {"infrastructure", "infra", "platform", "systems", "compute", "gpu", "serving", "observability"},
}
SEARCH_IGNORED_TOKENS = {
    "a", "an", "and", "for", "founder", "founders", "in", "last", "no", "of", "or",
    "prior", "the", "with", "within", "without", "days", "day", "vc", "funding",
    "shipped", "recent", "recently", "technical",
}


def empty_query_filter() -> dict[str, Any]:
    return {
        "technical_founder": None,
        "sectors": [],
        "geos": [],
        "shipped_within_days": None,
        "prior_vc": None,
    }


def _search_tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 1}


def _search_stem(token: str) -> str:
    for suffix in ("ization", "ational", "ments", "ment", "ing", "ics", "ies", "ers", "er", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def _semantic_token_match(token: str, corpus_tokens: set[str], corpus: str) -> bool:
    if token in corpus_tokens or (len(token) >= 4 and token in corpus):
        return True
    token_stem = _search_stem(token)
    for candidate in corpus_tokens:
        candidate_stem = _search_stem(candidate)
        if token_stem == candidate_stem:
            return True
        if min(len(token), len(candidate)) >= 5 and SequenceMatcher(None, token, candidate).ratio() >= 0.82:
            return True
    for canonical, aliases in SEARCH_TOKEN_GROUPS.items():
        if token == canonical or token in aliases:
            return bool(aliases & corpus_tokens)
    return False


def founder_search_match(
    query: str,
    query_filter: dict[str, Any],
    profile: dict[str, Any],
    signals: list[dict[str, Any]],
    related_terms: list[str] | None = None,
) -> list[str]:
    """Return forgiving, explainable matches over persisted Founder Memory."""

    corpus = " ".join(
        [
            str(profile.get("name") or ""),
            str(profile.get("headline") or ""),
            str(profile.get("location") or ""),
            str(profile.get("origin") or ""),
            str(profile.get("bio") or ""),
            *(str(signal.get("text") or "") for signal in signals),
            *(str(signal.get("url") or "") for signal in signals),
            *(str(item) for item in (related_terms or [])),
        ]
    ).casefold()
    corpus_tokens = _search_tokens(corpus)
    why: list[str] = []

    if query_filter.get("technical_founder") is True:
        if not (SEARCH_TOKEN_GROUPS["technical"] & corpus_tokens):
            return []
        why.append("Technical founder")

    sectors = [str(item).strip() for item in query_filter.get("sectors", []) if str(item).strip()]
    if sectors:
        matched_sectors = [
            sector
            for sector in sectors
            if any(_semantic_token_match(token, corpus_tokens, corpus) for token in _search_tokens(sector))
        ]
        if not matched_sectors:
            return []
        why.extend(matched_sectors)

    geos = [str(item).strip() for item in query_filter.get("geos", []) if str(item).strip()]
    if geos:
        matched_geos = [geo for geo in geos if geo.casefold() in corpus]
        if not matched_geos:
            return []
        why.extend(matched_geos)

    shipped_within_days = query_filter.get("shipped_within_days")
    if isinstance(shipped_within_days, int):
        cutoff = datetime.now(timezone.utc) - timedelta(days=shipped_within_days)
        if not any(
            parse_ts(str(signal.get("ts") or now_iso())) >= cutoff
            and any(word in str(signal.get("text") or "").casefold() for word in ("shipped", "released", "published", "launch", "deployed"))
            for signal in signals
        ):
            return []
        why.append("Recent product shipment")

    positive_funding_terms = ("raised a", "seed round", "series a", "venture-backed", "backed by", "vc funding found")
    prior_vc = query_filter.get("prior_vc")
    has_positive_funding = any(term in corpus for term in positive_funding_terms)
    if prior_vc is False:
        if has_positive_funding:
            return []
        why.append("No prior VC disclosed")
    elif prior_vc is True:
        if not has_positive_funding:
            return []
        why.append("Prior VC signal")

    # Preserve literal partial search for names, products, and arbitrary
    # sectors that are not represented by a structured filter.
    query_tokens = _search_tokens(query)
    structured_tokens = set().union(*(_search_tokens(sector) for sector in sectors)) if sectors else set()
    free_tokens = query_tokens - SEARCH_IGNORED_TOKENS - structured_tokens
    if free_tokens:
        matched_free_tokens = {
            token for token in free_tokens if _semantic_token_match(token, corpus_tokens, corpus)
        }
        required_matches = 1 if len(free_tokens) == 1 else math.ceil(len(free_tokens) * 0.6)
        if len(matched_free_tokens) < required_matches:
            return []
        if related_terms and any(
            sum(
                _semantic_token_match(token, _search_tokens(term), term.casefold())
                for token in free_tokens
            ) >= required_matches
            for term in related_terms
        ):
            why.append("Company or application match")
    if not why:
        why.append("Memory text match")
    return list(dict.fromkeys(why))


store = Store()
llm = LLMWrapper()
app = FastAPI(title="VentureIntelligence API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/thesis")
def set_thesis(payload: dict[str, Any]) -> dict[str, bool]:
    thesis = payload.get("thesis")
    if not isinstance(thesis, dict):
        raise HTTPException(422, "thesis is required.")
    store.set_thesis(thesis)
    return {"ok": True}


@app.get("/api/thesis")
def get_thesis() -> dict[str, Any]:
    return {"thesis": store.get_thesis()}


@app.post("/api/scan/run")
def run_scan() -> dict[str, Any]:
    thesis = store.get_thesis()
    live_payload = {
        "thesis": (
            f"Find technical founders in {', '.join(thesis['geo'])} building {', '.join(thesis['sectors'])}, "
            f"at {thesis['stage']} stage, with public execution and product-traction signals. "
            "Exclude companies with public VC funding evidence."
        ),
        "geography": ", ".join(thesis["geo"]),
        "sector": ", ".join(thesis["sectors"]),
        "max_candidates": 8,
    }
    try:
        sourcing_result = sourcing_orchestration.run_sourcing_workflow(live_payload)
        discovery_batch_id = stable_id("scan", now_iso(), uuid.uuid4().hex)
        founders, signals = store.ingest_live_discovery(sourcing_result, discovery_batch_id)
        ranking = sourcing_result.get("ranking") if isinstance(sourcing_result.get("ranking"), dict) else {}
        ranked = ranking.get("ranked_candidates") if isinstance(ranking.get("ranked_candidates"), list) else []
        reviewable = sum(
            1
            for candidate in ranked
            if isinstance(candidate, dict) and candidate.get("status") in {"candidate", "needs_review"}
        )
        return {
            "new_founders": founders,
            "new_signals": signals,
            "candidates_found": reviewable,
            "candidates_reviewed": len(ranked),
            "cached": False,
        }
    except Exception as exc:  # The reviewed cache keeps the demo usable offline or on provider failure.
        logger.warning("Live sourcing failed; falling back to reviewed cache: %s", exc)
        founders, signals = store.seed_cache()
        return {
            "new_founders": founders,
            "new_signals": signals,
            "candidates_found": 0,
            "candidates_reviewed": 0,
            "cached": True,
        }


@app.get("/api/dashboard")
def dashboard() -> list[dict[str, Any]]:
    return store.dashboard()


@app.post("/api/query")
def query_founders(payload: dict[str, Any]) -> dict[str, Any]:
    q = payload.get("q")
    if not isinstance(q, str) or not q.strip():
        raise HTTPException(422, "q is required.")
    dashboard_rows = store.dashboard()
    exact_name_matches = [
        founder for founder in dashboard_rows if normalized_name(str(founder["name"])) == normalized_name(q)
    ]
    if exact_name_matches:
        return {
            "filter": empty_query_filter(),
            "results": [
                {"founder_id": founder["founder_id"], "why_matched": ["Exact founder name"]}
                for founder in exact_name_matches
            ],
        }
    structured_query = bool(
        re.search(
            r"\b(technical|shipped|released|launched|within|last|days?|prior\s+vc|no\s+vc|venture[- ]backed|unfunded)\b",
            q.casefold(),
        )
    )
    # Plain names, companies, product terms, and paraphrases are a fast local
    # full-Memory search. Only explicit structured constraints need the model
    # to produce QueryFilter fields.
    query_filter = llm.query(q, store.get_thesis()) if structured_query else empty_query_filter()
    results = []
    for founder in dashboard_rows:
        founder_record = store.founder_profile(founder["founder_id"])
        why = founder_search_match(
            q,
            query_filter,
            founder_record["profile"],
            founder_record["signals"],
            store.founder_search_context(founder["founder_id"]),
        )
        if why:
            results.append({"founder_id": founder["founder_id"], "why_matched": why})
    return {"filter": query_filter, "results": results}


@app.post("/api/chat")
def founder_memory_chat(payload: dict[str, Any]) -> dict[str, Any]:
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(422, "message is required.")
    if len(message) > 4000:
        raise HTTPException(422, "message must be 4000 characters or fewer.")
    chat_id = payload.get("chat_id")
    if chat_id is None:
        chat_id = "legacy-chat"
    elif not isinstance(chat_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", chat_id):
        raise HTTPException(422, "chat_id must contain 8-80 letters, numbers, underscores, or hyphens.")
    founder_id = payload.get("founder_id")
    if founder_id is not None and (not isinstance(founder_id, str) or not founder_id.strip()):
        raise HTTPException(422, "founder_id must be a non-empty string or null.")
    history_input = payload.get("history", [])
    if not isinstance(history_input, list):
        raise HTTPException(422, "history must be an array.")
    history: list[dict[str, str]] = []
    for item in history_input[-8:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if isinstance(content, str) and content.strip():
            history.append({"role": str(item["role"]), "content": content.strip()[:2000]})

    chunks = store.sync_rag_chunks(founder_id)
    if not chunks:
        return {
            "answer": "There is no Founder Memory available in this scope yet.",
            "insufficient_evidence": True,
            "citations": [],
            "retrieval": {"searched_chunks": 0, "returned_chunks": 0},
        }
    try:
        result = llm.founder_chat(message.strip(), history, chunks, chat_id)
    except Exception as exc:
        logger.warning("Founder Memory chat failed: %s", exc)
        raise HTTPException(502, "Founder Memory chat could not complete. Please retry.") from exc
    updates = result.pop("embedding_updates", {})
    retrieved_chunk_ids = result.pop("retrieved_chunk_ids", [])
    if isinstance(updates, dict):
        store.save_rag_embeddings(updates)
    chunks_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    citation_number = {str(chunk_id): index for index, chunk_id in enumerate(retrieved_chunk_ids, start=1)}
    citations = []
    for chunk_id in result.get("cited_chunk_ids", []):
        chunk = chunks_by_id.get(str(chunk_id))
        if not chunk:
            continue
        citations.append(
            {
                "chunk_id": chunk["chunk_id"],
                "citation": citation_number.get(str(chunk["chunk_id"]), len(citations) + 1),
                "founder_id": chunk["founder_id"],
                "founder_name": chunk["founder_name"],
                "source_type": chunk["source_type"],
                "label": chunk["label"],
                "url": chunk["url"],
                "snippet": re.sub(r"\s+", " ", str(chunk["content"])).strip()[:360],
            }
        )
    return {
        "answer": str(result.get("answer") or "I could not produce a grounded answer."),
        "insufficient_evidence": bool(result.get("insufficient_evidence")),
        "citations": citations,
        "retrieval": {"searched_chunks": len(chunks), "returned_chunks": len(citations)},
    }


@app.get("/api/founders/{founder_id}")
def get_founder(founder_id: str) -> dict[str, Any]:
    return store.founder_profile(founder_id)


@app.post("/api/founders/{founder_id}/activate")
def activate_founder(founder_id: str) -> dict[str, str]:
    founder = store.find_founder(founder_id)
    return {"outreach_draft": f"Hi {founder['name'].split()[0]} - I saw your evidence-backed work and would like to learn what you are building. This is a review-only draft and will not be sent."}


@app.post("/api/applications")
def create_application(payload: dict[str, Any]) -> dict[str, Any]:
    company_name = payload.get("company_name")
    deck_text = payload.get("deck_text")
    if not isinstance(company_name, str) or not company_name.strip() or not isinstance(deck_text, str) or not deck_text.strip():
        raise HTTPException(422, "company_name and deck_text are required.")
    extracted = llm.extract(company_name, deck_text)
    return store.create_application(company_name.strip(), deck_text, extracted)


@app.get("/api/applications/{application_id}")
def get_application(application_id: str) -> dict[str, Any]:
    return store.application(application_id)


@app.post("/api/applications/{application_id}/screen")
def screen_application(application_id: str) -> dict[str, Any]:
    application = store.application(application_id)
    founder = store.find_founder(application["founder_id"])
    try:
        research = llm.research_application(
            application["company_name"],
            str(founder["name"]),
            application["claims"],
        )
        store.ingest_application_research(application_id, research)
    except Exception as exc:
        logger.warning("Inbound public-web research failed for %s: %s", application_id, exc)
        raise HTTPException(502, "Public web research failed before screening. Please retry.") from exc
    founder_score = store.score(application["founder_id"])
    thesis = store.get_thesis()
    profile_signals = store.founder_profile(application["founder_id"])["signals"]
    axes = llm.screen_after_research(
        {
            "company_name": application["company_name"],
            "claims": application["claims"],
            "signals": founder_score_signals(profile_signals),
            "founder_score": founder_score["score"],
            "band": founder_score["band"],
            "trend": founder_score["trend"],
            "thesis": thesis,
        }
    )
    store.update_stage(application_id, "axes_json", axes, "screen", dumps(thesis))
    return {"axes": axes}


@app.post("/api/applications/{application_id}/diligence")
def diligence_application(application_id: str) -> dict[str, Any]:
    application = store.application(application_id)
    if application["axes"] is None:
        raise HTTPException(409, "Screen must complete before diligence.")
    diligence = llm.diligence(application["claims"], store.founder_profile(application["founder_id"])["signals"])
    store.update_stage(application_id, "diligence_json", diligence, "diligence", "Resolved claim truth gaps against Memory.")
    return diligence


@app.post("/api/applications/{application_id}/memo")
def memo_application(application_id: str) -> dict[str, Any]:
    application = store.application(application_id)
    if application["diligence"] is None:
        raise HTTPException(409, "Diligence must complete before memo.")
    memo = llm.memo(application["company_name"], application["claims"], application["diligence"], application["axes"])
    store.update_stage(application_id, "memo_json", memo, "memo", "Wrote memo around committed claims only.")
    return memo


@app.post("/api/applications/{application_id}/adversary")
def adversary_application(application_id: str) -> dict[str, Any]:
    application = store.application(application_id)
    if application["memo"] is None:
        raise HTTPException(409, "Memo must complete before adversary.")
    if application["adversarial"] is not None and application["decision_brief"] is not None:
        return {
            "adversarial": application["adversarial"],
            "validator_report": application["validator_report"],
            "decision_brief": application["decision_brief"],
        }
    signals = store.founder_profile(application["founder_id"])["signals"]
    adversarial = llm.adversary(
        application["memo"], application["axes"], application["claims"], signals, application["diligence"]
    )
    verified = llm.verify_adversary(adversarial, application["claims"], signals)
    brief = decision_brief(application["diligence"], application["memo"], verified)
    store.update_stage(application_id, "adversarial_json", verified, "adversary", "Generated one counter-case and verified attacks in one batch.")
    store.update_stage(application_id, "decision_brief_json", brief, "decision_brief", "Built deterministic non-authoritative Decision Brief.")
    return {"adversarial": verified, "validator_report": validator_report(verified, signals), "decision_brief": brief}


@app.get("/api/decisions/queue")
def decision_queue() -> list[dict[str, Any]]:
    return store.queue()


@app.post("/api/decisions/{application_id}/decide")
def decide(application_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return store.decision(application_id, str(payload.get("action") or ""), str(payload.get("approver") or ""))


@app.get("/api/audit")
def get_audit(founder_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    return store.audit(founder_id)


@app.get("/api/metrics")
def get_metrics() -> dict[str, Any]:
    return store.metrics()


# Docker builds the client as a static export. Mounting it last preserves every
# frozen /api route above while letting one public origin serve the full demo.
STATIC_FRONTEND_DIR = ROOT / "frontend" / "out"
if (STATIC_FRONTEND_DIR / "index.html").is_file():
    app.mount("/", StaticFiles(directory=STATIC_FRONTEND_DIR, html=True), name="frontend")
