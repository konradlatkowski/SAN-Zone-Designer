"""Import zones from switch output (show zoneset active / cfgshow)."""

from __future__ import annotations

import re
from pathlib import Path

from .models import HBA, Target, Zone, Vendor


def import_zones(path: str | Path, vendor: Vendor | str) -> list[Zone]:
    """Import zones from a file, dispatching to the correct parser by vendor."""
    content = Path(path).read_text(encoding="utf-8")
    vendor_val = vendor if isinstance(vendor, str) else vendor.value

    if vendor_val == "cisco":
        return _parse_cisco_auto(content)
    return _parse_brocade_auto(content)


def _parse_cisco_auto(content: str) -> list[Zone]:
    """Auto-detect Cisco format: show zoneset active output vs .cfg commands."""
    if re.search(r"^\s*zone\s+name\s+\S+\s+vsan\s+\d+", content, re.MULTILINE):
        if re.search(r"^\s*member\s+", content, re.MULTILINE):
            return parse_cisco_show_zoneset(content)
    if re.search(r"^\s*zonecreate\s+", content, re.MULTILINE):
        return _parse_brocade_cfg_commands(content)
    return parse_cisco_show_zoneset(content)


def _parse_brocade_auto(content: str) -> list[Zone]:
    """Auto-detect Brocade format: cfgshow output vs .cfg commands."""
    if re.search(r"^\s*zone:\s+", content, re.MULTILINE):
        return parse_brocade_cfgshow(content)
    if re.search(r'^\s*zonecreate\s+"', content, re.MULTILINE):
        return _parse_brocade_cfg_commands(content)
    return parse_brocade_cfgshow(content)


def parse_cisco_show_zoneset(content: str) -> list[Zone]:
    """Parse Cisco 'show zoneset active' or zone config output.

    Formats handled:
      zone name ZONE_NAME vsan 100
        member device-alias ALIAS
        member pwwn AA:BB:CC:DD:EE:FF:00:11
    """
    zones: list[Zone] = []
    current_zone_name: str | None = None
    members: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()

        zone_match = re.match(r"zone\s+name\s+(\S+)\s+vsan\s+(\d+)", stripped)
        if zone_match:
            if current_zone_name and members:
                zones.append(_build_zone_from_members(current_zone_name, members))
            current_zone_name = zone_match.group(1)
            members = []
            continue

        if current_zone_name:
            alias_match = re.match(r"member\s+device-alias\s+(\S+)", stripped)
            if alias_match:
                members.append(alias_match.group(1))
                continue
            pwwn_match = re.match(r"member\s+pwwn\s+([0-9a-fA-F:]+)", stripped)
            if pwwn_match:
                members.append(pwwn_match.group(1))
                continue

            if stripped in ("exit", ""):
                continue
            if stripped.startswith("zone ") or stripped.startswith("zoneset "):
                if current_zone_name and members:
                    zones.append(_build_zone_from_members(current_zone_name, members))
                current_zone_name = None
                members = []

    if current_zone_name and members:
        zones.append(_build_zone_from_members(current_zone_name, members))

    return zones


def parse_brocade_cfgshow(content: str) -> list[Zone]:
    """Parse Brocade 'cfgshow' output.

    Format:
      zone:  ZONE_NAME
              ALIAS1;ALIAS2;ALIAS3
    """
    zones: list[Zone] = []

    for line in content.splitlines():
        zone_match = re.match(r"\s*zone:\s+(\S+)\s*(.*)", line)
        if zone_match:
            zone_name = zone_match.group(1)
            rest = zone_match.group(2).strip()
            if rest:
                member_aliases = [m.strip() for m in rest.split(";") if m.strip()]
                if member_aliases:
                    zones.append(_build_zone_from_members(zone_name, member_aliases))
            continue

        # Continuation line (indented, with semicolons) for multi-line cfgshow
        if zones and re.match(r"^\s+\S", line):
            continuation = line.strip()
            if ";" in continuation or (continuation and not continuation.startswith("zone:")):
                extra = [m.strip() for m in continuation.split(";") if m.strip()]
                if extra:
                    old_zone = zones[-1]
                    all_members = [old_zone.initiator.alias] + [t.alias for t in old_zone.targets] + extra
                    zones[-1] = _build_zone_from_members(old_zone.name, all_members)

    return zones


def _parse_brocade_cfg_commands(content: str) -> list[Zone]:
    """Parse Brocade CLI config commands (zonecreate lines).

    Format:
      zonecreate "ZONE_NAME","ALIAS1;ALIAS2;ALIAS3"
    """
    zones: list[Zone] = []

    for line in content.splitlines():
        match = re.match(r'\s*zonecreate\s+"([^"]+)"\s*,\s*"([^"]+)"', line)
        if match:
            zone_name = match.group(1)
            member_str = match.group(2)
            members = [m.strip() for m in member_str.split(";") if m.strip()]
            if members:
                zones.append(_build_zone_from_members(zone_name, members))

    return zones


_PLACEHOLDER_WWPN = "00:00:00:00:00:00:00:00"
_WWPN_PATTERN = re.compile(r"^([0-9a-fA-F]{2}:){7}[0-9a-fA-F]{2}$")


def _build_zone_from_members(zone_name: str, members: list[str]) -> Zone:
    """Build a Zone from a list of member aliases/WWPNs.

    First member = initiator, rest = targets.
    If member looks like a WWPN, use it directly; otherwise use placeholder.
    """
    def _make_hba(name_or_wwpn: str) -> HBA:
        if _WWPN_PATTERN.match(name_or_wwpn):
            return HBA(alias=zone_name.replace("__", "_init"), wwpn=name_or_wwpn)
        return HBA(alias=name_or_wwpn, wwpn=_PLACEHOLDER_WWPN)

    def _make_target(name_or_wwpn: str) -> Target:
        if _WWPN_PATTERN.match(name_or_wwpn):
            return Target(alias=zone_name.replace("__", "_tgt"), wwpn=name_or_wwpn)
        return Target(alias=name_or_wwpn, wwpn=_PLACEHOLDER_WWPN)

    initiator = _make_hba(members[0])
    targets = [_make_target(m) for m in members[1:]]

    return Zone(name=zone_name, initiator=initiator, targets=targets)
