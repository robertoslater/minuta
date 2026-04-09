"""WebSocket endpoint for live transcript streaming."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from minuta.server.deps import get_hub
from minuta.services.transcript_hub import TranscriptHub

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/transcript/{meeting_id}")
async def transcript_ws(
    websocket: WebSocket,
    meeting_id: str,
):
    await websocket.accept()
    hub: TranscriptHub = websocket.app.state.hub
    queue = await hub.subscribe(meeting_id)

    try:
        # Send initial status
        await websocket.send_json({
            "event": "connected",
            "data": {"meeting_id": meeting_id},
        })

        # Listen for events from the hub and forward to client
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_json({"event": "ping"})
                # Check if client is still connected
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass  # No response needed, connection still alive
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected from meeting %s", meeting_id)
    except Exception as e:
        logger.error("WebSocket error for meeting %s: %s", meeting_id, e)
    finally:
        hub.unsubscribe(meeting_id, queue)
