from __future__ import annotations
import logging
from app.core.runtime import ensure_tv_tools_path, setup_logging
def prepare_runtime() -> None:
    """Prepare logging and bundled TV tools for either legacy or modular UI."""
    setup_logging()
    ensure_tv_tools_path()
    logging.getLogger(__name__).info('Modular runtime prepared')