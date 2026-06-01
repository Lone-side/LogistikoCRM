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

from .models import ClientDocument, ClientProfile, MonthlyObligation
from .portal_mixins import ClientScopedQuerysetMixin


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
        """Filter by year in uploaded_at"""
        if value:
            return queryset.filter(uploaded_at__year=int(value))
        return queryset

    def filter_month(self, queryset, name, value):
        """Filter by month in uploaded_at"""
        if value:
            return queryset.filter(uploaded_at__month=int(value))
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
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_size(self, obj):
        """Return file size in bytes"""
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
    permission_classes = [IsAuthenticated]
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

        # Get client
        client = ClientProfile.objects.get(id=client_id)

        # Get obligation if provided
        obligation = None
        if obligation_id:
            obligation = MonthlyObligation.objects.get(id=obligation_id)
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

        # Create document
        document = ClientDocument.objects.create(
            client=client,
            obligation=obligation,
            file=uploaded_file,
            document_category=category,
            description=description
        )

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
    try:
        obligation = MonthlyObligation.objects.get(id=obligation_id)
    except MonthlyObligation.DoesNotExist:
        return Response(
            {'error': 'Η υποχρέωση δεν βρέθηκε.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Check if attaching existing document
    document_id = request.data.get('document_id')
    if document_id:
        try:
            document = ClientDocument.objects.get(id=document_id)
        except ClientDocument.DoesNotExist:
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
    try:
        obligation = MonthlyObligation.objects.get(id=obligation_id)
    except MonthlyObligation.DoesNotExist:
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
