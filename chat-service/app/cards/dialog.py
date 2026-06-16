"""Card and dialog builders for the dialogtest flow.

Bare-bones dialog spike: trigger card -> open dialog -> submit -> notify.
Plain-message responses use the chatDataAction envelope (see _chat_reply in
main.py); dialog open/submit responses use the renderActions envelope.
"""

from __future__ import annotations

from typing import Any

from app.cards import form_options

SERVICE_URL = "https://molli-chat-service-719635778769.us-central1.run.app/"


def trigger_card() -> dict[str, Any]:
    """Reply to 'dialogtest': a message card with a button that opens the dialog."""
    return {
        "hostAppDataAction": {
            "chatDataAction": {
                "createMessageAction": {
                    "message": {
                        "cardsV2": [
                            {
                                "cardId": "dialogtest-trigger",
                                "card": {
                                    "sections": [
                                        {
                                            "widgets": [
                                                {
                                                    "buttonList": {
                                                        "buttons": [
                                                            {
                                                                "text": "Create a Ticket",
                                                                "onClick": {
                                                                    "action": {
                                                                        "function": SERVICE_URL,
                                                                        "interaction": "OPEN_DIALOG",
                                                                        "parameters": [
                                                                            {
                                                                                "key": "actionName",
                                                                                "value": "openInitialDialog",
                                                                            }
                                                                        ],
                                                                    }
                                                                },
                                                            }
                                                        ]
                                                    }
                                                }
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


def open_dialog() -> dict[str, Any]:
    """Response to the openInitialDialog click: push the IT issue intake dialog."""

    location_items = [{"text": loc, "value": loc} for loc in form_options.LOCATIONS]
    system_items = [{"text": item, "value": item} for item in form_options.SYSTEM_ITEMS]
    group_items = [{"text": g["name"], "value": str(g["id"])} for g in form_options.GROUPS]
    status_items = [{"text": s["name"], "value": str(s["value"])} for s in form_options.STATUSES]
    priority_items = [
        {"text": p["name"], "value": str(p["value"])} for p in form_options.PRIORITIES
    ]

    return {
        "action": {
            "navigations": [
                {
                    "pushCard": {
                        "sections": [
                            {
                                "header": "Submit an IT issue",
                                "widgets": [
                                    {
                                        "textInput": {
                                            "label": "Email *",
                                            "type": "SINGLE_LINE",
                                            "name": "email",
                                            "value": "prefill-test@preiss.com",
                                        }
                                    },
                                    {
                                        "textInput": {
                                            "label": "Subject *",
                                            "type": "SINGLE_LINE",
                                            "name": "subject",
                                        }
                                    },
                                    {
                                        "selectionInput": {
                                            "name": "group",
                                            "label": "Group *",
                                            "type": "DROPDOWN",
                                            "items": group_items,
                                        }
                                    },
                                    {
                                        "selectionInput": {
                                            "name": "affectedLocation",
                                            "label": "Most Affected Location *",
                                            "type": "MULTI_SELECT",
                                            "items": location_items,
                                        }
                                    },
                                    {
                                        "selectionInput": {
                                            "name": "systemItem",
                                            "label": "System *",
                                            "type": "DROPDOWN",
                                            "items": system_items,
                                        }
                                    },
                                    {
                                        "textInput": {
                                            "label": "Computer Name",
                                            "type": "SINGLE_LINE",
                                            "name": "computerName",
                                        }
                                    },
                                    # NOTE: `columns` is first-time-use in this dialog and
                                    # unconfirmed in the Add-On envelope. If the dialog throws
                                    # a parse error on open, this is suspect #1 — fall back to
                                    # two stacked RADIO_BUTTON selectionInputs.
                                    {
                                        "columns": {
                                            "columnItems": [
                                                {
                                                    "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                                                    "widgets": [
                                                        {
                                                            "selectionInput": {
                                                                "name": "status",
                                                                "label": "Status *",
                                                                "type": "RADIO_BUTTON",
                                                                "items": status_items,
                                                            }
                                                        }
                                                    ],
                                                },
                                                {
                                                    "horizontalSizeStyle": "FILL_AVAILABLE_SPACE",
                                                    "widgets": [
                                                        {
                                                            "selectionInput": {
                                                                "name": "priority",
                                                                "label": "Priority *",
                                                                "type": "RADIO_BUTTON",
                                                                "items": priority_items,
                                                            }
                                                        }
                                                    ],
                                                },
                                            ]
                                        }
                                    },
                                    {"divider": {}},
                                    {
                                        "textInput": {
                                            "label": "Description *",
                                            "type": "MULTIPLE_LINE",
                                            "name": "description",
                                        }
                                    },
                                    {
                                        "buttonList": {
                                            "buttons": [
                                                {
                                                    "text": "Submit",
                                                    "onClick": {
                                                        "action": {
                                                            "function": SERVICE_URL,
                                                            "parameters": [
                                                                {
                                                                    "key": "actionName",
                                                                    "value": "submitNameDialog",
                                                                }
                                                            ],
                                                            # Required fields — host blocks
                                                            # submit until these have values.
                                                            "requiredWidgets": [
                                                                "email",
                                                                "subject",
                                                                "group",
                                                                "affectedLocation",
                                                                "systemItem",
                                                                "status",
                                                                "priority",
                                                                "description",
                                                            ],
                                                        }
                                                    },
                                                }
                                            ]
                                        }
                                    },
                                ],
                            }
                        ]
                    }
                }
            ]
        }
    }


def submit_notification(name: str) -> dict[str, Any]:
    """Response to submitNameDialog: confirm via notification.

    The notification is the confirmed-correct Add-On submit response
    (per SubmitFormResponse docs). The explicit dialog-close instruction
    (standalone-Chat docs call it EndNavigation -> CLOSE_DIALOG) may differ
    in the Add-On envelope. TODO: verify against a real submit event log
    whether the notification alone dismisses the modal; if not, add the
    Add-On close instruction here.
    """
    return {
        "action": {
            "navigations": [{"endNavigation": {"action": "CLOSE_DIALOG"}}],
            "notification": {"text": f"Got it — name received: {name}"},
        }
    }
