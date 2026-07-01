"""Tests for TicketDraft pre-fill in dialog.open_dialog().

Verifies the step-4 pre-fill flow against the three factory drafts:
- full:    every editable widget carries the draft's value / selected item
- partial: dropped fields (subject, location) render empty
- empty:   the dialog degrades to the same blank form as the manual path

These run entirely against factory drafts — no Kautilya code, no Firestore.
When the real source lands, open_dialog() is unchanged, so these stay valid.
"""

from __future__ import annotations

from typing import Any

import pytest
from app.cards import dialog
from molli_shared.schemas.factories import (
    _fc,
    make_draft,
    make_empty_draft,
    make_partial_draft,
)

# ---------------------------------------------------------------------------
# Helpers — flatten the nested dialog into name -> widget lookups so tests
# assert on intent ("subject is pre-filled") not on push-card path depth.
# ---------------------------------------------------------------------------


def _widgets(resp: dict[str, Any]) -> list[dict[str, Any]]:
    """All leaf widgets in the pushed card, descending into `columns`."""
    section = resp["action"]["navigations"][0]["pushCard"]["sections"][0]
    out: list[dict[str, Any]] = []
    for w in section["widgets"]:
        if "columns" in w:
            for col in w["columns"]["columnItems"]:
                out.extend(col["widgets"])
        else:
            out.append(w)
    return out


def _by_name(resp: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map input `name` -> the inner widget config (textInput/selectionInput)."""
    result: dict[str, dict[str, Any]] = {}
    for w in _widgets(resp):
        for kind in ("textInput", "selectionInput"):
            if kind in w and "name" in w[kind]:
                result[w[kind]["name"]] = w[kind]
    return result


def _selected(select_widget: dict[str, Any]) -> list[str]:
    """Values of items marked selected in a selectionInput."""
    return [it["value"] for it in select_widget["items"] if it.get("selected")]


# ---------------------------------------------------------------------------
# Full draft — everything pre-filled
# ---------------------------------------------------------------------------


def test_full_draft_prefills_text_inputs():
    draft = make_draft()
    fields = _by_name(dialog.open_dialog(draft))

    assert fields["email"]["value"] == draft.email.value
    assert fields["subject"]["value"] == draft.subject.value
    assert fields["description"]["value"] == draft.description.value
    assert fields["computerName"]["value"] == draft.computer_name_if_it_issue.value


def test_full_draft_preselects_group_dropdown():
    draft = make_draft()
    fields = _by_name(dialog.open_dialog(draft))
    # group_id is an int in the draft; the widget value is the stringified id.
    assert _selected(fields["group"]) == [str(draft.group_id.value)]


def test_full_draft_preselects_priority_radio():
    draft = make_draft()
    fields = _by_name(dialog.open_dialog(draft))
    assert _selected(fields["priority"]) == [str(draft.priority.value)]


def test_full_draft_preselects_system_dropdown():
    draft = make_draft()
    fields = _by_name(dialog.open_dialog(draft))
    assert _selected(fields["systemItem"]) == [draft.original_system.value]


def test_full_draft_preselects_multi_select_locations():
    draft = make_draft(msf_affected_location=_fc(["Raleigh Condos", "Nova Knoxville"]))
    fields = _by_name(dialog.open_dialog(draft))
    assert set(_selected(fields["affectedLocation"])) == {
        "Raleigh Condos",
        "Nova Knoxville",
    }


def test_int_fields_prefill_as_strings_not_ints():
    """Regression guard for the int->str boundary: widget values must be str."""
    draft = make_draft()
    fields = _by_name(dialog.open_dialog(draft))
    for item in fields["group"]["items"] + fields["priority"]["items"]:
        assert isinstance(item["value"], str)


# ---------------------------------------------------------------------------
# Partial draft — dropped fields render empty, the rest still fill
# ---------------------------------------------------------------------------


def test_partial_draft_leaves_dropped_text_empty():
    # make_partial_draft drops subject and location.
    fields = _by_name(dialog.open_dialog(make_partial_draft()))
    assert fields["subject"]["value"] == ""


def test_partial_draft_leaves_dropped_multiselect_unselected():
    fields = _by_name(dialog.open_dialog(make_partial_draft()))
    assert _selected(fields["affectedLocation"]) == []


def test_partial_draft_still_prefills_present_fields():
    fields = _by_name(dialog.open_dialog(make_partial_draft()))
    # email survives in the partial draft
    assert fields["email"]["value"] == "lindsey.bowman@preiss.com"


def test_none_value_field_renders_empty():
    """A FieldConfidence whose value is None -> empty widget, no crash."""
    draft = make_draft(subject=None)
    fields = _by_name(dialog.open_dialog(draft))
    assert fields["subject"]["value"] == ""


# ---------------------------------------------------------------------------
# Empty draft — degrades to a blank form
# ---------------------------------------------------------------------------


def test_empty_draft_all_text_inputs_blank():
    fields = _by_name(dialog.open_dialog(make_empty_draft()))
    for name in ("email", "subject", "description", "computerName"):
        assert fields[name]["value"] == ""


def test_empty_draft_no_selections():
    fields = _by_name(dialog.open_dialog(make_empty_draft()))
    for name in ("group", "systemItem", "priority", "affectedLocation"):
        assert _selected(fields[name]) == []


# ---------------------------------------------------------------------------
# Structure is preserved — pre-fill didn't break the envelope
# ---------------------------------------------------------------------------


def test_required_widgets_unchanged():
    """Pre-fill must not alter the submit button's requiredWidgets contract."""
    # find the submit button anywhere in the widget tree
    submit = None
    for w in _widgets(dialog.open_dialog(make_draft())):
        if "buttonList" in w:
            submit = w["buttonList"]["buttons"][0]
    assert submit is not None
    required = submit["onClick"]["action"]["requiredWidgets"]
    assert set(required) == {
        "email",
        "subject",
        "group",
        "affectedLocation",
        "systemItem",
        "priority",
        "description",
    }


def test_returns_pushcard_envelope():
    resp = dialog.open_dialog(make_draft())
    assert "navigations" in resp["action"]
    assert "pushCard" in resp["action"]["navigations"][0]


# ---------------------------------------------------------------------------
# Round-trip sanity — a full factory draft converts to a valid payload
# ---------------------------------------------------------------------------


def test_full_draft_converts_to_payload():
    """The full factory draft satisfies to_payload() (original_more_detail set)."""
    payload = make_draft().to_payload()
    assert payload.email == "lindsey.bowman@preiss.com"
    assert payload.group_id == 5000233136
    assert payload.custom_fields.original_more_detail == "Other"


def test_draft_without_more_detail_needs_override():
    """If the draft omits original_more_detail, to_payload needs it injected."""
    from molli_shared.schemas.ticket import DraftIncompleteError

    draft = make_draft(include_more_detail=False)
    with pytest.raises(DraftIncompleteError):
        draft.to_payload()
    # injecting it as an override (the handler's job) resolves it
    payload = draft.to_payload(overrides={"original_more_detail": "Other"})
    assert payload.custom_fields.original_more_detail == "Other"
