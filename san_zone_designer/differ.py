"""Diff engine for comparing zone sets."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Zone


@dataclass
class ZoneDiff:
    """Result of comparing two sets of zones."""

    added: list[Zone] = field(default_factory=list)
    removed: list[Zone] = field(default_factory=list)
    unchanged: list[Zone] = field(default_factory=list)
    modified: list[tuple[Zone, Zone]] = field(default_factory=list)


def _zone_member_set(zone: Zone) -> frozenset[str]:
    """Extract set of member alias names from a zone."""
    members = {zone.initiator.alias}
    for t in zone.targets:
        members.add(t.alias)
    return frozenset(members)


def _zones_equivalent(a: Zone, b: Zone) -> bool:
    """Compare two zones by their member alias sets."""
    return _zone_member_set(a) == _zone_member_set(b)


def compute_diff(existing: list[Zone], new: list[Zone]) -> ZoneDiff:
    """Compute diff between existing zones and newly generated zones.

    Matching is done by zone name. Equivalence is checked by member alias sets.
    """
    existing_by_name: dict[str, Zone] = {z.name: z for z in existing}
    new_by_name: dict[str, Zone] = {z.name: z for z in new}

    diff = ZoneDiff()

    for name, new_zone in new_by_name.items():
        if name not in existing_by_name:
            diff.added.append(new_zone)
        elif _zones_equivalent(existing_by_name[name], new_zone):
            diff.unchanged.append(new_zone)
        else:
            diff.modified.append((existing_by_name[name], new_zone))

    for name, existing_zone in existing_by_name.items():
        if name not in new_by_name:
            diff.removed.append(existing_zone)

    return diff
