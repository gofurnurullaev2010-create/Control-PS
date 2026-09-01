"""Orqaga moslik: database → app.db.database"""
from __future__ import annotations
import sys
from app.db import database as _impl
sys.modules[__name__] = _impl