"""Voice Activity Detection using Silero VAD (ONNX)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

MODEL_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
MODEL_FILENAME = "silero_vad.onnx"

# Silero VAD requires exactly 512 samples per chunk at 16kHz
CHUNK_SIZE = 512


class SileroVAD:
    """Silero VAD wrapper for speech/non-speech classification."""

    def __init__(self, model_dir: str, threshold: float = 0.15, sample_rate: int = 16000):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.model_path = Path(model_dir).expanduser() / MODEL_FILENAME
        self._session: ort.InferenceSession | None = None
        self._state: np.ndarray | None = None

    async def ensure_model(self) -> None:
        """Download the Silero VAD model if not present."""
        if self.model_path.exists():
            return

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading Silero VAD model...")

        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            response = await client.get(MODEL_URL)
            response.raise_for_status()
            self.model_path.write_bytes(response.content)

        logger.info("Silero VAD model saved to %s", self.model_path)

    def load(self) -> None:
        """Load the ONNX model."""
        if self._session is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(f"VAD model not found: {self.model_path}")

        self._session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        self.reset_state()
        logger.info("Silero VAD model loaded")

    def reset_state(self) -> None:
        """Reset the hidden state (call between meetings)."""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def is_speech(self, audio_chunk: np.ndarray) -> tuple[bool, float]:
        """Classify an audio chunk as speech or silence.

        Processes audio in 512-sample windows as required by Silero VAD.
        Returns the max probability across all windows.
        """
        if self._session is None:
            raise RuntimeError("VAD model not loaded. Call load() first.")

        # Flatten to 1D
        audio_chunk = audio_chunk.flatten().astype(np.float32)

        if len(audio_chunk) == 0:
            return False, 0.0

        max_prob = 0.0

        # Process in CHUNK_SIZE windows
        for i in range(0, len(audio_chunk), CHUNK_SIZE):
            window = audio_chunk[i:i + CHUNK_SIZE]
            if len(window) < CHUNK_SIZE:
                # Pad last window with zeros
                window = np.pad(window, (0, CHUNK_SIZE - len(window)))

            # Shape: [1, 512]
            input_data = window.reshape(1, -1)

            ort_inputs = {
                "input": input_data,
                "state": self._state,
                "sr": np.array(self.sample_rate, dtype=np.int64),
            }
            ort_outputs = self._session.run(None, ort_inputs)

            prob = float(ort_outputs[0].item())
            self._state = ort_outputs[1]

            if prob > max_prob:
                max_prob = prob

        return max_prob >= self.threshold, max_prob
