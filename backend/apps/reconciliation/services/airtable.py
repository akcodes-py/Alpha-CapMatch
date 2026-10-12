import logging
import os
from typing import Any, Iterable

import requests

from ..models import AirtableSyncStatus, BankTransaction, TransactionStatus

logger = logging.getLogger(__name__)


class AirtableClient:
    """Client for creating records in Airtable."""

    def __init__(
        self,
        api_key: str | None = None,
        base_id: str | None = None,
        table_name: str | None = None,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("AIRTABLE_API_KEY")
            or os.getenv("AIRTABLE_PERSONAL_ACCESS_TOKEN")
            or ""
        )
        self.base_id = base_id or os.getenv("AIRTABLE_BASE_ID") or ""
        self.table_name = table_name or os.getenv("AIRTABLE_TABLE_NAME") or "Needs Review"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_id)

    def create_record(self, fields: dict[str, Any]) -> str:
        """Create a record in the configured Airtable table.
        
        Returns the created record ID (e.g. 'rec12345').
        """
        if not self.is_configured:
            raise ValueError("Airtable client is not configured (missing API key or Base ID)")

        url = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, json={"fields": fields}, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("id", "")


def sync_needs_review_transactions(
    transactions: Iterable[BankTransaction],
    client: AirtableClient | None = None,
) -> None:
    """Sync newly imported needs_review transactions to Airtable.
    
    Per spec:
    - Only creates records for transactions with status 'needs_review'.
    - Stores record ID and status ('synced' or 'sync_failed').
    - Any failure must NEVER break the import (errors are caught and logged).
    """
    if client is None:
        client = AirtableClient()

    if not client.is_configured:
        return

    for tx in transactions:
        if tx.status != TransactionStatus.NEEDS_REVIEW:
            continue
        try:
            fields = {
                "Bank Reference": tx.bank_reference,
                "Date": str(tx.date),
                "Description": tx.description,
                "Amount": float(tx.amount),
                "Reason": tx.reason or "",
                "Organization": tx.organization.slug if tx.organization else "",
            }
            rec_id = client.create_record(fields)
            tx.airtable_record_id = rec_id
            tx.airtable_sync_status = AirtableSyncStatus.SYNCED
            tx.save(update_fields=["airtable_record_id", "airtable_sync_status"])
        except Exception as exc:
            logger.warning("Airtable sync failed for transaction %s: %s", tx.id, exc)
            tx.airtable_sync_status = AirtableSyncStatus.SYNC_FAILED
            tx.save(update_fields=["airtable_sync_status"])
