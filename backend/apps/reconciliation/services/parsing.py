import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping

REQUIRED_COLUMNS = ("date", "description", "bank_reference", "amount", "type")

# Accepted header spellings for each required column (first entry is canonical).
COLUMN_ALIASES = {
    "date": ("date",),
    "description": ("description",),
    "bank_reference": ("bank_reference", "reference", "bank_ref", "ref"),
    "amount": ("amount",),
    "type": ("type",),
}


class HeaderError(Exception):
    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Missing columns: {', '.join(missing)}")


class RowError(Exception):
    pass


@dataclass(frozen=True)
class ValidRow:
    line: int
    date: date
    description: str
    bank_reference: str
    amount: Decimal
    type: str


def parse_amount(raw: str) -> Decimal:
    cleaned = raw.replace(",", "").replace(" ", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise RowError(f"invalid amount '{raw}'")
    if value.is_nan() or value.is_infinite():
        raise RowError(f"invalid amount '{raw}'")
    if value == 0:
        raise RowError("amount must not be zero")
    return value


def parse_date(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise RowError(f"invalid date '{raw}', expected a real YYYY-MM-DD date")


def validate_row(row: Mapping[str, str | None], line: int) -> ValidRow:
    def get(col: str) -> str:
        return (row.get(col) or "").strip()

    tx_date = parse_date(get("date"))
    description = get("description")
    if not description:
        raise RowError("description is required")
    bank_reference = get("bank_reference")
    if not bank_reference:
        raise RowError("bank_reference is required")
    amount = parse_amount(get("amount"))
    tx_type = get("type").lower()
    if tx_type not in ("credit", "debit"):
        raise RowError(f"invalid type '{get('type')}', expected credit or debit")
    if tx_type == "credit" and amount <= 0:
        raise RowError("credit amount must be positive")
    if tx_type == "debit" and amount >= 0:
        raise RowError("debit amount must be negative")
    return ValidRow(
        line=line,
        date=tx_date,
        description=description,
        bank_reference=bank_reference,
        amount=amount,
        type=tx_type,
    )


def parse_csv_text(text: str) -> tuple[list[ValidRow], list[dict]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HeaderError(list(REQUIRED_COLUMNS))
    normalised = {name.strip().lower(): name for name in reader.fieldnames if name}
    key_map = {}
    missing = []
    for col in REQUIRED_COLUMNS:
        found = next((normalised[alias] for alias in COLUMN_ALIASES[col] if alias in normalised), None)
        if found is None:
            missing.append(col)
        else:
            key_map[col] = found
    if missing:
        raise HeaderError(missing)
    valid: list[ValidRow] = []
    errors: list[dict] = []
    for lineno, raw_row in enumerate(reader, start=2):
        values = [v for v in raw_row.values() if v is not None and str(v).strip() != ""]
        if not values:
            continue
        row = {col: raw_row.get(key_map[col]) for col in REQUIRED_COLUMNS}
        try:
            valid.append(validate_row(row, lineno))
        except RowError as exc:
            errors.append({"line": lineno, "message": str(exc)})
    return valid, errors


def decode_upload(data: bytes) -> str:
    return data.decode("utf-8-sig")
