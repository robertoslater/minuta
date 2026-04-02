"""License management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from minuta.services.license import get_license_manager

router = APIRouter()


@router.get("/license")
async def get_license_status():
    """Return current license status."""
    lm = get_license_manager()
    return lm.get_status()


class ActivateRequest(BaseModel):
    license_key: str


@router.post("/license/activate")
async def activate_license(data: ActivateRequest):
    """Activate a Pro license key."""
    lm = get_license_manager()
    result = await lm.activate(data.license_key)
    if result["status"] == "invalid":
        raise HTTPException(status_code=400, detail=result.get("message", "Invalid key"))
    return result


@router.post("/license/deactivate")
async def deactivate_license():
    """Deactivate the current license."""
    lm = get_license_manager()
    return await lm.deactivate()
