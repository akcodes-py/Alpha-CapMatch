from datetime import date
from decimal import Decimal

from apps.reconciliation.services.matching import (
    Candidate,
    match_credit,
    name_found,
    normalize_name,
    normalize_reference,
)


def make_candidate(id, reference, investor, remaining, call=date(2026, 3, 1)):
    return Candidate(
        id=id,
        reference=reference,
        normalized_reference=normalize_reference(reference),
        investor_name=investor,
        normalized_name=normalize_name(investor),
        remaining=Decimal(remaining),
        call_date=call,
    )


def test_normalize_reference():
    assert normalize_reference("cc-1001") == "CC1001"
    assert normalize_reference(" CC 1001 ") == "CC1001"
    assert normalize_reference(" - ") == ""


def test_normalize_name_drops_one_suffix_and_keeps_trust():
    assert normalize_name("Meridian Partners LLC") == "MERIDIAN PARTNERS"
    assert normalize_name("Foo LP") == "FOO"
    assert normalize_name("Foo Ltd") == "FOO"
    assert normalize_name("Foo Inc") == "FOO"
    assert normalize_name("Patel Family Trust") == "PATEL FAMILY TRUST"
    assert normalize_name("  meridian   partners ") == "MERIDIAN PARTNERS"
    assert normalize_name("!!!") == ""


def test_name_found_requires_whole_words():
    assert name_found("HALLER", "Haller capital call")
    assert not name_found("HALL", "Haller capital call")
    assert not name_found("", "anything at all")
    assert name_found("MERIDIAN PARTNERS", "meridian partners wire")


def test_reference_match_full_and_partial():
    cands = [make_candidate(1, "CC-1001", "Haller", "30000")]
    full = match_credit(Decimal("30000"), date(2026, 4, 3), "Haller CC-1001", "FT1", cands)
    assert full.status == "suggested"
    assert [m.line_item_id for m in full.matches] == [1]
    assert full.reason == "Reference CC-1001 found; amount equals remaining 30,000.00"
    partial = match_credit(Decimal("20000"), date(2026, 4, 3), "Haller CC-1001", "FT1", cands)
    assert partial.status == "suggested"
    assert (
        partial.reason
        == "Reference CC-1001 found; partial payment, 10,000.00 will remain "
        "(20,000.00 of 30,000.00)"
    )
    assert "FT1" not in partial.reason


def test_reference_found_in_bank_reference_says_so():
    cands = [make_candidate(1, "CC-1002", "Rahul Shah", "25000")]
    result = match_credit(
        Decimal("25000"), date(2026, 4, 3), "Something else", "FT-CC-1002-x", cands
    )
    assert result.status == "suggested"
    assert (
        result.reason
        == "Reference CC-1002 found in bank reference; amount equals remaining 25,000.00"
    )


def test_overpayment_needs_review_without_matches():
    cands = [make_candidate(1, "CC-1003", "Patel Family Trust", "12500")]
    result = match_credit(Decimal("13000"), date(2026, 4, 12), "Patel CC-1003", "FT1", cands)
    assert result.status == "needs_review"
    assert result.matches == ()
    assert (
        result.reason
        == "Reference CC-1003 found; amount 13,000.00 exceeds remaining 12,500.00 (overpayment)"
    )


def test_multiple_reference_hits_all_proposed():
    cands = [
        make_candidate(1, "CC-1005", "Oakridge Holdings", "15000"),
        make_candidate(2, "CC-1006", "Oakridge Holdings", "15000"),
    ]
    result = match_credit(
        Decimal("15000"), date(2026, 4, 11), "CC-1005 and CC-1006", "FT1", cands
    )
    assert result.status == "needs_review"
    assert sorted(m.line_item_id for m in result.matches) == [1, 2]


def test_name_amount_match_single_and_multiple():
    one = [make_candidate(1, "CC-1003", "Patel Family Trust", "12500")]
    result = match_credit(
        Decimal("12500"), date(2026, 4, 5), "Patel Family Trust distribution", "FTX", one
    )
    assert result.status == "suggested"
    assert [m.line_item_id for m in result.matches] == [1]

    two = [
        make_candidate(1, "CC-1005", "Oakridge Holdings", "15000"),
        make_candidate(2, "CC-1006", "Oakridge Holdings", "15000"),
    ]
    result = match_credit(
        Decimal("15000"), date(2026, 4, 11), "Oakridge Holdings investment", "FTX", two
    )
    assert result.status == "needs_review"
    assert sorted(m.line_item_id for m in result.matches) == [1, 2]


def test_no_match_without_name_or_reference():
    cands = [make_candidate(1, "CC-1001", "Haller", "30000")]
    result = match_credit(Decimal("9999.99"), date(2026, 4, 7), "Unknown wire", "FTX", cands)
    assert result.status == "needs_review"
    assert result.matches == ()
    assert result.reason == "No matching line item found for amount 9,999.99"


def test_unmatched_code_names_it():
    cands = [make_candidate(1, "CC-1001", "Haller", "30000")]
    result = match_credit(
        Decimal("11000"), date(2026, 4, 13), "WIRE INCOMING CEDAR GROVE FUND CC-2001",
        "FT20260416K", cands,
    )
    assert result.status == "needs_review"
    assert result.matches == ()
    assert (
        result.reason
        == "Reference CC-2001 does not match an eligible line item in this organization"
    )


def test_future_call_date_is_ineligible():
    cands = [make_candidate(1, "CC-1006", "Oakridge Holdings", "15000", call=date(2026, 4, 1))]
    result = match_credit(Decimal("15000"), date(2026, 3, 20), "Wire CC-1006", "FTX", cands)
    assert result.status == "needs_review"
    assert result.matches == ()


def test_zero_remaining_is_ineligible():
    cands = [make_candidate(1, "CC-1001", "Haller", "0")]
    result = match_credit(Decimal("100"), date(2026, 4, 3), "Haller CC-1001", "FT1", cands)
    assert result.status == "needs_review"
    assert result.matches == ()


def test_reference_hit_skips_name_step():
    cands = [
        make_candidate(1, "CC-1001", "Haller", "30000"),
        make_candidate(2, "CC-1003", "Patel Family Trust", "20000"),
    ]
    result = match_credit(
        Decimal("20000"), date(2026, 4, 3), "Patel Family Trust CC-1001", "FT1", cands
    )
    assert result.status == "suggested"
    assert [m.line_item_id for m in result.matches] == [1]


def test_pre_call_credit_needs_review_despite_ref_and_name_match():
    cands = [
        make_candidate(1, "CC-1005", "Oakridge Holdings LLC", "15000", call=date(2026, 3, 25)),
        make_candidate(2, "CC-1006", "Oakridge Holdings LLC", "15000", call=date(2026, 4, 1)),
    ]
    result = match_credit(
        Decimal("15000"),
        date(2026, 3, 20),
        "WIRE INCOMING OAKRIDGE HOLDINGS LLC REF CC-1006",
        "FTX",
        cands,
    )
    assert result.status == "needs_review"
    assert result.matches == ()


def test_match_result_types():
    cands = [make_candidate(1, "CC-1001", "Haller", "30000")]
    result = match_credit(Decimal("100"), date(2026, 4, 3), "Haller CC-1001", "FT1", cands)
    assert isinstance(result.matches, tuple)
    assert result.status in ("suggested", "needs_review")
