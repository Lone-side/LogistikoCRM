# mydata/admin.py
"""
Django Admin για myDATA models.

Παρέχει interface για:
- MyDataCredentials: Διαχείριση credentials ανά πελάτη
- VATRecord: Προβολή VAT records
- MyDataSyncLog: Ιστορικό sync operations
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import MyDataCredentials, VATRecord, VATSyncLog


@admin.register(MyDataCredentials)
class MyDataCredentialsAdmin(admin.ModelAdmin):
    """Admin για myDATA Credentials."""

    list_display = [
        'client_display',
        'environment_badge',
        'status_badge',
        'last_sync_display',
        'has_credentials_icon',
    ]
    list_filter = ['is_sandbox', 'is_active', 'is_verified']
    search_fields = ['client__afm', 'client__eponimia']
    readonly_fields = [
        'is_verified',
        'verification_error',
        'last_sync_at',
        'last_vat_sync_at',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        ('Πελάτης', {
            'fields': ('client',)
        }),
        ('Credentials', {
            'fields': ('_encrypted_user_id', '_encrypted_subscription_key', 'is_sandbox'),
            'description': 'Τα credentials αποθηκεύονται κρυπτογραφημένα.'
        }),
        ('Κατάσταση', {
            'fields': ('is_active', 'is_verified', 'verification_error'),
        }),
        ('Sync Info', {
            'fields': ('last_sync_at', 'last_vat_sync_at', 'last_income_mark', 'last_expense_mark'),
            'classes': ('collapse',),
        }),
        ('Σημειώσεις', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def client_display(self, obj):
        return f"{obj.client.eponimia} ({obj.client.afm})"
    client_display.short_description = 'Πελάτης'
    client_display.admin_order_field = 'client__eponimia'

    def environment_badge(self, obj):
        if obj.is_sandbox:
            return format_html(
                '<span style="background:#ffc107;color:#000;padding:2px 8px;'
                'border-radius:3px;font-size:11px;">SANDBOX</span>'
            )
        return format_html(
            '<span style="background:#28a745;color:#fff;padding:2px 8px;'
            'border-radius:3px;font-size:11px;">PRODUCTION</span>'
        )
    environment_badge.short_description = 'Environment'

    def status_badge(self, obj):
        if not obj.is_active:
            return format_html(
                '<span style="color:#6c757d;">Ανενεργό</span>'
            )
        if obj.is_verified:
            return format_html(
                '<span style="color:#28a745;">Επιβεβαιωμένο</span>'
            )
        return format_html(
            '<span style="color:#dc3545;">Μη επιβεβαιωμένο</span>'
        )
    status_badge.short_description = 'Κατάσταση'

    def last_sync_display(self, obj):
        if obj.last_vat_sync_at:
            return obj.last_vat_sync_at.strftime('%d/%m/%Y %H:%M')
        return '-'
    last_sync_display.short_description = 'Τελευταίο Sync'

    def has_credentials_icon(self, obj):
        if obj.has_credentials:
            return format_html('<span style="color:green;">&#10004;</span>')
        return format_html('<span style="color:red;">&#10008;</span>')
    has_credentials_icon.short_description = 'Credentials'

    actions = ['verify_credentials_action', 'sync_vat_action']

    @admin.action(description='Επαλήθευση credentials')
    def verify_credentials_action(self, request, queryset):
        verified = 0
        failed = 0
        for cred in queryset:
            if cred.verify_credentials():
                verified += 1
            else:
                failed += 1

        self.message_user(
            request,
            f"Επαληθεύτηκαν: {verified}, Απέτυχαν: {failed}"
        )

    @admin.action(description='Sync VAT (τελευταίος μήνας)')
    def sync_vat_action(self, request, queryset):
        from django.core.management import call_command
        from io import StringIO

        for cred in queryset:
            if cred.has_credentials and cred.is_active:
                out = StringIO()
                try:
                    call_command(
                        'mydata_sync_vat',
                        client=cred.client.afm,
                        days=30,
                        stdout=out
                    )
                    self.message_user(request, f"Sync {cred.client.afm}: OK")
                except Exception as e:
                    self.message_user(
                        request,
                        f"Sync {cred.client.afm}: {str(e)}",
                        level='ERROR'
                    )


@admin.register(VATRecord)
class VATRecordAdmin(admin.ModelAdmin):
    """Admin για VAT Records."""

    list_display = [
        'client_afm',
        'issue_date',
        'rec_type_display',
        'inv_type',
        'expense_category',
        'vat_category_display',
        'net_value',
        'vat_amount',
        'gross_value_display',
        'is_cancelled_icon',
    ]
    list_filter = [
        'rec_type',
        'expense_category',
        'vat_category',
        'is_cancelled',
        ('issue_date', admin.DateFieldListFilter),
    ]
    search_fields = ['client__afm', 'client__eponimia', 'counter_vat_number', 'mark']
    date_hierarchy = 'issue_date'
    ordering = ['-issue_date', '-mark']

    readonly_fields = [
        'mark',
        'fetched_at',
        'updated_at',
        'gross_value_display',
    ]

    fieldsets = (
        ('Πελάτης', {
            'fields': ('client', 'mark')
        }),
        ('Στοιχεία', {
            'fields': (
                'issue_date', 'rec_type', 'inv_type',
                'expense_category',
                'vat_category', 'vat_exemption_category'
            )
        }),
        ('Ποσά', {
            'fields': (
                'net_value', 'vat_amount', 'gross_value_display',
                'vat_offset_amount', 'deductions_amount'
            )
        }),
        ('Αντισυμβαλλόμενος', {
            'fields': ('counter_vat_number',),
            'classes': ('collapse',),
        }),
        ('Κατάσταση', {
            'fields': ('is_cancelled',)
        }),
        ('Metadata', {
            'fields': ('fetched_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def client_afm(self, obj):
        return obj.client.afm
    client_afm.short_description = 'ΑΦΜ'
    client_afm.admin_order_field = 'client__afm'

    def rec_type_display(self, obj):
        if obj.rec_type == 1:
            return format_html(
                '<span style="color:#28a745;">Εκροή</span>'
            )
        return format_html(
            '<span style="color:#dc3545;">Εισροή</span>'
        )
    rec_type_display.short_description = 'Τύπος'
    rec_type_display.admin_order_field = 'rec_type'

    def vat_category_display(self, obj):
        return obj.vat_rate_display
    vat_category_display.short_description = 'ΦΠΑ'
    vat_category_display.admin_order_field = 'vat_category'

    def gross_value_display(self, obj):
        return f"{obj.gross_value:.2f}"
    gross_value_display.short_description = 'Σύνολο'

    def is_cancelled_icon(self, obj):
        if obj.is_cancelled:
            return format_html('<span style="color:red;">ΑΚΥΡΟ</span>')
        return ''
    is_cancelled_icon.short_description = ''


@admin.register(VATSyncLog)
class VATSyncLogAdmin(admin.ModelAdmin):
    """Admin για VAT Sync Logs."""

    list_display = [
        'started_at',
        'client_display',
        'sync_type',
        'status_badge',
        'records_summary',
        'duration_display',
    ]
    list_filter = [
        'sync_type',
        'status',
        ('started_at', admin.DateFieldListFilter),
    ]
    search_fields = ['client__afm', 'client__eponimia', 'error_message']
    date_hierarchy = 'started_at'
    ordering = ['-started_at']

    readonly_fields = [
        'client',
        'sync_type',
        'status',
        'date_from',
        'date_to',
        'started_at',
        'completed_at',
        'records_fetched',
        'records_created',
        'records_updated',
        'records_skipped',
        'records_failed',
        'error_message',
        'details',
        'duration_display',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def client_display(self, obj):
        if obj.client:
            return f"{obj.client.eponimia} ({obj.client.afm})"
        return '-'
    client_display.short_description = 'Πελάτης'

    def status_badge(self, obj):
        colors = {
            'SUCCESS': '#28a745',
            'ERROR': '#dc3545',
            'PARTIAL': '#ffc107',
            'PENDING': '#17a2b8',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:3px;font-size:11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Κατάσταση'

    def records_summary(self, obj):
        return f"F:{obj.records_fetched} C:{obj.records_created} U:{obj.records_updated} E:{obj.records_failed}"
    records_summary.short_description = 'Records'

    def duration_display(self, obj):
        return obj.duration_display
    duration_display.short_description = 'Διάρκεια'
