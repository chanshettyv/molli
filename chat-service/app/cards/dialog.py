"""Card and dialog builders for the dialogtest flow.

Bare-bones dialog spike: trigger card -> open dialog -> submit -> notify.
Plain-message responses use the chatDataAction envelope (see _chat_reply in
main.py); dialog open/submit responses use the renderActions envelope.
"""

from __future__ import annotations

from typing import Any

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
                                                                "text": "Open dialog",
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
    """Response to the openInitialDialog click: push the name-input dialog."""
    return {
        "renderActions": {
            "action": {
                "navigations": [
                    {
                        "pushCard": {
                            "sections": [
                                {
                                    "header": "Enter your name",
                                    "widgets": [
                                        {
                                            "textInput": {
                                                "label": "Name",
                                                "type": "SINGLE_LINE",
                                                "name": "contactName",
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
        "renderActions": {"action": {"notification": {"text": f"Got it — name received: {name}"}}}
    }
