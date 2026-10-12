from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.reconciliation.models import CapitalCall, Investor, LineItem, Organization

SEED = {
    "northwind": {
        "name": "Northwind Ventures",
        "calls": {
            "CALL-N1": (date(2026, 3, 25), date(2026, 4, 10)),
            "CALL-N2": (date(2026, 4, 1), date(2026, 4, 20)),
        },
        "line_items": [
            ("Haller Capital LLC", "CALL-N1", "CC-1001", "27500.00"),
            ("Rahul Shah Trust", "CALL-N1", "CC-1002", "25000.00"),
            ("Patel Family Trust", "CALL-N1", "CC-1003", "12500.00"),
            ("Meridian Partners LP", "CALL-N1", "CC-1004", "15000.00"),
            ("Oakridge Holdings LLC", "CALL-N1", "CC-1005", "15000.00"),
            ("Oakridge Holdings LLC", "CALL-N2", "CC-1006", "15000.00"),
        ],
    },
    "bluebird": {
        "name": "Bluebird Capital",
        "calls": {
            "CALL-B1": (date(2026, 4, 1), date(2026, 4, 15)),
        },
        "line_items": [
            ("Cedar Grove Fund LP", "CALL-B1", "CC-2001", "40000.00"),
        ],
    },
}


class Command(BaseCommand):
    help = "Seed demo organizations, investors, calls and line items (idempotent)."

    def handle(self, *args, **options):
        with transaction.atomic():
            for slug, spec in SEED.items():
                org, _ = Organization.objects.get_or_create(
                    slug=slug, defaults={"name": spec["name"]}
                )
                calls = {}
                for call_name, (call_date, due_date) in spec["calls"].items():
                    call, _ = CapitalCall.objects.get_or_create(
                        organization=org,
                        name=call_name,
                        defaults={"call_date": call_date, "due_date": due_date},
                    )
                    calls[call_name] = call
                for investor_name, call_name, reference, called in spec["line_items"]:
                    investor, _ = Investor.objects.get_or_create(
                        organization=org, name=investor_name
                    )
                    LineItem.objects.get_or_create(
                        organization=org,
                        reference=reference,
                        defaults={
                            "investor": investor,
                            "capital_call": calls[call_name],
                            "amount_called": Decimal(called),
                        },
                    )
        self.stdout.write(self.style.SUCCESS("seed_demo ok"))
