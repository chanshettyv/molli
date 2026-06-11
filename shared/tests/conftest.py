"""Shared test fixtures.

Fixtures here are reused across test_ticket_schemas.py and
test_freshservice_client.py. Keep them minimal — tests that need richer
shapes should construct them inline or load from fixtures/freshservice/*.json.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from molli_shared.schemas.ticket import (
    FieldConfidence,
    TicketCreatePayload,
    TicketDraft,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "freshservice"


def load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture from fixtures/freshservice/."""
    path = FIXTURES_DIR / name
    return json.loads(path.read_text())


@pytest.fixture
def valid_custom_fields_dict() -> dict[str, Any]:
    return {
        "original_system": "Computer/Laptop",
        "original_more_detail": "Password Reset",
        "msf_affected_location": ["Corporate: PM"],
    }


@pytest.fixture
def valid_payload_dict(valid_custom_fields_dict: dict[str, Any]) -> dict[str, Any]:
    return {
        "email": "molli.svc@preiss.com",
        "subject": "[TEST-Molli] Schema test",
        "description": "Plain text body",
        "group_id": 5000233136,
        "custom_fields": valid_custom_fields_dict,
    }


@pytest.fixture
def valid_payload(valid_payload_dict: dict[str, Any]) -> TicketCreatePayload:
    return TicketCreatePayload(**valid_payload_dict)


@pytest.fixture
def fully_populated_draft() -> TicketDraft:
    """A TicketDraft where every required field has a FieldConfidence.

    Useful for tests that exercise the happy-path to_payload() conversion.
    """
    now = datetime.now(UTC)
    return TicketDraft(
        draft_id="draft-uuid-1",
        conversation_id="conv-uuid-1",
        created_at=now,
        updated_at=now,
        molli_conversation_id="conv-uuid-1",
        molli_confidence_score=0.85,
        molli_escalation_reason="user-requested-human",
        email=FieldConfidence(value="user@preiss.com", confidence=1.0, source="lookup"),
        subject=FieldConfidence(
            value="Laptop making beeping noise",
            confidence=0.9,
            source="inferred",
        ),
        description=FieldConfidence(
            value="The user reports their laptop beeps when closed.",
            confidence=0.85,
            source="inferred",
        ),
        group_id=FieldConfidence(value=5000233136, confidence=0.95, source="inferred"),
        original_system=FieldConfidence(
            value="Computer/Laptop", confidence=0.95, source="inferred"
        ),
        original_more_detail=FieldConfidence(
            value="Hardware Issue", confidence=0.7, source="inferred"
        ),
        msf_affected_location=FieldConfidence(
            value=["Corporate: PM"], confidence=0.8, source="lookup"
        ),
    )


@pytest.fixture
def created_ticket_response() -> dict[str, Any]:
    """A realistic 201 response body from POST /tickets, mirroring the shape
    we captured from real Freshservice traffic during the Postman spike."""
    return {
        "ticket": {
            "id": 87040,
            "subject": "[TEST-Molli] Postman spike",
            "group_id": 5000233136,
            "department_id": None,
            "category": None,
            "sub_category": None,
            "item_category": None,
            "requester_id": 5000387689,
            "responder_id": None,
            "due_by": "2026-06-02T19:16:07Z",
            "fr_escalated": False,
            "deleted": False,
            "spam": False,
            "is_escalated": False,
            "fr_due_by": "2026-06-01T19:46:07Z",
            "priority": 2,
            "status": 2,
            "source": 4,
            "created_at": "2026-06-01T19:16:06Z",
            "updated_at": "2026-06-01T19:16:07Z",
            "workspace_id": 2,
            "type": "Incident",
            "description": "<div>Test body</div>",
            "description_text": "Test body",
            "custom_fields": {
                "original_system": "Computer/Laptop",
                "original_more_detail": "Password Reset",
                "msf_affected_location": ["Corporate: PM"],
            },
            "tasks_dependency_type": 0,
        }
    }


@pytest.fixture
def requester_response() -> dict[str, Any]:
    """A 200 response body from GET /requesters?email=..."""
    return {
        "requesters": [
            {
                "id": 5000387689,
                "first_name": "Test",
                "last_name": "User",
                "primary_email": "user@preiss.com",
                "active": True,
                "address": None,
                "department_ids": [],
                "job_title": "Property Manager",
                "work_phone_number": None,
                "custom_fields": {},
            }
        ]
    }


@pytest.fixture
def validation_error_response() -> dict[str, Any]:
    """A 400 response body from POST /tickets with a missing-field error.

    Matches Freshservice's actual error envelope shape.
    """
    return {
        "description": "Validation failed",
        "errors": [
            {
                "field": "custom_fields.original_system",
                "message": "It should be one of these values: 'Google Workspace', 'Computer/Laptop', ...",
                "code": "invalid_value",
            }
        ],
    }
