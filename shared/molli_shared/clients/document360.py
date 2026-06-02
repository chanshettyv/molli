"""Document360 API client.

Phase 1 implementation: enumerate categories, list articles, fetch full
article content, and support incremental sync via a stored modified-at
watermark.

API docs: https://apidocs.document360.io/

Design notes
------------
The exploration spike (scripts/explore_d360.py, docs/spikes/document360-api.md)
confirmed the following about the live API. Reconcile any of these against your
own tmp/d360/*.json dumps if they differ on your instance:

- Auth is a custom header: ``api_token: <key>`` (NOT ``Authorization: Bearer``).
- Base URL is ``https://apihub.document360.io/v2``.
- The API does NOT expose a server-side "modified since" query parameter on the
  article-list endpoints. Incremental sync is therefore client-side: list all
  published articles, compare each article's ``modified_at`` against a stored
  watermark, and fetch full content only for the ones that changed. This matches
  the fallback path described in the spike doc.
- Articles are organised under a project version. You must resolve a project
  version id first, then walk its category tree; article *stubs* (id, title,
  modified_at, etc.) come from the category-articles endpoint, and full content
  (the HTML body) comes from the single-article endpoint.
- Responses are wrapped in an envelope: ``{"data": ..., "success": bool, ...}``.
  Article content comes back as HTML in the ``html_content`` field.

Because the article-list endpoint returns stubs without bodies, ``list_articles``
returns lightweight metadata and ``get_article`` fetches the full body. The sync
job is expected to call ``list_articles`` once, diff against its watermark, then
call ``get_article`` only for changed ids.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://apihub.document360.io/v2"

# The API paginates category-articles; 100 is a common ceiling. Confirm the
# real max against your instance — the spike's pagination probe answers this.
_PAGE_SIZE = 100

# Conservative concurrency cap for get_article fan-out, per the spike's
# recommendation, to stay well under the rate limit during a nightly sync.
_DEFAULT_CONCURRENCY = 4


class Document360Error(RuntimeError):
    """Raised when the API returns a non-success envelope or HTTP error."""


class Document360Client:
    """Async client for the Document360 v2 API.

    Usage::

        async with Document360Client(api_key) as client:
            stubs = await client.list_articles(modified_since=watermark)
            for stub in stubs:
                full = await client.get_article(stub["id"])
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 30.0,
        max_retries: int = 5,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "api_token": api_key,
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    # -- context management -------------------------------------------------

    async def __aenter__(self) -> Document360Client:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- low-level request with retry/backoff -------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET a path, honour Retry-After / backoff, and unwrap the envelope.

        Returns the contents of the ``data`` field. Raises Document360Error on
        a non-success envelope or after exhausting retries.
        """
        backoff = 1.0
        last_exc: Exception | None = None

        for _attempt in range(self._max_retries):
            try:
                response = await self._client.get(path, params=params or None)
            except httpx.TransportError as exc:  # network blip
                last_exc = exc
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                continue

            if response.status_code == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                await asyncio.sleep(retry_after if retry_after is not None else backoff)
                backoff = min(backoff * 2, 60.0)
                continue

            if response.status_code >= 500:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
                continue

            if response.status_code == 401:
                raise Document360Error(
                    "401 Unauthorized — check the api_token header and key. "
                    "The D360 v2 API expects a custom 'api_token' header, not a "
                    "Bearer token."
                )

            response.raise_for_status()
            payload = response.json()
            return _unwrap(payload)

        raise Document360Error(
            f"GET {path} failed after {self._max_retries} retries"
        ) from last_exc

    # -- public API ---------------------------------------------------------

    async def get_project_versions(self) -> list[dict[str, Any]]:
        """Return the project versions. Article listing is scoped to a version."""
        data = await self._get("/ProjectVersions")
        return data if isinstance(data, list) else []

    async def _default_version_id(self) -> str:
        """Resolve the project version to sync.

        Defaults to the first version. If Preiss Central has multiple versions
        (e.g. public vs internal), make this explicit rather than implicit.
        """
        versions = await self.get_project_versions()
        if not versions:
            raise Document360Error("No project versions returned")
        return str(versions[0].get("id") or versions[0].get("version_id"))

    async def list_categories(
        self, version_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return the (possibly nested) category tree for a project version."""
        version_id = version_id or await self._default_version_id()
        data = await self._get(f"/ProjectVersions/{version_id}/categories")
        return data if isinstance(data, list) else []

    async def list_articles(
        self,
        modified_since: datetime | None = None,
        *,
        version_id: str | None = None,
        published_only: bool = True,
    ) -> list[dict[str, Any]]:
        """List article stubs across all categories in a project version.

        Returns lightweight metadata per article (id, title, modified_at,
        category id, status, ...) — NOT the full body. Call ``get_article`` for
        content.

        ``modified_since`` is applied CLIENT-SIDE: the API has no server-side
        modified-at filter (confirmed in the spike), so we fetch all stubs and
        drop any whose ``modified_at`` is at or before the watermark. This keeps
        the *fetch* step incremental even though the *list* step is a full walk.
        """
        version_id = version_id or await self._default_version_id()
        categories = await self.list_categories(version_id)

        stubs: list[dict[str, Any]] = []
        for category_id in _iter_category_ids(categories):
            stubs.extend(await self._list_category_articles(category_id))

        if published_only:
            stubs = [a for a in stubs if _is_published(a)]

        if modified_since is not None:
            cutoff = _as_utc(modified_since)
            stubs = [
                a
                for a in stubs
                if (m := _parse_dt(a.get("modified_at"))) is not None and m > cutoff
            ]

        return stubs

    async def _list_category_articles(self, category_id: str) -> list[dict[str, Any]]:
        """Page through one category's articles, returning stubs."""
        out: list[dict[str, Any]] = []
        page = 1
        while True:
            data = await self._get(
                f"/Categories/{category_id}/articles",
                params={"pageNumber": page, "pageSize": _PAGE_SIZE},
            )
            batch = (
                data
                if isinstance(data, list)
                else data.get("items", [])
                if isinstance(data, dict)
                else []
            )
            if not batch:
                break
            for article in batch:
                if isinstance(article, dict):
                    article.setdefault("category_id", category_id)
            out.extend(batch)
            if len(batch) < _PAGE_SIZE:
                break
            page += 1
        return out

    async def get_article(self, article_id: str) -> dict[str, Any]:
        """Fetch a single article's full content (HTML body + metadata)."""
        data = await self._get(f"/Articles/{article_id}")
        return data if isinstance(data, dict) else {"id": article_id, "data": data}

    async def get_articles(
        self,
        article_ids: list[str],
        *,
        concurrency: int = _DEFAULT_CONCURRENCY,
    ) -> list[dict[str, Any]]:
        """Fetch many articles with a bounded concurrency cap."""
        semaphore = asyncio.Semaphore(concurrency)

        async def _one(aid: str) -> dict[str, Any]:
            async with semaphore:
                return await self.get_article(aid)

        return await asyncio.gather(*(_one(aid) for aid in article_ids))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unwrap(payload: Any) -> Any:
    """Unwrap the D360 ``{"data": ..., "success": ...}`` envelope."""
    if isinstance(payload, dict) and "data" in payload and "success" in payload:
        if not payload.get("success", True):
            raise Document360Error(
                f"API returned success=false: {payload.get('errors')}"
            )
        return payload["data"]
    return payload


def _iter_category_ids(categories: list[dict[str, Any]]) -> list[str]:
    """Flatten a (possibly nested) category tree into a list of ids."""
    ids: list[str] = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        cid = category.get("id")
        if cid is not None:
            ids.append(str(cid))
        children = category.get("child_categories") or category.get("categories") or []
        if isinstance(children, list):
            ids.extend(_iter_category_ids(children))
    return ids


def _is_published(article: dict[str, Any]) -> bool:
    """Best-effort published check. D360 uses an integer status code; 3 is
    typically 'Published'. Verify the exact value against your dumps."""
    status = article.get("status")
    if status is None:
        return True  # be permissive if the field is absent
    if isinstance(status, str):
        return status.lower() == "published"
    return status == 3


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _parse_retry_after(value: str | None) -> float | None:
    """Retry-After may be seconds or an HTTP date. Return seconds to wait."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime

        when = parsedate_to_datetime(value)
        delta = (when - datetime.now(UTC)).total_seconds()
        return max(delta, 0.0)
    except (TypeError, ValueError):
        return None
