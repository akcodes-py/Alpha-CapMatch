import pytest

from apps.reconciliation.models import ActivityLog
from apps.reconciliation.tests.test_actions import import_one


@pytest.mark.django_db
def test_approve_writes_approved_entry(north_client):
    tx = import_one(north_client, "Rahul CC-1002", "FT1", "25000")
    match = tx.matches.get()
    north_client.post(f"/api/matches/{match.id}/approve/")
    response = north_client.get(f"/api/transactions/{tx.id}/history/")
    assert response.status_code == 200
    actions = [e["action"] for e in response.data]
    assert actions == ["approved", "suggested", "imported"]
    assert response.data[0]["match"] == match.id


@pytest.mark.django_db
def test_failed_approve_writes_nothing(north_client):
    tx = import_one(north_client, "Rahul CC-1002", "FT1", "25000")
    match = tx.matches.get()
    north_client.post(f"/api/matches/{match.id}/approve/")
    count = ActivityLog.objects.count()
    again = north_client.post(f"/api/matches/{match.id}/approve/")
    assert again.status_code == 409
    assert ActivityLog.objects.count() == count


@pytest.mark.django_db
def test_history_of_other_organization_returns_404(north_client, blue_client):
    tx = import_one(north_client, "Rahul CC-1002", "FT1", "25000")
    assert blue_client.get(f"/api/transactions/{tx.id}/history/").status_code == 404
