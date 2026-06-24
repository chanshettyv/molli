# Molli — AI Employee Assistant

**Preiss Companies · Internal Tool · 2025 – present**

Molli is a RAG-powered AI assistant that lives inside Google Chat. Employees ask questions; Molli retrieves relevant articles from Preiss Central (Document360), grounds its answer in that content, and returns a cited response — all within Google Chat, using Workspace SSO identities. When Molli can't find an answer, it offers to pre-fill a Freshservice support ticket from the conversation context. Six compliance guardrails (Fair Housing, FCRA, OSHA, mental health, data privacy, escalation) run before every Gemini call.

---

## What it does

- Answers HR, IT, and operations questions grounded in the Preiss Central knowledge base
- Returns inline citations linking back to the source Document360 article
- Blocks or escalates sensitive queries (FHA violations, FCRA screening, OSHA emergencies, distress signals)
- Redacts PII from inbound messages and outbound answers via Google Cloud DLP
- Creates Freshservice support tickets — manually via a pre-filled dialog, or automatically when no knowledge base answer is available
- Runs structured admin workflows (e.g., Entrata access requests, distribution list changes) with field-specific ticket routing

---

## Architecture

Two Cloud Run workloads share a `molli-shared` Python package:

**`chat-service`** — FastAPI app, handles Google Chat `MESSAGE` and `CARD_CLICKED` events.
Request flow: classify event → run guardrail chain → RAG pipeline → Gemini → return cardsV2 response.

**`sync-job`** — Nightly Cloud Run job that keeps the knowledge index current.
Pipeline: list changed Document360 articles → fetch HTML → chunk by heading → embed → upsert to Vector Search → store text in Firestore → advance watermark.

**Firestore** stores three things independently: chunk text (keyed by Vector Search datapoint ID), conversation memory per user/space, and sync state (watermark + failed article IDs for retry).

**Vertex AI Vector Search** stores 768-dimension embeddings only — chunk text is fetched from Firestore by datapoint ID after neighbor lookup, keeping index payloads small.

---

## RAG pipeline

```
User query
  → embed (RETRIEVAL_QUERY task type, text-embedding-004)
  → Vector Search: top-5 nearest neighbors by DOT_PRODUCT distance
  → Firestore batch-read: fetch chunk text for returned IDs (~tens of ms)
  → Gemini 2.5 Flash: grounded answer with inline citations [1][2]
  → model emits INSUFFICIENT_CONTEXT sentinel if sources don't cover the question
  → fallback: general Gemini answer with disclaimer + Create Ticket button
```

Chunking targets ~750 tokens per chunk, split on HTML heading boundaries to preserve topical coherence. Each chunk carries its heading as metadata for citation rendering.

---

## Guardrails

Six guardrails run in priority order; the chain short-circuits on `BLOCK` or `ESCALATE`:

| Guardrail | Trigger | Action |
|---|---|---|
| **Mental Health** | Distress or self-harm signals | BLOCK → EAP referral |
| **Workplace Safety** | OSHA Tier 1 emergency | ESCALATE → Operations + 911 guidance |
| **Fair Housing (FHA)** | Tenant screening / housing discrimination queries | BLOCK → FHA explanation |
| **FCRA** | Background check / adverse action queries | BLOCK → FCRA explanation |
| **Data Privacy** | PII in message or Gemini output (Cloud DLP) | REDACT or BLOCK |
| **Escalation** | Low-confidence answer, repeated follow-ups | Tier 2: ticket offer / Tier 3: human handoff |

FHA and FCRA use a dual-layer approach: regex fast path for obvious phrasing, LLM semantic classifier for ambiguous cases. Cloud DLP fails open (availability over blocking on transient DLP errors), with a logged alert.

---

## Ticketing

Freshservice integration accepts a `TicketCreatePayload` with required custom fields (`original_system`, `original_more_detail`, `msf_affected_location`). The chat-service talks to a `TicketingProvider` protocol rather than the Freshservice client directly — the planned Autotask migration (Fall 2026) will be a single-file swap with no changes to the handler, card builders, or schemas.

When Molli can't answer a question, the reply card includes a **Create Ticket** button. Clicking it opens the existing ticket dialog pre-filled with the user's email, a subject derived from their question, and a description that includes the original question as context. Group, location, and system are left empty for the user to fill in before submitting.

---

## Tech stack

| Layer | Technology |
|---|---|
| AI / LLM | Gemini 2.5 Flash (RAG grounding + general Q&A fallback) |
| Embeddings | text-embedding-004, 768-d, batch 250 |
| Vector DB | Vertex AI Vector Search, DOT_PRODUCT |
| Interface | Google Chat native app, cardsV2, Workspace SSO |
| Storage | Firestore (chunks, memory, sync state) |
| Compute | Cloud Run (service + job), Cloud Scheduler |
| Privacy | Google Cloud DLP — PII scan on inbound + outbound |
| Knowledge Base | Document360 (Preiss Central), async client, 1 500 req/min |
| Ticketing | Freshservice REST v2 (→ Autotask Fall 2026) |
| Secrets | GCP Secret Manager, per-secret IAM |
| IaC | Terraform (Cloud Run, Vector Search, IAM, Secrets) |
| Backend | FastAPI, Python 3.12, uv workspace |
| Quality | mypy strict, ruff, pytest, coverage gate 30% |
| CI/CD | GitHub Actions + Workload Identity Federation |
| Observability | structlog + Cloud Logging, SHA-256 hashed user IDs in logs |

---

## Notable engineering decisions

**Watermark-based incremental sync** — `last_synced_at` is set to sync *start* time, not end, so articles modified mid-run are picked up next cycle. Failed article IDs are stored separately and retried regardless of watermark advance, preventing transient errors from silently dropping content.

**Split storage: vectors in Vector Search, text in Firestore** — Vector Search datapoints carry only the embedding + short metadata tokens. Chunk text lives in Firestore keyed by the same datapoint ID. Two-hop retrieval (neighbor IDs → Firestore batch read) keeps index payloads small and text retrieval fast.

**Dual-layer guardrail detection** — Regex catches obvious FHA/FCRA phrasing cheaply. Ambiguous cases that clear regex are escalated to a Gemini semantic classifier with explicit exclusion examples to suppress false positives ("kill this bug" ≠ fair housing violation).

**TicketingProvider protocol abstraction** — `chat-service` never imports Freshservice directly. The planned Autotask migration is scoped to one file replacement.

**Fail-open DLP** — If Cloud DLP is unreachable, Molli continues with a logged warning rather than blocking employee support. Availability is prioritized over perfect PII scanning in transient failure scenarios.

**No raw PII in logs** — User emails are hashed (`SHA256(email)[:16]`) for correlation. No message content is logged beyond session ID.

---

## Repository structure

```
molli/
├── chat-service/          # FastAPI app — Google Chat event handler
│   └── app/
│       ├── main.py        # Event router, guardrail chain, RAG dispatch
│       ├── gemini_client.py
│       ├── tools/rag_answer.py
│       └── cards/         # cardsV2 builders, dialogs, ticket forms
├── sync-job/              # Nightly Document360 → Vector Search job
│   └── sync_job/
│       ├── main.py        # 7-step pipeline orchestrator
│       ├── chunking.py    # HTML → heading-split text chunks
│       └── watermark.py   # Firestore-backed incremental sync state
├── shared/                # molli-shared package (used by both services)
│   └── molli_shared/
│       ├── clients/       # Document360, Freshservice, TicketingProvider
│       ├── guardrails/    # Six guardrails + chain orchestrator
│       ├── retrieval/     # Embedding + Vector Search index client
│       ├── chunk_store.py # Firestore chunk text store
│       └── schemas/       # Pydantic models (tickets, articles, drafts)
├── infra/terraform/       # GCP resources (Cloud Run, Vector Search, IAM)
├── .github/workflows/     # CI (lint, type, test, coverage), deploy pipelines
└── docs/                  # Architecture, runbook, guardrail design, spikes
```

---

## Roadmap

**Phase 0 — Foundations** ✅ Complete
Google Chat integration, six guardrails, Freshservice ticket dialog, structured admin workflows, Terraform IaC, CI/CD with WIF.

**Phase 1 — RAG Pipeline** 🔄 In Progress
Document360 sync pipeline, Vector Search index, RAG answer generation with citations, Create Ticket button on no-context replies. Remaining: latency instrumentation, sync monitoring.

**Phase 2 — Autonomous Ticketing** ⏳ Planned
Gemini function-calling for automatic ticket field extraction, confidence-scored field proposals, HR escalation routing, Autotask migration. Adoption target: 70% of employees, 4+ interactions per 30-day window.

---

## Team

Built by Vedant Chanshetty · Preiss Companies · 2025 – present
