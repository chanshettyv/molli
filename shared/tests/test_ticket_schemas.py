"""Tests for ticket pydantic schemas (no HTTP).

Covers:
- Strict models: MolliCustomFields, TicketCreatePayload, RequesterRecord, CreatedTicket
- Draft models: FieldConfidence, TicketDraft, to_payload() conversion

Client tests with mocked HTTP live in test_freshservice_client.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from molli_shared.schemas.ticket import (
    CreatedTicket,
    DraftIncompleteError,
    FieldConfidence,
    MolliCustomFields,
    RequesterRecord,
    TicketCreatePayload,
    TicketDraft,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# MolliCustomFields
# ---------------------------------------------------------------------------


class TestMolliCustomFields:
    def test_minimal_valid(self, valid_custom_fields_dict):
        fields = MolliCustomFields(**valid_custom_fields_dict)
        assert fields.original_system == "Computer/Laptop"
        assert fields.msf_affected_location == ["Corporate: PM"]

    def test_missing_original_system_rejected(self, valid_custom_fields_dict):
        del valid_custom_fields_dict["original_system"]
        with pytest.raises(ValidationError) as exc_info:
            MolliCustomFields(**valid_custom_fields_dict)
        assert "original_system" in str(exc_info.value)

    def test_missing_original_more_detail_rejected(self, valid_custom_fields_dict):
        del valid_custom_fields_dict["original_more_detail"]
        with pytest.raises(ValidationError):
            MolliCustomFields(**valid_custom_fields_dict)

    def test_empty_location_list_rejected(self, valid_custom_fields_dict):
        valid_custom_fields_dict["msf_affected_location"] = []
        with pytest.raises(ValidationError):
            MolliCustomFields(**valid_custom_fields_dict)

    def test_multiple_locations_accepted(self, valid_custom_fields_dict):
        valid_custom_fields_dict["msf_affected_location"] = [
            "Corporate: PM",
            "The Forum",
            "Cabana Beach",
        ]
        fields = MolliCustomFields(**valid_custom_fields_dict)
        assert len(fields.msf_affected_location) == 3

    @pytest.mark.parametrize("invalid", [-0.1, 1.5, 2.0])
    def test_confidence_score_out_of_range_rejected(
        self, valid_custom_fields_dict, invalid
    ):
        valid_custom_fields_dict["molli_confidence_score"] = invalid
        with pytest.raises(ValidationError):
            MolliCustomFields(**valid_custom_fields_dict)

    @pytest.mark.parametrize("valid", [0.0, 0.5, 1.0])
    def test_confidence_score_boundaries_accepted(
        self, valid_custom_fields_dict, valid
    ):
        valid_custom_fields_dict["molli_confidence_score"] = valid
        fields = MolliCustomFields(**valid_custom_fields_dict)
        assert fields.molli_confidence_score == valid

    @pytest.mark.parametrize(
        "reason",
        [
            "no-confident-answer",
            "user-requested-human",
            "guardrail-triggered",
            "other",
        ],
    )
    def test_escalation_reason_known_values(self, valid_custom_fields_dict, reason):
        valid_custom_fields_dict["molli_escalation_reason"] = reason
        fields = MolliCustomFields(**valid_custom_fields_dict)
        assert fields.molli_escalation_reason == reason

    def test_escalation_reason_unknown_rejected(self, valid_custom_fields_dict):
        valid_custom_fields_dict["molli_escalation_reason"] = "made-up-reason"
        with pytest.raises(ValidationError):
            MolliCustomFields(**valid_custom_fields_dict)

    def test_typo_in_field_name_rejected(self, valid_custom_fields_dict):
        """extra='forbid' catches typos at validation time."""
        valid_custom_fields_dict["orginal_system"] = "typo"
        with pytest.raises(ValidationError):
            MolliCustomFields(**valid_custom_fields_dict)


# ---------------------------------------------------------------------------
# TicketCreatePayload
# ---------------------------------------------------------------------------


class TestTicketCreatePayload:
    def test_minimal_valid(self, valid_payload_dict):
        payload = TicketCreatePayload(**valid_payload_dict)
        assert payload.email == "molli.svc@preiss.com"
        assert payload.status == 2  # Open
        assert payload.priority == 2  # Medium
        assert payload.source == 4  # Chat
        assert payload.type == "Incident"

    def test_invalid_email_rejected(self, valid_payload_dict):
        valid_payload_dict["email"] = "not-an-email"
        with pytest.raises(ValidationError):
            TicketCreatePayload(**valid_payload_dict)

    def test_empty_subject_rejected(self, valid_payload_dict):
        valid_payload_dict["subject"] = ""
        with pytest.raises(ValidationError):
            TicketCreatePayload(**valid_payload_dict)

    def test_empty_description_rejected(self, valid_payload_dict):
        valid_payload_dict["description"] = ""
        with pytest.raises(ValidationError):
            TicketCreatePayload(**valid_payload_dict)

    def test_missing_group_id_rejected(self, valid_payload_dict):
        del valid_payload_dict["group_id"]
        with pytest.raises(ValidationError):
            TicketCreatePayload(**valid_payload_dict)

    @pytest.mark.parametrize("status", [2, 3, 4, 5])
    def test_valid_status_values(self, valid_payload_dict, status):
        valid_payload_dict["status"] = status
        assert TicketCreatePayload(**valid_payload_dict).status == status

    @pytest.mark.parametrize("status", [0, 1, 6, 99])
    def test_invalid_status_rejected(self, valid_payload_dict, status):
        valid_payload_dict["status"] = status
        with pytest.raises(ValidationError):
            TicketCreatePayload(**valid_payload_dict)

    @pytest.mark.parametrize("priority", [1, 2, 3, 4])
    def test_valid_priority_values(self, valid_payload_dict, priority):
        valid_payload_dict["priority"] = priority
        assert TicketCreatePayload(**valid_payload_dict).priority == priority

    @pytest.mark.parametrize("priority", [0, 5, 99])
    def test_invalid_priority_rejected(self, valid_payload_dict, priority):
        valid_payload_dict["priority"] = priority
        with pytest.raises(ValidationError):
            TicketCreatePayload(**valid_payload_dict)

    @pytest.mark.parametrize("source", list(range(1, 11)))
    def test_valid_source_values(self, valid_payload_dict, source):
        valid_payload_dict["source"] = source
        assert TicketCreatePayload(**valid_payload_dict).source == source

    def test_invalid_source_rejected(self, valid_payload_dict):
        valid_payload_dict["source"] = 99
        with pytest.raises(ValidationError):
            TicketCreatePayload(**valid_payload_dict)

    def test_plain_text_description_accepted(self, valid_payload_dict):
        valid_payload_dict["description"] = "A plain text description."
        payload = TicketCreatePayload(**valid_payload_dict)
        assert "<" not in payload.description

    def test_html_description_accepted(self, valid_payload_dict):
        valid_payload_dict["description"] = "<p>Multi-paragraph.</p><p>Works.</p>"
        payload = TicketCreatePayload(**valid_payload_dict)
        assert payload.description.startswith("<p>")

    def test_serializes_excluding_none(self, valid_payload):
        dumped = valid_payload.model_dump(exclude_none=True)
        assert "email" in dumped
        assert "group_id" in dumped
        # Optional Molli fields with None values are stripped from custom_fields
        cf = dumped["custom_fields"]
        assert "molli_conversation_id" not in cf
        assert "computer_name_if_it_issue" not in cf


# ---------------------------------------------------------------------------
# RequesterRecord
# ---------------------------------------------------------------------------


class TestRequesterRecord:
    def test_minimal_valid(self):
        record = RequesterRecord(id=5000387689, email="user@preiss.com")
        assert record.active is True

    def test_extra_fields_ignored(self):
        """Real Freshservice responses include dozens of fields we don't model."""
        record = RequesterRecord.model_validate(
            {
                "id": 5000387689,
                "email": "user@preiss.com",
                "first_name": "Test",
                "last_name": "User",
                "department_ids": [1, 2],
                "job_title": "Property Manager",
                "work_phone_number": "555-1234",
                "custom_fields": {"some_field": "some_value"},
            }
        )
        assert record.first_name == "Test"
        assert not hasattr(record, "department_ids")


# ---------------------------------------------------------------------------
# CreatedTicket
# ---------------------------------------------------------------------------


class TestCreatedTicket:
    def test_parses_real_response(self, created_ticket_response):
        ticket = CreatedTicket.model_validate(created_ticket_response["ticket"])
        assert ticket.id == 87040
        assert ticket.subject.startswith("[TEST-Molli]")
        assert ticket.requester_id == 5000387689

    def test_minimal_required_fields(self):
        ticket = CreatedTicket(
            id=87040,
            subject="Test",
            status=2,
            priority=2,
            created_at="2026-06-01T19:16:06Z",
        )
        assert ticket.group_id is None

    def test_extra_response_fields_ignored(self):
        ticket = CreatedTicket.model_validate(
            {
                "id": 87040,
                "subject": "Test",
                "status": 2,
                "priority": 2,
                "created_at": "2026-06-01T19:16:06Z",
                # Real response noise
                "fr_escalated": False,
                "workspace_id": 2,
                "tasks_dependency_type": 0,
                "description": "<div>...</div>",
            }
        )
        assert ticket.id == 87040


# ---------------------------------------------------------------------------
# FieldConfidence
# ---------------------------------------------------------------------------


class TestFieldConfidence:
    def test_minimal_valid(self):
        fc = FieldConfidence(value="something", confidence=0.8, source="inferred")
        assert fc.value == "something"
        assert fc.confidence == 0.8

    @pytest.mark.parametrize("invalid", [-0.1, 1.5, 2.0])
    def test_confidence_out_of_range_rejected(self, invalid):
        with pytest.raises(ValidationError):
            FieldConfidence(value="x", confidence=invalid, source="inferred")

    def test_unknown_source_rejected(self):
        with pytest.raises(ValidationError):
            FieldConfidence(value="x", confidence=0.5, source="made-up")  # type: ignore[arg-type]

    def test_accepts_any_value_type(self):
        """value: Any — should accept strings, ints, lists, dicts, None."""
        FieldConfidence(value="string", confidence=0.5, source="inferred")
        FieldConfidence(value=42, confidence=0.5, source="inferred")
        FieldConfidence(value=["a", "b"], confidence=0.5, source="inferred")
        FieldConfidence(value=None, confidence=0.5, source="inferred")


# ---------------------------------------------------------------------------
# TicketDraft
# ---------------------------------------------------------------------------


class TestTicketDraft:
    def _now(self):
        return datetime.now(UTC)

    def test_minimal_valid(self):
        """A draft can be very sparse — only identity fields and Molli's
        traceability fields are required at construction."""
        draft = TicketDraft(
            draft_id="d1",
            conversation_id="c1",
            created_at=self._now(),
            updated_at=self._now(),
            molli_conversation_id="c1",
            molli_confidence_score=0.5,
            molli_escalation_reason="no-confident-answer",
        )
        assert draft.email is None
        assert draft.subject is None

    def test_field_wrappers_accepted(self):
        draft = TicketDraft(
            draft_id="d1",
            conversation_id="c1",
            created_at=self._now(),
            updated_at=self._now(),
            molli_conversation_id="c1",
            molli_confidence_score=0.5,
            molli_escalation_reason="no-confident-answer",
            email=FieldConfidence(value="u@p.com", confidence=1.0, source="lookup"),
        )
        assert draft.email is not None
        assert draft.email.value == "u@p.com"
        assert draft.email.source == "lookup"


# ---------------------------------------------------------------------------
# TicketDraft.to_payload()
# ---------------------------------------------------------------------------


class TestToPayload:
    def test_happy_path(self, fully_populated_draft):
        payload = fully_populated_draft.to_payload()
        assert isinstance(payload, TicketCreatePayload)
        assert payload.email == "user@preiss.com"
        assert payload.group_id == 5000233136
        assert payload.custom_fields.original_system == "Computer/Laptop"
        # Traceability fields propagated from draft -> custom_fields
        assert payload.custom_fields.molli_conversation_id == "conv-uuid-1"
        assert payload.custom_fields.molli_confidence_score == 0.85

    def test_missing_required_field_raises(self):
        """A draft with no email cannot become a payload."""
        draft = TicketDraft(
            draft_id="d1",
            conversation_id="c1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            molli_conversation_id="c1",
            molli_confidence_score=0.5,
            molli_escalation_reason="no-confident-answer",
        )
        with pytest.raises(DraftIncompleteError) as exc_info:
            draft.to_payload()
        assert "email" in exc_info.value.missing_fields
        assert "group_id" in exc_info.value.missing_fields

    def test_missing_required_listed_explicitly(self):
        """The exception names every missing field, not just the first."""
        draft = TicketDraft(
            draft_id="d1",
            conversation_id="c1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            molli_conversation_id="c1",
            molli_confidence_score=0.5,
            molli_escalation_reason="no-confident-answer",
        )
        with pytest.raises(DraftIncompleteError) as exc_info:
            draft.to_payload()
        for required in [
            "email",
            "subject",
            "description",
            "group_id",
            "original_system",
            "original_more_detail",
            "msf_affected_location",
        ]:
            assert required in exc_info.value.missing_fields

    def test_overrides_fill_in_missing(self, fully_populated_draft):
        """User edits in the modal can supply fields Molli didn't propose."""
        # Strip a field from the draft, supply it via overrides instead
        fully_populated_draft.email = None
        payload = fully_populated_draft.to_payload(
            overrides={"email": "edited@preiss.com"}
        )
        assert payload.email == "edited@preiss.com"

    def test_overrides_replace_draft_values(self, fully_populated_draft):
        """User-edited values win over Molli's proposed values."""
        payload = fully_populated_draft.to_payload(
            overrides={"subject": "User-edited subject"}
        )
        assert payload.subject == "User-edited subject"

    def test_overrides_can_supply_custom_fields(self, fully_populated_draft):
        """Custom fields can be overridden too."""
        payload = fully_populated_draft.to_payload(
            overrides={"original_system": "Google Workspace"}
        )
        assert payload.custom_fields.original_system == "Google Workspace"

    def test_priority_defaults_to_medium(self, fully_populated_draft):
        """If neither draft nor overrides set priority, default to Medium (2)."""
        # fully_populated_draft doesn't set priority
        payload = fully_populated_draft.to_payload()
        assert payload.priority == 2

    def test_priority_override_honored(self, fully_populated_draft):
        payload = fully_populated_draft.to_payload(overrides={"priority": 4})
        assert payload.priority == 4
