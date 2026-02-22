"""Diff endpoint: compare new zones against existing config."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

from ...differ import compute_diff
from ...importer import import_zones
from ...selector import batch_select
from ..audit import audit_log
from ..auth import check_project_access, get_current_user
from ..dependencies import autosave, build_web_config, resolve_db_path
from ..schemas import DiffRequest, DiffResponse

router = APIRouter(prefix="/api/diff", tags=["diff"])


def _zone_to_dict(zone) -> dict:
    return {
        "name": zone.name,
        "initiator": zone.initiator.alias,
        "initiator_wwpn": zone.initiator.wwpn,
        "targets": [{"alias": t.alias, "wwpn": t.wwpn} for t in zone.targets],
    }


@router.post("/", response_model=DiffResponse)
async def diff_zones(req: DiffRequest, user: dict = Depends(get_current_user)):
    """Compare generated zones against existing zone configuration."""
    project = req.initiators_path.split("/")[0] if "/" in req.initiators_path else ""
    if project:
        check_project_access(user, project)
    if req.vendor == "cisco" and req.vsan == 0:
        raise HTTPException(status_code=400, detail="VSAN is required for Cisco")

    if not req.existing_path:
        raise HTTPException(status_code=400, detail="Existing zone config path is required")

    config = build_web_config(
        initiators_path=req.initiators_path,
        targets_path=req.targets_path,
        vendor=req.vendor,
        mode=req.mode,
        order=req.order,
        separator=req.separator,
        vsan=req.vsan,
        vsan_name=req.vsan_name,
        iface_range=req.iface_range,
        zoneset_name=req.zoneset_name,
        fabric_filter=req.fabric_filter,
        rollback=req.rollback,
    )

    config.zones = batch_select(config)
    new_zones = config.zones

    abs_existing = resolve_db_path(req.existing_path)
    if not abs_existing.exists():
        raise HTTPException(status_code=404, detail=f"Existing zone file not found: {req.existing_path}")

    existing_zones = import_zones(str(abs_existing), req.vendor)

    result = compute_diff(existing_zones, new_zones)

    added = [_zone_to_dict(z) for z in result.added]
    removed = [_zone_to_dict(z) for z in result.removed]
    unchanged = [_zone_to_dict(z) for z in result.unchanged]
    modified = [
        {"old": _zone_to_dict(old), "new": _zone_to_dict(new)}
        for old, new in result.modified
    ]

    summary = {
        "added": len(result.added),
        "removed": len(result.removed),
        "unchanged": len(result.unchanged),
        "modified": len(result.modified),
    }

    # Auto-save diff report to the project working directory
    import json
    project = req.initiators_path.split("/")[0] if "/" in req.initiators_path else ""
    diff_report = json.dumps({"added": added, "removed": removed, "unchanged": unchanged, "modified": modified, "summary": summary}, indent=2)
    saved = [autosave("diff", diff_report, ".json", project=project)]

    logger.info(
        "User '%s' ran diff for project '%s': +%d -%d ~%d =%d zones",
        user["username"], project, summary["added"], summary["removed"], summary["modified"], summary["unchanged"],
    )
    audit_log("config.diff", user, project=project, detail=summary)
    return DiffResponse(
        added=added,
        removed=removed,
        unchanged=unchanged,
        modified=modified,
        summary=summary,
        saved_files=saved,
    )
