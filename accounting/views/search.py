"""
Search Views
Author: ddiplas
Description: Global search API for clients and obligations
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from django.db.models import Q

from ..models import ClientProfile, MonthlyObligation

import logging
from accounting.services.access import (
    accessible_clients, accessible_documents, accessible_obligations,
)

logger = logging.getLogger(__name__)


@require_GET
@staff_member_required
def global_search_api(request):
    """
    Global search API for clients and obligations.
    Searches by client name (eponimia), AFM, email, and obligation type.
    Returns max 5 results per category.
    """
    # RBAC: εκτός από staff, απαιτούνται και τα view_* model permissions
    from accounting.services.access import check_model_perms
    if not check_model_perms(
        request, 'accounting.view_clientprofile', 'accounting.view_monthlyobligation'
    ):
        return JsonResponse(
            {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'}, status=403
        )

    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'results': [], 'clients': [], 'obligations': []})

    try:
        # Search clients by eponimia, afm, email, or phone
        clients = accessible_clients(request.user).filter(
            Q(eponimia__icontains=query) |
            Q(afm__icontains=query) |
            Q(email__icontains=query) |
            Q(kinito_tilefono__icontains=query) |
            Q(tilefono_epixeirisis_1__icontains=query)
        ).filter(is_active=True)[:5]

        # Search obligations by client name or obligation type name
        obligations = accessible_obligations(request.user).filter(
            Q(client__eponimia__icontains=query) |
            Q(obligation_type__name__icontains=query) |
            Q(client__afm__icontains=query)
        ).select_related('client', 'obligation_type').order_by('-deadline')[:5]

        # Format results
        clients_data = [{
            'id': c.id,
            'name': c.eponimia,
            'afm': c.afm,
            'email': c.email or '',
            'url': f'/admin/accounting/clientprofile/{c.id}/change/',
            'type': 'client'
        } for c in clients]

        obligations_data = [{
            'id': o.id,
            'name': str(o),
            'client': o.client.eponimia,
            'client_afm': o.client.afm,
            'obligation_type': o.obligation_type.name,
            'period': f'{o.month:02d}/{o.year}',
            'status': o.status,
            'url': f'/admin/accounting/monthlyobligation/{o.id}/change/',
            'type': 'obligation'
        } for o in obligations]

        return JsonResponse({
            'success': True,
            'query': query,
            'clients': clients_data,
            'obligations': obligations_data,
            'total': len(clients_data) + len(obligations_data)
        })

    except Exception as e:
        logger.error(f"Error in global_search_api: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
            'clients': [],
            'obligations': []
        }, status=500)
