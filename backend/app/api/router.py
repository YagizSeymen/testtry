from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import dashboard, founders, thesis

api_router = APIRouter(prefix="/api")
api_router.include_router(thesis.router)
api_router.include_router(dashboard.router)
api_router.include_router(founders.router)
