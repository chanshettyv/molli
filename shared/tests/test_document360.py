"""Unit tests for the Document360 client.

All HTTP is mocked with respx, so these run in CI without a live API key.
Fixtures mirror the real shapes observed against Preiss Central, scrubbed of
author PII and signed CDN tokens.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from molli_shared.clients.document360 import (
    DEFAULT_BASE_URL,
    Document360Client,
    Document360Error,
)
from molli_shared.schemas.article import Article, ArticleStub

# ---------------------------------------------------------------------------
# Fixtures: canned API payloads (real shapes, scrubbed)
# ---------------------------------------------------------------------------

PROJECT_VERSIONS_PAYLOAD = {
    "data": [
        {
            "id": "5422b9ef-da52-4b25-82f2-0ebf5c0a3be5",
            "version_number": 1.0,
            "version_code_name": "PreissCentral",
            "is_main_version": True,
            "slug": "home",
            "language_versions": [
                {
                    "id": "bb7848ee-7baf-4d13-9f49-7e20ad41f4d6",
                    "name": "English",
                    "code": "en",
                    "set_as_default": True,
                    "hidden": False,
                }
            ],
        }
    ],
    "success": True,
    "errors": [],
}

VERSION_ID = "5422b9ef-da52-4b25-82f2-0ebf5c0a3be5"


def _stub(
    aid: str,
    title: str,
    *,
    status: int = 3,
    hidden: bool = False,
    modified_at: str = "2026-06-02T21:05:05.495Z",
    security_visibility: int = 1,
    content_type: int = 2,
) -> dict:
    return {
        "url": None,
        "exclude_from_external_search": False,
        "security_visibility": security_visibility,
        "id": aid,
        "title": title,
        "public_version": 1,
        "latest_version": 1,
        "language_code": "en",
        "hidden": hidden,
        "status": status,
        "order": 1,
        "slug": title.lower().replace(" ", "-"),
        "content_type": content_type,
        "translation_option": 0,
        "is_shared_article": False,
        "created_at": "0001-01-01T00:00:00",
        "modified_at": modified_at,
        "current_workflow_status_id": None,
    }


# A nested tree:
#   root category "General"
#     - published article (indexable)
#     - draft article (status 0 -> excluded)
#     - published-but-hidden article (excluded)
#   child category "IT"
#     - published article (indexable, recently modified)
CATEGORIES_PAYLOAD = {
    "data": [
        {
            "id": "cat-general",
            "name": "General",
            "order": 0,
            "hidden": False,
            "articles": [
                _stub(
                    "art-published",
                    "Central Documents List",
                    status=3,
                    modified_at="2026-06-02T21:05:05.495Z",
                ),
                _stub(
                    "art-draft",
                    "Benefits Resources",
                    status=0,
                    modified_at="2026-06-04T21:37:36.881Z",
                ),
                _stub(
                    "art-hidden",
                    "Known Issues",
                    status=3,
                    hidden=True,
                    modified_at="2024-01-03T12:53:07.664Z",
                ),
            ],
            "child_categories": [
                {
                    "id": "cat-it",
                    "name": "IT",
                    "order": 1,
                    "hidden": False,
                    "articles": [
                        _stub(
                            "art-vpn",
                            "Accessing the VPN",
                            status=3,
                            modified_at="2026-06-07T10:00:00.000Z",
                        ),
                    ],
                    "child_categories": [],
                }
            ],
        }
    ],
    "success": True,
    "errors": [],
}

ARTICLE_PAYLOAD = {
    "data": {
        "id": "art-published",
        "title": "Central Documents List",
        "content": "",
        "html_content": "<p>Other Document Pages: ...</p>",
        "category_id": "cat-general",
        "project_version_id": VERSION_ID,
        "public_version": 83,
        "latest_version": 83,
        "hidden": False,
        "status": 3,
        "content_type": 2,
        "security_visibility": 1,
        "modified_at": "2026-06-02T21:05:05.495Z",
        "slug": "central-documents-list",
        "description": "Repository of commonly-used documents.",
        "url": "https://preisscentral.com/docs/en/central-documents-list",
        # PII fields that must be ignored by the model:
        "authors": [
            {"first_name": "Jane", "last_name": "Doe", "email_id": "jane@x.com"}
        ],
        "created_by": "6a3a52d0-52dd-4b33-bf9a-d9bac1aea06f",
        "custom_fields": [],
    },
    "success": True,
    "errors": [],
}

FAILURE_PAYLOAD = {
    "data": None,
    "success": False,
    "errors": [{"description": "The url field is required."}],
}


def _make_client() -> Document360Client:
    return Document360Client("fake-test-key")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_get_project_versions_parses_and_sets_language():
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions").mock(
        return_value=httpx.Response(200, json=PROJECT_VERSIONS_PAYLOAD)
    )
    async with _make_client() as client:
        versions = await client.get_project_versions()

    assert len(versions) == 1
    v = versions[0]
    assert v.id == VERSION_ID
    assert v.is_main_version is True
    assert v.default_language_code == "en"


@respx.mock
@pytest.mark.asyncio
async def test_auth_header_is_api_token_not_bearer():
    route = respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions").mock(
        return_value=httpx.Response(200, json=PROJECT_VERSIONS_PAYLOAD)
    )
    async with _make_client() as client:
        await client.get_project_versions()

    request = route.calls.last.request
    assert request.headers.get("api_token") == "fake-test-key"
    assert "authorization" not in {k.lower() for k in request.headers}


@respx.mock
@pytest.mark.asyncio
async def test_list_articles_walks_nested_tree_and_filters_indexable():
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions").mock(
        return_value=httpx.Response(200, json=PROJECT_VERSIONS_PAYLOAD)
    )
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions/{VERSION_ID}/categories").mock(
        return_value=httpx.Response(200, json=CATEGORIES_PAYLOAD)
    )
    async with _make_client() as client:
        stubs = await client.list_articles()

    ids = {s.id for s in stubs}
    # published root article + published nested IT article
    assert ids == {"art-published", "art-vpn"}
    # draft (status 0) and hidden are excluded
    assert "art-draft" not in ids
    assert "art-hidden" not in ids


@respx.mock
@pytest.mark.asyncio
async def test_list_articles_tags_category_id_during_walk():
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions").mock(
        return_value=httpx.Response(200, json=PROJECT_VERSIONS_PAYLOAD)
    )
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions/{VERSION_ID}/categories").mock(
        return_value=httpx.Response(200, json=CATEGORIES_PAYLOAD)
    )
    async with _make_client() as client:
        stubs = await client.list_articles()

    by_id = {s.id: s for s in stubs}
    assert by_id["art-published"].category_id == "cat-general"
    assert by_id["art-vpn"].category_id == "cat-it"


@respx.mock
@pytest.mark.asyncio
async def test_list_articles_includes_drafts_when_not_indexable_only():
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions").mock(
        return_value=httpx.Response(200, json=PROJECT_VERSIONS_PAYLOAD)
    )
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions/{VERSION_ID}/categories").mock(
        return_value=httpx.Response(200, json=CATEGORIES_PAYLOAD)
    )
    async with _make_client() as client:
        stubs = await client.list_articles(indexable_only=False)

    assert {s.id for s in stubs} == {
        "art-published",
        "art-draft",
        "art-hidden",
        "art-vpn",
    }


@respx.mock
@pytest.mark.asyncio
async def test_list_articles_modified_since_filters_client_side():
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions").mock(
        return_value=httpx.Response(200, json=PROJECT_VERSIONS_PAYLOAD)
    )
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions/{VERSION_ID}/categories").mock(
        return_value=httpx.Response(200, json=CATEGORIES_PAYLOAD)
    )
    # Watermark between the two indexable articles:
    #   art-published @ 2026-06-02, art-vpn @ 2026-06-07
    watermark = datetime(2026, 6, 5, tzinfo=UTC)
    async with _make_client() as client:
        stubs = await client.list_articles(modified_since=watermark)

    assert {s.id for s in stubs} == {"art-vpn"}


@respx.mock
@pytest.mark.asyncio
async def test_get_article_uses_lang_code_path_and_ignores_pii():
    route = respx.get(f"{DEFAULT_BASE_URL}/Articles/art-published/en").mock(
        return_value=httpx.Response(200, json=ARTICLE_PAYLOAD)
    )
    async with _make_client() as client:
        article = await client.get_article("art-published", "en")

    assert route.called
    assert isinstance(article, Article)
    assert article.url == "https://preisscentral.com/docs/en/central-documents-list"
    assert article.body == "<p>Other Document Pages: ...</p>"
    assert article.is_indexable is True
    # PII fields are dropped by the model (extra="ignore")
    assert not hasattr(article, "authors")
    assert not hasattr(article, "created_by")


@respx.mock
@pytest.mark.asyncio
async def test_get_articles_fans_out_with_lang_codes():
    respx.get(f"{DEFAULT_BASE_URL}/Articles/art-published/en").mock(
        return_value=httpx.Response(200, json=ARTICLE_PAYLOAD)
    )
    vpn_payload = {
        "data": {**ARTICLE_PAYLOAD["data"], "id": "art-vpn", "title": "VPN"},
        "success": True,
        "errors": [],
    }
    respx.get(f"{DEFAULT_BASE_URL}/Articles/art-vpn/en").mock(
        return_value=httpx.Response(200, json=vpn_payload)
    )
    async with _make_client() as client:
        articles = await client.get_articles(
            [("art-published", "en"), ("art-vpn", "en")]
        )

    assert {a.id for a in articles} == {"art-published", "art-vpn"}


@respx.mock
@pytest.mark.asyncio
async def test_success_false_envelope_raises():
    respx.get(f"{DEFAULT_BASE_URL}/Articles/bad/en").mock(
        return_value=httpx.Response(200, json=FAILURE_PAYLOAD)
    )
    async with _make_client() as client:
        with pytest.raises(Document360Error, match="success=false"):
            await client.get_article("bad", "en")


@respx.mock
@pytest.mark.asyncio
async def test_401_raises_with_helpful_message():
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions").mock(
        return_value=httpx.Response(401, json={"message": "nope"})
    )
    async with _make_client() as client:
        with pytest.raises(Document360Error, match="api_token"):
            await client.get_project_versions()


@respx.mock
@pytest.mark.asyncio
async def test_429_then_success_is_retried(monkeypatch):
    # Don't actually sleep through the backoff.
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("molli_shared.clients.document360.asyncio.sleep", _no_sleep)
    route = respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "1"}, json={}),
        httpx.Response(200, json=PROJECT_VERSIONS_PAYLOAD),
    ]
    async with _make_client() as client:
        versions = await client.get_project_versions()

    assert len(versions) == 1
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_5xx_exhausts_retries_and_raises(monkeypatch):
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("molli_shared.clients.document360.asyncio.sleep", _no_sleep)
    respx.get(f"{DEFAULT_BASE_URL}/ProjectVersions").mock(
        return_value=httpx.Response(503, json={})
    )
    async with _make_client() as client:
        with pytest.raises(Document360Error, match="after .* retries"):
            await client.get_project_versions()


def test_article_stub_indexable_logic():
    base = {
        "id": "x",
        "title": "t",
        "modified_at": "2026-01-01T00:00:00Z",
    }
    assert ArticleStub.model_validate({**base, "status": 3}).is_indexable is True
    assert ArticleStub.model_validate({**base, "status": 0}).is_indexable is False
    assert (
        ArticleStub.model_validate({**base, "status": 3, "hidden": True}).is_indexable
        is False
    )
