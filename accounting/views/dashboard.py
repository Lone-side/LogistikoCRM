# accounting/views/dashboard.py
"""
Dashboard and Reports Views
Author: ddiplas
Description: Dashboard with comprehensive filtering, statistics, and reports analytics
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from datetime import timedelta

from ..models import (
    ClientProfile, MonthlyObligation, ObligationType,
)

from .helpers import (
    _safe_int,
    _calculate_dashboard_stats,
    _build_filtered_query,
    _calculate_monthly_completion_stats,
    _calculate_client_performance,
    _calculate_time_stats,
    _calculate_revenue,
    _calculate_type_stats,
    _calculate_current_month_stats,
    _format_chart_data,
)

import logging
from accounting.services.access import (
    accessible_clients, accessible_documents, accessible_obligations,
)

logger = logging.getLogger(__name__)


# ============================================
# MAIN DASHBOARD
# ============================================

@staff_member_required
@login_required
def dashboard_view(request):
    """
    Enhanced Dashboard with comprehensive filtering and statistics
    Features: Advanced filters, real-time stats, bulk operations support
    """
    from django.http import HttpResponseForbidden
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.view_monthlyobligation'):
        return HttpResponseForbidden('Δεν έχετε δικαίωμα πρόσβασης.')
    now = timezone.now()

    # ========== FILTER PARAMETERS ==========
    filter_params = {
        'status': request.GET.get('status', ''),
        'client': request.GET.get('client', ''),
        'type': request.GET.get('type', ''),
        'date_from': request.GET.get('date_from', ''),
        'date_to': request.GET.get('date_to', ''),
        'sort_by': request.GET.get('sort', 'deadline')
    }

    # Convert IDs to integers safely
    filter_client_id = _safe_int(filter_params['client'])
    filter_type_id = _safe_int(filter_params['type'])

    logger.info(f"Dashboard accessed by {request.user.username} with filters: {filter_params}")

    # ========== STATISTICS (UNFILTERED) ==========
    stats = _calculate_dashboard_stats(request.user)

    # ========== BUILD FILTERED QUERY ==========
    upcoming_query = _build_filtered_query(
        filter_params, filter_client_id, filter_type_id, now, request.user)

    # ========== APPLY SORTING ==========
    sort_mapping = {
        'deadline': 'deadline',
        'client': 'client__eponimia',
        'type': 'obligation_type__name',
        'status': 'status'
    }
    upcoming_query = upcoming_query.order_by(
        sort_mapping.get(filter_params['sort_by'], 'deadline')
    )

    # Get results with limit for performance
    upcoming = list(upcoming_query[:100])
    upcoming_count = upcoming_query.count()

    # ========== OVERDUE OBLIGATIONS ==========
    overdue_query = accessible_obligations(request.user).filter(
        deadline__lt=now.date(),
        status__in=['pending', 'overdue']
    ).select_related('client', 'obligation_type')

    # Apply client/type filters to overdue as well
    if filter_client_id:
        overdue_query = overdue_query.filter(client_id=filter_client_id)
    if filter_type_id:
        overdue_query = overdue_query.filter(obligation_type_id=filter_type_id)

    overdue_obligations = list(overdue_query.order_by('deadline')[:20])
    overdue_count = overdue_query.count()

    # ========== FILTER OPTIONS ==========
    all_clients = accessible_clients(request.user).all().order_by('eponimia').values('id', 'eponimia', 'afm')
    all_types = ObligationType.objects.filter(is_active=True).order_by('name')

    # ========== PREPARE CONTEXT ==========
    context = {
        'title': 'Dashboard - Επισκόπηση',

        # Statistics
        'total_clients': stats['total_clients'],
        'pending': stats['pending'],
        'completed': stats['completed'],
        'overdue': stats['overdue'],

        # Main data
        'upcoming': upcoming,
        'upcoming_count': upcoming_count,
        'overdue_obligations': overdue_obligations,
        'overdue_count': overdue_count,

        # Filter options
        'all_clients': all_clients,
        'all_types': all_types,

        # Current filter values
        **{f'filter_{k}': v for k, v in filter_params.items()},

        # Additional metadata
        'current_date': now.date(),
        'user': request.user,
    }

    return render(request, 'accounting/dashboard.html', context)


# ============================================
# REPORTS & ANALYTICS
# ============================================

@staff_member_required
@login_required
def reports_view(request):
    """
    Comprehensive analytics dashboard with charts and statistics
    """
    from django.http import HttpResponseForbidden
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.view_monthlyobligation'):
        return HttpResponseForbidden('Δεν έχετε δικαίωμα πρόσβασης.')
    now = timezone.now()
    # Ασφαλής μετατροπή + clamp 1..36 (άκυρο input → default 6)
    months_back = _safe_int(request.GET.get('months')) or 6
    months_back = max(1, min(months_back, 36))
    start_date = (now - timedelta(days=30*months_back)).date()

    # Monthly completion statistics
    monthly_stats = _calculate_monthly_completion_stats(start_date, request.user)

    # Client performance metrics
    client_stats = _calculate_client_performance(start_date, request.user)

    # Time tracking summary
    time_stats = _calculate_time_stats(start_date, request.user)

    # Revenue calculations
    revenue_data = _calculate_revenue(start_date, request.user)

    # Obligation type statistics
    type_stats = _calculate_type_stats(start_date)

    # Current month summary
    current_stats = _calculate_current_month_stats(now)

    # Format data for charts
    chart_data = _format_chart_data(monthly_stats)

    # Get clients for PDF export dropdown
    clients = accessible_clients(request.user).filter(is_active=True).order_by('eponimia')

    # Year choices for monthly report
    current_year = now.year
    year_choices = list(range(current_year - 2, current_year + 2))

    context = {
        'title': 'Reports & Analytics',
        'months_back': months_back,
        **chart_data,
        'client_stats': client_stats,
        'time_stats': time_stats,
        'total_revenue': revenue_data['total'],
        'type_stats': type_stats,
        'current_stats': current_stats,
        # PDF Export context
        'clients': clients,
        'current_month': now.month,
        'current_year': current_year,
        'year_choices': year_choices,
    }

    return render(request, 'accounting/reports.html', context)
