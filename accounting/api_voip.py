# -*- coding: utf-8 -*-
"""
accounting/api_voip.py
Author: ddiplas
Version: 1.0
Description: REST API for VoIP calls and Tickets management
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import VoIPCall, VoIPCallLog, Ticket, ClientProfile
from .phone_utils import auto_match_call, batch_auto_match_calls, find_client_by_phone
from .permissions import (
    ClientModelPermissions, IsVoIPMonitor, IsLocalRequest, ServiceWriteOnly,
)
from .services.access import require_model_perms

import logging

logger = logging.getLogger(__name__)


# ============================================
# PAGINATION
# ============================================

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ============================================
# SERIALIZERS
# ============================================

class ClientMiniSerializer(serializers.ModelSerializer):
    """Minimal client info for embedding"""
    class Meta:
        model = ClientProfile
        fields = ['id', 'eponimia', 'afm']


class VoIPCallFullSerializer(serializers.ModelSerializer):
    """Enhanced VoIP Call serializer with client and ticket info"""
    client = ClientMiniSerializer(read_only=True)
    client_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    has_ticket = serializers.SerializerMethodField()
    duration_formatted = serializers.SerializerMethodField()
    direction_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = VoIPCall
        fields = [
            'id', 'call_id', 'phone_number', 'direction', 'direction_display',
            'status', 'status_display', 'duration_seconds', 'duration_formatted',
            'started_at', 'ended_at', 'client', 'client_id', 'has_ticket',
            'notes', 'resolution', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'call_id', 'created_at', 'updated_at']

    def get_has_ticket(self, obj):
        return hasattr(obj, 'ticket')

    def get_duration_formatted(self, obj):
        if obj.duration_seconds:
            minutes = obj.duration_seconds // 60
            seconds = obj.duration_seconds % 60
            return f"{minutes:02d}:{seconds:02d}"
        return "-"

    def get_direction_display(self, obj):
        return obj.get_direction_display()

    def get_status_display(self, obj):
        return obj.get_status_display()



class TicketSerializer(serializers.ModelSerializer):
    """Full Ticket serializer"""
    client = ClientMiniSerializer(read_only=True)
    client_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    call = serializers.SerializerMethodField()
    call_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    status_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    days_since_created = serializers.ReadOnlyField()
    is_open = serializers.ReadOnlyField()

    class Meta:
        model = Ticket
        fields = [
            'id', 'title', 'description', 'status', 'status_display',
            'priority', 'priority_display', 'client', 'client_id',
            'call', 'call_id', 'assigned_to', 'assigned_to_name',
            'notes', 'created_at', 'assigned_at', 'resolved_at', 'closed_at',
            'days_since_created', 'is_open'
        ]
        read_only_fields = ['id', 'created_at', 'assigned_at', 'resolved_at', 'closed_at']

    def get_call(self, obj):
        if obj.call:
            return {
                'id': obj.call.id,
                'phone_number': obj.call.phone_number,
                'direction': obj.call.direction,
                'direction_display': obj.call.get_direction_display(),
                'started_at': obj.call.started_at,
            }
        return None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_priority_display(self, obj):
        return obj.get_priority_display()

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return None


class TicketCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tickets"""
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'priority', 'client', 'call', 'notes']
        extra_kwargs = {
            'client': {'required': False},
            'call': {'required': False},
            'description': {'required': False},
            'priority': {'required': False},
            'notes': {'required': False},
        }


# ============================================
# VIEWSETS
# ============================================

def _scope_by_client(queryset, user):
    """
    RBAC scoping για κλήσεις/tickets: scoped χρήστες βλέπουν εγγραφές
    των ανατεθειμένων πελατών τους + όσες δεν έχουν αντιστοιχιστεί ακόμη
    σε πελάτη (χρειάζονται triage από όποιον απαντά το τηλέφωνο).
    """
    from accounting.mixins import user_sees_all_clients
    if not getattr(user, 'is_authenticated', False):
        # Service caller (Fritz monitor / localhost) που πέρασε το δικό του
        # permission gate — χωρίς user δεν έχει νόημα assignment scoping,
        # και το PATCH του monitor πρέπει να βρίσκει την κλήση.
        return queryset
    if user_sees_all_clients(user):
        return queryset
    return queryset.filter(
        Q(client__isnull=True) | Q(client__assigned_users=user)
    ).distinct()


class VoIPCallViewSet(viewsets.ModelViewSet):
    """
    Enhanced VoIP Call ViewSet with match and ticket creation

    Endpoints:
    - GET /api/v1/calls/ - List all calls with pagination and filters
    - GET /api/v1/calls/{id}/ - Get call detail
    - POST /api/v1/calls/{id}/match-client/ - Match call to client
    - POST /api/v1/calls/{id}/create-ticket/ - Create ticket from call

    Authentication (any of these):
    - JWT/Session authentication for user access
    - X-API-Key header for internal services (Fritz!Box monitor)
    - Localhost requests (127.0.0.1, ::1) for same-machine services
    """
    queryset = VoIPCall.objects.select_related('client').order_by('-started_at')
    serializer_class = VoIPCallFullSerializer
    # Χρήστες: auth + model perms. Εσωτερικές υπηρεσίες (Fritz monitor,
    # localhost): δικό τους gate, χωρίς model perms.
    # Service callers (monitor/localhost): ΜΟΝΟ create/update κλήσης
    permission_classes = [
        (permissions.IsAuthenticated & ClientModelPermissions)
        | ((IsVoIPMonitor | IsLocalRequest) & ServiceWriteOnly)
    ]
    pagination_class = StandardPagination
    action_perms = {
        'match_client': ['accounting.change_voipcall'],
        'auto_match': ['accounting.change_voipcall'],
        'auto_match_all': ['accounting.change_voipcall'],
        'create_ticket': ['accounting.add_ticket'],
    }

    def _validate_client_id(self, serializer):
        # Το client_id στο payload μόνο για προσβάσιμο πελάτη
        from accounting.services.access import get_accessible_client_or_404
        client_id = serializer.validated_data.get('client_id')
        if client_id is None:
            return
        if not getattr(self.request.user, 'is_authenticated', False):
            # Service caller (Fritz monitor / localhost): δεν επιτρέπεται να
            # αντιστοιχίσει πελάτη — η κλήση μένει unassigned και η
            # αντιστοίχιση γίνεται από χρήστη ή από το auto-match.
            serializer.validated_data.pop('client_id', None)
            return
        get_accessible_client_or_404(self.request.user, client_id, request=self.request)

    def perform_create(self, serializer):
        self._validate_client_id(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validate_client_id(serializer)
        serializer.save()

    def get_queryset(self):
        queryset = _scope_by_client(super().get_queryset(), self.request.user)

        # Filter by direction
        direction = self.request.query_params.get('direction')
        if direction:
            if direction == 'missed':
                queryset = queryset.filter(status='missed')
            else:
                queryset = queryset.filter(direction=direction)

        # Filter by status
        call_status = self.request.query_params.get('status')
        if call_status:
            queryset = queryset.filter(status=call_status)

        # Filter by client
        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(started_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(started_at__date__lte=date_to)

        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(phone_number__icontains=search) |
                Q(client__eponimia__icontains=search) |
                Q(notes__icontains=search)
            )

        return queryset

    def list(self, request, *args, **kwargs):
        """Override list to add stats"""
        queryset = self.get_queryset()

        # Calculate stats (σύνολα μόνο στις προσβάσιμες κλήσεις)
        all_calls = _scope_by_client(VoIPCall.objects.all(), request.user)
        today = timezone.now().date()

        stats = {
            'total': all_calls.count(),
            'incoming': all_calls.filter(direction='incoming').exclude(status='missed').count(),
            'outgoing': all_calls.filter(direction='outgoing').count(),
            'missed': all_calls.filter(status='missed').count(),
            'today': all_calls.filter(started_at__date=today).count(),
        }

        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['stats'] = stats
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'stats': stats
        })

    @action(detail=True, methods=['post'])
    def match_client(self, request, pk=None):
        """Match a call to a client"""
        call = self.get_object()
        client_id = request.data.get('client_id')

        if not client_id:
            return Response(
                {'error': 'client_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from accounting.services.access import accessible_clients
            client = accessible_clients(request.user).get(id=client_id)
            call.client = client
            call.client_email = client.email
            call.save()

            # Log the action
            VoIPCallLog.objects.create(
                call=call,
                action='client_matched',
                description=f'Matched to client: {client.eponimia}'
            )

            return Response(VoIPCallFullSerializer(call).data)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Client not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def create_ticket(self, request, pk=None):
        """Create a ticket from a call"""
        call = self.get_object()

        # Check if ticket already exists
        if hasattr(call, 'ticket'):
            return Response(
                {'error': 'Ticket already exists for this call'},
                status=status.HTTP_400_BAD_REQUEST
            )

        title = request.data.get('title', f'Κλήση από {call.phone_number}')
        description = request.data.get('description', '')
        priority = request.data.get('priority', 'medium')

        try:
            ticket = Ticket.objects.create(
                call=call,
                client=call.client,
                title=title,
                description=description,
                priority=priority,
                status='open'
            )

            call.ticket_created = True
            call.ticket_id = str(ticket.id)
            call.save()

            # Log the action
            VoIPCallLog.objects.create(
                call=call,
                action='ticket_created',
                description=f'Ticket #{ticket.id} created: {title}'
            )

            return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error creating ticket: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def auto_match_all(self, request):
        """
        Batch auto-match all unmatched calls to clients.

        POST /api/v1/calls/auto_match_all/
        Query params:
        - dry_run: If 'true', show what would be matched without saving
        """
        dry_run = request.query_params.get('dry_run', 'false').lower() == 'true'

        # Global ενέργεια: μόνο για χρήστες που βλέπουν όλους τους πελάτες
        from accounting.mixins import user_sees_all_clients
        if not user_sees_all_clients(request.user):
            return Response(
                {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        stats = batch_auto_match_calls(dry_run=dry_run)

        return Response({
            'dry_run': dry_run,
            'total_unmatched': stats['total'],
            'matched': stats['matched'],
            'still_unmatched': stats['unmatched'],
            'details': stats['details']
        })

    @action(detail=True, methods=['post'])
    def auto_match(self, request, pk=None):
        """
        Auto-match a single call to a client by phone number.

        POST /api/v1/calls/{id}/auto_match/
        """
        call = self.get_object()

        if call.client is not None:
            return Response({
                'message': 'Call is already matched to a client',
                'client': ClientMiniSerializer(call.client).data
            })

        # Scoped χρήστες αντιστοιχίζουν μόνο σε ανατεθειμένους πελάτες τους
        from accounting.mixins import user_sees_all_clients
        from accounting.services.access import accessible_clients
        clients_qs = None
        if not user_sees_all_clients(request.user):
            clients_qs = accessible_clients(request.user)

        client = auto_match_call(call, save=True, clients_qs=clients_qs)

        if client:
            return Response({
                'message': 'Successfully auto-matched call to client',
                'client': ClientMiniSerializer(client).data
            })
        else:
            return Response({
                'message': 'No matching client found for this phone number',
                'phone_number': call.phone_number
            }, status=status.HTTP_404_NOT_FOUND)


class TicketViewSet(viewsets.ModelViewSet):
    """
    Ticket management ViewSet

    Endpoints:
    - GET /api/v1/tickets/ - List all tickets
    - POST /api/v1/tickets/ - Create ticket
    - GET /api/v1/tickets/{id}/ - Get ticket detail
    - PUT/PATCH /api/v1/tickets/{id}/ - Update ticket
    - DELETE /api/v1/tickets/{id}/ - Delete ticket
    - POST /api/v1/tickets/{id}/change-status/ - Change ticket status
    """
    queryset = Ticket.objects.select_related('client', 'call', 'assigned_to').order_by('-created_at')
    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated, ClientModelPermissions]
    pagination_class = StandardPagination
    action_perms = {
        'change_status': ['accounting.change_ticket'],
        'assign': ['accounting.change_ticket'],
    }

    def get_serializer_class(self):
        if self.action == 'create':
            return TicketCreateSerializer
        return TicketSerializer

    def get_queryset(self):
        queryset = _scope_by_client(super().get_queryset(), self.request.user)

        # Filter by status
        ticket_status = self.request.query_params.get('status')
        if ticket_status:
            queryset = queryset.filter(status=ticket_status)

        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        # Filter by client
        client_id = self.request.query_params.get('client_id')
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        # Filter by assigned_to
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)

        # Filter open only
        if self.request.query_params.get('open_only') == 'true':
            queryset = queryset.filter(status__in=['open', 'assigned', 'in_progress'])

        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(client__eponimia__icontains=search)
            )

        return queryset

    def list(self, request, *args, **kwargs):
        """Override list to add stats"""
        queryset = self.get_queryset()

        # Calculate stats (μόνο προσβάσιμα tickets)
        all_tickets = _scope_by_client(Ticket.objects.all(), request.user)

        stats = {
            'total': all_tickets.count(),
            'open': all_tickets.filter(status='open').count(),
            'in_progress': all_tickets.filter(status='in_progress').count(),
            'resolved': all_tickets.filter(status='resolved').count(),
            'closed': all_tickets.filter(status='closed').count(),
        }

        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['stats'] = stats
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'stats': stats
        })

    def _check_client_id(self, serializer):
        # Το client/client_id στο payload πρέπει να δείχνει σε προσβάσιμο πελάτη
        from accounting.services.access import get_accessible_client_or_404, user_can_access_client
        from django.http import Http404
        client = serializer.validated_data.get('client')
        if client is not None and not user_can_access_client(self.request.user, client):
            raise Http404('ClientProfile not found')
        client_id = serializer.validated_data.get('client_id')
        if client_id:
            client = get_accessible_client_or_404(
                self.request.user, client_id, request=self.request
            )
        if (
            client is None
            and 'client_id' not in serializer.validated_data
            and serializer.instance is not None
        ):
            # Update χωρίς αλλαγή πελάτη: έλεγχος συνέπειας κλήσης με τον
            # υπάρχοντα πελάτη του ticket
            client = serializer.instance.client
        self._check_call(serializer, client)

    def _check_call(self, serializer, client):
        # Η κλήση στο payload πρέπει να είναι προσβάσιμη και να συμφωνεί
        # με τον πελάτη του ticket. Unassigned κλήση επιτρέπεται (triage).
        from django.http import Http404
        from accounting.services.access import user_can_access_client
        from rest_framework.exceptions import ValidationError
        call = serializer.validated_data.get('call')
        if call is None:
            call_id = serializer.validated_data.get('call_id')
            if call_id:
                call = VoIPCall.objects.filter(pk=call_id).first()
                if call is None:
                    raise Http404('VoIPCall not found')
        if call is None:
            return
        if call.client_id and not user_can_access_client(self.request.user, call.client):
            raise Http404('VoIPCall not found')
        if client is not None and call.client_id and call.client_id != client.pk:
            raise ValidationError(
                {'call': 'Η κλήση ανήκει σε διαφορετικό πελάτη από το ticket.'}
            )

    def perform_create(self, serializer):
        """Auto-set status to open on create (μόνο για προσβάσιμο πελάτη)"""
        self._check_client_id(serializer)
        serializer.save(status='open')

    def perform_update(self, serializer):
        self._check_client_id(serializer)
        serializer.save()

    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        """Change ticket status"""
        ticket = self.get_object()
        new_status = request.data.get('status')

        valid_statuses = ['open', 'assigned', 'in_progress', 'resolved', 'closed']
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Must be one of: {valid_statuses}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_status = ticket.status

        # Handle status transitions
        if new_status == 'assigned':
            ticket.mark_as_assigned(request.user)
        elif new_status == 'in_progress':
            ticket.mark_as_in_progress()
        elif new_status == 'resolved':
            ticket.mark_as_resolved()
        elif new_status == 'closed':
            ticket.mark_as_closed()
        else:
            ticket.status = new_status
            ticket.save()

        logger.info(f"Ticket #{ticket.id} status changed: {old_status} -> {new_status}")

        return Response(TicketSerializer(ticket).data)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign ticket to a user"""
        ticket = self.get_object()
        user_id = request.data.get('user_id')

        if user_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(id=user_id)
                ticket.mark_as_assigned(user)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Assign to current user
            ticket.mark_as_assigned(request.user)

        return Response(TicketSerializer(ticket).data)


# ============================================
# STANDALONE API VIEWS
# ============================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@require_model_perms('accounting.view_voipcall')
def calls_stats(request):
    """Get call statistics"""
    today = timezone.now().date()
    this_week_start = today - timezone.timedelta(days=today.weekday())
    this_month_start = today.replace(day=1)

    calls = _scope_by_client(VoIPCall.objects.all(), request.user)
    stats = {
        'today': {
            'total': calls.filter(started_at__date=today).count(),
            'incoming': calls.filter(started_at__date=today, direction='incoming').exclude(status='missed').count(),
            'outgoing': calls.filter(started_at__date=today, direction='outgoing').count(),
            'missed': calls.filter(started_at__date=today, status='missed').count(),
        },
        'this_week': {
            'total': calls.filter(started_at__date__gte=this_week_start).count(),
            'missed': calls.filter(started_at__date__gte=this_week_start, status='missed').count(),
        },
        'this_month': {
            'total': calls.filter(started_at__date__gte=this_month_start).count(),
            'missed': calls.filter(started_at__date__gte=this_month_start, status='missed').count(),
        },
        'unmatched_calls': calls.filter(client__isnull=True).count(),
        'calls_without_tickets': calls.filter(status='missed', ticket_created=False).count(),
    }

    return Response(stats)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@require_model_perms('accounting.view_ticket')
def tickets_stats(request):
    """Get ticket statistics"""
    tickets = _scope_by_client(Ticket.objects.all(), request.user)
    stats = {
        'total': tickets.count(),
        'by_status': {
            'open': tickets.filter(status='open').count(),
            'assigned': tickets.filter(status='assigned').count(),
            'in_progress': tickets.filter(status='in_progress').count(),
            'resolved': tickets.filter(status='resolved').count(),
            'closed': tickets.filter(status='closed').count(),
        },
        'by_priority': {
            'urgent': tickets.filter(priority='urgent', status__in=['open', 'assigned', 'in_progress']).count(),
            'high': tickets.filter(priority='high', status__in=['open', 'assigned', 'in_progress']).count(),
            'medium': tickets.filter(priority='medium', status__in=['open', 'assigned', 'in_progress']).count(),
            'low': tickets.filter(priority='low', status__in=['open', 'assigned', 'in_progress']).count(),
        },
        'open_tickets': tickets.filter(status__in=['open', 'assigned', 'in_progress']).count(),
        'avg_resolution_days': None,  # Could calculate if needed
    }

    return Response(stats)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
@require_model_perms('accounting.view_clientprofile')
def search_clients_for_match(request):
    """Search clients for matching to a call"""
    query = request.query_params.get('q', '')

    if len(query) < 2:
        return Response([])

    from accounting.services.access import accessible_clients
    clients = accessible_clients(request.user).filter(
        Q(eponimia__icontains=query) |
        Q(afm__icontains=query) |
        Q(kinito_tilefono__icontains=query) |
        Q(tilefono_oikias_1__icontains=query) |
        Q(tilefono_epixeirisis_1__icontains=query)
    )[:10]

    return Response(ClientMiniSerializer(clients, many=True).data)
