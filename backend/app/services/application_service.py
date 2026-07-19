from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domain import (
    core_person_name,
    guard_memo_recommendation,
    normalize_diligence_row,
    normalize_founder_name,
)
from app.models import Application, Founder
from app.repositories.applications import (
    ApplicationRepository,
    dumps,
    loads,
    new_application_id,
    new_founder_id,
)
from app.repositories.founders import FounderRepository
from app.repositories.thesis import ThesisRepository
from app.schemas.application import (
    ApplicationAggregate,
    ApplicationCreateRequest,
    ApplicationCreateResponse,
    Axes,
    Claim,
    Diligence,
    Memo,
)
from app.schemas.common import SignalOut
from app.services.intelligence import IntelligenceService


class ApplicationService:
    def __init__(self, db: Session, intelligence: IntelligenceService | None = None) -> None:
        self._db = db
        self._apps = ApplicationRepository(db)
        self._founders = FounderRepository(db)
        self._thesis = ThesisRepository(db)
        self._ai = intelligence or IntelligenceService()

    def create(self, body: ApplicationCreateRequest) -> ApplicationCreateResponse:
        extraction = self._ai.extract(company_name=body.company_name, deck_text=body.deck_text)
        founder_name = str(extraction.get("founder_name") or "").strip() or "Unknown founder"
        claims_raw = extraction.get("claims") if isinstance(extraction.get("claims"), list) else []
        claims = [Claim.model_validate(item) for item in claims_raw]

        founder = self._resolve_founder(founder_name)
        application = Application(
            id=new_application_id(),
            founder_id=founder.id,
            company_name=body.company_name.strip(),
            status="open",
            deck_text=body.deck_text,
            created_at=datetime.now(timezone.utc),
            claims_json=dumps([c.model_dump() for c in claims]),
        )
        self._apps.add(application)
        self._apps.add_audit(
            stage="extract",
            action="application_created",
            detail=f"Extracted {len(claims)} claims for {body.company_name}",
            founder_id=founder.id,
            application_id=application.id,
        )
        self._apps.save()
        return ApplicationCreateResponse(
            application_id=application.id,
            founder_id=founder.id,
            claims=claims,
        )

    def get(self, application_id: str) -> ApplicationAggregate:
        app = self._require_app(application_id)
        claims = [Claim.model_validate(c) for c in loads(app.claims_json) or []]
        diligence = Diligence.model_validate(loads(app.diligence_json)) if app.diligence_json else None
        adversarial = loads(app.adversarial_json)
        evidence = self._aggregate_evidence(app, diligence, adversarial)
        return ApplicationAggregate(
            application_id=app.id,
            founder_id=app.founder_id,
            company_name=app.company_name,
            status=app.status,  # type: ignore[arg-type]
            claims=claims,
            axes=Axes.model_validate(loads(app.axes_json)) if app.axes_json else None,
            diligence=diligence,
            memo=Memo.model_validate(loads(app.memo_json)) if app.memo_json else None,
            adversarial=adversarial,
            decision_brief=loads(app.decision_brief_json),
            evidence=evidence,
        )

    def screen(self, application_id: str) -> Axes:
        app = self._require_app(application_id)
        claims = loads(app.claims_json) or []
        if not claims:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Screen requires extracted claims")

        thesis = self._thesis.get()
        if thesis is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Thesis not configured")

        founder = app.founder
        latest = max(founder.score_snapshots, key=lambda s: s.ts, default=None)
        if latest is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Founder Score missing")

        payload = {
            "company_name": app.company_name,
            "claims": claims,
            "signals": self._signals_payload(founder),
            "founder_score": latest.score,
            "band": latest.band,
            "trend": latest.trend,
            "thesis": thesis.model_dump(),
        }
        axes_raw = self._ai.screen(payload)
        axes = Axes.model_validate(axes_raw)
        thesis_json = json.dumps(thesis.model_dump(), separators=(",", ":"))
        app.axes_json = dumps(axes.model_dump())
        app.thesis_snapshot_json = thesis_json
        # Clear downstream stages when re-screening.
        app.diligence_json = None
        app.memo_json = None
        app.adversarial_json = None
        app.decision_brief_json = None
        self._apps.add_audit(
            stage="screen",
            action="screened",
            detail=thesis_json,
            founder_id=app.founder_id,
            application_id=app.id,
        )
        self._apps.save()
        return axes

    def diligence(self, application_id: str) -> Diligence:
        app = self._require_app(application_id)
        if not app.axes_json:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diligence requires screening")
        claims = loads(app.claims_json) or []
        signals = self._signals_payload(app.founder)
        valid_ids = {s["signal_id"] for s in signals}
        claim_by_id = {c["claim_id"]: c for c in claims}

        raw = self._ai.diligence({"claims": claims, "signals": signals})
        normalised_claims = []
        for row in raw.get("claims", []):
            claim_id = str(row.get("claim_id") or "")
            claim = claim_by_id.get(claim_id, {})
            normalised_claims.append(
                normalize_diligence_row(
                    claim_id=claim_id,
                    verdict=str(row.get("verdict") or "unverifiable"),
                    evidence_ids=list(row.get("evidence") or []),
                    valid_signal_ids=valid_ids,
                    source_span=claim.get("source_span"),
                    note=str(row.get("note") or ""),
                )
            )
        gaps = [str(g) for g in raw.get("gaps", []) if str(g).strip()]
        if "Cap table: not disclosed" not in gaps:
            gaps.append("Cap table: not disclosed")

        diligence = Diligence.model_validate({"claims": normalised_claims, "gaps": gaps})
        app.diligence_json = dumps(diligence.model_dump())
        app.memo_json = None
        app.adversarial_json = None
        app.decision_brief_json = None
        self._apps.add_audit(
            stage="diligence",
            action="diligenced",
            detail=f"{len(normalised_claims)} claims judged",
            founder_id=app.founder_id,
            application_id=app.id,
        )
        self._apps.save()
        return diligence

    def memo(self, application_id: str) -> Memo:
        app = self._require_app(application_id)
        if not app.diligence_json:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Memo requires diligence")
        claims = loads(app.claims_json) or []
        axes = loads(app.axes_json)
        diligence = loads(app.diligence_json)
        raw = self._ai.memo(
            {
                "company_name": app.company_name,
                "claims": claims,
                "axes": axes,
                "diligence": diligence,
            }
        )
        recommendation = raw.get("recommendation") if isinstance(raw.get("recommendation"), dict) else {}
        guarded = guard_memo_recommendation(
            based_on=list(recommendation.get("based_on") or []),
            claims=claims,
            diligence_claims=list(diligence.get("claims") or []),
            invest=bool(recommendation.get("invest")),
            rationale=str(recommendation.get("rationale") or ""),
        )
        memo = Memo.model_validate(
            {
                "memo_id": raw.get("memo_id"),
                "sections": raw.get("sections"),
                "recommendation": guarded,
            }
        )
        app.memo_json = dumps(memo.model_dump())
        app.adversarial_json = None
        app.decision_brief_json = None
        self._apps.add_audit(
            stage="memo",
            action="memo_written",
            detail=memo.memo_id,
            founder_id=app.founder_id,
            application_id=app.id,
        )
        self._apps.save()
        return memo

    def _resolve_founder(self, founder_name: str) -> Founder:
        normalized = normalize_founder_name(founder_name)
        existing = self._founders.get_by_normalized_name(normalized)
        if existing is not None:
            return existing

        # Match "Maya Chen" to seeded "Maya Chen (Synthetic)" via core name.
        core = core_person_name(founder_name)
        for founder in self._founders.list_all():
            if core_person_name(founder.name) == core:
                return founder

        founder = Founder(
            id=new_founder_id(),
            name=founder_name,
            normalized_name=normalized,
            headline=None,
            location=None,
            origin="inbound",
            bio=None,
        )
        self._founders.add(founder)
        self._db.flush()
        return founder

    def _require_app(self, application_id: str) -> Application:
        app = self._apps.get(application_id)
        if app is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
        return app

    def _signals_payload(self, founder: Founder) -> list[dict[str, Any]]:
        return [
            {
                "signal_id": s.id,
                "ts": s.ts.isoformat().replace("+00:00", "Z") if s.ts.tzinfo else s.ts.isoformat() + "Z",
                "source": s.source,
                "text": s.text,
                "url": s.url,
            }
            for s in founder.signals
        ]

    def _aggregate_evidence(
        self,
        app: Application,
        diligence: Diligence | None,
        adversarial: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        wanted: list[str] = []
        if diligence is not None:
            for row in diligence.claims:
                wanted.extend(row.evidence)
        if isinstance(adversarial, dict):
            for obj in adversarial.get("objections") or []:
                if isinstance(obj, dict) and isinstance(obj.get("evidence"), list):
                    wanted.extend(str(x) for x in obj["evidence"] if x)

        seen: set[str] = set()
        ordered_ids: list[str] = []
        for signal_id in wanted:
            if signal_id not in seen:
                seen.add(signal_id)
                ordered_ids.append(signal_id)

        by_id = {s.id: s for s in app.founder.signals}
        evidence: list[dict[str, Any]] = []
        for signal_id in ordered_ids:
            signal = by_id.get(signal_id)
            if signal is None:
                continue
            evidence.append(
                SignalOut(
                    signal_id=signal.id,
                    ts=signal.ts if signal.ts.tzinfo else signal.ts.replace(tzinfo=timezone.utc),
                    source=signal.source,
                    text=signal.text,
                    url=signal.url,
                ).model_dump(mode="json")
            )
        return evidence
