"""Summary generation and retrieval endpoints."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from minuta.db.repository import MeetingRepository
from minuta.models.config import AppSettings
from minuta.models.meeting import Summary, SummarizeRequest
from minuta.server.deps import get_repo, get_settings
from minuta.services.summarizer import create_summarizer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/meetings/{meeting_id}/summarize", response_model=Summary)
async def summarize_meeting(
    meeting_id: str,
    request: SummarizeRequest = SummarizeRequest(),
    repo: MeetingRepository = Depends(get_repo),
    settings: AppSettings = Depends(get_settings),
):
    meeting = await repo.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    segments = await repo.get_transcript(meeting_id)
    if not segments:
        raise HTTPException(status_code=400, detail="No transcript to summarize")

    # Build transcript text
    transcript_text = "\n".join(
        f"[{seg.speaker}] {seg.text}" for seg in segments
    )

    provider = request.provider or settings.summarization.default_provider
    summarizer = create_summarizer(provider, settings)

    start = time.time()
    try:
        result = await summarizer.summarize(
            transcript=transcript_text,
            language=request.language,
            model_override=request.model,
        )
    except Exception as e:
        logger.error("Summarization failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Summarization failed: {e}")

    summary = Summary(
        id=uuid.uuid4().hex[:12],
        meeting_id=meeting_id,
        provider=provider,
        model=result.model,
        title=result.title,
        key_points=result.key_points,
        action_items=result.action_items,
        decisions=result.decisions,
        sections=result.sections,
        participants_mentioned=result.participants_mentioned,
        full_text=result.full_text,
        language=request.language,
        token_count=result.token_count,
        generation_time_seconds=round(time.time() - start, 2),
    )
    await repo.save_summary(summary)
    return summary


@router.get("/meetings/{meeting_id}/summary", response_model=Summary | None)
async def get_summary(
    meeting_id: str,
    repo: MeetingRepository = Depends(get_repo),
):
    meeting = await repo.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    summary = await repo.get_summary(meeting_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="No summary available")
    return summary


class SummaryUpdate(BaseModel):
    title: str | None = None
    full_text: str | None = None
    key_points: list[str] | None = None
    action_items: list[str] | None = None
    decisions: list[str] | None = None


@router.put("/meetings/{meeting_id}/summary", response_model=Summary)
async def update_summary(
    meeting_id: str,
    data: SummaryUpdate,
    repo: MeetingRepository = Depends(get_repo),
):
    meeting = await repo.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    summary = await repo.update_summary(
        meeting_id,
        title=data.title,
        full_text=data.full_text,
        key_points=data.key_points,
        action_items=data.action_items,
        decisions=data.decisions,
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="No summary to update")
    return summary
