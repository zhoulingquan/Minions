# -*- coding: utf-8 -*-
"""App-owned lifecycle hooks registered by app composition roots."""
from .error import CancelCleanupHook, ErrorNormalizeHook

__all__ = ["CancelCleanupHook", "ErrorNormalizeHook"]
