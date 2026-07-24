# -*- coding: utf-8 -*-
"""Compatibility facade for :mod:`minions.channels`."""
from __future__ import annotations

from minions import channels as _channels

__all__ = _channels.__all__


def __getattr__(name: str):
    return getattr(_channels, name)
