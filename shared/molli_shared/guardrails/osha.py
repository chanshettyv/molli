"""OSHA / Workplace Safety guardrail.

Two tiers:
  Tier 1 — Active/immediate safety emergency → ESCALATE
  Tier 2 — General safety/compliance question → ALLOW with mandatory referral

Tier 1 takes priority over Tier 2 if both signals are present.
"""

from __future__ import annotations

import re

from .base import Action, GuardrailVerdict

# ---------------------------------------------------------------------------
# Tier 1 — active emergency patterns (present-tense incident or active threat)
# ---------------------------------------------------------------------------

_TIER1_PATTERNS: list[str] = [
    r"\bthere'?s a fire\b",
    r"\bfire in\b",
    r"\bsomeone (just )?(collapsed|fell|is injured|was injured|is hurt|got hurt)\b",
    r"\bthere'?s been an accident\b",
    r"\bgas leak\b",
    r"\bactive (threat|shooter|emergency)\b",
    r"\bsomeone (is )?(threatening|attacked?|assaulted?)\b",
    r"\bresident is threatening\b",
    r"\bstaff member (is being|was) threatened\b",
    r"\bfight (broke out|in|at)\b",
    r"\bfell off (a |the )?ladder\b",
    r"\bmaintenance (tech|worker|staff).{0,30}(fell|fallen|accident)\b",
    r"\b(accident|injury|collapse|emergency)\b.{0,30}\b(now|just|happening|occurred)\b",
    r"\bcall 911\b",
    r"\bevacuat(e|ing)\b",
    r"\bcaught on fire\b",
    r"\bon fire\b",
    r"\bbuilding (is |was )?(on fire|burning)\b",
    r"\bfire (at|on|in) (the |my )?(property|building|unit|office|complex)\b",
    r"\bsmoke (everywhere|filling|coming from)\b",
    r"\bsomething'?s (on fire|burning)\b",
    r"\bfire broke out\b",
    r"\bbreak[- ]?in\b",
    r"\bsomeone broke in\b",
    r"\bintruder\b",
    r"\bunauthorized (person|individual|entry|access).{0,30}(property|building|office|unit)\b",
    r"\btrespassing\b",
    r"\btrespasser\b",
    r"\bsomeone (is |was )?trespassing\b",
    r"\bforced (entry|their way in)\b",
    r"\bbroken into\b",
    r"\bsomeone in the (building|property|office) who (shouldn't|doesn't) belong\b",
]

# Tier 2 — general OSHA compliance / process questions
_TIER2_PATTERNS: list[str] = [
    r"\bhow do i report (a|an) (workplace )?(injury|incident|accident)\b",
    r"\bwhat'?s the (process|procedure|steps?) after (a|an) (workplace )?(accident|injury)\b",
    r"\bosha (requirement|regulation|standard|violation|compliance|rule)\b",
    r"\bfire drill\b",
    r"\bladder safety\b",
    r"\bppe (required?|for|needed)\b",
    r"\bpool chemicals?\b",
    r"\bincident report\b",
    r"\bsafety training\b",
    r"\bpost safety (notice|sign|poster)\b",
    r"\bslipped? (in|on|at)\b",
    r"\bdo i (still )?need to file\b",
]

CANNED_RESPONSE_TIER1 = """This sounds like an active safety situation — please stop and act immediately:

• Call 911 if there is any immediate risk to life
• Evacuate the area if needed and follow your site's emergency plan
• Notify your site manager or Operations lead immediately — do not wait

Once everyone is safe, report the incident through Freshservice or contact the Preiss Operations safety officer.

I'm logging this interaction now so the safety team is aware."""

SAFETY_REFERRAL_SUFFIX = """

⚠️ For any active safety concern or incident, stop using Molli and contact your site manager or the Operations safety officer directly. I can answer general questions, but I'm not a substitute for real-time safety judgment."""


def _is_tier1(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _TIER1_PATTERNS)


def _is_tier2(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _TIER2_PATTERNS)


class OSHAGuardrail:
    name = "osha"

    async def check(self, message: str, user_email: str) -> GuardrailVerdict:
        # Tier 1 takes priority — check first
        if _is_tier1(message):
            return GuardrailVerdict(
                action=Action.ESCALATE,
                category="OSHA",
                reason="OSHA Tier 1 emergency detected | ops_safety_officer_notification=true",
                canned_response=CANNED_RESPONSE_TIER1,
            )

        if _is_tier2(message):
            return GuardrailVerdict(
                action=Action.ALLOW,
                category="OSHA",
                reason="OSHA Tier 2 safety question — allow with mandatory referral suffix",
                # canned_response here is the referral suffix to APPEND to Gemini answer
                canned_response=SAFETY_REFERRAL_SUFFIX,
            )

        return GuardrailVerdict(
            action=Action.ALLOW,
            category="OSHA",
            reason="No OSHA signals detected",
        )
