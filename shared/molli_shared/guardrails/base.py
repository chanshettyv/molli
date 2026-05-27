"""Guardrail layer.

Six categories from the kickoff deck:
- Mental health: detect distress, escalate to EAP, never give clinical advice
- Fair Housing (FHA): refuse questions about tenant screening on protected classes
- FCRA: no background check / credit guidance without HR authorization
- OSHA / Safety: urgent safety -> immediate escalation
- Escalation: 3-tier (answer -> ticket -> human handoff)
- Data Privacy: DLP-scan inputs, no PII in chat logs

Each guardrail is a callable that inspects an inbound message and returns a
GuardrailVerdict. The chain runs all of them; any block stops the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Action(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"          # refuse, return canned response
    ESCALATE = "escalate"    # answer + immediate human handoff
    REDACT = "redact"        # allow but strip flagged content first


@dataclass(frozen=True)
class GuardrailVerdict:
    action: Action
    category: str
    reason: str
    canned_response: str | None = None


class Guardrail(Protocol):
    name: str

    async def check(self, message: str, user_email: str) -> GuardrailVerdict: ...


# Concrete guardrails live in sibling modules:
#   mental_health.py, fair_housing.py, fcra.py, osha.py, data_privacy.py
# Each implements `Guardrail` and is added to GUARDRAIL_CHAIN below.

GUARDRAIL_CHAIN: list[Guardrail] = []  # populated in Phase 2
