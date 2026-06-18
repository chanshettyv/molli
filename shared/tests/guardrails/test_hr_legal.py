"""Tests for the HRLegalGuardrail.

Covers:
- Harassment signals
- Discrimination signals
- Retaliation signals
- Hostile workplace signals
- Wants to report signals
- Exclusion patterns (policy/training questions)
- Normal messages that should pass through
"""

from __future__ import annotations

import pytest

from molli_shared.guardrails.hr_legal import HRLegalGuardrail
from molli_shared.guardrails.base import Action

USER = "test.user@preiss.com"

guardrail = HRLegalGuardrail()


# ---------------------------------------------------------------------------
# Harassment — should ESCALATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalates_sexual_harassment():
    verdict = await guardrail.check("my manager committed sexual harassment", USER)
    assert verdict.action == Action.ESCALATE
    assert verdict.category == "HR_LEGAL"


@pytest.mark.asyncio
async def test_escalates_being_harassed():
    verdict = await guardrail.check("I feel like I am being harassed at work", USER)
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_unwanted_touching():
    verdict = await guardrail.check("a coworker touched me inappropriately", USER)
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_hostile_work_environment():
    verdict = await guardrail.check(
        "my manager is creating a hostile work environment", USER
    )
    assert verdict.action == Action.ESCALATE


# ---------------------------------------------------------------------------
# Discrimination — should ESCALATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalates_discrimination():
    verdict = await guardrail.check("I think I am being discriminated against", USER)
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_age_discrimination():
    verdict = await guardrail.check(
        "I was passed over for a promotion because of my age", USER
    )
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_gender_discrimination():
    verdict = await guardrail.check("I filed a gender discrimination complaint", USER)
    assert verdict.action == Action.ESCALATE


# ---------------------------------------------------------------------------
# Retaliation — should ESCALATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalates_retaliation():
    verdict = await guardrail.check(
        "I am scared I will face retaliation for reporting this", USER
    )
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_afraid_to_report():
    verdict = await guardrail.check("I am afraid to report what happened", USER)
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_threatened_for_reporting():
    verdict = await guardrail.check(
        "my manager threatened me for reporting the incident", USER
    )
    assert verdict.action == Action.ESCALATE


# ---------------------------------------------------------------------------
# Hostile workplace — should ESCALATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalates_feel_unsafe():
    verdict = await guardrail.check("I feel unsafe at work", USER)
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_manager_yelling():
    verdict = await guardrail.check("my manager is yelling and threatening me", USER)
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_workplace_violence():
    verdict = await guardrail.check("there is a workplace violence situation", USER)
    assert verdict.action == Action.ESCALATE


# ---------------------------------------------------------------------------
# Wants to report — should ESCALATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_escalates_wants_to_file_complaint():
    verdict = await guardrail.check("I want to file a harassment complaint", USER)
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_how_to_report_harassment():
    verdict = await guardrail.check("how do I report harassment at work", USER)
    assert verdict.action == Action.ESCALATE


@pytest.mark.asyncio
async def test_escalates_report_confidentially():
    verdict = await guardrail.check("I need to report something confidentially", USER)
    assert verdict.action == Action.ESCALATE


# ---------------------------------------------------------------------------
# Canned response checks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canned_response_is_set():
    verdict = await guardrail.check("I am being harassed at work", USER)
    assert verdict.canned_response is not None


@pytest.mark.asyncio
async def test_canned_response_mentions_hr():
    verdict = await guardrail.check("I am being harassed at work", USER)
    assert "HR" in verdict.canned_response


@pytest.mark.asyncio
async def test_canned_response_does_not_mention_manager():
    verdict = await guardrail.check("I am being harassed at work", USER)
    assert (
        "direct manager" not in verdict.canned_response.lower()
        or "not" in verdict.canned_response.lower()
    )


# ---------------------------------------------------------------------------
# Exclusion patterns — should ALLOW
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allows_harassment_policy_question():
    verdict = await guardrail.check("where can I find the harassment policy?", USER)
    assert verdict.action == Action.ALLOW


@pytest.mark.asyncio
async def test_allows_discrimination_training():
    verdict = await guardrail.check(
        "how do I complete the discrimination training module?", USER
    )
    assert verdict.action == Action.ALLOW


@pytest.mark.asyncio
async def test_allows_define_harassment():
    verdict = await guardrail.check("what is sexual harassment?", USER)
    assert verdict.action == Action.ALLOW


# ---------------------------------------------------------------------------
# Normal messages — should ALLOW
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allows_password_reset():
    verdict = await guardrail.check("how do I reset my Google password?", USER)
    assert verdict.action == Action.ALLOW


@pytest.mark.asyncio
async def test_allows_pto_question():
    verdict = await guardrail.check("how many PTO days do I have left?", USER)
    assert verdict.action == Action.ALLOW


@pytest.mark.asyncio
async def test_allows_printer_question():
    verdict = await guardrail.check("how do I connect to the office printer?", USER)
    assert verdict.action == Action.ALLOW
