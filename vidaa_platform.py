"""Orqaga moslik: vidaa_platform → app.tv.vidaa_platform"""
from __future__ import annotations
import sys
from app.tv import vidaa_platform as _impl
sys.modules[__name__] = _impl