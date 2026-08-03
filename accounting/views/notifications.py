"""
Notification Views
Author: ddiplas
Description: Views for retrieving user notifications
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone

from datetime import timedelta

from ..models import MonthlyObligation

import logging

logger = logging.getLogger(__name__)


@staff_member_required
def get_notifications(request):
    """
    Get user notifications for dashboard
    """
    # RBAC: view perm + scoping — το staff_member_required δεν αρκεί,
    # αλλιώς scoped staff έβλεπε υποχρεώσεις/επωνυμίες όλων των πελατών
    from accounting.services.access import accessible_obligations, check_model_perms
    if not check_model_perms(request, 'accounting.view_monthlyobligation'):
        return JsonResponse(
            {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'}, status=403,
        )
    scoped_obligations = accessible_obligations(request.user)

    now = timezone.now()
    notifications = []

    # Overdue obligations
    overdue = scoped_obligations.filter(
        deadline__lt=now.date(),
        status__in=['pending', 'overdue']
    ).select_related('client', 'obligation_type').order_by('deadline')[:10]

    for obl in overdue:
        days_overdue = (now.date() - obl.deadline).days
        notifications.append({
            'id': obl.id,
            'type': 'overdue',
            'priority': 'high',
            'title': f'Καθυστερημένη: {obl.obligation_type.name}',
            'message': f'{obl.client.eponimia} - {days_overdue} μέρες καθυστέρηση',
            'deadline': obl.deadline.isoformat(),
            'client_id': obl.client.id,
            'icon': 'overdue',
        })

    # Due today
    today_obligations = scoped_obligations.filter(
        deadline=now.date(),
        status='pending'
    ).select_related('client', 'obligation_type')

    for obl in today_obligations:
        notifications.append({
            'id': obl.id,
            'type': 'due_today',
            'priority': 'medium',
            'title': f'Λήγει Σήμερα: {obl.obligation_type.name}',
            'message': f'{obl.client.eponimia}',
            'deadline': obl.deadline.isoformat(),
            'client_id': obl.client.id,
            'icon': 'warning',
        })

    # Upcoming (next 3 days)
    next_3_days = now.date() + timedelta(days=3)
    upcoming = scoped_obligations.filter(
        deadline__range=[now.date() + timedelta(days=1), next_3_days],
        status='pending'
    ).select_related('client', 'obligation_type').order_by('deadline')[:5]

    for obl in upcoming:
        days_until = (obl.deadline - now.date()).days
        notifications.append({
            'id': obl.id,
            'type': 'upcoming',
            'priority': 'low',
            'title': f'Προσεχώς: {obl.obligation_type.name}',
            'message': f'{obl.client.eponimia} - σε {days_until} μέρες',
            'deadline': obl.deadline.isoformat(),
            'client_id': obl.client.id,
            'icon': 'calendar',
        })

    return JsonResponse({
        'notifications': notifications,
        'count': len(notifications),
        'overdue_count': len([n for n in notifications if n['type'] == 'overdue']),
        'today_count': len([n for n in notifications if n['type'] == 'due_today']),
    })
