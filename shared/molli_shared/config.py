"""Config loader.

Non-secret config from env vars; secrets from GCP Secret Manager.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from google.cloud import secretmanager
from pydantic import BaseModel


class Settings(BaseModel):
    gcp_project_id: str
    gcp_project_number: str
    gcp_region: str = "us-central1"
    environment: str = "dev"  # dev or prod
    document360_secret_name: str = "document360-api-key"
    freshservice_api_secret_name: str = "freshservice-api-key"
    freshservice_domain: str  # e.g. "tpco-org" — see freshservice_base_url
    vector_index_endpoint: str | None = None
    firestore_database: str = "(default)"

    @property
    def freshservice_base_url(self) -> str:
        """Full base URL for Freshservice API.

        Constructed from the per-tenant domain. The custom support portal
        domain (support.preisscentral.com) is UI-only and does NOT serve the
        API — confirmed during the Postman spike. Always use the underlying
        *.freshservice.com hostname.
        """
        return f"https://{self.freshservice_domain}.freshservice.com/api/v2"


@lru_cache
def get_settings() -> Settings:
    load_dotenv()  # only reads .env on first call, so safe to call multiple times
    return Settings(
        gcp_project_id=os.environ["GCP_PROJECT_ID"],
        gcp_project_number=os.environ["GCP_PROJECT_NUMBER"],
        gcp_region=os.environ.get("GCP_REGION", "us-central1"),
        environment=os.environ.get("ENVIRONMENT", "dev"),
        freshservice_domain=os.environ.get("FRESHSERVICE_DOMAIN", "tpco-org"),
        vector_index_endpoint=os.environ.get("VECTOR_INDEX_ENDPOINT"),
    )


def get_secret(secret_name: str, project_id: str, version: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")
