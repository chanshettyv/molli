# Contributing to Molli

## Team and ownership

| Area | Primary | Backup |
|---|---|---|
| `chat-service/` (Gemini, RAG, Chat events) | Kautilya | Vedant |
| `sync-job/` (Document360 -> Vector Search) | Kautilya | Sidney |
| `shared/clients/freshservice.py` | Vedant | Kautilya |
| `shared/clients/google_chat.py` | Vedant | Kautilya |
| `shared/clients/document360.py` | Kautilya | Vedant |
| `shared/guardrails/` (FCRA, FHA, OSHA, MH, DLP) | Sidney | Vedant |
| `infra/` (Terraform, IAM, secrets) | Sidney | Vedant |
| `.github/workflows/` (CI/CD) | Sidney | Kautilya |
| `docs/` | Vedant | all |

Anyone can edit anywhere. `CODEOWNERS` just routes review requests.

## Sprint cadence

- **Sprint length**: 2 weeks, starts Monday.
- **Standup**: 10 minutes, weekdays, fixed time (TBD).
- **Sprint planning**: Monday of sprint start, ~45 minutes. Estimate new issues, pull from backlog into the sprint.
- **Sprint review and retro**: Friday of sprint end, ~30 minutes. Demo, then what went well / what to change.
- **Grooming**: anytime mid-sprint; clean up the backlog, write acceptance criteria for upcoming issues.

## Definition of Ready (DoR)

An issue can enter a sprint when:

1. It has a clear acceptance criteria checklist.
2. It is sized (story points or T-shirt).
3. Dependencies are linked or noted as none.
4. The owner role is set on the project board (AI-Backend / Integrations / Security-QA).

## Definition of Done (DoD)

A task is done when:

1. Code is merged to `main` via PR.
2. Tests pass in CI (unit + integration where applicable).
3. New code has tests; coverage for the touched package does not drop.
4. Docs updated if behavior changed (`README`, runbook, or relevant `docs/*`).
5. If the change touches a guardrail, Sidney has reviewed.
6. If the change touches infra, the Terraform plan was posted in the PR.

## Branching and PRs

- Branch from `main`. Name: `<role>/<issue-number>-short-description`.
  - Examples: `backend/42-add-rag-citations`, `integrations/57-freshservice-create-ticket`, `security/63-dlp-pii-scan`.
- Reference the issue in the PR description: `Closes #42`.
- Keep PRs small (< 400 lines diff is the target). Split if larger.
- At least one approval required before merge. Auto-merge enabled once checks pass.
- Squash merge to keep `main` history linear.

## Commit messages

Conventional Commits:
```
feat: add Gemini function calling for kb search
fix(sync-job): handle d360 pagination correctly
chore: bump pydantic to 2.x
docs: update runbook with secret rotation steps
test: add guardrail unit tests for FCRA refusal
```

## Local dev

Use `uv` (https://docs.astral.sh/uv/).

```bash
uv sync                          # at the repo root, installs everything
uv run pytest                    # run all tests
uv run ruff check .              # lint
uv run ruff format .             # format
uv run mypy chat-service shared  # type check
```

Pre-commit runs `ruff check --fix` and `ruff format` on staged files. Install once with `pre-commit install`.

## Asking for help

Tag the area owner from the table above in the PR or issue. For architecture questions, drop a thread in the team Chat space.
