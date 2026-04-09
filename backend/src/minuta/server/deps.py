"""FastAPI dependency injection helpers."""

from __future__ import annotations

from fastapi import HTTPException, Request

from minuta.db.repository import MeetingRepository
from minuta.models.config import AppSettings
from minuta.services.license import get_license_manager
from minuta.services.meeting_manager import MeetingManager
from minuta.services.transcript_hub import TranscriptHub


def get_settings(request: Request) -> AppSettings:
    return request.app.state.settings


def get_repo(request: Request) -> MeetingRepository:
    return request.app.state.repo


def get_hub(request: Request) -> TranscriptHub:
    return request.app.state.hub


def get_meeting_manager(request: Request) -> MeetingManager:
    return request.app.state.meeting_manager


def require_pro(feature: str = "webhook"):
    """Dependency that checks if a Pro feature is allowed."""
    def _check():
        lm = get_license_manager()
        if not lm.feature_allowed(feature):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "pro_required",
                    "feature": feature,
                    "message": f"'{feature}' ist ein Pro-Feature. Upgrade auf Minuta Pro.",
                    "plan": lm.plan_name,
                },
            )
    return _check
