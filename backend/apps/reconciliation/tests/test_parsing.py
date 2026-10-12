import pytest

from apps.reconciliation.services.parsing import (
    HeaderError,
    decode_upload,
    parse_amount,
    parse_csv_text,
    validate_row,
)
from decimal import Decimal


def test_thousands_separator_parsed():
    assert parse_amount('"25,000"'.strip('"')) == Decimal("25000")


def test_zero_nan_infinity_rejected():
    import pytest as _pytest

    for bad in ("0", "0.00", "NaN", "Infinity", "-Infinity", "nan", "abc", ""):
        with _pytest.raises(Exception):
            parse_amount(bad)


def test_sign_type_mismatch_reported_with_line_number():
    text = (
        "date,description,bank_reference,amount,type\n"
        "2026-04-14,Negative credit,FT1,-15000,credit\n"
        "2026-04-14,Positive debit,FT2,15000,debit\n"
    )
    rows, errors = parse_csv_text(text)
    assert rows == []
    assert [e["line"] for e in errors] == [2, 3]
    assert "positive" in errors[0]["message"]
    assert "negative" in errors[1]["message"]


def test_invalid_date_reported():
    text = "date,description,bank_reference,amount,type\n2026-04-31,Bad,FT1,100,credit\n"
    rows, errors = parse_csv_text(text)
    assert rows == []
    assert errors[0]["line"] == 2
    assert "date" in errors[0]["message"]


def test_missing_and_blank_fields_reported():
    with pytest.raises(Exception):
        validate_row(
            {"date": "2026-04-03", "description": "  ", "bank_reference": "FT1",
             "amount": "10", "type": "credit"},
            2,
        )


def test_header_check_comes_first_and_saves_nothing():
    with pytest.raises(HeaderError) as exc:
        parse_csv_text("date,amount\n2026-04-03,10\n")
    assert "description" in exc.value.missing


def test_blank_lines_skipped_and_type_case_insensitive():
    text = (
        "date,description,bank_reference,amount,type\n"
        "\n"
        '2026-04-12,Haller cc1001,FT1,"7,500",CREDIT\n'
    )
    rows, errors = parse_csv_text(text)
    assert errors == []
    assert len(rows) == 1
    assert rows[0].type == "credit"
    assert rows[0].amount == Decimal("7500")


def test_reference_alias_accepted():
    text = "date,description,reference,amount,type\n2026-04-03,Test,FT1,100,credit\n"
    rows, errors = parse_csv_text(text)
    assert errors == []
    assert rows[0].bank_reference == "FT1"


def test_bom_stripped():
    assert decode_upload("date,x\n".encode("utf-8-sig")) == "date,x\n"
