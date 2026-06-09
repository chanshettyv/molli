"""Tests for the FairHousingGuardrail.

Covers:
- FHA trigger patterns (screening criteria, adverse action, protected classes)
- FCRA is handled in test_fcra.py — not tested here
- Exclusion patterns (Grace Hill, job screening interviews)
- Normal messages that should pass through
"""

from __future__ import annotations

import pytest

from molli_shared.guardrails.fair_housing import FairHousingGuardrail
from molli_shared.guardrails.base import Action

USER = "test.user@preiss.com"

guardrail = FairHousingGuardrail()


# ---------------------------------------------------------------------------
# FHA triggers — should BLOCK
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blocks_screening_criteria():
    verdict = await guardrail.check("what are the screening criteria for applicants?", USER)
    assert verdict.action == Action.BLOCK
    assert verdict.category == "FAIR_HOUSING"

@pytest.mark.asyncio
async def test_blocks_adverse_action():
    verdict = await guardrail.check("how do I write an adverse action letter?", USER)
    assert verdict.action == Action.BLOCK

@pytest.mark.asyncio
async def test_blocks_applicant_denial():
    verdict = await guardrail.check("what's the process for applicant denial?", USER)
    assert verdict.action == Action.BLOCK

@pytest.mark.asyncio
async def test_blocks_fair_housing_direct():
    verdict = await guardrail.check("can you explain the fair housing rules?", USER)
    assert verdict.action == Action.BLOCK

@pytest.mark.asyncio
async def test_blocks_fha_abbreviation():
    verdict = await guardrail.check("what does FHA require us to do?", USER)
    assert verdict.action == Action.BLOCK

@pytest.mark.asyncio
async def test_blocks_deny_applicant():
    verdict = await guardrail.check("can we deny an applicant based on income?", USER)
    assert verdict.action == Action.BLOCK

@pytest.mark.asyncio
async def test_blocks_denial_letter():
    verdict = await guardrail.check("where do I find a denial letter template?", USER)
    assert verdict.action == Action.BLOCK

@pytest.mark.asyncio
async def test_canned_response_is_set():
    verdict = await guardrail.check("what are the screening criteria?", USER)
    assert verdict.canned_response is not None
    assert "Sally" in verdict.canned_response


# ---------------------------------------------------------------------------
# Exclusion patterns — should ALLOW
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_allows_grace_hill():
    verdict = await guardrail.check("how do I access Grace Hill training?", USER)
    assert verdict.action == Action.ALLOW

@pytest.mark.asyncio
async def test_allows_screening_interview():
    verdict = await guardrail.check("I have a screening call with a vendor tomorrow", USER)
    assert verdict.action == Action.ALLOW

@pytest.mark.asyncio
async def test_allows_screening_meeting():
    verdict = await guardrail.check("can you help me prep for my screening interview?", USER)
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

@pytest.mark.asyncio
async def test_allows_entrata_question():
    verdict = await guardrail.check("how do I request access to Entrata?", USER)
    assert verdict.action == Action.ALLOW