from django.db import transaction

from ..models import (
    ActivityAction,
    ActivityLog,
    BankTransaction,
    LineItem,
    Match,
    MatchRule,
    MatchStatus,
    Organization,
    TransactionStatus,
    TransactionType,
)
from ..api.errors import ServiceError
from .airtable import sync_needs_review_transactions
from .matching import build_candidates, match_credit
from .parsing import HeaderError, ValidRow, decode_upload, parse_csv_text


class InvalidHeaderError(ServiceError):
    status_code = 400
    default_code = "invalid_header"


def import_csv(organization: Organization, data: bytes, dry_run: bool = False) -> dict:
    text = decode_upload(data)
    try:
        rows, errors = parse_csv_text(text)
    except HeaderError as exc:
        raise InvalidHeaderError(f"Missing columns: {', '.join(exc.missing)}")

    existing = set(
        BankTransaction.objects.filter(organization=organization).values_list(
            "bank_reference", flat=True
        )
    )
    candidates = build_candidates(
        LineItem.objects.filter(organization=organization).select_related(
            "investor", "capital_call"
        )
    )

    tx_to_create: list[BankTransaction] = []
    pending_matches: list[tuple[ValidRow, tuple]] = []
    seen: set[str] = set()
    duplicates = 0

    for row in rows:
        if row.bank_reference in existing or row.bank_reference in seen:
            duplicates += 1
            continue
        seen.add(row.bank_reference)
        if row.type == TransactionType.DEBIT:
            tx_to_create.append(
                BankTransaction(
                    organization=organization,
                    date=row.date,
                    description=row.description,
                    bank_reference=row.bank_reference,
                    amount=row.amount,
                    type=TransactionType.DEBIT,
                    status=TransactionStatus.IGNORED,
                    reason="Debit transactions are ignored",
                )
            )
            continue
        result = match_credit(
            row.amount, row.date, row.description, row.bank_reference, candidates
        )
        tx_to_create.append(
            BankTransaction(
                organization=organization,
                date=row.date,
                description=row.description,
                bank_reference=row.bank_reference,
                amount=row.amount,
                type=TransactionType.CREDIT,
                status=result.status,
                reason="" if result.status == TransactionStatus.SUGGESTED else result.reason,
            )
        )
        pending_matches.append((row, result))

    if dry_run:
        by_status = {
            TransactionStatus.SUGGESTED: 0,
            TransactionStatus.NEEDS_REVIEW: 0,
            TransactionStatus.IGNORED: 0,
        }
        for tx in tx_to_create:
            by_status[tx.status] += 1
        return {
            "would_import": len(tx_to_create),
            "duplicates": duplicates,
            "errors": errors,
            "by_status": by_status,
        }

    with transaction.atomic():
        created = BankTransaction.objects.bulk_create(tx_to_create)
        created_by_ref = {tx.bank_reference: tx for tx in created}
        matches = [
            Match(
                transaction=created_by_ref[row.bank_reference],
                line_item_id=proposed.line_item_id,
                status=MatchStatus.PROPOSED,
                reason=proposed.reason,
                rule=result.rule or MatchRule.REFERENCE,
            )
            for row, result in pending_matches
            if row.bank_reference in created_by_ref
            for proposed in result.matches
        ]
        created_matches = Match.objects.bulk_create(matches)
        references = {c.id: c.reference for c in candidates}
        logs = [
            ActivityLog(
                organization=organization,
                transaction=tx,
                action=ActivityAction.IMPORTED,
                message=f"Imported with status {tx.status}",
            )
            for tx in created
        ]
        logs += [
            ActivityLog(
                organization=organization,
                transaction=match.transaction,
                match=match,
                action=ActivityAction.SUGGESTED,
                message=f"Suggested {references.get(match.line_item_id, '')}: {match.reason}",
            )
            for match in created_matches
        ]
        ActivityLog.objects.bulk_create(logs)

    sync_needs_review_transactions(created)

    return {"imported": len(created), "duplicates": duplicates, "errors": errors}
