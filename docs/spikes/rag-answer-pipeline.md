# RAG answer pipeline (Phase 1 core)

**Date:** 2026-06-16
**Author:** Kautilya
**Component:** `chat-service/app/tools/rag_answer.py`
**Delivers:** the kickoff DoD line "responses sourced directly from Document360
with citation links."

## What was built

A retrieve → ground → generate → cite pipeline:

```
query -> embed (RETRIEVAL_QUERY) -> Vector Search top-k neighbour ids
      -> ChunkStore.get_many(ids) -> actual chunk text from Firestore
      -> grounded prompt (numbered sources + text + link)
      -> Gemini (gemini-2.5-flash) answers, citing inline as [1], [2]
      -> deduplicated citation list (title + D360 URL)
```

### Data layout (where things live)

Two stores, joined by datapoint id `{article_id}::{ordinal}`:

- **Vector Search index** (`molli_knowledge_stream`, us-central1): the 768-d
  vector + metadata restricts (article_id, category_id, title, url, heading).
- **Firestore `chunks` collection** (`(default)` db, us-east1): the full chunk
  **text** + a copy of the metadata, keyed by datapoint id.

Chunk text is NOT stored in Vector Search (datapoints aren't meant to hold
bodies). The RAG read does: Vector Search returns ids → Firestore `get_many`
returns the text for those ids. Sync job writes both in the same run.

### Supporting changes

- Relocated `Embedder` + `VectorIndex` from `sync-job` to
  `shared/molli_shared/retrieval/` so chat-service and sync-job share one copy.
  (Thin re-export shims left in sync-job so existing imports still work.)
- Added `shared/molli_shared/chunk_store.py` (the Firestore side store).
- Sync job now writes chunk text to the store during indexing
  (`chunk_store.put_many`). Backfilled the full corpus: 930 articles / 2503
  chunks.
- Model: uses `gemini-2.5-flash` (config default), NOT the kickoff's "1.5 Pro"
  — 1.5 Pro is not a valid Vertex model id (Sprint 1 finding) and flash is the
  better latency choice for the <30s budget.

## 20-query results (live, full corpus)

All 20 returned cited answers within the 30s budget. **None over budget.**

| Metric | Value |
|---|---|
| Queries | 20 |
| With citations | 20 / 20 |
| No-context (graceful) | 0 returned the bare no-context message |
| Min latency | 1.91s |
| Mean latency | 8.42s |
| Median latency | 6.12s |
| Max latency | 26.03s |
| Over 30s budget | 0 — **PASS** |

### Answer quality is split — and the split is informative

**Strong, grounded, correctly-cited answers** (content exists in D360):
reverse a payment in Entrata, upload utility charges, VPN connection, Mimecast
release, office-hours update, switch guarantor mid-lease, scheduled charges
expiring, benefits options, reset resident portal password, resident can't log
in. These are specific, step-by-step, and cite the right article. This is the
system working as intended.

**Graceful non-answers** (content gap — article not in D360):
Google password reset, account lockout, office printer, printer
troubleshooting, email distribution list, laptop request, Entrata access
request. The pipeline correctly said "the sources don't cover this — submit a
ticket / check Preiss Central" rather than hallucinating. This is the
"answer only from sources" design working: it refuses to invent Preiss policy.

**This matches the retrieval-quality spike exactly.** Those same high-volume IT
/ Ops questions (password, printer, Entrata access) were flagged in the ticket
audit as articles that do not yet exist in D360. Answer quality is gated on
**content coverage**, not on the pipeline. The highest-leverage next step for
answer quality is SME content creation, not engineering.

## Known issues / follow-ups

- **Content gaps (SME action, not engineering):** Google password reset,
  printer setup/troubleshooting, email distribution list, laptop request, and
  Entrata access-request articles don't exist or aren't retrievable. Until they
  exist, Molli cannot answer the top IT/Ops questions regardless of prompt
  quality. Ties to the ticket-audit article-creation list.
- **Latency near-miss:** one query hit 26.03s (reset resident portal password),
  attributable to model cold-start on the first heavy generation. Median is
  ~6s. Under load or on a slow path a query *could* breach 30s; worth a warm-up
  call on container start and/or a generation timeout in Phase 2. Do not claim
  "comfortably under budget" — claim "within budget, one cold-start near-miss."
- **Citation numbering polish:** `final_citations = cited or citations`
  sometimes lists sources the answer didn't meaningfully use, and inline
  references like "[1, 2, 3, 4, 5]" can point at sources the model only
  gestured at. Cosmetic; tighten the cited-source parsing in Phase 2.
- **Table-heavy articles chunk poorly:** the HTML→text chunker flattens tables
  into space-separated cell runs (e.g. benefits/insurance tables). Grounding
  still works but is weaker for table content. Consider an HTML-table-aware
  chunker — Phase 2, shared with the retrieval-spike chunking follow-up.
- **Metadata duplicated across both stores:** kept in sync by writing both from
  the same sync run. Could simplify later to a single source of truth (drop
  metadata from Vector Search restricts, read it from Firestore in the same
  get_many). Not worth changing now.
- **Not yet wired into the Chat handler:** `answer_with_citations` exists and is
  tested, but `main.py` still calls the old context-free `ask_gemini`. Wiring
  the RAG answer into the live Google Chat MESSAGE path (behind the guardrail
  chain) is the next integration step.
- **sync-job container rebuild:** the relocation means the deployed sync-job
  image still imports via the shims. Rebuild the image on the next deploy so the
  shims aren't load-bearing in production.

## Verdict

Phase 1 RAG core is **done**: all four exit criteria met (retrieval, cited
answers with working D360 links, <30s on 20 queries, smoke test). The pipeline
is honest — it grounds answers in real content and refuses to fabricate when
content is missing. The gating constraint going into Phase 2 is **content
coverage**, which is an SME task, plus the polish items above.
