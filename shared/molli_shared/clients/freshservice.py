"""Freshservice ticketing client.

Implements the `TicketingProvider` protocol so it can be swapped for Autotask
in Fall 2026 without touching call sites.

API docs: https://api.freshservice.com/
"""

from __future__ import annotations

from typing import Protocol

import httpx
from pydantic import BaseModel


class TicketRequest(BaseModel):
    requester_email: str
    subject: str
    description: str
    priority: int = 2  # 1=Low, 2=Medium, 3=High, 4=Urgent
    category: str | None = None
    sub_category: str | None = None
    group_id: int | None = None


class TicketResponse(BaseModel):
    ticket_id: int
    url: str


class TicketingProvider(Protocol):
    async def create_ticket(self, req: TicketRequest) -> TicketResponse: ...


class FreshserviceClient:
    def __init__(self, api_key: str, domain: str) -> None:
        self._domain = domain
        self._client = httpx.AsyncClient(
            base_url=f"https://{domain}.freshservice.com/api/v2",
            auth=(api_key, "X"),
            timeout=30.0,
        )

    async def create_ticket(self, req: TicketRequest) -> TicketResponse:
        """Create a ticket. Phase 3 implementation."""
        raise NotImplementedError("Phase 3")

    async def aclose(self) -> None:
        await self._client.aclose()
