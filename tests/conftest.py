"""Test-wide defaults.

Loaded before any test module is imported, so the FastAPI app in
``hush.main`` (which builds a ``DemoService`` at import time) never touches a
real database file: every store is an isolated in-memory SQLite. Individual
tests may still override these with ``monkeypatch``.
"""

import os

os.environ.setdefault("HUSH_DATABASE_URL", "sqlite://")
os.environ.pop("HUSH_STATE_KEY", None)
