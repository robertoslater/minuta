"""Meeting CRUD endpoints with audio capture integration."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from minuta.db.repository import MeetingRepository
from minuta.models.config import AppSettings
from minuta.models.meeting import Meeting, MeetingCreate, MeetingUpdate, WebhookPayload
from minuta.server.deps import get_repo, get_meeting_manager, get_settings, require_pro
from minuta.services.meeting_manager import MeetingManager
from minuta.services.webhook import send_webhook

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/meetings", response_model=list[Meeting])
async def list_meetings(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    repo: MeetingRepository = Depends(get_repo),
):
    return await repo.list_meetings(status=status, limit=limit, offset=offset)


@router.post("/meetings", response_model=Meeting, status_code=201)
async def create_meeting(
    data: MeetingCreate,
    manager: MeetingManager = Depends(get_meeting_manager),
):
    """Create a new meeting and start audio recording."""
    try:
        meeting = await manager.start_recording(data)
        return meeting
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error("Failed to start recording: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to start recording: {e}")


@router.get("/meetings/{meeting_id}", response_model=Meeting)
async def get_meeting(
    meeting_id: str,
    repo: MeetingRepository = Depends(get_repo),
):
    meeting = await repo.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.put("/meetings/{meeting_id}", response_model=Meeting)
async def update_meeting(
    meeting_id: str,
    data: MeetingUpdate,
    repo: MeetingRepository = Depends(get_repo),
):
    meeting = await repo.update_meeting(meeting_id, data)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.delete("/meetings/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: str,
    repo: MeetingRepository = Depends(get_repo),
):
    deleted = await repo.delete_meeting(meeting_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Meeting not found")


@router.post("/meetings/{meeting_id}/stop", response_model=Meeting)
async def stop_meeting(
    meeting_id: str,
    manager: MeetingManager = Depends(get_meeting_manager),
):
    """Stop the current recording."""
    meeting = await manager.stop_recording()
    if meeting is None:
        raise HTTPException(status_code=404, detail="No active recording to stop")
    return meeting


@router.post("/meetings/{meeting_id}/webhook", dependencies=[Depends(require_pro("webhook"))])
async def trigger_webhook(
    meeting_id: str,
    repo: MeetingRepository = Depends(get_repo),
    settings: AppSettings = Depends(get_settings),
):
    """Manually send webhook for a meeting."""
    meeting = await repo.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    segments = await repo.get_transcript(meeting_id)
    summary = await repo.get_summary(meeting_id)

    payload = WebhookPayload(
        meeting=meeting,
        transcript=segments if settings.webhook.include_transcript else None,
        summary=summary if settings.webhook.include_summary else None,
    )
    sent = await send_webhook(settings.webhook, payload)
    if sent:
        await repo.set_webhook_sent(meeting_id)
        return {"status": "sent"}
    raise HTTPException(status_code=502, detail="Webhook delivery failed")
