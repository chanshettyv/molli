"""Cloud Run entrypoint for the Molli Google Chat service.

Routes Google Chat events to the appropriate handler. Phase 0 scaffold:
the endpoints exist, return placeholder responses, and have a health check.
Real logic lands in Phase 1 and 2.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request

log = structlog.get_logger()

app = FastAPI(title="Molli chat-service", version="0.1.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
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
        return {"text": "Hi! I'm Molli. I'm still being built — check back soon."}
    if event_type == "ADDED_TO_SPACE":
        return {"text": "Hello! I'm Molli. I'll help you find answers from Preiss Central once I'm ready."}

    return {"text": ""}
