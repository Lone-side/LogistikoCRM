# -*- coding: utf-8 -*-
"""
accounting/api_documents.py
Author: Claude
Description: REST API for document management - upload, list, attach to obligations
"""

from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, NumberFilter, CharFilter
from django.db.models import Q
import os

from common.utils.media_tokens import signed_media_url
from .models import ClientDocument, ClientProfile, MonthlyObligation


class DocumentPagination(PageNumberPagination):
    """Pagination for document list"""
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class DocumentFilter(FilterSet):
    """Filter for ClientDocument"""
    client_id = NumberFilter(field_name='client_id')
    obligation_id = NumberFilter(field_name='obligation_id')
    category = CharFilter(field_name='document_category')
    year = CharFilter(method='filter_year')
    month = CharFilter(method='filter_month')
    search = CharFilter(method='filter_search')

    class Meta:
        model = ClientDocument
        fields = ['client_id', 'obligation_id', 'category']

    def filter_year(self, queryset, name, value):
        """Filter στο πεδίο year — άκυρη τιμή → 400 (όχι 500)."""
        if value:
            try:
                return queryset.filter(year=int(value))
            except (TypeError, ValueError):
                raise serializers.ValidationError({'year': 'Μη έγκυρο έτος.'})
        return queryset

    def filter_month(self, queryset, name, value):
        """Filter στο πεδίο month — άκυρη τιμή → 400 (όχι 500)."""
        if value:
            try:
                return queryset.filter(month=int(value))
            except (TypeError, ValueError):
                raise serializers.ValidationError({'month': 'Μη έγκυρος μήνας.'})
        return queryset

    def filter_search(self, queryset, name, value):
        """Search by filename or description"""
        if value:
            return queryset.filter(
                Q(filename__icontains=value) |
                Q(description__icontains=value)
            )
        return queryset


# ============================================
# DOCUMENT SERIALIZERS
# ============================================

class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for ClientDocument"""
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    client_afm = serializers.CharField(source='client.afm', read_only=True)
    obligation_type = serializers.CharField(
        source='obligation.obligation_type.name',
        read_only=True,
        allow_null=True
    )
    obligation_period = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    category_display = serializers.CharField(
        source='get_document_category_display',
        read_only=True
    )

    class Meta:
        model = ClientDocument
        fields = [
            'id', 'client', 'client_name', 'client_afm',
            'obligation', 'obligation_type', 'obligation_period',
            'file', 'file_url', 'filename', 'file_type', 'file_size',
            'document_category', 'category_display', 'description',
            'uploaded_at'
        ]
        # file: κάθε πραγματικό upload περνά ΜΟΝΟ από το filing service.
        # client/obligation/document_category: καθορίζουν ownership και
        # storage path — αλλαγή τους ΧΩΡΙΣ μετακίνηση αρχείου θα άφηνε
        # row/path mismatch. Attach/detach obligation ΜΟΝΟ μέσω των
        # dedicated actions (με τα δικά τους permissions/consistency checks).
        read_only_fields = ['file', 'client', 'obligation',
                            'document_category', 'filename', 'file_type',
                            'uploaded_at']

    def get_file_url(self, obj):
        if obj.file:
            return signed_media_url(obj.file, self.context.get('request'))
        return None

    def get_file_size(self, obj):
        """Return file size in bytes"""
        # Το αποθηκευμένο πεδίο αποφεύγει ένα stat() στο storage ανά έγγραφο
        if obj.file_size:
            return obj.file_size
        if obj.file:
            try:
                return obj.file.size
            except (OSError, FileNotFoundError):
                return None
        return None

    def get_obligation_period(self, obj):
        """Return obligation period as MM/YYYY"""
        if obj.obligation:
            return f"{obj.obligation.month:02d}/{obj.obligation.year}"
        return None


    def validate_client(self, client):
        """RBAC: το client FK δεν μπορεί να δείξει σε πελάτη εκτός ανάθεσης."""
        from accounting.services.access import user_can_access_client
        request = self.context.get('request')
        if request is not None and client is not None and \
                not user_can_access_client(request.user, client):
            raise serializers.ValidationError('Ο πελάτης δεν βρέθηκε.')
        return client

    def validate_obligation(self, obligation):
        """RBAC: το obligation FK μόνο σε προσβάσιμη υποχρέωση."""
        from accounting.services.access import user_can_access_client
        request = self.context.get('request')
        if request is not None and obligation is not None and \
                not user_can_access_client(request.user, obligation.client):
            raise serializers.ValidationError('Η υποχρέωση δεν βρέθηκε.')
        return obligation

    def validate(self, attrs):
        """
        Cross-model invariant στο generic create/update: το client δεν
        μπορεί να ζευγαρώσει με obligation/previous_version άλλου πελάτη.
        Merge με το instance για partial updates.
        """
        instance = getattr(self, 'instance', None)
        client = attrs.get('client', getattr(instance, 'client', None))
        obligation = attrs.get(
            'obligation', getattr(instance, 'obligation', None))
        previous = attrs.get(
            'previous_version', getattr(instance, 'previous_version', None))
        if client is not None and obligation is not None \
                and obligation.client_id != client.id:
            raise serializers.ValidationError(
                {'obligation': 'Η υποχρέωση ανήκει σε διαφορετικό πελάτη.'})
        if client is not None and previous is not None \
                and previous.client_id != client.id:
            raise serializers.ValidationError(
                {'previous_version': 'Η προηγούμενη έκδοση ανήκει σε '
                                     'διαφορετικό πελάτη.'})
        return attrs

class DocumentUploadSerializer(serializers.Serializer):
    """Serializer for document upload"""
    file = serializers.FileField()
    client_id = serializers.IntegerField()
    obligation_id = serializers.IntegerField(required=False, allow_null=True)
    document_category = serializers.ChoiceField(
        choices=[
            ('contracts', 'Συμβάσεις'),
            ('invoices', 'Τιμολόγια'),
            ('tax', 'Φορολογικά'),
            ('myf', 'ΜΥΦ'),
            ('vat', 'ΦΠΑ'),
            ('payroll', 'Μισθοδοσία'),
            ('general', 'Γενικά'),
        ],
        default='general'
    )
    description = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_file(self, value):
        """Validate file type and size"""
        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png']
        ext = os.path.splitext(value.name)[1].lower()

        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f'Μη επιτρεπτός τύπος αρχείου. Επιτρέπονται: {", ".join(allowed_extensions)}'
            )

        # Max 10MB
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('Το αρχείο είναι μεγαλύτερο από 10MB.')

        return value

    # ΟΧΙ global existence checks εδώ — η ύπαρξη+πρόσβαση κρίνονται scoped
    # στο view (get_accessible_client_or_404 / get_accessible_obligation_or_404)
    # ώστε ξένο και ανύπαρκτο ID να μη διακρίνονται (neutral 404).


# ============================================
# DOCUMENT VIEWSET
# ============================================

from .mixins import ClientScopedQuerysetMixin
from .permissions import CanAccessClient, ClientModelPermissions


class DocumentViewSet(ClientScopedQuerysetMixin, viewsets.ModelViewSet):
    """
    REST API ViewSet for ClientDocument

    Endpoints:
    - GET /api/v1/documents/ - List all documents (with filters)
    - GET /api/v1/documents/{id}/ - Get single document
    - POST /api/v1/documents/upload/ - Upload new document
    - DELETE /api/v1/documents/{id}/ - Delete document
    """
    queryset = ClientDocument.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, ClientModelPermissions, CanAccessClient]
    action_perms = {
        'attach_to_obligation': ['accounting.change_clientdocument',
                                 'accounting.view_monthlyobligation'],
        'detach_from_obligation': ['accounting.change_clientdocument'],
    }
    client_field = 'client__assigned_users'
    pagination_class = DocumentPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = DocumentFilter
    ordering_fields = ['uploaded_at', 'filename']
    ordering = ['-uploaded_at']
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        """Optimize queryset with select_related"""
        return super().get_queryset().select_related(
            'client', 'obligation', 'obligation__obligation_type'
        )

    def create(self, request, *args, **kwargs):
        """Generic POST απενεργοποιημένο: uploads ΜΟΝΟ μέσω /upload/ (filing)."""
        return Response(
            {'error': 'Χρησιμοποιήστε το /api/v1/documents/upload/ για '
                      'μεταφόρτωση εγγράφων.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # Πεδία που καθορίζουν ownership/storage path — ΔΕΝ αλλάζουν από
    # generic PUT/PATCH (μόνο descriptive metadata, π.χ. description)
    IMMUTABLE_UPDATE_FIELDS = ('file', 'client', 'obligation',
                               'document_category', 'previous_version',
                               'is_current', 'version', 'year', 'month')

    def update(self, request, *args, **kwargs):
        """Descriptive-metadata-only updates: file/ownership/path πεδία → 400."""
        blocked = [f for f in self.IMMUTABLE_UPDATE_FIELDS
                   if f in request.data]
        if blocked:
            return Response(
                {'error': 'Τα πεδία αρχείου/ιδιοκτησίας δεν αλλάζουν από '
                          'αυτό το endpoint — χρησιμοποιήστε τα dedicated '
                          'actions (upload-with-version, attach/detach).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """
        POST /api/v1/documents/upload/
        Upload a new document with multipart/form-data
        """
        serializer = DocumentUploadSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get validated data
        uploaded_file = serializer.validated_data['file']
        client_id = serializer.validated_data['client_id']
        obligation_id = serializer.validated_data.get('obligation_id')
        category = serializer.validated_data.get('document_category', 'general')
        description = serializer.validated_data.get('description', '')

        # Get client — μόνο ανατεθειμένος στον χρήστη (RBAC)
        from accounting.services.access import (
            get_accessible_client_or_404, get_accessible_obligation_or_404,
        )
        client = get_accessible_client_or_404(request.user, client_id, request=request)

        # Get obligation if provided
        obligation = None
        if obligation_id:
            obligation = get_accessible_obligation_or_404(
                request.user, obligation_id, request=request
            )
            if obligation.client_id != client.id:
                return Response(
                    {'error': 'Η υποχρέωση ανήκει σε διαφορετικό πελάτη.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Auto-set category based on obligation type if not specified
            if category == 'general' and obligation.obligation_type:
                type_code = obligation.obligation_type.code.upper()
                if 'ΦΠΑ' in type_code or 'VAT' in type_code:
                    category = 'vat'
                elif 'ΜΥΦ' in type_code:
                    category = 'myf'
                elif 'ΑΠΔ' in type_code or 'PAYROLL' in type_code:
                    category = 'payroll'
                elif 'Ε1' in type_code or 'Ε3' in type_code:
                    category = 'tax'

        # Create document (ενιαία διαδρομή: validation βάσει ρυθμίσεων + versioning)
        from django.core.exceptions import ValidationError
        from .services import filing

        try:
            document = filing.create_client_document(
                client=client,
                uploaded_file=uploaded_file,
                category=category,
                obligation=obligation,
                user=request.user,
                description=description,
            )
        except ValidationError as e:
            return Response({'error': '; '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        result_serializer = DocumentSerializer(document, context={'request': request})
        return Response({
            'message': 'Το αρχείο μεταφορτώθηκε επιτυχώς.',
            'document': result_serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='attach-to-obligation')
    def attach_to_obligation(self, request, pk=None):
        """
        POST /api/v1/documents/{id}/attach-to-obligation/
        Attach an existing document to an obligation

        Body: { "obligation_id": 123 }
        """
        from django.http import Http404
        from accounting.services.access import get_accessible_obligation_or_404
        document = self.get_object()
        obligation_id = request.data.get('obligation_id')

        if not obligation_id:
            return Response(
                {'error': 'Απαιτείται obligation_id.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Scoped resolution: ξένη και ανύπαρκτη υποχρέωση → ίδιο ουδέτερο 404
        obligation = get_accessible_obligation_or_404(
            request.user, obligation_id, request=request
        )

        # Invariant: το έγγραφο και η υποχρέωση πρέπει να είναι ίδιου πελάτη.
        # (Το document είναι ήδη scoped από το get_object.) Ασυμφωνία →
        # ουδέτερο 404 ώστε να μη διακρίνεται από «δεν βρέθηκε».
        if document.client_id != obligation.client_id:
            raise Http404

        # Κοινό transactional service: validation → perms → locks →
        # exact target-key conflict (fail closed) → mutation → audit
        from django.core.exceptions import ValidationError
        from .services import filing
        try:
            filing.attach_document_service(request.user, document, obligation)
        except filing.DocumentKeyConflict as e:
            return Response({'error': e.message},
                            status=status.HTTP_409_CONFLICT)
        except ValidationError as e:
            return Response({'error': '; '.join(e.messages)},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = DocumentSerializer(document, context={'request': request})
        return Response({
            'message': 'Το έγγραφο συνδέθηκε με την υποχρέωση.',
            'document': serializer.data
        })

    @action(detail=True, methods=['post'], url_path='detach-from-obligation')
    def detach_from_obligation(self, request, pk=None):
        """
        POST /api/v1/documents/{id}/detach-from-obligation/
        Remove document association with obligation (κοινό service)
        """
        from django.core.exceptions import ValidationError
        from .services import filing
        document = self.get_object()
        try:
            filing.detach_document_service(request.user, document)
        except filing.DocumentKeyConflict as e:
            return Response({'error': e.message},
                            status=status.HTTP_409_CONFLICT)
        except ValidationError as e:
            return Response({'error': '; '.join(e.messages)},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = DocumentSerializer(document, context={'request': request})
        return Response({
            'message': 'Η σύνδεση με την υποχρέωση αφαιρέθηκε.',
            'document': serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """
        Διαγραφή μέσω delete_document_service: πολιτική versioned deletion
        (descendants → 400, current → προαγωγή προηγούμενης), DB πρώτα,
        αρχείο μόνο on_commit.
        """
        from django.core.exceptions import ValidationError
        from .services import filing

        document = self.get_object()
        try:
            filing.delete_document_service(request.user, document)
        except ValidationError as e:
            return Response({'error': '; '.join(e.messages)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'Το έγγραφο διαγράφηκε επιτυχώς.'})


# ============================================
# OBLIGATION DOCUMENT ENDPOINTS
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def attach_document_to_obligation(request, obligation_id):
    """
    POST /api/v1/obligations/{id}/attach-document/
    Attach existing document or upload new one to obligation

    Body options:
    1. Attach existing: { "document_id": 123 }
    2. Upload new: multipart/form-data with 'file' and optional 'description'
    """
    from django.http import Http404
    from accounting.services.access import (
        get_accessible_obligation_or_404, get_accessible_document_or_404,
        check_model_perms,
    )
    # Σύνδεση υπάρχοντος = change, upload νέου αρχείου = add
    required_perm = (
        'accounting.change_clientdocument'
        if request.data.get('document_id')
        else 'accounting.add_clientdocument'
    )
    if not check_model_perms(request, required_perm):
        return Response(
            {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        obligation = get_accessible_obligation_or_404(
            request.user, obligation_id, request=request
        )
    except Http404:
        return Response(
            {'error': 'Η υποχρέωση δεν βρέθηκε.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Check if attaching existing document
    document_id = request.data.get('document_id')
    if document_id:
        try:
            document = get_accessible_document_or_404(
                request.user, document_id, request=request
            )
        except Http404:
            return Response(
                {'error': 'Το έγγραφο δεν βρέθηκε.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Κοινό transactional service — ίδια πολιτική με το ViewSet action
        from django.core.exceptions import ValidationError
        from .services import filing as _filing
        try:
            _filing.attach_document_service(request.user, document, obligation)
        except _filing.DocumentKeyConflict as e:
            return Response({'error': e.message},
                            status=status.HTTP_409_CONFLICT)
        except ValidationError as e:
            return Response({'error': '; '.join(e.messages)},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = DocumentSerializer(document, context={'request': request})
        return Response({
            'message': 'Το έγγραφο συνδέθηκε με την υποχρέωση.',
            'document': serializer.data
        })

    # Check if uploading new file — ΠΑΝΤΑ μέσω filing service (validation
    # βάσει ρυθμίσεων, dangerous-content check, ονομασία, versioning)
    if 'file' in request.FILES:
        from django.core.exceptions import ValidationError
        from .services import filing

        try:
            document = filing.create_client_document(
                client=obligation.client,
                obligation=obligation,
                uploaded_file=request.FILES['file'],
                user=request.user,
                description=request.data.get('description', ''),
            )
        except ValidationError as e:
            return Response(
                {'error': '; '.join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DocumentSerializer(document, context={'request': request})
        return Response({
            'message': 'Το αρχείο μεταφορτώθηκε και συνδέθηκε με την υποχρέωση.',
            'document': serializer.data
        }, status=status.HTTP_201_CREATED)

    return Response(
        {'error': 'Απαιτείται document_id ή αρχείο.'},
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obligation_documents(request, obligation_id):
    """
    GET /api/v1/obligations/{id}/documents/
    List all documents attached to an obligation
    """
    from django.http import Http404
    from accounting.services.access import (
        check_model_perms, get_accessible_obligation_or_404,
    )
    # Model permissions ΠΡΙΝ από κάθε ανάκτηση: επιστρέφει στοιχεία
    # υποχρέωσης ΚΑΙ εγγράφων (με signed URLs)
    if not check_model_perms(request, 'accounting.view_monthlyobligation',
                             'accounting.view_clientdocument'):
        return Response(
            {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        obligation = get_accessible_obligation_or_404(
            request.user, obligation_id, request=request
        )
    except Http404:
        return Response(
            {'error': 'Η υποχρέωση δεν βρέθηκε.'},
            status=status.HTTP_404_NOT_FOUND
        )

    documents = ClientDocument.objects.filter(obligation=obligation).order_by('-uploaded_at')
    serializer = DocumentSerializer(documents, many=True, context={'request': request})

    return Response({
        'obligation_id': obligation_id,
        'client_id': obligation.client_id,
        'client_name': obligation.client.eponimia,
        'obligation_type': obligation.obligation_type.name if obligation.obligation_type else None,
        'period': f"{obligation.month:02d}/{obligation.year}",
        'count': documents.count(),
        'documents': serializer.data
    })
