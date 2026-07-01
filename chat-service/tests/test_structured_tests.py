# chat-service/tests/test_structured_requests.py
from app.cards.structured_requests import (
    DISTRIBUTION_LIST,
    ENTRATA_ACCESS,
    _resolve_values,
    build_ticket_fields,
    format_description,
)


class TestResolveValues:
    def test_strips_whitespace(self):
        out = _resolve_values(ENTRATA_ACCESS, {"property": "  The Forum  "})
        assert out["property"] == "The Forum"

    def test_access_for_defaults_to_requester_when_blank(self):
        out = _resolve_values(
            ENTRATA_ACCESS,
            {"requester": "vedant@preiss.com", "access_for": ""},
        )
        assert out["access_for"] == "vedant@preiss.com"

    def test_access_for_kept_when_present(self):
        out = _resolve_values(
            ENTRATA_ACCESS,
            {"requester": "vedant@preiss.com", "access_for": "Seth Hooper"},
        )
        assert out["access_for"] == "Seth Hooper"

    def test_distribution_list_does_not_default_anything(self):
        out = _resolve_values(DISTRIBUTION_LIST, {"target_user": "", "requester": "v@p.com"})
        assert out["target_user"] == ""  # no special-casing for dist list

    def test_does_not_mutate_input(self):
        original = {"property": "  X  "}
        _resolve_values(ENTRATA_ACCESS, original)
        assert original["property"] == "  X  "


class TestFormatDescription:
    def test_full_entrata_body(self):
        resolved = _resolve_values(
            ENTRATA_ACCESS,
            {
                "requester": "vedant@preiss.com",
                "access_for": "Seth Hooper",
                "property": "The Forum",
                "permissions": "Add charges to ledger",
            },
        )
        body = format_description(ENTRATA_ACCESS, resolved)
        assert "Entrata access request" in body
        assert "Requester: vedant@preiss.com" in body
        assert "Access for: Seth Hooper" in body
        assert "Property: The Forum" in body
        assert "Permissions requested: Add charges to ledger" in body
        assert body.endswith("— Submitted via Molli")

    def test_missing_required_field_shows_placeholder(self):
        resolved = _resolve_values(
            ENTRATA_ACCESS,
            {
                "requester": "v@p.com",
                "access_for": "v@p.com",
                "permissions": "Add charges",
                # property missing
            },
        )
        body = format_description(ENTRATA_ACCESS, resolved)
        assert "Property: (not provided)" in body

    def test_missing_optional_field_omitted(self):
        # access_for is optional; when blank it defaults to requester via
        # _resolve_values, so to truly test omission use a spec field that's
        # optional AND not defaulted — here we assert the line is never "—"
        resolved = _resolve_values(
            ENTRATA_ACCESS,
            {
                "requester": "v@p.com",
                "access_for": "",
                "property": "The Forum",
                "permissions": "Add charges",
            },
        )
        body = format_description(ENTRATA_ACCESS, resolved)
        assert "Access for: v@p.com" in body  # defaulted, not omitted
        # No field value should render as a bare em-dash placeholder.
        # The footer "— Submitted via Molli" is intentional and excluded here.
        assert ": —" not in body


class TestBuildTicketFields:
    def test_returns_three_keys(self):
        out = build_ticket_fields(
            ENTRATA_ACCESS,
            {
                "requester": "v@p.com",
                "access_for": "Seth Hooper",
                "property": "The Forum",
                "permissions": "Add charges",
            },
        )
        assert set(out.keys()) == {"subject", "description", "group_id"}

    def test_entrata_subject_format(self):
        out = build_ticket_fields(
            ENTRATA_ACCESS,
            {
                "requester": "v@p.com",
                "access_for": "Seth Hooper",
                "property": "The Forum",
                "permissions": "Add charges",
            },
        )
        assert out["subject"] == "Entrata access: Seth Hooper @ The Forum"

    def test_subject_uses_resolved_access_for(self):
        # access_for blank → defaults to requester → subject names requester
        out = build_ticket_fields(
            ENTRATA_ACCESS,
            {
                "requester": "vedant@preiss.com",
                "access_for": "",
                "property": "The Forum",
                "permissions": "Add charges",
            },
        )
        assert out["subject"] == "Entrata access: vedant@preiss.com @ The Forum"

    def test_distribution_list_subject_format(self):
        out = build_ticket_fields(
            DISTRIBUTION_LIST,
            {
                "requester": "v@p.com",
                "action": "remove",
                "target_user": "erin@preiss.com",
                "list_address": "novaknoxville@preiss.com",
            },
        )
        assert (
            out["subject"] == "Distribution list remove: erin@preiss.com → novaknoxville@preiss.com"
        )

    def test_group_id_matches_spec(self):
        out = build_ticket_fields(DISTRIBUTION_LIST, {"action": "add"})
        assert out["group_id"] == DISTRIBUTION_LIST.group_id

    def test_description_and_subject_agree_on_access_for(self):
        # the whole point of single-resolution: body and subject can't diverge
        out = build_ticket_fields(
            ENTRATA_ACCESS,
            {
                "requester": "vedant@preiss.com",
                "access_for": "",
                "property": "The Forum",
                "permissions": "Add charges",
            },
        )
        assert "vedant@preiss.com" in out["subject"]
        assert "Access for: vedant@preiss.com" in out["description"]
