from django.urls import path

from .views import (
    approve_match_view,
    export_transactions_view,
    health_view,
    ignore_transaction_view,
    import_csv_view,
    line_item_list_view,
    preview_csv_view,
    reject_match_view,
    transaction_history_view,
    transaction_list_view,
    unignore_transaction_view,
)

urlpatterns = [
    path("health/", health_view, name="health"),
    path("imports/", import_csv_view, name="import-csv"),
    path("imports/preview/", preview_csv_view, name="import-preview"),
    path("transactions/", transaction_list_view, name="transaction-list"),
    path("transactions/export/", export_transactions_view, name="transaction-export"),
    path("transactions/<int:tx_id>/ignore/", ignore_transaction_view, name="transaction-ignore"),
    path("transactions/<int:tx_id>/unignore/", unignore_transaction_view, name="transaction-unignore"),
    path("transactions/<int:tx_id>/history/", transaction_history_view, name="transaction-history"),
    path("matches/<int:match_id>/approve/", approve_match_view, name="match-approve"),
    path("matches/<int:match_id>/reject/", reject_match_view, name="match-reject"),
    path("line-items/", line_item_list_view, name="line-item-list"),
]
