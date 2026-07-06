"""Gmail API client for sending escalation notification emails.

Uses a Google service account with domain-wide delegation (DWD) so the
Cloud Run service can send email as a Workspace address (e.g. molli@preiss.com)
without a user ever being logged in.

Setup required (one-time, done in GCP + Google Admin Console):
  1. Enable the Gmail API on the GCP project.
  2. Enable domain-wide delegation on the Cloud Run service account in
     GCP Console → IAM → Service Accounts → [SA] → Edit → Enable DWD.
  3. In Google Admin Console → Security → API Controls → Domain-wide
     delegation, add the SA client ID with scope:
       https://www.googleapis.com/auth/gmail.send
  4. Create a service account key (JSON) for the SA, store it in
     Secret Manager under the name referenced by GMAIL_SA_SECRET_NAME.

The send_email() method is synchronous — the Gmail API client (googleapiclient)
is not async. Call it via FastAPI BackgroundTasks so it runs in a thread pool
and never blocks the event loop.
"""

from __future__ import annotations

import base64
import json
import logging
from email.mime.text import MIMEText
from typing import Any

log = logging.getLogger(__name__)

_GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class GmailClient:
    """Sends email via the Gmail API using a service account with DWD.

    Args:
        sender_email: The Workspace address to send as (e.g. molli@preiss.com).
                      Must be within the domain that authorised the SA for DWD.
        sa_key_info:  Parsed JSON dict of the service account key downloaded
                      from GCP. Load from Secret Manager at startup and pass in.
    """

    def __init__(self, *, sender_email: str, sa_key_info: dict[str, Any]) -> None:
        self._sender_email = sender_email
        self._sa_key_info = sa_key_info
        self._service: Any = None  # lazy-loaded

    def _get_service(self) -> Any:
        if self._service is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build  # type: ignore[import-untyped]

            creds = service_account.Credentials.from_service_account_info(
                self._sa_key_info,
                scopes=[_GMAIL_SEND_SCOPE],
            ).with_subject(self._sender_email)

            # cache_discovery=False avoids a filesystem write in Cloud Run.
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def send_email(self, *, to: str, subject: str, body: str) -> None:
        """Send a plain-text email. Raises on failure — callers should catch."""
        msg = MIMEText(body)
        msg["to"] = to
        msg["from"] = self._sender_email
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        self._get_service().users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        log.info("gmail_sent", to=to, subject=subject)
