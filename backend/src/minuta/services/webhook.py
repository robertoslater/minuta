"""Webhook sender for N8N integration (Sally.io compatible format)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

import httpx

from minuta.models.config import WebhookConfig
from minuta.models.meeting import WebhookPayload

logger = logging.getLogger(__name__)


def _to_sally_format(payload: WebhookPayload) -> dict:
    """Convert Minuta payload to Sally.io compatible format for N8N workflow."""
    meeting = payload.meeting
    summary = payload.summary

    # Build Sally-compatible payload
    sally = {
        "recordingSummaryId": meeting.id,
        "directoryId": f"minuta-{meeting.id}",
        "appointmentSubject": summary.title if summary else meeting.title,
        "appointmentDate": meeting.started_at.isoformat(),
        "meetingUrl": None,
        "meetingPlatform": "Minuta",
        "transcriptionTool": "Minuta",
        "languageCode": "de",
        "company": meeting.company,
        "project": meeting.project,
        "domain": meeting.domain,
        "attendees": [],
        "summary": summary.full_text if summary else "",
        "topics": [],
        "decisions": [],
        "tasks": [],
        "objections": [],
        "customInsights": [],
        "transcriptParts": [],
    }

    if summary:
        # Map sections to topics
        for sec in summary.sections:
            sally["topics"].append({
                "summary": sec.heading,
                "description": sec.content,
                "startTimeStamp": None,
                "endTimeStamp": None,
            })

        # Map decisions
        for d in summary.decisions:
            sally["decisions"].append({
                "summary": d,
                "description": d,
            })

        # Map action items to tasks
        for a in summary.action_items:
            sally["tasks"].append({
                "subject": a,
                "description": a,
                "responsiblePersonName": None,
                "responsiblePersonEmail": None,
                "dueDate": None,
            })

        # Map participants
        for p in summary.participants_mentioned:
            sally["attendees"].append({
                "name": p,
                "email": None,
            })

    return sally


async def send_webhook(config: WebhookConfig, payload: WebhookPayload) -> bool:
    """Send a webhook in Sally.io format to the configured N8N URL.

    Returns True if the webhook was delivered successfully.
    """
    if not config.enabled or not config.url:
        logger.debug("Webhook disabled or no URL configured")
        return False

    sally_payload = _to_sally_format(payload)
    body = json.dumps(sally_payload, ensure_ascii=False, default=str)
    signature = _sign(body, config.secret) if config.secret else ""

    headers = {
        "Content-Type": "application/json",
        "X-Minuta-Event": payload.event,
        "X-Minuta-Signature": signature,
    }

    # Basic Auth support for N8N
    auth = None
    if config.basic_auth_user and config.basic_auth_password:
        auth = httpx.BasicAuth(config.basic_auth_user, config.basic_auth_password)

    for attempt in range(1, config.retry_count + 1):
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                response = await client.post(config.url, content=body, headers=headers, auth=auth)
                response.raise_for_status()
                logger.info("Webhook delivered (attempt %d): %s", attempt, config.url)
                return True
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Webhook HTTP error (attempt %d/%d): %s %s",
                attempt, config.retry_count, e.response.status_code, e.response.text[:200],
            )
        except httpx.RequestError as e:
            logger.warning(
                "Webhook request error (attempt %d/%d): %s",
                attempt, config.retry_count, e,
            )

        if attempt < config.retry_count:
            delay = 2 ** attempt
            logger.info("Retrying webhook in %ds...", delay)
            import asyncio
            await asyncio.sleep(delay)

    logger.error("Webhook delivery failed after %d attempts: %s", config.retry_count, config.url)
    return False


def _sign(body: str, secret: str) -> str:
    """Create HMAC-SHA256 signature."""
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
