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

from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounting.models import ClientProfile
from accounting.mixins import ClientScopedQuerysetMixin
from accounting.permissions import CanAccessClient, ClientModelPermissions
from accounting.services.access import (
    accessible_clients, check_model_perms, user_can_access_client,
)

_PERM_DENIED = {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'}
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

def _parse_int(value, param='παράμετρος', default=None, min_val=None, max_val=None):
    """
    Μετατρέπει query param σε int με επικύρωση.

    Επιστρέφει το default αν η τιμή λείπει. Σηκώνει rest_framework
    ValidationError (HTTP 400) για μη έγκυρη ή εκτός ορίων τιμή.
    """
    if value is None or value == '':
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValidationError({'error': f'Μη έγκυρη τιμή για την παράμετρο {param}'})
    if (min_val is not None and result < min_val) or (max_val is not None and result > max_val):
        raise ValidationError({'error': f'Η παράμετρος {param} είναι εκτός επιτρεπτών ορίων'})
    return result


def _audit_vat_sync(user, client_id, success, period_id=None):
    """
    Audit event για εξωτερικό myDATA VAT sync — χωρίς πλήρες ΑΦΜ,
    credentials, raw response ή exception text (μόνο internal IDs).
    """
    try:
        from common.models import AuditLog
        detail = f'client id={client_id}'
        if period_id is not None:
            detail += f', period id={period_id}'
        AuditLog.objects.create(
            user=user if getattr(user, 'is_authenticated', False) else None,
            action='update',
            model_name='MyDataSync',
            object_id=str(client_id),
            description=(
                f'myDATA VAT sync {"επιτυχία" if success else "αποτυχία"}: '
                f'{detail}'
            ),
            severity='medium',
        )
    except Exception:
        logger.warning('Could not write mydata sync audit', exc_info=True)


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

class MyDataCredentialsViewSet(ClientScopedQuerysetMixin, viewsets.ModelViewSet):
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
    permission_classes = [permissions.IsAuthenticated, ClientModelPermissions, CanAccessClient]
    client_field = 'client__assigned_users'
    # Όλα τα custom POST actions τροποποιούν credentials → change permission
    action_perms = {
        'verify': ['mydata.change_mydatacredentials'],
        'update_credentials': ['mydata.change_mydatacredentials'],
        'set_initial_credit': ['mydata.change_mydatacredentials'],
        # Εξωτερικό myDATA sync: ΔΕΝ αρκεί το change στα credentials —
        # απαιτείται το dedicated mydata.sync_vatdata
        'sync': ['mydata.change_mydatacredentials', 'mydata.sync_vatdata'],
        'by_client': ['mydata.view_mydatacredentials'],
    }

    def perform_create(self, serializer):
        from django.http import Http404
        client = serializer.validated_data.get('client')
        if client is not None and not user_can_access_client(self.request.user, client):
            raise Http404('ClientProfile not found')
        serializer.save()

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
            credentials = self.get_queryset().get(
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

        # Check if credentials are corrupted (can't be decrypted)
        if credentials.credentials_corrupted:
            return Response({
                'success': False,
                'is_verified': False,
                'error': 'Τα credentials δεν μπορούν να αποκρυπτογραφηθούν (πιθανή αλλαγή SECRET_KEY). Παρακαλώ εισάγετε νέα.',
                'needs_reconfiguration': True,
                'credentials_corrupted': True,
            }, status=status.HTTP_400_BAD_REQUEST)

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

            period_year = request.data.get('initial_credit_period_year')
            period = request.data.get('initial_credit_period')
            if period_year is not None:
                period_year = int(period_year)
                if not 2000 <= period_year <= 2100:
                    raise ValueError('year out of range')
            if period is not None:
                period = int(period)
                if not 1 <= period <= 12:
                    raise ValueError('period out of range')

            credentials.initial_credit_balance = balance
            credentials.initial_credit_period_year = period_year
            credentials.initial_credit_period = period
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
        except (ValueError, TypeError, InvalidOperation):
            return Response(
                {'error': 'Μη έγκυρη τιμή — απαιτούνται αριθμοί (ποσό, έτος, περίοδος)'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def clear_corrupted(self, request, pk=None):
        """
        Clear corrupted credentials that cannot be decrypted.

        Use this when SECRET_KEY has changed and old credentials
        are no longer readable. After clearing, user can re-enter
        new credentials.
        """
        credentials = self.get_object()

        if not credentials.credentials_corrupted:
            return Response({
                'success': False,
                'error': 'Τα credentials δεν είναι κατεστραμμένα',
            }, status=status.HTTP_400_BAD_REQUEST)

        credentials.clear_corrupted_credentials()

        return Response({
            'success': True,
            'message': 'Τα κατεστραμμένα credentials διαγράφηκαν. Παρακαλώ εισάγετε νέα.',
            'needs_reconfiguration': True,
        })

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Trigger VAT sync for this client."""
        from django.core.management import call_command
        from io import StringIO

        credentials = self.get_object()

        if not credentials.has_credentials:
            return Response(
                {'error': 'Δεν έχουν οριστεί credentials'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if credentials are corrupted (can't be decrypted)
        if credentials.credentials_corrupted:
            return Response({
                'error': 'Τα credentials δεν μπορούν να αποκρυπτογραφηθούν (πιθανή αλλαγή SECRET_KEY). Παρακαλώ εισάγετε νέα.',
                'needs_reconfiguration': True,
                'credentials_corrupted': True,
            }, status=status.HTTP_400_BAD_REQUEST)

        if not credentials.is_active:
            return Response(
                {'error': 'Τα credentials είναι απενεργοποιημένα'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get sync parameters — validated με λογικά bounds
        try:
            days = int(request.data.get('days', 30))
            year = request.data.get('year')
            month = request.data.get('month')
            if year is not None:
                year = int(year)
            if month is not None:
                month = int(month)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Μη έγκυρες παράμετροι — απαιτούνται αριθμοί'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not 1 <= days <= 365:
            return Response(
                {'error': 'Το days πρέπει να είναι 1-365'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if year is not None and not 2000 <= year <= 2100:
            return Response(
                {'error': 'Μη έγκυρο έτος'}, status=status.HTTP_400_BAD_REQUEST
            )
        if month is not None and not 1 <= month <= 12:
            return Response(
                {'error': 'Μη έγκυρος μήνας'}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            out = StringIO()
            args = ['--client', credentials.client.afm]

            if year and month:
                args.extend(['--year', str(year), '--month', str(month)])
            else:
                args.extend(['--days', str(days)])

            call_command('mydata_sync_vat', *args, stdout=out)

            _audit_vat_sync(request.user, credentials.client_id, success=True)
            return Response({
                'success': True,
                'message': out.getvalue(),
            })

        except Exception:
            # Client DB id αντί για πλήρες ΑΦΜ στα logs· χωρίς raw
            # exception text στον χρήστη
            logger.exception(
                f"Sync error for client id={credentials.client_id}"
            )
            _audit_vat_sync(request.user, credentials.client_id, success=False)
            return Response(
                {'error': 'Σφάλμα συγχρονισμού myDATA'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# VAT RECORD VIEWSET
# =============================================================================

class VATRecordViewSet(ClientScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet για VATRecord (read-only).

    Endpoints:
    - GET /api/mydata/records/ - List records
    - GET /api/mydata/records/{id}/ - Record detail
    - GET /api/mydata/records/summary/ - Period summary
    - GET /api/mydata/records/by_category/ - Category breakdown
    """

    queryset = VATRecord.objects.select_related('client').all()
    permission_classes = [permissions.IsAuthenticated, ClientModelPermissions, CanAccessClient]
    client_field = 'client__assigned_users'

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
        year = _parse_int(self.request.query_params.get('year'), 'year')
        if year:
            queryset = queryset.filter(issue_date__year=year)

        month = _parse_int(self.request.query_params.get('month'), 'month', min_val=1, max_val=12)
        if month:
            queryset = queryset.filter(issue_date__month=month)

        # Filter by rec_type (1=income, 2=expense)
        rec_type = _parse_int(self.request.query_params.get('rec_type'), 'rec_type')
        if rec_type:
            queryset = queryset.filter(rec_type=rec_type)

        # Filter by VAT category
        vat_category = _parse_int(self.request.query_params.get('vat_category'), 'vat_category')
        if vat_category:
            queryset = queryset.filter(vat_category=vat_category)

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
            client = accessible_clients(request.user).get(afm=afm)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Δεν βρέθηκε πελάτης'},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        year = _parse_int(request.query_params.get('year'), 'year', default=today.year)
        month = _parse_int(request.query_params.get('month'), 'month', default=today.month, min_val=1, max_val=12)

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
            client = accessible_clients(request.user).get(afm=afm)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Δεν βρέθηκε πελάτης'},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        year = _parse_int(request.query_params.get('year'), 'year', default=today.year)
        month = _parse_int(request.query_params.get('month'), 'month', default=today.month, min_val=1, max_val=12)
        rec_type = _parse_int(request.query_params.get('rec_type'), 'rec_type')

        if rec_type:
            breakdown = build_category_breakdown(client, year, month, rec_type)
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

class VATSyncLogViewSet(ClientScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """
    ViewSet για VATSyncLog (read-only).

    Endpoints:
    - GET /api/mydata/logs/ - List logs
    - GET /api/mydata/logs/{id}/ - Log detail
    """

    queryset = VATSyncLog.objects.select_related('client').all()
    serializer_class = VATSyncLogSerializer
    permission_classes = [permissions.IsAuthenticated, ClientModelPermissions, CanAccessClient]
    client_field = 'client__assigned_users'

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

        # Limit results (μη-αρνητικός int, default 50)
        limit = _parse_int(self.request.query_params.get('limit'), 'limit', default=50, min_val=0)
        queryset = queryset[:limit]

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

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Επιστρέφει client metadata (ΑΦΜ/επωνυμίες) → απαιτεί και
        # accounting.view_clientprofile
        if not check_model_perms(
            request, 'mydata.view_vatrecord', 'accounting.view_clientprofile'
        ):
            return Response(_PERM_DENIED, status=status.HTTP_403_FORBIDDEN)
        can_see_credentials = request.user.has_perm('mydata.view_mydatacredentials')
        today = date.today()
        year = _parse_int(request.query_params.get('year'), 'year', default=today.year)
        month = _parse_int(request.query_params.get('month'), 'month', default=today.month, min_val=1, max_val=12)

        # Μόνο πελάτες στους οποίους έχει πρόσβαση ο χρήστης (RBAC scoping)
        allowed_clients = accessible_clients(request.user)
        credentials_qs = MyDataCredentials.objects.select_related('client').filter(
            client__in=allowed_clients
        )

        total_clients = allowed_clients.count()
        # Aggregate credential metadata μόνο με view_mydatacredentials —
        # χωρίς αυτό ακόμη και τα σύνολα δεν διαρρέουν (null)
        if can_see_credentials:
            clients_with_credentials = credentials_qs.count()
            verified_credentials = credentials_qs.filter(is_verified=True).count()
        else:
            clients_with_credentials = None
            verified_credentials = None

        # Aggregate totals for the period
        period_records = VATRecord.objects.filter(
            client__in=allowed_clients,
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

        # Per-client summaries — ΠΑΝΤΑ πάνω σε ΟΛΟΥΣ τους προσβάσιμους
        # πελάτες, ΟΧΙ στο credentials_qs: αλλιώς η ίδια η ύπαρξη του πελάτη
        # στη λίστα θα διέρρεε ποιος έχει MyDataCredentials row (side channel)
        # ακόμη και χωρίς το view_mydatacredentials permission.
        creds_by_client = {c.client_id: c for c in credentials_qs}
        clients_data = []
        for client in allowed_clients:
            creds = creds_by_client.get(client.id)
            summary = build_period_summary(client, year, month)
            income_breakdown = build_category_breakdown(client, year, month, 1)
            expense_breakdown = build_category_breakdown(client, year, month, 2)

            entry = {
                'client_afm': client.afm,
                'client_name': client.eponimia,
                'current_period': summary,
                'income_by_category': income_breakdown,
                'expense_by_category': expense_breakdown,
            }
            # Credential-derived πεδία ΜΟΝΟ με mydata.view_mydatacredentials —
            # χωρίς το permission είναι null για ΟΛΟΥΣ (ίδια μορφή, καμία
            # διάκριση ποιος έχει/δεν έχει credentials)
            if can_see_credentials:
                entry['has_credentials'] = bool(creds and creds.has_credentials)
                entry['is_verified'] = bool(creds and creds.is_verified)
                entry['last_sync'] = creds.last_vat_sync_at if creds else None
            else:
                entry['has_credentials'] = None
                entry['is_verified'] = None
                entry['last_sync'] = None
            clients_data.append(entry)

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

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, afm):
        if not check_model_perms(
            request, 'mydata.view_vatrecord', 'accounting.view_clientprofile'
        ):
            return Response(_PERM_DENIED, status=status.HTTP_403_FORBIDDEN)
        try:
            client = accessible_clients(request.user).get(afm=afm)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Δεν βρέθηκε πελάτης'},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        year = _parse_int(request.query_params.get('year'), 'year', default=today.year)
        period_type = request.query_params.get('period_type', 'month')
        if period_type not in ('month', 'quarter', 'year'):
            return Response(
                {'error': "Μη έγκυρο period_type (επιτρεπτά: 'month', 'quarter', 'year')"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get month or quarter based on period type
        if period_type == 'quarter':
            # Default to current quarter
            current_quarter = (today.month - 1) // 3 + 1
            quarter = _parse_int(
                request.query_params.get('quarter'), 'quarter',
                default=current_quarter, min_val=1, max_val=4
            )
            month = None
        elif period_type == 'year':
            quarter = None
            month = None
        else:
            quarter = None
            month = _parse_int(
                request.query_params.get('month'), 'month',
                default=today.month, min_val=1, max_val=12
            )

        try:
            include_records = request.query_params.get('include_records', 'false').lower() == 'true'

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
                'credentials': (
                    {
                        'has_credentials': has_credentials,
                        'is_verified': is_verified,
                        'last_sync': last_sync,
                    }
                    if request.user.has_perm('mydata.view_mydatacredentials')
                    else None
                ),
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

        except Exception:
            from accounting.services.access import mask_pii_value
            logger.exception(
                'Σφάλμα στο ClientVATDetailView για ΑΦΜ %s', mask_pii_value(afm)
            )
            return Response(
                {'error': 'Εσωτερικό σφάλμα διακομιστή'},
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

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not check_model_perms(request, 'mydata.view_vatrecord'):
            return Response(_PERM_DENIED, status=status.HTTP_403_FORBIDDEN)
        afm = request.query_params.get('afm')
        months_count = _parse_int(request.query_params.get('months'), 'months', default=6)
        # Clamp σε λογικά όρια 1..36
        months_count = max(1, min(36, months_count))

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

        # Build queryset filter (RBAC: μόνο προσβάσιμοι πελάτες)
        base_qs = VATRecord.objects.filter(
            is_cancelled=False,
            client__in=accessible_clients(request.user),
        )
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
    permission_classes = [permissions.IsAuthenticated, ClientModelPermissions, CanAccessClient]
    action_perms = {
        'calculate': ['mydata.change_vatperiodresult'],
        'lock': ['mydata.change_vatperiodresult'],
        'unlock': ['mydata.change_vatperiodresult'],
        'set_credit': ['mydata.change_vatperiodresult'],
    }

    def get_queryset(self):
        from .models import VATPeriodResult

        qs = VATPeriodResult.objects.select_related('client', 'locked_by').filter(
            client__in=accessible_clients(self.request.user)
        )

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
        year = _parse_int(self.request.query_params.get('year'), 'year')
        if year:
            qs = qs.filter(year=year)

        return qs.order_by('-year', '-period')

    def get_serializer_class(self):
        from .serializers import VATPeriodResultSerializer, VATPeriodResultDetailSerializer

        if self.action == 'retrieve':
            return VATPeriodResultDetailSerializer
        return VATPeriodResultSerializer

    def perform_create(self, serializer):
        """Δημιουργία νέας περιόδου με κληρονομιά πιστωτικού."""
        from django.http import Http404
        client = serializer.validated_data.get('client')
        if client is not None and not user_can_access_client(self.request.user, client):
            raise Http404('ClientProfile not found')
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

        # Optional: sync missing months first — εξωτερικό side effect, ΧΩΡΙΣ
        # το dedicated permission επιτρέπεται μόνο απλός υπολογισμός.
        # Αυστηρό boolean parsing: "false"/"0" → False, άκυρη τιμή → 400.
        from accounting.services.access import parse_strict_bool
        sync_first = parse_strict_bool(
            request.data.get('sync_first'), 'sync_first', default=False)
        if sync_first:
            if not request.user.has_perm('mydata.sync_vatdata'):
                return Response(
                    {'error': 'Δεν έχετε δικαίωμα συγχρονισμού δεδομένων ΦΠΑ.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            sync_result = self._normalize_sync_result(
                self._sync_period_months(period))
            # Το audit αντικατοπτρίζει το ΠΡΑΓΜΑΤΙΚΟ αποτέλεσμα (Γύρος 23)
            _audit_vat_sync(
                request.user, period.client_id,
                success=(sync_result['status'] == 'success'),
                period_id=period.pk)

            if sync_result['status'] == 'failed':
                # Fail closed: ΔΕΝ υπολογίζουμε πάνω σε stale δεδομένα
                http_status = (
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                    if sync_result['reason'] in ('missing_credentials',
                                                 'authentication')
                    else status.HTTP_502_BAD_GATEWAY
                )
                return Response({
                    'success': False,
                    'sync_status': 'failed',
                    'error': 'Ο συγχρονισμός myDATA απέτυχε — ο υπολογισμός '
                             'δεν εκτελέστηκε για να μη χρησιμοποιηθούν '
                             'παλαιά δεδομένα.',
                    'sync_reason': sync_result['reason'],
                    'failed_months': sync_result['failed_months'],
                }, status=http_status)

        # Calculate from records
        result = period.calculate_from_records(save=True)

        response = {
            'success': True,
            'message': 'Ο υπολογισμός ολοκληρώθηκε',
            'result': result,
            'period': self.get_serializer(period).data
        }
        if sync_first:
            # Ρητή δήλωση κατάστασης συγχρονισμού — ποτέ «πλήρως
            # ενημερωμένο» όταν κάποιοι μήνες απέτυχαν
            response['sync_status'] = sync_result['status']
            if sync_result['status'] == 'partial':
                response['warning'] = (
                    'Ο συγχρονισμός myDATA ολοκληρώθηκε ΜΕΡΙΚΩΣ — ο '
                    'υπολογισμός μπορεί να μην περιλαμβάνει όλα τα '
                    'δεδομένα της περιόδου.'
                )
                response['failed_months'] = sync_result['failed_months']
                response['synced_months'] = sync_result['successful_months']
        return Response(response)

    @staticmethod
    def _normalize_sync_result(result):
        """
        Fail-closed κανονικοποίηση του αποτελέσματος συγχρονισμού.

        Αν το `_sync_period_months` (π.χ. σε override/patch) επιστρέψει
        κάτι που δεν είναι αναγνωρίσιμο δομημένο αποτέλεσμα, το
        θεωρούμε **αποτυχία** αντί να σκάσει ο caller ή —χειρότερα— να
        θεωρηθεί επιτυχία.
        """
        valid = ('success', 'partial', 'failed')
        if isinstance(result, dict) and result.get('status') in valid:
            return {
                'status': result['status'],
                'reason': result.get('reason', ''),
                'successful_months': result.get('successful_months', []),
                'failed_months': result.get('failed_months', []),
                'errors': result.get('errors', []),
            }
        logger.error(
            'myDATA sync: μη αναγνωρίσιμο αποτέλεσμα συγχρονισμού (%s) — '
            'θεωρείται αποτυχία', type(result).__name__)
        return {
            'status': 'failed',
            'reason': 'unexpected_error',
            'successful_months': [],
            'failed_months': [],
            'errors': ['Μη αναγνωρίσιμο αποτέλεσμα συγχρονισμού.'],
        }

    def _sync_period_months(self, period):
        """
        Sync all months in the period.

        Γύρος 23 — ΔΟΜΗΜΕΝΟ αποτέλεσμα αντί για σιωπηλή κατάποση
        σφαλμάτων. Ο caller ΔΕΝ επιτρέπεται να δηλώσει success=True όταν
        ο συγχρονισμός απέτυχε ολικά ή μερικά, ούτε να παρουσιάσει stale
        δεδομένα ως ενημερωμένα.

        Returns dict:
            {
              'status': 'success' | 'partial' | 'failed',
              'reason': '' | 'missing_credentials' | 'authentication'
                        | 'api_failure' | 'unexpected_error',
              'successful_months': [...],
              'failed_months': [...],
              'errors': [...],   # γενικά μηνύματα, ΧΩΡΙΣ credentials/PII
            }
        """
        result = {
            'status': 'failed',
            'reason': '',
            'successful_months': [],
            'failed_months': [],
            'errors': [],
        }
        months = list(period.months_in_period)

        try:
            credentials = period.client.mydata_credentials
        except Exception:
            logger.warning(
                'myDATA sync: δεν βρέθηκαν credentials για client id=%s',
                period.client_id)
            result.update(reason='missing_credentials',
                          failed_months=months,
                          errors=['Δεν υπάρχουν διαπιστευτήρια myDATA.'])
            return result

        if not credentials.has_credentials:
            logger.warning(
                'myDATA sync: ελλιπή credentials για client id=%s',
                period.client_id)
            result.update(reason='missing_credentials',
                          failed_months=months,
                          errors=['Δεν υπάρχουν διαπιστευτήρια myDATA.'])
            return result

        from django.core.management import call_command
        from django.core.management.base import CommandError
        from io import StringIO

        for month in months:
            # Sync μήνα μέσω του ίδιου command με το credentials.sync action.
            # Per-month try: ο μήνας σημειώνεται synced ΜΟΝΟ σε επιτυχία και
            # η αποτυχία ΚΑΤΑΓΡΑΦΕΤΑΙ στο αποτέλεσμα (δεν καταπίνεται).
            try:
                call_command(
                    'mydata_sync_vat',
                    '--client', period.client.afm,
                    '--year', str(period.year),
                    '--month', str(month),
                    stdout=StringIO(),
                )
            except Exception as exc:
                # Ταξινόμηση χωρίς να διαρρεύσει raw exception text
                text = str(exc).lower()
                if any(k in text for k in ('auth', '401', 'unauthor',
                                           'διαπιστευτ')):
                    reason = 'authentication'
                elif isinstance(exc, CommandError):
                    reason = 'api_failure'
                else:
                    reason = 'unexpected_error'
                if not result['reason']:
                    result['reason'] = reason
                logger.error(
                    'myDATA sync απέτυχε: client id=%s %s/%s (%s)',
                    period.client_id, month, period.year,
                    type(exc).__name__)
                result['failed_months'].append(month)
                result['errors'].append(
                    f'Αποτυχία συγχρονισμού για τον μήνα {month}.')
                continue

            result['successful_months'].append(month)
            if month not in period.months_synced:
                period.months_synced.append(month)

        try:
            period.save(update_fields=['months_synced'])
        except Exception:
            logger.exception(
                'myDATA sync: αποτυχία αποθήκευσης months_synced για '
                'period id=%s', period.pk)
            result.update(status='failed', reason='unexpected_error')
            result['errors'].append('Αποτυχία αποθήκευσης κατάστασης '
                                    'συγχρονισμού.')
            return result

        if not result['failed_months']:
            result['status'] = 'success'
            result['reason'] = ''
        elif result['successful_months']:
            result['status'] = 'partial'
        else:
            result['status'] = 'failed'
        return result

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

        # Μόνο Διαχειριστής (superuser ή view_all_clients) — το σκέτο
        # is_staff θα επέτρεπε σε staff Λογιστή με change_vatperiodresult
        # να ξεκλειδώνει κλειδωμένες περιόδους
        if not (
            request.user.is_superuser
            or request.user.has_perm('accounting.view_all_clients')
        ):
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
            period.previous_credit = Decimal(str(credit))
            if period.previous_credit < 0:
                return Response(
                    {'error': 'Το πιστωτικό δεν μπορεί να είναι αρνητικό'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            period.save(update_fields=['previous_credit', 'updated_at'])

            # Recalculate with new credit
            period.calculate_from_records(save=True)

            return Response({
                'success': True,
                'message': f'Το πιστωτικό ορίστηκε σε {period.previous_credit}€',
                'period': self.get_serializer(period).data
            })
        except (ValueError, TypeError):
            return Response(
                {'error': 'Μη έγκυρο ποσό'},
                status=status.HTTP_400_BAD_REQUEST
            )


class VATPeriodCalculatorView(APIView):
    """
    Quick calculator view για υπολογισμό ΦΠΑ περιόδου.

    GET /api/mydata/calculator/?client_id=1&period_type=quarterly&year=2025&period=1
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .models import VATPeriodResult

        # Read endpoint: απαιτεί το view model permission, όχι μόνο auth
        if not request.user.has_perm('mydata.view_vatperiodresult'):
            return Response(
                {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
                status=status.HTTP_403_FORBIDDEN,
            )

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

        if period_type not in ('monthly', 'quarterly'):
            return Response(
                {'error': "Μη έγκυρο period_type (επιτρεπτά: 'monthly', 'quarterly')"},
                status=status.HTTP_400_BAD_REQUEST
            )

        year = _parse_int(year, 'year')
        max_period = 12 if period_type == 'monthly' else 4
        period = _parse_int(period, 'period', min_val=1, max_val=max_period)

        # Get client (RBAC: μόνο προσβάσιμοι πελάτες)
        try:
            allowed = accessible_clients(request.user)
            if client_id:
                client = allowed.get(pk=client_id)
            else:
                client = allowed.get(afm=afm)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Ο πελάτης δεν βρέθηκε'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Το GET δεν δημιουργεί εγγραφές για read-only χρήστες: η δημιουργία
        # ή ο επανυπολογισμός απαιτούν το change permission
        can_write = request.user.has_perm('mydata.change_vatperiodresult')
        period_result = VATPeriodResult.objects.filter(
            client=client, period_type=period_type, year=year, period=period,
        ).first()
        created = False
        if period_result is None:
            if not can_write:
                return Response(
                    {'error': 'Δεν έχει υπολογιστεί ακόμη αυτή η περίοδος.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            period_result, created = VATPeriodResult.get_or_create_for_period(
                client=client,
                period_type=period_type,
                year=year,
                period=period
            )

        # If new or request wants recalculation
        if (created or request.query_params.get('recalculate')) and can_write:
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


# =============================================================================
# INVOICE SUBMISSION (Αποστολή τιμολογίων στο myDATA)
# =============================================================================

class _CanSubmitInvoices(permissions.BasePermission):
    """Απαιτεί inventory.change_invoice για υποβολή/ακύρωση στην ΑΑΔΕ."""

    def has_permission(self, request, view):
        return request.user.has_perm('inventory.change_invoice')


class _CanViewInvoices(permissions.BasePermission):
    """Απαιτεί inventory.view_invoice για ανάγνωση τιμολογίων."""

    def has_permission(self, request, view):
        return request.user.has_perm('inventory.view_invoice')


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Τιμολόγια (inventory.Invoice) με actions αποστολής/ακύρωσης στο myDATA.

    list:   GET  /api/mydata/invoices/?direction=outgoing&mydata_sent=false
    send:   POST /api/mydata/invoices/{id}/send/
    cancel: POST /api/mydata/invoices/{id}/cancel/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        # Υποβολή/ακύρωση φορολογικών παραστατικών στην ΑΑΔΕ: staff ΚΑΙ
        # ρητό model permission (όχι απλώς is_staff)
        if self.action in ('send', 'cancel'):
            return [permissions.IsAuthenticated(), permissions.IsAdminUser(),
                    _CanSubmitInvoices()]
        # list/retrieve: όχι μόνο authenticated — και view permission
        return [permissions.IsAuthenticated(), _CanViewInvoices()]

    def get_queryset(self):
        from inventory.models import Invoice
        from .serializers import InvoiceListSerializer  # noqa: F401 (import check)

        # RBAC: μόνο τιμολόγια αντισυμβαλλομένων στους οποίους έχει πρόσβαση
        qs = Invoice.objects.select_related('counterpart').prefetch_related('items').filter(
            counterpart__in=accessible_clients(self.request.user)
        )

        direction = self.request.query_params.get('direction', 'outgoing')
        if direction == 'outgoing':
            qs = qs.filter(is_outgoing=True)
        elif direction == 'incoming':
            qs = qs.filter(is_outgoing=False)

        sent = self.request.query_params.get('mydata_sent')
        if sent is not None:
            qs = qs.filter(mydata_sent=sent.lower() in ('true', '1', 'yes'))

        year = self.request.query_params.get('year')
        if year and year.isdigit():
            qs = qs.filter(issue_date__year=int(year))

        return qs.order_by('-issue_date', '-number')

    def get_serializer_class(self):
        from .serializers import InvoiceListSerializer
        return InvoiceListSerializer

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """Αποστολή του τιμολογίου στο myDATA."""
        from .client import MyDataAPIError, MyDataValidationError
        from .services import MyDataService

        invoice = self.get_object()
        try:
            result = MyDataService().submit_invoice(invoice)
        except ValueError as e:
            # Ελεγχόμενα guard messages (λάθος κατεύθυνση, ήδη απεσταλμένο,
            # χωρίς γραμμές) — hand-written, χωρίς traceback/credentials.
            logger.warning('myDATA submit rejected invoice id=%s', invoice.pk)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except MyDataValidationError as e:
            # Η ΑΑΔΕ απέρριψε το παραστατικό (business validation) — 422, όχι 502.
            # Μόνο το ελεγχόμενο .message, όχι raw response_text.
            logger.warning('myDATA validation rejected invoice id=%s', invoice.pk)
            return Response(
                {'error': e.message or 'Το παραστατικό απορρίφθηκε από το myDATA.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except MyDataAPIError:
            logger.exception('myDATA submit failed for invoice id=%s', invoice.pk)
            return Response(
                {'error': 'Σφάλμα επικοινωνίας με το myDATA'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        invoice.refresh_from_db()
        return Response({
            'success': True,
            'mark': result['mark'],
            'uid': result['uid'],
            'invoice': self.get_serializer(invoice).data,
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Ακύρωση του απεσταλμένου τιμολογίου στο myDATA."""
        from .client import MyDataAPIError, MyDataValidationError
        from .services import MyDataService

        invoice = self.get_object()
        try:
            result = MyDataService().cancel_invoice(invoice)
        except ValueError as e:
            # Ελεγχόμενα guard messages — hand-written, χωρίς traceback/credentials.
            logger.warning('myDATA cancel rejected invoice id=%s', invoice.pk)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except MyDataValidationError as e:
            logger.warning('myDATA validation rejected cancel invoice id=%s', invoice.pk)
            return Response(
                {'error': e.message or 'Η ακύρωση απορρίφθηκε από το myDATA.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except MyDataAPIError:
            logger.exception('myDATA cancel failed for invoice id=%s', invoice.pk)
            return Response(
                {'error': 'Σφάλμα επικοινωνίας με το myDATA'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        invoice.refresh_from_db()
        return Response({
            'success': True,
            'cancellation_mark': result['cancellation_mark'],
            'invoice': self.get_serializer(invoice).data,
        })
