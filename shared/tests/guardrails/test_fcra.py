"""Tests for the FCRAGuardrail.

Covers:
- Background check triggers (criminal record, felony, conviction, screening services)
- Credit report triggers (score, pull, FICO, bankruptcy)
- Adverse action triggers
- Screening criteria triggers (eviction history, FCRA mentions)
- Allow patterns (onboarding docs)
- Normal messages that should pass through
"""

from __future__ import annotations

import pytest

from molli_shared.guardrails.fcra import FCRAGuardrail
from molli_shared.guardrails.base import Action

USER = "test.user@preiss.com"

guardrail = FCRAGuardrail()


# ---------------------------------------------------------------------------
# Background check triggers — should BLOCK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocks_background_check():
    verdict = await guardrail.check(
        "how do I run a background check on an applicant?", USER
    )
    assert verdict.action == Action.BLOCK
    assert verdict.category == "FCRA"


@pytest.mark.asyncio
async def test_blocks_criminal_history():
    verdict = await guardrail.check("can we see their criminal history?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_criminal_record():
    verdict = await guardrail.check(
        "they have a criminal record, should we deny them?", USER
    )
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_felony():
    verdict = await guardrail.check(
        "does a felony automatically disqualify an applicant?", USER
    )
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_conviction():
    verdict = await guardrail.check("how far back do we look at convictions?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_misdemeanor():
    verdict = await guardrail.check(
        "does a misdemeanor show up on the screening report?", USER
    )
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_arrest_record():
    verdict = await guardrail.check("can we see their arrest record?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_sex_offender():
    verdict = await guardrail.check("do we check if they are a sex offender?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_consumer_report():
    verdict = await guardrail.check(
        "what counts as a consumer report under the law?", USER
    )
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_transunion():
    verdict = await guardrail.check("how do I read the TransUnion report?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_equifax():
    verdict = await guardrail.check("the Equifax report came back with flags", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_checkr():
    verdict = await guardrail.check("where do I find results in Checkr?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_credit_bureau():
    verdict = await guardrail.check("which credit bureau does Entrata use?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_background_screening():
    verdict = await guardrail.check(
        "what background screening company do we use?", USER
    )
    assert verdict.action == Action.BLOCK


# ---------------------------------------------------------------------------
# Credit report triggers — should BLOCK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocks_credit_score():
    verdict = await guardrail.check("what credit score is required to rent?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_credit_report():
    verdict = await guardrail.check(
        "how do I read a credit report for an applicant?", USER
    )
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_credit_pull():
    verdict = await guardrail.check("when do we pull their credit?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_soft_credit_pull():
    verdict = await guardrail.check("is the first pull a soft credit pull?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_fico():
    verdict = await guardrail.check("what FICO score do we require?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_bankruptcy():
    verdict = await guardrail.check("does a bankruptcy disqualify someone?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_collection_account():
    verdict = await guardrail.check(
        "they have a collection account, can we deny them?", USER
    )
    assert verdict.action == Action.BLOCK


# ---------------------------------------------------------------------------
# Adverse action triggers — should BLOCK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocks_adverse_action():
    verdict = await guardrail.check("how do I send an adverse action notice?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_rejection_letter():
    verdict = await guardrail.check("where is the rejection letter template?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_denied_based_on():
    verdict = await guardrail.check(
        "can we say they were denied based on the report?", USER
    )
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_consumer_dispute():
    verdict = await guardrail.check(
        "they filed a consumer dispute, what do we do?", USER
    )
    assert verdict.action == Action.BLOCK


# ---------------------------------------------------------------------------
# Screening criteria triggers — should BLOCK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocks_screening_policy():
    verdict = await guardrail.check(
        "what is our screening policy for applicants?", USER
    )
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_eviction_history():
    verdict = await guardrail.check("do we check eviction history?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_prior_evictions():
    verdict = await guardrail.check(
        "they have prior evictions, should we approve them?", USER
    )
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_eviction_on_record():
    verdict = await guardrail.check("there is an eviction on their record", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_fcra_standalone():
    verdict = await guardrail.check("what does FCRA require us to do?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_rental_history():
    verdict = await guardrail.check("how do we verify rental history?", USER)
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_should_we_approve():
    verdict = await guardrail.check(
        "based on the report, should we approve them?", USER
    )
    assert verdict.action == Action.BLOCK


@pytest.mark.asyncio
async def test_blocks_should_we_deny():
    verdict = await guardrail.check("should we deny this applicant?", USER)
    assert verdict.action == Action.BLOCK


# ---------------------------------------------------------------------------
# Canned response sanity check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canned_response_is_set():
    verdict = await guardrail.check("what credit score do we require?", USER)
    assert verdict.canned_response is not None
    assert "Sally" in verdict.canned_response


# ---------------------------------------------------------------------------
# Allow patterns — should ALLOW
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allows_new_hire_onboarding():
    verdict = await guardrail.check(
        "what documents do we need to collect from a new hire?", USER
    )
    assert verdict.action == Action.ALLOW


@pytest.mark.asyncio
async def test_allows_new_employee_paperwork():
    verdict = await guardrail.check(
        "where is the new employee onboarding paperwork?", USER
    )
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
async def test_allows_entrata_access():
    verdict = await guardrail.check("how do I request access to Entrata?", USER)
    assert verdict.action == Action.ALLOW


@pytest.mark.asyncio
async def test_allows_maintenance_request():
    verdict = await guardrail.check("how do I submit a maintenance request?", USER)
    assert verdict.action == Action.ALLOW
