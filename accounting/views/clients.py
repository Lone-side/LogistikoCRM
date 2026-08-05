"""
Client Views
Author: ddiplas
Description: Views for client details and document management
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from rest_framework import viewsets

from datetime import timedelta

from ..models import (
    ClientProfile, ClientObligation, MonthlyObligation,
    ClientDocument
)
from ..serializers import ClientDocumentSerializer
from .helpers import _calculate_monthly_stats

import logging
from accounting.services.access import (
    accessible_clients, accessible_documents, accessible_obligations,
)

logger = logging.getLogger(__name__)


@staff_member_required
def client_detail_view(request, client_id):
    """
    Comprehensive client view with all obligations and analytics
    """
    from django.http import HttpResponseForbidden
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.view_clientprofile'):
        return HttpResponseForbidden('Δεν έχετε δικαίωμα πρόσβασης.')
    client = get_object_or_404(accessible_clients(request.user), id=client_id)
    now = timezone.now()

    # All obligations for this client
    all_obligations = accessible_obligations(request.user).filter(
        client=client
    ).select_related('obligation_type').order_by('-deadline')

    # Calculate statistics
    stats = {
        'total': all_obligations.count(),
        'pending': all_obligations.filter(status='pending').count(),
        'completed': all_obligations.filter(status='completed').count(),
        'overdue': all_obligations.filter(status='overdue').count(),
    }

    # Upcoming obligations (next 30 days)
    next_month = now.date() + timedelta(days=30)
    upcoming = all_obligations.filter(
        deadline__range=[now.date(), next_month],
        status='pending'
    ).order_by('deadline')[:10]

    # Overdue obligations
    overdue = all_obligations.filter(
        deadline__lt=now.date(),
        status__in=['pending', 'overdue']
    ).order_by('deadline')

    # Recent completed (last 30 days)
    past_month = now.date() - timedelta(days=30)
    recent_completed = all_obligations.filter(
        status='completed',
        completed_date__gte=past_month
    ).order_by('-completed_date')[:10]

    # Monthly breakdown (last 6 months)
    monthly_stats = _calculate_monthly_stats(all_obligations, now)

    # Active obligation types
    active_types = ClientObligation.objects.filter(
        client=client,
        is_active=True
    ).select_related('obligation_type')

    # Client documents
    documents = accessible_documents(request.user).filter(
        client=client
    ).order_by('-uploaded_at')

    context = {
        'title': f'{client.eponimia} - Λεπτομέρειες',
        'client': client,
        'stats': stats,
        'upcoming': upcoming,
        'overdue': overdue,
        'recent_completed': recent_completed,
        'monthly_stats': monthly_stats,
        'active_types': active_types,
        'documents': documents,
    }

    return render(request, 'accounting/client_detail.html', context)


class ClientDocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing client documents via API"""
    queryset = ClientDocument.objects.all()
    serializer_class = ClientDocumentSerializer

    def get_queryset(self):
        # RBAC + ο serializer διαβάζει client/obligation/uploaded_by ανά έγγραφο
        queryset = accessible_documents(self.request.user).select_related(
            'client', 'obligation', 'obligation__obligation_type', 'uploaded_by'
        )
        client_id = self.request.query_params.get('client')
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        return queryset
