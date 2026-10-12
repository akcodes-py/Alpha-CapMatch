import csv

from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..models import ActivityLog, BankTransaction, LineItem, TransactionStatus
from ..services import actions
from ..services.importing import import_csv
from .errors import NotFoundError, ServiceError
from .org import resolve_organization
from .serializers import ActivityLogSerializer, LineItemSerializer, TransactionSerializer


class MissingFileError(ServiceError):
    status_code = 400
    default_code = "missing_file"


def _read_upload(request) -> bytes:
    upload = request.FILES.get("file")
    if upload is None:
        raise MissingFileError("No file uploaded (expected multipart field 'file')")
    return upload.read()


def _full_transaction(tx_id: int, org) -> dict:
    tx = (
        BankTransaction.objects.filter(id=tx_id, organization=org)
        .prefetch_related("matches__line_item__investor", "matches__line_item__capital_call")
        .get()
    )
    return TransactionSerializer(tx).data


@api_view(["GET"])
def health_view(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def import_csv_view(request):
    org = resolve_organization(request)
    result = import_csv(org, _read_upload(request))
    return Response(result, status=201)


@api_view(["POST"])
def preview_csv_view(request):
    org = resolve_organization(request)
    result = import_csv(org, _read_upload(request), dry_run=True)
    return Response(result)


@api_view(["GET"])
def transaction_list_view(request):
    org = resolve_organization(request)
    transactions = (
        BankTransaction.objects.filter(organization=org)
        .prefetch_related("matches__line_item__investor", "matches__line_item__capital_call")
        .order_by("-date", "-id")
    )
    return Response(TransactionSerializer(transactions, many=True).data)


@api_view(["GET"])
def line_item_list_view(request):
    org = resolve_organization(request)
    items = (
        LineItem.objects.filter(organization=org)
        .select_related("investor", "capital_call")
        .order_by("reference")
    )
    return Response(LineItemSerializer(items, many=True).data)


@api_view(["POST"])
def approve_match_view(request, match_id: int):
    org = resolve_organization(request)
    match, tx, item = actions.approve_match(org, match_id)
    item_data = LineItemSerializer(
        LineItem.objects.select_related("investor", "capital_call").get(
            id=item.id, organization=org
        )
    ).data
    return Response(
        {
            "transaction": _full_transaction(tx.id, org),
            "match": {"id": match.id, "status": match.status},
            "line_item": item_data,
        }
    )


@api_view(["POST"])
def reject_match_view(request, match_id: int):
    org = resolve_organization(request)
    match, tx = actions.reject_match(org, match_id)
    return Response(
        {
            "id": match.id,
            "status": match.status,
            "transaction": tx.id,
            "transaction_status": tx.status,
        }
    )


@api_view(["POST"])
def ignore_transaction_view(request, tx_id: int):
    org = resolve_organization(request)
    tx = actions.ignore_transaction(org, tx_id)
    return Response(_full_transaction(tx.id, org))


@api_view(["POST"])
def unignore_transaction_view(request, tx_id: int):
    org = resolve_organization(request)
    tx = actions.unignore_transaction(org, tx_id)
    return Response(_full_transaction(tx.id, org))


@api_view(["GET"])
def transaction_history_view(request, tx_id: int):
    org = resolve_organization(request)
    try:
        tx = BankTransaction.objects.get(id=tx_id, organization=org)
    except BankTransaction.DoesNotExist:
        raise NotFoundError(f"Transaction {tx_id} not found")
    logs = ActivityLog.objects.filter(transaction=tx).order_by("-created_at", "-id")
    return Response(ActivityLogSerializer(logs, many=True).data)


class _Echo:
    def write(self, value):
        return value


def _safe_cell(cell) -> str:
    text = "" if cell is None else str(cell)
    if text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text


@api_view(["GET"])
def export_transactions_view(request):
    org = resolve_organization(request)
    status = request.query_params.get("status", TransactionStatus.NEEDS_REVIEW)
    if status not in TransactionStatus.values:
        raise ServiceError("Unknown status", code="invalid_status", status_code=400)
    rows = (
        BankTransaction.objects.filter(organization=org, status=status)
        .order_by("-date", "-id")
        .values_list("date", "description", "amount", "bank_reference", "status", "reason")
    )
    writer = csv.writer(_Echo())

    def stream():
        yield writer.writerow(
            ["date", "description", "amount", "bank_reference", "status", "reason"]
        )
        for row_date, description, amount, bank_reference, row_status, reason in rows.iterator():
            yield writer.writerow(
                [
                    str(row_date),
                    _safe_cell(description),
                    str(amount),
                    _safe_cell(bank_reference),
                    _safe_cell(row_status),
                    _safe_cell(reason or ""),
                ]
            )

    response = StreamingHttpResponse(stream(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{status}.csv"'
    return response
