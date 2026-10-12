import importlib.util
from pathlib import Path

import pytest

from apps.reconciliation.tests.test_actions import import_one


def load_migration():
    path = (
        Path(__file__).resolve().parents[1] / "migrations" / "0004_match_rule.py"
    )
    spec = importlib.util.spec_from_file_location("m0004_match_rule", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backfill_maps_reasons_to_rules():
    module = load_migration()
    assert module.rule_for_reason("Reference CC-1001 found; partial payment") == "reference"
    assert module.rule_for_reason("Investor X matches 'Y' for exact amount") == "name_and_amount"
    assert module.rule_for_reason("Multiple line items match 'Y'") == "name_and_amount"
    assert module.rule_for_reason("") == "name_and_amount"


@pytest.mark.django_db
def test_rule_tag_matches_rule(north_client):
    ref_tx = import_one(north_client, "Rahul CC-1002", "FT1", "25000")
    assert ref_tx.matches.get().rule == "reference"
    name_tx = import_one(
        north_client, "Patel Family Trust distribution", "FT2", "12500", date="2026-04-05"
    )
    assert name_tx.matches.get().rule == "name_and_amount"
    response = north_client.get("/api/transactions/")
    by_ref = {t["bank_reference"]: t for t in response.data}
    assert by_ref["FT1"]["matches"][0]["rule"] == "reference"
    assert by_ref["FT2"]["matches"][0]["rule"] == "name_and_amount"
