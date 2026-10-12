from decimal import Decimal

import pytest

from apps.reconciliation.models import BankTransaction, LineItem
from apps.reconciliation.tests.conftest import make_client, upload

HEADER = "date,description,bank_reference,amount,type"


def row(date, desc, ref, amount, type):
    return f"{date},{desc},{ref},{amount},{type}"


@pytest.mark.django_db
def test_missing_column_rejects_file_and_saves_nothing(north_client):
    response = upload(north_client, "date,amount\n2026-04-03,100\n")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "invalid_header"
    assert BankTransaction.objects.count() == 0


@pytest.mark.django_db
def test_missing_file_returns_400(north_client):
    response = north_client.post("/api/imports/", {}, format="multipart")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "missing_file"


@pytest.mark.django_db
def test_organization_header_required_and_unknown(seed):
    anon = make_client(None)
    response = upload(anon, f"{HEADER}\n")
    assert response.status_code == 400
    assert response.data["error"]["code"] == "missing_organization"
    ghost = make_client("ghost")
    response = upload(ghost, f"{HEADER}\n")
    assert response.status_code == 404
    assert response.data["error"]["code"] == "unknown_organization"


@pytest.mark.django_db
def test_amount_parsing_and_stored_decimal(north_client):
    body = "\n".join(
        [
            HEADER,
            row("2026-04-03", "Rahul CC-1002", "FT1", '"25,000"', "credit"),
            row("2026-04-31", "Bad date", "FT2", "100", "credit"),
            row("2026-04-03", "Neg credit", "FT3", "-15000", "credit"),
            row("2026-04-03", "Zero", "FT4", "0", "credit"),
        ]
    )
    response = upload(north_client, body)
    assert response.status_code == 201
    assert response.data["imported"] == 1
    assert [e["line"] for e in response.data["errors"]] == [3, 4, 5]
    tx = BankTransaction.objects.get(bank_reference="FT1")
    assert tx.amount == Decimal("25000")
    assert isinstance(tx.amount, Decimal)


@pytest.mark.django_db
def test_duplicates_reupload_and_in_file(north_client):
    body = "\n".join(
        [
            HEADER,
            row("2026-04-03", "Rahul CC-1002", "FT1", "25000", "credit"),
            row("2026-04-04", "Haller CC-1001", "FT1", "25000", "credit"),
            row("2026-04-04", "Haller CC-1001", "FT2", "20000", "credit"),
        ]
    )
    first = upload(north_client, body)
    assert first.status_code == 201
    assert first.data == {"imported": 2, "duplicates": 1, "errors": []}
    second = upload(north_client, body)
    assert second.data == {"imported": 0, "duplicates": 3, "errors": []}
    assert BankTransaction.objects.count() == 2


@pytest.mark.django_db
def test_bank_reference_shared_across_organizations(north_client, blue_client):
    body = "\n".join([HEADER, row("2026-04-03", "Rahul CC-1002", "SHARED1", "25000", "credit")])
    assert upload(north_client, body).status_code == 201
    response = upload(blue_client, body)
    assert response.status_code == 201
    assert response.data["imported"] == 1


@pytest.mark.django_db
def test_reference_match_lowercase_and_partial(north_client):
    body = "\n".join(
        [
            HEADER,
            row("2026-04-04", "Haller payment cc1001", "FT1", "20000", "credit"),
        ]
    )
    assert upload(north_client, body).status_code == 201
    tx = BankTransaction.objects.get(bank_reference="FT1")
    assert tx.status == "suggested"
    assert tx.matches.count() == 1
    match = tx.matches.get()
    assert match.line_item.reference == "CC-1001"
    assert match.status == "proposed"
    assert (
        match.reason
        == "Reference CC-1001 found; partial payment, 7,500.00 will remain "
        "(20,000.00 of 27,500.00)"
    )


@pytest.mark.django_db
def test_name_amount_match_single_and_multiple(north_client):
    body = "\n".join(
        [
            HEADER,
            row("2026-04-05", "Patel Family Trust distribution", "FT1", "12500", "credit"),
            row("2026-04-11", "Oakridge Holdings investment", "FT2", "15000", "credit"),
        ]
    )
    assert upload(north_client, body).status_code == 201
    single = BankTransaction.objects.get(bank_reference="FT1")
    assert single.status == "suggested"
    assert single.matches.get().line_item.reference == "CC-1003"
    multi = BankTransaction.objects.get(bank_reference="FT2")
    assert multi.status == "needs_review"
    assert sorted(m.line_item.reference for m in multi.matches.all()) == ["CC-1005", "CC-1006"]
    assert all(m.status == "proposed" for m in multi.matches.all())


@pytest.mark.django_db
def test_overpayment_needs_review_without_matches(north_client):
    body = "\n".join(
        [HEADER, row("2026-04-12", "Patel CC-1003 top-up", "FT1", "13000", "credit")]
    )
    assert upload(north_client, body).status_code == 201
    tx = BankTransaction.objects.get(bank_reference="FT1")
    assert tx.status == "needs_review"
    assert tx.matches.count() == 0
    assert tx.reason != ""


@pytest.mark.django_db
def test_pre_call_credit_needs_review_with_no_matches(north_client):
    body = "\n".join(
        [
            HEADER,
            row(
                "2026-03-20",
                "WIRE INCOMING OAKRIDGE HOLDINGS LLC REF CC-1006",
                "FT1",
                "15000",
                "credit",
            ),
        ]
    )
    assert upload(north_client, body).status_code == 201
    tx = BankTransaction.objects.get(bank_reference="FT1")
    assert tx.status == "needs_review"
    assert tx.matches.count() == 0


@pytest.mark.django_db
def test_debit_saved_as_ignored(north_client):
    body = "\n".join([HEADER, row("2026-04-04", "Bank fee", "FT1", "-25.00", "debit")])
    assert upload(north_client, body).status_code == 201
    tx = BankTransaction.objects.get(bank_reference="FT1")
    assert tx.status == "ignored"
    assert tx.matches.count() == 0


@pytest.mark.django_db
def test_organization_isolation_on_list(north_client, blue_client):
    upload(north_client, "\n".join([HEADER, row("2026-04-03", "Rahul CC-1002", "FT1", "25000", "credit")]))
    assert len(north_client.get("/api/transactions/").data) == 1
    assert blue_client.get("/api/transactions/").data == []
    north_items = north_client.get("/api/line-items/").data
    blue_items = blue_client.get("/api/line-items/").data
    assert {i["reference"] for i in north_items} == {
        "CC-1001", "CC-1002", "CC-1003", "CC-1004", "CC-1005", "CC-1006",
    }
    assert [i["reference"] for i in blue_items] == ["CC-2001"]
    item = {i["reference"]: i for i in north_items}["CC-1001"]
    assert item["investor"] == "Haller Capital LLC"
    assert Decimal(item["remaining"]) == Decimal("27500")
    assert item["status"] == "open"


@pytest.mark.django_db
def test_transaction_list_newest_first_with_matches(north_client):
    body = "\n".join(
        [
            HEADER,
            row("2026-04-03", "Rahul CC-1002", "FT1", "25000", "credit"),
            row("2026-04-05", "Patel Family Trust distribution", "FT2", "12500", "credit"),
        ]
    )
    upload(north_client, body)
    data = north_client.get("/api/transactions/").data
    assert [t["bank_reference"] for t in data] == ["FT2", "FT1"]
    by_ref = {t["bank_reference"]: t for t in data}
    assert by_ref["FT1"]["matches"][0]["line_item_reference"] == "CC-1002"
    assert by_ref["FT1"]["matches"][0]["investor_name"] == "Rahul Shah Trust"
    assert by_ref["FT1"]["matches"][0]["reason"] != ""


@pytest.mark.django_db
def test_list_endpoints_avoid_n_plus_one(north_client, django_assert_num_queries):
    body = "\n".join(
        [HEADER]
        + [
            row("2026-04-03", f"Rahul CC-1002-{i}", f"FT{i}", "25000", "credit")
            for i in range(6)
        ]
    )
    upload(north_client, body)
    with django_assert_num_queries(6):
        response = north_client.get("/api/transactions/")
        assert len(response.data) == 6
    with django_assert_num_queries(2):
        response = north_client.get("/api/line-items/")
        assert len(response.data) == 6
