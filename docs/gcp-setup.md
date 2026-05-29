# GCP setup — service accounts, secrets, and CI authentication

Documents the foundational GCP setup for Molli: the three service accounts, the secrets they consume, and the Workload Identity Federation (WIF) configuration that lets GitHub Actions deploy without a long-lived JSON key.

Owner: Sidney. Sprint 1 ticket: *"Set up service accounts, IAM, Secret Manager, WIF"*.

Both `molli-dev` and `molli-prod` follow the same structure. WIF is configured only in `molli-dev` for now — prod WIF will be added before the first production deploy.

---

## 1. Service accounts

Three identities, each with a narrow job. The split exists so that a compromise of one component (the chat service, the sync job, or the CI pipeline) does not inherit permissions the other components have. Project-level admin and full-secret access deliberately do not appear on any of these accounts.

| Account | Email | Used by | What it does |
|---|---|---|---|
| Chat service runtime | `molli-chat-service@<project>.iam.gserviceaccount.com` | Cloud Run service `chat-service` | Serves live Google Chat traffic. Reads three secrets, reads/writes Firestore conversation memory, calls Vertex AI (Gemini + Vector Search). |
| Sync job runtime | `molli-sync-job@<project>.iam.gserviceaccount.com` | Cloud Run job `sync-job` | Runs the nightly Document360 → Vector Search sync. Reads one secret, writes embeddings to Vector Search. No Firestore access, no Freshservice access. |
| CI deploy | `molli-ci-deploy@<project>.iam.gserviceaccount.com` | GitHub Actions, via WIF | Builds container images, pushes them to Artifact Registry, deploys new Cloud Run revisions. Acts as the two runtime accounts during deploy but does not have their runtime permissions. |

---

## 2. IAM roles granted

Roles are deliberately scoped as narrowly as the resource allows. Vertex AI and Firestore do not have useful resource-level scoping for our use case, so those are project-wide. Secret Manager scoping is per-secret (see section 3). Service-account impersonation is bound on the target SA, not at the project level.

### Chat service runtime

| Scope | Role | Why |
|---|---|---|
| Project | `roles/aiplatform.user` | Gemini calls and Vector Search reads |
| Project | `roles/datastore.user` | Firestore reads/writes for conversation memory (role name predates the Firestore rebrand) |
| Per-secret | `roles/secretmanager.secretAccessor` on `document360-api-key`, `freshservice-api-key`, `google-chat-signing-secret` | Runtime secret reads |

### Sync job runtime

| Scope | Role | Why |
|---|---|---|
| Project | `roles/aiplatform.user` | Vector Search writes |
| Per-secret | `roles/secretmanager.secretAccessor` on `document360-api-key` | Read the D360 API key |

Notably absent: Firestore (the sync job has no business reading conversation memory) and the other two secrets.

### CI deploy

| Scope | Role | Why |
|---|---|---|
| Project | `roles/run.admin` | Deploy and update Cloud Run services and jobs |
| Project | `roles/artifactregistry.writer` | Push container images |
| On `molli-chat-service` | `roles/iam.serviceAccountUser` | Allow this deployer to set chat-service as the runtime SA when creating a new revision |
| On `molli-sync-job` | `roles/iam.serviceAccountUser` | Same, for the sync job |

The CI account does **not** have Vertex AI, Firestore, or any secret-read permissions. It can deploy code that runs as the runtime accounts, but it cannot itself read the secrets that code uses. This is the trust boundary that matters most — if the CI workflow is ever compromised, the attacker can push and deploy code, but they cannot directly exfiltrate API keys.

---

## 3. Secret Manager

Three empty secrets exist in each project, created with no initial value. Values are populated after SME interviews establish the real API credentials.

| Secret | Populated by | Used by |
|---|---|---|
| `document360-api-key` | Vedant (after Aswin issues the key) | chat-service + sync-job |
| `freshservice-api-key` | Vedant (after Adam confirms the integration user) | chat-service only |
| `google-chat-signing-secret` | Vedant (from Google Chat app registration) | chat-service only |

Access is granted **per-secret on the secret resource**, not as a project-level role. This means:

- Listing IAM on each secret with `gcloud secrets get-iam-policy <name>` shows exactly who can read it.
- If a new secret is added to the project in the future, no existing service account can read it until access is granted explicitly. That is the intended behavior.

---

## 4. Workload Identity Federation

WIF replaces long-lived JSON service account keys with short-lived OIDC tokens that GitHub mints and GCP trusts. The trust chain:

1. A GitHub Actions workflow starts and mints an OIDC token identifying the repo, ref, and workflow.
2. The workflow exchanges the OIDC token for a GCP access token by impersonating `molli-ci-deploy`.
3. GCP verifies the token's GitHub signature and checks the attribute condition before issuing the GCP token.
4. The GCP token expires in roughly one hour. Nothing long-lived ever existed.

### Pool and provider

Configured in `molli-dev` only:

| Resource | Value |
|---|---|
| Pool | `github-pool` (location: `global`) |
| Provider | `github-provider`, OIDC issuer `https://token.actions.githubusercontent.com` |
| Attribute mapping | `google.subject=assertion.sub`, `attribute.repository=assertion.repository`, `attribute.repository_owner=assertion.repository_owner`, `attribute.ref=assertion.ref` |
| Attribute condition | `assertion.repository_owner == 'chanshettyv'` |

The attribute condition is a hard gate that rejects any OIDC token where the repo owner is not `chanshettyv`. Without it, any GitHub repository on the internet could attempt to exchange tokens against this provider, leaving security to rest entirely on the SA-level binding below. The condition is required by recent GCP safety checks when `google.subject` is mapped.

### Service account binding

`molli-ci-deploy` has `roles/iam.workloadIdentityUser` granted to the principal set:

```
principalSet://iam.googleapis.com/projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-pool/attribute.repository/chanshettyv/molli
```

This restricts impersonation to workflows running in the `chanshettyv/molli` repo specifically. The attribute-condition restricts to the org; the principal set restricts further to the repo. If we later add a sibling repo that also needs to deploy, it gets its own binding — this is intentional, deploy access is granted per repo, not inherited.

The principal set is currently repo-scoped (any branch). Locking it further to `refs/heads/main` would require swapping `attribute.repository/...` for `attribute.ref/refs/heads/main` in the principalSet string, but our CI runs on PR branches and that would break it.

---

## 5. GitHub Actions secrets

Three repository secrets at `https://github.com/chanshettyv/molli/settings/secrets/actions`:

| Secret name | Value |
|---|---|
| `GCP_WIF_PROVIDER` | `projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `GCP_DEPLOY_SA` | `molli-ci-deploy@molli-dev.iam.gserviceaccount.com` |
| `GCP_RUNTIME_SA` | `molli-chat-service@molli-dev.iam.gserviceaccount.com` |

These are repo secrets, not environment secrets. The deploy workflows reference them as `${{ secrets.GCP_WIF_PROVIDER }}` etc. The previously-disabled deploy workflows can be re-enabled once these three secrets are populated and the verification step below passes.

---

## 6. Verifying the setup

A minimal `workflow_dispatch` workflow proves the auth chain works without needing the full deploy pipeline:

```yaml
name: test-wif
on:
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WIF_PROVIDER }}
          service_account: ${{ secrets.GCP_DEPLOY_SA }}
      - name: Confirm identity
        run: |
          gcloud auth list
          gcloud projects describe molli-dev --format="value(projectId)"
```

A successful run prints `molli-ci-deploy@molli-dev.iam.gserviceaccount.com` and `molli-dev`. Common failure modes:

- *"unauthorized_client" / permission denied* — the attribute condition rejected the token. Almost always a case-sensitive typo in the org name.
- *"Failed to generate Google Cloud federated token"* — the principal-set binding does not match. Re-check repo name, project number, and pool name in the principalSet string.
- *Token request failed* — the workflow is missing `permissions: id-token: write`.

---

## 7. How to rotate or extend

**Adding a new secret.** Create the empty secret (`gcloud secrets create <name>`), then grant per-secret access only to the runtime SAs that need it. Do not grant project-wide `secretAccessor`. Add the secret to this document.

**Adding a new runtime service account.** Create the SA, grant only the project-level roles it needs, and grant `roles/iam.serviceAccountUser` on the new SA to `molli-ci-deploy` so deploys can set it as a Cloud Run runtime.

**Rotating a secret value.** Create a new version in Secret Manager (`gcloud secrets versions add <name> --data-file=-`) and set the application to reference `latest`. The previous version stays accessible until explicitly disabled, which makes rollback trivial.

**Removing a CI repo's access.** Delete the `iam.workloadIdentityUser` binding on `molli-ci-deploy` that names that repo's principal set. The repo's workflows immediately stop being able to authenticate as the deploy SA; nothing else is affected.

**Setting up prod WIF.** Repeat section 4 with `PROJECT_ID=molli-prod`, then add three new repo secrets in GitHub (`GCP_WIF_PROVIDER_PROD`, `GCP_DEPLOY_SA_PROD`, `GCP_RUNTIME_SA_PROD`) and gate the prod deploy workflow on `main`-only triggers.

---

## 8. Reference: full setup as a script

The complete setup for one project, captured as a script that takes the project ID as an argument. Idempotent for the pieces that support it; for the rest, errors on re-run are expected and safe to ignore (they mean the resource already exists).

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:?usage: setup_gcp_project.sh <project-id>}"
GITHUB_ORG="chanshettyv"
GITHUB_REPO="molli"

gcloud config set project "${PROJECT_ID}"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")

CHAT_SA="molli-chat-service@${PROJECT_ID}.iam.gserviceaccount.com"
SYNC_SA="molli-sync-job@${PROJECT_ID}.iam.gserviceaccount.com"
CI_SA="molli-ci-deploy@${PROJECT_ID}.iam.gserviceaccount.com"

# --- APIs ---
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  secretmanager.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  firestore.googleapis.com

# --- Service accounts ---
gcloud iam service-accounts create molli-chat-service \
  --display-name="Molli chat service (Cloud Run runtime)" || true
gcloud iam service-accounts create molli-sync-job \
  --display-name="Molli sync job (Cloud Run job runtime)" || true
gcloud iam service-accounts create molli-ci-deploy \
  --display-name="Molli CI deploy (GitHub Actions)" || true

# --- Project-level role bindings ---
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CHAT_SA}" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CHAT_SA}" --role="roles/datastore.user"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SYNC_SA}" --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CI_SA}" --role="roles/run.admin"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CI_SA}" --role="roles/artifactregistry.writer"

# --- CI can act as runtime SAs ---
gcloud iam service-accounts add-iam-policy-binding "${CHAT_SA}" \
  --member="serviceAccount:${CI_SA}" --role="roles/iam.serviceAccountUser"
gcloud iam service-accounts add-iam-policy-binding "${SYNC_SA}" \
  --member="serviceAccount:${CI_SA}" --role="roles/iam.serviceAccountUser"

# --- Secrets (empty) ---
for SECRET in document360-api-key freshservice-api-key google-chat-signing-secret; do
  echo -n "" | gcloud secrets create "${SECRET}" --data-file=- || true
done

# --- Per-secret access ---
for SECRET in document360-api-key freshservice-api-key google-chat-signing-secret; do
  gcloud secrets add-iam-policy-binding "${SECRET}" \
    --member="serviceAccount:${CHAT_SA}" \
    --role="roles/secretmanager.secretAccessor"
done

gcloud secrets add-iam-policy-binding document360-api-key \
  --member="serviceAccount:${SYNC_SA}" \
  --role="roles/secretmanager.secretAccessor"

# --- WIF (dev only; comment out for prod until ready) ---
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name="GitHub Actions pool" || true

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub OIDC provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}'" \
  --issuer-uri="https://token.actions.githubusercontent.com" || true

gcloud iam service-accounts add-iam-policy-binding "${CI_SA}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}"

echo
echo "Setup complete for ${PROJECT_ID}."
echo
echo "GitHub repo secrets to set:"
echo "  GCP_WIF_PROVIDER = projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo "  GCP_DEPLOY_SA    = ${CI_SA}"
echo "  GCP_RUNTIME_SA   = ${CHAT_SA}"
```

Save as `scripts/setup_gcp_project.sh` and run with `bash scripts/setup_gcp_project.sh molli-dev`. Comment out the WIF block when running against prod until prod WIF is intentionally set up.
