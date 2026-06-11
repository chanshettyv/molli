"""Cloud Run entrypoint for the Molli Google Chat service.

Routes Google Chat events to the appropriate handler. Phase 0 scaffold:
the endpoints exist, return placeholder responses, and have a health check.
Real logic lands in Phase 1 and 2.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from molli_shared.config import get_settings
from molli_shared.guardrails.chain import run_chain, scan_gemini_output

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

    if event_type == "CARD_CLICKED":
        payload = event.get("chat", {}).get("buttonClickedPayload", {})
        log.info("button_click", body=payload)  # TEMP: confirm the invoked-function key
        invoked = payload.get("invokedFunction") or payload.get("function")
        if invoked == "open_ticket_dialog":
            return _chat_dialog(summary="test ticket", description="testing the dialog render")
        if invoked == "submit_ticket":
            return _chat_reply("Got the submission (handler not wired yet).")
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
