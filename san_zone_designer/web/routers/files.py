"""File management CRUD endpoints."""

from __future__ import annotations

import logging

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

logger = logging.getLogger(__name__)

from ...migrator import detect_type_from_filename
from ...models import HBA, Target
from ...parser import load_initiators, load_targets
from ...validator import check_duplicates, scan_raw_file_warnings
from ..audit import audit_log
from ..auth import check_project_access, get_current_user, grant_project_access, require_admin
from ..dependencies import DATABASE_DIR, DELETED_DIR, resolve_db_path, soft_delete_file, soft_delete_project
from ..schemas import (
    FileContentResponse,
    FileInfo,
    FileListResponse,
    FileSaveRequest,
    FileSaveResponse,
    ProjectCreateRequest,
    ProjectInfo,
)

router = APIRouter(prefix="/api/files", tags=["files"])

ALLOWED_EXTENSIONS = {".yaml", ".yml", ".txt", ".cfg", ".csv", ".json"}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


async def _read_limited(file: UploadFile) -> bytes:
    """Read UploadFile in 64 KB chunks, raise 413 if MAX_UPLOAD_SIZE is exceeded."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' exceeds maximum upload size of {MAX_UPLOAD_SIZE // 1024 // 1024} MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _detect_file_type(filename: str) -> str:
    """Detect file type from filename."""
    result = detect_type_from_filename(filename)
    if result == "auto":
        return "unknown"
    return result


def _collect_files(directory, allowed_exts):
    """Collect FileInfo items from a directory."""
    files: list[FileInfo] = []
    for f in sorted(directory.iterdir()):
        if f.is_file() and f.suffix in allowed_exts:
            files.append(FileInfo(
                name=f.name,
                type=_detect_file_type(f.name),
                size=f.stat().st_size,
            ))
    return files


@router.get("/", response_model=FileListResponse)
async def list_files(include_output: bool = Query(False), user: dict = Depends(get_current_user)):
    """List all files grouped by project.

    By default _output/ subdirectories are hidden.
    Pass ?include_output=true to include them (used by Manage Files modal).
    Non-admin users only see their assigned projects.
    """
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    projects: list[ProjectInfo] = []
    user_projects = user.get("projects", [])
    is_admin = user["role"] == "admin"

    for project_dir in sorted(DATABASE_DIR.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue
        # Always hide system directories regardless of include_output
        if project_dir.name in {"logs", "_generated", "deleted"}:
            continue

        # Filter by user access
        if not is_admin and project_dir.name not in user_projects:
            continue

        files = _collect_files(project_dir, ALLOWED_EXTENSIONS)

        # Include _output/ subfolder contents if requested
        output_dir = project_dir / "_output"
        if include_output and output_dir.is_dir():
            for f in sorted(output_dir.iterdir()):
                if f.is_file() and f.suffix in ALLOWED_EXTENSIONS:
                    files.append(FileInfo(
                        name=f"_output/{f.name}",
                        type=_detect_file_type(f.name),
                        size=f.stat().st_size,
                    ))

        projects.append(ProjectInfo(name=project_dir.name, files=files))

    return FileListResponse(projects=projects)


@router.post("/project")
async def create_project(req: ProjectCreateRequest, user: dict = Depends(get_current_user)):
    """Create a new project directory. Any authenticated user can create a project.
    Non-admin users automatically receive access to the project they created.
    """
    name = req.name.strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="Invalid project name")

    project_path = resolve_db_path(name)
    if project_path.exists():
        raise HTTPException(status_code=409, detail=f"Project '{name}' already exists")

    project_path.mkdir(parents=True, exist_ok=True)
    logger.info("Project '%s' created by user '%s'", name, user["username"])
    audit_log("project.created", user, project=name)

    # Grant access to the creator (no-op for admins)
    grant_project_access(user["username"], name)

    return {"message": f"Project '{name}' created", "name": name}


@router.post("/upload")
async def upload_files(project: str, files: list[UploadFile], user: dict = Depends(get_current_user)):
    """Upload files to a project directory."""
    if not project.strip():
        raise HTTPException(status_code=400, detail="Project name is required")

    check_project_access(user, project)

    project_path = resolve_db_path(project)
    project_path.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for file in files:
        if not file.filename:
            continue
        ext = "." + file.filename.rsplit(".", 1)[-1] if "." in file.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file extension: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        dest = project_path / file.filename
        content = await _read_limited(file)
        dest.write_bytes(content)
        uploaded.append(file.filename)

    logger.info("User '%s' uploaded %d file(s) to project '%s': %s", user["username"], len(uploaded), project, uploaded)
    audit_log("file.uploaded", user, project=project, detail={"files": uploaded, "count": len(uploaded)})
    return {"message": f"Uploaded {len(uploaded)} file(s)", "files": uploaded}


@router.get("/{project}/{filename:path}", response_model=FileContentResponse)
async def preview_file(project: str, filename: str, user: dict = Depends(get_current_user)):
    """Preview file content and parsed entries."""
    check_project_access(user, project)

    file_path = resolve_db_path(f"{project}/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    content = file_path.read_text(encoding="utf-8")
    base_name = file_path.name
    file_type = _detect_file_type(base_name)

    entries: list[dict] = []
    warnings: list[str] = []
    try:
        if file_type == "initiators":
            hbas = load_initiators(file_path)
            entries = [
                {"alias": h.alias, "wwpn": h.wwpn, "host": h.host, "fabric": h.fabric,
                 "vsan_id": h.vsan_id, "description": h.description}
                for h in hbas
            ]
            warnings += scan_raw_file_warnings(file_path, "initiators")
        elif file_type == "targets":
            tgts = load_targets(file_path, mode="many")
            entries = [
                {"alias": t.alias, "wwpn": t.wwpn, "group": t.group, "storage_array": t.storage_array,
                 "port": t.port, "fabric": t.fabric, "vsan_id": t.vsan_id, "description": t.description}
                for t in tgts
            ]
            warnings += scan_raw_file_warnings(file_path, "targets")
    except Exception as exc:
        logger.warning("Could not parse entries from '%s/%s': %s", project, filename, exc)
        warnings.append(f"Parse error: {exc}")

    if warnings:
        logger.warning("Validation warnings for '%s/%s': %s", project, filename, warnings)

    return FileContentResponse(content=content, entries=entries, file_type=file_type, warnings=warnings)


@router.put("/{project}/{filename:path}", response_model=FileSaveResponse)
async def save_file(project: str, filename: str, req: FileSaveRequest, user: dict = Depends(get_current_user)):
    """Save edited entries back to a YAML file."""
    check_project_access(user, project)

    file_path = resolve_db_path(f"{project}/{filename}")
    if file_path.suffix not in (".yaml", ".yml"):
        raise HTTPException(status_code=400, detail="Only YAML files can be edited")

    file_type = req.file_type
    if file_type not in ("initiators", "targets"):
        raise HTTPException(status_code=400, detail="file_type must be 'initiators' or 'targets'")

    validated: list[dict] = []
    warnings: list[str] = []

    for entry in req.entries:
        alias = str(entry.get("alias", "")).strip()
        wwpn = str(entry.get("wwpn", "")).strip()
        if not alias or not wwpn:
            continue  # skip incomplete entries

        try:
            if file_type == "initiators":
                obj = HBA(
                    alias=alias,
                    wwpn=wwpn,
                    host=str(entry.get("host", "")).strip(),
                    fabric=str(entry.get("fabric", "")).strip(),
                    vsan_id=int(entry.get("vsan_id", 0) or 0),
                    description=str(entry.get("description", "")).strip(),
                )
                d = {"alias": obj.alias, "wwpn": obj.wwpn}
                if obj.host:
                    d["host"] = obj.host
                if obj.fabric:
                    d["fabric"] = obj.fabric
                if obj.vsan_id:
                    d["vsan_id"] = obj.vsan_id
                if obj.description:
                    d["description"] = obj.description
            else:
                obj = Target(
                    alias=alias,
                    wwpn=wwpn,
                    group=str(entry.get("group", "")).strip(),
                    storage_array=str(entry.get("storage_array", "")).strip(),
                    port=str(entry.get("port", "")).strip(),
                    fabric=str(entry.get("fabric", "")).strip(),
                    vsan_id=int(entry.get("vsan_id", 0) or 0),
                    description=str(entry.get("description", "")).strip(),
                )
                d = {"alias": obj.alias, "wwpn": obj.wwpn}
                if obj.group:
                    d["group"] = obj.group
                if obj.storage_array:
                    d["storage_array"] = obj.storage_array
                if obj.port:
                    d["port"] = obj.port
                if obj.fabric:
                    d["fabric"] = obj.fabric
                if obj.vsan_id:
                    d["vsan_id"] = obj.vsan_id
                if obj.description:
                    d["description"] = obj.description
            validated.append(d)
        except ValueError as exc:
            warnings.append(f"{alias}: {exc}")

    # Check for duplicates
    pairs = [(d["alias"], d["wwpn"]) for d in validated]
    warnings += check_duplicates(pairs)

    # Write YAML
    yaml_data = {file_type: validated}
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    logger.info("User '%s' edited '%s/%s': %d entries", user["username"], project, filename, len(validated))
    audit_log("file.edited", user, project=project, detail={"filename": filename, "entry_count": len(validated)})

    return FileSaveResponse(saved=True, warnings=warnings, entry_count=len(validated))


@router.delete("/{project}/{filename:path}")
async def delete_file(project: str, filename: str, user: dict = Depends(get_current_user)):
    """Delete a file from a project (supports _output/filename paths)."""
    check_project_access(user, project)

    file_path = resolve_db_path(f"{project}/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    archived_path = soft_delete_file(project, filename)

    logger.info("User '%s' archived file '%s/%s' → '%s'", user["username"], project, filename, archived_path)
    audit_log("file.deleted", user, project=project, detail={"filename": filename, "archived_to": archived_path})
    return {"message": f"Archived {project}/{filename}"}


@router.delete("/{project}")
async def delete_project(project: str, user: dict = Depends(require_admin)):
    """Archive a project directory to deleted/. Admin only. Data is recoverable."""
    project_path = resolve_db_path(project)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    archived_path = soft_delete_project(project)
    logger.warning(
        "Admin '%s' archived project '%s' → '%s'",
        user["username"], project, archived_path,
    )
    audit_log("project.deleted", user, project=project, detail={"archived_to": archived_path})
    return {"message": f"Project '{project}' archived to '{archived_path}'"}
