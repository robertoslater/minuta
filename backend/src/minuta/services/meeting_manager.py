"""Meeting lifecycle orchestration - ties audio, transcription, and storage together."""

from __future__ import annotations

import asyncio
import json
import logging
import struct

import numpy as np

from minuta.db.repository import MeetingRepository
from minuta.models.config import AppSettings
from minuta.models.meeting import (
    Meeting,
    MeetingCreate,
    MeetingStatus,
    TranscriptSegment,
    WebhookPayload,
)
from minuta.services.audio_manager import AudioManager
from minuta.services.summarizer import create_summarizer
from minuta.services.transcript_hub import TranscriptHub
from minuta.services.transcriber import Transcriber
from minuta.services.webhook import send_webhook

logger = logging.getLogger(__name__)


class MeetingManager:
    """Orchestrates recording, transcription, and delivery for a meeting."""

    def __init__(
        self,
        settings: AppSettings,
        repo: MeetingRepository,
        hub: TranscriptHub,
    ):
        self.settings = settings
        self.repo = repo
        self.hub = hub
        self.audio_manager = AudioManager(settings)
        self.transcriber = Transcriber(settings)
        self._current_meeting: Meeting | None = None
        self._initialized = False
        self._mic_sample_rate: int = 48000  # Default, updated by metadata

    async def initialize(self) -> None:
        """Initialize transcription models (call once at startup)."""
        if self._initialized:
            return
        await self.transcriber.initialize()
        self._initialized = True
        logger.info("MeetingManager initialized")

    @property
    def current_meeting(self) -> Meeting | None:
        return self._current_meeting

    @property
    def is_recording(self) -> bool:
        return self._current_meeting is not None

    async def _generate_title(self) -> str:
        """Generate a title like '2026-04-02-Meeting 1'."""
        from datetime import date
        today = date.today().isoformat()
        meetings = await self.repo.list_meetings(limit=1000)
        today_count = sum(1 for m in meetings if m.started_at.date().isoformat() == today)
        return f"{today}-Meeting {today_count + 1}"

    async def start_recording(self, data: MeetingCreate) -> Meeting:
        """Start a new meeting recording."""
        if self.is_recording:
            raise RuntimeError("A recording is already in progress")

        if not self._initialized:
            await self.initialize()

        # Auto-generate title if empty
        if not data.title:
            data.title = await self._generate_title()

        meeting = await self.repo.create_meeting(data)
        self._current_meeting = meeting

        # Setup transcriber callback
        async def on_segment(segment: TranscriptSegment):
            segment.meeting_id = meeting.id
            await self.repo.add_segment(segment)
            await self.hub.publish(meeting.id, {
                "event": "segment",
                "data": segment.model_dump(mode="json"),
            })

        self.transcriber.start_meeting(on_segment=on_segment)

        # Start audio capture
        await self.audio_manager.start(audio_callback=self._handle_audio)

        logger.info("Recording started: %s", meeting.id)
        return meeting

    async def stop_recording(self) -> Meeting | None:
        """Stop the current recording and trigger post-processing."""
        if not self.is_recording:
            return None

        meeting_id = self._current_meeting.id

        # Stop audio capture
        await self.audio_manager.stop()

        # Flush remaining audio
        remaining = await self.transcriber.flush_all()
        for seg in remaining:
            seg.meeting_id = meeting_id
            await self.repo.add_segment(seg)
            await self.hub.publish(meeting_id, {
                "event": "segment",
                "data": seg.model_dump(mode="json"),
            })

        # Update meeting status
        meeting = await self.repo.stop_meeting(meeting_id)
        self._current_meeting = None

        # Notify clients
        await self.hub.publish(meeting_id, {
            "event": "meeting_ended",
            "data": {
                "meeting_id": meeting_id,
                "total_segments": meeting.transcript_segment_count if meeting else 0,
                "total_duration": meeting.duration_seconds if meeting else 0,
            },
        })

        logger.info("Recording stopped: %s", meeting_id)

        # Auto-summarize and webhook in background
        if meeting:
            asyncio.create_task(self._post_processing(meeting))

        return meeting

    async def _handle_audio(self, raw_payload: bytes) -> None:
        """Handle audio data from the socket (decode source tag + PCM)."""
        if len(raw_payload) < 2:
            return

        # Decode source tag from payload
        source_len = raw_payload[0]
        source = raw_payload[1:1 + source_len].decode("utf-8", errors="replace")
        pcm_data = raw_payload[1 + source_len:]

        # Resample mic audio from native rate (48kHz) to 16kHz
        if source == "mic" and self._mic_sample_rate != self.settings.audio.sample_rate:
            audio = np.frombuffer(pcm_data, dtype=np.float32)
            if len(audio) > 0:
                ratio = self.settings.audio.sample_rate / self._mic_sample_rate
                new_len = int(len(audio) * ratio)
                indices = np.linspace(0, len(audio) - 1, new_len).astype(int)
                audio = audio[indices]
                pcm_data = audio.tobytes()

        # Process through transcription pipeline
        await self.transcriber.process_audio(pcm_data, source)

    async def _post_processing(self, meeting: Meeting) -> None:
        """Run summarization and webhook after recording stops."""
        try:
            # Auto-summarize
            segments = await self.repo.get_transcript(meeting.id)
            if segments:
                transcript_text = "\n".join(f"[{s.speaker}] {s.text}" for s in segments)
                summarizer = create_summarizer(
                    self.settings.summarization.default_provider, self.settings
                )
                result = await summarizer.summarize(transcript_text)

                import uuid
                from minuta.models.meeting import Summary
                summary = Summary(
                    id=uuid.uuid4().hex[:12],
                    meeting_id=meeting.id,
                    provider=self.settings.summarization.default_provider,
                    model=result.model,
                    title=result.title,
                    key_points=result.key_points,
                    action_items=result.action_items,
                    decisions=result.decisions,
                    sections=result.sections,
                    participants_mentioned=result.participants_mentioned,
                    full_text=result.full_text,
                    token_count=result.token_count,
                )
                await self.repo.save_summary(summary)

                await self.hub.publish(meeting.id, {
                    "event": "summary_ready",
                    "data": {"meeting_id": meeting.id, "summary_id": summary.id},
                })

                # Webhook is sent manually via the dashboard button

        except Exception as e:
            logger.error("Post-processing failed for meeting %s: %s", meeting.id, e)
