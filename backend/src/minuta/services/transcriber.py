"""MLX Whisper transcription service with VAD-chunked inference."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from datetime import datetime

import numpy as np

from minuta.models.config import AppSettings
from minuta.models.meeting import TranscriptSegment
from minuta.services.vad import SileroVAD

logger = logging.getLogger(__name__)


class Transcriber:
    """Real-time transcription using VAD + MLX Whisper."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.vad = SileroVAD(
            model_dir=settings.transcription.model_dir,
            threshold=settings.transcription.vad_threshold,
            sample_rate=settings.audio.sample_rate,
        )
        self._whisper_model = None
        self._sample_rate = settings.audio.sample_rate

        # Audio buffers per source
        self._buffers: dict[str, list[np.ndarray]] = {"mic": [], "system": []}
        self._speech_active: dict[str, bool] = {"mic": False, "system": False}
        self._silence_frames: dict[str, int] = {"mic": 0, "system": 0}
        self._speech_start_time: dict[str, float] = {"mic": 0.0, "system": 0.0}
        self._meeting_start: float = 0.0
        self._segment_index: int = 0

        # VAD settings
        silence_ms = settings.transcription.silence_duration_ms
        self._silence_threshold_frames = int(silence_ms / 100)  # 100ms per frame
        self._max_segment_samples = settings.transcription.max_segment_seconds * self._sample_rate

        # Callback for completed segments
        self._on_segment = None

    async def initialize(self) -> None:
        """Download VAD model and load Whisper."""
        await self.vad.ensure_model()
        self.vad.load()
        await self._load_whisper()

    async def _load_whisper(self) -> None:
        """Load MLX Whisper model (runs in thread to avoid blocking)."""
        def _load():
            import mlx_whisper
            model_name = self.settings.transcription.model
            logger.info("Loading MLX Whisper model: %s", model_name)
            # Trigger model download/cache by doing a tiny transcription
            # The model will be cached for subsequent calls
            return model_name

        self._whisper_model = await asyncio.to_thread(_load)
        logger.info("MLX Whisper ready: %s", self._whisper_model)

    def start_meeting(self, on_segment=None) -> None:
        """Reset state for a new meeting."""
        self._meeting_start = time.time()
        self._segment_index = 0
        self._on_segment = on_segment
        self.vad.reset_state()
        for source in self._buffers:
            self._buffers[source] = []
            self._speech_active[source] = False
            self._silence_frames[source] = 0

    async def process_audio(self, pcm_data: bytes, source: str) -> TranscriptSegment | None:
        """Process an audio chunk through VAD and optionally transcribe.

        Args:
            pcm_data: Raw PCM float32 bytes
            source: "mic" or "system"

        Returns:
            TranscriptSegment if a segment was completed, None otherwise.
        """
        audio = np.frombuffer(pcm_data, dtype=np.float32)
        if len(audio) == 0:
            return None

        # Simple RMS-based voice activity detection
        # (Silero VAD has issues with resampled audio, use energy-based detection)
        rms = float(np.sqrt(np.mean(audio ** 2)))
        is_speech = rms > 0.003  # Threshold for speech detection

        # Debug logging
        if not hasattr(self, '_debug_count'):
            self._debug_count = 0
        self._debug_count += 1
        if self._debug_count % 30 == 1 or is_speech:
            logger.info("Audio: src=%s rms=%.6f speech=%s", source, rms, is_speech)

        if is_speech:
            if not self._speech_active[source]:
                # Speech started
                self._speech_active[source] = True
                self._speech_start_time[source] = time.time() - self._meeting_start
                self._silence_frames[source] = 0
            self._buffers[source].append(audio)
            self._silence_frames[source] = 0

            # Force split if segment is too long
            total_samples = sum(len(b) for b in self._buffers[source])
            if total_samples >= self._max_segment_samples:
                return await self._flush_buffer(source)

        elif self._speech_active[source]:
            # Silence during active speech
            self._silence_frames[source] += 1
            self._buffers[source].append(audio)  # Include trailing silence

            if self._silence_frames[source] >= self._silence_threshold_frames:
                # End of speech segment
                return await self._flush_buffer(source)

        return None

    async def _flush_buffer(self, source: str) -> TranscriptSegment | None:
        """Transcribe accumulated audio buffer and create a segment."""
        if not self._buffers[source]:
            return None

        audio = np.concatenate(self._buffers[source])
        start_time = self._speech_start_time[source]
        end_time = time.time() - self._meeting_start

        # Clear buffer
        self._buffers[source] = []
        self._speech_active[source] = False
        self._silence_frames[source] = 0

        # Transcribe in thread
        segment = await asyncio.to_thread(
            self._transcribe, audio, source, start_time, end_time
        )

        if segment and self._on_segment:
            await self._on_segment(segment)

        return segment

    def _transcribe(
        self, audio: np.ndarray, source: str, start_time: float, end_time: float
    ) -> TranscriptSegment | None:
        """Run MLX Whisper inference (blocking, runs in thread)."""
        if self._whisper_model is None:
            return None

        import mlx_whisper

        try:
            result = mlx_whisper.transcribe(
                audio,
                path_or_hf_repo=self._whisper_model,
                language=self.settings.transcription.language,
                # MLX Whisper only supports greedy decoding (beam_size=1)

            )

            text = result.get("text", "").strip()
            if not text:
                return None

            speaker = (
                self.settings.speaker.user_name
                if source == "mic"
                else self.settings.speaker.participant_name
            )

            self._segment_index += 1
            return TranscriptSegment(
                id=uuid.uuid4().hex[:8],
                meeting_id="",  # Set by caller
                index=self._segment_index,
                speaker=speaker,
                source=source,
                text=text,
                start_time=round(start_time, 2),
                end_time=round(end_time, 2),
                confidence=0.0,  # MLX Whisper doesn't expose per-segment confidence
                language=self.settings.transcription.language,
                created_at=datetime.now(),
            )
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return None

    async def flush_all(self) -> list[TranscriptSegment]:
        """Flush any remaining audio in buffers (call when meeting ends)."""
        segments = []
        for source in ["mic", "system"]:
            if self._buffers[source]:
                seg = await self._flush_buffer(source)
                if seg:
                    segments.append(seg)
        return segments
