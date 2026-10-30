"""Entry point for serverless hosts (e.g. Vercel). Long-running hosts use uvicorn app.api.main:app."""
from app.api.main import app  # noqa: F401
