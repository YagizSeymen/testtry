"""Cache-first FastAPI implementation of the frozen VentureIntelligence API."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .llm.wrapper import LLMWrapper
from ai_service import sourcing_orchestration


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# A deployed container mounts a persistent disk at /data; local development
# continues to use the ignored database next to this module.
PERSISTENT_DATABASE_PATH = Path("/data/venture_intelligence.db")
DATABASE_PATH = PERSISTENT_DATABASE_PATH if PERSISTENT_DATABASE_PATH.parent.is_dir() else Path(__file__).with_name("venture_intelligence.db")
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


def parse_ts(value: str, fallback: datetime | None = None) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return fallback or datetime.now(timezone.utc)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class Store:
    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.path = path
        self.initialize()
        self.seed_cache()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
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
                """
            )
            existing = db.execute("SELECT payload FROM thesis WHERE singleton = 1").fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO thesis(singleton, payload, updated_at) VALUES(1, ?, ?)",
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

    def ingest_live_discovery(self, sourcing_result: dict[str, Any]) -> tuple[int, int]:
        """Promote source-backed, reviewable live leads into product Memory.

        The sourcing workflow has already ranked evidence coverage. This layer
        deliberately keeps only leads without a public VC-funding exclusion,
        stores at most twelve deduplicated signals per candidate, and never
        treats an absence of funding evidence as proof of no funding.
        """

        discovery = sourcing_result.get("discovery") if isinstance(sourcing_result.get("discovery"), dict) else {}
        ranking = sourcing_result.get("ranking") if isinstance(sourcing_result.get("ranking"), dict) else {}
        evidence_by_candidate: dict[str, list[dict[str, Any]]] = {}
        for evidence in discovery.get("evidence", []):
            if isinstance(evidence, dict) and evidence.get("candidate_id") and evidence.get("source_url") and evidence.get("claim"):
                evidence_by_candidate.setdefault(str(evidence["candidate_id"]), []).append(evidence)

        new_founders = 0
        new_signals = 0
        with self.connection() as db:
            for candidate in ranking.get("ranked_candidates", []):
                # The dashboard is an actionable candidate queue, not an
                # exploratory lead list. Lower-coverage leads remain in the
                # sourcing result for human research but are not promoted.
                if not isinstance(candidate, dict) or candidate.get("status") != "candidate":
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
                seen: set[tuple[str, str]] = set()
                for evidence in candidate_evidence:
                    key = (
                        str(evidence.get("signal_type") or ""),
                        str(evidence.get("source_url") or ""),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    deduplicated.append(evidence)
                    if len(deduplicated) == 12:
                        break
                acquisition_sources = {live_signal_source(str(item["source_url"])) for item in deduplicated}
                profile_origin = live_profile_origin(acquisition_sources)

                for founder_name in founder_names:
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
                                now_iso(),
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
                    refreshed_urls = sorted({str(item["source_url"]) for item in deduplicated})
                    placeholders = ", ".join("?" for _ in refreshed_urls)
                    db.execute(
                        f"DELETE FROM signals WHERE founder_id = ? AND text LIKE 'Live %' AND url IN ({placeholders})",
                        (founder_id, *refreshed_urls),
                    )

                    for evidence in deduplicated:
                        signal_id = stable_id("sig", "live", founder_id, evidence.get("evidence_id"), evidence.get("source_url"))
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
                                live_signal_source(str(evidence["source_url"])),
                                f"Live {signal_type}: {str(evidence['claim']).strip()}",
                                str(evidence["source_url"]),
                            ),
                        )
                        new_signals += 1
                    self._record_score(db, founder_id, now_iso())
                    self._audit(
                        db,
                        founder_id,
                        None,
                        "ingest",
                        "live-sourcing",
                        "ingested_public_web_signals",
                        "Stored bounded, source-backed public-web signals for human review.",
                    )
        return new_founders, new_signals

    def _signals(self, db: sqlite3.Connection, founder_id: str) -> list[dict[str, Any]]:
        rows = db.execute(
            "SELECT signal_id, ts, source, text, url FROM signals WHERE founder_id = ? ORDER BY ts DESC",
            (founder_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _record_score(self, db: sqlite3.Connection, founder_id: str, snapshot_ts: str) -> dict[str, Any]:
        signals = self._signals(db, founder_id)
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
                    }
                )
        return sorted(output, key=lambda item: item["founder_score"], reverse=True)

    def find_founder(self, founder_id: str) -> sqlite3.Row:
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
                        "INSERT OR REPLACE INTO claims VALUES(?, ?, ?, ?, ?)",
                        (claim["claim_id"], application_id, claim["type"], claim["text"], claim["source_span"]),
                    )
                self._audit(db, founder_id, application_id, "extract", "system", "extracted_claims", f"Extracted {len(claims)} typed deck claims.")
        return {"application_id": application_id, "founder_id": founder_id, "claims": claims}

    def application_row(self, application_id: str) -> sqlite3.Row:
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
            evidence = [
                dict(row)
                for row in db.execute(
                    f"SELECT signal_id, ts, source, text, url FROM signals WHERE signal_id IN ({','.join('?' for _ in evidence_ids)})",
                    tuple(sorted(evidence_ids)),
                ).fetchall()
            ] if evidence_ids else []
        return {
            "application_id": app["application_id"],
            "founder_id": app["founder_id"],
            "company_name": app["company_name"],
            "status": app["status"],
            "claims": self.claims(application_id),
            "axes": axes,
            "diligence": diligence,
            "memo": memo,
            "adversarial": adversarial,
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
        db: sqlite3.Connection,
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
            sourced = db.execute("SELECT COUNT(*) FROM founders").fetchone()[0]
            screened = db.execute("SELECT COUNT(*) FROM applications WHERE axes_json IS NOT NULL").fetchone()[0]
            diligenced = db.execute("SELECT COUNT(*) FROM applications WHERE diligence_json IS NOT NULL").fetchone()[0]
            decided = db.execute("SELECT COUNT(*) FROM applications WHERE status IN ('approved', 'rejected')").fetchone()[0]
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
        founders, signals = store.ingest_live_discovery(sourcing_result)
        return {"new_founders": founders, "new_signals": signals, "cached": False}
    except Exception as exc:  # The reviewed cache keeps the demo usable offline or on provider failure.
        logger.warning("Live sourcing failed; falling back to reviewed cache: %s", exc)
        founders, signals = store.seed_cache()
        return {"new_founders": founders, "new_signals": signals, "cached": True}


@app.get("/api/dashboard")
def dashboard() -> list[dict[str, Any]]:
    return store.dashboard()


@app.post("/api/query")
def query_founders(payload: dict[str, Any]) -> dict[str, Any]:
    q = payload.get("q")
    if not isinstance(q, str) or not q.strip():
        raise HTTPException(422, "q is required.")
    query_filter = llm.query(q, store.get_thesis())
    results = []
    for founder in store.dashboard():
        profile = store.founder_profile(founder["founder_id"])["profile"]
        signals = store.founder_profile(founder["founder_id"])["signals"]
        corpus = " ".join([profile.get("headline") or "", profile.get("location") or "", *(signal["text"] for signal in signals)]).lower()
        why = []
        if query_filter["technical_founder"] and any(term in corpus for term in ("technical", "engineer", "github", "compiler", "systems")):
            why.append("Technical founder")
        if any(sector.lower() in corpus for sector in query_filter["sectors"]):
            why.append(query_filter["sectors"][0])
        europe_locations = ("berlin", "paris", "sofia", "london", "amsterdam", "munich", "zurich", "stockholm", "helsinki")
        for geo in query_filter["geos"]:
            geo_match = geo.lower() in corpus or (geo.casefold() == "europe" and any(location in corpus for location in europe_locations))
            if geo_match:
                why.append(geo)
                break
        if query_filter["shipped_within_days"] is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=query_filter["shipped_within_days"])
            if any(parse_ts(signal["ts"]) >= cutoff and any(word in signal["text"].lower() for word in ("shipped", "released", "published", "launch")) for signal in signals):
                why.append("Recent product shipment")
        if query_filter["prior_vc"] is False and not any("vc" in signal["text"].lower() or "funding" in signal["text"].lower() for signal in signals):
            why.append("No prior VC disclosed")
        requested = [query_filter["technical_founder"] is None or "Technical founder" in why, not query_filter["sectors"] or any(item in why for item in query_filter["sectors"]), not query_filter["geos"] or any(item in why for item in query_filter["geos"]), query_filter["shipped_within_days"] is None or "Recent product shipment" in why, query_filter["prior_vc"] is None or "No prior VC disclosed" in why]
        if all(requested):
            results.append({"founder_id": founder["founder_id"], "why_matched": why})
    return {"filter": query_filter, "results": results}


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
    founder_score = store.score(application["founder_id"])
    thesis = store.get_thesis()
    axes = llm.screen(
        {
            "company_name": application["company_name"],
            "claims": application["claims"],
            "signals": store.founder_profile(application["founder_id"])["signals"],
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
        return {"adversarial": application["adversarial"], "decision_brief": application["decision_brief"]}
    signals = store.founder_profile(application["founder_id"])["signals"]
    adversarial = llm.adversary(application["memo"], application["axes"], application["claims"], signals)
    verified = llm.verify_adversary(adversarial, application["claims"], signals)
    brief = decision_brief(application["diligence"], application["memo"], verified)
    store.update_stage(application_id, "adversarial_json", verified, "adversary", "Generated one counter-case and verified attacks in one batch.")
    store.update_stage(application_id, "decision_brief_json", brief, "decision_brief", "Built deterministic non-authoritative Decision Brief.")
    return {"adversarial": verified, "decision_brief": brief}


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
