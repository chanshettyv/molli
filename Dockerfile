# Cloud Run job image for the Molli Document360 -> Vector Search sync job.
# Build context is the repo root so the uv workspace (sync-job + shared) is
# available; the job imports molli_shared.
FROM python:3.12-slim

# uv for fast, reproducible installs from the committed uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy workspace manifests + lockfile first for layer caching
COPY pyproject.toml uv.lock ./
COPY sync-job/pyproject.toml ./sync-job/
COPY shared/pyproject.toml ./shared/

# Copy the source for the two packages this job actually needs.
# chat-service is a workspace member but irrelevant here, so it is NOT copied
# and NOT installed (installing --all-packages would fail looking for it).
COPY shared/ ./shared/
COPY sync-job/ ./sync-job/

# Install only the sync-job package (and its deps, incl. the local molli-shared)
# from the frozen lockfile. --package scopes the install to one workspace member.
RUN uv sync --frozen --package sync-job

# Run the sync job. Cloud Run jobs run this to completion (not a server).
ENTRYPOINT ["uv", "run", "--package", "sync-job", "python", "-m", "sync_job.main"]