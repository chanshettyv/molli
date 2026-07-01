"""Conversation-aware ticket field extraction for smarter Freshservice pre-fill.

When the user clicks "Create Ticket", this module analyses the full conversation
history to produce a TicketAnalysis: a professional summary, inferred routing
fields, and targeted follow-up questions for any required fields that cannot be
reasonably extracted.

Conventions mirror query_rewrite.py / topic_detection.py exactly:
- Synchronous _call_gemini() run inside asyncio.to_thread()
- asyncio.wait_for timeout (8 s — richer work than rewrite/detection)
- Fail-safe: _fallback() on any error; never raises, never blocks

Vocabulary snapping (mapping free-text Gemini output to exact SYSTEM_ITEMS /
LOCATIONS strings) uses stdlib difflib — no new dependencies. The snap helpers
accept the vocabulary as a plain list[str] argument so this module has zero
dependency on chat-service's form_options.py.
"""

from __future__ import annotations

import asyncio
import difflib
import json
from dataclasses import dataclass, field

import structlog
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

from molli_shared.config import get_settings
from molli_shared.conversation_store import ConversationStore, Turn

log = structlog.get_logger()

_ANALYSIS_TIMEOUT = 8.0

VALID_GROUP_LABELS = {"IT", "HR", "Ops", "general"}

_SYSTEM_PROMPT = """\
You are a ticket-drafting assistant for The Preiss Company's internal helpdesk.
You are given a conversation between an employee and Molli (Preiss's AI assistant)
that ended without a knowledge-base answer. Extract structured Freshservice ticket
fields from that conversation so the employee can submit a ticket with minimal effort.

Output ONLY a single JSON object — no markdown fences, no prose before or after.

JSON schema:
{
  "subject": "<concise ticket title, ≤80 chars, imperative or noun-phrase>",
  "description": "<2–4 sentences summarising the issue professionally. Write in third-person: 'The user reports…'. Do NOT quote raw chat messages. Cover: what the problem is, which system or process is affected, any scope or urgency context.>",
  "group_label": "<one of: IT | HR | Ops | general>",
  "system_raw": "<software, hardware, or system most relevant to this issue; free text; null if genuinely unclear>",
  "locations_raw": ["<property or office name if mentioned>"],
  "priority": <integer: 1=Low | 2=Medium | 3=High | 4=Urgent>,
  "computer_name": "<computer hostname if explicitly stated; otherwise null>",
  "follow_up_questions": ["<question 1>", "<question 2>"]
}

Rules:
1. subject: derive a concise title from the conversation. Max 80 chars.
2. description: 2–4 sentences. Third-person professional tone. No raw chat lines.
3. group_label — use these definitions:
   IT  = technology: Google/Gmail/Drive, passwords, login, printers, VPN, hardware,
         software, distribution lists, computer problems, network, Windows
   HR  = people: benefits, PTO, payroll, onboarding, conduct, compensation, hiring
   Ops = property operations: Entrata, resident portals, leases, ledgers, move-ins/outs,
         property settings, utilities, rent collection, property management systems
   general = anything that does not clearly fit IT, HR, or Ops
4. system_raw: name the specific app, software, or hardware involved.
   Examples: "Entrata", "Gmail", "Printer", "Windows", "Google Drive", "Laptop".
   Use null only if the issue has no clear system anchor (e.g. a pure policy question).
5. locations_raw: list only property or office names the user explicitly mentioned.
   Use the name as the user stated it. Do NOT invent locations. Empty list [] if none.
6. priority:
   1 (Low)    = minor inconvenience, work continues normally
   2 (Medium) = default; typical issue with no time pressure
   3 (High)   = work is blocked or significantly impaired
   4 (Urgent) = system-wide outage, payroll deadline, legal/safety risk, all staff affected
   Default to 2 unless the conversation contains clear urgency signals such as
   "can't work", "payroll is tomorrow", "all staff affected", "emergency", "urgent".
7. computer_name: set only when the user explicitly stated a hostname or asset tag
   (e.g. "LAPTOP-LB-014"). Do not infer or guess it.
8. follow_up_questions: generate at most 3 questions, only for required fields
   that CANNOT be reasonably inferred from the conversation. Prioritise:
   - group/department if truly ambiguous
   - which system or application is involved
   - which property or office location is affected
   Do NOT ask for information already present in the conversation.
   If all required fields can be inferred, return an empty list [].
   Write questions in friendly, direct language addressed to the user.
"""

_USER_TEMPLATE = (
    "Conversation transcript:\n{transcript}\n\n"
    "Original question that triggered the ticket button: {question}\n\n"
    "Extract ticket fields as instructed."
)


@dataclass
class TicketAnalysis:
    subject: str
    description: str
    group_label: str  # "IT" | "HR" | "Ops" | "general"
    system_raw: str | None  # free text; caller snaps to SYSTEM_ITEMS
    locations_raw: list[str]  # free text list; caller snaps to LOCATIONS
    priority: int  # 1–4
    computer_name: str | None
    follow_up_questions: list[str] = field(default_factory=list)
    is_complete: bool = False  # True iff follow_up_questions is empty


# ---------------------------------------------------------------------------
# Vocabulary snap helpers (no form_options dependency — vocabulary injected)
# ---------------------------------------------------------------------------


def snap_to_vocabulary(
    raw: str, vocabulary: list[str], cutoff: float = 0.55
) -> str | None:
    """Return the closest match in vocabulary, or None if below cutoff.

    Uses difflib.get_close_matches (stdlib SequenceMatcher). Performs a
    case-insensitive comparison by lower-casing both sides before matching,
    then returns the original-case vocabulary item.
    """
    if not raw or not raw.strip():
        return None
    raw_lower = raw.strip().lower()
    vocab_lower = [v.lower() for v in vocabulary]
    matches = difflib.get_close_matches(raw_lower, vocab_lower, n=1, cutoff=cutoff)
    if not matches:
        return None
    idx = vocab_lower.index(matches[0])
    return vocabulary[idx]


def snap_list_to_vocabulary(
    raw_values: list[str], vocabulary: list[str], cutoff: float = 0.55
) -> list[str]:
    """Snap each item in raw_values to the vocabulary; drop items that don't match."""
    result = []
    for raw in raw_values:
        snapped = snap_to_vocabulary(raw, vocabulary, cutoff)
        if snapped and snapped not in result:
            result.append(snapped)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _derive_subject(user_question: str, max_len: int = 80) -> str:
    q = user_question.strip().rstrip("?").strip()
    if len(q) <= max_len:
        return q
    return q[:max_len].rsplit(" ", 1)[0] + "..."


def _generic_description(user_question: str) -> str:
    q = user_question.strip()[:300]
    return (
        "The user reports an issue they were unable to resolve through Preiss Central. "
        f'Original question: "{q}". '
        "Additional context may be available in the conversation history."
    )


def _fallback(user_question: str) -> TicketAnalysis:
    """Returned when Gemini is unavailable or the response cannot be parsed."""
    return TicketAnalysis(
        subject=_derive_subject(user_question),
        description=_generic_description(user_question),
        group_label="general",
        system_raw=None,
        locations_raw=[],
        priority=2,
        computer_name=None,
        follow_up_questions=[
            "Is this an IT, HR, or Operations issue?",
            "Which system or application are you having trouble with?",
            "Which property or office location does this affect?",
        ],
        is_complete=False,
    )


def _parse(raw: str, user_question: str) -> TicketAnalysis:
    """Parse Gemini JSON output into a TicketAnalysis, falling back gracefully."""
    text = raw.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        log.warning("ticket_analysis_parse_failed", raw_snippet=raw[:300])
        return _fallback(user_question)

    subject = str(data.get("subject", "")).strip() or _derive_subject(user_question)
    description = str(data.get("description", "")).strip() or _generic_description(
        user_question
    )

    group_label = str(data.get("group_label", "general")).strip()
    if group_label not in VALID_GROUP_LABELS:
        group_label = "general"

    system_raw_val = data.get("system_raw")
    system_raw = str(system_raw_val).strip() if system_raw_val else None

    raw_locs = data.get("locations_raw", [])
    locations_raw = (
        [str(loc).strip() for loc in raw_locs if loc]
        if isinstance(raw_locs, list)
        else []
    )

    try:
        priority = int(data.get("priority", 2))
        if priority not in (1, 2, 3, 4):
            priority = 2
    except (ValueError, TypeError):
        priority = 2

    cn_val = data.get("computer_name")
    computer_name = str(cn_val).strip() if cn_val else None

    raw_qs = data.get("follow_up_questions", [])
    follow_up_questions = (
        [str(q).strip() for q in raw_qs if q][:3] if isinstance(raw_qs, list) else []
    )

    return TicketAnalysis(
        subject=subject,
        description=description,
        group_label=group_label,
        system_raw=system_raw,
        locations_raw=locations_raw,
        priority=priority,
        computer_name=computer_name,
        follow_up_questions=follow_up_questions,
        is_complete=len(follow_up_questions) == 0,
    )


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------


def _call_gemini(
    project_id: str, region: str, model_name: str, transcript: str, question: str
) -> str:
    """Synchronous Gemini call — runs inside asyncio.to_thread."""
    vertexai.init(project=project_id, location=region)
    model = GenerativeModel(model_name=model_name, system_instruction=_SYSTEM_PROMPT)
    response = model.generate_content(
        _USER_TEMPLATE.format(transcript=transcript, question=question),
        generation_config=GenerationConfig(temperature=0.0),
    )
    return (response.text or "").strip()


async def analyze_for_ticket(
    history: list[Turn],
    user_question: str,
) -> TicketAnalysis:
    """Analyse conversation history and extract ticket fields. Fail-safe to _fallback.

    Returns _fallback() (is_complete=False, 3 generic questions) when Gemini
    is unavailable, times out, or returns unparseable output. Never raises.
    """
    if not user_question or not user_question.strip():
        return _fallback("(no question provided)")

    transcript = ConversationStore.as_transcript(history) if history else ""

    try:
        settings = get_settings()
    except Exception:
        return _fallback(user_question)

    if not settings.use_gemini:
        return _fallback(user_question)

    try:
        raw = await asyncio.wait_for(
            asyncio.to_thread(
                _call_gemini,
                settings.gcp_project_id,
                settings.gcp_region,
                settings.gemini_model,
                transcript,
                user_question,
            ),
            timeout=_ANALYSIS_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning("ticket_analysis_timeout", question_len=len(user_question))
        return _fallback(user_question)
    except Exception as exc:  # noqa: BLE001
        log.error("ticket_analysis_error", error=str(exc))
        return _fallback(user_question)

    result = _parse(raw, user_question)
    log.info(
        "ticket_analysis_complete",
        group=result.group_label,
        is_complete=result.is_complete,
        follow_up_count=len(result.follow_up_questions),
        system_raw=result.system_raw,
    )
    return result
