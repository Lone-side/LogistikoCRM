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
        """Filter στο πεδίο year (έτος αναφοράς — συμφωνεί με τη δομή φακέλων)"""
        if value:
            return queryset.filter(year=int(value))
        return queryset

    def filter_month(self, queryset, name, value):
        """Filter στο πεδίο month (μήνας αναφοράς — συμφωνεί με τη δομή φακέλων)"""
        if value:
            return queryset.filter(month=int(value))
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
        read_only_fields = ['filename', 'file_type', 'uploaded_at']

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

    def validate_client_id(self, value):
        """Validate client exists"""
        try:
            ClientProfile.objects.get(id=value)
        except ClientProfile.DoesNotExist:
            raise serializers.ValidationError('Ο πελάτης δεν βρέθηκε.')
        return value

    def validate_obligation_id(self, value):
        """Validate obligation exists if provided"""
        if value:
            try:
                MonthlyObligation.objects.get(id=value)
            except MonthlyObligation.DoesNotExist:
                raise serializers.ValidationError('Η υποχρέωση δεν βρέθηκε.')
        return value


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
        'attach_to_obligation': ['accounting.change_clientdocument'],
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
        document = self.get_object()
        obligation_id = request.data.get('obligation_id')

        if not obligation_id:
            return Response(
                {'error': 'Απαιτείται obligation_id.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            obligation = MonthlyObligation.objects.get(id=obligation_id)
        except MonthlyObligation.DoesNotExist:
            return Response(
                {'error': 'Η υποχρέωση δεν βρέθηκε.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verify document belongs to same client
        if document.client_id != obligation.client_id:
            return Response(
                {'error': 'Το έγγραφο ανήκει σε διαφορετικό πελάτη.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        document.obligation = obligation
        document.save()

        serializer = DocumentSerializer(document, context={'request': request})
        return Response({
            'message': 'Το έγγραφο συνδέθηκε με την υποχρέωση.',
            'document': serializer.data
        })

    @action(detail=True, methods=['post'], url_path='detach-from-obligation')
    def detach_from_obligation(self, request, pk=None):
        """
        POST /api/v1/documents/{id}/detach-from-obligation/
        Remove document association with obligation
        """
        document = self.get_object()
        document.obligation = None
        document.save()

        serializer = DocumentSerializer(document, context={'request': request})
        return Response({
            'message': 'Η σύνδεση με την υποχρέωση αφαιρέθηκε.',
            'document': serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """Override delete to also remove file from storage"""
        document = self.get_object()

        # Delete file from storage
        if document.file:
            try:
                document.file.delete(save=False)
            except Exception:
                pass  # File might not exist

        document.delete()
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
    # Σύνδεση/upload εγγράφου = write: ο read-only ρόλος παίρνει 403
    if not check_model_perms(request, 'accounting.change_clientdocument'):
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

        # Verify same client
        if document.client_id != obligation.client_id:
            return Response(
                {'error': 'Το έγγραφο ανήκει σε διαφορετικό πελάτη.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        document.obligation = obligation
        document.save()

        serializer = DocumentSerializer(document, context={'request': request})
        return Response({
            'message': 'Το έγγραφο συνδέθηκε με την υποχρέωση.',
            'document': serializer.data
        })

    # Check if uploading new file
    if 'file' in request.FILES:
        uploaded_file = request.FILES['file']

        # Validate file
        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png']
        ext = os.path.splitext(uploaded_file.name)[1].lower()

        if ext not in allowed_extensions:
            return Response(
                {'error': f'Μη επιτρεπτός τύπος αρχείου. Επιτρέπονται: {", ".join(allowed_extensions)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if uploaded_file.size > 10 * 1024 * 1024:
            return Response(
                {'error': 'Το αρχείο είναι μεγαλύτερο από 10MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Determine category based on obligation type
        category = 'general'
        if obligation.obligation_type:
            type_code = obligation.obligation_type.code.upper()
            if 'ΦΠΑ' in type_code or 'VAT' in type_code:
                category = 'vat'
            elif 'ΜΥΦ' in type_code:
                category = 'myf'
            elif 'ΑΠΔ' in type_code:
                category = 'payroll'
            elif 'Ε1' in type_code or 'Ε3' in type_code:
                category = 'tax'

        # Create document
        document = ClientDocument.objects.create(
            client=obligation.client,
            obligation=obligation,
            file=uploaded_file,
            document_category=category,
            description=request.data.get('description', '')
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
    from accounting.services.access import get_accessible_obligation_or_404
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
