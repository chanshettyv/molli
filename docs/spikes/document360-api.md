# Document360 API exploration

**Status:** in progress — awaiting API key (expected Monday).
**Owner:** Vedant
**Sprint:** Sprint 1
**Related:** sync-job design, Kautilya's vector backend ADR (`docs/spikes/vector-backend.md`).

> This document captures findings from the Document360 API exploration spike. Sections marked **(to verify with live API)** are based on the published docs and need confirmation against the live endpoint once the API key is available.

---

## TL;DR

_(Fill in after Monday's live exploration. One paragraph: which endpoints the sync job will use, whether server-side `modified_at` filtering works, observed rate limits, and the recommended request shape.)_

---

## Authentication

**Header format:** `Authorization: Bearer ...`

**Base URL:** `https://apihub.document360.io/v2`

**Key rotation:** Aswin Ramesh (Kovai) issues and rotates keys. Email him with Lane, Toni, and Whitney on CC for any key-related request.

**Where the key lives:**
- **Production:** Google Secret Manager → `d360-api-key` in both `molli-dev` and `molli-prod`.
- **Local dev:** `.env` file at the repo root (gitignored). See `.env.example` for the variable name (`D360_API_KEY`).
- **CI:** not needed — tests mock the client. The deploy workflows pull from Secret Manager at runtime.

**Loading in code:** `shared/molli_shared/config.py` exposes `settings.d360_api_key`. The Document360 client in `shared/molli_shared/clients/document360.py` reads from that.

---

## Endpoints used by the sync job

The sync job needs four operations: enumerate the content tree, list articles (with pagination and ideally a modified-since filter), fetch full article content, and detect deletions. Mapping those to D360's API:

### List categories

`GET /v2/categories` _(to verify path)_

Returns the category tree (categories and sub-categories). The sync job uses this to:
- Tag each chunk with its category path (so retrieval can filter or boost by category).
- Decide which categories to sync at all (Preiss Central may have categories we don't want indexed — internal-only, archived, etc.).

**Response shape (to verify):** array of category objects with `id`, `name`, `parent_id`, `order`, and possibly a nested `articles` array.

### List articles

`GET /v2/articles` _(to verify path — may be nested under category, e.g., `/v2/categories/{id}/articles`)_

**Query parameters of interest:**
- `page` / `page_size` (or whatever the docs specify — confirm)
- `modified_since` or `updated_after` if it exists _(critical — see "Incremental sync" below)_
- `status` filter to exclude drafts _(to verify it exists)_
- `category_id` filter if scoping by category

### Get article by ID

`GET /v2/articles/{id}` _(to verify path)_

Returns the full article including content body. **Open question for live testing:**
- Does the response include `content` as HTML, Markdown, or both fields?
- Are embedded images returned as full URLs, relative paths, or base64?
- How are tables, code blocks, and callouts/admonitions marked up?

### Filter by `modified_at` — critical for incremental sync

The single most important question this spike has to answer: **can the sync job ask "what changed in the last 24 hours?" server-side?**

- **If yes:** the nightly job fetches only modified articles. Cheap, fast, no full-corpus traversal.
- **If no:** the nightly job must list all articles, compare each `modified_at` against a stored watermark, and fetch only changed ones. Still incremental for the *fetch* step, but the *list* step gets more expensive as the corpus grows.

The fallback case is fine — Preiss Central will not grow to tens of thousands of articles. But it shapes the client design, so confirm Monday.

---

## Pagination behavior

_(To verify with live API across 50+ articles)_

**Expected shape:**
- Page-based: `?page=1&page_size=50`, max page size ~100.
- Response includes a `total_count` or `total_pages` field, and either `next`/`previous` links or an `is_last_page` flag.

**Things to test Monday:**
- What does the API do when `page` exceeds the number of pages? (Empty array? 404?)
- What's the maximum `page_size`?
- Is ordering stable across pages? (Important — if articles can shift between pages mid-sync, the sync job can miss or duplicate items.)
- Are paginated results sorted by `modified_at`, by `id`, or by display order? The sync job's correctness depends on this.

If pagination is cursor-based instead of offset-based, document the cursor format and how to detect end-of-stream.
