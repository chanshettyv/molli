"""Cloud Run entrypoint for the Molli Google Chat service.

Routes Google Chat events to the appropriate handler. Phase 0 scaffold:
the endpoints exist, return placeholder responses, and have a health check.
Real logic lands in Phase 1 and 2.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from molli_shared.config import get_settings
from molli_shared.guardrails.dlp import DLPScanner

from app.gemini_client import ask_gemini


def _classify(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return (event_type, message_dict) for the Chat API event envelope."""
    chat = event.get("chat", {})
    if "messagePayload" in chat:
        return "MESSAGE", chat["messagePayload"].get("message", {})
    if "addedToSpacePayload" in chat:
        return "ADDED_TO_SPACE", {}
    if "removedFromSpacePayload" in chat:
        return "REMOVED_FROM_SPACE", {}
    if "buttonClickedPayload" in chat:
        return "CARD_CLICKED", {}
    # Legacy fallback, in case config ever changes
    if "type" in event:
        return event["type"], event.get("message", {})
    return "UNKNOWN", {}


def _chat_reply(text: str) -> dict[str, Any]:
    """Wrap a plain text reply in the Chat API event-format response envelope."""
    return {
        "hostAppDataAction": {
            "chatDataAction": {"createMessageAction": {"message": {"text": text}}}
        }
    }


log = structlog.get_logger()
app = FastAPI(title="Molli chat-service", version="0.1.0")
_dlp = DLPScanner(project_id=get_settings().gcp_project_id)

# The service account Google Chat uses to sign requests to your app.
CHAT_ISSUER = "chat@system.gserviceaccount.com"

# Your GCP project number — the audience Google Chat sets on the token.
EXPECTED_AUDIENCE = get_settings().gcp_project_number

_request_adapter = google_requests.Request()


async def verify_chat_request(request: Request) -> None:
    """Reject any request that isn't a genuine, signed Google Chat event."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        log.warning("chat_auth_missing_bearer")
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth_header.removeprefix("Bearer ").strip()
    try:
        claims = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            token,
            _request_adapter,
            audience=EXPECTED_AUDIENCE,
        )
    except ValueError as exc:
        log.warning("chat_auth_invalid_token", error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if claims.get("iss") != CHAT_ISSUER:
        log.warning("chat_auth_wrong_issuer", issuer=claims.get("iss"))
        raise HTTPException(status_code=401, detail="Wrong issuer")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def chat_event(request: Request) -> dict[str, Any]:
    event = await request.json()
    event_type, message = _classify(event)
    log.info("chat_event_received", event_type=event_type)

    if event_type == "MESSAGE":
        user_text = message.get("text", "")
        sender = message.get("sender", {})
        # user_email = sender.get("email", "")
        user_name = sender.get("displayName", "")

        settings = get_settings()
        if settings.use_gemini:
            reply_text = ask_gemini(user_text)
        else:
            reply_text = (
                f"Hi {user_name or 'there'}! I'm Molli. " "I'm still being built — check back soon."
            )
        return _chat_reply(reply_text)

    if event_type == "ADDED_TO_SPACE":
        return _chat_reply(
            "Hello! I'm Molli. I'll help you find answers from Preiss Central once I'm ready."
        )

    return {}
