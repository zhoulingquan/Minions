# -*- coding: utf-8 -*-
"""Resolve the public Minions version from installed distribution metadata."""

from importlib import metadata

__version__ = "0.1.0"

for _distribution in ("minions", "minions-core"):
    try:
        __version__ = metadata.version(_distribution)
        break
    except metadata.PackageNotFoundError:
        continue
