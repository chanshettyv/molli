# Runbook

Operational procedures for Molli. Filled in incrementally — each new operational concern adds a section here.

## Local development

### Windows / PowerShell gotcha: `curl` vs `curl.exe`

On Windows, PowerShell maps `curl` to `Invoke-WebRequest`, which does not accept
the standard `-X`, `-H`, or `-d` flags. Any `curl` command in this repo's docs or
task descriptions will fail with "parameter cannot be found" errors.

**Fix:** use `curl.exe` explicitly to invoke the real curl binary instead:

```powershell
# Health check
curl.exe http://localhost:8080/healthz

# Send a fake Chat event
curl.exe -X POST http://localhost:8080/ -H "Content-Type: application/json" -d '{"type":"MESSAGE"}'
```

This applies everywhere in the docs — any `curl` command should be run as `curl.exe`
on Windows. Linux/macOS users are unaffected.

### First-time setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install gcloud
# https://cloud.google.com/sdk/docs/install

# Auth
gcloud auth login
gcloud auth application-default login
gcloud config set project molli-dev

# Install Python deps
cd molli
uv sync

# Run the chat service
cd chat-service
uv run uvicorn app.main:app --reload --port 8080
```

### Running tests

```bash
uv run pytest
uv run pytest chat-service/tests        # one package
uv run pytest -k "test_healthz"          # by name
```

## Secrets

All secrets live in GCP Secret Manager. Names:

| Secret | Used by |
|---|---|
| `document360-api-key` | sync-job |
| `freshservice-api-key` | chat-service |
| `google-chat-signing-secret` | chat-service |

Rotation procedure: TBD (Sidney to document in Phase 0).

## Deploys

CI/CD via GitHub Actions. See `.github/workflows/`.

- Push to `main` with changes under `chat-service/**` -> deploys chat-service to Cloud Run.
- Push to `main` with changes under `sync-job/**` -> deploys the Cloud Run job (next scheduled run picks up new image).
- Manual deploy: `workflow_dispatch` on each workflow.

## Incident response

TBD.

## Sync job operations

TBD — how to manually trigger, how to inspect last successful run, how to backfill.
