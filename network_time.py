"""Orqaga moslik: network_time → app.core.network_time"""
from __future__ import annotations
import sys
from app.core import network_time as _impl
sys.modules[__name__] = _impl