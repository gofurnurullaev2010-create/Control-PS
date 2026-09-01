"""Orqaga moslik: app_password → app.auth.app_password"""
from __future__ import annotations
import sys
from app.auth import app_password as _impl
sys.modules[__name__] = _impl