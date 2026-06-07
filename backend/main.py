"""Thin entry point compatible with the legacy `main:app` import path."""

from app.main import app

__all__ = ["app"]
