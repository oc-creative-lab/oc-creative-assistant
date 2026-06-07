"""Backend runtime path conventions.

After the source moved into the `app/` package, dev-mode data still defaults to
`backend/data`. In packaged mode the Electron main process passes in the
persistence directory via an environment variable, to avoid a portable
temp-extraction directory swallowing the data.
This module centralizes the path constants, so the database and vector index do
not each have to derive paths from `__file__` hierarchy levels.
"""

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
"""Backend project root directory; in dev mode, the `backend` directory containing both `app/` and `data/`."""

DATA_DIR_ENV = "OC_CREATIVE_DATA_DIR"
"""Name of the environment variable Electron's packaged mode passes to the backend for the data directory."""


def _resolve_data_dir() -> Path:
    """Resolve the backend runtime data directory.

    In Electron packaged mode the directory is passed in explicitly: portable
    builds write next to the exe, installed builds write to the user data
    directory. In dev mode, when no environment variable is passed, it falls back
    to the in-source `backend/data`.
    """
    configured_data_dir = os.environ.get(DATA_DIR_ENV)

    if configured_data_dir:
        return Path(configured_data_dir).expanduser().resolve()

    return BACKEND_ROOT / "data"


DATA_DIR = _resolve_data_dir()
"""Backend runtime data directory; both SQLite and ChromaDB write into this directory."""

DATABASE_PATH = DATA_DIR / "oc_creative.sqlite3"
"""Path to the local SQLite database file."""

CHROMA_PATH = DATA_DIR / "chroma"
"""Local ChromaDB persistence directory."""
