"""Orqaga moslik: tv_handler → app.tv.tv_handler"""
from __future__ import annotations
import sys
from app.tv import tv_handler as _impl
sys.modules[__name__] = _impl