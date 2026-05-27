"""Config loader.

Non-secret config from env vars; secrets from GCP Secret Manager.
"""

from __future__ import annotations

import os
from functools import lru_cache

from google.cloud import secretmanager
from pydantic import BaseModel


class Settings(BaseModel):
    gcp_project_id: str
    gcp_region: str = "us-central1"
    environment: str = "dev"  # dev or prod
    document360_secret_name: str = "document360-api-key"
    freshservice_api_secret_name: str = "freshservice-api-key"
    freshservice_domain: str
    vector_index_endpoint: str | None = None
    firestore_database: str = "(default)"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        gcp_project_id=os.environ["GCP_PROJECT_ID"],
        gcp_region=os.environ.get("GCP_REGION", "us-central1"),
        environment=os.environ.get("ENVIRONMENT", "dev"),
        freshservice_domain=os.environ.get("FRESHSERVICE_DOMAIN", "preiss"),
        vector_index_endpoint=os.environ.get("VECTOR_INDEX_ENDPOINT"),
    )


def get_secret(secret_name: str, project_id: str, version: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")
