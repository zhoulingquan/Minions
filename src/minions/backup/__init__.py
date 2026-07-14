# -*- coding: utf-8 -*-
"""Backup package public API."""
from __future__ import annotations

__all__ = [
    "create_stream",
    "list_backups",
    "get_backup",
    "delete_backups",
    "export_backup",
    "import_backup",
    "execute_restore",
]


def __getattr__(name: str):
    """Load public backup operations without eager startup dependencies."""
    if name == "create_stream":
        from ._ops.create import create_stream as value
    elif name in {
        "delete_backups",
        "export_backup",
        "get_backup",
        "import_backup",
        "list_backups",
    }:
        from ._ops import storage

        value = getattr(storage, name)
    elif name == "execute_restore":
        from .orchestration import execute_restore as value
    else:
        raise AttributeError(name)
    globals()[name] = value
    return value
