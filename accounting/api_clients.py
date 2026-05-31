# -*- coding: utf-8 -*-
"""
accounting/api_clients.py
Author: Claude
Description: REST API ViewSet for ClientProfile management
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, BooleanFilter
from django.db.models import Count, Q

from .models import ClientProfile, MonthlyObligation, ClientDocument
from .serializers import ClientDocumentSerializer


class ClientPagination(PageNumberPagination):
    """Pagination for client list"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000  # Increased to allow full client list in dropdowns


class ClientFilter(FilterSet):
    """Filter for ClientProfile"""
    search = CharFilter(method='filter_search')
    is_active = BooleanFilter(field_name='is_active')

    class Meta:
        model = ClientProfile
        fields = ['is_active']

    def filter_search(self, queryset, name, value):
        """Search by name, afm, email, phone"""
        if value:
            return queryset.filter(
                Q(eponimia__icontains=value) |
                Q(afm__icontains=value) |
                Q(email__icontains=value) |
                Q(kinito_tilefono__icontains=value) |
                Q(tilefono_oikias_1__icontains=value) |
                Q(tilefono_epixeirisis_1__icontains=value)
            )
        return queryset


# ============================================
# CLIENT SERIALIZERS
# ============================================

from rest_framework import serializers


class ClientListSerializer(serializers.ModelSerializer):
    """Serializer for client list view"""

    class Meta:
        model = ClientProfile
        fields = [
            'id', 'afm', 'eponimia', 'email',
            'kinito_tilefono', 'is_active',
            # Fields needed for edit form population
            'eidos_ipoxreou',  # Required for quick edit
            'doy', 'nomiki_morfi',
            'diefthinsi_epixeirisis', 'arithmos_epixeirisis',
            'poli_epixeirisis', 'tk_epixeirisis',
            'imerominia_enarksis',
        ]


class ClientDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single client view"""
    obligations_count = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()
    pending_obligations_count = serializers.SerializerMethodField()

    class Meta:
        model = ClientProfile
        fields = [
            # Basic info
            'id', 'afm', 'doy', 'eponimia', 'onoma', 'onoma_patros',
            # Identity
            'arithmos_taftotitas', 'eidos_taftotitas', 'prosopikos_arithmos',
            'amka', 'am_ika', 'arithmos_gemi', 'arithmos_dypa',
            # Personal dates
            'imerominia_gennisis', 'imerominia_gamou', 'filo',
            # Home address
            'diefthinsi_katoikias', 'arithmos_katoikias', 'poli_katoikias',
            'dimos_katoikias', 'nomos_katoikias', 'tk_katoikias',
            'tilefono_oikias_1', 'tilefono_oikias_2', 'kinito_tilefono',
            # Business address
            'diefthinsi_epixeirisis', 'arithmos_epixeirisis', 'poli_epixeirisis',
            'dimos_epixeirisis', 'nomos_epixeirisis', 'tk_epixeirisis',
            'tilefono_epixeirisis_1', 'tilefono_epixeirisis_2', 'email',
            # Bank info
            'trapeza', 'iban',
            # Tax info
            'eidos_ipoxreou', 'katigoria_vivlion', 'nomiki_morfi',
            'agrotis', 'imerominia_enarksis',
            # Credentials
            'onoma_xristi_taxisnet', 'kodikos_taxisnet',
            'onoma_xristi_ika_ergodoti', 'kodikos_ika_ergodoti',
            'onoma_xristi_gemi', 'kodikos_gemi',
            # Related
            'afm_sizigou', 'afm_foreas', 'am_klidi',
            # Meta
            'is_active', 'created_at', 'updated_at',
            # Computed
            'obligations_count', 'documents_count', 'pending_obligations_count'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_obligations_count(self, obj):
        # Use annotated value if available (avoids N+1 queries)
        if hasattr(obj, '_obligations_count'):
            return obj._obligations_count
        return obj.monthly_obligations.count()

    def get_documents_count(self, obj):
        # Use annotated value if available (avoids N+1 queries)
        if hasattr(obj, '_documents_count'):
            return obj._documents_count
        return obj.documents.count()

    def get_pending_obligations_count(self, obj):
        # Use annotated value if available (avoids N+1 queries)
        if hasattr(obj, '_pending_obligations_count'):
            return obj._pending_obligations_count
        return obj.monthly_obligations.filter(status='pending').count()


class ClientCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating clients"""

    class Meta:
        model = ClientProfile
        fields = [
            # Basic info
            'afm', 'doy', 'eponimia', 'onoma', 'onoma_patros',
            # Identity
            'arithmos_taftotitas', 'eidos_taftotitas', 'prosopikos_arithmos',
            'amka', 'am_ika', 'arithmos_gemi', 'arithmos_dypa',
            # Personal dates
            'imerominia_gennisis', 'imerominia_gamou', 'filo',
            # Home address
            'diefthinsi_katoikias', 'arithmos_katoikias', 'poli_katoikias',
            'dimos_katoikias', 'nomos_katoikias', 'tk_katoikias',
            'tilefono_oikias_1', 'tilefono_oikias_2', 'kinito_tilefono',
            # Business address
            'diefthinsi_epixeirisis', 'arithmos_epixeirisis', 'poli_epixeirisis',
            'dimos_epixeirisis', 'nomos_epixeirisis', 'tk_epixeirisis',
            'tilefono_epixeirisis_1', 'tilefono_epixeirisis_2', 'email',
            # Bank info
            'trapeza', 'iban',
            # Tax info
            'eidos_ipoxreou', 'katigoria_vivlion', 'nomiki_morfi',
            'agrotis', 'imerominia_enarksis',
            # Credentials
            'onoma_xristi_taxisnet', 'kodikos_taxisnet',
            'onoma_xristi_ika_ergodoti', 'kodikos_ika_ergodoti',
            'onoma_xristi_gemi', 'kodikos_gemi',
            # Related
            'afm_sizigou', 'afm_foreas', 'am_klidi',
            # Status
            'is_active',
        ]

    def validate_afm(self, value):
        """Validate Greek AFM (Tax ID)"""
        # Strip whitespace
        value = value.strip()

        if len(value) != 9 or not value.isdigit():
            raise serializers.ValidationError(
                "Το ΑΦΜ πρέπει να αποτελείται από 9 ψηφία."
            )

        # AFM checksum validation (blocking - the Greek AFM checksum is deterministic)
        total = sum(int(value[i]) * (2 ** (8 - i)) for i in range(8))
        check_digit = (total % 11) % 10
        if check_digit != int(value[8]):
            raise serializers.ValidationError(
                "Μη έγκυρο ΑΦΜ (αποτυχία ελέγχου checksum)."
            )
        return value


# Nested serializers for obligations/documents in client detail
class ClientObligationNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for client's obligations"""
    obligation_type_name = serializers.CharField(
        source='obligation_type.name', read_only=True
    )
    obligation_type_code = serializers.CharField(
        source='obligation_type.code', read_only=True
    )

    class Meta:
        model = MonthlyObligation
        fields = [
            'id', 'obligation_type', 'obligation_type_name', 'obligation_type_code',
            'year', 'month', 'deadline', 'status', 'completed_date', 'notes'
        ]


# ============================================
# CLIENT VIEWSET
# ============================================

class ClientViewSet(viewsets.ModelViewSet):
    """
    REST API ViewSet for ClientProfile

    Endpoints:
    - GET /api/clients/ - List all clients (with pagination, search, filters)
    - GET /api/clients/{id}/ - Get single client
    - POST /api/clients/ - Create client
    - PUT /api/clients/{id}/ - Update client
    - DELETE /api/clients/{id}/ - Delete client
    - GET /api/clients/{id}/obligations/ - Get client's obligations
    - GET /api/clients/{id}/documents/ - Get client's documents
    """
    queryset = ClientProfile.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = ClientPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ClientFilter
    ordering_fields = ['eponimia', 'afm', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return ClientListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ClientCreateUpdateSerializer
        return ClientDetailSerializer

    def get_queryset(self):
        """Optimize queryset with counts to avoid N+1 queries"""
        queryset = super().get_queryset()

        # Add annotations for all actions to avoid N+1 queries in serializers
        queryset = queryset.annotate(
            _obligations_count=Count('monthly_obligations', distinct=True),
            _documents_count=Count('documents', distinct=True),
            _pending_obligations_count=Count(
                'monthly_obligations',
                filter=Q(monthly_obligations__status='pending'),
                distinct=True
            )
        )
        return queryset

    @action(detail=True, methods=['get'])
    def obligations(self, request, pk=None):
        """
        GET /api/clients/{id}/obligations/
        Returns all obligations for a specific client
        """
        client = self.get_object()
        obligations = client.monthly_obligations.select_related(
            'obligation_type'
        ).order_by('-year', '-month')

        # Optional filtering
        status_filter = request.query_params.get('status')
        year_filter = request.query_params.get('year')
        month_filter = request.query_params.get('month')

        if status_filter:
            obligations = obligations.filter(status=status_filter)
        if year_filter:
            obligations = obligations.filter(year=year_filter)
        if month_filter:
            obligations = obligations.filter(month=month_filter)

        serializer = ClientObligationNestedSerializer(obligations, many=True)
        return Response({
            'client_id': client.id,
            'client_name': client.eponimia,
            'total_count': obligations.count(),
            'obligations': serializer.data
        })

    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """
        GET /api/clients/{id}/documents/
        Returns all documents for a specific client
        """
        client = self.get_object()
        documents = client.documents.select_related(
            'obligation', 'obligation__obligation_type'
        ).order_by('-uploaded_at')

        # Optional filtering
        category = request.query_params.get('category')
        if category:
            documents = documents.filter(document_category=category)

        serializer = ClientDocumentSerializer(
            documents, many=True, context={'request': request}
        )
        return Response({
            'client_id': client.id,
            'client_name': client.eponimia,
            'total_count': documents.count(),
            'documents': serializer.data
        })

    @action(detail=True, methods=['post'], url_path='documents/upload')
    def upload_document(self, request, pk=None):
        """
        POST /api/clients/{id}/documents/upload/
        Upload a document for a specific client (multipart/form-data)
        """
        from django.core.exceptions import ValidationError as DjangoValidationError
        from common.utils.file_validation import validate_file_upload, sanitize_filename

        client = self.get_object()

        if 'file' not in request.FILES:
            return Response(
                {'error': 'Δεν βρέθηκε αρχείο.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES['file']

        # Use comprehensive file validation from common utilities
        try:
            validate_file_upload(uploaded_file)
        except DjangoValidationError as e:
            return Response(
                {'error': str(e.message) if hasattr(e, 'message') else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Sanitize filename to prevent directory traversal
        uploaded_file.name = sanitize_filename(uploaded_file.name)

        # Create document
        document = ClientDocument.objects.create(
            client=client,
            file=uploaded_file,
            document_category=request.data.get('category', 'general'),
            description=request.data.get('description', '')
        )

        # Link to obligation if provided
        obligation_id = request.data.get('obligation_id')
        if obligation_id:
            try:
                from .models import MonthlyObligation
                obligation = MonthlyObligation.objects.get(id=obligation_id, client=client)
                document.obligation = obligation
                document.save()
            except MonthlyObligation.DoesNotExist:
                pass

        serializer = ClientDocumentSerializer(document, context={'request': request})
        return Response({
            'message': 'Το αρχείο μεταφορτώθηκε επιτυχώς.',
            'document': serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='documents/(?P<doc_id>[^/.]+)/delete')
    def delete_document(self, request, pk=None, doc_id=None):
        """
        DELETE /api/clients/{id}/documents/{doc_id}/delete/
        Delete a specific document
        """
        import logging
        logger = logging.getLogger(__name__)

        client = self.get_object()

        try:
            document = ClientDocument.objects.get(id=doc_id, client=client)
        except ClientDocument.DoesNotExist:
            return Response(
                {'error': 'Το έγγραφο δεν βρέθηκε.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Delete file from storage
            if document.file:
                try:
                    document.file.delete(save=False)
                except Exception as file_error:
                    logger.warning(f"Could not delete file from storage: {file_error}")

            # Store filename for response
            filename = document.filename

            # Delete document (this will cascade delete related tags, favorites, etc.)
            document.delete()

            return Response({
                'message': f'Το έγγραφο "{filename}" διαγράφηκε επιτυχώς.'
            })
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return Response(
                {'error': f'Σφάλμα κατά τη διαγραφή: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def emails(self, request, pk=None):
        """
        GET /api/clients/{id}/emails/
        Returns all email logs for a specific client
        """
        from .models import EmailLog

        client = self.get_object()
        emails = EmailLog.objects.filter(client=client).order_by('-sent_at')

        # Pagination
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size

        total_count = emails.count()
        emails_page = emails[start:end]

        data = [{
            'id': email.id,
            'recipient_email': email.recipient_email,
            'subject': email.subject,
            'status': email.status,
            'status_display': email.get_status_display(),
            'sent_at': email.sent_at.isoformat() if email.sent_at else None,
            'template_name': email.template_used.name if email.template_used else None,
            'obligation_id': email.obligation_id,
        } for email in emails_page]

        return Response({
            'client_id': client.id,
            'client_name': client.eponimia,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'emails': data
        })

    @action(detail=True, methods=['get'])
    def calls(self, request, pk=None):
        """
        GET /api/clients/{id}/calls/
        Returns all VoIP calls for a specific client
        """
        from .models import VoIPCall

        client = self.get_object()
        calls = VoIPCall.objects.filter(client=client).order_by('-started_at')

        # Pagination
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size

        total_count = calls.count()
        calls_page = calls[start:end]

        data = [{
            'id': call.id,
            'call_id': call.call_id,
            'phone_number': call.phone_number,
            'direction': call.direction,
            'direction_display': call.get_direction_display(),
            'status': call.status,
            'status_display': call.get_status_display(),
            'started_at': call.started_at.isoformat() if call.started_at else None,
            'ended_at': call.ended_at.isoformat() if call.ended_at else None,
            'duration_seconds': call.duration_seconds,
            'duration_formatted': call.duration_formatted,
            'notes': call.notes,
            'resolution': call.resolution,
            'ticket_created': call.ticket_created,
        } for call in calls_page]

        return Response({
            'client_id': client.id,
            'client_name': client.eponimia,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'calls': data
        })

    @action(detail=True, methods=['get', 'post'])
    def tickets(self, request, pk=None):
        """
        GET /api/clients/{id}/tickets/ - List tickets for client
        POST /api/clients/{id}/tickets/ - Create new ticket for client
        """
        from .models import Ticket, VoIPCall

        client = self.get_object()

        if request.method == 'POST':
            # Create new ticket (manual, not from missed call)
            title = request.data.get('title')
            description = request.data.get('description', '')
            priority = request.data.get('priority', 'medium')

            if not title:
                return Response(
                    {'error': 'Απαιτείται τίτλος για το ticket.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create a dummy VoIPCall for manual ticket (required by model)
            from django.utils import timezone
            import uuid

            dummy_call = VoIPCall.objects.create(
                call_id=f'manual_{uuid.uuid4().hex[:8]}',
                phone_number=client.kinito_tilefono or 'N/A',
                direction='incoming',
                status='completed',
                started_at=timezone.now(),
                client=client,
                ticket_created=True
            )

            ticket = Ticket.objects.create(
                call=dummy_call,
                client=client,
                title=title,
                description=description,
                priority=priority,
                status='open'
            )

            return Response({
                'message': 'Το ticket δημιουργήθηκε επιτυχώς.',
                'ticket': {
                    'id': ticket.id,
                    'title': ticket.title,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'created_at': ticket.created_at.isoformat()
                }
            }, status=status.HTTP_201_CREATED)

        # GET - List tickets
        tickets = Ticket.objects.filter(client=client).order_by('-created_at')

        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            tickets = tickets.filter(status=status_filter)

        data = [{
            'id': ticket.id,
            'title': ticket.title,
            'description': ticket.description,
            'status': ticket.status,
            'status_display': ticket.get_status_display(),
            'priority': ticket.priority,
            'priority_display': ticket.get_priority_display(),
            'assigned_to': ticket.assigned_to_id,
            'assigned_to_name': ticket.assigned_to.username if ticket.assigned_to else None,
            'created_at': ticket.created_at.isoformat(),
            'resolved_at': ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            'is_open': ticket.is_open,
            'days_since_created': ticket.days_since_created,
        } for ticket in tickets]

        return Response({
            'client_id': client.id,
            'client_name': client.eponimia,
            'total_count': tickets.count(),
            'tickets': data
        })

    @action(detail=True, methods=['get'])
    def full(self, request, pk=None):
        """
        GET /api/clients/{id}/full/
        Returns complete client data with all related counts
        """
        from .models import EmailLog, VoIPCall, Ticket

        client = self.get_object()

        # Get counts
        obligations_count = client.monthly_obligations.count()
        pending_obligations = client.monthly_obligations.filter(status='pending').count()
        overdue_obligations = client.monthly_obligations.filter(status='overdue').count()
        documents_count = client.documents.count()
        emails_count = EmailLog.objects.filter(client=client).count()
        calls_count = VoIPCall.objects.filter(client=client).count()
        tickets_count = Ticket.objects.filter(client=client).count()
        open_tickets = Ticket.objects.filter(client=client, status__in=['open', 'assigned', 'in_progress']).count()

        serializer = ClientDetailSerializer(client, context={'request': request})

        return Response({
            **serializer.data,
            'counts': {
                'obligations': obligations_count,
                'pending_obligations': pending_obligations,
                'overdue_obligations': overdue_obligations,
                'documents': documents_count,
                'emails': emails_count,
                'calls': calls_count,
                'tickets': tickets_count,
                'open_tickets': open_tickets,
            }
        })
