"""FHA semantic fallback classifier.

Runs as a guardrail AFTER the regex-based FairHousingGuardrail. Only reached
when a message passes the regex check but may still semantically touch FHA
territory — paraphrased or indirect phrasing the patterns cannot match.

FCRA (screening) questions are intentionally allowed through to the normal
RAG pipeline. If Document360 has screening policy docs, Molli will answer
from them; if not, it returns the standard no-context response.

Calls Gemini at temperature-0 with a compact classification prompt and
parses a single-token response: FHA | NONE.

Fail-open:  any error or timeout returns ALLOW so normal Molli traffic is
            never disrupted by a classifier outage.
Skipped:    when settings.use_gemini is False (local / CI without GCP creds).
"""

from __future__ import annotations

import asyncio

import structlog
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

from molli_shared.config import get_settings

from .base import Action, GuardrailVerdict
from .fair_housing import CANNED_RESPONSE as _FHA_CANNED

log = structlog.get_logger()

_CLASSIFY_TIMEOUT = 2.0  # seconds; fail-open on breach

_SYSTEM_PROMPT = (
    "You are a compliance classifier for a property management company's "
    "internal assistant. Respond with exactly one token — no punctuation, "
    "no explanation.\n"
    "\n"
    "Reply FHA  if the message touches Fair Housing Act topics: race, "
    "religion, color, national origin, sex, gender identity, sexual "
    "orientation, familial status, disability, or protected classes.\n"
    "\n"
    "Reply NONE for: tenant screening policies, background checks, credit "
    "requirements, income thresholds, criminal history screening, FCRA, "
    "adverse action letters, state screening laws, or anything else."
)

_USER_PROMPT = "Message: {message}"

_VALID_TOPICS = {"FHA", "NONE"}


def _call_gemini(project_id: str, region: str, model_name: str, text: str) -> str:
    """Synchronous Gemini call — runs inside asyncio.to_thread.

    Isolated as a named function so tests can patch it directly without
    touching the async plumbing.
    """
    vertexai.init(project=project_id, location=region)
    model = GenerativeModel(
        model_name=model_name,
        system_instruction=_SYSTEM_PROMPT,
    )
    response = model.generate_content(
        _USER_PROMPT.format(message=text),
        generation_config=GenerationConfig(temperature=0.0),
    )
    return (response.text or "").strip().upper()


async def _classify(text: str) -> str:
    """Return 'FHA' or 'NONE'.  Fails open on any error or timeout."""
    try:
        settings = get_settings()
    except Exception:
        return "NONE"  # no GCP env vars — fail-open

    if not settings.use_gemini:
        return "NONE"

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                _call_gemini,
                settings.gcp_project_id,
                settings.gcp_region,
                settings.gemini_model,
                text,
            ),
            timeout=_CLASSIFY_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning("fha_classifier_timeout", text_len=len(text))
        return "NONE"
    except Exception as exc:  # noqa: BLE001
        log.error("fha_classifier_error", error=str(exc))
        return "NONE"

    return result if result in _VALID_TOPICS else "NONE"


class FHAFCRAClassifier:
    name = "fha_llm"

    async def check(self, message: str, user_email: str) -> GuardrailVerdict:
        topic = await _classify(message)

        if topic == "FHA":
            return GuardrailVerdict(
                action=Action.BLOCK,
                category="FAIR_HOUSING",
                reason="LLM classifier: FHA topic detected (regex miss)",
                canned_response=_FHA_CANNED,
            )
        return GuardrailVerdict(
            action=Action.ALLOW,
            category="FHA_LLM",
            reason="LLM classifier: no FHA topic detected",
        )
