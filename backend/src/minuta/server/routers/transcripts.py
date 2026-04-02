"""Transcript endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from minuta.db.repository import MeetingRepository
from minuta.models.meeting import TranscriptSegment
from minuta.server.deps import get_repo, require_pro

router = APIRouter()


@router.get("/meetings/{meeting_id}/transcript", response_model=list[TranscriptSegment])
async def get_transcript(
    meeting_id: str,
    repo: MeetingRepository = Depends(get_repo),
):
    meeting = await repo.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return await repo.get_transcript(meeting_id)


@router.get("/meetings/{meeting_id}/transcript/export", dependencies=[Depends(require_pro("export_csv"))])
async def export_transcript(
    meeting_id: str,
    format: str = "markdown",
    repo: MeetingRepository = Depends(get_repo),
):
    meeting = await repo.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    segments = await repo.get_transcript(meeting_id)
    if not segments:
        raise HTTPException(status_code=404, detail="No transcript available")

    if format == "markdown":
        lines = [f"# Meeting Transkript: {meeting.title or meeting.id}\n"]
        lines.append(f"**Datum:** {meeting.started_at.strftime('%d.%m.%Y %H:%M')}\n")
        if meeting.duration_seconds:
            mins = meeting.duration_seconds // 60
            lines.append(f"**Dauer:** {mins} Minuten\n")
        lines.append("---\n")
        current_speaker = ""
        for seg in segments:
            if seg.speaker != current_speaker:
                current_speaker = seg.speaker
                lines.append(f"\n**{current_speaker}:**\n")
            lines.append(f"{seg.text}\n")
        content = "\n".join(lines)
        return PlainTextResponse(content, media_type="text/markdown")

    # Plain text
    lines = []
    for seg in segments:
        ts = f"[{int(seg.start_time // 60):02d}:{int(seg.start_time % 60):02d}]"
        lines.append(f"{ts} {seg.speaker}: {seg.text}")
    return PlainTextResponse("\n".join(lines), media_type="text/plain")
