# -*- coding: utf-8 -*-
"""
accounting/api_dashboard.py
Author: Claude
Description: REST API views for Dashboard statistics and calendar
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Count, Q
from datetime import datetime, timedelta
from calendar import monthrange
from collections import defaultdict

from .models import ClientProfile, MonthlyObligation


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    from accounting.services.access import accessible_clients, accessible_obligations
    ClientQS = accessible_clients(request.user)
    ObligationQS = accessible_obligations(request.user)
    """
    GET /api/dashboard/stats/

    Returns dashboard statistics:
    - total_clients (active)
    - total_obligations_pending
    - total_obligations_completed_this_month
    - overdue_count
    - upcoming_deadlines (next 7 days)
    """
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year
    next_week = today + timedelta(days=7)

    # Active clients count
    total_clients = ClientQS.filter(is_active=True).count()

    # Pending obligations
    total_obligations_pending = ObligationQS.filter(
        status='pending'
    ).count()

    # Completed this month
    total_obligations_completed_this_month = ObligationQS.filter(
        status='completed',
        completed_date__year=current_year,
        completed_date__month=current_month
    ).count()

    # Overdue count
    overdue_count = ObligationQS.filter(
        Q(status='overdue') | Q(status='pending', deadline__lt=today)
    ).count()

    # Το GET δεν γράφει στη βάση: το overdue_count πιο πάνω υπολογίζεται
    # δυναμικά (pending + deadline < σήμερα)· η μόνιμη μετάβαση σε
    # 'overdue' γίνεται από το Celery task update_overdue_obligations.

    # Upcoming deadlines (next 7 days)
    upcoming_obligations = ObligationQS.filter(
        status='pending',
        deadline__gte=today,
        deadline__lte=next_week
    ).select_related('client', 'obligation_type').order_by('deadline')[:10]

    upcoming_deadlines = [
        {
            'id': obl.id,
            'client_name': obl.client.eponimia,
            'client_afm': obl.client.afm,
            'type': obl.obligation_type.name,
            'type_code': obl.obligation_type.code,
            'deadline': obl.deadline.isoformat(),
            'days_until': (obl.deadline - today).days
        }
        for obl in upcoming_obligations
    ]

    # Additional stats
    stats_by_status = ObligationQS.values('status').annotate(
        count=Count('id')
    )
    status_breakdown = {item['status']: item['count'] for item in stats_by_status}

    # Top obligation types this month
    top_types = ObligationQS.filter(
        year=current_year,
        month=current_month
    ).values('obligation_type__name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    # === Κατανομή μήνα ανά τύπο υποχρέωσης, με ανάλυση κατάστασης ===
    type_breakdown = list(
        ObligationQS.filter(year=current_year, month=current_month)
        .values('obligation_type__name', 'obligation_type__code')
        .annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            pending=Count('id', filter=Q(status__in=['pending', 'in_progress'])),
            overdue=Count('id', filter=Q(status='overdue')),
        )
        .order_by('-total')[:8]
    )

    # === Φόρτος εργασίας ανά υπάλληλο ===
    # Ανοιχτές (pending/overdue) ανά assigned_to + ολοκληρωμένες μήνα ανά completed_by
    open_by_user = (
        ObligationQS.filter(status__in=['pending', 'in_progress', 'overdue'])
        .values('assigned_to__id', 'assigned_to__username',
                'assigned_to__first_name', 'assigned_to__last_name')
        .annotate(
            open_count=Count('id', filter=Q(status__in=['pending', 'in_progress'])),
            overdue_count=Count('id', filter=Q(status='overdue')),
        )
    )
    completed_by_user = {
        row['completed_by__id']: row['done']
        for row in ObligationQS.filter(
            status='completed',
            completed_date__year=current_year,
            completed_date__month=current_month,
        ).values('completed_by__id').annotate(done=Count('id'))
    }

    def _user_label(row):
        full = f"{row['assigned_to__first_name'] or ''} {row['assigned_to__last_name'] or ''}".strip()
        return full or row['assigned_to__username'] or 'Χωρίς ανάθεση'

    team_workload = sorted(
        (
            {
                'user_id': row['assigned_to__id'],
                'name': _user_label(row),
                'open': row['open_count'],
                'overdue': row['overdue_count'],
                'completed_this_month': completed_by_user.get(row['assigned_to__id'], 0),
            }
            for row in open_by_user
        ),
        key=lambda r: r['open'] + r['overdue'],
        reverse=True,
    )[:10]

    # === Τάση 6 μηνών (σωστή αριθμητική μηνών — όχι timedelta(30*i)) ===
    greek_months_short = ['Ιαν', 'Φεβ', 'Μάρ', 'Απρ', 'Μάι', 'Ιούν',
                          'Ιούλ', 'Αύγ', 'Σεπ', 'Οκτ', 'Νοέ', 'Δεκ']
    monthly_trend = []
    year, month = current_year, current_month
    for _ in range(6):
        counts = ObligationQS.filter(year=year, month=month).aggregate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
        )
        monthly_trend.append({
            'year': year,
            'month': month,
            'label': f"{greek_months_short[month - 1]} {str(year)[2:]}",
            'total': counts['total'],
            'completed': counts['completed'],
        })
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    monthly_trend.reverse()

    return Response({
        'total_clients': total_clients,
        'total_obligations_pending': total_obligations_pending,
        'total_obligations_completed_this_month': total_obligations_completed_this_month,
        'overdue_count': overdue_count,
        'upcoming_deadlines': upcoming_deadlines,
        'upcoming_count': len(upcoming_deadlines),
        'status_breakdown': status_breakdown,
        'top_obligation_types': list(top_types),
        'type_breakdown': type_breakdown,
        'team_workload': team_workload,
        'monthly_trend': monthly_trend,
        'current_period': {
            'month': current_month,
            'year': current_year
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_calendar(request):
    from accounting.services.access import accessible_obligations
    ObligationQS = accessible_obligations(request.user)
    """
    GET /api/dashboard/calendar/

    Returns obligations for calendar view.
    Parameters:
    - month: 1-12 (default: current month)
    - year: YYYY (default: current year)

    Returns: [{date, count, obligations: [{id, client_name, type}]}]
    """
    today = timezone.now().date()

    # Get parameters
    try:
        month = int(request.query_params.get('month', today.month))
        year = int(request.query_params.get('year', today.year))
    except (ValueError, TypeError):
        month = today.month
        year = today.year

    # Validate month
    if month < 1 or month > 12:
        month = today.month

    # Validate year (clamp όπως ο μήνας)
    if year < 1900 or year > 2100:
        year = today.year

    # Get first and last day of month
    first_day = datetime(year, month, 1).date()
    last_day_num = monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num).date()

    # Get all obligations for this month range
    obligations = ObligationQS.filter(
        deadline__gte=first_day,
        deadline__lte=last_day
    ).select_related('client', 'obligation_type').order_by('deadline')

    # Group by date
    calendar_data = defaultdict(lambda: {'count': 0, 'obligations': []})

    for obl in obligations:
        date_str = obl.deadline.isoformat()
        calendar_data[date_str]['count'] += 1
        calendar_data[date_str]['obligations'].append({
            'id': obl.id,
            'client_name': obl.client.eponimia,
            'client_afm': obl.client.afm,
            'type': obl.obligation_type.name,
            'type_code': obl.obligation_type.code,
            'status': obl.status,
        })

    # Convert to list format
    events = [
        {
            'date': date_str,
            'count': data['count'],
            'obligations': data['obligations']
        }
        for date_str, data in sorted(calendar_data.items())
    ]

    # Summary stats for the month
    total_for_month = obligations.count()
    pending_for_month = obligations.filter(status='pending').count()
    completed_for_month = obligations.filter(status='completed').count()
    overdue_for_month = obligations.filter(
        Q(status='overdue') | Q(status='pending', deadline__lt=today)
    ).count()

    return Response({
        'month': month,
        'year': year,
        'first_day': first_day.isoformat(),
        'last_day': last_day.isoformat(),
        'total_obligations': total_for_month,
        'pending': pending_for_month,
        'completed': completed_for_month,
        'overdue': overdue_for_month,
        'events': events
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_recent_activity(request):
    from accounting.services.access import accessible_clients, accessible_obligations
    ClientQS = accessible_clients(request.user)
    ObligationQS = accessible_obligations(request.user)
    """
    GET /api/dashboard/recent-activity/

    Returns recent activity for dashboard
    """
    try:
        limit = int(request.query_params.get('limit', 10))
        if limit < 1 or limit > 100:
            limit = 10
    except (ValueError, TypeError):
        limit = 10

    # Recent completed obligations
    recent_completed = ObligationQS.filter(
        status='completed'
    ).select_related(
        'client', 'obligation_type', 'completed_by'
    ).order_by('-completed_date', '-updated_at')[:limit]

    completed_activity = [
        {
            'id': obl.id,
            'type': 'completion',
            'client_name': obl.client.eponimia,
            'obligation_type': obl.obligation_type.name,
            'completed_date': obl.completed_date.isoformat() if obl.completed_date else None,
            'completed_by': obl.completed_by.username if obl.completed_by else None,
            'period': f"{obl.month:02d}/{obl.year}"
        }
        for obl in recent_completed
    ]

    # Recently created clients
    recent_clients = ClientQS.order_by('-created_at')[:5]
    new_clients = [
        {
            'id': client.id,
            'type': 'new_client',
            'eponimia': client.eponimia,
            'afm': client.afm,
            'created_at': client.created_at.isoformat()
        }
        for client in recent_clients
    ]

    return Response({
        'recent_completions': completed_activity,
        'new_clients': new_clients
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_client_stats(request):
    from accounting.services.access import accessible_clients
    ClientQS = accessible_clients(request.user)
    """
    GET /api/dashboard/client-stats/

    Returns client-related statistics
    """
    # Client counts by type
    client_by_type = ClientQS.values('eidos_ipoxreou').annotate(
        count=Count('id')
    )

    # Clients with most pending obligations
    clients_with_pending = ClientQS.filter(
        is_active=True,
        monthly_obligations__status='pending'
    ).annotate(
        pending_count=Count('monthly_obligations', filter=Q(monthly_obligations__status='pending'))
    ).order_by('-pending_count')[:10]

    top_clients_pending = [
        {
            'id': client.id,
            'eponimia': client.eponimia,
            'afm': client.afm,
            'pending_count': client.pending_count
        }
        for client in clients_with_pending
    ]

    # Client creation trend (last 6 months)
    from django.db.models.functions import TruncMonth
    creation_trend = ClientQS.filter(
        created_at__gte=timezone.now() - timedelta(days=180)
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    return Response({
        'by_type': list(client_by_type),
        'top_pending': top_clients_pending,
        'creation_trend': list(creation_trend)
    })
