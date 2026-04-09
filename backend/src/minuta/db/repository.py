"""Data access layer for meetings, transcripts, and summaries."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from minuta.db.engine import Database
from minuta.models.meeting import (
    Meeting,
    MeetingCreate,
    MeetingStatus,
    MeetingUpdate,
    Summary,
    TranscriptSegment,
)


def _new_id(length: int = 12) -> str:
    return uuid.uuid4().hex[:length]


def _now_iso() -> str:
    return datetime.now().isoformat()


class MeetingRepository:
    def __init__(self, db: Database):
        self.db = db

    # --- Meetings ---

    async def create_meeting(self, data: MeetingCreate) -> Meeting:
        meeting_id = _new_id()
        now = _now_iso()
        await self.db.execute(
            """INSERT INTO meetings (id, title, status, started_at, audio_source, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (meeting_id, data.title, MeetingStatus.RECORDING.value, now,
             data.audio_source, json.dumps(data.tags), now),
        )
        await self.db.commit()
        return await self.get_meeting(meeting_id)  # type: ignore

    async def get_meeting(self, meeting_id: str) -> Meeting | None:
        row = await self.db.fetchone("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
        if row is None:
            return None
        return _row_to_meeting(row)

    async def list_meetings(
        self, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Meeting]:
        if status:
            rows = await self.db.fetchall(
                "SELECT * FROM meetings WHERE status = ? ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
        else:
            rows = await self.db.fetchall(
                "SELECT * FROM meetings ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [_row_to_meeting(r) for r in rows]

    async def update_meeting(self, meeting_id: str, data: MeetingUpdate) -> Meeting | None:
        updates = []
        params = []
        if data.title is not None:
            updates.append("title = ?")
            params.append(data.title)
        if data.company is not None:
            updates.append("company = ?")
            params.append(data.company)
        if data.project is not None:
            updates.append("project = ?")
            params.append(data.project)
        if data.domain is not None:
            updates.append("domain = ?")
            params.append(data.domain)
        if data.tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(data.tags))
        if data.notes is not None:
            updates.append("notes = ?")
            params.append(data.notes)
        if not updates:
            return await self.get_meeting(meeting_id)
        params.append(meeting_id)
        await self.db.execute(
            f"UPDATE meetings SET {', '.join(updates)} WHERE id = ?", tuple(params)
        )
        await self.db.commit()
        return await self.get_meeting(meeting_id)

    async def stop_meeting(self, meeting_id: str) -> Meeting | None:
        now = _now_iso()
        meeting = await self.get_meeting(meeting_id)
        if meeting is None:
            return None
        duration = int((datetime.now() - meeting.started_at).total_seconds())
        await self.db.execute(
            "UPDATE meetings SET status = ?, ended_at = ?, duration_seconds = ? WHERE id = ?",
            (MeetingStatus.COMPLETED.value, now, duration, meeting_id),
        )
        await self.db.commit()
        return await self.get_meeting(meeting_id)

    async def update_meeting_status(self, meeting_id: str, status: MeetingStatus) -> None:
        await self.db.execute(
            "UPDATE meetings SET status = ? WHERE id = ?", (status.value, meeting_id)
        )
        await self.db.commit()

    async def set_webhook_sent(self, meeting_id: str) -> None:
        await self.db.execute(
            "UPDATE meetings SET webhook_sent = 1, webhook_sent_at = ? WHERE id = ?",
            (_now_iso(), meeting_id),
        )
        await self.db.commit()

    async def delete_meeting(self, meeting_id: str) -> bool:
        cursor = await self.db.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        await self.db.commit()
        return cursor.rowcount > 0

    # --- Transcript Segments ---

    async def add_segment(self, segment: TranscriptSegment) -> None:
        await self.db.execute(
            """INSERT INTO transcript_segments
               (id, meeting_id, idx, speaker, source, text, start_time, end_time,
                confidence, language, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (segment.id, segment.meeting_id, segment.index, segment.speaker,
             segment.source, segment.text, segment.start_time, segment.end_time,
             segment.confidence, segment.language, segment.created_at.isoformat()),
        )
        await self.db.execute(
            "UPDATE meetings SET transcript_segment_count = transcript_segment_count + 1 WHERE id = ?",
            (segment.meeting_id,),
        )
        await self.db.commit()

    async def get_transcript(self, meeting_id: str) -> list[TranscriptSegment]:
        rows = await self.db.fetchall(
            "SELECT * FROM transcript_segments WHERE meeting_id = ? ORDER BY idx",
            (meeting_id,),
        )
        return [_row_to_segment(r) for r in rows]

    # --- Summaries ---

    async def save_summary(self, summary: Summary) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO summaries
               (id, meeting_id, provider, model, title, key_points, action_items,
                decisions, sections, participants_mentioned, full_text, language,
                token_count, generation_time_seconds, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (summary.id, summary.meeting_id, summary.provider, summary.model,
             summary.title, json.dumps(summary.key_points), json.dumps(summary.action_items),
             json.dumps(summary.decisions),
             json.dumps([s.model_dump() for s in summary.sections]),
             json.dumps(summary.participants_mentioned),
             summary.full_text, summary.language, summary.token_count,
             summary.generation_time_seconds, summary.created_at.isoformat()),
        )
        await self.db.execute(
            "UPDATE meetings SET has_summary = 1, summary_provider = ? WHERE id = ?",
            (summary.provider, summary.meeting_id),
        )
        await self.db.commit()

    async def update_summary(self, meeting_id: str, title: str | None = None,
                             full_text: str | None = None,
                             key_points: list[str] | None = None,
                             action_items: list[str] | None = None,
                             decisions: list[str] | None = None) -> Summary | None:
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if full_text is not None:
            updates.append("full_text = ?")
            params.append(full_text)
        if key_points is not None:
            updates.append("key_points = ?")
            params.append(json.dumps(key_points))
        if action_items is not None:
            updates.append("action_items = ?")
            params.append(json.dumps(action_items))
        if decisions is not None:
            updates.append("decisions = ?")
            params.append(json.dumps(decisions))
        if not updates:
            return await self.get_summary(meeting_id)
        params.append(meeting_id)
        await self.db.execute(
            f"UPDATE summaries SET {', '.join(updates)} WHERE meeting_id = ?", tuple(params)
        )
        await self.db.commit()
        return await self.get_summary(meeting_id)

    async def get_summary(self, meeting_id: str) -> Summary | None:
        row = await self.db.fetchone(
            "SELECT * FROM summaries WHERE meeting_id = ? ORDER BY created_at DESC LIMIT 1",
            (meeting_id,),
        )
        if row is None:
            return None
        return _row_to_summary(row)


def _row_to_meeting(row: dict) -> Meeting:
    return Meeting(
        id=row["id"],
        title=row["title"],
        status=MeetingStatus(row["status"]),
        started_at=datetime.fromisoformat(row["started_at"]),
        ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        duration_seconds=row["duration_seconds"],
        audio_source=row["audio_source"],
        transcript_segment_count=row["transcript_segment_count"],
        has_summary=bool(row["has_summary"]),
        summary_provider=row["summary_provider"],
        webhook_sent=bool(row["webhook_sent"]),
        webhook_sent_at=datetime.fromisoformat(row["webhook_sent_at"]) if row["webhook_sent_at"] else None,
        company=row.get("company", ""),
        project=row.get("project", ""),
        domain=row.get("domain", ""),
        tags=json.loads(row["tags"]),
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_segment(row: dict) -> TranscriptSegment:
    return TranscriptSegment(
        id=row["id"],
        meeting_id=row["meeting_id"],
        index=row["idx"],
        speaker=row["speaker"],
        source=row["source"],
        text=row["text"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        confidence=row["confidence"],
        language=row["language"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _row_to_summary(row: dict) -> Summary:
    from minuta.models.meeting import SummarySection
    return Summary(
        id=row["id"],
        meeting_id=row["meeting_id"],
        provider=row["provider"],
        model=row["model"],
        title=row["title"],
        key_points=json.loads(row["key_points"]),
        action_items=json.loads(row["action_items"]),
        decisions=json.loads(row["decisions"]),
        sections=[SummarySection(**s) for s in json.loads(row["sections"])],
        participants_mentioned=json.loads(row["participants_mentioned"]),
        full_text=row["full_text"],
        language=row["language"],
        token_count=row["token_count"],
        generation_time_seconds=row["generation_time_seconds"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
