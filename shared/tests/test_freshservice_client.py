"""Tests for FreshserviceClient (mocked HTTP — no live API).

Uses pytest-httpx to mock httpx.AsyncClient transport. No test in this file
makes a real HTTP call.
"""

from __future__ import annotations

import pytest
from molli_shared.clients.freshservice import FreshserviceClient
from molli_shared.clients.ticketing import (
    TicketingAuthError,
    TicketingError,
    TicketingRateLimitError,
    TicketingValidationError,
)

BASE_URL = "https://test.freshservice.com/api/v2"


@pytest.fixture
def client():
    """Fresh client per test. Backoff is monkey-patched in retry tests
    that need fast execution; the default client is fine for everything else.
    """
    return FreshserviceClient(
        base_url=BASE_URL,
        api_key="test-api-key",
        max_retries=2,  # Lower than default to keep test runs quick
    )


@pytest.fixture
def fast_client(monkeypatch):
    """Client whose retry backoff is zeroed out so retry tests run fast."""
    monkeypatch.setattr(
        FreshserviceClient, "_backoff", classmethod(lambda cls, attempt: 0.0)
    )
    monkeypatch.setattr(
        FreshserviceClient,
        "_wait_for_retry_after",
        classmethod(lambda cls, response, attempt: 0.0),
    )
    return FreshserviceClient(
        base_url=BASE_URL,
        api_key="test-api-key",
        max_retries=2,
    )


# ---------------------------------------------------------------------------
# create_ticket — happy paths
# ---------------------------------------------------------------------------


class TestCreateTicketHappyPath:
    @pytest.mark.asyncio
    async def test_201_returns_parsed_ticket(
        self, httpx_mock, client, valid_payload, created_ticket_response
    ):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            json=created_ticket_response,
            status_code=201,
        )
        async with client:
            result = await client.create_ticket(valid_payload)
        assert result.id == 87040
        assert result.subject.startswith("[TEST-Molli]")

    @pytest.mark.asyncio
    async def test_request_body_serializes_correctly(
        self, httpx_mock, client, valid_payload, created_ticket_response
    ):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            json=created_ticket_response,
            status_code=201,
        )
        async with client:
            await client.create_ticket(valid_payload)

        # Inspect the request the client sent
        sent = httpx_mock.get_requests()[0]
        import json as _json

        body = _json.loads(sent.content)
        assert body["email"] == "molli.svc@preiss.com"
        assert body["source"] == 4  # Chat
        assert body["custom_fields"]["original_system"] == "Computer/Laptop"
        # None fields stripped
        assert "computer_name_if_it_issue" not in body["custom_fields"]

    @pytest.mark.asyncio
    async def test_basic_auth_header_set(
        self, httpx_mock, client, valid_payload, created_ticket_response
    ):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            json=created_ticket_response,
            status_code=201,
        )
        async with client:
            await client.create_ticket(valid_payload)

        sent = httpx_mock.get_requests()[0]
        assert sent.headers["Authorization"].startswith("Basic ")


# ---------------------------------------------------------------------------
# create_ticket — error paths
# ---------------------------------------------------------------------------


class TestCreateTicketErrors:
    @pytest.mark.asyncio
    async def test_400_validation_raises_no_retry(
        self, httpx_mock, client, valid_payload, validation_error_response
    ):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            json=validation_error_response,
            status_code=400,
        )
        async with client:
            with pytest.raises(TicketingValidationError) as exc_info:
                await client.create_ticket(valid_payload)
        assert exc_info.value.status_code == 400
        # Only one request — no retries on 4xx
        assert len(httpx_mock.get_requests()) == 1

    @pytest.mark.asyncio
    async def test_401_raises_auth_error_no_retry(
        self, httpx_mock, client, valid_payload
    ):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            status_code=401,
            json={"description": "Invalid credentials"},
        )
        async with client:
            with pytest.raises(TicketingAuthError):
                await client.create_ticket(valid_payload)
        assert len(httpx_mock.get_requests()) == 1

    @pytest.mark.asyncio
    async def test_403_raises_auth_error_no_retry(
        self, httpx_mock, client, valid_payload
    ):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            status_code=403,
        )
        async with client:
            with pytest.raises(TicketingAuthError):
                await client.create_ticket(valid_payload)
        assert len(httpx_mock.get_requests()) == 1


# ---------------------------------------------------------------------------
# Retry behavior
# ---------------------------------------------------------------------------


class TestRetries:
    @pytest.mark.asyncio
    async def test_429_then_201_succeeds(
        self, httpx_mock, fast_client, valid_payload, created_ticket_response
    ):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            status_code=429,
            headers={"Retry-After": "1"},
        )
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            json=created_ticket_response,
            status_code=201,
        )
        async with fast_client:
            result = await fast_client.create_ticket(valid_payload)
        assert result.id == 87040
        assert len(httpx_mock.get_requests()) == 2

    @pytest.mark.asyncio
    async def test_429_persistent_eventually_raises(
        self, httpx_mock, fast_client, valid_payload
    ):
        # max_retries=2 means 3 total attempts. Mock 3 429s.
        for _ in range(3):
            httpx_mock.add_response(
                method="POST",
                url=f"{BASE_URL}/tickets",
                status_code=429,
                headers={"Retry-After": "1"},
            )
        async with fast_client:
            with pytest.raises(TicketingRateLimitError):
                await fast_client.create_ticket(valid_payload)
        assert len(httpx_mock.get_requests()) == 3

    @pytest.mark.asyncio
    async def test_500_then_201_succeeds(
        self, httpx_mock, fast_client, valid_payload, created_ticket_response
    ):
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            status_code=500,
        )
        httpx_mock.add_response(
            method="POST",
            url=f"{BASE_URL}/tickets",
            json=created_ticket_response,
            status_code=201,
        )
        async with fast_client:
            result = await fast_client.create_ticket(valid_payload)
        assert result.id == 87040
        assert len(httpx_mock.get_requests()) == 2

    @pytest.mark.asyncio
    async def test_500_persistent_eventually_raises(
        self, httpx_mock, fast_client, valid_payload
    ):
        for _ in range(3):
            httpx_mock.add_response(
                method="POST",
                url=f"{BASE_URL}/tickets",
                status_code=500,
            )
        async with fast_client:
            with pytest.raises(TicketingError):
                await fast_client.create_ticket(valid_payload)
        assert len(httpx_mock.get_requests()) == 3


# ---------------------------------------------------------------------------
# lookup_requester
# ---------------------------------------------------------------------------


class TestLookupRequester:
    @pytest.mark.asyncio
    async def test_match_returns_record(self, httpx_mock, client, requester_response):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/requesters?email=user@preiss.com",
            json=requester_response,
            status_code=200,
        )
        async with client:
            result = await client.lookup_requester("user@preiss.com")
        assert result is not None
        assert result.id == 5000387689
        assert result.email == "user@preiss.com"

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self, httpx_mock, client):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/requesters?email=nobody@preiss.com",
            json={"requesters": []},
            status_code=200,
        )
        async with client:
            result = await client.lookup_requester("nobody@preiss.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_404_returns_none_or_raises(self, httpx_mock, client):
        """Some Freshservice plans return 404 for no-match; others return
        200 with empty list. We treat 404 as a terminal validation error."""
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/requesters?email=nobody@preiss.com",
            status_code=404,
        )
        async with client:
            with pytest.raises(TicketingValidationError):
                await client.lookup_requester("nobody@preiss.com")

    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self, httpx_mock, client):
        httpx_mock.add_response(
            method="GET",
            url=f"{BASE_URL}/requesters?email=user@preiss.com",
            status_code=401,
        )
        async with client:
            with pytest.raises(TicketingAuthError):
                await client.lookup_requester("user@preiss.com")
