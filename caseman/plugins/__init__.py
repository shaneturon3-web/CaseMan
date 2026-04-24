from __future__ import annotations

import argparse
from importlib.metadata import entry_points


def register_plugin_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Load and register all caseman.plugins entry points."""
    eps = entry_points().select(group="caseman.plugins")
    for ep in sorted(eps, key=lambda e: e.name):
        register = ep.load()
        register(subparsers)
