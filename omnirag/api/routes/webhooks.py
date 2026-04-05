"""Webhook registration + delivery dispatcher."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/v1")
logger = structlog.get_logger(__name__)

MAX_RETRIES = 5
BACKOFF_BASE = 1  # seconds


class WebhookRegistration(BaseModel):
    url: str
    events: list[str] = ["intake.completed", "intake.failed"]
    secret: str = ""


# In-memory store
_webhooks: dict[str, dict] = {}
_deliveries: list[dict] = []
_dlq: list[dict] = []


@router.post("/webhooks", tags=["webhooks"])
async def register_webhook(body: WebhookRegistration):
    """Register a webhook endpoint (admin only)."""
    wh_id = str(uuid.uuid4())[:8]
    _webhooks[wh_id] = {
        "id": wh_id,
        "url": body.url,
        "events": body.events,
        "secret": body.secret,
        "created_at": time.time(),
    }
    return {"id": wh_id, "url": body.url, "events": body.events}


@router.get("/webhooks", tags=["webhooks"])
async def list_webhooks():
    """List registered webhooks."""
    return list(_webhooks.values())


@router.delete("/webhooks/{wh_id}", tags=["webhooks"])
async def delete_webhook(wh_id: str):
    """Delete a webhook."""
    if wh_id not in _webhooks:
        raise HTTPException(404, "Webhook not found")
    del _webhooks[wh_id]
    return {"deleted": True}


def sign_payload(payload: str, secret: str) -> str:
    """HMAC-SHA256 signature."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def deliver_event(event_type: str, data: dict) -> None:
    """Deliver event to all matching webhooks with retry + DLQ."""
    import httpx

    for wh in _webhooks.values():
        if event_type not in wh["events"]:
            continue

        payload = json.dumps({"event": event_type, "timestamp": time.time(), **data})
        headers = {"Content-Type": "application/json"}
        if wh["secret"]:
            headers["X-Webhook-Signature"] = sign_payload(payload, wh["secret"])

        delivered = False
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(wh["url"], content=payload, headers=headers)
                    if resp.status_code < 400:
                        _deliveries.append({
                            "webhook_id": wh["id"],
                            "event": event_type,
                            "status": "success",
                            "attempt": attempt + 1,
                            "timestamp": time.time(),
                        })
                        delivered = True
                        break
            except Exception as e:
                delay = BACKOFF_BASE * (2 ** attempt)
                logger.warning("webhook.retry", wh_id=wh["id"], attempt=attempt + 1, delay=delay, error=str(e))
                await asyncio.sleep(delay)

        if not delivered:
            _dlq.append({
                "webhook_id": wh["id"],
                "event": event_type,
                "data": data,
                "error": "max retries exceeded",
                "timestamp": time.time(),
            })
            logger.error("webhook.dlq", wh_id=wh["id"], event=event_type)


@router.get("/webhooks/deliveries", tags=["webhooks"])
async def list_deliveries():
    return {"deliveries": _deliveries[-50:], "dlq": _dlq[-20:]}
