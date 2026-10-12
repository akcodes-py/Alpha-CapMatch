import pytest

from apps.reconciliation.models import ActivityLog
from apps.reconciliation.tests.test_actions import import_one


@pytest.mark.django_db
def test_unignore_allowed_case(north_client):
    tx = import_one(north_client, "Unknown wire", "FT1", "9999.99")
    assert tx.status == "needs_review"
    north_client.post(f"/api/transactions/{tx.id}/ignore/")
    response = north_client.post(f"/api/transactions/{tx.id}/unignore/")
    assert response.status_code == 200
    tx.refresh_from_db()
    assert tx.status == "needs_review"
    assert tx.matches.filter(status="proposed").count() == 0
    assert ActivityLog.objects.filter(
        transaction=tx, action="unignored"
    ).count() == 1


@pytest.mark.django_db
def test_unignore_debit_refused(north_client):
    tx = import_one(north_client, "Bank fee", "FT1", "-25.00", type="debit")
    assert tx.status == "ignored"
    response = north_client.post(f"/api/transactions/{tx.id}/unignore/")
    assert response.status_code == 409
    tx.refresh_from_db()
    assert tx.status == "ignored"


@pytest.mark.django_db
def test_unignore_reconciled_refused(north_client):
    tx = import_one(north_client, "Rahul CC-1002", "FT1", "25000")
    north_client.post(f"/api/matches/{tx.matches.get().id}/approve/")
    response = north_client.post(f"/api/transactions/{tx.id}/unignore/")
    assert response.status_code == 409


@pytest.mark.django_db
def test_unignore_other_organization_returns_404(north_client, blue_client):
    tx = import_one(north_client, "Unknown wire", "FT1", "9999.99")
    north_client.post(f"/api/transactions/{tx.id}/ignore/")
    assert blue_client.post(f"/api/transactions/{tx.id}/unignore/").status_code == 404
