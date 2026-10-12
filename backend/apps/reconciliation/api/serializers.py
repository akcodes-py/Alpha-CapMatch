from rest_framework import serializers


class MatchSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    line_item = serializers.IntegerField(source="line_item_id")
    line_item_reference = serializers.CharField(source="line_item.reference")
    investor_name = serializers.CharField(source="line_item.investor.name")
    amount_called = serializers.DecimalField(
        source="line_item.amount_called", max_digits=14, decimal_places=2
    )
    remaining = serializers.SerializerMethodField()
    status = serializers.CharField()
    rule = serializers.CharField()
    reason = serializers.CharField()
    def get_remaining(self, obj):
        return obj.line_item.amount_called - obj.line_item.amount_funded


class TransactionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    date = serializers.DateField()
    description = serializers.CharField()
    bank_reference = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    type = serializers.CharField()
    status = serializers.CharField()
    reason = serializers.CharField()
    airtable_record_id = serializers.CharField()
    airtable_sync_status = serializers.CharField()
    matches = MatchSerializer(many=True)


class LineItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference = serializers.CharField()
    investor = serializers.CharField(source="investor.name")
    capital_call = serializers.CharField(source="capital_call.name")
    call_date = serializers.DateField(source="capital_call.call_date")
    amount_called = serializers.DecimalField(max_digits=14, decimal_places=2)
    amount_funded = serializers.DecimalField(max_digits=14, decimal_places=2)
    remaining = serializers.SerializerMethodField()
    status = serializers.CharField()

    def get_remaining(self, obj):
        return obj.amount_called - obj.amount_funded


class ActivityLogSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    action = serializers.CharField()
    message = serializers.CharField()
    match = serializers.IntegerField(source="match_id", allow_null=True)
    created_at = serializers.DateTimeField()
