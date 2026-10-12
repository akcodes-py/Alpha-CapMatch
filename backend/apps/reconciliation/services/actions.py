from decimal import Decimal

from django.db import transaction as db_transaction

from ..api.errors import ConflictError, NotFoundError
from ..models import (
    ActivityAction,
    ActivityLog,
    BankTransaction,
    LineItem,
    LineItemStatus,
    Match,
    MatchStatus,
    Organization,
    TransactionStatus,
    TransactionType,
)


def line_status_for(called: Decimal, funded: Decimal) -> str:
    if funded >= called:
        return LineItemStatus.FUNDED
    if funded > 0:
        return LineItemStatus.PARTIALLY_FUNDED
    return LineItemStatus.OPEN


def approve_match(organization: Organization, match_id: int) -> tuple[Match, BankTransaction, LineItem]:
    with db_transaction.atomic():
        try:
            match = (
                Match.objects.select_for_update()
                .select_related("transaction")
                .get(id=match_id, transaction__organization=organization)
            )
        except Match.DoesNotExist:
            raise NotFoundError(f"Match {match_id} not found")
        tx = match.transaction
        if match.status != MatchStatus.PROPOSED:
            raise ConflictError(f"Match {match_id} is {match.status}, only proposed matches can be approved")
        if tx.status in (TransactionStatus.RECONCILED, TransactionStatus.IGNORED):
            raise ConflictError(f"Transaction {tx.id} is {tx.status} and cannot be approved")
        try:
            item = LineItem.objects.select_for_update().get(
                id=match.line_item_id, organization=organization
            )
        except LineItem.DoesNotExist:
            raise NotFoundError(f"Line item {match.line_item_id} not found")
        remaining = item.amount_called - item.amount_funded
        if tx.amount > remaining:
            raise ConflictError(
                f"Amount {tx.amount} exceeds remaining {remaining} on {item.reference}"
            )
        item.amount_funded = item.amount_funded + tx.amount
        item.status = line_status_for(item.amount_called, item.amount_funded)
        item.save()
        match.status = MatchStatus.APPROVED
        match.save()
        Match.objects.filter(transaction=tx, status=MatchStatus.PROPOSED).exclude(
            id=match.id
        ).update(status=MatchStatus.REJECTED)
        tx.status = TransactionStatus.RECONCILED
        tx.save()
        ActivityLog.objects.create(
            organization=organization,
            transaction=tx,
            match=match,
            action=ActivityAction.APPROVED,
            message=f"Approved {item.reference}, funded {tx.amount}",
        )
    return match, tx, item


def reject_match(organization: Organization, match_id: int) -> tuple[Match, BankTransaction]:
    with db_transaction.atomic():
        try:
            match = (
                Match.objects.select_for_update()
                .select_related("transaction", "line_item")
                .get(id=match_id, transaction__organization=organization)
            )
        except Match.DoesNotExist:
            raise NotFoundError(f"Match {match_id} not found")
        if match.status != MatchStatus.PROPOSED:
            raise ConflictError(f"Match {match_id} is {match.status}, only proposed matches can be rejected")
        tx = match.transaction
        match.status = MatchStatus.REJECTED
        match.save()
        ActivityLog.objects.create(
            organization=organization,
            transaction=tx,
            match=match,
            action=ActivityAction.REJECTED,
            message=f"Rejected {match.line_item.reference}",
        )
        if not Match.objects.filter(transaction=tx, status=MatchStatus.PROPOSED).exists():
            if tx.status in (TransactionStatus.SUGGESTED, TransactionStatus.NEEDS_REVIEW):
                tx.status = TransactionStatus.NEEDS_REVIEW
                tx.reason = "All proposed matches were rejected"
                tx.save()
    return match, tx


def ignore_transaction(organization: Organization, tx_id: int) -> BankTransaction:
    with db_transaction.atomic():
        try:
            tx = BankTransaction.objects.select_for_update().get(
                id=tx_id, organization=organization
            )
        except BankTransaction.DoesNotExist:
            raise NotFoundError(f"Transaction {tx_id} not found")
        if tx.status not in (TransactionStatus.SUGGESTED, TransactionStatus.NEEDS_REVIEW):
            raise ConflictError(f"Transaction {tx.id} is {tx.status} and cannot be ignored")
        tx.status = TransactionStatus.IGNORED
        tx.save()
        Match.objects.filter(transaction=tx, status=MatchStatus.PROPOSED).update(
            status=MatchStatus.REJECTED
        )
        ActivityLog.objects.create(
            organization=organization,
            transaction=tx,
            action=ActivityAction.IGNORED,
            message="Ignored transaction",
        )
    return tx


def unignore_transaction(organization: Organization, tx_id: int) -> BankTransaction:
    with db_transaction.atomic():
        try:
            tx = BankTransaction.objects.select_for_update().get(
                id=tx_id, organization=organization
            )
        except BankTransaction.DoesNotExist:
            raise NotFoundError(f"Transaction {tx_id} not found")
        if tx.status != TransactionStatus.IGNORED:
            raise ConflictError(f"Transaction {tx.id} is {tx.status}, only ignored rows can be un-ignored")
        if tx.type != TransactionType.CREDIT:
            raise ConflictError("Only ignored credits can be un-ignored")
        tx.status = TransactionStatus.NEEDS_REVIEW
        tx.reason = "Un-ignored by the GP"
        tx.save()
        ActivityLog.objects.create(
            organization=organization,
            transaction=tx,
            action=ActivityAction.UNIGNORED,
            message="Un-ignored back to needs_review",
        )
    return tx
