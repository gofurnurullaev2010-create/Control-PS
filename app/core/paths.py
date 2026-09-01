from __future__ import annotations
from pathlib import Path
from typing import Optional
from app.core.runtime import app_dir, bundle_path
def resource_path(filename: str) -> Optional[Path]:
    """Return a runtime-safe path for images and bundled TV assets."""
    return bundle_path(filename)
def application_dir() -> Path:
    """Directory that contains the running app or packaged executable."""
    return app_dir()