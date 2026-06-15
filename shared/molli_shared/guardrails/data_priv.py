"""Data Privacy guardrail.

Mode A — Input scanning (pre-Gemini): detect PII in user messages.
Mode B — Output scanning (post-Gemini): detect PII in Gemini responses.

If entire message is PII → BLOCK.
If PII present alongside a valid question → REDACT.
Third-party PII requests (asking about someone else's data) → BLOCK.

DLP wrapper is used for redaction — regex is a fast pre-filter only.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from molli_shared.config import get_settings

from .base import Action, GuardrailVerdict
from .dlp import DLPScanner

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PII detection patterns — keyed by type (fast pre-filter only)
# ---------------------------------------------------------------------------

_PII_PATTERNS: dict[str, str] = {
    "SSN": r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
    "credit_card": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b",
    "bank_account": r"(?:account|acct|routing|bank|direct\s+deposit)\s*(?:number|#|num|no\.?)?\s*:?\s*(\d{8,17})|\b(\d{8,17})\b(?=.{0,50}(?:account|acct|routing|bank|deposit))",
    "drivers_license": r"\b[A-Z]{1,2}\d{3}[-\s]?\d{3}[-\s]?\d{3}\b",
    "passport": r"\b[A-Z]{1,2}\d{7,9}\b(?=.{0,30}\b(passport)\b)",
    "dob_with_name": r"\b(DOB|date of birth|born on|birthday)[:\s]+\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
    "medical_record": r"\bMRN[:\s]?\d{6,10}\b|\bmedical record (number|#)[:\s]?\d+\b",
}

# Patterns indicating a request about a third party's data (always BLOCK)
_THIRD_PARTY_PATTERNS: list[str] = [
    # Existing patterns
    r"\b(look up|find|show|pull|get|access|summarize).{0,40}\b(salary|ssn|social security|record|background|credit).{0,40}\bfor\b",
    r"\bapplicant.{0,30}(DOB|date of birth|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b",
    r"\bcan you (look up|find|tell me).{0,30}(john|jane|[A-Z][a-z]+)\b",

    # Account number + resident/tenant name requests
    r"\b(get to|access|find|pull up|look up|open).{0,40}\b(resident|tenant).{0,40}account\b",
    r"\bresident.{0,20}account.{0,20}number\b",
    r"\baccount (number|#|num).{0,30}\d{4,}\b",

    # Any message referencing a specific named person + account/record/data
    r"\b[A-Z][a-z]+\s[A-Z][a-z]+.{0,40}(account|record|ssn|salary|information|data|profile|number)\b",

    # Asking about a named person's anything
    r"\b(show|get|find|pull|access|open|look up).{0,30}[A-Z][a-z]+\s[A-Z][a-z]+\b",

    # Resident/tenant + any identifier
    r"\b(resident|tenant).{0,30}(account|number|record|ssn|dob|date of birth|profile)\b",

    # Someone else's personal details
    r"\b(his|her|their).{0,20}(account|ssn|salary|record|information|profile|number)\b",
]

CANNED_RESPONSE_REDACT = """Just a heads up — I noticed your message contained what looks like sensitive personal information (like a Social Security Number or account number). I've removed it before processing your question to keep your data safe.

For anything involving personal data or account details, please contact HR or IT directly rather than sharing it here."""

CANNED_RESPONSE_BLOCK = """I can't process that message because it appears to contain sensitive personal information. Please don't share SSNs, account numbers, or other personal data in chat.

If you need help with something involving personal data, contact HR (Sally Sousa) or IT (Adam Tomlinson) directly."""


def detect_pii(text: str) -> dict[str, list[str]]:
    """Return dict of {pii_type: [matched_values]} found in text."""
    found: dict[str, list[str]] = {}
    for pii_type, pattern in _PII_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            found[pii_type] = matches
    return found


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Redact PII using Google Cloud DLP. Falls back to regex if DLP unavailable."""
    try:
        settings = get_settings()
        scanner = DLPScanner(project_id=settings.gcp_project_id)
        result = scanner.scan(text)
        if result.scan_skipped:
            log.warning("DLP unavailable — falling back to regex redaction")
            return _regex_redact(text)
        counts = {t: 1 for t in result.found_types}
        return result.redacted_text, counts
    except Exception as exc:
        log.error("DLP redaction failed — falling back to regex. error=%s", exc)
        return _regex_redact(text)


def _regex_redact(text: str) -> tuple[str, dict[str, int]]:
    """Fallback regex-based redaction when DLP is unavailable."""
    redacted = text
    counts: dict[str, int] = {}
    for pii_type, pattern in _PII_PATTERNS.items():
        new_text, n = re.subn(
            pattern, f"[REDACTED:{pii_type}]", redacted, flags=re.IGNORECASE
        )
        if n:
            redacted = new_text
            counts[pii_type] = n
    return redacted, counts


def _is_third_party_request(text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in _THIRD_PARTY_PATTERNS)


def _is_entirely_pii(text: str, pii_found: dict[str, Any]) -> bool:
    """True if the message is essentially all PII with no real question."""
    if not pii_found:
        return False

    if "drivers_license" in pii_found or "passport" in pii_found:
        if re.search(
            r"\b(here'?s|here is|my).{0,30}(driver'?s license|passport|license number|DL number)\b",
            text,
            re.IGNORECASE,
        ):
            return True

    if "SSN" in pii_found:
        if re.search(
            r"\b(update|change|fix|correct|edit|modify|add|save|can you).{0,40}(my|the)\b.{0,40}(record|file|info|information|account|details)\b",
            text,
            re.IGNORECASE,
        ):
            return True
        if re.search(
            r"\bmy ssn is\b|\bssn:\s*\d|\bsocial security number is\b",
            text,
            re.IGNORECASE,
        ):
            return True

    redacted, _ = _regex_redact(text)
    remaining = re.sub(r"\[REDACTED:[A-Z_]+\]", "", redacted).strip()
    return len(re.sub(r"\s+", "", remaining)) < 10


class DataPrivacyGuardrail:
    name = "data_privacy"

    async def check(self, message: str, user_email: str) -> GuardrailVerdict:
        # Third-party data request → always BLOCK
        if _is_third_party_request(message):
            return GuardrailVerdict(
                action=Action.BLOCK,
                category="DATA_PRIVACY",
                reason="Third-party PII request detected | mode=input_scan",
                canned_response=CANNED_RESPONSE_BLOCK,
            )

        pii_found = detect_pii(message)

        if not pii_found:
            return GuardrailVerdict(
                action=Action.ALLOW,
                category="DATA_PRIVACY",
                reason="No PII detected",
            )

        pii_types = list(pii_found.keys())

        # Entire message is PII → BLOCK
        if _is_entirely_pii(message, pii_found):
            return GuardrailVerdict(
                action=Action.BLOCK,
                category="DATA_PRIVACY",
                reason=f"Message is entirely PII | types={pii_types} | mode=input_scan",
                canned_response=CANNED_RESPONSE_BLOCK,
            )

        # PII alongside a real question → REDACT via DLP
        return GuardrailVerdict(
            action=Action.REDACT,
            category="DATA_PRIVACY",
            reason=f"PII detected alongside valid question | types={pii_types} | mode=input_scan",
            canned_response=CANNED_RESPONSE_REDACT,
        )

    async def check_output(self, response: str) -> GuardrailVerdict:
        """Mode B — scan Gemini output before sending to user."""
        pii_found = detect_pii(response)
        if pii_found:
            return GuardrailVerdict(
                action=Action.REDACT,
                category="DATA_PRIVACY",
                reason=f"PII detected in Gemini output | types={list(pii_found.keys())} | mode=output_scan",
                canned_response=CANNED_RESPONSE_REDACT,
            )
        return GuardrailVerdict(
            action=Action.ALLOW,
            category="DATA_PRIVACY",
            reason="No PII in Gemini output",
        )
