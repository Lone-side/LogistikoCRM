# accounting/views/calendar.py
"""
Calendar Views
Author: ddiplas
Description: Calendar views for obligation management with FullCalendar integration
"""

import calendar
from datetime import datetime, timedelta

from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.utils import timezone

from ..models import (
    ClientProfile, MonthlyObligation, ObligationType,
)

import logging
from accounting.services.access import (
    accessible_clients, accessible_documents, accessible_obligations,
)

logger = logging.getLogger(__name__)


# ============================================
# CALENDAR VIEWS
# ============================================

@staff_member_required
@login_required
def calendar_view(request):
    """
    Προβολή ημερολογίου υποχρεώσεων με FullCalendar
    Features: Month/Week/List views, filters, color-coded status
    """
    today = timezone.now().date()

    # Get all clients for filter dropdown
    clients = accessible_clients(request.user).filter(is_active=True).order_by('eponimia')

    # Get all obligation types for filter dropdown
    obligation_types = ObligationType.objects.filter(is_active=True).order_by('name')

    # Calculate statistics for the current month
    current_month_start = today.replace(day=1)
    if today.month == 12:
        next_month_start = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month_start = today.replace(month=today.month + 1, day=1)

    month_obligations = accessible_obligations(request.user).filter(
        deadline__gte=current_month_start,
        deadline__lt=next_month_start
    )

    stats = {
        'pending_count': month_obligations.filter(status='pending').count(),
        'overdue_count': accessible_obligations(request.user).filter(
            status='pending',
            deadline__lt=today
        ).count(),
        'completed_this_month': month_obligations.filter(status='completed').count(),
    }

    context = {
        "title": "Ημερολόγιο Υποχρεώσεων",
        "clients": clients,
        "obligation_types": obligation_types,
        "today": today,
        "stats": stats,
    }
    return render(request, "accounting/calendar.html", context)


@staff_member_required
@login_required
@require_GET
def calendar_events_api(request):
    """
    API endpoint for FullCalendar events
    Returns JSON with obligations formatted for FullCalendar
    """
    # Get date range from FullCalendar
    start_str = request.GET.get('start', '')
    end_str = request.GET.get('end', '')

    # Get filter parameters
    client_id = request.GET.get('client', '')
    obligation_type_id = request.GET.get('type', '')
    status_filter = request.GET.get('status', '')

    # Parse dates
    try:
        if start_str:
            start_date = datetime.strptime(start_str[:10], '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date().replace(day=1)

        if end_str:
            end_date = datetime.strptime(end_str[:10], '%Y-%m-%d').date()
        else:
            # Default to end of month
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1, day=1)
    except ValueError:
        start_date = timezone.now().date().replace(day=1)
        end_date = start_date + timedelta(days=31)

    # Build query
    queryset = accessible_obligations(request.user).filter(
        deadline__gte=start_date,
        deadline__lte=end_date
    ).select_related('client', 'obligation_type')

    # Apply filters
    if client_id:
        try:
            queryset = queryset.filter(client_id=int(client_id))
        except ValueError:
            pass

    if obligation_type_id:
        try:
            queryset = queryset.filter(obligation_type_id=int(obligation_type_id))
        except ValueError:
            pass

    if status_filter:
        if status_filter == 'overdue':
            queryset = queryset.filter(status='pending', deadline__lt=timezone.now().date())
        else:
            queryset = queryset.filter(status=status_filter)

    # Define colors based on status
    status_colors = {
        'pending': '#f59e0b',    # Yellow/amber
        'completed': '#22c55e',  # Green
        'overdue': '#ef4444',    # Red
    }

    today = timezone.now().date()

    # Build events list
    events = []
    for obligation in queryset:
        # Determine actual status (check for overdue)
        actual_status = obligation.status
        if actual_status == 'pending' and obligation.deadline and obligation.deadline < today:
            actual_status = 'overdue'

        color = status_colors.get(actual_status, '#6b7280')

        # Build event title
        client_name = obligation.client.eponimia if obligation.client else 'Άγνωστος'
        type_name = obligation.obligation_type.name if obligation.obligation_type else 'Άγνωστος'

        event = {
            'id': obligation.id,
            'title': f"{type_name} - {client_name}",
            'start': obligation.deadline.isoformat() if obligation.deadline else None,
            'end': obligation.deadline.isoformat() if obligation.deadline else None,
            'color': color,
            'backgroundColor': color,
            'borderColor': color,
            'extendedProps': {
                'status': actual_status,
                'client_id': obligation.client_id,
                'client_name': client_name,
                'client_afm': obligation.client.afm if obligation.client else '',
                'obligation_type': type_name,
                'obligation_type_id': obligation.obligation_type_id,
                'period': f"{obligation.month:02d}/{obligation.year}",
                'notes': obligation.notes or '',
                'edit_url': f"/admin/accounting/monthlyobligation/{obligation.id}/change/",
            }
        }
        events.append(event)

    return JsonResponse({'events': events})
