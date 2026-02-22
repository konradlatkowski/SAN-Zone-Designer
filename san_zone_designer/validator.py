"""Validation utilities for SAN Zone Designer."""

from __future__ import annotations

from .models import ALIAS_RE, MAX_ALIAS_LEN, WWPN_RE, normalize_wwpn

# NAA identifiers valid in Fibre Channel (first hex nibble of WWPN)
_VALID_NAA = frozenset("1256")


def validate_wwpn(wwpn: str) -> str:
    """Validate and normalize a WWPN string.

    Returns normalized WWPN or raises ValueError.
    """
    normalized = normalize_wwpn(wwpn)
    if not WWPN_RE.match(normalized):
        raise ValueError(f"Invalid WWPN: {wwpn}")
    return normalized


def validate_alias_name(name: str) -> str:
    """Validate alias name — only [a-zA-Z0-9_-], max 64 chars.

    Returns stripped name or raises ValueError.
    """
    name = name.strip()
    if not name:
        raise ValueError("Alias name cannot be empty")
    if len(name) > MAX_ALIAS_LEN:
        raise ValueError(f"Alias name too long ({len(name)} > {MAX_ALIAS_LEN}): {name}")
    if not ALIAS_RE.match(name):
        raise ValueError(f"Alias name contains invalid characters: {name}")
    return name


def validate_wwpn_range(wwpn: str) -> str | None:
    """Check if a normalized WWPN is in a reserved or suspicious range.

    Returns a warning message string, or None if the WWPN looks valid.
    """
    raw = wwpn.replace(":", "").lower()
    if raw == "0" * 16:
        return f"{wwpn} — all-zero WWPN is invalid"
    if raw == "f" * 16:
        return f"{wwpn} — all-ones (broadcast) WWPN is invalid"
    naa = raw[0]
    if naa not in _VALID_NAA:
        return f"{wwpn} — unusual NAA identifier '{naa}' (expected 1/2/5/6 for Fibre Channel)"
    return None


def check_duplicates(items: list[tuple[str, str]]) -> list[str]:
    """Check for duplicate aliases or WWPNs in a list of (alias, wwpn) tuples.

    Returns a list of warning messages.
    """
    warnings: list[str] = []
    seen_aliases: set[str] = set()
    seen_wwpns: set[str] = set()

    for alias, wwpn in items:
        if alias in seen_aliases:
            warnings.append(f"Duplicate alias: {alias}")
        else:
            seen_aliases.add(alias)

        normalized = normalize_wwpn(wwpn)
        if normalized in seen_wwpns:
            warnings.append(f"Duplicate WWPN: {wwpn} (alias: {alias})")
        else:
            seen_wwpns.add(normalized)

    return warnings


def count_raw_entries(path, file_type: str = "unknown") -> int:
    """Count candidate data lines in a file before validation/deduplication.

    For YAML files: counts items in the 'initiators' or 'targets' list.
    For TXT files: counts non-comment, non-blank lines with at least 2 fields.
    """
    from pathlib import Path
    import yaml

    p = Path(path)
    if p.suffix in (".yaml", ".yml"):
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if file_type == "initiators":
            return len(data.get("initiators", []))
        if file_type == "targets":
            return len(data.get("targets", []))
        # auto-detect: whichever key is present
        return len(data.get("initiators", data.get("targets", [])))

    count = 0
    with open(p, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if len(stripped.split()) >= 2:
                count += 1
    return count


def _read_raw_entries(path, file_type: str = "unknown") -> list[tuple[str, str]]:
    """Read all raw (alias, wwpn) pairs from a file without any validation."""
    from pathlib import Path
    import yaml

    p = Path(path)
    entries: list[tuple[str, str]] = []

    if p.suffix in (".yaml", ".yml"):
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if file_type == "initiators":
            items = data.get("initiators", [])
        elif file_type == "targets":
            items = data.get("targets", [])
        else:
            items = data.get("initiators", data.get("targets", []))
        for item in items:
            alias = str(item.get("alias", ""))
            wwpn = str(item.get("wwpn", ""))
            if alias or wwpn:
                entries.append((alias, wwpn))
    else:
        with open(p, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                parts = stripped.split()
                if len(parts) >= 2:
                    entries.append((parts[0], parts[1]))

    return entries


def scan_raw_file_warnings(path, file_type: str = "unknown") -> list[str]:
    """Comprehensive scan of a raw file for all validation issues.

    Checks every entry for:
    - Invalid alias format (bad characters, too long, empty)
    - Invalid WWPN format (wrong length, bad characters, missing octets)
    - WWPN range issues (all-zero, broadcast, unusual NAA)
    - Duplicate aliases
    - Duplicate WWPNs

    Returns a list of specific warning messages.
    """
    raw_entries = _read_raw_entries(path, file_type)
    warnings: list[str] = []
    valid_pairs: list[tuple[str, str]] = []

    for alias_raw, wwpn_raw in raw_entries:
        # Validate alias
        try:
            validate_alias_name(alias_raw)
        except ValueError as e:
            warnings.append(str(e))
            continue

        # Validate WWPN format
        normalized = normalize_wwpn(wwpn_raw)
        if not WWPN_RE.match(normalized):
            warnings.append(f"Invalid WWPN '{wwpn_raw}' (alias: {alias_raw})")
            continue

        valid_pairs.append((alias_raw, normalized))

        # WWPN range check on valid entries
        msg = validate_wwpn_range(normalized)
        if msg:
            warnings.append(f"{alias_raw}: {msg}")

    # Duplicate check on valid pairs
    warnings += check_duplicates(valid_pairs)

    return warnings
