import os
import yaml
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from san_zone_designer.license_check import verify_and_decode, LicenseError

router = APIRouter(prefix="/api/config", tags=["config"])

# Paths
DATABASE_DIR = Path("database")
CONFIG_FILE = DATABASE_DIR / "configuration.yaml"
PUBLIC_KEY_FILE = Path("san_zone_designer/license_public.pem")

# Ensure database directory exists
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

class LicenseRequest(BaseModel):
    license_key: str

@router.get("/license")
async def get_license():
    """Retrieve the current license and its decoded info."""
    if not CONFIG_FILE.exists():
        return {"license_key": None, "info": None}

    try:
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        return {"license_key": None, "info": None, "error": f"Failed to read config: {str(e)}"}

    license_key = config.get("license_key")
    if not license_key:
        return {"license_key": None, "info": None}

    # Decode license
    try:
        if not PUBLIC_KEY_FILE.exists():
            return {"license_key": license_key, "info": None, "error": "Public key missing."}
        
        with open(PUBLIC_KEY_FILE, "rb") as f:
            public_pem = f.read()

        info = verify_and_decode(license_key, public_pem)
        return {"license_key": license_key, "info": info}
    except LicenseError as e:
        return {"license_key": license_key, "info": None, "error": str(e)}
    except Exception as e:
        return {"license_key": license_key, "info": None, "error": f"Verification error: {str(e)}"}

@router.post("/license")
async def set_license(req: LicenseRequest):
    """Verify and save a new license key."""
    if not req.license_key:
        raise HTTPException(status_code=400, detail="License key cannot be empty.")

    # 1. Verify before saving
    try:
        if not PUBLIC_KEY_FILE.exists():
            raise HTTPException(status_code=500, detail="Server misconfiguration: Public key missing.")
            
        with open(PUBLIC_KEY_FILE, "rb") as f:
            public_pem = f.read()

        info = verify_and_decode(req.license_key, public_pem)
    except LicenseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

    # 2. Save
    try:
        config: Dict[str, Any] = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    config.update(loaded)
        
        config["license_key"] = req.license_key
        
        with open(CONFIG_FILE, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
            
        return {"message": "License key saved successfully.", "info": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save license key: {str(e)}")
