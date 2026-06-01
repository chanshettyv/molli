# Freshservice API exploration

**Status:** in progress — awaiting API key (expected Monday).
**Owner:** Vedant
**Sprint:** Sprint 1
**Related:** sync-job design is separate; this feeds the `TicketingProvider` interface in `shared/molli_shared/clients/freshservice.py` and the Autotask migration plan (Fall 2026).

> This document captures findings from the Freshservice API exploration spike. Sections marked **(to verify with live API)** are based on the published docs and will be confirmed Monday against the live endpoint.

---

## TL;DR

_(Fill in after Monday's live exploration. One paragraph: which endpoints Molli will call, the exact category/sub_category strings used for routing, how requester lookup behaves for unrecognized emails, observed rate limits, and the final shape of the three reference payloads.)_

---

## Test environment

**Decision (from Adam, confirmed before this spike started):** There is no Freshservice sandbox available. The spike runs against the live Preiss Freshservice instance.

**Conventions to keep test traffic visible and dismissible:**

- Every test ticket subject is prefixed `[TEST-Molli]`. The exploration script enforces this at the call site — it's not possible to POST a ticket through the script without the prefix.
- Every test ticket has a tag `molli-spike` so the team can bulk-filter or bulk-delete after the spike concludes.
- Every test ticket is created and then immediately deleted (or closed if delete isn't permitted on the plan). The script captures the created ticket payload before deletion for the spike doc; no test tickets persist in the queue.
- Adam is CC'd on the test tickets so he sees them land and can confirm routing.

**If anyone runs this script later:** the same rules apply. Treat the prefix and tag as load-bearing.

---

## Authentication

**Format:** HTTP Basic Auth. Username = API key, password = any non-empty string (convention: `X`). _(Confirm against docs.)_

**Base URL:** `https://{domain}.freshservice.com/api/v2` — domain is per-tenant. Confirm Preiss's exact domain with Adam (likely `preiss` or `preisscompany` or similar).

**Where the key lives:**
- **Production:** Google Secret Manager → `freshservice-api-key` and `freshservice-domain` in both `molli-dev` and `molli-prod`, once Sidney's GCP setup completes.
- **Spike (this week):** local `.env` file at the repo root. Adam provides the key directly.
- **CI:** not needed — tests mock the client.

**Loading in code:** `shared/molli_shared/config.py` exposes `settings.freshservice_api_key` and `settings.freshservice_domain`. The client in `shared/molli_shared/clients/freshservice.py` consumes both.

**Permissions consideration:** the spike key Adam provides should be scoped to an "agent" user with permission to read groups, agents, requesters, and ticket fields, plus create and delete tickets. If the live key is more restricted than the eventual production key, document the gap.

---

## Endpoints used by Molli

Molli's three ticketing operations: look up the requester from the chat user's email, create a ticket with appropriate routing fields, and (eventually) attach the conversation transcript. Mapping those to Freshservice:

### Connectivity check

`GET /api/v2/agents/me` _(to verify path)_

Returns the agent the API key represents. Cheapest possible call; the script uses it as a connectivity probe and a rate-limit probe target.

### List groups

`GET /api/v2/groups`

Returns the set of agent groups (likely: IT, Operations, HR, plus possibly more granular sub-teams). Each ticket gets routed to a group via `group_id`. The investigation already identified that Molli will route to three groups; this call confirms the exact IDs.

### List agents

`GET /api/v2/agents`

Used to look up specific agent IDs if Molli ever wants to assign tickets directly (e.g., HR escalations to Sally specifically). For the v1, group-level routing is sufficient; agent-level routing is a Phase 2 consideration.

### List ticket form fields — critical for routing

`GET /api/v2/ticket_form_fields` _(to verify path; may be `/api/v2/admin/ticket_fields` on some plans)_

This is the most important read-only call in the spike. Returns the structured definition of every field on a ticket, including the dropdown choices for `category`, `sub_category`, `item_category`, and any custom fields. The ticket investigation grouped tickets by Freshservice's `Issue` and `System` labels — this call returns the exact string values Molli must send to match those labels. Without this mapping, tickets will land in the wrong queues.

**The mapping the spike must produce** (this table gets filled in Monday):

| Investigation cluster | Department | category | sub_category | item_category | group_id |
|---|---|---|---|---|---|
| Password resets (Google) | IT | _(to fill)_ | _(to fill)_ | _(to fill)_ | _(to fill)_ |
| Printer connection | IT | | | | |
| Hardware request | IT | | | | |
| Email distribution list | IT | | | | |
| Entrata: requesting access | Ops | | | | |
| Entrata: refunds / ledger | Ops | | | | |
| Tenant screening (sensitive) | Ops | | | | |
| Benefits / PTO question | HR | | | | |
| Generic "Molli unsure" | _(triage)_ | | | | |

### Lookup requester by email

`GET /api/v2/requesters?email=<email>` _(to verify; some Freshservice plans use `/api/v2/contacts`)_

Molli's identity flow is Google Chat event → Workspace email → Freshservice requester. The response includes a `requester_id` that gets attached to the created ticket.

**Open design question** (raise with Sally and Adam): what should Molli do when the lookup returns no match? Options:
- (a) POST the ticket with `email` only and let Freshservice auto-create the requester.
- (b) Refuse to create the ticket; tell the user their account isn't provisioned.
- (c) Create the ticket with a fallback "unknown requester" placeholder and flag for triage.

The investigation showed ~85 new-hire-related tickets per quarter — there's a real window where someone exists in Workspace but not yet in Freshservice. The right answer is probably (a) with a custom field flagging the auto-creation; confirm Monday.

### Create ticket

`POST /api/v2/tickets`

Documented required fields:
- `email` (or `requester_id`)
- `subject`
- `description` (HTML accepted)
- `status` (integer enum)
- `priority` (integer enum)

Likely additional fields Molli will set on every ticket: `source`, `group_id`, `category`, `sub_category`, `tags`, `custom_fields`.

**Status / priority / source enum mapping** _(to verify against the live API)_:

| Field | Value | Meaning |
|---|---|---|
| status | 2 | Open |
| status | 3 | Pending |
| status | 4 | Resolved |
| status | 5 | Closed |
| priority | 1 | Low |
| priority | 2 | Medium |
| priority | 3 | High |
| priority | 4 | Urgent |
| source | 7 | Other (or "Chat"? — verify) |

Getting these wrong is silent — the API accepts the integer, Molli looks like it's working, but tickets are mispriced and never SLA'd correctly. Worth a careful confirm against the docs.

### Delete ticket

`DELETE /api/v2/tickets/{id}`

Used in the spike script to clean up test tickets immediately after creation. May require admin permissions on some plans — if delete fails, the script falls back to setting status=5 (Closed) and adding a `molli-spike-cleanup` tag.

### Attach conversation transcript

**Design choice for v1: inline in `description`.** The chat transcript becomes part of the ticket body as formatted HTML. Trade-offs:

- ✅ Self-contained — no external dependency, no link rot.
- ✅ Visible to agents without needing access to anything else.
- ✅ Searchable within Freshservice.
- ❌ Long ticket descriptions are ugly in the agent UI.
- ❌ Can't be updated after creation.

Alternatives considered: separate attachment via `POST /api/v2/tickets/{id}/attachments` (cleaner UI but two requests, file-size limits, and complexity around the multipart upload); link to a Firestore-hosted transcript viewer (cleanest, but depends on the admin dashboard existing — that's Phase 2 per the kickoff deck).

**Recommendation:** ship v1 with inline HTML, revisit when the admin dashboard exists.

---

## Rate limits

_(To verify Monday — fire `GET /agents/me` in a loop and log the headers)_

**From the docs:** Freshservice publishes per-plan rate limits. Confirm the exact numbers for Preiss's plan tier with Adam.

**Headers to inspect:**
- `X-RateLimit-Total`
- `X-RateLimit-Remaining`
- `X-RateLimit-Used-CurrentRequest`
- `Retry-After` (on 429 responses)

**Expected client behavior:**
- Honor `Retry-After` strictly when present.
- Exponential backoff with jitter on 5xx (1s, max 30s, max 3 retries — ticket creation is user-facing in a chat flow, so retry budget is much smaller than D360 sync's).
- Surface persistent failures to the user clearly: "I couldn't reach the ticketing system. Please try again in a minute, or contact IT directly."

---

## Custom fields Molli should request from Adam

Strongly recommend asking Adam to add the following custom fields to the Freshservice ticket schema before Molli goes live. They make the admin dashboard's "how is Molli doing?" analytics possible, and they're a one-time setup:

| Field name | Type | Purpose |
|---|---|---|
| `molli_conversation_id` | text | Cross-references the Firestore conversation. Lets us audit what Molli did before escalating. |
| `molli_confidence_score` | number (0–1) | Molli's self-reported confidence at the moment of escalation. Useful for tuning the escalation threshold. |
| `molli_d360_articles_consulted` | multi-line text | The article IDs Molli retrieved before deciding to escalate. Reveals D360 content gaps — articles that should exist but don't, or that exist but aren't being matched. |
| `molli_escalation_reason` | dropdown | Enum: `no-confident-answer`, `user-requested-human`, `guardrail-triggered`, `other`. |

Adding these requires admin access in Freshservice, which Adam has. Putting them on the request list now (rather than discovering we need them mid-Phase 2) saves a turnaround.

---

## Reference payloads — the three common cases

These are the three highest-volume escalation patterns from the ticket investigation, expressed as the exact JSON Molli will POST. Values marked `<...>` get filled in Monday from the live `ticket_form_fields` and `groups` calls.

### Scenario A — Password reset escalation

**Trigger:** User asked Molli to reset their password. Molli explained the Google self-service flow. User replied that they have no recovery email or phone. Molli now escalates to IT.

**Volume basis:** IT cluster #5 — 29 tickets / 90 days, ~120/year. Highest-impact deflection target if Molli succeeds on the self-service path; this payload covers the residual cases that genuinely need a human.

```json
{
  "email": "<requester email from Google Chat>",
  "subject": "[TEST-Molli] Password reset needed — self-service unavailable",
  "description": "<html>...full chat transcript here, including Molli's explanation of self-service and the user's reason for needing manual help...</html>",
  "status": 2,
  "priority": 2,
  "source": 7,
  "group_id": "<IT group_id>",
  "category": "<Software or similar>",
  "sub_category": "<Google Workspace>",
  "item_category": "<Password Reset>",
  "tags": ["molli", "molli-spike"],
  "custom_fields": {
    "molli_conversation_id": "<conversation uuid>",
    "molli_confidence_score": 0.85,
    "molli_d360_articles_consulted": "kb-1234, kb-5678",
    "molli_escalation_reason": "no-confident-answer"
  }
}
```

### Scenario B — Hardware request

**Trigger:** User asked Molli for a new laptop. Molli collected structured fields through chat (who the laptop is for, role, property, urgency). Molli now creates a ticket with those fields pre-populated for Adam to approve.

**Volume basis:** IT cluster #6 — 20 tickets / 90 days. Always needs approval; Molli's job is to make sure the request lands fully-specified so Adam doesn't have to round-trip for missing fields.

```json
{
  "email": "<requester email>",
  "subject": "[TEST-Molli] Hardware request: laptop for new hire at The Forum",
  "description": "<html>Requested by: <name>\nRecipient: <new hire name>\nRole: <role>\nProperty: <property>\nUrgency: <date needed>\n\nFull chat transcript:\n...</html>",
  "status": 2,
  "priority": 3,
  "source": 7,
  "group_id": "<IT group_id>",
  "category": "<Hardware>",
  "sub_category": "<Computer / Laptop>",
  "item_category": "<New Request>",
  "tags": ["molli", "molli-hardware-request"],
  "custom_fields": {
    "molli_conversation_id": "<conversation uuid>",
    "molli_confidence_score": 1.0,
    "molli_d360_articles_consulted": "kb-procurement-process",
    "molli_escalation_reason": "user-requested-human"
  }
}
```

### Scenario C — Generic "I don't know, please help"

**Trigger:** Molli could not find a confident answer in D360 and has no clear routing signal from intent classification. Falls through to a triage queue.

**Volume basis:** the long tail. Likely 10–20% of all Molli escalations once the bot is live — uncategorized questions, edge cases, novel issues.

```json
{
  "email": "<requester email>",
  "subject": "[TEST-Molli] Unable to resolve: <first 60 chars of user question>",
  "description": "<html>Molli could not find a confident answer. Routing this to triage.\n\nFull chat transcript:\n...</html>",
  "status": 2,
  "priority": 2,
  "source": 7,
  "group_id": "<triage group_id — confirm with Adam which group handles this>",
  "category": "<Other or Something Else>",
  "tags": ["molli", "molli-triage", "molli-low-confidence"],
  "custom_fields": {
    "molli_conversation_id": "<conversation uuid>",
    "molli_confidence_score": 0.3,
    "molli_d360_articles_consulted": "kb-1234, kb-5678, kb-9012",
    "molli_escalation_reason": "no-confident-answer"
  }
}
```

**Open question on Scenario C:** the investigation showed 212 tickets (12% of the corpus) land in "Other"/"Something Else" buckets — Molli routing more traffic into the same buckets makes the existing intake-quality problem worse. Worth a conversation about whether Molli should refuse to create a ticket at all when confidence is below some threshold, vs. forwarding to triage with a clear "Molli is unsure" signal. This is a Phase 2 product decision, not an API question.

---

## Gotchas

_(Fill in surprises discovered Monday. Likely candidates:)_

- ~~`source` enum value for "chatbot" differs from "API" — choose deliberately~~
- ~~`requester_id` vs `email` precedence when both are sent~~
- ~~Custom field naming: spaces, casing, or `cf_` prefix required~~
- ~~HTML in `description` is sanitized — some tags stripped~~
- ~~Tags are case-sensitive and split on commas~~

Strike through what doesn't apply; expand what does.

---

## Recommendation for the Freshservice client

_(Fill in Monday after empirical results. Sketch of what the doc should land on:)_

- The `TicketingProvider` protocol exposes `lookup_requester(email) -> RequesterId | None` and `create_ticket(payload: TicketPayload) -> TicketId`. The Autotask implementation in Fall 2026 must match the same protocol.
- `TicketPayload` is a Pydantic model with the fields the three reference payloads above demand. Routing-related fields (`group_id`, `category`, etc.) are enums populated from a constants module that the spike doc maps.
- The client uses `httpx.AsyncClient` with retry logic in a small wrapper, not `tenacity` or similar — keep the dependency footprint small.
- Failed ticket creation is **never** silently swallowed; it surfaces to the user as a clear message and logs to Cloud Logging at ERROR with the full payload (minus PII).

---

## Open questions for Adam

1. **Freshservice domain.** Exact value for the base URL — `https://<?>.freshservice.com`.
2. **Spike API key permissions.** Can the spike key delete tickets? If not, what's the closest equivalent (close + tag)?
3. **Custom fields.** Can Adam add the four `molli_*` custom fields listed above? Lead time?
4. **"Triage" group.** Which existing group should Molli route low-confidence tickets to? If none exists, should one be created (e.g., `molli-triage`)?
5. **Requester auto-creation.** What happens on `POST /tickets` with an `email` that doesn't match a requester? Auto-created? Rejected? If auto-created, is the new requester record correctly linked downstream?
6. **Rate limit on Preiss's plan.** Documented number and observed ceiling.
7. **Existing taxonomy.** Can Adam share the current `category` / `sub_category` / `item_category` dropdown values? (The script will pull this from `ticket_form_fields` Monday, but Adam's eyes on the output will surface mismatches between the technical names and how the team actually uses the fields.)
8. **Intake form revision.** The investigation flagged that 12% of tickets land in "Other"/"Something Else" buckets. Is Adam open to revising the intake form in parallel with Molli's rollout?

---

## Test plan executed Monday

In order — read-only operations first, write operations last and minimal:

1. **Connectivity.** `GET /api/v2/agents/me`. Confirm auth works and capture the agent record for the spike key.
2. **List groups.** Dump full response to `tmp/freshservice/groups.json`. Identify IT, Ops, HR, and any triage group IDs.
3. **List agents.** Dump to `tmp/freshservice/agents.json`. Confirm Adam, Lane, Toni, Sally are present and capture their IDs.
4. **List ticket form fields.** Dump to `tmp/freshservice/ticket_fields.json`. Fill in the routing table above.
5. **Requester lookup.** Look up one known Preiss email (Adam's — with his prior consent). Confirm the response shape. Also try a deliberately bogus email to see how the API handles no-match.
6. **Rate limit probe.** Fire `GET /agents/me` 30 times in a sequential loop. Log all rate-limit headers per call.
7. **Create + delete cycle, Scenario A.** Create one `[TEST-Molli]` ticket using the Scenario A payload (populated with real IDs from steps 2–4). Capture the response JSON. Delete the ticket. Confirm deletion succeeded.
8. **Create + delete cycle, Scenario B.** Same with Scenario B.
9. **Create + delete cycle, Scenario C.** Same with Scenario C.

Total tickets created: 3. Total tickets remaining in queue afterward: 0.

Once these are done, the spike doc gets its TL;DR and recommendation, and a PR goes up.

---

## Code reference

The exploration script lives at `scripts/explore_freshservice.py`. Run with:

```bash
FRESHSERVICE_API_KEY=... FRESHSERVICE_DOMAIN=... uv run python scripts/explore_freshservice.py
```

Output is human-readable (uses `rich`) and dumps raw API responses to `tmp/freshservice/*.json` for inspection. By design, the script cannot create a ticket without the `[TEST-Molli]` subject prefix.
