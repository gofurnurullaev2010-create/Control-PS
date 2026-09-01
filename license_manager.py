"""Orqaga moslik: license_manager → app.auth.license_manager"""
from __future__ import annotations
import sys
from app.auth import license_manager as _impl
sys.modules[__name__] = _impl