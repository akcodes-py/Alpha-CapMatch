import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Literal, Sequence

_SUFFIXES = ("LLC", "LP", "LTD", "INC")
_CODE_RE = re.compile(r"[A-Za-z]{2,}-?\d+")


def money(value: Decimal) -> str:
    return f"{value:,.2f}"


def normalize_reference(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def normalize_name(value: str) -> str:
    text = re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    words = text.split(" ")
    if len(words) > 1 and words[-1] in _SUFFIXES:
        words = words[:-1]
    return " ".join(words)


def name_found(normalized_name: str, description: str) -> bool:
    if not normalized_name:
        return False
    haystack = f" {normalize_name(description)} "
    return f" {normalized_name} " in haystack


@dataclass(frozen=True)
class Candidate:
    id: int
    reference: str
    normalized_reference: str
    investor_name: str
    normalized_name: str
    remaining: Decimal
    call_date: date


@dataclass(frozen=True)
class ProposedMatch:
    line_item_id: int
    reason: str


@dataclass(frozen=True)
class MatchResult:
    status: Literal["suggested", "needs_review"]
    matches: tuple[ProposedMatch, ...]
    reason: str
    rule: Literal["reference", "name_and_amount"] | None = None


def build_candidates(line_items: Iterable) -> list[Candidate]:
    candidates = []
    for item in line_items:
        candidates.append(
            Candidate(
                id=item.id,
                reference=item.reference,
                normalized_reference=normalize_reference(item.reference),
                investor_name=item.investor.name,
                normalized_name=normalize_name(item.investor.name),
                remaining=item.amount_called - item.amount_funded,
                call_date=item.capital_call.call_date,
            )
        )
    return candidates


def _reference_location(normalized_ref: str, description: str, bank_reference: str) -> str:
    if not normalized_ref:
        return ""
    if normalized_ref in normalize_reference(bank_reference):
        return "bank"
    if normalized_ref in normalize_reference(description):
        return "description"
    return ""


def _unmatched_code(description: str, bank_reference: str, candidates: Sequence[Candidate]) -> str:
    norm_desc = normalize_reference(description)
    norm_bank_ref = normalize_reference(bank_reference)
    for c in sorted(candidates, key=lambda c: c.id):
        if c.normalized_reference and (
            c.normalized_reference in norm_desc or c.normalized_reference in norm_bank_ref
        ):
            return c.reference
    tokens = _CODE_RE.findall(description)
    if tokens:
        return tokens[0].strip().upper()
    return ""


def match_credit(
    amount: Decimal,
    tx_date: date,
    description: str,
    bank_reference: str,
    candidates: Sequence[Candidate],
) -> MatchResult:
    eligible = sorted(
        (c for c in candidates if c.remaining > 0 and c.call_date <= tx_date),
        key=lambda c: c.id,
    )
    ref_hits = [
        (c, _reference_location(c.normalized_reference, description, bank_reference))
        for c in eligible
    ]
    ref_hits = [(c, loc) for c, loc in ref_hits if loc]
    if ref_hits:
        if len(ref_hits) == 1:
            hit, loc = ref_hits[0]
            found = (
                f"Reference {hit.reference} found in bank reference"
                if loc == "bank"
                else f"Reference {hit.reference} found"
            )
            if amount <= hit.remaining:
                if amount == hit.remaining:
                    reason = f"{found}; amount equals remaining {money(hit.remaining)}"
                else:
                    reason = (
                        f"{found}; partial payment, {money(hit.remaining - amount)} "
                        f"will remain ({money(amount)} of {money(hit.remaining)})"
                    )
                return MatchResult(
                    status="suggested",
                    matches=(ProposedMatch(line_item_id=hit.id, reason=reason),),
                    reason=reason,
                    rule="reference",
                )
            reason = (
                f"{found}; amount {money(amount)} exceeds remaining "
                f"{money(hit.remaining)} (overpayment)"
            )
            return MatchResult(
                status="needs_review", matches=(), reason=reason, rule="reference"
            )
        matches = tuple(
            ProposedMatch(
                line_item_id=c.id,
                reason=(
                    f"Reference {c.reference} found"
                    f"{' in bank reference' if loc == 'bank' else ''}; "
                    f"amount {money(amount)}"
                ),
            )
            for c, loc in ref_hits
        )
        reason = "Reference matches multiple line items: " + ", ".join(
            c.reference for c, _ in ref_hits
        )
        return MatchResult(
            status="needs_review", matches=matches, reason=reason, rule="reference"
        )

    name_hits = [
        c
        for c in eligible
        if c.remaining == amount and name_found(c.normalized_name, description)
    ]
    if len(name_hits) == 1:
        hit = name_hits[0]
        reason = (
            f"Investor {hit.investor_name} matches '{description.strip()}' "
            f"for exact amount {money(amount)} (line item {hit.reference})"
        )
        return MatchResult(
            status="suggested",
            matches=(ProposedMatch(line_item_id=hit.id, reason=reason),),
            reason=reason,
            rule="name_and_amount",
        )
    if len(name_hits) > 1:
        matches = tuple(
            ProposedMatch(
                line_item_id=c.id,
                reason=(
                    f"Investor {c.investor_name} matches '{description.strip()}' "
                    f"for exact amount {money(amount)} (line item {c.reference})"
                ),
            )
            for c in name_hits
        )
        reason = "Multiple line items match '{}' for amount {}: {}".format(
            description.strip(), money(amount), ", ".join(c.reference for c in name_hits)
        )
        return MatchResult(
            status="needs_review", matches=matches, reason=reason, rule="name_and_amount"
        )
    code = _unmatched_code(description, bank_reference, candidates)
    if code:
        return MatchResult(
            status="needs_review",
            matches=(),
            reason=f"Reference {code} does not match an eligible line item in this organization",
        )
    return MatchResult(
        status="needs_review",
        matches=(),
        reason=f"No matching line item found for amount {money(amount)}",
    )
