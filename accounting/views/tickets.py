"""
Ticket Management Views
Author: ddiplas
Description: Views for ticket assignment and status management
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone

from ..models import Ticket, VoIPCallLog

import json
import logging

logger = logging.getLogger(__name__)


@staff_member_required
@require_POST
def assign_ticket(request, ticket_id):
    """Assign ticket to current user"""
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_ticket'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )

    try:
        from accounting.api_voip import _scope_by_client
        ticket = _scope_by_client(Ticket.objects.all(), request.user).get(id=ticket_id)

        # Mark as assigned
        ticket.mark_as_assigned(request.user)

        # Log
        VoIPCallLog.objects.create(
            call=ticket.call,
            action='ticket_assigned',
            description=f"Ticket #{ticket_id} assigned to {request.user.username}"
        )

        logger.info(f"Ticket #{ticket_id} assigned to {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': f'Ticket ανατέθηκε σε {request.user.get_full_name() or request.user.username}'
        })

    except Ticket.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Ticket δεν βρέθηκε'
        }, status=404)
    except Exception as e:
        logger.error(f"Error assigning ticket: {e}")
        return JsonResponse({
            'success': False,
            'message': f'Σφάλμα: {str(e)}'
        }, status=500)


@staff_member_required
@require_POST
def update_ticket_status(request, ticket_id):
    """Update ticket status and notes"""
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_ticket'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )

    try:
        from accounting.api_voip import _scope_by_client
        ticket = _scope_by_client(Ticket.objects.all(), request.user).get(id=ticket_id)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON'
            }, status=400)

        # Update status
        if 'status' in data and data['status'] in ['open', 'assigned', 'in_progress', 'resolved', 'closed']:
            ticket.status = data['status']

        # Update notes
        if 'notes' in data:
            new_note = data['notes']
            timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
            if ticket.notes:
                ticket.notes += f"\n[{timestamp}] {new_note}"
            else:
                ticket.notes = f"[{timestamp}] {new_note}"

        # Auto-mark dates
        if ticket.status == 'resolved' and not ticket.resolved_at:
            ticket.mark_as_resolved()
        elif ticket.status == 'closed' and not ticket.closed_at:
            ticket.mark_as_closed()

        ticket.save()

        # Log
        VoIPCallLog.objects.create(
            call=ticket.call,
            action='ticket_updated',
            description=f"Ticket #{ticket_id} status → {ticket.get_status_display()}"
        )

        logger.info(f"Ticket #{ticket_id} updated to status {ticket.status}")

        return JsonResponse({
            'success': True,
            'message': 'Ticket ενημερώθηκε!',
            'ticket': {
                'id': ticket.id,
                'status': ticket.get_status_display(),
                'notes': ticket.notes,
            }
        })

    except Ticket.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Ticket δεν βρέθηκε'
        }, status=404)
    except Exception as e:
        logger.error(f"Error updating ticket: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Σφάλμα: {str(e)}'
        }, status=500)
