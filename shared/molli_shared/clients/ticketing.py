"""TicketingProvider protocol and exception hierarchy.

The protocol is the abstraction the chat-service depends on. The Freshservice
implementation lives in ``freshservice.py``; the Autotask implementation
(Fall 2026) will live in ``autotask.py`` and implement the same protocol so
the swap is a one-line dependency-injection change at the chat-service
entrypoint.

Keep this protocol minimal. List groups, list agents, list ticket fields are
bootstrap-time concerns (query once to populate routing tables, not per chat
message). They belong on a separate admin-style client, not on the protocol
the chat-service uses on every escalation.
"""

from __future__ import annotations

from typing import Protocol

from molli_shared.schemas.ticket import (
    CreatedTicket,
    RequesterRecord,
    TicketCreatePayload,
)


class TicketingProvider(Protocol):
    """Abstracts over Freshservice (now) and Autotask (Fall 2026).

    Implementations may add additional methods, but the chat-service only
    depends on the two below. Adding methods to this protocol is a breaking
    change to the migration contract — discuss before doing it.
    """

    async def lookup_requester(self, email: str) -> RequesterRecord | None:
        """Find a requester by email. Returns ``None`` if no match."""
        ...

    async def create_ticket(self, payload: TicketCreatePayload) -> CreatedTicket:
        """Create a ticket. Raises ``TicketingError`` (or a subclass) on failure."""
        ...


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TicketingError(Exception):
    """Base exception for all ticketing-provider failures.

    The chat-service catches this and surfaces a user-friendly message;
    callers do not need to distinguish subclasses unless they want to.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class TicketingAuthError(TicketingError):
    """Authentication or authorization failure (401/403).

    Not retried. Usually indicates the API key is wrong, expired, or lacks
    the required scope. Operators should rotate the key.
    """


class TicketingValidationError(TicketingError):
    """The request shape was rejected by the provider (4xx other than 429).

    Not retried. Usually means a custom field has an invalid value, a
    required field was omitted, or an enum value isn't recognized. The
    ``response_body`` attribute holds the provider's error detail.
    """


class TicketingRateLimitError(TicketingError):
    """The provider rate-limited us and retries were exhausted (429).

    The client retries 429s with backoff; this exception only fires if the
    backoff budget runs out. Callers should surface a "try again in a minute"
    message to the user.
    """
