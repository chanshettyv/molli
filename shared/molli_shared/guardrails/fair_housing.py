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
    # Tenant decision language tied to protected classes
    r"\bdeny(ing)? (an? )?(applicant|tenant|renter)\b",
    r"\brefuse (to rent|an? applicant)\b",
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
    r"\breject.{0,30}(kids|children|families|pregnant)\b",
    r"\baccent.{0,30}(good fit|approve|deny|reject)\b",
    r"\bwheelchair.{0,30}(modify|modification|unit)\b",
    r"\bkeep (families|kids|children) out\b",
    r"\bavoid renting to\b",
    r"\bstop accepting (vouchers|section 8)\b",
    r"\bsection 8.{0,30}(stop|refuse|avoid|reject)\b",
    r"\breject.{0,30}(kids|children|families|pregnant)\b",
    r"\baccent.{0,30}(good fit|approve|deny|reject)\b",
    r"\bwheelchair.{0,30}(modify|modification|unit)\b",
    r"\bkeep (families|kids|children) out\b",
    r"\bavoid renting to\b",
    r"\bstop accepting (vouchers|section 8)\b",
    r"\bsection 8.{0,30}(stop|refuse|avoid|reject)\b",
    r"\bstop renting to\b",
    r"\bdon'?t (want to|rent to).{0,30}(people from|anyone from)\b",
    r"\breject.{0,60}(kids|children|families|pregnant)\b",
    r"\b(kids|children|families).{0,30}reject\b",
    r"\bapplicant.{0,30}(kids|children|a lot of kids)\b",
    r"\bhas an accent\b",
    r"\baccent.{0,60}(good fit|fit|approve|deny|reject)\b",
    r"\bnot sure (they'?ll?|she'?ll?|he'?ll?) be a good fit\b",
]

# Exclusion patterns — benign uses of otherwise triggering words.
# Checked BEFORE trigger patterns; a match here always allows.
_EXCLUSION_PATTERNS: list[str] = [
    r"\bgrace hill\b",  # training platform
    # Tenant screening / FCRA — intentionally allowed through to RAG
    r"\bscreening\b",
    r"\bbackground (check|report)\b",
    r"\bcredit (check|report|score|requirement)\b",
    r"\bcriminal (history|background|record|conviction)\b",
    r"\bincome (requirement|verification|threshold|ratio|multiplier|limit)\b",
    r"\badverse action\b",
    r"\bfcra\b",
    r"\bscreening (call|interview|meeting|session)\b",  # job interviews
    r"\bsexual harassment\b",  # HR topic, not FHA
    r"\breligious (holiday|accommodation|observance|leave|exemption)\b",  # HR/EEO
    r"\brace condition\b",  # software term
    r"\b(a race|in a race)\b",  # competitive idiom: "in a race to finish"
    r"\bdisability (insurance|benefit|claim|leave|accommodation|access|paperwork|form|services|request)\b",
    r"\breligion (in the workplace|policy|accommodation|training|question)\b",
    r"\bsex (on the|on a|field|column|box|section)\b",  # employment form fields
    r"\bfor sex on\b",  # "fill in for sex on the form"
    r"\bwhat is (the )?fair housing\b",
    r"\bfair housing (act|law|complaint|process|policy|training|requirements?|compliance)\b",
    r"\b(comply|complian).{0,40}fair housing\b",
    r"\bour process for.{0,30}fair housing\b",
    r"\bhandle.{0,30}fair housing complaint\b",
    r"\bnational origin.{0,40}(field|column|box|section|form|required|question|on the)\b",
    r"\bsource of income.{0,40}(verify|verif|qualif|eligib|question|can i ask|allowed|policy|requirement)\b",
    r"\b(can i|can we|is it (ok|okay|legal|allowed)).{0,30}(ask|require).{0,30}(source of income|income verification)\b",
]

CANNED_RESPONSE = (
    "I'm not able to help with questions about tenant screening criteria "
    "or Fair Housing. These topics require HR or legal review. Please "
    "contact HR directly for guidance."
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
