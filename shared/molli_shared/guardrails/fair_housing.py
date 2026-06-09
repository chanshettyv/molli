"""Fair Housing (FHA) guardrail.

Detects questions about tenant screening criteria, protected classes,
and adverse action language under the Fair Housing Act.

Action: BLOCK — refuse the question entirely and direct the employee
to HR. Simple always-block, no repeat-trigger logic, no escalation email.
"""

from __future__ import annotations

import re

from .base import Action, GuardrailVerdict

# ---------------------------------------------------------------------------
# Trigger patterns — FHA protected classes and screening language
# ---------------------------------------------------------------------------

_FHA_PATTERNS: list[str] = [
    # Explicit FHA references
    r"\bprotected class(es)?\b",
    r"\bfair housing\b",
    r"\bfha\b",
    # Tenant decision language
    r"\bdeny(ing)? (an? )?(applicant|tenant|renter)\b",
    r"\brefuse (to rent|an? applicant)\b",
    r"\bscreening criter(ia|ion)\b",
    r"\bapplicant denial\b",
    r"\bdisqualif(y|ied|ying) (an? )?(applicant|tenant)\b",
    r"\badverse action\b",
    r"\bdenial (letter|notice|reason)\b",
    # FHA protected classes — any standalone mention triggers the guardrail;
    # Molli must never engage with these topics regardless of available info.
    r"\brace\b",
    r"\breligion\b",
    r"\bnational origin\b",
    r"\bfamilial status\b",
    r"\b(disability|handicap)\b",
    r"\bsex\b",
    r"\bsexual orientation\b",
    r"\bgender identity\b",
    r"\bsource of income\b",
]

# Exclusion patterns — benign uses of otherwise triggering words.
# Checked BEFORE trigger patterns; a match here always allows.
_EXCLUSION_PATTERNS: list[str] = [
    r"\bgrace hill\b",  # training platform
    r"\bscreening (call|interview|meeting|session)\b",  # job interviews
    r"\bsexual harassment\b",  # HR topic, not FHA
    r"\breligious (holiday|accommodation|observance|leave|exemption)\b",  # HR/EEO
    r"\brace condition\b",  # software term
    r"\bdisability (insurance|benefit|claim|leave)\b",  # HR/benefits
]

CANNED_RESPONSE = (
    "I'm not able to help with questions about tenant screening criteria "
    "or Fair Housing. These topics require HR or legal review. Please "
    "contact Sally Sousa in HR directly for guidance."
)


def _matches_any(text: str, patterns: list[str]) -> str | None:
    """Return the first matching pattern string, or None."""
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return p
    return None


class FairHousingGuardrail:
    name = "fair_housing"

    async def check(self, message: str, user_email: str) -> GuardrailVerdict:
        lower = message.lower()

        # Exclusion check first
        if _matches_any(lower, _EXCLUSION_PATTERNS):
            return GuardrailVerdict(
                action=Action.ALLOW,
                category="FAIR_HOUSING",
                reason="Matched exclusion pattern (known-safe language)",
            )

        if matched := _matches_any(lower, _FHA_PATTERNS):
            return GuardrailVerdict(
                action=Action.BLOCK,
                category="FAIR_HOUSING",
                reason=f"FHA pattern matched: {matched}",
                canned_response=CANNED_RESPONSE,
            )

        return GuardrailVerdict(
            action=Action.ALLOW,
            category="FAIR_HOUSING",
            reason="No FHA signals detected",
        )
