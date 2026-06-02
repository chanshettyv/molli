"""FCRA (Fair Credit Reporting Act) guardrail.

Blocks any guidance on background checks, credit reports, adverse action,
or consumer report interpretation without verified HR authorization.
All triggers are flagged for Sally Sousa's weekly review.

Action: BLOCK — return FCRA canned response.
"""
from __future__ import annotations

import re

from .base import Action, Guardrail, GuardrailVerdict

# ---------------------------------------------------------------------------
# Trigger patterns — keyed by FCRA subcategory
# ---------------------------------------------------------------------------

_SUBCATEGORY_PATTERNS: dict[str, list[str]] = {
    "background_check": [
        r"\bbackground check\b",
        r"\bcriminal (history|record|background)\b",
        r"\brun a (background|check)\b",
        r"\bwhat shows up on\b",
        r"\bbackground check results\b",
        r"\bwhere do i find the background check\b",
        r"\bfelony\b",
        r"\bconviction\b",
    ],
    "credit_report": [
        r"\bcredit (report|score|check|pull|history)\b",
        r"\bpull their credit\b",
        r"\bwhat credit score\b",
        r"\bread a credit report\b",
        r"\bhard (and )?soft credit pull\b",
        r"\bsoft credit pull\b",
    ],
    "adverse_action": [
        r"\badverse action\b",
        r"\brejection (letter|notice)\b",
        r"\bdenied? (because of|based on|due to)\b",
        r"\bhow (do i|to) (tell|write|notify|inform).{0,60}(rejected?|denied?|background|credit)\b",
        r"\bconsumer dispute\b",
        r"\bdisputing their background\b",
    ],
    "screening_criteria": [
        r"\bautomatic(ally)? reject\b",
        r"\bpolicy on evictions?\b",
        r"\beviction on (their )?record\b",
        r"\bscreening (criteria|policy|standards?)\b",
        r"\bshould we approve them\b",
        r"\bshould we (deny|reject|decline)\b",
        r"\bdoes fcra apply\b",
        r"\bfcra (scope|apply|applies)\b",
    ],
}

# Safe / allowed patterns that explicitly should NOT trigger
_ALLOW_PATTERNS: list[str] = [
    r"\bwhat documents do we need (to collect|from) a new hire\b",
    r"\bnew (hire|employee) (onboarding|documents?|paperwork)\b",
]

CANNED_RESPONSE = """I'm not able to provide guidance on background checks, credit reports, or adverse action under the Fair Credit Reporting Act.

This area requires verified HR authorization and legal review. Please contact HR (Sally Sousa) directly for any screening-related questions.

Handling this incorrectly can create legal exposure for Preiss — please don't rely on informal guidance for FCRA matters."""


def _detect_subcategory(text: str) -> str | None:
    for subcategory, patterns in _SUBCATEGORY_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return subcategory
    return None


def _is_allowed(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _ALLOW_PATTERNS)


class FCRAGuardrail:
    name = "fcra"

    async def check(self, message: str, user_email: str) -> GuardrailVerdict:
        if _is_allowed(message):
            return GuardrailVerdict(
                action=Action.ALLOW,
                category="FCRA",
                reason="Matched safe onboarding/HR pattern — not FCRA territory",
            )

        subcategory = _detect_subcategory(message)
        if subcategory:
            return GuardrailVerdict(
                action=Action.BLOCK,
                category="FCRA",
                reason=f"FCRA trigger: subcategory={subcategory} | flagged_for_sally_review=true",
                canned_response=CANNED_RESPONSE,
            )

        return GuardrailVerdict(
            action=Action.ALLOW,
            category="FCRA",
            reason="No FCRA signals detected",
        )
