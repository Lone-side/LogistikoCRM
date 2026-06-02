# mydata/views.py
"""
Django REST Framework Views για myDATA module.

Παρέχει API endpoints για:
- VAT Records (list, detail, summaries)
- Credentials management
- Sync operations
- Dashboard data
"""

from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal, InvalidOperation
import logging

from django.db import transaction
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounting.models import ClientProfile
from accounting.permissions import IsStaffUser
from .models import MyDataCredentials, VATRecord, VATSyncLog
from .serializers import (
    MyDataCredentialsSerializer,
    CredentialsUpdateSerializer,
    VATRecordSerializer,
    VATRecordListSerializer,
    VATSyncLogSerializer,
    VATPeriodSummarySerializer,
    VATCategoryBreakdownSerializer,
    ClientVATSummarySerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_vat_rate_for_category(category: int) -> int:
    """Get VAT rate percentage for category."""
    rates = {1: 24, 2: 13, 3: 6, 4: 17, 5: 9, 6: 4, 7: 0, 8: 0}
    return rates.get(category, 0)


def get_vat_rate_display(category: int) -> str:
    """Get VAT rate display string."""
    rate = get_vat_rate_for_category(category)
    return f"{rate}%" if category < 8 else "Χωρίς ΦΠΑ"


def build_period_summary(client, year: int, month: int) -> dict:
    """Build complete period summary for a client."""
    income = VATRecord.get_period_summary(client, year, month, rec_type=1)
    expense = VATRecord.get_period_summary(client, year, month, rec_type=2)

    return {
        'year': year,
        'month': month,
        'income_net': income['net_value'],
        'income_vat': income['vat_amount'],
        'income_gross': income['gross_value'],
        'income_count': income['count'],
        'expense_net': expense['net_value'],
        'expense_vat': expense['vat_amount'],
        'expense_gross': expense['gross_value'],
        'expense_count': expense['count'],
        'net_difference': income['net_value'] - expense['net_value'],
        'vat_difference': income['vat_amount'] - expense['vat_amount'],
    }


def build_category_breakdown(client, year: int, month: int, rec_type: int) -> list:
    """Build VAT category breakdown for a period."""
    breakdown = VATRecord.get_period_by_category(client, year, month, rec_type)

    return [
        {
            'vat_category': item['vat_category'],
            'vat_rate': get_vat_rate_for_category(item['vat_category']),
            'vat_rate_display': get_vat_rate_display(item['vat_category']),
            'net_value': item['total_net'] or Decimal('0.00'),
            'vat_amount': item['total_vat'] or Decimal('0.00'),
            'count': item['record_count'] or 0,
        }
        for item in breakdown
    ]


def get_period_date_range(year: int, month: int = None, quarter: int = None, period_type: str = 'month'):
    """
    Calculate date range based on period type.

    Args:
        year: Year
        month: Month (1-12), used when period_type='month'
        quarter: Quarter (1-4), used when period_type='quarter'
        period_type: 'month', 'quarter', or 'year'

    Returns:
        Tuple (date_from, date_to, display_label)
    """
    if period_type == 'quarter':
        if quarter is None:
            quarter = 1
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        date_from = date(year, start_month, 1)
        last_day = monthrange(year, end_month)[1]
        date_to = date(year, end_month, last_day)
        label = f"Q{quarter} {year}"
    elif period_type == 'year':
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)
        label = str(year)
    else:  # month
        if month is None:
            month = 1
        date_from = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        date_to = date(year, month, last_day)
        label = f"{month}/{year}"

    return date_from, date_to, label


def build_date_range_summary(client, date_from, date_to) -> dict:
    """Build complete period summary for a client using date range."""
    income = VATRecord.get_date_range_summary(client, date_from, date_to, rec_type=1)
    expense = VATRecord.get_date_range_summary(client, date_from, date_to, rec_type=2)

    return {
        'income_net': float(income['net_value']),
        'income_vat': float(income['vat_amount']),
        'income_gross': float(income['gross_value']),
        'income_count': income['count'],
        'expense_net': float(expense['net_value']),
        'expense_vat': float(expense['vat_amount']),
        'expense_gross': float(expense['gross_value']),
        'expense_count': expense['count'],
        'net_difference': float(income['net_value'] - expense['net_value']),
        'vat_difference': float(income['vat_amount'] - expense['vat_amount']),
    }


def build_date_range_category_breakdown(client, date_from, date_to, rec_type: int) -> list:
    """Build VAT category breakdown for a date range."""
    breakdown = VATRecord.get_date_range_by_category(client, date_from, date_to, rec_type)

    return [
        {
            'vat_category': item['vat_category'],
            'vat_rate': get_vat_rate_for_category(item['vat_category']),
            'vat_rate_display': get_vat_rate_display(item['vat_category']),
            'net_value': float(item['total_net'] or 0),
            'vat_amount': float(item['total_vat'] or 0),
            'count': item['record_count'] or 0,
        }
        for item in breakdown
    ]


# =============================================================================
# CREDENTIALS VIEWSET
# =============================================================================

class MyDataCredentialsViewSet(viewsets.ModelViewSet):
    """
    ViewSet για MyDataCredentials.

    Endpoints:
    - GET /api/mydata/credentials/ - List all
    - GET /api/mydata/credentials/{id}/ - Detail
    - POST /api/mydata/credentials/ - Create
    - PUT /api/mydata/credentials/{id}/ - Update
    - DELETE /api/mydata/credentials/{id}/ - Delete
    - POST /api/mydata/credentials/{id}/verify/ - Verify credentials
    - POST /api/mydata/credentials/{id}/update_credentials/ - Update secret keys
    - POST /api/mydata/credentials/{id}/sync/ - Trigger sync
    """

    queryset = MyDataCredentials.objects.select_related('client').all()
    serializer_class = MyDataCredentialsSerializer
    permission_classes = [IsStaffUser]

    def get_queryset(self):
        """Filter by client if specified."""
        queryset = super().get_queryset()

        # Filter by client AFM
        afm = self.request.query_params.get('afm')
        if afm:
            queryset = queryset.filter(client__afm=afm)

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        # Filter by verified status
        is_verified = self.request.query_params.get('is_verified')
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == 'true')

        return queryset

    @action(detail=False, methods=['get'], url_path='by-client/(?P<client_id>[^/.]+)')
    def by_client(self, request, client_id=None):
        """
        Get credentials for a specific client by client ID.

        GET /api/mydata/credentials/by-client/{client_id}/
        """
        try:
            credentials = MyDataCredentials.objects.select_related('client').get(
                client_id=client_id,
                is_active=True
            )
            serializer = self.get_serializer(credentials)
            return Response(serializer.data)
        except MyDataCredentials.DoesNotExist:
            return Response(
                {'error': 'Δεν βρέθηκαν credentials για αυτόν τον πελάτη'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify credentials by making a test API call."""
        credentials = self.get_object()

        if not credentials.has_credentials:
            return Response(
                {'error': 'Δεν έχουν οριστεί credentials'},
                status=status.HTTP_400_BAD_REQUEST
            )

        success = credentials.verify_credentials()

        return Response({
            'success': success,
            'is_verified': credentials.is_verified,
            'error': credentials.verification_error if not success else None,
        })

    @action(detail=True, methods=['post'])
    def update_credentials(self, request, pk=None):
        """Update the encrypted credentials."""
        credentials = self.get_object()
        serializer = CredentialsUpdateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Set new credentials (will be encrypted automatically)
        credentials.user_id = serializer.validated_data['user_id']
        credentials.subscription_key = serializer.validated_data['subscription_key']
        credentials.is_sandbox = serializer.validated_data.get('is_sandbox', False)
        credentials.save()

        return Response({
            'success': True,
            'message': 'Τα credentials ενημερώθηκαν. Κάντε verify για επιβεβαίωση.',
        })

    @action(detail=True, methods=['post'])
    def set_initial_credit(self, request, pk=None):
        """
        Ορίζει το αρχικό πιστωτικό υπόλοιπο.

        Body:
        - initial_credit_balance: Decimal amount
        - initial_credit_period_year: Year (optional)
        - initial_credit_period: Period/Month (optional)
        """
        credentials = self.get_object()

        try:
            balance = Decimal(str(request.data.get('initial_credit_balance', 0)))
            if balance < 0:
                return Response(
                    {'error': 'Το πιστωτικό δεν μπορεί να είναι αρνητικό'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            credentials.initial_credit_balance = balance
            credentials.initial_credit_period_year = request.data.get('initial_credit_period_year')
            credentials.initial_credit_period = request.data.get('initial_credit_period')
            credentials.save(update_fields=[
                'initial_credit_balance',
                'initial_credit_period_year',
                'initial_credit_period'
            ])

            return Response({
                'success': True,
                'message': f'Το αρχικό πιστωτικό ορίστηκε σε {balance}€',
                'initial_credit_balance': str(balance),
            })
        except (ValueError, TypeError) as e:
            return Response(
                {'error': f'Μη έγκυρο ποσό: {e}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Trigger VAT sync for this client."""
        from django.core.management import call_command
        from django.db.models import Max
        from io import StringIO
        from mydata.models import VATSyncLog
        from mydata.services import summarize_vat_sync

        credentials = self.get_object()

        if not credentials.has_credentials:
            return Response(
                {'error': 'Δεν έχουν οριστεί credentials'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not credentials.is_active:
            return Response(
                {'error': 'Τα credentials είναι απενεργοποιημένα'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get sync parameters
        days = request.data.get('days', 30)
        year = request.data.get('year')
        month = request.data.get('month')

        try:
            out = StringIO()
            args = ['--client', credentials.client.afm]

            if year and month:
                args.extend(['--year', str(year), '--month', str(month)])
            else:
                args.extend(['--days', str(days)])

            # Κρατάμε το τελευταίο sync-log id ΠΡΙΝ τρέξει το command, ώστε μετά
            # να εξετάσουμε ΜΟΝΟ τα logs που δημιούργησε αυτό το sync.
            before_id = VATSyncLog.objects.filter(
                client=credentials.client
            ).aggregate(m=Max('id'))['m'] or 0

            call_command('mydata_sync_vat', *args, stdout=out)

            # Skip/locked detection — κοινή λογική με το client self-sync.
            return Response(summarize_vat_sync(credentials.client, before_id, out))

        except Exception as e:
            logger.error(f"Sync error for {credentials.client.afm}: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# VAT RECORD VIEWSET
# =============================================================================

class VATRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet για VATRecord (read-only).

    Endpoints:
    - GET /api/mydata/records/ - List records
    - GET /api/mydata/records/{id}/ - Record detail
    - GET /api/mydata/records/summary/ - Period summary
    - GET /api/mydata/records/by_category/ - Category breakdown
    """

    queryset = VATRecord.objects.select_related('client').all()
    permission_classes = [IsStaffUser]

    def get_serializer_class(self):
        if self.action == 'list':
            return VATRecordListSerializer
        return VATRecordSerializer

    def get_queryset(self):
        """Apply filters."""
        queryset = super().get_queryset()

        # Filter by client
        client_id = self.request.query_params.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        afm = self.request.query_params.get('afm')
        if afm:
            queryset = queryset.filter(client__afm=afm)

        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(issue_date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(issue_date__lte=date_to)

        # Filter by year/month
        year = self.request.query_params.get('year')
        if year:
            queryset = queryset.filter(issue_date__year=int(year))

        month = self.request.query_params.get('month')
        if month:
            queryset = queryset.filter(issue_date__month=int(month))

        # Filter by rec_type (1=income, 2=expense)
        rec_type = self.request.query_params.get('rec_type')
        if rec_type:
            queryset = queryset.filter(rec_type=int(rec_type))

        # Filter by VAT category
        vat_category = self.request.query_params.get('vat_category')
        if vat_category:
            queryset = queryset.filter(vat_category=int(vat_category))

        # Exclude cancelled by default
        include_cancelled = self.request.query_params.get('include_cancelled', 'false')
        if include_cancelled.lower() != 'true':
            queryset = queryset.filter(is_cancelled=False)

        return queryset.order_by('-issue_date', '-mark')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get period summary.

        Query params:
        - afm: Client AFM (required)
        - year: Year (default: current)
        - month: Month (default: current)
        """
        afm = request.query_params.get('afm')
        if not afm:
            return Response(
                {'error': 'Απαιτείται AFM πελάτη'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = ClientProfile.objects.get(afm=afm)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Δεν βρέθηκε πελάτης'},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        year = int(request.query_params.get('year', today.year))
        month = int(request.query_params.get('month', today.month))

        summary = build_period_summary(client, year, month)
        serializer = VATPeriodSummarySerializer(summary)

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """
        Get breakdown by VAT category.

        Query params:
        - afm: Client AFM (required)
        - year: Year (default: current)
        - month: Month (default: current)
        - rec_type: 1=income, 2=expense (optional, returns both if not specified)
        """
        afm = request.query_params.get('afm')
        if not afm:
            return Response(
                {'error': 'Απαιτείται AFM πελάτη'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = ClientProfile.objects.get(afm=afm)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Δεν βρέθηκε πελάτης'},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        year = int(request.query_params.get('year', today.year))
        month = int(request.query_params.get('month', today.month))
        rec_type = request.query_params.get('rec_type')

        if rec_type:
            breakdown = build_category_breakdown(client, year, month, int(rec_type))
            serializer = VATCategoryBreakdownSerializer(breakdown, many=True)
            return Response(serializer.data)

        # Return both income and expense
        income_breakdown = build_category_breakdown(client, year, month, 1)
        expense_breakdown = build_category_breakdown(client, year, month, 2)

        return Response({
            'income': VATCategoryBreakdownSerializer(income_breakdown, many=True).data,
            'expense': VATCategoryBreakdownSerializer(expense_breakdown, many=True).data,
        })


# =============================================================================
# SYNC LOG VIEWSET
# =============================================================================

class VATSyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet για VATSyncLog (read-only).

    Endpoints:
    - GET /api/mydata/logs/ - List logs
    - GET /api/mydata/logs/{id}/ - Log detail
    """

    queryset = VATSyncLog.objects.select_related('client').all()
    serializer_class = VATSyncLogSerializer
    permission_classes = [IsStaffUser]

    def get_queryset(self):
        """Apply filters."""
        queryset = super().get_queryset()

        # Filter by client
        client_id = self.request.query_params.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        afm = self.request.query_params.get('afm')
        if afm:
            queryset = queryset.filter(client__afm=afm)

        # Filter by sync type
        sync_type = self.request.query_params.get('sync_type')
        if sync_type:
            queryset = queryset.filter(sync_type=sync_type.upper())

        # Filter by status
        log_status = self.request.query_params.get('status')
        if log_status:
            queryset = queryset.filter(status=log_status.upper())

        # Limit results
        limit = self.request.query_params.get('limit', 50)
        queryset = queryset[:int(limit)]

        return queryset


# =============================================================================
# DASHBOARD API VIEW
# =============================================================================

class MyDataDashboardView(APIView):
    """
    Dashboard endpoint για myDATA overview.

    GET /api/mydata/dashboard/
    Returns aggregated data for all clients.

    Query params:
    - year: Year (default: current)
    - month: Month (default: current)
    """

    permission_classes = [IsStaffUser]

    def get(self, request):
        today = date.today()
        year = int(request.query_params.get('year', today.year))
        month = int(request.query_params.get('month', today.month))

        # Get all clients with mydata credentials
        credentials_qs = MyDataCredentials.objects.select_related('client').all()

        total_clients = ClientProfile.objects.count()
        clients_with_credentials = credentials_qs.count()
        verified_credentials = credentials_qs.filter(is_verified=True).count()

        # Aggregate totals for the period
        period_records = VATRecord.objects.filter(
            issue_date__year=year,
            issue_date__month=month,
            is_cancelled=False
        )

        income_totals = period_records.filter(rec_type=1).aggregate(
            total_net=Sum('net_value'),
            total_vat=Sum('vat_amount'),
        )

        expense_totals = period_records.filter(rec_type=2).aggregate(
            total_net=Sum('net_value'),
            total_vat=Sum('vat_amount'),
        )

        # Per-client summaries
        clients_data = []
        for creds in credentials_qs:
            client = creds.client
            summary = build_period_summary(client, year, month)
            income_breakdown = build_category_breakdown(client, year, month, 1)
            expense_breakdown = build_category_breakdown(client, year, month, 2)

            clients_data.append({
                'client_afm': client.afm,
                'client_name': client.eponimia,
                'has_credentials': creds.has_credentials,
                'is_verified': creds.is_verified,
                'last_sync': creds.last_vat_sync_at,
                'current_period': summary,
                'income_by_category': income_breakdown,
                'expense_by_category': expense_breakdown,
            })

        return Response({
            'period': {
                'year': year,
                'month': month,
            },
            'overview': {
                'total_clients': total_clients,
                'clients_with_credentials': clients_with_credentials,
                'verified_credentials': verified_credentials,
                'total_income_net': income_totals['total_net'] or Decimal('0.00'),
                'total_income_vat': income_totals['total_vat'] or Decimal('0.00'),
                'total_expense_net': expense_totals['total_net'] or Decimal('0.00'),
                'total_expense_vat': expense_totals['total_vat'] or Decimal('0.00'),
            },
            'clients': clients_data,
        })


# =============================================================================
# CLIENT VAT DETAIL VIEW
# =============================================================================

class ClientVATDetailView(APIView):
    """
    Detailed VAT view for a single client.

    GET /api/mydata/client/{afm}/
    Returns complete VAT data for a client.

    Query params:
    - year: Year (default: current)
    - month: Month (default: current, used when period_type='month')
    - quarter: Quarter 1-4 (used when period_type='quarter')
    - period_type: 'month', 'quarter', or 'year' (default: 'month')
    - include_records: Include individual records (default: false)
    """

    permission_classes = [IsStaffUser]

    def get(self, request, afm):
        try:
            client = ClientProfile.objects.get(afm=afm)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Δεν βρέθηκε πελάτης'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            today = date.today()
            year = int(request.query_params.get('year', today.year))
            period_type = request.query_params.get('period_type', 'month')
            include_records = request.query_params.get('include_records', 'false').lower() == 'true'

            # Get month or quarter based on period type
            if period_type == 'quarter':
                # Default to current quarter
                current_quarter = (today.month - 1) // 3 + 1
                quarter = int(request.query_params.get('quarter', current_quarter))
                month = None
            elif period_type == 'year':
                quarter = None
                month = None
            else:
                quarter = None
                month = int(request.query_params.get('month', today.month))

            # Calculate date range
            date_from, date_to, period_label = get_period_date_range(
                year, month=month, quarter=quarter, period_type=period_type
            )

            # Check for credentials
            try:
                credentials = client.mydata_credentials
                has_credentials = credentials.has_credentials
                is_verified = credentials.is_verified
                last_sync = credentials.last_vat_sync_at.isoformat() if credentials.last_vat_sync_at else None
            except MyDataCredentials.DoesNotExist:
                has_credentials = False
                is_verified = False
                last_sync = None

            # Build response using date range functions
            summary = build_date_range_summary(client, date_from, date_to)
            income_breakdown = build_date_range_category_breakdown(client, date_from, date_to, 1)
            expense_breakdown = build_date_range_category_breakdown(client, date_from, date_to, 2)

            # Add period info to summary
            summary['year'] = year
            summary['month'] = month
            summary['quarter'] = quarter
            summary['period_type'] = period_type
            summary['date_from'] = date_from.isoformat()
            summary['date_to'] = date_to.isoformat()

            response_data = {
                'client': {
                    'afm': client.afm,
                    'name': client.eponimia,
                },
                'credentials': {
                    'has_credentials': has_credentials,
                    'is_verified': is_verified,
                    'last_sync': last_sync,
                },
                'period': {
                    'year': year,
                    'month': month,
                    'quarter': quarter,
                    'period_type': period_type,
                    'date_from': date_from.isoformat(),
                    'date_to': date_to.isoformat(),
                    'label': period_label,
                },
                'summary': summary,
                'income_by_category': income_breakdown,
                'expense_by_category': expense_breakdown,
            }

            if include_records:
                records = VATRecord.objects.filter(
                    client=client,
                    issue_date__gte=date_from,
                    issue_date__lte=date_to,
                    is_cancelled=False,
                ).order_by('-issue_date', '-mark')

                response_data['records'] = VATRecordListSerializer(records, many=True).data

            return Response(response_data)

        except Exception as e:
            import traceback
            return Response(
                {'error': str(e), 'traceback': traceback.format_exc()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# MONTHLY TREND VIEW
# =============================================================================

class MonthlyTrendView(APIView):
    """
    Monthly trend data for charts.

    GET /api/mydata/trend/
    Returns VAT data for the last N months.

    Query params:
    - afm: Client AFM (optional, returns all if not specified)
    - months: Number of months to include (default: 6)
    """

    permission_classes = [IsStaffUser]

    def get(self, request):
        afm = request.query_params.get('afm')
        months_count = int(request.query_params.get('months', 6))

        # Build list of months
        today = date.today()
        months = []
        current = today.replace(day=1)

        for _ in range(months_count):
            months.append((current.year, current.month))
            # Go to previous month
            if current.month == 1:
                current = current.replace(year=current.year - 1, month=12)
            else:
                current = current.replace(month=current.month - 1)

        months.reverse()  # Oldest first

        # Build queryset filter
        base_qs = VATRecord.objects.filter(is_cancelled=False)
        if afm:
            base_qs = base_qs.filter(client__afm=afm)

        # Collect data for each month
        trend_data = []
        for year, month in months:
            income = base_qs.filter(
                issue_date__year=year,
                issue_date__month=month,
                rec_type=1
            ).aggregate(
                net=Sum('net_value'),
                vat=Sum('vat_amount'),
                count=Count('id')
            )

            expense = base_qs.filter(
                issue_date__year=year,
                issue_date__month=month,
                rec_type=2
            ).aggregate(
                net=Sum('net_value'),
                vat=Sum('vat_amount'),
                count=Count('id')
            )

            trend_data.append({
                'year': year,
                'month': month,
                'month_name': self._get_month_name(month),
                'income_net': income['net'] or Decimal('0.00'),
                'income_vat': income['vat'] or Decimal('0.00'),
                'income_count': income['count'] or 0,
                'expense_net': expense['net'] or Decimal('0.00'),
                'expense_vat': expense['vat'] or Decimal('0.00'),
                'expense_count': expense['count'] or 0,
                'vat_balance': (income['vat'] or Decimal('0.00')) - (expense['vat'] or Decimal('0.00')),
            })

        return Response({
            'afm': afm,
            'months_count': months_count,
            'data': trend_data,
        })

    def _get_month_name(self, month: int) -> str:
        """Get Greek month abbreviation."""
        names = {
            1: 'Ιαν', 2: 'Φεβ', 3: 'Μαρ', 4: 'Απρ',
            5: 'Μάι', 6: 'Ιουν', 7: 'Ιουλ', 8: 'Αυγ',
            9: 'Σεπ', 10: 'Οκτ', 11: 'Νοε', 12: 'Δεκ'
        }
        return names.get(month, str(month))


# =============================================================================
# VAT PERIOD RESULT - Υπολογισμός ΦΠΑ ανά περίοδο
# =============================================================================

class VATPeriodResultViewSet(viewsets.ModelViewSet):
    """
    ViewSet για διαχείριση VATPeriodResult.

    Endpoints:
    - GET /periods/ - Λίστα περιόδων
    - POST /periods/ - Δημιουργία νέας περιόδου
    - GET /periods/{id}/ - Λεπτομέρειες περιόδου
    - POST /periods/{id}/calculate/ - Υπολογισμός ΦΠΑ
    - POST /periods/{id}/lock/ - Κλείδωμα περιόδου
    - POST /periods/{id}/unlock/ - Ξεκλείδωμα περιόδου
    - POST /periods/{id}/set_credit/ - Ορισμός πιστωτικού
    """
    permission_classes = [IsStaffUser]

    def get_queryset(self):
        from .models import VATPeriodResult

        qs = VATPeriodResult.objects.select_related('client', 'locked_by')

        # Filter by client
        client_id = self.request.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)

        # Filter by AFM
        afm = self.request.query_params.get('afm')
        if afm:
            qs = qs.filter(client__afm=afm)

        # Filter by period type
        period_type = self.request.query_params.get('period_type')
        if period_type in ['monthly', 'quarterly']:
            qs = qs.filter(period_type=period_type)

        # Filter by year
        year = self.request.query_params.get('year')
        if year:
            qs = qs.filter(year=int(year))

        return qs.order_by('-year', '-period')

    def get_serializer_class(self):
        from .serializers import VATPeriodResultSerializer, VATPeriodResultDetailSerializer

        if self.action == 'retrieve':
            return VATPeriodResultDetailSerializer
        return VATPeriodResultSerializer

    def perform_create(self, serializer):
        """Δημιουργία νέας περιόδου με κληρονομιά πιστωτικού."""
        instance = serializer.save()
        # Αυτόματη κληρονομιά πιστωτικού από προηγούμενη περίοδο
        instance.inherit_credit_from_previous(save=True)

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """
        Υπολογίζει το ΦΠΑ για την περίοδο από τα VATRecords.

        Optionally syncs missing months first.
        """
        from .models import VATPeriodResult

        period = self.get_object()

        if period.is_locked:
            return Response(
                {'error': 'Η περίοδος είναι κλειδωμένη'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Optional: sync missing months first
        sync_first = request.data.get('sync_first', False)
        if sync_first:
            self._sync_period_months(period)

        # Calculate from records
        result = period.calculate_from_records(save=True)

        return Response({
            'success': True,
            'message': 'Ο υπολογισμός ολοκληρώθηκε',
            'result': result,
            'period': self.get_serializer(period).data
        })

    def _sync_period_months(self, period):
        """Sync all months in the period."""
        try:
            credentials = period.client.mydata_credentials
            if not credentials.has_credentials:
                return

            for month in period.months_in_period:
                from datetime import date
                import calendar

                # Calculate date range for month
                first_day = date(period.year, month, 1)
                last_day = date(period.year, month, calendar.monthrange(period.year, month)[1])

                # Sync this month
                from .services import sync_vat_records_for_client
                sync_vat_records_for_client(
                    client=period.client,
                    date_from=first_day,
                    date_to=last_day
                )

                # Track synced month
                if month not in period.months_synced:
                    period.months_synced.append(month)

            period.save(update_fields=['months_synced'])
        except Exception as e:
            logger.error(f"Error syncing period months: {e}")

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Κλειδώνει την περίοδο."""
        period = self.get_object()

        if period.is_locked:
            return Response(
                {'error': 'Η περίοδος είναι ήδη κλειδωμένη'},
                status=status.HTTP_400_BAD_REQUEST
            )

        period.lock(user=request.user)

        return Response({
            'success': True,
            'message': f'Η περίοδος {period.get_period_display()} κλειδώθηκε',
            'period': self.get_serializer(period).data
        })

    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        """Ξεκλειδώνει την περίοδο (admin only)."""
        period = self.get_object()

        if not period.is_locked:
            return Response(
                {'error': 'Η περίοδος δεν είναι κλειδωμένη'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Only admin can unlock
        if not request.user.is_staff:
            return Response(
                {'error': 'Μόνο διαχειριστές μπορούν να ξεκλειδώσουν περιόδους'},
                status=status.HTTP_403_FORBIDDEN
            )

        period.unlock()

        return Response({
            'success': True,
            'message': f'Η περίοδος {period.get_period_display()} ξεκλειδώθηκε',
            'period': self.get_serializer(period).data
        })

    @action(detail=True, methods=['post'])
    def set_credit(self, request, pk=None):
        """
        Ορίζει χειροκίνητα το πιστωτικό υπόλοιπο.

        Χρήση για αρχικό πιστωτικό ή διορθώσεις.
        """
        period = self.get_object()

        if period.is_locked:
            return Response(
                {'error': 'Η περίοδος είναι κλειδωμένη'},
                status=status.HTTP_400_BAD_REQUEST
            )

        credit = request.data.get('previous_credit')
        if credit is None:
            return Response(
                {'error': 'Απαιτείται το πεδίο previous_credit'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            credit_value = Decimal(str(credit))
        except (ValueError, TypeError, InvalidOperation):
            return Response(
                {'error': 'Μη έγκυρο ποσό'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Το πιστωτικό υπόλοιπο δεν μπορεί να είναι αρνητικό.
        if credit_value < 0:
            return Response(
                {'error': 'Το πιστωτικό υπόλοιπο δεν μπορεί να είναι αρνητικό'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Atomic: η αποθήκευση του credit και ο επανυπολογισμός commit-άρουν μαζί.
        with transaction.atomic():
            period.previous_credit = credit_value
            period.save(update_fields=['previous_credit', 'updated_at'])
            period.calculate_from_records(save=True)

        return Response({
            'success': True,
            'message': f'Το πιστωτικό ορίστηκε σε {period.previous_credit}€',
            'period': self.get_serializer(period).data
        })


class VATPeriodCalculatorView(APIView):
    """
    Quick calculator view για υπολογισμό ΦΠΑ περιόδου.

    GET /api/mydata/calculator/?client_id=1&period_type=quarterly&year=2025&period=1
    """
    permission_classes = [IsStaffUser]

    def get(self, request):
        from .models import VATPeriodResult

        client_id = request.query_params.get('client_id')
        afm = request.query_params.get('afm')
        period_type = request.query_params.get('period_type', 'monthly')
        year = request.query_params.get('year')
        period = request.query_params.get('period')

        # Validate required params
        if not (client_id or afm):
            return Response(
                {'error': 'Απαιτείται client_id ή afm'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not year or not period:
            return Response(
                {'error': 'Απαιτούνται year και period'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get client
        try:
            if client_id:
                client = ClientProfile.objects.get(pk=client_id)
            else:
                client = ClientProfile.objects.get(afm=afm)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Ο πελάτης δεν βρέθηκε'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get or create period result
        period_result, created = VATPeriodResult.get_or_create_for_period(
            client=client,
            period_type=period_type,
            year=int(year),
            period=int(period)
        )

        # If new or request wants recalculation — αλλά ΠΟΤΕ σε κλειδωμένη
        # (υποβεβλημένη) περίοδο: το calculate_from_records πετάει ValidationError
        # για locked, που αλλιώς γινόταν αναπιάστο 500 στην προβολή. Οι κλειδωμένες
        # κρατούν τις οριστικοποιημένες τιμές τους.
        if (created or request.query_params.get('recalculate')) and not period_result.is_locked:
            period_result.calculate_from_records(save=True)

        # Build response - flat structure matching frontend interface
        final_result = float(period_result.final_result)
        return Response({
            'id': period_result.pk,  # Important: needed for lock/unlock operations
            # Client info (flat)
            'client': client.pk,
            'client_afm': client.afm,
            'client_name': client.eponimia,
            # Period info (flat)
            'period_type': period_result.period_type,
            'year': period_result.year,
            'period': period_result.period,
            'period_display': period_result.get_period_display(),
            'period_start_date': period_result.period_start_date.isoformat(),
            'period_end_date': period_result.period_end_date.isoformat(),
            # VAT values (as numbers for frontend)
            'vat_output': float(period_result.vat_output),
            'vat_input': float(period_result.vat_input),
            'vat_difference': float(period_result.vat_difference),
            'previous_credit': float(period_result.previous_credit),
            'final_result': final_result,
            'credit_to_next': float(period_result.credit_to_next),
            # Status flags
            'is_locked': period_result.is_locked,
            'is_payable': final_result > 0,
            'is_credit': final_result < 0,
            'locked_at': period_result.locked_at.isoformat() if period_result.locked_at else None,
            'last_calculated_at': period_result.last_calculated_at.isoformat() if period_result.last_calculated_at else None,
            'months_synced': period_result.months_synced,
            'created': created,
        })
