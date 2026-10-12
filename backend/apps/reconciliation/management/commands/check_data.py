from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum

from apps.reconciliation.models import (
    BankTransaction,
    LineItem,
    Match,
    MatchStatus,
    Organization,
    TransactionStatus,
)


class Command(BaseCommand):
    help = "Verify reconciliation invariants for every organization."

    def handle(self, *args, **options):
        problems: list[str] = []
        for org in Organization.objects.order_by("slug"):
            for item in LineItem.objects.filter(organization=org).order_by("reference"):
                if not (Decimal("0") <= item.amount_funded <= item.amount_called):
                    problems.append(
                        f"{org.slug} {item.reference}: funded {item.amount_funded} "
                        f"outside [0, {item.amount_called}]"
                    )
                approved_total = (
                    Match.objects.filter(line_item=item, status=MatchStatus.APPROVED).aggregate(
                        total=Sum("transaction__amount")
                    )["total"]
                    or Decimal("0")
                )
                if item.amount_funded != approved_total:
                    problems.append(
                        f"{org.slug} {item.reference}: funded {item.amount_funded} != "
                        f"approved total {approved_total}"
                    )
            for tx in BankTransaction.objects.filter(organization=org).order_by("id"):
                approved = tx.matches.filter(status=MatchStatus.APPROVED).count()
                if tx.status == TransactionStatus.RECONCILED and approved != 1:
                    problems.append(
                        f"{org.slug} {tx.bank_reference}: reconciled with {approved} approved matches"
                    )
                if tx.status in (TransactionStatus.IGNORED, TransactionStatus.NEEDS_REVIEW) and approved:
                    problems.append(
                        f"{org.slug} {tx.bank_reference}: {tx.status} with an approved match"
                    )
        if problems:
            for problem in problems:
                self.stdout.write(problem)
            raise CommandError(f"check_data found {len(problems)} problem(s)")
        self.stdout.write(self.style.SUCCESS("check_data ok"))
