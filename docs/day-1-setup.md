# Day 1 setup

For Kautilya, Vedant, and Sidney to do on the first day.

## Before you start

You'll need:
- A GitHub account with access to the `chanshettyv` org
- `gcloud` installed (https://cloud.google.com/sdk/docs/install)
- Python 3.12 and `uv` (https://docs.astral.sh/uv/)
- Docker (for local container builds later)

## Step 1: Clone and bootstrap

```bash
git clone https://github.com/chanshettyv/molli.git
cd molli
bash scripts/bootstrap.sh
```

The bootstrap script installs Python deps, sets up pre-commit hooks, and creates a `.env`.

## Step 2: Smoke test

```bash
uv run pytest
```

Both tests in `chat-service/tests/test_smoke.py` should pass.

## Step 3: Set up GitHub access

Make sure your GitHub username is in `.github/CODEOWNERS`. Currently placeholders (`@KautilyaChopra`, `@chanshettyv`, `@SidneyRoss8`) — replace with your real handles in a quick PR.

## Step 4: Get GCP access (Sidney to coordinate)

- Sidney creates `molli-dev` and `molli-prod` GCP projects.
- Sidney adds Kautilya and Vedant as `Editor` on `molli-dev` (prod access is more limited).
- All three: `gcloud auth login` then `gcloud config set project molli-dev`.

## Step 5: Pick up your first issues

Open the [project board](https://github.com/chanshettyv/molli/projects). The backlog is seeded with Phase 0 work.

Today specifically, each of you owns one ticket investigation:
- Vedant: Operations (Lane Sheer, Toni Yrlas)
- Sidney: HR (Sally Sousa)
- Kautilya: IT (Adam Tomlinson)

Fill in your section of `docs/ticket-investigation.md` as you go.

## Step 6: Standup time

Agree on a 10-minute daily standup time. Suggest 9:30am or 10:00am.

## Things you don't need to do today

- Touch Gemini, Vertex AI, or any model code (Phase 2)
- Spin up Cloud Run (Phase 0 task #X, not until after investigation)
- Configure the Google Chat app (Phase 0 task #X)
- Write guardrails (Phase 2)

Stay focused on the investigation. Build comes after we know what we're building for.
