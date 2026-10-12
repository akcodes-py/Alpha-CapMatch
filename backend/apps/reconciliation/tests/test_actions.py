from decimal import Decimal

import pytest

from apps.reconciliation.models import BankTransaction, LineItem, Match
from apps.reconciliation.tests.conftest import make_client, upload

HEADER = "date,description,bank_reference,amount,type"


def import_one(client, desc, ref, amount, date="2026-04-03", type="credit"):
    body = f"{HEADER}\n{date},{desc},{ref},{amount},{type}"
    response = upload(client, body)
    assert response.status_code == 201, response.data
    return BankTransaction.objects.get(bank_reference=ref)


@pytest.mark.django_db
def test_approve_updates_funded_and_second_approve_conflicts(north_client):
    tx = import_one(north_client, "Rahul CC-1002", "FT1", "25000")
    match = tx.matches.get()
    response = north_client.post(f"/api/matches/{match.id}/approve/")
    assert response.status_code == 200
    item = LineItem.objects.get(reference="CC-1002")
    assert item.amount_funded == Decimal("25000")
    assert isinstance(item.amount_funded, Decimal)
    assert item.status == "funded"
    assert BankTransaction.objects.get(id=tx.id).status == "reconciled"

    again = north_client.post(f"/api/matches/{match.id}/approve/")
    assert again.status_code == 409
    assert again.data["error"]["code"] == "conflict"
    assert LineItem.objects.get(reference="CC-1002").amount_funded == Decimal("25000")


@pytest.mark.django_db
def test_partial_approve_sets_partially_funded(north_client):
    tx = import_one(north_client, "Haller CC-1001", "FT1", "20000", date="2026-04-04")
    north_client.post(f"/api/matches/{tx.matches.get().id}/approve/")
    item = LineItem.objects.get(reference="CC-1001")
    assert item.amount_funded == Decimal("20000")
    assert item.status == "partially_funded"


@pytest.mark.django_db
def test_approve_one_of_many_rejects_siblings(north_client):
    tx = import_one(
        north_client, "Oakridge Holdings investment", "FT1", "15000", date="2026-04-11"
    )
    assert tx.matches.count() == 2
    first = tx.matches.order_by("id").first()
    response = north_client.post(f"/api/matches/{first.id}/approve/")
    assert response.status_code == 200
    statuses = dict(Match.objects.filter(transaction=tx).values_list("id", "status"))
    assert statuses[first.id] == "approved"
    assert list(statuses.values()).count("rejected") == 1
    assert BankTransaction.objects.get(id=tx.id).status == "reconciled"


@pytest.mark.django_db
def test_reject_marks_needs_review_when_none_proposed_left(north_client):
    tx = import_one(north_client, "Rahul CC-1002", "FT1", "25000")
    match = tx.matches.get()
    response = north_client.post(f"/api/matches/{match.id}/reject/")
    assert response.status_code == 200
    assert Match.objects.get(id=match.id).status == "rejected"
    tx.refresh_from_db()
    assert tx.status == "needs_review"
    assert tx.reason != ""
    again = north_client.post(f"/api/matches/{match.id}/reject/")
    assert again.status_code == 409


@pytest.mark.django_db
def test_reject_keeps_suggested_while_sibling_proposed(north_client):
    tx = import_one(
        north_client, "Oakridge Holdings investment", "FT1", "15000", date="2026-04-11"
    )
    first, second = list(tx.matches.order_by("id"))
    north_client.post(f"/api/matches/{first.id}/reject/")
    tx.refresh_from_db()
    assert tx.status == "needs_review"
    assert Match.objects.get(id=second.id).status == "proposed"


@pytest.mark.django_db
def test_ignore_rejects_proposed_and_conflicts_when_reconciled(north_client):
    tx = import_one(north_client, "Rahul CC-1002", "FT1", "25000")
    response = north_client.post(f"/api/transactions/{tx.id}/ignore/")
    assert response.status_code == 200
    tx.refresh_from_db()
    assert tx.status == "ignored"
    assert tx.matches.filter(status="proposed").count() == 0

    tx2 = import_one(north_client, "Haller CC-1001", "FT2", "20000", date="2026-04-04")
    north_client.post(f"/api/matches/{tx2.matches.get().id}/approve/")
    conflict = north_client.post(f"/api/transactions/{tx2.id}/ignore/")
    assert conflict.status_code == 409
    assert conflict.data["error"]["code"] == "conflict"


@pytest.mark.django_db
def test_ignore_unknown_transaction_returns_404(north_client):
    assert north_client.post("/api/transactions/99999/ignore/").status_code == 404


@pytest.mark.django_db
def test_cross_organization_approve_returns_404(north_client, blue_client, seed):
    tx = import_one(north_client, "Rahul CC-1002", "FT1", "25000")
    match = tx.matches.get()
    response = blue_client.post(f"/api/matches/{match.id}/approve/")
    assert response.status_code == 404
    assert LineItem.objects.get(reference="CC-1002").amount_funded == Decimal("0")
    cross_list = blue_client.get("/api/transactions/").data
    assert cross_list == []
    ghost = make_client("ghost")
    assert ghost.post(f"/api/matches/{match.id}/approve/").status_code == 404
