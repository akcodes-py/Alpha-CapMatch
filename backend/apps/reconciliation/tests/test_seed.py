from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.reconciliation.models import CapitalCall, LineItem, Organization


@pytest.mark.django_db
def test_seed_demo_creates_exact_spec_data():
    call_command("seed_demo")
    call_command("seed_demo")
    assert Organization.objects.count() == 2
    assert Organization.objects.get(slug="northwind").name == "Northwind Ventures"
    assert Organization.objects.get(slug="bluebird").name == "Bluebird Capital"

    call1 = CapitalCall.objects.get(organization__slug="northwind", name="CALL-N1")
    assert (call1.call_date, call1.due_date) == (date(2026, 3, 25), date(2026, 4, 10))
    call2 = CapitalCall.objects.get(organization__slug="northwind", name="CALL-N2")
    assert (call2.call_date, call2.due_date) == (date(2026, 4, 1), date(2026, 4, 20))
    callb = CapitalCall.objects.get(organization__slug="bluebird", name="CALL-B1")
    assert (callb.call_date, callb.due_date) == (date(2026, 4, 1), date(2026, 4, 15))

    expected = {
        ("northwind", "CC-1001", "Haller Capital LLC", "27500.00"),
        ("northwind", "CC-1002", "Rahul Shah Trust", "25000.00"),
        ("northwind", "CC-1003", "Patel Family Trust", "12500.00"),
        ("northwind", "CC-1004", "Meridian Partners LP", "15000.00"),
        ("northwind", "CC-1005", "Oakridge Holdings LLC", "15000.00"),
        ("northwind", "CC-1006", "Oakridge Holdings LLC", "15000.00"),
        ("bluebird", "CC-2001", "Cedar Grove Fund LP", "40000.00"),
    }
    assert LineItem.objects.count() == 7
    actual = {
        (
            item.organization.slug,
            item.reference,
            item.investor.name,
            f"{item.amount_called:.2f}",
        )
        for item in LineItem.objects.select_related("organization", "investor")
    }
    assert actual == expected
    for item in LineItem.objects.all():
        assert item.status == "open"
        assert item.amount_funded == Decimal("0.00")
