"""
Global Search API
Author: ddiplas
Version: 1.0
Description: Unified search API for clients, obligations, tickets, and calls.
             Supports Greek characters and returns max 5 results per category.
"""

import logging
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClientProfile, MonthlyObligation, VoIPCall, Ticket
from .mixins import user_sees_all_clients
from .services.access import accessible_clients, accessible_obligations

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def global_search(request):
    """
    Global search API for searching across all entities.

    GET /api/v1/search/?q=<query>

    Search fields per entity:
    - Clients: eponimia, afm, kinito_tilefono, tilefono_epixeirisis_1, email
    - Obligations: client.eponimia, obligation_type.name, notes
    - Tickets: title, description, client.eponimia
    - Calls: phone_number, client.eponimia

    Returns max 5 results per category.
    """
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return Response({
            'query': query,
            'results': {
                'clients': [],
                'obligations': [],
                'tickets': [],
                'calls': []
            },
            'total': 0
        })

    try:
        # RBAC: κάθε κατηγορία απαιτεί το αντίστοιχο view_* permission —
        # χρήστης χωρίς ρόλο (κανένα view perm) παίρνει κενά αποτελέσματα
        # αντί να διαβάζει ΑΦΜ/emails/κλήσεις από εναλλακτική διαδρομή.
        user = request.user
        results = {
            'clients': (
                search_clients(query, user=user)
                if user.has_perm('accounting.view_clientprofile') else []
            ),
            'obligations': (
                search_obligations(query, user=user)
                if user.has_perm('accounting.view_monthlyobligation') else []
            ),
            'tickets': (
                search_tickets(query, user=user)
                if user.has_perm('accounting.view_ticket') else []
            ),
            'calls': (
                search_calls(query, user=user)
                if user.has_perm('accounting.view_voipcall') else []
            ),
        }

        total = sum(len(v) for v in results.values())

        return Response({
            'query': query,
            'results': results,
            'total': total
        })

    except Exception as e:
        logger.error(f"Error in global_search: {e}", exc_info=True)
        return Response({
            'query': query,
            'results': {
                'clients': [],
                'obligations': [],
                'tickets': [],
                'calls': []
            },
            'total': 0,
            'error': str(e)
        }, status=500)


def search_clients(query: str, limit: int = 5, user=None) -> list:
    """
    Search clients by:
    - eponimia (company name)
    - afm (tax ID)
    - kinito_tilefono (mobile phone)
    - tilefono_epixeirisis_1 (business phone)
    - email
    """
    base = accessible_clients(user) if user is not None else ClientProfile.objects.all()
    clients = base.filter(
        Q(eponimia__icontains=query) |
        Q(afm__icontains=query) |
        Q(kinito_tilefono__icontains=query) |
        Q(tilefono_epixeirisis_1__icontains=query) |
        Q(email__icontains=query)
    ).filter(is_active=True).order_by('eponimia')[:limit]

    return [{
        'id': c.id,
        'title': c.eponimia,
        'subtitle': f'ΑΦΜ: {c.afm}',
        'url': f'/clients/{c.id}',
        'type': 'client',
        'extra': {
            'afm': c.afm,
            'email': c.email or '',
            'phone': c.kinito_tilefono or c.tilefono_epixeirisis_1 or '',
            'is_active': c.is_active
        }
    } for c in clients]


def search_obligations(query: str, limit: int = 5, user=None) -> list:
    """
    Search obligations by:
    - client.eponimia (client name)
    - obligation_type.name (type name)
    - notes
    """
    base = accessible_obligations(user) if user is not None else MonthlyObligation.objects.all()
    obligations = base.filter(
        Q(client__eponimia__icontains=query) |
        Q(obligation_type__name__icontains=query) |
        Q(notes__icontains=query) |
        Q(client__afm__icontains=query)
    ).select_related('client', 'obligation_type').order_by('-deadline')[:limit]

    status_labels = {
        'pending': 'Εκκρεμεί',
        'in_progress': 'Σε εξέλιξη',
        'completed': 'Ολοκληρώθηκε',
        'overdue': 'Εκπρόθεσμη',
        'cancelled': 'Ακυρώθηκε'
    }

    return [{
        'id': o.id,
        'title': f'{o.obligation_type.name} {o.month:02d}/{o.year}',
        'subtitle': f'{o.client.eponimia} - {status_labels.get(o.status, o.status)}',
        'url': f'/clients/{o.client.id}?tab=obligations',
        'type': 'obligation',
        'extra': {
            'client_id': o.client.id,
            'client_name': o.client.eponimia,
            'type_name': o.obligation_type.name,
            'status': o.status,
            'status_display': status_labels.get(o.status, o.status),
            'month': o.month,
            'year': o.year,
            'deadline': o.deadline.isoformat() if o.deadline else None
        }
    } for o in obligations]


def search_tickets(query: str, limit: int = 5, user=None) -> list:
    """
    Search tickets by:
    - title
    - description
    - client.eponimia (client name)
    """
    base = Ticket.objects.all()
    if user is not None and not user_sees_all_clients(user):
        # Tickets ξένων πελατών εκτός — χωρίς πελάτη (π.χ. αναπάντητες) ορατά
        base = base.filter(
            Q(client__isnull=True) | Q(client__assigned_users=user)
        ).distinct()
    tickets = base.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(client__eponimia__icontains=query) |
        Q(call__phone_number__icontains=query)
    ).select_related('client', 'call').order_by('-created_at')[:limit]

    status_labels = {
        'open': 'Ανοιχτό',
        'assigned': 'Ανατεθειμένο',
        'in_progress': 'Σε εξέλιξη',
        'resolved': 'Επιλυμένο',
        'closed': 'Κλειστό'
    }

    return [{
        'id': t.id,
        'title': t.title,
        'subtitle': f'{t.client.eponimia if t.client else "Άγνωστος"} - {status_labels.get(t.status, t.status)}',
        'url': '/calls?tab=tickets',
        'type': 'ticket',
        'extra': {
            'client_id': t.client.id if t.client else None,
            'client_name': t.client.eponimia if t.client else None,
            'status': t.status,
            'status_display': status_labels.get(t.status, t.status),
            'priority': t.priority,
            'phone_number': t.call.phone_number if t.call else None
        }
    } for t in tickets]


def search_calls(query: str, limit: int = 5, user=None) -> list:
    """
    Search calls by:
    - phone_number
    - client.eponimia (client name)
    """
    base = VoIPCall.objects.all()
    if user is not None and not user_sees_all_clients(user):
        base = base.filter(
            Q(client__isnull=True) | Q(client__assigned_users=user)
        ).distinct()
    calls = base.filter(
        Q(phone_number__icontains=query) |
        Q(client__eponimia__icontains=query) |
        Q(notes__icontains=query)
    ).select_related('client').order_by('-started_at')[:limit]

    direction_labels = {
        'incoming': 'Εισερχόμενη',
        'outgoing': 'Εξερχόμενη'
    }

    status_labels = {
        'active': 'Ενεργή',
        'completed': 'Ολοκληρώθηκε',
        'missed': 'Αναπάντητη',
        'failed': 'Αποτυχία'
    }

    return [{
        'id': c.id,
        'title': c.phone_number,
        'subtitle': f'{direction_labels.get(c.direction, c.direction)} - {c.client.eponimia if c.client else "Άγνωστος"}',
        'url': '/calls',
        'type': 'call',
        'extra': {
            'client_id': c.client.id if c.client else None,
            'client_name': c.client.eponimia if c.client else None,
            'direction': c.direction,
            'direction_display': direction_labels.get(c.direction, c.direction),
            'status': c.status,
            'status_display': status_labels.get(c.status, c.status),
            'started_at': c.started_at.isoformat() if c.started_at else None
        }
    } for c in calls]
