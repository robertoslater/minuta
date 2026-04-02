"""Health check endpoint."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from minuta.models.config import AppSettings
from minuta.server.deps import get_settings

router = APIRouter()

_start_time = time.time()


@router.get("/health")
async def health(settings: AppSettings = Depends(get_settings)):
    return {
        "status": "ok",
        "version": "0.1.0",
        "uptime_seconds": int(time.time() - _start_time),
        "transcription_model": settings.transcription.model,
        "summarization_provider": settings.summarization.default_provider,
    }
