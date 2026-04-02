"""SQLite database engine and schema management."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'recording',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    duration_seconds INTEGER DEFAULT 0,
    audio_source TEXT DEFAULT 'mic+system',
    transcript_segment_count INTEGER DEFAULT 0,
    has_summary INTEGER DEFAULT 0,
    summary_provider TEXT,
    webhook_sent INTEGER DEFAULT 0,
    webhook_sent_at TEXT,
    company TEXT DEFAULT '',
    project TEXT DEFAULT '',
    domain TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    speaker TEXT NOT NULL,
    source TEXT NOT NULL,
    text TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    confidence REAL DEFAULT 0.0,
    language TEXT DEFAULT 'de',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_segments_meeting
    ON transcript_segments(meeting_id, idx);

CREATE TABLE IF NOT EXISTS summaries (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    title TEXT NOT NULL,
    key_points TEXT DEFAULT '[]',
    action_items TEXT DEFAULT '[]',
    decisions TEXT DEFAULT '[]',
    sections TEXT DEFAULT '[]',
    participants_mentioned TEXT DEFAULT '[]',
    full_text TEXT NOT NULL,
    language TEXT DEFAULT 'de',
    token_count INTEGER DEFAULT 0,
    generation_time_seconds REAL DEFAULT 0.0,
    created_at TEXT NOT NULL
);
"""


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()
        logger.info("Database connected: %s", self.db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not connected")
        return self._db

    async def _init_schema(self) -> None:
        await self.db.executescript(SCHEMA_SQL)
        cursor = await self.db.execute("SELECT version FROM schema_version LIMIT 1")
        row = await cursor.fetchone()
        current_version = row[0] if row else 0
        if row is None:
            await self.db.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )
        # Migrations
        if current_version < 2:
            for col in ["company", "project", "domain"]:
                try:
                    await self.db.execute(f"ALTER TABLE meetings ADD COLUMN {col} TEXT DEFAULT ''")
                except Exception:
                    pass  # Column already exists
            await self.db.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
        await self.db.commit()

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        return await self.db.execute(sql, params)

    async def executemany(self, sql: str, params_seq: list[tuple]) -> None:
        await self.db.executemany(sql, params_seq)

    async def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = await self.db.execute(sql, params)
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = await self.db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def commit(self) -> None:
        await self.db.commit()
