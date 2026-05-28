# Molli

Preiss's AI-powered employee assistant. A Gemini-powered chatbot living natively inside Google Chat, connected to Preiss Central (Document360), with automatic Freshservice ticket creation when it can't resolve a query.

## Goals

- Reduce support ticket volume by 20% YoY
- 70% employee adoption (4+ interactions per rolling 30-day window)
- < 30s first response time
- 100% guardrail coverage for FCRA, FHA, OSHA, and mental health topics

## Architecture (high level)

- **Interface layer**: Google Chat native app, Workspace SSO, mobile + desktop
- **AI engine**: Gemini 1.5 Pro via Vertex AI, conversational memory in Firestore
- **Knowledge layer**: Document360 (Preiss Central), daily incremental sync into Vertex AI Vector Search
- **Integration layer**: Freshservice API for ticketing (Autotask migration Fall 2026), webhook handlers
- **Infrastructure**: Google Cloud Platform, Cloud Run, Secret Manager, Cloud Logging

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and component breakdown.

## Repo layout

```
chat-service/   FastAPI service handling Google Chat events (Cloud Run)
sync-job/       Daily batch that pulls Document360 -> embeds -> upserts to Vector Search (Cloud Run job)
shared/         Shared Python package: API clients, schemas, guardrails
infra/          Terraform for GCP resources
docs/           Architecture, runbook, ticket investigation, prompt templates
scripts/        Developer helper scripts
.github/        Issue templates and CI/CD workflows
```

## Team

| Role | Owner |
|---|---|
| AI / Backend Engineer | Kautilya |
| Integrations Engineer | Vedant |
| Security / QA Engineer | Sidney |

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for ownership boundaries, sprint cadence, and the definition of done.

## Quick start

```bash
# Prereqs: Python 3.12, uv (https://docs.astral.sh/uv/), gcloud, terraform
git clone <repo-url>
cd molli
uv sync                         # installs all three packages and dev deps
gcloud auth application-default login
cp .env.example .env            # then fill in non-secret config

# Run the chat service locally
cd chat-service && uv run uvicorn app.main:app --reload --port 8080
```

Secrets live in GCP Secret Manager, never in `.env`. See `docs/runbook.md` for how local dev pulls them.

## Status

In Phase 0 (Foundations). See the [project board](https://github.com/chanshettyv/molli/projects) for current sprint.
