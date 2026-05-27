# Infrastructure

Terraform-managed GCP resources for Molli.

## Layout

- `terraform/main.tf` — provider, variables, backend
- `terraform/cloud_run.tf` — chat-service and sync-job (Phase 1)
- `terraform/vector_search.tf` — Vertex AI Vector Search index + endpoint (Phase 1)
- `terraform/secrets.tf` — Secret Manager secret definitions (Phase 0)
- `terraform/iam.tf` — service accounts and role bindings (Phase 0)

## First-time setup

```bash
cd infra/terraform
gcloud auth application-default login
terraform init
terraform workspace new dev
terraform plan -var="project_id=molli-dev" -var="environment=dev"
```

## State

Stored in a GCS bucket per environment. Configure `backend "gcs"` in `main.tf` before the first apply. Bootstrap procedure: create the bucket manually once, then `terraform init -migrate-state`.
