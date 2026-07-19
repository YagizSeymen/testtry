from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import applications, audit, dashboard, decisions, founders, metrics, query, thesis

api_router = APIRouter(prefix="/api")
api_router.include_router(thesis.router)
api_router.include_router(dashboard.router)
api_router.include_router(founders.router)
api_router.include_router(query.router)
api_router.include_router(applications.router)
api_router.include_router(decisions.router)
api_router.include_router(audit.router)
api_router.include_router(metrics.router)
