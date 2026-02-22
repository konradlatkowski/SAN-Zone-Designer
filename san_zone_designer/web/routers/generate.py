"""Generation endpoints: preview, init (all×all), expand (selected pairs)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

from ...models import NameOrder, Zone, ZoneMode
from ...selector import batch_select
from ...validator import scan_raw_file_warnings
from ..audit import audit_log
from ..auth import check_project_access, get_current_user
from ..dependencies import autosave, build_web_config, get_generator, resolve_db_path
from ..schemas import (
    ExpandRequest,
    GenerateRequest,
    GenerateResponse,
    PreviewResponse,
    ZoneEntry,
)

router = APIRouter(prefix="/api/generate", tags=["generate"])


def _collect_config_warnings(config, initiators_path: str, targets_path: str) -> list[str]:
    """Collect all validation warnings (invalid format, duplicates, WWPN range)."""
    warnings: list[str] = []
    try:
        abs_init = resolve_db_path(initiators_path)
        warnings += scan_raw_file_warnings(abs_init, "initiators")
    except Exception:
        pass
    try:
        abs_tgt = resolve_db_path(targets_path)
        warnings += scan_raw_file_warnings(abs_tgt, "targets")
    except Exception:
        pass
    return warnings


def _extract_project(path: str) -> str:
    """Extract project name from a path like 'MyProject/initiators.yaml' → 'MyProject'."""
    parts = path.split("/")
    return parts[0] if len(parts) > 1 else ""


def _zones_to_entries(zones: list[Zone]) -> list[ZoneEntry]:
    return [
        ZoneEntry(
            name=z.name,
            initiator_alias=z.initiator.alias,
            initiator_wwpn=z.initiator.wwpn,
            target_aliases=[t.alias for t in z.targets],
            target_wwpns=[t.wwpn for t in z.targets],
        )
        for z in zones
    ]


def _build_summary(config) -> dict:
    summary = {
        "vendor": config.vendor.value,
        "mode": config.mode.value,
        "initiators": len(config.initiators),
        "targets": len(config.targets),
        "zones": len(config.zones),
        "zoneset": config.zoneset_name,
    }
    if config.mode == ZoneMode.many:
        groups = set(t.group for t in config.targets if t.group)
        summary["groups"] = len(groups)
    return summary


@router.post("/preview", response_model=PreviewResponse)
async def generate_preview(req: GenerateRequest, user: dict = Depends(get_current_user)):
    project = _extract_project(req.initiators_path)
    if project:
        check_project_access(user, project)
    """Dry-run: load files, show initiators/targets/zones without generating config."""
    if req.vendor == "cisco" and req.vsan == 0:
        raise HTTPException(status_code=400, detail="VSAN is required for Cisco")

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

    initiators = [
        {"alias": h.alias, "wwpn": h.wwpn, "host": h.host, "fabric": h.fabric}
        for h in config.initiators
    ]
    targets = [
        {"alias": t.alias, "wwpn": t.wwpn, "group": t.group, "storage_array": t.storage_array}
        for t in config.targets
    ]
    warnings = _collect_config_warnings(config, req.initiators_path, req.targets_path)

    return PreviewResponse(
        initiators=initiators,
        targets=targets,
        zones=_zones_to_entries(config.zones),
        summary=_build_summary(config),
        warnings=warnings,
    )


@router.post("/init", response_model=GenerateResponse)
async def generate_init(req: GenerateRequest, user: dict = Depends(get_current_user)):
    """Full generation: all initiators × all targets → config text + CSV."""
    project = _extract_project(req.initiators_path)
    if project:
        check_project_access(user, project)
    if req.vendor == "cisco" and req.vsan == 0:
        raise HTTPException(status_code=400, detail="VSAN is required for Cisco")

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

    gen = get_generator(config)
    result = gen.generate()

    csv_header = "ZoneName;Initiator;InitiatorWWPN;Target;TargetWWPN;VSAN"
    csv_content = csv_header + "\n" + "\n".join(gen.csv_lines)

    rollback_cfg = ""
    if config.rollback:
        rollback_cfg = gen.rollback_cfg

    project = _extract_project(req.initiators_path)
    saved = []
    saved.append(autosave("initial", result, ".cfg", project=project))
    saved.append(autosave("initial", csv_content, ".csv", project=project))
    if rollback_cfg:
        saved.append(autosave("initial_rollback", rollback_cfg, ".cfg", project=project))

    warnings = _collect_config_warnings(config, req.initiators_path, req.targets_path)

    logger.info(
        "User '%s' generated initial config for project '%s': %d zones, vendor=%s, saved=%s",
        user["username"], project, len(config.zones), req.vendor, saved,
    )
    audit_log("config.generated", user, project=project, detail={
        "zones": len(config.zones), "vendor": req.vendor, "mode": req.mode, "saved_files": saved,
    })
    return GenerateResponse(
        config=result,
        summary=_build_summary(config),
        csv=csv_content,
        rollback_cfg=rollback_cfg,
        zones=_zones_to_entries(config.zones),
        saved_files=saved,
        warnings=warnings,
    )


@router.post("/expand", response_model=GenerateResponse)
async def generate_expand(req: ExpandRequest, user: dict = Depends(get_current_user)):
    """Generate config from selected initiator-target pairs."""
    project = _extract_project(req.initiators_path)
    if project:
        check_project_access(user, project)
    if req.vendor == "cisco" and req.vsan == 0:
        raise HTTPException(status_code=400, detail="VSAN is required for Cisco")

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

    if not req.selected_pairs:
        raise HTTPException(status_code=400, detail="No pairs selected")

    # Build zones from selected pairs
    init_by_alias = {h.alias: h for h in config.initiators}
    tgt_by_alias = {t.alias: t for t in config.targets}

    zones = []
    for pair in req.selected_pairs:
        init_alias = pair.get("initiator")
        tgt_aliases = pair.get("targets", [])

        if init_alias not in init_by_alias:
            raise HTTPException(status_code=400, detail=f"Unknown initiator: {init_alias}")

        init_obj = init_by_alias[init_alias]
        tgt_objs = []
        for ta in tgt_aliases:
            if ta not in tgt_by_alias:
                raise HTTPException(status_code=400, detail=f"Unknown target: {ta}")
            tgt_objs.append(tgt_by_alias[ta])

        if not tgt_objs:
            continue

        if config.mode == ZoneMode.single:
            for tgt in tgt_objs:
                zone_name = Zone.build_name(init_alias, tgt.alias, config.order, config.separator)
                zones.append(Zone(name=zone_name, initiator=init_obj, targets=[tgt]))
        else:
            group_name = tgt_aliases[0] if len(tgt_aliases) == 1 else pair.get("group", tgt_aliases[0])
            zone_name = Zone.build_name(init_alias, group_name, config.order, config.separator)
            zones.append(Zone(name=zone_name, initiator=init_obj, targets=tgt_objs))

    if not zones:
        raise HTTPException(status_code=400, detail="No valid zones from selected pairs")

    config.zones = zones

    gen = get_generator(config)
    result = gen.generate()

    csv_header = "ZoneName;Initiator;InitiatorWWPN;Target;TargetWWPN;VSAN"
    csv_content = csv_header + "\n" + "\n".join(gen.csv_lines)

    rollback_cfg = ""
    if config.rollback:
        rollback_cfg = gen.rollback_cfg

    project = _extract_project(req.initiators_path)
    saved = []
    saved.append(autosave("expand", result, ".cfg", project=project))
    saved.append(autosave("expand", csv_content, ".csv", project=project))
    if rollback_cfg:
        saved.append(autosave("expand_rollback", rollback_cfg, ".cfg", project=project))

    warnings = _collect_config_warnings(config, req.initiators_path, req.targets_path)

    logger.info(
        "User '%s' generated expand config for project '%s': %d zones from %d pairs, vendor=%s",
        user["username"], project, len(config.zones), len(req.selected_pairs), req.vendor,
    )
    audit_log("config.expanded", user, project=project, detail={
        "zones": len(config.zones), "pairs": len(req.selected_pairs), "vendor": req.vendor, "saved_files": saved,
    })
    return GenerateResponse(
        config=result,
        summary=_build_summary(config),
        csv=csv_content,
        rollback_cfg=rollback_cfg,
        zones=_zones_to_entries(config.zones),
        saved_files=saved,
        warnings=warnings,
    )
