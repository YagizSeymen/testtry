"""Vercel FastAPI service entrypoint.

The service root is the repository root so the backend can import the shared
ai_service package. Vercel resolves this module as ``main:app``.
"""

from backend.main import app

