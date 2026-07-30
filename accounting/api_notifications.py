# -*- coding: utf-8 -*-
"""
accounting/api_notifications.py
REST API endpoint for notifications - JWT authenticated for React frontend.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from .models import MonthlyObligation

import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications_list(request):
    """
    Get user notifications for dashboard.
    GET /api/v1/notifications/

    Returns notifications for:
    - Overdue obligations
    - Due today
    - Upcoming (next 3 days)
    """
    now = timezone.now()
    notifications = []

    try:
        # Νέα έγγραφα από portal (τελευταίες 48 ώρες)
        from datetime import timedelta
        from .models import SharedLinkAccess
        recent_uploads = (
            SharedLinkAccess.objects.filter(
                action='upload',
                accessed_at__gte=now - timedelta(hours=48),
            )
            .select_related('shared_link__client', 'shared_link__document__client')
            .order_by('-accessed_at')[:10]
        )
        for access in recent_uploads:
            link = access.shared_link
            client = link.upload_target_client if link else None
            notifications.append({
                'id': f'portal-upload-{access.id}',
                'type': 'portal_upload',
                'priority': 'medium',
                'title': 'Νέο έγγραφο από portal',
                'message': (
                    f'{client.eponimia if client else "Πελάτης"} ανέβασε '
                    f'έγγραφα μέσω «{link.name if link else "portal"}»'
                ),
                'deadline': None,
                'client_id': client.id if client else None,
                'icon': 'upload',
            })

        # Overdue obligations
        overdue = MonthlyObligation.objects.filter(
            deadline__lt=now.date(),
            status__in=['pending', 'overdue']
        ).select_related('client', 'obligation_type').order_by('deadline')[:10]

        for obl in overdue:
            days_overdue = (now.date() - obl.deadline).days
            notifications.append({
                'id': obl.id,
                'type': 'overdue',
                'priority': 'high',
                'title': f'Καθυστερημένη: {obl.obligation_type.name if obl.obligation_type else "Υποχρέωση"}',
                'message': f'{obl.client.eponimia if obl.client else "Πελάτης"} - {days_overdue} μέρες καθυστέρηση',
                'deadline': obl.deadline.isoformat() if obl.deadline else None,
                'client_id': obl.client.id if obl.client else None,
                'icon': 'overdue',
            })

        # Due today
        today_obligations = MonthlyObligation.objects.filter(
            deadline=now.date(),
            status='pending'
        ).select_related('client', 'obligation_type')

        for obl in today_obligations:
            notifications.append({
                'id': obl.id,
                'type': 'due_today',
                'priority': 'medium',
                'title': f'Λήγει Σήμερα: {obl.obligation_type.name if obl.obligation_type else "Υποχρέωση"}',
                'message': f'{obl.client.eponimia if obl.client else "Πελάτης"}',
                'deadline': obl.deadline.isoformat() if obl.deadline else None,
                'client_id': obl.client.id if obl.client else None,
                'icon': 'warning',
            })

        # Upcoming (next 3 days)
        next_3_days = now.date() + timedelta(days=3)
        upcoming = MonthlyObligation.objects.filter(
            deadline__range=[now.date() + timedelta(days=1), next_3_days],
            status='pending'
        ).select_related('client', 'obligation_type').order_by('deadline')[:5]

        for obl in upcoming:
            days_until = (obl.deadline - now.date()).days
            notifications.append({
                'id': obl.id,
                'type': 'upcoming',
                'priority': 'low',
                'title': f'Προσεχώς: {obl.obligation_type.name if obl.obligation_type else "Υποχρέωση"}',
                'message': f'{obl.client.eponimia if obl.client else "Πελάτης"} - σε {days_until} μέρες',
                'deadline': obl.deadline.isoformat() if obl.deadline else None,
                'client_id': obl.client.id if obl.client else None,
                'icon': 'calendar',
            })

    except Exception as e:
        logger.error(f"Error fetching notifications: {e}")
        # Return empty list on error instead of failing
        return Response({
            'notifications': [],
            'count': 0,
            'overdue_count': 0,
            'today_count': 0,
            'error': str(e)
        })

    return Response({
        'notifications': notifications,
        'count': len(notifications),
        'overdue_count': len([n for n in notifications if n['type'] == 'overdue']),
        'today_count': len([n for n in notifications if n['type'] == 'due_today']),
    })
