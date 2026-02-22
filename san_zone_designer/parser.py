"""Parsers for initiator/target files (txt + yaml formats)."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .models import HBA, Target, validate_alias_name, validate_wwpn

logger = logging.getLogger(__name__)


def parse_initiators_txt(path: str | Path) -> list[HBA]:
    """Parse initiators from txt file. Format: ALIAS WWPN (one per line, # = comment)."""
    initiators: list[HBA] = []
    seen_aliases: set[str] = set()
    seen_wwpns: set[str] = set()

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                logger.warning("Skipping malformed initiator line: %r", line)
                continue

            alias_raw, wwpn_raw = parts[0], parts[1]
            try:
                alias = validate_alias_name(alias_raw)
                wwpn = validate_wwpn(wwpn_raw)
            except ValueError as e:
                logger.warning("Invalid initiator entry: %s", e)
                continue

            if wwpn in seen_wwpns:
                logger.warning("Duplicate initiator WWPN %s (alias: %s) — skipping", wwpn, alias)
                continue
            if alias in seen_aliases:
                logger.warning("Duplicate initiator alias %s — skipping", alias)
                continue

            seen_aliases.add(alias)
            seen_wwpns.add(wwpn)
            initiators.append(HBA(alias=alias, wwpn=wwpn))

    return initiators


def parse_targets_txt(path: str | Path, mode: str = "single") -> list[Target]:
    """Parse targets from txt file with optional group support.

    In 'single' mode: ignores # comments and blank lines.
    In 'many' mode: # lines define group names, blank lines separate groups.
    """
    targets: list[Target] = []
    seen_aliases: set[str] = set()
    seen_wwpns: set[str] = set()

    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    if mode == "single":
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            alias_raw, wwpn_raw = parts[0], parts[1]
            try:
                alias = validate_alias_name(alias_raw)
                wwpn = validate_wwpn(wwpn_raw)
            except ValueError as e:
                logger.warning("Invalid target entry: %s", e)
                continue

            if wwpn in seen_wwpns:
                logger.warning("Duplicate target WWPN %s (alias: %s) — skipping", wwpn, alias)
                continue
            if alias in seen_aliases:
                logger.warning("Duplicate target alias %s — skipping", alias)
                continue

            seen_aliases.add(alias)
            seen_wwpns.add(wwpn)
            targets.append(Target(alias=alias, wwpn=wwpn))
    else:
        # 'many' mode — group parsing
        group_name = ""
        group_index = 0

        # Ensure file ends with empty line for final group flush
        lines_with_end = lines + ["\n"]

        for line in lines_with_end:
            stripped = line.strip()

            if stripped.startswith("#"):
                group_name = stripped[1:].strip()
                continue

            if not stripped:
                # flush current group — just update group_name counter
                if group_name == "":
                    # No name was set but we might have entries
                    pass
                group_name = ""
                group_index += 1
                continue

            parts = stripped.split()
            if len(parts) < 2:
                continue

            alias_raw, wwpn_raw = parts[0], parts[1]
            try:
                alias = validate_alias_name(alias_raw)
                wwpn = validate_wwpn(wwpn_raw)
            except ValueError as e:
                logger.warning("Invalid target entry (many mode): %s", e)
                continue

            if wwpn in seen_wwpns:
                logger.warning("Duplicate target WWPN %s (alias: %s) — skipping", wwpn, alias)
                continue
            if alias in seen_aliases:
                logger.warning("Duplicate target alias %s — skipping", alias)
                continue

            seen_aliases.add(alias)
            seen_wwpns.add(wwpn)

            effective_group = group_name if group_name else f"GROUP{group_index + 1}"
            targets.append(Target(alias=alias, wwpn=wwpn, group=effective_group))

    return targets


def _parse_targets_txt_grouped(path: str | Path) -> dict[str, list[Target]]:
    """Parse targets in 'many' mode and return grouped dict (preserves order)."""
    targets = parse_targets_txt(path, mode="many")
    groups: dict[str, list[Target]] = {}
    for t in targets:
        groups.setdefault(t.group, []).append(t)
    return groups


def parse_initiators_yaml(path: str | Path) -> list[HBA]:
    """Parse initiators from YAML file with metadata."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    initiators: list[HBA] = []
    seen_aliases: set[str] = set()
    seen_wwpns: set[str] = set()
    for item in data.get("initiators", []):
        try:
            hba = HBA(
                alias=item["alias"],
                wwpn=item["wwpn"],
                host=item.get("host", ""),
                fabric=item.get("fabric", ""),
                vsan_id=item.get("vsan_id", 0),
                description=item.get("description", ""),
            )
        except (ValueError, KeyError) as e:
            logger.warning("Skipping invalid YAML initiator entry: %s", e)
            continue
        if hba.wwpn in seen_wwpns:
            logger.warning("Duplicate initiator WWPN %s (alias: %s) — skipping", hba.wwpn, hba.alias)
            continue
        if hba.alias in seen_aliases:
            logger.warning("Duplicate initiator alias %s — skipping", hba.alias)
            continue
        seen_aliases.add(hba.alias)
        seen_wwpns.add(hba.wwpn)
        initiators.append(hba)

    return initiators


def parse_targets_yaml(path: str | Path) -> list[Target]:
    """Parse targets from YAML file with metadata."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    targets: list[Target] = []
    seen_aliases: set[str] = set()
    seen_wwpns: set[str] = set()
    for item in data.get("targets", []):
        try:
            tgt = Target(
                alias=item["alias"],
                wwpn=item["wwpn"],
                group=item.get("group", ""),
                storage_array=item.get("storage_array", ""),
                port=item.get("port", ""),
                fabric=item.get("fabric", ""),
                vsan_id=item.get("vsan_id", 0),
                description=item.get("description", ""),
            )
        except (ValueError, KeyError) as e:
            logger.warning("Skipping invalid YAML target entry: %s", e)
            continue
        if tgt.wwpn in seen_wwpns:
            logger.warning("Duplicate target WWPN %s (alias: %s) — skipping", tgt.wwpn, tgt.alias)
            continue
        if tgt.alias in seen_aliases:
            logger.warning("Duplicate target alias %s — skipping", tgt.alias)
            continue
        seen_aliases.add(tgt.alias)
        seen_wwpns.add(tgt.wwpn)
        targets.append(tgt)

    return targets


def load_initiators(path: str | Path) -> list[HBA]:
    """Auto-detect format and load initiators."""
    p = Path(path)
    if p.suffix in (".yaml", ".yml"):
        return parse_initiators_yaml(p)
    return parse_initiators_txt(p)


def load_targets(path: str | Path, mode: str = "single") -> list[Target]:
    """Auto-detect format and load targets."""
    p = Path(path)
    if p.suffix in (".yaml", ".yml"):
        return parse_targets_yaml(p)
    return parse_targets_txt(p, mode=mode)
