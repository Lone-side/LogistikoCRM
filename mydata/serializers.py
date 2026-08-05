# mydata/serializers.py
"""
Django REST Framework Serializers για myDATA module.

Παρέχει serialization για:
- MyDataCredentials (με masked secrets)
- VATRecord (με computed fields)
- VATSyncLog
- Custom summary serializers
"""

from rest_framework import serializers
from decimal import Decimal

from .models import MyDataCredentials, VATRecord, VATSyncLog


# =============================================================================
# CREDENTIALS SERIALIZERS
# =============================================================================

class MyDataCredentialsSerializer(serializers.ModelSerializer):
    """
    Serializer για MyDataCredentials.

    SECURITY: Τα credentials δεν επιστρέφονται ποτέ decrypted.
    Για update, χρησιμοποιείται ξεχωριστό endpoint.
    """

    client_afm = serializers.CharField(source='client.afm', read_only=True)
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    has_credentials = serializers.BooleanField(read_only=True)
    environment = serializers.SerializerMethodField()
    # Write-only fields for creating/updating credentials
    user_id = serializers.CharField(write_only=True, required=False)
    subscription_key = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = MyDataCredentials
        fields = [
            'id',
            'client',
            'client_afm',
            'client_name',
            'user_id',
            'subscription_key',
            'has_credentials',
            'is_sandbox',
            'environment',
            'is_active',
            'is_verified',
            'verification_error',
            'last_sync_at',
            'last_vat_sync_at',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'is_verified',
            'verification_error',
            'last_sync_at',
            'last_vat_sync_at',
            'created_at',
            'updated_at',
        ]

    def get_environment(self, obj):
        return 'sandbox' if obj.is_sandbox else 'production'


    def validate_client(self, client):
        """RBAC: το client FK δεν μπορεί να δείξει σε πελάτη εκτός ανάθεσης."""
        from accounting.services.access import user_can_access_client
        request = self.context.get('request')
        if request is not None and client is not None and \
                not user_can_access_client(request.user, client):
            raise serializers.ValidationError('Ο πελάτης δεν βρέθηκε.')
        return client

class CredentialsUpdateSerializer(serializers.Serializer):
    """
    Serializer για update credentials.

    Ξεχωριστός serializer για security - τα credentials
    γράφονται μόνο, δεν διαβάζονται ποτέ.
    """

    user_id = serializers.CharField(write_only=True, required=True)
    subscription_key = serializers.CharField(write_only=True, required=True)
    is_sandbox = serializers.BooleanField(required=False, default=False)

    def validate_user_id(self, value):
        if len(value) < 5:
            raise serializers.ValidationError("User ID πρέπει να έχει τουλάχιστον 5 χαρακτήρες")
        return value

    def validate_subscription_key(self, value):
        if len(value) < 10:
            raise serializers.ValidationError("Subscription Key πρέπει να έχει τουλάχιστον 10 χαρακτήρες")
        return value


# =============================================================================
# VAT RECORD SERIALIZERS
# =============================================================================

class VATRecordSerializer(serializers.ModelSerializer):
    """Serializer για VATRecord."""

    client_afm = serializers.CharField(source='client.afm', read_only=True)
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    gross_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    vat_rate = serializers.IntegerField(read_only=True)
    vat_rate_display = serializers.CharField(read_only=True)
    rec_type_display = serializers.CharField(source='get_rec_type_display', read_only=True)
    vat_category_display = serializers.CharField(source='get_vat_category_display', read_only=True)

    class Meta:
        model = VATRecord
        fields = [
            'id',
            'client',
            'client_afm',
            'client_name',
            'mark',
            'is_cancelled',
            'issue_date',
            'rec_type',
            'rec_type_display',
            'inv_type',
            'vat_category',
            'vat_category_display',
            'vat_exemption_category',
            'net_value',
            'vat_amount',
            'gross_value',
            'vat_rate',
            'vat_rate_display',
            'counter_vat_number',
            'vat_offset_amount',
            'deductions_amount',
            'fetched_at',
            'updated_at',
        ]
        read_only_fields = ['fetched_at', 'updated_at']


class VATRecordListSerializer(serializers.ModelSerializer):
    """Lightweight serializer για list views."""

    client_afm = serializers.CharField(source='client.afm', read_only=True)
    gross_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    vat_rate_display = serializers.CharField(read_only=True)

    class Meta:
        model = VATRecord
        fields = [
            'id',
            'client_afm',
            'mark',
            'issue_date',
            'rec_type',
            'inv_type',
            'vat_category',
            'vat_rate_display',
            'net_value',
            'vat_amount',
            'gross_value',
            'is_cancelled',
        ]


# =============================================================================
# VAT SYNC LOG SERIALIZER
# =============================================================================

class VATSyncLogSerializer(serializers.ModelSerializer):
    """Serializer για VATSyncLog."""

    client_afm = serializers.CharField(source='client.afm', read_only=True, allow_null=True)
    client_name = serializers.CharField(source='client.eponimia', read_only=True, allow_null=True)
    duration_display = serializers.CharField(read_only=True)
    sync_type_display = serializers.CharField(source='get_sync_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = VATSyncLog
        fields = [
            'id',
            'client',
            'client_afm',
            'client_name',
            'sync_type',
            'sync_type_display',
            'status',
            'status_display',
            'date_from',
            'date_to',
            'started_at',
            'completed_at',
            'duration_display',
            'records_fetched',
            'records_created',
            'records_updated',
            'records_skipped',
            'records_failed',
            'error_message',
        ]


# =============================================================================
# SUMMARY SERIALIZERS
# =============================================================================

class VATPeriodSummarySerializer(serializers.Serializer):
    """Summary για μια περίοδο (μήνα)."""

    year = serializers.IntegerField()
    month = serializers.IntegerField()

    # Εκροές (Έσοδα)
    income_net = serializers.DecimalField(max_digits=15, decimal_places=2)
    income_vat = serializers.DecimalField(max_digits=15, decimal_places=2)
    income_gross = serializers.DecimalField(max_digits=15, decimal_places=2)
    income_count = serializers.IntegerField()

    # Εισροές (Έξοδα)
    expense_net = serializers.DecimalField(max_digits=15, decimal_places=2)
    expense_vat = serializers.DecimalField(max_digits=15, decimal_places=2)
    expense_gross = serializers.DecimalField(max_digits=15, decimal_places=2)
    expense_count = serializers.IntegerField()

    # Διαφορά
    net_difference = serializers.DecimalField(max_digits=15, decimal_places=2)
    vat_difference = serializers.DecimalField(max_digits=15, decimal_places=2)


class VATCategoryBreakdownSerializer(serializers.Serializer):
    """Breakdown ανά κατηγορία ΦΠΑ."""

    vat_category = serializers.IntegerField()
    vat_rate = serializers.IntegerField()
    vat_rate_display = serializers.CharField()
    net_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    vat_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    count = serializers.IntegerField()


class ClientVATSummarySerializer(serializers.Serializer):
    """Complete VAT summary για έναν πελάτη."""

    client_afm = serializers.CharField()
    client_name = serializers.CharField()
    has_credentials = serializers.BooleanField()
    is_verified = serializers.BooleanField()
    last_sync = serializers.DateTimeField(allow_null=True)

    # Current period summary
    current_period = VATPeriodSummarySerializer()

    # Breakdown by category
    income_by_category = VATCategoryBreakdownSerializer(many=True)
    expense_by_category = VATCategoryBreakdownSerializer(many=True)


class MultiClientSummarySerializer(serializers.Serializer):
    """Summary για πολλούς πελάτες (dashboard overview)."""

    total_clients = serializers.IntegerField()
    clients_with_credentials = serializers.IntegerField()
    verified_credentials = serializers.IntegerField()

    # Aggregated totals
    total_income_net = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_income_vat = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expense_net = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_expense_vat = serializers.DecimalField(max_digits=15, decimal_places=2)

    # Per-client breakdown
    clients = ClientVATSummarySerializer(many=True)


# =============================================================================
# VAT PERIOD RESULT SERIALIZERS
# =============================================================================

class VATPeriodResultSerializer(serializers.ModelSerializer):
    """Serializer για VATPeriodResult - βασική λίστα."""

    client_afm = serializers.CharField(source='client.afm', read_only=True)
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    period_display = serializers.CharField(source='get_period_display', read_only=True)
    is_payable = serializers.BooleanField(read_only=True)
    is_credit = serializers.BooleanField(read_only=True)

    class Meta:
        from .models import VATPeriodResult
        model = VATPeriodResult
        fields = [
            'id', 'client', 'client_afm', 'client_name',
            'period_type', 'year', 'period', 'period_display',
            'vat_output', 'vat_input', 'vat_difference',
            'previous_credit', 'final_result', 'credit_to_next',
            'is_locked', 'locked_at', 'is_payable', 'is_credit',
            'last_calculated_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'vat_output', 'vat_input', 'vat_difference',
            'final_result', 'credit_to_next',
            'is_locked', 'locked_at', 'last_calculated_at',
            'created_at', 'updated_at'
        ]


    def validate_client(self, client):
        """RBAC: το client FK δεν μπορεί να δείξει σε πελάτη εκτός ανάθεσης."""
        from accounting.services.access import user_can_access_client
        request = self.context.get('request')
        if request is not None and client is not None and \
                not user_can_access_client(request.user, client):
            raise serializers.ValidationError('Ο πελάτης δεν βρέθηκε.')
        return client

class VATPeriodResultDetailSerializer(VATPeriodResultSerializer):
    """Detailed serializer για VATPeriodResult."""

    locked_by_name = serializers.SerializerMethodField()
    months_in_period = serializers.ListField(read_only=True)
    period_start_date = serializers.DateField(read_only=True)
    period_end_date = serializers.DateField(read_only=True)

    class Meta(VATPeriodResultSerializer.Meta):
        fields = VATPeriodResultSerializer.Meta.fields + [
            'locked_by', 'locked_by_name',
            'months_synced', 'months_in_period',
            'period_start_date', 'period_end_date',
            'notes'
        ]

    def get_locked_by_name(self, obj):
        if obj.locked_by:
            return obj.locked_by.get_full_name() or obj.locked_by.username
        return None


class InvoiceItemSerializer(serializers.Serializer):
    """Γραμμή τιμολογίου (read-only, για την οθόνη αποστολής myDATA)."""
    line_number = serializers.IntegerField()
    description = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    net_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    vat_category = serializers.IntegerField()
    vat_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class InvoiceListSerializer(serializers.Serializer):
    """inventory.Invoice για τη λίστα/αποστολή myDATA (read-only)."""
    id = serializers.IntegerField(read_only=True)
    series = serializers.CharField()
    number = serializers.CharField()
    invoice_type = serializers.CharField()
    invoice_type_display = serializers.CharField(
        source='get_invoice_type_display', read_only=True
    )
    issue_date = serializers.DateField()
    counterpart_name = serializers.CharField()
    counterpart_vat = serializers.CharField()
    is_outgoing = serializers.BooleanField()
    total_net = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_vat = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_gross = serializers.DecimalField(max_digits=12, decimal_places=2)
    mydata_mark = serializers.IntegerField(allow_null=True)
    mydata_uid = serializers.CharField(allow_blank=True)
    mydata_sent = serializers.BooleanField()
    mydata_sent_at = serializers.DateTimeField(allow_null=True)
    mydata_cancelled = serializers.BooleanField()
    mydata_cancellation_mark = serializers.IntegerField(allow_null=True)
    correlated_mark = serializers.IntegerField(allow_null=True)
    notes = serializers.CharField(allow_blank=True)
    items = InvoiceItemSerializer(many=True, read_only=True)
