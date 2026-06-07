"""Global pytest fixtures.

Point the data directory at a temporary directory before importing any app module,
so tests use a fresh SQLite database and don't pollute the dev database
(app.core.paths resolves paths once at import time, so the env var must be set first).
"""

import os
import tempfile

import pytest

# Must be set before `import app.*`, otherwise paths/database has already built the engine with the default path.
_TMP_DATA_DIR = tempfile.mkdtemp(prefix="oc-test-data-")
os.environ["OC_CREATIVE_DATA_DIR"] = _TMP_DATA_DIR


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    """Create tables once. When TestClient isn't wrapped in `with`, the startup event won't fire, so this is the fallback."""
    from app.db.database import init_db

    init_db()
