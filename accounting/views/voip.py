# accounting/views/voip.py
"""
VoIP Views for Accounting Application

This module contains all VoIP-related views including:
- VoIP Dashboard and management views
- Fritz!Box webhook integration
- VoIP API endpoints (function-based and DRF ViewSets)
- Statistics, bulk actions, and CSV export

Author: ddiplas
"""

import hmac

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.middleware.csrf import get_token
from django.core.mail import send_mail
from django.conf import settings
from django.views.generic import ListView

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from datetime import timedelta
import logging
import json
import csv

from ..permissions import (
    INSECURE_DEFAULT_TOKEN, IsVoIPMonitor, IsLocalRequest,
    ClientModelPermissions,
)
from ..models import (
    ClientProfile, VoIPCall, VoIPCallLog, Ticket
)
from ..serializers import VoIPCallSerializer, VoIPCallLogSerializer

from .helpers import (
    _match_client_by_phone_standalone,
    _format_voip_call,
    _calculate_success_rate,
    _log_voip_change,
)


# ============================================
# LOGGER CONFIGURATION
# ============================================
from accounting.services.access import mask_pii_value

logger = logging.getLogger(__name__)

from accounting.api_voip import _scope_by_client
from accounting.permissions import ServiceWriteOnly


# ============================================
# VOIP DASHBOARD & MANAGEMENT
# ============================================

@staff_member_required
def voip_dashboard(request):
    """
    Modern VoIP Dashboard with real-time updates
    """
    from django.http import HttpResponseForbidden
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.view_voipcall'):
        return HttpResponseForbidden('Δεν έχετε δικαίωμα πρόσβασης.')
    # Get recent calls with optimized query
    calls = _scope_by_client(
        VoIPCall.objects.select_related('client'), request.user
    ).order_by('-started_at')[:50]

    # Calculate statistics
    today = timezone.now().date()
    stats = _scope_by_client(VoIPCall.objects.all(), request.user).aggregate(
        total=Count('id'),
        missed=Count('id', filter=Q(status='missed')),
        completed=Count('id', filter=Q(status='completed')),
        today_total=Count('id', filter=Q(started_at__date=today)),
        pending_followup=Count('id', filter=Q(resolution='follow_up')),
    )

    # Calculate success rate
    stats['success_rate'] = _calculate_success_rate(
        stats['completed'],
        stats['total']
    )

    context = {
        'calls': calls,
        'stats': stats,
        'csrf_token': get_token(request),
    }

    logger.info(f"VoIP Dashboard accessed by {request.user.username}")
    return render(request, 'admin/voip_dashboard.html', context)


# ============================================
# FRITZ WEBHOOK - Token-authenticated endpoint
# ============================================

@csrf_exempt
@require_http_methods(["POST"])
def fritz_webhook(request):
    """
    Secure webhook endpoint for Fritz!Box monitor.
    Uses token authentication instead of session/admin auth.
    """
    # Verify token
    auth_header = request.headers.get('Authorization', '')
    expected_token = getattr(settings, 'FRITZ_API_TOKEN', '')

    if not expected_token or expected_token == INSECURE_DEFAULT_TOKEN:
        logger.error("FRITZ_API_TOKEN not configured (or left at insecure default)")
        return JsonResponse({'error': 'Server misconfigured'}, status=500)

    if not hmac.compare_digest(auth_header, f'Bearer {expected_token}'):
        logger.warning(f"Fritz webhook: Invalid token attempt")
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'create':
            # Create new call record (or get existing to handle duplicates)
            call_id = data.get('call_id')
            call, created = VoIPCall.objects.get_or_create(
                call_id=call_id,
                defaults={
                    'phone_number': data.get('phone_number', ''),
                    'direction': data.get('direction', 'incoming'),
                    'status': 'active',
                    'started_at': data.get('started_at'),
                }
            )

            if not created:
                # Call already exists, return existing data
                logger.info(f"VoIP: Call {call_id} already exists, skipping duplicate")
                return JsonResponse({
                    'success': True,
                    'id': call.id,
                    'call_id': call.call_id,
                    'client_id': call.client.id if call.client else None,
                    'client_name': call.client.eponimia if call.client else None,
                    'is_known': call.client is not None,
                    'duplicate': True
                })

            # Auto-match client by phone
            client = _match_client_by_phone_standalone(call.phone_number)
            if client:
                call.client = client
                call.client_email = client.email
                call.save()
                logger.info(f"VoIP: Matched call {call.call_id} to client {client.eponimia}")

            # Create log entry
            VoIPCallLog.objects.create(
                call=call,
                action='started',
                description=f"Εισερχόμενη κλήση από {call.phone_number}" +
                           (f" - {client.eponimia}" if client else " - Άγνωστος")
            )

            logger.info(f"VoIP: Created call {call.call_id} from {mask_pii_value(call.phone_number)}")

            return JsonResponse({
                'success': True,
                'id': call.id,
                'call_id': call.call_id,
                'client_id': client.id if client else None,
                'client_name': client.eponimia if client else None,
                'is_known': client is not None
            })

        elif action == 'update':
            call_id = data.get('id')
            call = VoIPCall.objects.filter(id=call_id).first()

            if not call:
                return JsonResponse({'error': 'Call not found'}, status=404)

            # Update fields
            old_status = call.status
            call.status = data.get('status', call.status)

            if data.get('ended_at'):
                ended_at_str = data.get('ended_at')
                if isinstance(ended_at_str, str):
                    call.ended_at = timezone.now()
                else:
                    call.ended_at = ended_at_str

                # Calculate duration
                if call.started_at:
                    delta = call.ended_at - call.started_at
                    call.duration_seconds = max(0, int(delta.total_seconds()))

            call.save()

            # Log status change
            if old_status != call.status:
                VoIPCallLog.objects.create(
                    call=call,
                    action='status_changed',
                    description=f"Κατάσταση: {old_status} → {call.status}"
                )

            # CRITICAL: Trigger Celery task for missed calls
            if call.status == 'missed':
                from accounting.tasks import create_or_update_ticket_for_missed_call
                create_or_update_ticket_for_missed_call.delay(call.id)
                logger.info(f"VoIP: Triggered ticket creation for missed call {call.id}")

            logger.info(f"VoIP: Updated call {call.id} to status {call.status}")

            return JsonResponse({
                'success': True,
                'id': call.id,
                'status': call.status,
                'duration': call.duration_seconds
            })

        else:
            return JsonResponse({'error': f'Invalid action: {action}'}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Fritz webhook error: {e}")
        return JsonResponse({'error': 'Παρουσιάστηκε σφάλμα'}, status=500)


@staff_member_required
@require_http_methods(["GET"])
@cache_page(5)  # Cache for 5 seconds
def voip_calls_api(request):
    """
    Real-time API for VoIP calls with AJAX support
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.view_voipcall'):
        return JsonResponse({'error': 'Δεν έχετε δικαίωμα.'}, status=403)
    try:
        # Get recent calls
        calls = _scope_by_client(
            VoIPCall.objects.select_related('client'), request.user
        ).order_by('-started_at')[:30]

        # Sort by priority (missed first)
        calls = sorted(calls, key=lambda x: (
            x.status != 'missed',
            -x.started_at.timestamp()
        ))

        # Format data for JSON
        data = [_format_voip_call(call) for call in calls]

        return JsonResponse({
            'success': True,
            'calls': data,
            'timestamp': timezone.now().isoformat(),
            'total_missed': _scope_by_client(
                VoIPCall.objects.all(), request.user
            ).filter(status='missed').count(),
        })

    except Exception as e:
        logger.error(f"Error in voip_calls_api: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Παρουσιάστηκε σφάλμα'
        }, status=500)


@staff_member_required
@require_POST
def voip_call_update(request, call_id):
    """Update VoIP call via AJAX"""
    try:
        from accounting.services.access import check_model_perms
        if not check_model_perms(request, 'accounting.change_voipcall'):
            return JsonResponse(
                {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
                status=403,
            )
        call = _scope_by_client(
            VoIPCall.objects.select_related('client'), request.user
        ).get(id=call_id)
    except VoIPCall.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Κλήση δεν βρέθηκε!'
        }, status=404)

    # Parse JSON body
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)

    old_values = {
        'notes': call.notes,
        'resolution': call.resolution,
        'status': call.status,
    }

    # Update fields safely
    if 'notes' in data:
        if not isinstance(data['notes'], str):
            return JsonResponse({
                'success': False,
                'message': 'Μη έγκυρη τιμή για notes'
            }, status=400)
        call.notes = data['notes'][:1000]

    if 'resolution' in data and data['resolution'] in ['pending', 'closed', 'follow_up', '']:
        call.resolution = data['resolution']

    old_status = call.status
    if 'status' in data and data['status'] in ['active', 'completed', 'missed', 'failed']:
        call.status = data['status']

    call.save()
    _log_voip_change(call, old_values, request.user)

    # Optional: trigger ticket when completed
    if old_status != 'completed' and call.status == 'completed':
        try:
            from accounting.tasks import trigger_answered_call_ticket
            trigger_answered_call_ticket(call, request.user)
            logger.info(f"Triggered answered call ticket for call #{call_id}")
        except Exception as e:
            logger.warning(f"Could not trigger answered call ticket: {e}")

    return JsonResponse({
        'success': True,
        'message': f'Κλήση {call.phone_number} ενημερώθηκε!',
        'updated_call': _format_voip_call(call)
    })


# ============================================
# VOIP API VIEWSETS (REST Framework)
# ============================================

class VoIPCallViewSet(viewsets.ModelViewSet):
    """
    REST API ViewSet for VoIP calls

    Authentication (any of these):
    - Admin user access
    - X-API-Key header for internal services (Fritz!Box monitor)
    - Localhost requests (127.0.0.1, ::1) for same-machine services
    """
    queryset = VoIPCall.objects.all()

    def get_queryset(self):
        return _scope_by_client(super().get_queryset(), self.request.user)
    serializer_class = VoIPCallSerializer
    # Service callers (monitor/localhost): ΜΟΝΟ create/update/end_call
    permission_classes = [
        permissions.IsAdminUser
        | ((IsVoIPMonitor | IsLocalRequest) & ServiceWriteOnly)
    ]
    filterset_fields = ['direction', 'status', 'client', 'phone_number']
    search_fields = ['phone_number', 'client__eponimia', 'notes']
    ordering_fields = ['started_at', 'duration_seconds']
    ordering = ['-started_at']

    def perform_create(self, serializer):
        """Create call and auto-match client"""
        voip_call = serializer.save()
        client = self._match_client_by_phone(voip_call.phone_number)

        if client:
            voip_call.client = client
            voip_call.client_email = client.email
            voip_call.save()
            logger.info(f"Matched call to client: {client.eponimia}")

        # Log call creation
        VoIPCallLog.objects.create(
            call=voip_call,
            action='started',
            description=f'Call started from {voip_call.phone_number}'
        )

    def _match_client_by_phone(self, phone_number):
        """Match phone number to client"""
        clean_number = phone_number.replace(" ", "").replace("-", "")

        return ClientProfile.objects.filter(
            Q(tilefono_oikias_1__icontains=clean_number) |
            Q(tilefono_oikias_2__icontains=clean_number) |
            Q(kinito_tilefono__icontains=clean_number) |
            Q(tilefono_epixeirisis_1__icontains=clean_number) |
            Q(tilefono_epixeirisis_2__icontains=clean_number)
        ).first()

    def perform_update(self, serializer):
        """Update call and create ticket if requested"""
        voip_call = serializer.save()

        # Check if we should create a ticket (for missed calls)
        create_ticket = self.request.data.get('create_ticket', False)

        if create_ticket and voip_call.status == 'missed' and not voip_call.ticket_created:
            try:
                # Create ticket for missed call
                ticket = Ticket.objects.create(
                    client=voip_call.client,
                    title=f"Αναπάντητη κλήση από {voip_call.phone_number}",
                    description=f"Αναπάντητη κλήση στις {voip_call.started_at.strftime('%d/%m/%Y %H:%M') if voip_call.started_at else 'N/A'}",
                    priority='medium',
                    status='open',
                    call=voip_call
                )

                # Update call with ticket info
                voip_call.ticket_created = True
                voip_call.ticket_id = str(ticket.id)
                voip_call.save(update_fields=['ticket_created', 'ticket_id'])

                # Log the action
                VoIPCallLog.objects.create(
                    call=voip_call,
                    action='ticket_created',
                    description=f'Auto-created ticket #{ticket.id} for missed call'
                )

                logger.info(f"Created ticket #{ticket.id} for missed call {voip_call.call_id}")

            except Exception as e:
                logger.error(f"Failed to create ticket for call {voip_call.id}: {e}")

    @action(detail=True, methods=['post'])
    def end_call(self, request, pk=None):
        """End a call and process follow-up actions"""
        voip_call = self.get_object()
        ended_at = request.data.get('ended_at')

        if not ended_at:
            return Response(
                {'error': 'ended_at is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Parse and set end time
            from dateutil import parser as dateutil_parser
            if isinstance(ended_at, str):
                ended_at = dateutil_parser.parse(ended_at)

            if ended_at.tzinfo is None:
                ended_at = timezone.make_aware(ended_at)

            voip_call.ended_at = ended_at
            voip_call.status = 'completed' if voip_call.duration_seconds > 10 else 'missed'
            voip_call.save()

            # Log call end
            VoIPCallLog.objects.create(
                call=voip_call,
                action='ended',
                description=f'Call ended - Duration: {voip_call.duration_formatted}'
            )

            # Handle missed call actions
            if voip_call.status == 'missed':
                self._handle_missed_call(voip_call)

            return Response(
                VoIPCallSerializer(voip_call).data,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error ending call: {e}", exc_info=True)
            return Response(
                {'error': 'Παρουσιάστηκε σφάλμα'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def _handle_missed_call(self, voip_call):
        """Process missed call - create ticket and send email"""
        try:
            voip_call.ticket_created = True
            voip_call.save()

            VoIPCallLog.objects.create(
                call=voip_call,
                action='ticket_created',
                description=f'Missed call ticket for {voip_call.phone_number}'
            )

            if voip_call.client_email:
                self._send_missed_call_email(voip_call)

            # Trigger Celery task for smart ticket creation
            try:
                from accounting.tasks import create_or_update_ticket_for_missed_call
                create_or_update_ticket_for_missed_call.delay(voip_call.id)
                logger.info(f"Triggered ticket task for call {voip_call.id}")
            except Exception as e:
                logger.error(f"Failed to trigger ticket task: {e}")

        except Exception as e:
            logger.error(f"Error handling missed call: {e}")

    def _send_missed_call_email(self, voip_call):
        """Send email notification for missed call"""
        try:
            subject = f"Αναπάντητη κλήση - {voip_call.phone_number}"
            message = f"""
Καλησπέρα,

Είχατε μια αναπάντητη κλήση:

Αριθμός: {voip_call.phone_number}
Ώρα: {voip_call.started_at.strftime('%d/%m/%Y %H:%M')}
Κατεύθυνση: {voip_call.get_direction_display()}

Παρακαλώ επικοινωνήστε μαζί μας αν χρειάζεστε κάτι.

Ευχαριστούμε,
Λογιστικό Γραφείο
            """

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [voip_call.client_email],
                fail_silently=False,
            )

            logger.info(f"Email sent to {voip_call.client_email}")

        except Exception as e:
            logger.error(f"Failed to send email: {e}")


class VoIPCallLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for call logs (audit trail).

    RBAC: απαιτεί το model permission `view_voipcalllog` και εφαρμόζει
    client scoping μέσω του snapshot `client` (επιβιώνει της διαγραφής
    της κλήσης). Fail closed: logs με `client=None` (unassigned/legacy
    orphan) βλέπουν ΜΟΝΟ superusers / χρήστες με global client access —
    ΠΟΤΕ scoped χρήστης. Δεν χρησιμοποιείται το nullable `call__client`.
    """
    serializer_class = VoIPCallLogSerializer
    permission_classes = [permissions.IsAuthenticated, ClientModelPermissions]
    filterset_fields = ['call', 'action']
    ordering = ['-created_at']

    def get_queryset(self):
        from accounting.mixins import user_sees_all_clients
        qs = VoIPCallLog.objects.all()
        if user_sees_all_clients(self.request.user):
            return qs
        # Scoping στο snapshot client· client__isnull αποκλείεται (fail closed)
        return qs.filter(
            client__assigned_users=self.request.user
        ).distinct()


# ============================================
# VOIP STATISTICS & ANALYTICS
# ============================================

@staff_member_required
@cache_page(60)  # Cache 1 minute
def voip_statistics(request):
    """
    Advanced statistics για VoIP calls
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.view_voipcall'):
        return JsonResponse({'error': 'Δεν έχετε δικαίωμα.'}, status=403)
    try:
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)

        stats = {
            'today': {
                'total': _scope_by_client(VoIPCall.objects.all(), request.user).filter(started_at__date=today).count(),
                'missed': _scope_by_client(VoIPCall.objects.all(), request.user).filter(started_at__date=today, status='missed').count(),
                'completed': _scope_by_client(VoIPCall.objects.all(), request.user).filter(started_at__date=today, status='completed').count(),
            },
            'week': {
                'total': _scope_by_client(VoIPCall.objects.all(), request.user).filter(started_at__date__gte=week_ago).count(),
                'missed': _scope_by_client(VoIPCall.objects.all(), request.user).filter(started_at__date__gte=week_ago, status='missed').count(),
                'completed': _scope_by_client(VoIPCall.objects.all(), request.user).filter(started_at__date__gte=week_ago, status='completed').count(),
            },
            'by_client': list(
                _scope_by_client(VoIPCall.objects.all(), request.user).filter(client__isnull=False)
                .values('client__eponimia')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
            ),
            'by_resolution': list(
                _scope_by_client(VoIPCall.objects.all(), request.user).values('resolution')
                .annotate(count=Count('id'))
                .order_by('-count')
            ),
        }

        # Calculate average duration
        durations = _scope_by_client(VoIPCall.objects.all(), request.user).filter(
            status='completed',
            duration_seconds__gt=0
        ).values_list('duration_seconds', flat=True)[:100]

        if durations:
            stats['average_duration'] = sum(durations) / len(durations)
        else:
            stats['average_duration'] = 0

        logger.info(f"Statistics generated for {request.user.username}")

        return JsonResponse({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"Error generating statistics: {e}")
        return JsonResponse({'success': False, 'error': 'Παρουσιάστηκε σφάλμα'}, status=500)


@staff_member_required
@require_POST
def voip_bulk_action(request):
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_voipcall'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )
    """
    Bulk update multiple VoIP calls
    """
    try:
        data = json.loads(request.body)
        call_ids = data.get('call_ids', [])
        action = data.get('action')
        value = data.get('value')

        if not isinstance(call_ids, list) or len(call_ids) == 0:
            return JsonResponse({
                'success': False,
                'message': 'No calls selected'
            }, status=400)

        # Update based on action
        updated = 0
        if action == 'resolution':
            if value in ['pending', 'closed', 'follow_up', '']:
                updated = _scope_by_client(VoIPCall.objects.all(), request.user).filter(id__in=call_ids).update(resolution=value)
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid resolution value'
                }, status=400)

        elif action == 'status':
            if value in ['active', 'completed', 'missed', 'failed']:
                updated = _scope_by_client(VoIPCall.objects.all(), request.user).filter(id__in=call_ids).update(status=value)
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid status value'
                }, status=400)

        elif action == 'delete':
            # Η διαγραφή απαιτεί delete_voipcall (όχι μόνο change)
            if not check_model_perms(request, 'accounting.delete_voipcall'):
                return JsonResponse(
                    {'success': False, 'error': 'Δεν έχετε δικαίωμα διαγραφής κλήσεων.'},
                    status=403,
                )
            updated = _scope_by_client(VoIPCall.objects.all(), request.user).filter(id__in=call_ids).delete()[0]

        else:
            return JsonResponse({
                'success': False,
                'message': f'Unknown action: {action}'
            }, status=400)

        logger.info(f"Bulk update: {updated} calls updated by {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': f'{updated} κλήσεις ενημερώθηκαν!',
            'updated_count': updated
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)

    except Exception as e:
        logger.error(f"Error in bulk action: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Παρουσιάστηκε σφάλμα'
        }, status=500)


@staff_member_required
def voip_export_csv(request):
    """
    Export VoIP calls to CSV
    """
    # Τηλέφωνα/emails/επωνυμίες πελατών — θέλει το ξεχωριστό export permission
    if not request.user.has_perm('accounting.export_clientprofile'):
        return JsonResponse(
            {'error': 'Δεν έχετε δικαίωμα εξαγωγής στοιχείων πελατών.'}, status=403
        )
    try:
        # Create response
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="voip_calls_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        # Add BOM for Excel UTF-8 compatibility
        response.write('\ufeff')

        # Create CSV writer
        writer = csv.writer(response)

        # Write headers
        writer.writerow([
            'ID',
            'Αριθμός',
            'Πελάτης',
            'Email',
            'Κατεύθυνση',
            'Κατάσταση',
            'Διάρκεια',
            'Ημερομηνία',
            'Ώρα',
            'Σημειώσεις',
            'Resolution'
        ])

        # Get filtered calls
        calls_query = _scope_by_client(
            VoIPCall.objects.select_related('client').all(), request.user
        )

        # Apply filters if provided
        status_filter = request.GET.get('status')
        if status_filter:
            calls_query = calls_query.filter(status=status_filter)

        direction = request.GET.get('direction')
        if direction:
            calls_query = calls_query.filter(direction=direction)

        date_from = request.GET.get('date_from')
        if date_from:
            calls_query = calls_query.filter(started_at__date__gte=date_from)

        date_to = request.GET.get('date_to')
        if date_to:
            calls_query = calls_query.filter(started_at__date__lte=date_to)

        # Order and limit
        calls_query = calls_query.order_by('-started_at')[:1000]

        # Write data rows
        for call in calls_query:
            writer.writerow([
                call.id,
                call.phone_number,
                call.client.eponimia if call.client else '—',
                call.client_email or '—',
                call.get_direction_display(),
                call.get_status_display(),
                call.duration_formatted,
                call.started_at.strftime('%d/%m/%Y'),
                call.started_at.strftime('%H:%M:%S'),
                (call.notes[:100] + '...') if call.notes and len(call.notes) > 100 else (call.notes or ''),
                call.get_resolution_display() if call.resolution else '—',
            ])

        logger.info(f"CSV exported by {request.user.username}: {calls_query.count()} records")
        return response

    except Exception as e:
        logger.error(f"Error exporting CSV: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Παρουσιάστηκε σφάλμα'}, status=500)
