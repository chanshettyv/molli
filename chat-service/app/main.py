"""Cloud Run entrypoint for the Molli Google Chat service.

Routes Google Chat events to the appropriate handler. Phase 0 scaffold:
the endpoints exist, return placeholder responses, and have a health check.
Real logic lands in Phase 1 and 2.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from molli_shared.clients.freshservice import FreshserviceClient
from molli_shared.clients.ticketing import (
    TicketingAuthError,
    TicketingError,
    TicketingRateLimitError,
    TicketingValidationError,
)
from molli_shared.config import get_settings
from molli_shared.guardrails.chain import run_chain, scan_gemini_output

from app.cards import dialog
from app.cards.ticket_mapper import build_ticket_payload
from app.gemini_client import ask_gemini


def _classify(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return (event_type, message_dict) for the Chat API event envelope."""
    chat = event.get("chat", {})

    if "appCommandPayload" in chat:
        return "APP_COMMAND", chat["appCommandPayload"].get("message", {})
    if "messagePayload" in chat:
        return "MESSAGE", chat["messagePayload"].get("message", {})
    if "addedToSpacePayload" in chat:
        return "ADDED_TO_SPACE", {}
    if "removedFromSpacePayload" in chat:
        return "REMOVED_FROM_SPACE", {}
    if "buttonClickedPayload" in chat:
        return "CARD_CLICKED", chat["buttonClickedPayload"]
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


def _extract_form_inputs(event: dict[str, Any]) -> dict[str, Any]:
    """Pull dialog form values out of a SUBMIT_DIALOG event.

    Form inputs live at commonEventObject.formInputs, keyed by widget name,
    each as {"stringInputs": {"value": [...]}}. Single-value widgets return a
    one-element list; the multi-select returns all selected values. Empty
    fields come back as [''] (a list with one empty string), not [].
    """
    form_inputs = event.get("commonEventObject", {}).get("formInputs", {})

    def single(name: str) -> str:
        """First value for a single-value widget; '' if absent."""
        return form_inputs.get(name, {}).get("stringInputs", {}).get("value", [""])[0]

    def multi(name: str) -> list[str]:
        """All values for a multi-select; drops empty strings."""
        values = form_inputs.get(name, {}).get("stringInputs", {}).get("value", [])
        return [v for v in values if v]

    return {
        "email": single("email"),
        "subject": single("subject"),
        "group": single("group"),
        "affectedLocation": multi("affectedLocation"),
        "systemItem": single("systemItem"),
        "status": single("status"),
        "priority": single("priority"),
        "description": single("description"),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Construct the Freshservice client once per container at startup and
    close it (and its httpx connection pool) at shutdown. Cloud Run may run
    several container instances under load; each gets its own client, which
    is correct — each manages its own connection pool.
    """
    settings = get_settings()
    app.state.ticketing = FreshserviceClient(
        base_url=settings.freshservice_base_url,
        api_key=settings.freshservice_api_key,
    )
    log.info("ticketing_client_initialized", base_url=settings.freshservice_base_url)
    yield
    await app.state.ticketing.aclose()
    log.info("ticketing_client_closed")


log = structlog.get_logger()
app = FastAPI(title="Molli chat-service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def chat_event(request: Request) -> dict[str, Any]:
    event = await request.json()
    log.info("received_chat_event", payload=event)
    event_type, message = _classify(event)
    log.info("chat_event_received", event_type=event_type)

    if event_type == "MESSAGE":
        # Slash command arrives with the command metadata on the message.
        user_text = message.get("text", "")
        if user_text == "dialogtest":
            resp = dialog.trigger_card()
            log.info("outgoing_trigger_payload", payload=resp)
            return resp
        sender = message.get("sender", {})
        user_email = sender.get("email", "")
        user_name = sender.get("displayName", "")
        space_id = event.get("space", {}).get("name", "unknown")
        session_id = message.get("name", "unknown")

        chain_result = await run_chain(user_text, user_email, space_id, session_id)
        log.info(
            "guardrail_chain_result",
            action=chain_result.verdict.action,
            category=chain_result.verdict.category,
        )

        if not chain_result.should_call_gemini:
            return _chat_reply(chain_result.response_to_user or "")

        settings = get_settings()
        if settings.use_gemini:
            reply_text = ask_gemini(chain_result.message_to_gemini or user_text)
            reply_text, _ = await scan_gemini_output(reply_text, user_email, space_id, session_id)
        else:
            reply_text = (
                f"Hi {user_name or 'there'}! I'm Molli. I'm still being built — check back soon."
            )

        if chain_result.append_to_response:
            reply_text = f"{reply_text}\n\n{chain_result.append_to_response}"

        return _chat_reply(reply_text)

    if event_type == "ADDED_TO_SPACE":
        return _chat_reply(
            "Hello! I'm Molli. I'll help you find answers from Preiss Central once I'm ready."
        )

    if event_type == "CARD_CLICKED":
        # `message` here is the buttonClickedPayload (see _classify).
        common = event.get("commonEventObject", {})
        action = common.get("parameters", {}).get("actionName", "")
        log.info("card_click_received", action=action)
        if action == "openInitialDialog":
            resp = dialog.open_dialog()
            log.info("outgoing_dialog_payload", payload=resp)
            return resp

        if action == "submitNameDialog":
            inputs = _extract_form_inputs(event)
            log.info("dialog_submit_received", inputs=inputs)

            # Build + validate the payload. Strict schema raises on bad data.
            try:
                payload = build_ticket_payload(inputs)
            except Exception as exc:
                log.warning("ticket_payload_build_failed", error=str(exc))
                return dialog.submit_notification(
                    "Something was wrong with the ticket details. Please check your entries and try again."
                )

            settings = get_settings()
            if settings.freshservice_dry_run:
                # DRY RUN: log exactly what would be sent, create nothing.
                log.info(
                    "ticket_dry_run",
                    payload=payload.model_dump(exclude_none=True),
                )
                return dialog.submit_notification(
                    "Dry run: ticket payload built and validated (not sent)."
                )

            # LIVE: create the ticket.
            try:
                created = await request.app.state.ticketing.create_ticket(payload)
                log.info("ticket_created", ticket_id=created.id)
                return dialog.submit_notification(f"#{created.id}.")
            except TicketingValidationError as exc:
                log.warning("ticket_validation_error", error=str(exc))
                return dialog.submit_notification(
                    "The ticketing system rejected the ticket. Please check your entries."
                )
            except (TicketingAuthError, TicketingRateLimitError, TicketingError) as exc:
                log.error("ticket_create_failed", error=str(exc))
                return dialog.submit_notification(
                    "Couldn't reach the ticketing system right now. Please try again shortly."
                )

        log.info("unhandled_card_click", action=action)
        return {}

    return {}
