# Runbook

Operational reference for Molli. Covers where things live, how to do common operational tasks (deploys, secret rotation, debugging), and known gotchas. Not a tutorial — for *how* the system was put together, see `docs/architecture.md` (system shape) and `docs/gcp-setup.md` (foundational GCP setup).

This is a living document. The project is mid-Sprint-1; the runbook reflects what's actually in place today and is explicit about what isn't.

---

## Quick reference

| What | Where |
|---|---|
| GitHub repo | `github.com/chanshettyv/molli` |
| Project board | linked from the repo's Projects tab |
| GCP dev project | `molli-dev` |
| GCP prod project | `molli-prod` (provisioned; no deploys yet) |
| Architecture overview | `docs/architecture.md` |
| Foundational GCP setup | `docs/gcp-setup.md` |
| Day-1 dev setup | `docs/day-1-setup.md` |
| Ticket investigation findings | `docs/ticket-investigation.md` |
| Guardrails spec | `docs/guardrails-design.md` |
| Guardrail eval prompts | `docs/guardrail-eval-prompts.md` |
| Code ownership | `.github/CODEOWNERS` |
| Contribution rules (branch naming, DoR/DoD) | `CONTRIBUTING.md` |

---

## Local development

**Prerequisites:** Python 3.12+, `uv`, `gcloud` CLI (for any GCP task), and a clone of the repo.

**First-time setup:**

```bash
git clone https://github.com/chanshettyv/molli.git
cd molli
bash scripts/bootstrap.sh
```

The bootstrap script installs dependencies via `uv` (with `--all-packages` to include workspace members), configures pre-commit hooks, and copies `.env.example` to `.env`.

**Day-to-day commands:**

```bash
uv run pytest                                                       # all tests
uv run ruff check . --fix                                           # lint + auto-fix
uv run mypy chat-service shared                                     # type check
cd chat-service && uv run uvicorn app.main:app --reload --port 8080 # run chat-service locally
```

---

## GCP environments

Two projects exist. Both have the same foundational setup per `docs/gcp-setup.md`; they differ in what's wired beyond that.

| Project | Purpose | State |
|---|---|---|
| `molli-dev` | Development, spikes, integration testing | Service accounts, IAM, empty secrets, WIF all configured |
| `molli-prod` | Production | Service accounts, IAM, empty secrets configured. WIF not yet set up. No deploys yet. |

Switch active project before running commands:

```bash
gcloud config set project molli-dev
gcloud config list   # confirm
```

The active project also appears in the Cloud Shell prompt as `(project-id)`. Glance at it before running anything destructive — many "not found" errors are really "wrong project" errors.

---

## Secrets

Full setup and rationale in `docs/gcp-setup.md`. Operational summary:

Three secrets per project, all currently empty pending SME and Document360 conversations:

| Secret | Read by |
|---|---|
| `document360-api-key` | `chat-service`, `sync-job` |
| `freshservice-api-key` | `chat-service` |
| `google-chat-signing-secret` | `chat-service` |

Access is granted per-secret on the secret resource, never at the project level. Run `gcloud secrets get-iam-policy <name>` to see who can read a specific secret.

### Reading a value

Requires `roles/secretmanager.secretAccessor` on the specific secret:

```bash
gcloud secrets versions access latest --secret=document360-api-key
```

### Populating an empty secret or rotating a value

```bash
echo -n "the-new-value" | gcloud secrets versions add <secret-name> --data-file=-
```

The previous version stays accessible until explicitly disabled — rollback is `gcloud secrets versions disable <version> --secret=<name>` and the app picks up the previous version on the next read of `latest`.

### Adding a new secret

1. `gcloud secrets create <name>`
2. Grant `roles/secretmanager.secretAccessor` per-secret to only the runtime SAs that need it. Do **not** grant `secretAccessor` at the project level.
3. Document the new secret in `docs/gcp-setup.md` and add a row to the table above.

---

## Deploys

**Current state: triggers are live but will fail.** `.github/workflows/deploy-chat-service.yml` and `.github/workflows/deploy-sync-job.yml` fire on every push to `main` that touches their respective path patterns. Both target `molli-prod`, which does not yet have WIF configured — any triggered run will fail at the auth step. Until prod WIF is in place, avoid merging to `main` changes that would trigger these workflows, or be prepared for failed runs in the Actions tab.

### Authentication

GitHub Actions authenticates to GCP via Workload Identity Federation. No JSON service-account keys exist anywhere — short-lived OIDC tokens only. The trust chain is documented in `docs/gcp-setup.md` section 4.

Required GitHub repo secrets (set in repo settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `GCP_WIF_PROVIDER` | Full provider resource name (`projects/<NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider`) |
| `GCP_DEPLOY_SA` | `molli-ci-deploy@molli-dev.iam.gserviceaccount.com` |
| `GCP_RUNTIME_SA` | `molli-chat-service@molli-dev.iam.gserviceaccount.com` |

### Verifying WIF works

A `workflow_dispatch` workflow at `.github/workflows/test-wif.yml` proves the auth chain end to end. Run it from the Actions tab whenever WIF config changes or secrets are rotated. A successful run prints `molli-ci-deploy@molli-dev.iam.gserviceaccount.com` as the active account.

### Before the first prod deploy

Three pieces need to land:

1. **Prod WIF setup.** Mirror `docs/gcp-setup.md` section 4 with `PROJECT_ID=molli-prod`.
2. **Prod GitHub secrets.** Either three new repo secrets (`GCP_WIF_PROVIDER_PROD` etc.) or — preferred — GitHub Actions environments (`dev`, `prod`) with environment-scoped secrets so the same secret name resolves differently per environment.
3. **Branch protection.** Restrict the prod deploy workflow's principal-set binding to `refs/heads/main` so feature branches can't deploy to prod.

---

## Troubleshooting

### Pre-commit hooks

Pre-commit runs automatically on `git commit`. Most failures explain themselves; a few have non-obvious fixes.

**`end-of-file-fixer` loops forever.** The hook fixes the file on disk but doesn't re-stage it, so the next commit attempt sees the same broken staged version. Fix: `git add <file>` after the hook runs, then commit again. `git add -u && git commit -m "..."` re-stages all tracked changes in one go.

**`ruff` complains about line length over 100 chars.** Repo limit is 100. For long string literals, split into adjacent literals — Python concatenates them at parse time:

```python
f"[yellow]Hit 429 at call {i}. "
f"Retry-After: {response.headers.get('Retry-After')!r}[/yellow]"
```

**Line-ending warnings on Windows (`LF will be replaced by CRLF`).** Harmless. Git stores LF in the repo; Windows working copies get CRLF on checkout. If they're noisy, the repo's `.gitattributes` pins endings explicitly (PowerShell/batch as CRLF, everything else LF).

### gcloud

**"NOT_FOUND: Requested entity was not found"** after a `describe` or `list`. Almost always the wrong active project. `gcloud config list` shows the current project; switch with `gcloud config set project <id>`. The Cloud Shell prompt shows the active project in parentheses — glance at it.

**"API not enabled" errors.** Full API list lives in `docs/gcp-setup.md`. Enable a missing one with:

```bash
gcloud services enable <api-name>.googleapis.com
```

Wait 30 seconds for propagation before retrying. The easy ones to miss: `iamcredentials.googleapis.com` (required for WIF) and `cloudresourcemanager.googleapis.com` (required by `gcloud projects describe`).

### WIF / GitHub Actions auth

**`google-github-actions/auth@v2` fails with "unauthorized_client" or permission denied.** The OIDC token was rejected by the WIF provider. Likely causes, in order:

- Typo in the `GCP_WIF_PROVIDER` repo secret. Project *number* (not ID), no whitespace, no trailing slash.
- Attribute condition rejecting the org name. Case-sensitive: `chanshettyv`, not `Chanshettyv`.
- Principal-set binding on `molli-ci-deploy` doesn't include this repo. Inspect with:

  ```bash
  gcloud iam service-accounts get-iam-policy \
    molli-ci-deploy@molli-dev.iam.gserviceaccount.com
  ```

  Look for a `workloadIdentityUser` binding whose member contains `attribute.repository/chanshettyv/molli`.

**`permissions: id-token: write` missing.** The workflow needs:

```yaml
permissions:
  id-token: write
  contents: read
```

at the **top level** of the workflow, not nested inside `jobs:`. Without it, GitHub refuses to mint an OIDC token and the auth step fails before reaching GCP.

**`gcloud auth list` shows "No credentialed accounts" inside an otherwise-successful auth step.** Misleading — auth succeeded but `gcloud auth list` doesn't understand the federated credential file format. The presence of `gha-creds-*.json` in the log confirms auth worked. Verify the impersonated identity with:

```bash
gcloud auth list --filter=status:ACTIVE --format="value(account)"
```

---

## Known issues at the time of writing

Mirrored from section 9 of the project context doc; updated as items resolve.

- **Deploy workflows target `molli-prod` but prod WIF is not yet set up.** Any push to `main` touching `chat-service/`, `sync-job/`, or `shared/` will trigger a deploy run that fails at the auth step. Set up prod WIF (mirror `docs/gcp-setup.md` section 4 with `PROJECT_ID=molli-prod`) before those merges land.
- **`google-github-actions/auth@v2` runs on Node 20** — URGENT. GitHub enforces Node 24 on **June 2, 2026** (4 days away) and removes Node 20 on September 16, 2026. Bump `google-github-actions/auth` and `google-github-actions/setup-gcloud` to their current major versions in all three workflow files immediately.
- **Travtus chatbot exists at Preiss** for resident-facing chat. Relationship and possible overlap with Molli unclear — Lane or Toni should clarify.
- **Freshservice intake form is too coarse.** 12% of tickets (212 of 1,700) land in "Other"/"Something Else" buckets. Worth discussing with Adam whether the form can be revised in parallel with Molli rollout.

---

## When in doubt

- **Architecture question:** `docs/architecture.md`, then the implementation plan PDF.
- **Guardrail behavior or trigger question:** `docs/guardrails-design.md` for the spec, `docs/guardrail-eval-prompts.md` for test cases.
- **Process question (sprint cadence, branch naming, DoR/DoD):** `CONTRIBUTING.md`.
- **Setup problem on a fresh machine:** `docs/day-1-setup.md`, then this runbook.
- **What am I supposed to be working on:** the project board's Current Sprint view, filtered to your assignee.
- **Who owns this area:** `.github/CODEOWNERS`.
- **What did the ticket investigation say about X:** `docs/ticket-investigation.md`.
- **Real ambiguity:** ask in the team Chat space rather than guessing.

## Vector Search provisioning (molli-dev)

Vertex AI Vector Search is the vector backend (per superior's direction; no decision
doc was written). These steps provision the index + endpoint in `molli-dev` and are
reproducible for `molli-prod` at launch time.

### Current resource IDs (molli-dev)

| Resource | ID |
|---|---|
| Index | `3890822006001631232` |
| Index endpoint | `5864348620836306944` |
| Deployed index ID | `molli_knowledge_stream` |
| Public endpoint domain | `163164439.us-central1-719635778769.vdb.vertexai.goog` |
| Region | `us-central1` |

These are stored in `.env` as `VECTOR_INDEX_ID` and `VECTOR_INDEX_ENDPOINT` and loaded
via `shared/molli_shared/config.py`. The public endpoint domain is needed for queries
(see gotcha below) � record it when provisioning prod.

### Provisioning steps

All commands run in Cloud Shell with `gcloud config set project molli-dev`.

1. Create the index � use `stream-update` from the start. Build a metadata file with
   `dimensions: 768` (matches text-embedding-004), `SHARD_SIZE_SMALL`,
   `DOT_PRODUCT_DISTANCE`, then `gcloud ai indexes create` with
   `--index-update-method=stream-update`. Takes ~30 min.

2. Create the index endpoint with `gcloud ai index-endpoints create`.

3. Deploy the index to the endpoint with `gcloud ai index-endpoints deploy-index`,
   using `--deployed-index-id=molli_knowledge_stream` and
   `--machine-type=n1-standard-16`. Takes ~30 min. Confirm with
   `gcloud ai index-endpoints describe` and look for an `indexSyncTime`.

4. Verify with `uv run python scripts/spikes/vector_search_test.py` � it upserts
   `test-doc-001` and retrieves it as the nearest neighbor.

### Gotchas hit during molli-dev provisioning

- Use `stream-update`, not the default `batch-update`. `upsert_datapoints` (the
  streaming API the sync job uses) requires `STREAM_UPDATE`; batch mode gives
  `FAILED_PRECONDITION: StreamUpdate is not enabled on this index`. Fixing it after
  the fact means undeploy ? delete ? recreate ? redeploy (~1 hr).

- `us-central1` ran out of capacity on first deploy (`Not enough resources available`).
  A retry later succeeded; if it persists, try another region or escalate to Adam.

- `e2-standard-2` is not valid for `SHARD_SIZE_MEDIUM` � medium shards need a larger
  machine. We used `SHARD_SIZE_SMALL` for dev, which is cheaper and sufficient.

- Queries must hit the endpoint's `publicEndpointDomainName`, not the regional API
  host. Upserts use `{region}-aiplatform.googleapis.com`, but `find_neighbors` queries
  must target the public domain. Using the regional host for queries returns
  `501 Operation is not implemented, or supported, or enabled`.

### Cost note

A deployed index endpoint runs `n1-standard-16` replicas 24/7 and bills even when idle.
For dev, undeploy the index when not actively testing:

    gcloud ai index-endpoints undeploy-index <ENDPOINT_ID> \
      --deployed-index-id=molli_knowledge_stream \
      --region=us-central1 --project=molli-dev

Redeploying takes ~30 min, so weigh idle cost vs. convenience.
