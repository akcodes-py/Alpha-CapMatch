from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.reconciliation.models import BankTransaction, Match
from apps.reconciliation.tests.conftest import upload

SAMPLE = Path(__file__).resolve().parents[4] / "sample_bank_statement.csv"


def preview(client, data):
    return client.post(
        "/api/imports/preview/",
        {"file": SimpleUploadedFile("stmt.csv", data, content_type="text/csv")},
        format="multipart",
    )


@pytest.mark.django_db
def test_preview_matches_real_import_and_saves_nothing(north_client):
    data = SAMPLE.read_bytes()
    response = preview(north_client, data)
    assert response.status_code == 200
    assert BankTransaction.objects.count() == 0
    assert Match.objects.count() == 0
    assert response.data["would_import"] == 11
    assert response.data["duplicates"] == 1
    assert [e["line"] for e in response.data["errors"]] == [13, 14]
    assert response.data["by_status"] == {"suggested": 5, "needs_review": 5, "ignored": 1}

    real = upload(north_client, data)
    assert real.status_code == 201
    assert real.data["imported"] == response.data["would_import"]
    assert real.data["duplicates"] == response.data["duplicates"]
    assert real.data["errors"] == response.data["errors"]


@pytest.mark.django_db
def test_preview_without_file_returns_400(north_client):
    response = north_client.post("/api/imports/preview/", {}, format="multipart")
    assert response.status_code == 400
