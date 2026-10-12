import csv
import io

import pytest

from apps.reconciliation.tests.conftest import upload

HEADER = "date,description,bank_reference,amount,type"


@pytest.mark.django_db
def test_export_content_type_and_rows(north_client):
    body = "\n".join(
        [
            HEADER,
            "2026-04-07,Unknown wire,FT1,9999.99,credit",
            "2026-04-03,Rahul CC-1002,FT2,25000,credit",
        ]
    )
    assert upload(north_client, body).status_code == 201
    response = north_client.get("/api/transactions/export/?status=needs_review")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert "needs_review.csv" in response["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(b"".join(response.streaming_content).decode())))
    assert rows[0] == ["date", "description", "amount", "bank_reference", "status", "reason"]
    assert len(rows) == 2
    assert rows[1][1] == "Unknown wire"


@pytest.mark.django_db
def test_export_scoped_to_organization(north_client, blue_client):
    upload(north_client, "\n".join([HEADER, "2026-04-07,Unknown wire,FT1,9999.99,credit"]))
    upload(
        north_client,
        "\n".join([HEADER, "2026-04-07,North only,FT9,9999.99,credit"]),
    )
    upload(blue_client, "\n".join([HEADER, "2026-04-07,Unknown wire,FT1,9999.99,credit"]))
    content = b"".join(
        blue_client.get("/api/transactions/export/?status=needs_review").streaming_content
    ).decode()
    blue_rows = list(csv.reader(io.StringIO(content)))
    assert len(blue_rows) == 2
    assert "FT9" not in content


@pytest.mark.django_db
def test_export_neutralises_formula_cells(north_client):
    body = "\n".join([HEADER, '2026-04-07,"=HYPERLINK(""x"")",FT1,9999.99,credit'])
    assert upload(north_client, body).status_code == 201
    response = north_client.get("/api/transactions/export/?status=needs_review")
    rows = list(csv.reader(io.StringIO(b"".join(response.streaming_content).decode())))
    assert rows[1][1].startswith("'=")


@pytest.mark.django_db
def test_export_unknown_status_returns_400(north_client):
    assert north_client.get("/api/transactions/export/?status=bogus").status_code == 400
