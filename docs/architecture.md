# Architecture

This doc captures the technical architecture of Molli. Source of truth is the kickoff deck slide 4 plus the diagrams below.

## Component map

```
[User in Google Chat]
        |
        v
[Google Chat app] --SSO--> [Workspace identity]
        |
        v
[Cloud Run: chat-service]
   |                    |                       |
   v                    v                       v
[Firestore]      [Vertex AI Gemini 1.5 Pro]   [Secret Manager]
 (memory)              |
                  function calls
                       |
            +----------+----------+
            v                     v
   [Vertex AI Vector       [Freshservice API]
    Search index]          (ticket create)
            ^
            | upsert nightly
            |
   [Cloud Run job: sync-job] <--cron-- [Cloud Scheduler]
            ^
            |
     [Document360 API]
```

## Layers (from the deck)

| Layer | Components |
|---|---|
| Interface | Google Chat (native app), Workspace SSO, mobile + desktop |
| AI engine | Gemini 1.5 Pro via Vertex AI, conversational memory in Firestore |
| Knowledge | Document360 (Preiss Central), nightly sync to Vertex AI Vector Search |
| Integration | Freshservice API (Phase 1), Autotask (Phase 2, Fall 2026), Google Workspace Admin SDK |
| Infrastructure | GCP, Cloud Run, Secret Manager, Cloud Logging, Cloud Pub/Sub, Cloud Build |

## Key design choices

- **Daily sync, not per-query**: Document360 is too large to search live on every turn. Nightly incremental sync into Vertex AI Vector Search keeps freshness within 24 hours.
- **Ticketing behind an interface**: `TicketingProvider` protocol in `shared/clients/freshservice.py`. The Autotask migration in Fall 2026 is a single-file change.
- **User confirms before ticket creation**: Gemini's `create_ticket` tool call is intercepted; the chat-service renders a Chat card with Confirm / Edit / Cancel buttons.
- **Guardrail chain runs before Gemini**: all six guardrails (MH, FHA, FCRA, OSHA, escalation, data privacy) inspect the message first. Any BLOCK or ESCALATE short-circuits the pipeline.

## Open questions

- Vector index choice: Vertex AI Vector Search (current plan) vs. pgvector on Cloud SQL. Decision needed before Phase 1.
- Conversation memory horizon: last N turns vs. summary + last N. TBD based on usage.
