"""
Unit tests for molli_shared.guardrails.dlp.DLPScanner.

All Google Cloud DLP calls are mocked — no live GCP project needed.
Run with: uv run pytest shared/tests/test_dlp.py -v
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Stub out google.cloud.dlp_v2 before any import of our module.
# This lets the lazy-load inside _call_dlp succeed with a mock object.
# ---------------------------------------------------------------------------
def _make_dlp_stub():
    google = ModuleType("google")
    google_cloud = ModuleType("google.cloud")
    dlp_v2 = ModuleType("google.cloud.dlp_v2")
    dlp_v2.DlpServiceClient = MagicMock  # type: ignore[attr-defined]
    google.cloud = google_cloud  # type: ignore[attr-defined]
    google_cloud.dlp_v2 = dlp_v2  # type: ignore[attr-defined]
    sys.modules.setdefault("google", google)
    sys.modules["google.cloud"] = google_cloud
    sys.modules["google.cloud.dlp_v2"] = dlp_v2
    return dlp_v2


_dlp_stub = _make_dlp_stub()

from molli_shared.guardrails.dlp import (  # noqa: E402 — must come after stub
    DEFAULT_INFO_TYPES,
    DLPResult,
    DLPScanner,
)


# ---------------------------------------------------------------------------
# Helpers to build mock DLP responses
# ---------------------------------------------------------------------------


def _mock_dlp_response(
    original: str, redacted: str, found_types: list[str]
) -> MagicMock:
    response = MagicMock()
    response.item.value = redacted

    summaries = []
    for name in found_types:
        summary = MagicMock()
        summary.info_type.name = name
        summaries.append(summary)

    response.overview.transformed_bytes = (
        len(original) - len(redacted) if redacted != original else 0
    )
    response.overview.transformation_summaries = summaries
    return response


def _scanner_with_mock_client(mock_response):
    """Return (scanner, mock_client) with deidentify_content pre-configured."""
    scanner = DLPScanner(project_id="molli-dev")
    mock_client = MagicMock()
    mock_client.deidentify_content.return_value = mock_response
    scanner._client = mock_client  # bypass lazy-load
    return scanner, mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDLPScannerNoChange:
    def test_clean_message_unchanged(self):
        clean_text = "How do I connect to the office printer?"
        scanner, _ = _scanner_with_mock_client(
            _mock_dlp_response(clean_text, clean_text, [])
        )
        result = scanner.scan(clean_text)
        assert result.redacted_text == clean_text
        assert result.has_pii is False
        assert result.found_types == []
        assert result.scan_skipped is False

    def test_empty_string_skips_dlp(self):
        scanner = DLPScanner(project_id="molli-dev")
        mock_client = MagicMock()
        scanner._client = mock_client
        result = scanner.scan("")
        mock_client.deidentify_content.assert_not_called()
        assert result.redacted_text == ""
        assert result.has_pii is False

    def test_whitespace_only_skips_dlp(self):
        scanner = DLPScanner(project_id="molli-dev")
        mock_client = MagicMock()
        scanner._client = mock_client
        result = scanner.scan("   \n\t  ")
        mock_client.deidentify_content.assert_not_called()
        assert result.has_pii is False


class TestDLPScannerRedaction:
    def test_email_redacted(self):
        original = "Please email me at alice@preiss.com for details."
        redacted = "Please email me at [REDACTED] for details."
        scanner, _ = _scanner_with_mock_client(
            _mock_dlp_response(original, redacted, ["EMAIL_ADDRESS"])
        )
        result = scanner.scan(original)
        assert result.redacted_text == redacted
        assert result.has_pii is True
        assert "EMAIL_ADDRESS" in result.found_types

    def test_ssn_redacted(self):
        original = "My SSN is 123-45-6789."
        redacted = "My SSN is [REDACTED]."
        scanner, _ = _scanner_with_mock_client(
            _mock_dlp_response(original, redacted, ["US_SOCIAL_SECURITY_NUMBER"])
        )
        result = scanner.scan(original)
        assert result.has_pii is True
        assert "US_SOCIAL_SECURITY_NUMBER" in result.found_types
        assert "[REDACTED]" in result.redacted_text

    def test_multiple_pii_types(self):
        original = "Call me at 555-867-5309 or email bob@preiss.com."
        redacted = "Call me at [REDACTED] or email [REDACTED]."
        scanner, _ = _scanner_with_mock_client(
            _mock_dlp_response(original, redacted, ["PHONE_NUMBER", "EMAIL_ADDRESS"])
        )
        result = scanner.scan(original)
        assert result.has_pii is True
        assert set(result.found_types) == {"PHONE_NUMBER", "EMAIL_ADDRESS"}
        assert result.redacted_text.count("[REDACTED]") == 2

    def test_credit_card_redacted(self):
        original = "Card number 4111 1111 1111 1111"
        redacted = "Card number [REDACTED]"
        scanner, _ = _scanner_with_mock_client(
            _mock_dlp_response(original, redacted, ["CREDIT_CARD_NUMBER"])
        )
        result = scanner.scan(original)
        assert result.has_pii is True
        assert "CREDIT_CARD_NUMBER" in result.found_types


class TestDLPScannerFailOpen:
    def test_dlp_exception_returns_original_text(self):
        scanner = DLPScanner(project_id="molli-dev")
        mock_client = MagicMock()
        mock_client.deidentify_content.side_effect = Exception("Connection refused")
        scanner._client = mock_client

        text = "My email is alice@preiss.com"
        result = scanner.scan(text)

        assert result.scan_skipped is True
        assert result.skip_reason is not None
        assert "Connection refused" in result.skip_reason
        assert result.redacted_text == text  # fail open
        assert result.has_pii is False

    def test_dlp_api_error_does_not_raise(self):
        scanner = DLPScanner(project_id="molli-dev")
        mock_client = MagicMock()
        mock_client.deidentify_content.side_effect = RuntimeError("DLP quota exceeded")
        scanner._client = mock_client

        result = scanner.scan("Some text with info@preiss.com in it")

        assert result.scan_skipped is True
        assert result.skip_reason is not None
        assert "quota exceeded" in result.skip_reason


class TestDLPScannerConfig:
    def test_default_info_types_coverage(self):
        required = {
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "US_SOCIAL_SECURITY_NUMBER",
            "CREDIT_CARD_NUMBER",
            "PERSON_NAME",
        }
        assert required.issubset(set(DEFAULT_INFO_TYPES))

    def test_custom_info_types_passed_to_api(self):
        text = "hello@example.com"
        scanner = DLPScanner(project_id="molli-dev", info_types=["EMAIL_ADDRESS"])
        mock_client = MagicMock()
        mock_client.deidentify_content.return_value = _mock_dlp_response(
            text, "[REDACTED]", ["EMAIL_ADDRESS"]
        )
        scanner._client = mock_client
        scanner.scan(text)

        request = mock_client.deidentify_content.call_args[1]["request"]
        assert request["inspect_config"]["info_types"] == [{"name": "EMAIL_ADDRESS"}]

    def test_include_quote_is_false(self):
        text = "test@example.com"
        scanner, mock_client = _scanner_with_mock_client(
            _mock_dlp_response(text, "[REDACTED]", ["EMAIL_ADDRESS"])
        )
        scanner.scan(text)

        request = mock_client.deidentify_content.call_args[1]["request"]
        assert request["inspect_config"]["include_quote"] is False

    def test_redact_placeholder_is_REDACTED(self):
        text = "555-867-5309"
        scanner, mock_client = _scanner_with_mock_client(
            _mock_dlp_response(text, "[REDACTED]", ["PHONE_NUMBER"])
        )
        scanner.scan(text)

        request = mock_client.deidentify_content.call_args[1]["request"]
        replacement = request["deidentify_config"]["info_type_transformations"][
            "transformations"
        ][0]["primitive_transformation"]["replace_config"]["new_value"]["string_value"]
        assert replacement == "[REDACTED]"


class TestDLPResult:
    def test_result_defaults(self):
        r = DLPResult(original_text="hi", redacted_text="hi")
        assert r.found_types == []
        assert r.has_pii is False
        assert r.scan_skipped is False
        assert r.skip_reason is None

    def test_result_with_pii(self):
        r = DLPResult(
            original_text="foo@bar.com",
            redacted_text="[REDACTED]",
            found_types=["EMAIL_ADDRESS"],
            has_pii=True,
        )
        assert r.has_pii is True
        assert "EMAIL_ADDRESS" in r.found_types
