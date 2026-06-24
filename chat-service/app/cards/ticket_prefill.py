"""Helpers for the 'Create Ticket' button shown on no-context replies.

When Molli can't find an answer in Preiss Central, the reply card includes a
'Create Ticket' button. Clicking it opens the existing ticket dialog pre-filled
with the user's email, a subject derived from their question, and a description
that includes the original question as context.

Pre-fill data travels through the button's action parameters (plain strings),
so no Firestore round-trip is needed between the button click and the dialog open.
"""

from __future__ import annotations

from typing import Any

from molli_shared.schemas.factories import _fc, make_draft
from molli_shared.schemas.ticket import TicketDraft

from app.cards.dialog import SERVICE_URL

_MAX_SUBJECT_LEN = 100
_MAX_QUESTION_PARAM = 800  # trimmed before embedding in action parameters


def _derive_subject(question: str) -> str:
    """Trim a user question into a short ticket subject line."""
    q = question.strip().rstrip("?").strip()
    if len(q) <= _MAX_SUBJECT_LEN:
        return q
    return q[:_MAX_SUBJECT_LEN].rsplit(" ", 1)[0] + "..."


def create_ticket_button(user_question: str, user_email: str) -> dict[str, Any]:
    """Return a button widget dict that opens the ticket dialog pre-filled.

    Passes subject, email, and the trimmed question as action parameters so
    the openPrefillDialog handler can build the draft without extra I/O.
    """
    subject = _derive_subject(user_question)
    return {
        "text": "Create Ticket",
        "onClick": {
            "action": {
                "function": SERVICE_URL,
                "interaction": "OPEN_DIALOG",
                "parameters": [
                    {"key": "actionName", "value": "openPrefillDialog"},
                    {"key": "userEmail", "value": user_email},
                    {"key": "subject", "value": subject},
                    {"key": "userQuestion", "value": user_question[:_MAX_QUESTION_PARAM]},
                ],
            }
        },
    }


def build_prefill_draft(
    user_email: str,
    subject: str,
    user_question: str,
    conversation_id: str = "unknown",
) -> TicketDraft:
    """Build a TicketDraft pre-filled from no-context conversation context.

    Email, subject, and description are pre-filled from the conversation.
    Group, location, and system are left empty — the user fills them in the
    dialog before submitting.
    """
    description = (
        f"Question: {user_question}\n\n"
        "Molli could not find this information in Preiss Central. "
        "Please fill in the remaining fields and submit."
    )
    return make_draft(
        draft_id=f"prefill-{conversation_id}",
        conversation_id=conversation_id,
        email=_fc(user_email, 0.99, "user-stated"),
        subject=_fc(subject, 0.85, "inferred"),
        description=_fc(description, 0.80, "inferred"),
        group_id=None,
        original_system=None,
        msf_affected_location=None,
        computer_name_if_it_issue=None,
    )
