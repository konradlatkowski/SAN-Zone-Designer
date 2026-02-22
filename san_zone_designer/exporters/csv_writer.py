"""CSV export for zone data and rollback."""

from __future__ import annotations

from pathlib import Path


def write_csv(csv_lines: list[str], path: str | Path) -> None:
    """Write zone CSV: ZoneName;Initiator;InitiatorWWPN;Target;TargetWWPN;VSAN."""
    header = "ZoneName;Initiator;InitiatorWWPN;Target;TargetWWPN;VSAN"
    content = header + "\n" + "\n".join(csv_lines) + "\n"
    Path(path).write_text(content, encoding="utf-8")


def write_rollback_csv(csv_lines: list[str], path: str | Path = "rollback.csv") -> None:
    """Write rollback CSV: Type;Name;VSAN."""
    # csv_lines already contains header from generator
    content = "\n".join(csv_lines) + "\n"
    Path(path).write_text(content, encoding="utf-8")
