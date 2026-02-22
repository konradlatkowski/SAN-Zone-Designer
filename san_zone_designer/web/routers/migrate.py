"""Migration endpoints: txt → yaml conversion."""

from __future__ import annotations

from pathlib import Path

import yaml
import logging

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

from ...migrator import (
    detect_host_from_alias,
    detect_storage_array_from_alias,
    detect_type_from_filename,
    migrate_initiators,
    migrate_targets,
)
from ...parser import load_initiators, load_targets
from ..audit import audit_log
from ..auth import check_project_access, get_current_user
from ..dependencies import DATABASE_DIR, autosave, resolve_db_path
from ..schemas import MigratePreviewResponse, MigrateRequest

router = APIRouter(prefix="/api/migrate", tags=["migrate"])


def _extract_project(path: str) -> str:
    parts = path.split("/")
    return parts[0] if len(parts) > 1 else ""


@router.post("/preview", response_model=MigratePreviewResponse)
async def migrate_preview(req: MigrateRequest, user: dict = Depends(get_current_user)):
    """Preview YAML migration without saving."""
    input_project = _extract_project(req.input_path)
    if input_project:
        check_project_access(user, input_project)
    check_project_access(user, req.output_project)
    abs_input = resolve_db_path(req.input_path)
    if not abs_input.exists():
        raise HTTPException(status_code=404, detail=f"Input file not found: {req.input_path}")

    file_type = req.file_type
    if file_type == "auto":
        file_type = detect_type_from_filename(abs_input.name)
        if file_type == "auto":
            raise HTTPException(
                status_code=400,
                detail="Cannot auto-detect file type. Specify 'initiators' or 'targets'.",
            )

    if file_type == "initiators":
        hbas = load_initiators(abs_input)
        data = {"initiators": []}
        for hba in hbas:
            entry: dict = {"alias": hba.alias, "wwpn": hba.wwpn, "host": detect_host_from_alias(hba.alias)}
            if hba.fabric:
                entry["fabric"] = hba.fabric
            data["initiators"].append(entry)
        yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return MigratePreviewResponse(yaml_content=yaml_content, entry_count=len(hbas), file_type=file_type)
    else:
        tgts = load_targets(abs_input, mode="many")
        data = {"targets": []}
        for tgt in tgts:
            entry = {"alias": tgt.alias, "wwpn": tgt.wwpn}
            if tgt.group:
                entry["group"] = tgt.group
            entry["storage_array"] = detect_storage_array_from_alias(tgt.alias)
            data["targets"].append(entry)
        yaml_content = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return MigratePreviewResponse(yaml_content=yaml_content, entry_count=len(tgts), file_type=file_type)


@router.post("/")
async def migrate_file(req: MigrateRequest, user: dict = Depends(get_current_user)):
    """Migrate txt → yaml and save to database/."""
    input_project = _extract_project(req.input_path)
    if input_project:
        check_project_access(user, input_project)
    check_project_access(user, req.output_project)
    abs_input = resolve_db_path(req.input_path)
    if not abs_input.exists():
        raise HTTPException(status_code=404, detail=f"Input file not found: {req.input_path}")

    file_type = req.file_type
    if file_type == "auto":
        file_type = detect_type_from_filename(abs_input.name)
        if file_type == "auto":
            raise HTTPException(
                status_code=400,
                detail="Cannot auto-detect file type. Specify 'initiators' or 'targets'.",
            )

    output_dir = resolve_db_path(req.output_project)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_filename = req.output_filename
    if not output_filename.endswith((".yaml", ".yml")):
        output_filename += ".yaml"

    output_path = output_dir / output_filename

    if file_type == "initiators":
        count = migrate_initiators(str(abs_input), str(output_path))
    else:
        count = migrate_targets(str(abs_input), str(output_path))

    # Auto-save a copy to the output project directory
    yaml_content = output_path.read_text(encoding="utf-8")
    saved = autosave("migrate", yaml_content, ".yaml", project=req.output_project)

    logger.info(
        "User '%s' migrated '%s' → '%s/%s' (%d entries, type=%s)",
        user["username"], req.input_path, req.output_project, output_filename, count, file_type,
    )
    audit_log("file.migrated", user, project=req.output_project, detail={
        "input": req.input_path, "output": f"{req.output_project}/{output_filename}",
        "entries": count, "file_type": file_type,
    })
    return {
        "message": f"Migrated {count} entries",
        "output": f"{req.output_project}/{output_filename}",
        "count": count,
        "file_type": file_type,
        "saved_files": [saved],
    }
