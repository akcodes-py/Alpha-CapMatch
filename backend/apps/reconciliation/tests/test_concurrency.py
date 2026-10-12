import threading
from decimal import Decimal

from django.core.management import call_command
from django.db import connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.reconciliation.models import BankTransaction, LineItem, Match


class ConcurrentApproveTest(TransactionTestCase):
    def setUp(self):
        call_command("seed_demo")
        org_txs = BankTransaction.objects.create(
            organization_id=self._org_id(),
            date="2026-04-03",
            description="Rahul CC-1002",
            bank_reference="FTCONC1",
            amount=Decimal("25000"),
            type="credit",
            status="suggested",
        )
        item = LineItem.objects.get(reference="CC-1002")
        self.match_id = Match.objects.create(
            transaction=org_txs, line_item=item, status="proposed", reason="test",
            rule="reference",
        ).id

    def _org_id(self):
        from apps.reconciliation.models import Organization

        return Organization.objects.get(slug="northwind").id

    def test_concurrent_approve_funds_exactly_once(self):
        barrier = threading.Barrier(2)
        results = []

        def approve():
            try:
                client = APIClient()
                client.credentials(HTTP_X_ORGANIZATION="northwind")
                barrier.wait()
                results.append(client.post(f"/api/matches/{self.match_id}/approve/").status_code)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=approve) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(results) == [200, 409]
        assert LineItem.objects.get(reference="CC-1002").amount_funded == Decimal("25000")
        assert Match.objects.get(id=self.match_id).status == "approved"
