"""Data models for SAN Zone Designer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

WWPN_RE = re.compile(r"^([0-9a-fA-F]{2}:){7}[0-9a-fA-F]{2}$")
ALIAS_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_ALIAS_LEN = 64


class Vendor(str, Enum):
    cisco = "cisco"
    brocade = "brocade"


class ZoneMode(str, Enum):
    single = "single"
    many = "many"


class NameOrder(str, Enum):
    it = "it"  # initiator_target
    ti = "ti"  # target_initiator


def normalize_wwpn(wwpn: str) -> str:
    """Normalize WWPN to lowercase with leading-zero bytes."""
    parts = wwpn.strip().lower().split(":")
    return ":".join(p.zfill(2) for p in parts)


def validate_wwpn(wwpn: str) -> str:
    """Validate and normalize a WWPN. Raises ValueError if invalid."""
    normalized = normalize_wwpn(wwpn)
    if not WWPN_RE.match(normalized):
        raise ValueError(f"Invalid WWPN: {wwpn}")
    return normalized


def validate_alias_name(name: str) -> str:
    """Validate alias name — safe chars only. Raises ValueError if invalid."""
    name = name.strip()
    if not name:
        raise ValueError("Alias name cannot be empty")
    if len(name) > MAX_ALIAS_LEN:
        raise ValueError(f"Alias name too long ({len(name)} > {MAX_ALIAS_LEN}): {name}")
    if not ALIAS_RE.match(name):
        raise ValueError(f"Alias name contains invalid characters: {name}")
    return name


@dataclass
class HBA:
    """Host Bus Adapter (initiator)."""

    alias: str
    wwpn: str
    host: str = ""
    fabric: str = ""
    vsan_id: int = 0
    description: str = ""

    def __post_init__(self) -> None:
        self.alias = validate_alias_name(self.alias)
        self.wwpn = validate_wwpn(self.wwpn)


@dataclass
class Target:
    """Storage target port."""

    alias: str
    wwpn: str
    group: str = ""
    storage_array: str = ""
    port: str = ""
    fabric: str = ""
    vsan_id: int = 0
    description: str = ""

    def __post_init__(self) -> None:
        self.alias = validate_alias_name(self.alias)
        self.wwpn = validate_wwpn(self.wwpn)


@dataclass
class Zone:
    """A SAN zone pairing initiator(s) with target(s)."""

    name: str
    initiator: HBA
    targets: list[Target] = field(default_factory=list)

    @staticmethod
    def build_name(
        initiator_alias: str,
        target_alias: str,
        order: NameOrder = NameOrder.ti,
        separator: str = "__",
    ) -> str:
        if order == NameOrder.it:
            return f"{initiator_alias}{separator}{target_alias}"
        return f"{target_alias}{separator}{initiator_alias}"


@dataclass
class ZoneSet:
    """Collection of zones."""

    name: str
    zones: list[Zone] = field(default_factory=list)


@dataclass
class Configuration:
    """Full SAN configuration context."""

    vendor: Vendor = Vendor.cisco
    mode: ZoneMode = ZoneMode.single
    order: NameOrder = NameOrder.ti
    separator: str = "__"
    vsan: int = 0
    vsan_name: str = ""
    iface_range: str = "1-32"
    zoneset_name: str = ""
    initiators: list[HBA] = field(default_factory=list)
    targets: list[Target] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    dry_run: bool = False
    rollback: bool = False
