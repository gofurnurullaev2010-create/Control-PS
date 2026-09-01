"""Orqaga moslik: license_online → app.auth.license_online"""
from __future__ import annotations
import sys
from app.auth import license_online as _impl
sys.modules[__name__] = _impl