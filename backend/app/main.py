"""Compatibility entrypoint; use backend/main.py as the canonical server."""

try:
    from main import app
except ImportError:
    from backend.main import app

__all__ = ["app"]
