"""Config file (.cfg) writer."""

from __future__ import annotations

from pathlib import Path


def write_config(content: str, path: str | Path) -> None:
    """Write configuration output to a .cfg file."""
    Path(path).write_text(content + "\n", encoding="utf-8")


def write_rollback(content: str, path: str | Path = "rollback.cfg") -> None:
    """Write rollback configuration to file."""
    Path(path).write_text(content + "\n", encoding="utf-8")
