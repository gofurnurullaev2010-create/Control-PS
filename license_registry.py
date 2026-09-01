"""Orqaga moslik: license_registry → app.auth.license_registry"""
from __future__ import annotations
import sys
from app.auth import license_registry as _impl
sys.modules[__name__] = _impl