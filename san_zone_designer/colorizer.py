"""Colorize plain-text generator output using Rich markup."""

from __future__ import annotations

import re

_WWPN_PATTERN = re.compile(r"([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:"
                           r"[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})")

_CISCO_KEYWORDS = re.compile(
    r"^(device-alias\s+(?:database|commit|name)|zone\s+name|zoneset\s+(?:name|activate)"
    r"|vsan\s|config\s+t|member\s|copy\s+running)",
    re.IGNORECASE,
)

_BROCADE_KEYWORDS = re.compile(
    r"^(alicreate|zonecreate|cfgcreate|cfgadd|cfgenable|cfgsave|cfgdisable|alidelete|zonedelete|cfgdelete)",
    re.IGNORECASE,
)


def colorize_line(line: str, vendor: str = "cisco") -> str:
    """Apply Rich markup to a single output line.

    Returns the line with Rich markup tags for colorized terminal display.
    """
    stripped = line.strip()

    # Comment lines with separator
    if stripped.startswith("!") and "---" in stripped:
        return f"[bold cyan]{line}[/bold cyan]"

    # Comment lines without separator
    if stripped.startswith("!"):
        return f"[dim]{line}[/dim]"

    # Vendor-specific keyword lines
    if vendor == "cisco" and _CISCO_KEYWORDS.match(stripped):
        # Also highlight WWPNs within the line
        return _highlight_wwpn(f"[bold green]{line}[/bold green]")

    if vendor == "brocade" and _BROCADE_KEYWORDS.match(stripped):
        return _highlight_wwpn(f"[bold green]{line}[/bold green]")

    # Lines containing WWPNs
    if _WWPN_PATTERN.search(line):
        return _highlight_wwpn(line)

    return line


def _highlight_wwpn(line: str) -> str:
    """Highlight WWPN patterns in yellow within a line."""
    return _WWPN_PATTERN.sub(r"[yellow]\1[/yellow]", line)
