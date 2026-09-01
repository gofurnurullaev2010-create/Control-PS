from __future__ import annotations
from app.db import database as legacy_db
def init() -> None:
    """Initialize the existing SQLite database and inline migrations."""
    legacy_db.init_db()
def module():
    """Expose the legacy module for repository methods not yet split."""
    return legacy_db