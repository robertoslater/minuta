"""WebSocket broadcast hub for live transcript streaming."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class TranscriptHub:
    """Pub/sub hub for broadcasting transcript events to WebSocket clients."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    async def subscribe(self, meeting_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers.setdefault(meeting_id, []).append(q)
        logger.debug("Client subscribed to meeting %s (%d total)",
                      meeting_id, len(self._subscribers[meeting_id]))
        return q

    def unsubscribe(self, meeting_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(meeting_id, [])
        if queue in subs:
            subs.remove(queue)
        if not subs:
            self._subscribers.pop(meeting_id, None)

    async def publish(self, meeting_id: str, event: dict) -> None:
        for q in self._subscribers.get(meeting_id, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest if consumer is slow
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

    def subscriber_count(self, meeting_id: str) -> int:
        return len(self._subscribers.get(meeting_id, []))
