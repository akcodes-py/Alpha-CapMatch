from decimal import Decimal

from django.db import models


class Organization(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)

    def __str__(self) -> str:
        return self.slug


class Investor(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="investors")
    name = models.CharField(max_length=200)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="uniq_investor_org_name"),
        ]
        indexes = [models.Index(fields=["organization"])]

    def __str__(self) -> str:
        return self.name


class CapitalCall(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="capital_calls"
    )
    name = models.CharField(max_length=200)
    call_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="uniq_call_org_name"),
        ]
        indexes = [models.Index(fields=["organization"])]

    def __str__(self) -> str:
        return self.name


class LineItemStatus(models.TextChoices):
    OPEN = "open", "Open"
    PARTIALLY_FUNDED = "partially_funded", "Partially funded"
    FUNDED = "funded", "Funded"


class LineItem(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="line_items"
    )
    investor = models.ForeignKey(Investor, on_delete=models.CASCADE, related_name="line_items")
    capital_call = models.ForeignKey(
        CapitalCall, on_delete=models.CASCADE, related_name="line_items"
    )
    reference = models.CharField(max_length=50)
    amount_called = models.DecimalField(max_digits=14, decimal_places=2)
    amount_funded = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(
        max_length=20, choices=LineItemStatus.choices, default=LineItemStatus.OPEN
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"], name="uniq_lineitem_org_reference"
            ),
            models.CheckConstraint(
                condition=models.Q(amount_funded__gte=0, amount_funded__lte=models.F("amount_called")),
                name="chk_lineitem_funded_range",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "reference"]),
        ]

    @property
    def remaining(self) -> Decimal:
        return self.amount_called - self.amount_funded

    def __str__(self) -> str:
        return self.reference


class TransactionType(models.TextChoices):
    CREDIT = "credit", "Credit"
    DEBIT = "debit", "Debit"


class TransactionStatus(models.TextChoices):
    SUGGESTED = "suggested", "Suggested"
    NEEDS_REVIEW = "needs_review", "Needs review"
    RECONCILED = "reconciled", "Reconciled"
    IGNORED = "ignored", "Ignored"


class AirtableSyncStatus(models.TextChoices):
    NOT_SYNCED = "not_synced", "Not synced"
    SYNCED = "synced", "Synced"
    SYNC_FAILED = "sync_failed", "Sync failed"


class BankTransaction(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="transactions"
    )
    date = models.DateField()
    description = models.CharField(max_length=500)
    bank_reference = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    type = models.CharField(max_length=10, choices=TransactionType.choices)
    status = models.CharField(
        max_length=20, choices=TransactionStatus.choices, default=TransactionStatus.NEEDS_REVIEW
    )
    reason = models.TextField(blank=True, default="")
    airtable_record_id = models.CharField(max_length=64, blank=True, default="")
    airtable_sync_status = models.CharField(
        max_length=20,
        choices=AirtableSyncStatus.choices,
        default=AirtableSyncStatus.NOT_SYNCED,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "bank_reference"], name="uniq_tx_org_bankref"
            ),
            models.CheckConstraint(condition=~models.Q(amount=0), name="chk_tx_amount_nonzero"),
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "date"]),
        ]

    def __str__(self) -> str:
        return self.bank_reference

class MatchStatus(models.TextChoices):
    PROPOSED = "proposed", "Proposed"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class MatchRule(models.TextChoices):
    REFERENCE = "reference", "Reference"
    NAME_AND_AMOUNT = "name_and_amount", "Name and amount"


class Match(models.Model):
    transaction = models.ForeignKey(
        BankTransaction, on_delete=models.CASCADE, related_name="matches"
    )
    line_item = models.ForeignKey(LineItem, on_delete=models.CASCADE, related_name="matches")
    status = models.CharField(
        max_length=10, choices=MatchStatus.choices, default=MatchStatus.PROPOSED
    )
    rule = models.CharField(max_length=15, choices=MatchRule.choices)
    reason = models.TextField(blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["transaction", "status"])]

    def __str__(self) -> str:
        return f"{self.transaction_id}->{self.line_item_id} ({self.status})"


class ActivityAction(models.TextChoices):
    IMPORTED = "imported", "Imported"
    SUGGESTED = "suggested", "Suggested"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    IGNORED = "ignored", "Ignored"
    UNIGNORED = "unignored", "Unignored"


class ActivityLog(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="activity_logs"
    )
    transaction = models.ForeignKey(
        BankTransaction, null=True, blank=True, on_delete=models.CASCADE, related_name="activity_logs"
    )
    match = models.ForeignKey(
        Match, null=True, blank=True, on_delete=models.CASCADE, related_name="activity_logs"
    )
    action = models.CharField(max_length=10, choices=ActivityAction.choices)
    message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "created_at"])]

    def __str__(self) -> str:
        return f"{self.action} tx={self.transaction_id} match={self.match_id}"
