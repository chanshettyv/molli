"""Cloud Run entrypoint for the Molli Google Chat service.

Routes Google Chat events to the appropriate handler. Phase 0 scaffold:
the endpoints exist, return placeholder responses, and have a health check.
Real logic lands in Phase 1 and 2.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from molli_shared.config import get_settings
from molli_shared.guardrails.dlp import DLPScanner

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


@app.get("/health")  # <-- add this
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def chat_event(request: Request) -> dict[str, str]:
    """Receive a Google Chat event.

    Google Chat sends JSON with a `type` field: MESSAGE, ADDED_TO_SPACE,
    REMOVED_FROM_SPACE, CARD_CLICKED. Phase 0 just acknowledges.
    """
    event = await request.json()
    event_type = event.get("type", "UNKNOWN")
    log.info("chat_event_received", event_type=event_type)

    if event_type == "MESSAGE":
        user_text = event.get("message", {}).get("text", "")
        dlp_result = _dlp.scan(user_text)
        if dlp_result.scan_skipped:
            log.warning("dlp_scan_skipped", reason=dlp_result.skip_reason)
        if dlp_result.has_pii:
            log.info("dlp_pii_redacted", found_types=dlp_result.found_types)
        return {"text": "Hi! I'm Molli. I'm still being built — check back soon."}
    if event_type == "ADDED_TO_SPACE":
        return {
            "text": "Hello! I'm Molli. I'll help you find answers from Preiss Central once I'm ready."
        }

    return {"text": ""}
