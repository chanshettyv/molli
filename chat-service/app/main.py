"""Cloud Run entrypoint for the Molli Google Chat service.

Routes Google Chat events to the appropriate handler. Phase 0 scaffold:
the endpoints exist, return placeholder responses, and have a health check.
Real logic lands in Phase 1 and 2.
"""

from __future__ import annotations

import uuid  # NEW (ticket submit): conversation-id for the mock custom field
from typing import Any

import structlog
from fastapi import FastAPI, Request
from molli_shared.clients.freshservice import MockTicketingProvider, TicketingProvider
from molli_shared.config import get_settings
from molli_shared.guardrails.chain import run_chain, scan_gemini_output

# ---------------------------------------------------------------------------
# NEW (ticket submit): schema + ticketing provider
# ---------------------------------------------------------------------------
# These back the submit_ticket handler. The provider is the seam for the
# Autotask migration — swap MockTicketingProvider for a real FreshserviceProvider
# (same TicketingProvider interface) and nothing else in this file changes.
from molli_shared.schemas.ticket import (
    DraftIncompleteError,
    MolliCustomFields,
    TicketCreatePayload,
    TicketPriority,
)

from app.gemini_client import ask_gemini

PROVIDER: TicketingProvider = MockTicketingProvider()

# Department dropdown value -> Freshservice group_id.
# DUMMY mapping for the mock. Replace with Adam's real group IDs when going live.
_DEPT_TO_GROUP = {"IT": 1, "Ops": 2, "HR": 3}
# ---------------------------------------------------------------------------


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
        return "CARD_CLICKED", {}
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


def _chat_dialog(
    *,
    summary: str = "",
    description: str = "",
    department: str = "IT",
    priority: str = "2",
) -> dict[str, Any]:
    """Open a ticket-edit dialog in the new Chat event (hostAppDataAction) format.

    Pass the values Gemini extracted from the `create_ticket` call to pre-fill
    each widget. Every field stays editable; submitting fires the
    `submit_ticket` action back to the POST / endpoint.
    """

    def _dropdown_items(
        options: list[tuple[str, str]], selected_value: str
    ) -> list[dict[str, object]]:
        return [
            {"text": text, "value": value, "selected": value == selected_value}
            for text, value in options
        ]

    dialog_body = {
        "sections": [
            {
                "header": "Review and edit your ticket",
                "widgets": [
                    {
                        "textInput": {
                            "name": "summary",
                            "label": "Summary",
                            "value": summary,
                        }
                    },
                    {
                        "textInput": {
                            "name": "description",
                            "label": "Details",
                            "type": "MULTIPLE_LINE",
                            "value": description,
                        }
                    },
                    {
                        "selectionInput": {
                            "name": "department",
                            "label": "Department",
                            "type": "DROPDOWN",
                            "items": _dropdown_items(
                                [
                                    ("IT", "IT"),
                                    ("Operations", "Ops"),
                                    ("Human Resources", "HR"),
                                ],
                                department,
                            ),
                        }
                    },
                    {
                        "selectionInput": {
                            "name": "priority",
                            "label": "Priority",
                            "type": "DROPDOWN",
                            "items": _dropdown_items(
                                [
                                    ("Low", "1"),
                                    ("Medium", "2"),
                                    ("High", "3"),
                                ],
                                priority,
                            ),
                        }
                    },
                    {
                        "buttonList": {
                            "buttons": [
                                {
                                    "text": "Create ticket",
                                    "onClick": {"action": {"function": "submit_ticket"}},
                                }
                            ]
                        }
                    },
                ],
            }
        ]
    }

    return {
        "hostAppDataAction": {"chatDataAction": {"dialogAction": {"dialog": {"body": dialog_body}}}}
    }


def _chat_dialog_trigger_button(text: str = "Tap to open the ticket dialog") -> dict[str, Any]:
    """Reply with a card button that opens the dialog when clicked (smoke test)."""
    return {
        "hostAppDataAction": {
            "chatDataAction": {
                "createMessageAction": {
                    "message": {
                        "cardsV2": [
                            {
                                "cardId": "dialog-trigger",
                                "card": {
                                    "sections": [
                                        {
                                            "widgets": [
                                                {"textParagraph": {"text": text}},
                                                {
                                                    "buttonList": {
                                                        "buttons": [
                                                            {
                                                                "text": "Open ticket form",
                                                                "onClick": {
                                                                    "action": {
                                                                        "function": "open_ticket_dialog",
                                                                        "interaction": "OPEN_DIALOG",
                                                                    }
                                                                },
                                                            }
                                                        ]
                                                    }
                                                },
                                            ]
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        }
    }


# ---------------------------------------------------------------------------
# NEW (ticket submit): read form inputs + build the strict payload
# ---------------------------------------------------------------------------
def _read_form(payload: dict[str, Any], name: str) -> str | None:
    """Pull a single string value from the submit payload's form inputs.

    !!! VERIFY THIS PATH AGAINST A REAL SUBMIT-CLICK LOG !!!
    The new Chat event format may nest formInputs differently from the old
    `common.formInputs` shape the public docs show. The submit branch below
    logs the raw payload — click Create once in real Chat, read the log line,
    and correct the lookup here if needed. Both common locations are tried.
    All values arrive as STRING arrays, so we take value[0].
    """
    form_inputs = (
        payload.get("formInputs")
        or payload.get("commonEventObject", {}).get("formInputs", {})
        or payload.get("common", {}).get("formInputs", {})
    )
    widget = form_inputs.get(name)
    if not widget:
        return None
    values = widget.get("stringInputs", {}).get("value", [])
    return values[0] if values else None


def _build_ticket_payload(payload: dict[str, Any], user_email: str) -> TicketCreatePayload:
    """Map the dialog's form fields onto a strict TicketCreatePayload.

    Field name reconciliation (dialog -> schema):
        summary     -> subject
        department  -> group_id   (via _DEPT_TO_GROUP)
        priority    -> priority   (string "3" parsed to int)
    The schema-required custom_fields the dialog doesn't collect are backfilled
    with DUMMY values for the mock. When going live, either add widgets for them
    or resolve via the Workspace Admin SDK (computer name, location).
    """
    summary = _read_form(payload, "summary")
    description = _read_form(payload, "description")
    department = _read_form(payload, "department") or "IT"
    priority_raw = _read_form(payload, "priority")

    priority: TicketPriority = 2  # Medium default
    if priority_raw and int(priority_raw) in (1, 2, 3, 4):
        priority = int(priority_raw)  # type: ignore[assignment]

    custom = MolliCustomFields(
        original_system="Unknown (mock)",
        original_more_detail="Created via Molli ticket dialog.",
        msf_affected_location=["UNKNOWN"],
        molli_conversation_id=str(uuid.uuid4()),
        molli_confidence_score=1.0,
        molli_escalation_reason="user-requested-human",
    )

    return TicketCreatePayload(
        email=user_email or "unknown@preiss.com",  # type: ignore[arg-type]
        subject=summary or "(no subject)",
        description=description or "(no description)",
        group_id=_DEPT_TO_GROUP.get(department, 1),
        custom_fields=custom,
        priority=priority,
    )


# ---------------------------------------------------------------------------


log = structlog.get_logger()
app = FastAPI(title="Molli chat-service", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def chat_event(request: Request) -> dict[str, Any]:
    event = await request.json()
    log.info("received_chat_event", payload=event)
    event_type, message = _classify(event)
    log.info("chat_event_received", event_type=event_type)
    if event_type == "APP_COMMAND":
        meta = event.get("chat", {}).get("appCommandPayload", {}).get("appCommandMetadata", {})
        command_id = str(meta.get("appCommandId", ""))
        log.info("app_command", command_id=command_id)
        if command_id == "1":  # /newticket
            return _chat_dialog(summary="test ticket", description="testing the dialog render")
        return _chat_reply("Command not recognized.")

    if event_type == "CARD_CLICKED":
        payload = event.get("chat", {}).get("buttonClickedPayload", {})
        log.info("button_click", body=payload)  # TEMP: confirm the invoked-function key
        invoked = payload.get("invokedFunction") or payload.get("function")
        if invoked == "open_ticket_dialog":
            return _chat_dialog(summary="test ticket", description="testing the dialog render")

        # vvv NEW (ticket submit): wire the submit handler vvv
        if invoked == "submit_ticket":
            # Requester email: on a button-click event the sender may sit
            # elsewhere in the envelope than on a message event. VERIFY against
            # the logged payload above; fall through to empty if absent.
            sender = (
                event.get("chat", {}).get("messagePayload", {}).get("message", {}).get("sender", {})
            )
            user_email = sender.get("email", "")
            try:
                ticket_payload = _build_ticket_payload(payload, user_email)
            except (ValueError, DraftIncompleteError) as exc:
                log.warning("ticket_build_failed", error=str(exc))
                return _chat_reply(f"Couldn't create the ticket: {exc}")
            ref = PROVIDER.create(ticket_payload)
            log.info("ticket_created", ref=ref)
            return _chat_reply(f"Done — ticket {ref} created. We'll follow up shortly.")
        # ^^^ NEW (ticket submit) ^^^

        return {}

    if event_type == "MESSAGE":
        # Slash command arrives with the command metadata on the message.
        slash = message.get("slashCommand") or message.get("appCommand") or {}
        command_id = str(slash.get("commandId", ""))
        if command_id == "1":  # the Command Id you set for /newticket
            return _chat_dialog(summary="test ticket", description="testing the dialog render")
        user_text = message.get("text", "")
        if user_text.strip().lower() == "/dialogtest":
            return _chat_dialog_trigger_button()
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

    return {}
