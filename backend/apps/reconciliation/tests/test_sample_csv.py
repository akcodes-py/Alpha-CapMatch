from decimal import Decimal
from pathlib import Path

import pytest

from apps.reconciliation.models import BankTransaction
from apps.reconciliation.tests.conftest import upload

SAMPLE = Path(__file__).resolve().parents[4] / "sample_bank_statement.csv"


@pytest.mark.django_db
def test_sample_csv_matches_expected_table(north_client):
    response = upload(north_client, SAMPLE.read_bytes())
    assert response.status_code == 201
    assert response.data["imported"] == 11
    assert response.data["duplicates"] == 1
    assert [(e["line"]) for e in response.data["errors"]] == [13, 14]

    txs = {
        t.bank_reference: t
        for t in BankTransaction.objects.prefetch_related("matches__line_item")
    }

    def refs(ref):
        return sorted(m.line_item.reference for m in txs[ref].matches.all())

    assert txs["FT20260403A"].status == "suggested" and refs("FT20260403A") == ["CC-1002"]
    assert txs["FT20260403A"].amount == Decimal("25000.00")
    assert txs["ACH20260404B"].status == "suggested" and refs("ACH20260404B") == ["CC-1001"]
    assert txs["FEE20260405"].status == "ignored" and refs("FEE20260405") == []
    assert txs["FT20260407C"].status == "suggested" and refs("FT20260407C") == ["CC-1003"]
    assert txs["FT20260408E"].status == "suggested" and refs("FT20260408E") == ["CC-1004"]
    assert txs["FT20260409D"].status == "needs_review" and refs("FT20260409D") == []
    assert txs["FT20260409D"].reason == "No matching line item found for amount 9,999.99"
    assert txs["FT20260411G"].status == "needs_review"
    assert refs("FT20260411G") == ["CC-1005", "CC-1006"]
    assert txs["ACH20260414H"].status == "suggested" and refs("ACH20260414H") == ["CC-1001"]
    assert txs["FT20260415J"].status == "needs_review"
    assert refs("FT20260415J") == []
    assert (
        txs["FT20260415J"].reason
        == "Reference CC-1003 found; amount 13,000.00 exceeds remaining 12,500.00 (overpayment)"
    )
    assert txs["FT20260416K"].status == "needs_review"
    assert refs("FT20260416K") == []
    assert (
        txs["FT20260416K"].reason
        == "Reference CC-2001 does not match an eligible line item in this organization"
    )
    assert txs["FT20260320N"].status == "needs_review"
    assert refs("FT20260320N") == []
    assert (
        txs["FT20260320N"].reason
        == "Reference CC-1006 does not match an eligible line item in this organization"
    )
    assert isinstance(txs["FT20260403A"].amount, Decimal)


@pytest.mark.django_db
def test_sample_csv_cedar_grove_suggested_under_bluebird(blue_client):
    response = upload(blue_client, SAMPLE.read_bytes())
    assert response.status_code == 201
    tx = BankTransaction.objects.get(bank_reference="FT20260416K")
    assert tx.status == "suggested"
    assert tx.amount == Decimal("40000.00")
    assert [m.line_item.reference for m in tx.matches.all()] == ["CC-2001"]
