"""In-memory mock implementing TicketingProvider for local dev and tests.

No network, no secrets, no Freshservice tenant required. Returns a synthetic
CreatedTicket so the chat-service dialog flow can be exercised end-to-end
before the real Freshservice credentials/fields are wired.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from molli_shared.schemas.ticket import (
    CreatedTicket,
    RequesterRecord,
    TicketCreatePayload,
)

logger = logging.getLogger(__name__)


class MockTicketingProvider:
    """Satisfies the TicketingProvider protocol without any external calls."""

    def __init__(self) -> None:
        self._counter = 1041

    async def lookup_requester(self, email: str) -> RequesterRecord | None:
        # Pretend everyone exists; echo the email back as a requester.
        return RequesterRecord(id=1, primary_email=email)

    async def create_ticket(self, payload: TicketCreatePayload) -> CreatedTicket:
        self._counter += 1
        logger.info(
            "MOCK ticket %s: %s", self._counter, payload.model_dump(exclude_none=True)
        )
        return CreatedTicket(
            id=self._counter,
            subject=payload.subject,
            status=payload.status,
            priority=payload.priority,
            group_id=payload.group_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
