"""FastAPI application factory with lifespan management."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from minuta.db.engine import Database
from minuta.db.repository import MeetingRepository
from minuta.models.config import AppSettings, load_settings
from minuta.server.routers import health, meetings, transcripts, summaries, config, ws, license
from minuta.services.meeting_manager import MeetingManager
from minuta.services.transcript_hub import TranscriptHub

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of database and services."""
    settings: AppSettings = app.state.settings
    db = Database(settings.db_path)
    await db.connect()

    app.state.db = db
    app.state.repo = MeetingRepository(db)
    app.state.hub = TranscriptHub()
    app.state.meeting_manager = MeetingManager(settings, app.state.repo, app.state.hub)

    logger.info(
        "Minuta backend started on %s:%d",
        settings.server.host, settings.server.port,
    )
    yield

    await db.close()
    logger.info("Minuta backend stopped.")


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = load_settings()

    logging.basicConfig(
        level=getattr(logging, settings.general.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = FastAPI(
        title="Minuta",
        version="0.1.0",
        description="Meeting transcription and summarization API",
        lifespan=lifespan,
    )
    app.state.settings = settings

    # CORS for Next.js frontend (localhost:3000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3100"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(meetings.router, prefix="/api", tags=["meetings"])
    app.include_router(transcripts.router, prefix="/api", tags=["transcripts"])
    app.include_router(summaries.router, prefix="/api", tags=["summaries"])
    app.include_router(config.router, prefix="/api", tags=["config"])
    app.include_router(license.router, prefix="/api", tags=["license"])
    app.include_router(ws.router, tags=["websocket"])

    return app
