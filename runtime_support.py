"""Orqaga moslik: runtime_support → app.core.runtime"""
from __future__ import annotations
import sys
from app.core import runtime as _impl
sys.modules[__name__] = _impl