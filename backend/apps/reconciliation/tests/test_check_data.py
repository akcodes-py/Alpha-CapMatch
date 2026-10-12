import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.reconciliation.models import LineItem
from apps.reconciliation.tests.conftest import upload


@pytest.mark.django_db
def test_check_data_passes_on_clean_import(north_client):
    body = (
        "date,description,bank_reference,amount,type\n"
        "2026-04-03,Rahul CC-1002,FT1,25000,credit\n"
    )
    assert upload(north_client, body).status_code == 201
    call_command("check_data")


@pytest.mark.django_db
def test_check_data_fails_on_tampered_funded(north_client):
    body = (
        "date,description,bank_reference,amount,type\n"
        "2026-04-03,Rahul CC-1002,FT1,25000,credit\n"
    )
    upload(north_client, body)
    LineItem.objects.filter(reference="CC-1002").update(amount_funded=1)
    with pytest.raises(CommandError):
        call_command("check_data")


@pytest.mark.django_db
def test_health_needs_no_organization_header(seed):
    from rest_framework.test import APIClient

    response = APIClient().get("/api/health/")
    assert response.status_code == 200
    assert response.data == {"status": "ok"}
