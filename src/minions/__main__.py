# -*- coding: utf-8 -*-
"""Allow running Minions via ``python -m minions``."""
from .cli.main import cli

if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
