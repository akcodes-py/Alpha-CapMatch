from unittest.mock import MagicMock, patch

import pytest

from apps.reconciliation.models import AirtableSyncStatus, BankTransaction
from apps.reconciliation.services.airtable import AirtableClient, sync_needs_review_transactions
from apps.reconciliation.tests.conftest import upload

HEADER = "date,description,bank_reference,amount,type"


class FakeAirtableClient:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.created_records: list[dict] = []
        self.is_configured = True

    def create_record(self, fields: dict) -> str:
        if self.should_fail:
            raise RuntimeError("Airtable API connection timed out")
        self.created_records.append(fields)
        return f"rec_{len(self.created_records)}"


@pytest.mark.django_db
def test_airtable_not_configured_leaves_transactions_not_synced(north_client):
    body = f"{HEADER}\n2026-04-09,UNKNOWN INCOMING WIRE,FT_UN1,9999.99,credit"
    with patch.object(AirtableClient, "is_configured", False):
        response = upload(north_client, body)
    assert response.status_code == 201
    tx = BankTransaction.objects.get(bank_reference="FT_UN1")
    assert tx.status == "needs_review"
    assert tx.airtable_sync_status == AirtableSyncStatus.NOT_SYNCED
    assert tx.airtable_record_id == ""


@pytest.mark.django_db
def test_airtable_syncs_only_needs_review_transactions(north_client):
    fake = FakeAirtableClient()
    body = "\n".join(
        [
            HEADER,
            "2026-04-03,Rahul CC-1002,FT_SUGG,25000.00,credit",  # suggested
            "2026-04-09,UNKNOWN INCOMING WIRE,FT_NR,9999.99,credit",  # needs_review
            "2026-04-05,BANK FEE,FT_DEB,-25.00,debit",  # ignored
        ]
    )
    with patch("apps.reconciliation.services.importing.sync_needs_review_transactions") as mock_sync:
        # call real sync with our fake client
        def side_effect(transactions):
            sync_needs_review_transactions(transactions, client=fake)

        mock_sync.side_effect = side_effect
        response = upload(north_client, body)

    assert response.status_code == 201
    assert len(fake.created_records) == 1
    assert fake.created_records[0]["Bank Reference"] == "FT_NR"

    nr_tx = BankTransaction.objects.get(bank_reference="FT_NR")
    assert nr_tx.airtable_sync_status == AirtableSyncStatus.SYNCED
    assert nr_tx.airtable_record_id == "rec_1"

    sugg_tx = BankTransaction.objects.get(bank_reference="FT_SUGG")
    assert sugg_tx.airtable_sync_status == AirtableSyncStatus.NOT_SYNCED
    assert sugg_tx.airtable_record_id == ""


@pytest.mark.django_db
def test_airtable_failure_never_breaks_import(north_client):
    failing_client = FakeAirtableClient(should_fail=True)
    body = f"{HEADER}\n2026-04-09,UNKNOWN INCOMING WIRE,FT_FAIL,9999.99,credit"
    with patch("apps.reconciliation.services.importing.sync_needs_review_transactions") as mock_sync:
        def side_effect(transactions):
            sync_needs_review_transactions(transactions, client=failing_client)

        mock_sync.side_effect = side_effect
        # Import must still succeed 201 even when Airtable completely fails
        response = upload(north_client, body)

    assert response.status_code == 201
    tx = BankTransaction.objects.get(bank_reference="FT_FAIL")
    assert tx.airtable_sync_status == AirtableSyncStatus.SYNC_FAILED
    assert tx.airtable_record_id == ""


def test_airtable_client_create_record_request():
    client = AirtableClient(api_key="pat_test123", base_id="appXYZ", table_name="Needs Review")
    assert client.is_configured is True
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "recABC123"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        rec_id = client.create_record({"Amount": 100.0, "Description": "Test"})
        assert rec_id == "recABC123"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.airtable.com/v0/appXYZ/Needs Review"
        assert kwargs["headers"]["Authorization"] == "Bearer pat_test123"
        assert kwargs["json"] == {"fields": {"Amount": 100.0, "Description": "Test"}}
