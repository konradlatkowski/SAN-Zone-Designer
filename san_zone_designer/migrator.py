"""Migrate initiators/targets from txt to yaml format."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .parser import parse_initiators_txt, parse_targets_txt


def detect_host_from_alias(alias: str) -> str:
    """Auto-detect host name from HBA alias by stripping _HBA\\d+ or _FC\\d+ suffix."""
    stripped = re.sub(r"_HBA\d+$", "", alias, flags=re.IGNORECASE)
    if stripped != alias:
        return stripped
    stripped = re.sub(r"_FC\d+$", "", alias, flags=re.IGNORECASE)
    if stripped != alias:
        return stripped
    return alias


def detect_storage_array_from_alias(alias: str) -> str:
    """Auto-detect storage array name from target alias.

    Strips suffixes like _CT\\d_FC\\d, _CT\\d+, _SVM_FC_\\d+, _SVM, _FC\\d+ etc.
    """
    # Order matters: try most specific patterns first
    patterns = [
        r"_CT\d+_FC\d+$",    # e.g. _CT0_FC0
        r"_SVM_FC_\d+$",     # e.g. _SVM_FC_01
        r"_CT\d+$",          # e.g. _CT0
        r"_SVM$",            # e.g. _SVM
        r"_FC_\d+$",         # e.g. _FC_01
        r"_FC\d+$",          # e.g. _FC0
    ]
    for pattern in patterns:
        stripped = re.sub(pattern, "", alias, flags=re.IGNORECASE)
        if stripped != alias:
            return stripped
    return alias


def detect_type_from_filename(filename: str) -> str:
    """Auto-detect file type from filename. Returns 'initiators', 'targets', or 'auto'."""
    name_lower = filename.lower()
    if any(kw in name_lower for kw in ("init", "hba")):
        return "initiators"
    if any(kw in name_lower for kw in ("target", "tgt")):
        return "targets"
    return "auto"


def migrate_initiators(input_path: str | Path, output_path: str | Path) -> int:
    """Migrate initiators from txt to yaml. Returns count of migrated entries."""
    hbas = parse_initiators_txt(input_path)

    data = {"initiators": []}
    for hba in hbas:
        entry: dict = {
            "alias": hba.alias,
            "wwpn": hba.wwpn,
            "host": detect_host_from_alias(hba.alias),
        }
        if hba.fabric:
            entry["fabric"] = hba.fabric
        data["initiators"].append(entry)

    Path(output_path).write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return len(hbas)


def migrate_targets(input_path: str | Path, output_path: str | Path) -> int:
    """Migrate targets from txt (many mode) to yaml. Returns count of migrated entries."""
    targets = parse_targets_txt(input_path, mode="many")

    data = {"targets": []}
    for tgt in targets:
        entry: dict = {
            "alias": tgt.alias,
            "wwpn": tgt.wwpn,
        }
        if tgt.group:
            entry["group"] = tgt.group
        entry["storage_array"] = detect_storage_array_from_alias(tgt.alias)
        data["targets"].append(entry)

    Path(output_path).write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return len(targets)
