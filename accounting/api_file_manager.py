# -*- coding: utf-8 -*-
"""
accounting/api_file_manager.py
Author: Claude
Description: Comprehensive REST API for File Manager - documents, tags, sharing, collections

Endpoints:
  Documents:
    - GET    /api/v1/file-manager/documents/           - List with advanced filters
    - GET    /api/v1/file-manager/documents/{id}/      - Get single document
    - POST   /api/v1/file-manager/documents/upload/    - Upload single/multiple
    - DELETE /api/v1/file-manager/documents/{id}/      - Delete document
    - POST   /api/v1/file-manager/documents/bulk-delete/  - Bulk delete
    - GET    /api/v1/file-manager/documents/{id}/preview/ - Preview info
    - GET    /api/v1/file-manager/documents/{id}/download/ - Download file
    - GET    /api/v1/file-manager/documents/{id}/versions/ - Version history

  Tags:
    - GET/POST /api/v1/file-manager/tags/              - List/Create tags
    - PUT/DELETE /api/v1/file-manager/tags/{id}/       - Update/Delete tag
    - POST /api/v1/file-manager/documents/{id}/tags/   - Add tags to document
    - DELETE /api/v1/file-manager/documents/{id}/tags/{tag_id}/ - Remove tag

  Shared Links:
    - GET/POST /api/v1/file-manager/shared-links/      - List/Create
    - GET/PUT/DELETE /api/v1/file-manager/shared-links/{id}/ - CRUD
    - GET /api/v1/share/{token}/                       - Public access (no auth)

  Favorites:
    - GET    /api/v1/file-manager/favorites/           - List favorites
    - POST   /api/v1/file-manager/favorites/           - Add favorite
    - DELETE /api/v1/file-manager/favorites/{doc_id}/ - Remove favorite

  Collections:
    - GET/POST /api/v1/file-manager/collections/       - List/Create
    - GET/PUT/DELETE /api/v1/file-manager/collections/{id}/ - CRUD
    - POST /api/v1/file-manager/collections/{id}/documents/ - Add documents
    - DELETE /api/v1/file-manager/collections/{id}/documents/{doc_id}/ - Remove

  Dashboard/Stats:
    - GET /api/v1/file-manager/stats/                  - File statistics
    - GET /api/v1/file-manager/recent/                 - Recent documents
    - GET /api/v1/file-manager/browse/                 - Browse folder structure
"""

from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, NumberFilter, CharFilter, BooleanFilter
from django.db.models import Q, Count, Sum
from django.db.models.functions import TruncMonth
from django.http import FileResponse, Http404
from common.utils.media_tokens import signed_media_url
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
import logging
import os
import mimetypes

from .models import (
    ClientDocument, ClientProfile, MonthlyObligation,
    DocumentTag, DocumentTagAssignment, SharedLink, SharedLinkAccess,
    DocumentFavorite, DocumentCollection, get_client_folder
)

logger = logging.getLogger(__name__)


# ============================================
# PAGINATION
# ============================================

class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class LargePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


# ============================================
# FILTERS
# ============================================

class DocumentFilter(FilterSet):
    """Advanced filter for documents"""
    client_id = NumberFilter(field_name='client_id')
    client_afm = CharFilter(field_name='client__afm')
    obligation_id = NumberFilter(field_name='obligation_id')
    category = CharFilter(field_name='document_category')
    year = NumberFilter(field_name='year')
    month = NumberFilter(field_name='month')
    file_type = CharFilter(field_name='file_type')
    is_current = BooleanFilter(field_name='is_current')
    has_obligation = BooleanFilter(method='filter_has_obligation')
    search = CharFilter(method='filter_search')
    tag = CharFilter(method='filter_tag')
    date_from = CharFilter(method='filter_date_from')
    date_to = CharFilter(method='filter_date_to')

    class Meta:
        model = ClientDocument
        fields = ['client_id', 'obligation_id', 'category', 'year', 'month']

    def filter_has_obligation(self, queryset, name, value):
        if value:
            return queryset.exclude(obligation__isnull=True)
        return queryset.filter(obligation__isnull=True)

    def filter_search(self, queryset, name, value):
        if value:
            from .services.search import apply_document_search
            return apply_document_search(queryset, value, include_client_fields=True)
        return queryset

    def filter_tag(self, queryset, name, value):
        if value:
            return queryset.filter(tag_assignments__tag__name__iexact=value)
        return queryset

    def filter_date_from(self, queryset, name, value):
        if value:
            return queryset.filter(uploaded_at__date__gte=value)
        return queryset

    def filter_date_to(self, queryset, name, value):
        if value:
            return queryset.filter(uploaded_at__date__lte=value)
        return queryset


# ============================================
# SERIALIZERS
# ============================================

class DocumentTagSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentTag
        fields = ['id', 'name', 'color', 'icon', 'description', 'document_count', 'created_at']
        read_only_fields = ['created_at']

    def get_document_count(self, obj):
        return obj.document_assignments.count()


class DocumentTagAssignmentSerializer(serializers.ModelSerializer):
    tag = DocumentTagSerializer(read_only=True)
    tag_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = DocumentTagAssignment
        fields = ['id', 'tag', 'tag_id', 'assigned_at']


class DocumentSerializer(serializers.ModelSerializer):
    """Full document serializer with all relations"""
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    client_afm = serializers.CharField(source='client.afm', read_only=True)
    obligation_type = serializers.CharField(
        source='obligation.obligation_type.name',
        read_only=True,
        allow_null=True
    )
    obligation_period = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.CharField(read_only=True)
    category_display = serializers.CharField(source='get_document_category_display', read_only=True)
    tags = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    can_preview = serializers.SerializerMethodField()
    shared_links_count = serializers.SerializerMethodField()

    class Meta:
        model = ClientDocument
        fields = [
            'id', 'client', 'client_name', 'client_afm',
            'obligation', 'obligation_type', 'obligation_period',
            'file', 'file_url', 'filename', 'original_filename', 'file_type', 'file_size', 'file_size_display',
            'document_category', 'category_display', 'description',
            'year', 'month', 'version', 'is_current',
            'ocr_status', 'afm_mismatch',
            'uploaded_at', 'uploaded_by',
            'tags', 'is_favorite', 'can_preview', 'shared_links_count'
        ]
        read_only_fields = ['filename', 'file_type', 'file_size', 'uploaded_at', 'version']

    def get_file_url(self, obj):
        if obj.file:
            return signed_media_url(obj.file, self.context.get('request'))
        return None

    def get_obligation_period(self, obj):
        if obj.obligation:
            return f"{obj.obligation.month:02d}/{obj.obligation.year}"
        return f"{obj.month:02d}/{obj.year}" if obj.month and obj.year else None

    def get_tags(self, obj):
        assignments = obj.tag_assignments.select_related('tag').all()
        return [{'id': a.tag.id, 'name': a.tag.name, 'color': a.tag.color} for a in assignments]

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.favorited_by.filter(user=request.user).exists()
        return False

    def get_can_preview(self, obj):
        preview_types = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp']
        return obj.file_type.lower() in preview_types if obj.file_type else False

    def get_shared_links_count(self, obj):
        return obj.shared_links.filter(is_active=True).count()


class DocumentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for lists"""
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.CharField(read_only=True)
    category_display = serializers.CharField(source='get_document_category_display', read_only=True)
    tags = serializers.SerializerMethodField()

    class Meta:
        model = ClientDocument
        fields = [
            'id', 'client', 'client_name', 'obligation',
            'file_url', 'filename', 'file_type', 'file_size_display',
            'document_category', 'category_display',
            'year', 'month', 'version', 'is_current',
            'uploaded_at', 'tags'
        ]

    def get_file_url(self, obj):
        if obj.file:
            return signed_media_url(obj.file, self.context.get('request'))
        return None

    def get_tags(self, obj):
        assignments = obj.tag_assignments.select_related('tag').all()[:3]  # Limit for list view
        return [{'id': a.tag.id, 'name': a.tag.name, 'color': a.tag.color} for a in assignments]


class SharedLinkSerializer(serializers.ModelSerializer):
    document_filename = serializers.CharField(source='document.filename', read_only=True, allow_null=True)
    client_name = serializers.CharField(source='client.eponimia', read_only=True, allow_null=True)
    public_url = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)

    class Meta:
        model = SharedLink
        fields = [
            'id', 'document', 'document_filename', 'client', 'client_name',
            'token', 'name', 'access_level',
            'requires_email', 'expires_at', 'max_downloads',
            'allow_upload', 'upload_category', 'upload_note',
            'max_uploads', 'upload_count',
            'download_count', 'view_count', 'last_accessed_at',
            'is_active', 'is_expired', 'is_valid',
            'public_url', 'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['token', 'download_count', 'view_count', 'upload_count',
                            'last_accessed_at', 'created_at']

    def get_public_url(self, obj):
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/share/{obj.token}/')
        return f'/share/{obj.token}/'


class SharedLinkCreateSerializer(serializers.Serializer):
    """Serializer for creating shared links"""
    document_id = serializers.IntegerField(required=False, allow_null=True)
    client_id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    access_level = serializers.ChoiceField(choices=['view', 'download'], default='download')
    password = serializers.CharField(required=False, allow_blank=True, max_length=128)
    requires_email = serializers.BooleanField(default=False)
    expires_in_days = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=365)
    max_downloads = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    allow_upload = serializers.BooleanField(default=False)
    upload_category = serializers.CharField(required=False, allow_blank=True, max_length=20)
    upload_note = serializers.CharField(required=False, allow_blank=True)
    max_uploads = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, data):
        if not data.get('document_id') and not data.get('client_id'):
            raise serializers.ValidationError("Πρέπει να δοθεί document_id ή client_id")
        from .models import ClientDocument
        category = data.get('upload_category')
        if category and category not in dict(ClientDocument.CATEGORY_CHOICES):
            raise serializers.ValidationError(
                {'upload_category': 'Μη έγκυρη κατηγορία εγγράφων'}
            )
        return data


class DocumentFavoriteSerializer(serializers.ModelSerializer):
    document = DocumentListSerializer(read_only=True)

    class Meta:
        model = DocumentFavorite
        fields = ['id', 'document', 'note', 'created_at']


class DocumentCollectionSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(source='documents.count', read_only=True)
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    documents = DocumentListSerializer(many=True, read_only=True)

    class Meta:
        model = DocumentCollection
        fields = [
            'id', 'name', 'description', 'color', 'icon',
            'owner', 'owner_name', 'is_shared',
            'document_count', 'documents',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at']


class DocumentCollectionListSerializer(serializers.ModelSerializer):
    """Lightweight for list views"""
    document_count = serializers.IntegerField(source='documents.count', read_only=True)

    class Meta:
        model = DocumentCollection
        fields = ['id', 'name', 'description', 'color', 'icon', 'is_shared', 'document_count']


# ============================================
# DOCUMENT VIEWSET
# ============================================

class DocumentViewSet(viewsets.ModelViewSet):
    """
    Main ViewSet for document operations
    """
    queryset = ClientDocument.objects.filter(is_current=True)
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = DocumentFilter
    ordering_fields = ['uploaded_at', 'filename', 'file_size', 'year', 'month']
    ordering = ['-uploaded_at']
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        return super().get_queryset().select_related(
            'client', 'obligation', 'obligation__obligation_type', 'uploaded_by'
        ).prefetch_related('tag_assignments__tag')

    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentListSerializer
        return DocumentSerializer

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """
        Upload one or multiple documents
        Supports: file, client_id, obligation_id?, category?, description?, year?, month?
        """
        files = request.FILES.getlist('file') or request.FILES.getlist('files')
        if not files:
            return Response({'error': 'Δεν δόθηκε αρχείο'}, status=status.HTTP_400_BAD_REQUEST)

        client_id = request.data.get('client_id')
        if not client_id:
            return Response({'error': 'Απαιτείται client_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = ClientProfile.objects.get(id=client_id)
        except ClientProfile.DoesNotExist:
            return Response({'error': 'Ο πελάτης δεν βρέθηκε'}, status=status.HTTP_404_NOT_FOUND)

        obligation_id = request.data.get('obligation_id')
        obligation = None
        if obligation_id:
            try:
                obligation = MonthlyObligation.objects.get(id=obligation_id)
            except MonthlyObligation.DoesNotExist:
                return Response({'error': 'Η υποχρέωση δεν βρέθηκε'}, status=status.HTTP_404_NOT_FOUND)

        category = request.data.get('document_category', 'general')
        description = request.data.get('description', '')
        year = request.data.get('year')
        month = request.data.get('month')

        # Ενιαία διαδρομή αρχειοθέτησης (validation βάσει ρυθμίσεων + versioning)
        from django.core.exceptions import ValidationError
        from .services import filing

        uploaded_docs = []
        errors = []

        for f in files:
            try:
                doc = filing.create_client_document(
                    client=client,
                    uploaded_file=f,
                    category=category,
                    obligation=obligation,
                    year=year,
                    month=month,
                    user=request.user,
                    description=description,
                )
            except ValidationError as e:
                errors.append(f'{f.name}: {"; ".join(e.messages)}')
                continue
            uploaded_docs.append(doc)

        result_serializer = DocumentSerializer(uploaded_docs, many=True, context={'request': request})
        return Response({
            'message': f'Μεταφορτώθηκαν {len(uploaded_docs)} αρχεία',
            'uploaded': len(uploaded_docs),
            'errors': errors,
            'documents': result_serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='bulk-delete')
    def bulk_delete(self, request):
        """Delete multiple documents"""
        doc_ids = request.data.get('document_ids', [])
        if not doc_ids:
            return Response({'error': 'Δεν δόθηκαν document_ids'}, status=status.HTTP_400_BAD_REQUEST)

        deleted_count = 0
        for doc_id in doc_ids:
            try:
                doc = ClientDocument.objects.get(id=doc_id)
                if doc.file:
                    doc.file.delete(save=False)
                doc.delete()
                deleted_count += 1
            except ClientDocument.DoesNotExist:
                continue

        return Response({
            'message': f'Διαγράφηκαν {deleted_count} έγγραφα',
            'deleted_count': deleted_count
        })

    @action(detail=True, methods=['get'], url_path='preview')
    def preview(self, request, pk=None):
        """Get preview information for a document"""
        doc = self.get_object()
        preview_types = {
            'pdf': 'pdf',
            'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'gif': 'image', 'webp': 'image'
        }
        file_type = doc.file_type.lower() if doc.file_type else ''
        preview_type = preview_types.get(file_type, 'unknown')

        return Response({
            'id': doc.id,
            'filename': doc.filename,
            'file_type': doc.file_type,
            'preview_type': preview_type,
            'can_preview': preview_type != 'unknown',
            'url': signed_media_url(doc.file, request) if doc.file else None,
            'file_size': doc.file_size,
            'file_size_display': doc.file_size_display,
            'uploaded_at': doc.uploaded_at,
            'version': doc.version,
            'client_name': doc.client.eponimia
        })

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """Download the document file"""
        doc = self.get_object()
        if not doc.file:
            raise Http404("Το αρχείο δεν βρέθηκε")

        try:
            file_handle = doc.file.open('rb')
            response = FileResponse(file_handle, as_attachment=True, filename=doc.filename)
            content_type, _ = mimetypes.guess_type(doc.filename)
            if content_type:
                response['Content-Type'] = content_type
            return response
        except Exception:
            raise Http404("Σφάλμα κατά τη λήψη του αρχείου")

    @action(detail=True, methods=['get'], url_path='versions')
    def versions(self, request, pk=None):
        """Get all versions of a document"""
        doc = self.get_object()
        all_versions = doc.get_all_versions()
        serializer = DocumentSerializer(all_versions, many=True, context={'request': request})
        return Response({
            'document_id': doc.id,
            'current_version': doc.version,
            'total_versions': len(all_versions),
            'versions': serializer.data
        })

    @action(detail=True, methods=['post'], url_path='tags')
    def add_tags(self, request, pk=None):
        """Add tags to a document"""
        doc = self.get_object()
        tag_ids = request.data.get('tag_ids', [])

        added = []
        for tag_id in tag_ids:
            try:
                tag = DocumentTag.objects.get(id=tag_id)
                assignment, created = DocumentTagAssignment.objects.get_or_create(
                    document=doc,
                    tag=tag,
                    defaults={'assigned_by': request.user}
                )
                if created:
                    added.append(tag.name)
            except DocumentTag.DoesNotExist:
                continue

        return Response({
            'message': f'Προστέθηκαν {len(added)} ετικέτες',
            'added_tags': added
        })

    @action(detail=True, methods=['delete'], url_path='tags/(?P<tag_id>[^/.]+)')
    def remove_tag(self, request, pk=None, tag_id=None):
        """Remove a tag from a document"""
        doc = self.get_object()
        try:
            assignment = DocumentTagAssignment.objects.get(document=doc, tag_id=tag_id)
            tag_name = assignment.tag.name
            assignment.delete()
            return Response({'message': f'Αφαιρέθηκε η ετικέτα "{tag_name}"'})
        except DocumentTagAssignment.DoesNotExist:
            return Response({'error': 'Η ετικέτα δεν βρέθηκε'}, status=status.HTTP_404_NOT_FOUND)


# ============================================
# TAG VIEWSET
# ============================================

class TagViewSet(viewsets.ModelViewSet):
    """ViewSet for document tags"""
    queryset = DocumentTag.objects.all()
    serializer_class = DocumentTagSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering = ['name']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ============================================
# SHARED LINK VIEWSET
# ============================================

class SharedLinkViewSet(viewsets.ModelViewSet):
    """ViewSet for shared links management"""
    queryset = SharedLink.objects.all()
    serializer_class = SharedLinkSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'document', 'client', 'created_by'
        ).filter(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = SharedLinkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Get document or client
        document = None
        client = None
        if data.get('document_id'):
            document = get_object_or_404(ClientDocument, id=data['document_id'])
        elif data.get('client_id'):
            client = get_object_or_404(ClientProfile, id=data['client_id'])

        # Calculate expiration
        expires_at = None
        if data.get('expires_in_days'):
            expires_at = timezone.now() + timedelta(days=data['expires_in_days'])

        # Create shared link
        shared_link = SharedLink(
            document=document,
            client=client,
            name=data.get('name', ''),
            access_level=data.get('access_level', 'download'),
            requires_email=data.get('requires_email', False),
            expires_at=expires_at,
            max_downloads=data.get('max_downloads'),
            allow_upload=data.get('allow_upload', False),
            upload_category=data.get('upload_category', ''),
            upload_note=data.get('upload_note', ''),
            max_uploads=data.get('max_uploads'),
            created_by=request.user
        )

        # Set password if provided
        if data.get('password'):
            shared_link.set_password(data['password'])

        shared_link.save()

        result_serializer = SharedLinkSerializer(shared_link, context={'request': request})
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='regenerate-token')
    def regenerate_token(self, request, pk=None):
        """Generate a new token for the shared link"""
        shared_link = self.get_object()
        from .models import generate_share_token
        shared_link.token = generate_share_token()
        shared_link.save(update_fields=['token'])
        serializer = SharedLinkSerializer(shared_link, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='access-logs')
    def access_logs(self, request, pk=None):
        """Get access logs for a shared link"""
        shared_link = self.get_object()
        logs = shared_link.access_logs.all()[:50]
        return Response({
            'shared_link_id': shared_link.id,
            'total_views': shared_link.view_count,
            'total_downloads': shared_link.download_count,
            'logs': [{
                'accessed_at': log.accessed_at,
                'ip_address': log.ip_address,
                'action': log.action,
                'email_provided': log.email_provided
            } for log in logs]
        })


# ============================================
# PUBLIC SHARED LINK ACCESS (NO AUTH)
# ============================================

# Υπογεγραμμένο access token: εκδίδεται ΜΟΝΟ μετά από επιτυχή έλεγχο
# κωδικού/email και απαιτείται για download/upload σε προστατευμένα links
# (το download είναι GET από window.open — δεν μπορεί να ξαναστείλει κωδικό).
ACCESS_TOKEN_SALT = 'accounting.shared-link-access'
ACCESS_TOKEN_MAX_AGE = 4 * 3600  # 4 ώρες


def _password_fingerprint(shared_link):
    """Σύντομο αποτύπωμα του password_hash — αλλαγή κωδικού ακυρώνει τα tokens"""
    import hashlib
    return hashlib.sha256((shared_link.password_hash or '').encode()).hexdigest()[:16]


def make_shared_access_token(shared_link):
    from django.core import signing
    return signing.dumps(
        {'t': shared_link.token, 'p': _password_fingerprint(shared_link)},
        salt=ACCESS_TOKEN_SALT,
    )


def verify_shared_access_token(shared_link, token_value):
    from django.core import signing
    if not token_value:
        return False
    try:
        data = signing.loads(token_value, salt=ACCESS_TOKEN_SALT,
                             max_age=ACCESS_TOKEN_MAX_AGE)
    except signing.BadSignature:
        return False
    return (
        data.get('t') == shared_link.token
        and data.get('p') == _password_fingerprint(shared_link)
    )


def shared_link_auth_ok(shared_link, request):
    """
    Έλεγχος εξουσιοδότησης για ενέργεια σε προστατευμένο link:
    είτε έγκυρο υπογεγραμμένο access token, είτε σωστός κωδικός στο request.
    Τα links χωρίς κωδικό είναι πάντα OK.
    """
    if not shared_link.password_hash:
        return True
    token_value = request.query_params.get('auth') or request.data.get('auth')
    if verify_shared_access_token(shared_link, token_value):
        return True
    password = request.data.get('password', '')
    return bool(password) and shared_link.check_password(password)


class PublicSharedLinkView(APIView):
    """
    Public endpoint for accessing shared links
    GET /share/{token}/ - Get shared content info
    POST /share/{token}/ - Verify password/email if required
    GET /share/{token}/download/ - Download file
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        shared_link = get_object_or_404(SharedLink, token=token)

        # Check validity
        if not shared_link.is_active:
            return Response({'error': 'Ο σύνδεσμος δεν είναι ενεργός'}, status=status.HTTP_410_GONE)
        if shared_link.is_expired:
            return Response({'error': 'Ο σύνδεσμος έχει λήξει'}, status=status.HTTP_410_GONE)
        if shared_link.is_download_limit_reached:
            return Response({'error': 'Έχει φτάσει το όριο λήψεων'}, status=status.HTTP_410_GONE)

        # Check if password/email required
        needs_password = bool(shared_link.password_hash)
        needs_email = shared_link.requires_email

        if needs_password or needs_email:
            return Response({
                'requires_auth': True,
                'needs_password': needs_password,
                'needs_email': needs_email,
                'name': shared_link.name,
                'access_level': shared_link.access_level
            })

        # Record view access
        self._log_access(request, shared_link, 'view')
        shared_link.record_access(is_download=False)

        return self._get_content_response(request, shared_link)

    def post(self, request, token):
        """Verify password/email and return content"""
        shared_link = get_object_or_404(SharedLink, token=token)

        if not shared_link.is_valid:
            return Response({'error': 'Μη έγκυρος σύνδεσμος'}, status=status.HTTP_410_GONE)

        # Verify password if required
        if shared_link.password_hash:
            password = request.data.get('password', '')
            if not shared_link.check_password(password):
                return Response({'error': 'Λάθος κωδικός'}, status=status.HTTP_401_UNAUTHORIZED)

        # Verify email if required
        email = request.data.get('email', '')
        if shared_link.requires_email and not email:
            return Response({'error': 'Απαιτείται email'}, status=status.HTTP_400_BAD_REQUEST)

        # Log access
        self._log_access(request, shared_link, 'view', email)
        shared_link.record_access(is_download=False)

        return self._get_content_response(request, shared_link)

    def _get_content_response(self, request, shared_link):
        """Get the content based on link type"""
        # Access token για επόμενες ενέργειες (download/upload) χωρίς
        # επανάληψη κωδικού — εκδίδεται μόνο εδώ, μετά τον έλεγχο
        common = {
            'access_level': shared_link.access_level,
            'access_token': make_shared_access_token(shared_link),
            'allow_upload': shared_link.can_upload,
            'upload_note': shared_link.upload_note if shared_link.can_upload else '',
            'document_request': self._get_document_request(shared_link),
        }
        if shared_link.document:
            doc = shared_link.document
            return Response({
                'type': 'document',
                'name': shared_link.name,
                'document': {
                    'id': doc.id,
                    'filename': doc.filename,
                    'file_type': doc.file_type,
                    'file_size_display': doc.file_size_display,
                    'preview_url': signed_media_url(doc.file, request) if doc.file else None,
                    'can_download': shared_link.access_level == 'download'
                },
                **common,
            })
        elif shared_link.client:
            # Return list of client documents
            docs = ClientDocument.objects.filter(
                client=shared_link.client,
                is_current=True
            ).order_by('-uploaded_at')[:50]

            return Response({
                'type': 'folder',
                'name': shared_link.name,
                'client': {
                    'eponimia': shared_link.client.eponimia,
                    'afm': shared_link.client.afm
                },
                'documents': [{
                    'id': doc.id,
                    'filename': doc.filename,
                    'file_type': doc.file_type,
                    'file_size_display': doc.file_size_display,
                    'category': doc.get_document_category_display(),
                    'uploaded_at': doc.uploaded_at
                } for doc in docs],
                **common,
            })

    def _get_document_request(self, shared_link):
        """Το ανοιχτό αίτημα εγγράφων του link (ή None) — για το portal checklist."""
        if not shared_link.can_upload:
            return None
        doc_request = (
            shared_link.document_requests.filter(status='open')
            .prefetch_related('items')
            .first()
        )
        if not doc_request:
            return None
        return {
            'id': doc_request.id,
            'title': doc_request.title,
            'notes': doc_request.notes,
            'due_date': doc_request.due_date.isoformat() if doc_request.due_date else None,
            'items': [
                {
                    'id': item.id,
                    'label': item.label,
                    'category': item.category,
                    'is_received': item.is_received,
                }
                for item in doc_request.items.all()
            ],
        }

    def _log_access(self, request, shared_link, action, email=''):
        """Log access to shared link"""
        SharedLinkAccess.objects.create(
            shared_link=shared_link,
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            email_provided=email,
            action=action
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class PublicSharedLinkDownloadView(APIView):
    """Download endpoint for shared links"""
    permission_classes = [AllowAny]

    def get(self, request, token):
        shared_link = get_object_or_404(SharedLink, token=token)

        if not shared_link.is_valid:
            return Response({'error': 'Μη έγκυρος σύνδεσμος'}, status=status.HTTP_410_GONE)

        if shared_link.access_level != 'download':
            return Response({'error': 'Δεν επιτρέπεται η λήψη'}, status=status.HTTP_403_FORBIDDEN)

        # SECURITY: σε προστατευμένα links απαιτείται το access token που
        # εκδόθηκε μετά τον έλεγχο κωδικού — πριν, το download δεν έλεγχε
        # καθόλου τον κωδικό
        if shared_link.password_hash and not verify_shared_access_token(
            shared_link, request.query_params.get('auth')
        ):
            return Response({'error': 'Απαιτείται έλεγχος κωδικού'},
                            status=status.HTTP_401_UNAUTHORIZED)

        # Εύρεση αρχείου: document link ή folder link με ?doc_id=
        doc = shared_link.document
        if not doc and shared_link.client:
            doc_id = request.query_params.get('doc_id')
            if doc_id:
                doc = ClientDocument.objects.filter(
                    id=doc_id, client=shared_link.client, is_current=True
                ).first()
        if not doc or not doc.file:
            raise Http404("Το αρχείο δεν βρέθηκε")

        # Record download
        shared_link.record_access(is_download=True)

        # Log access
        SharedLinkAccess.objects.create(
            shared_link=shared_link,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            action='download'
        )

        try:
            file_handle = doc.file.open('rb')
            response = FileResponse(file_handle, as_attachment=True, filename=doc.filename)
            content_type, _ = mimetypes.guess_type(doc.filename)
            if content_type:
                response['Content-Type'] = content_type
            return response
        except Exception:
            raise Http404("Σφάλμα κατά τη λήψη")


class PublicSharedLinkUploadView(APIView):
    """
    Upload εγγράφων από τον πελάτη μέσω shared link (χωρίς login).

    POST /share/{token}/upload/ (multipart)
        - files: ένα ή περισσότερα αρχεία (μέχρι 10 ανά αίτημα)
        - auth: το access token από το GET/POST του link (για προστατευμένα)
        - email: αν το link απαιτεί email

    Τα αρχεία περνούν από την ενιαία υπηρεσία αρχειοθέτησης (validation
    βάσει ρυθμίσεων, αυτόματη ονομασία, φάκελος πελάτη, έλεγχος ΑΦΜ).
    """
    permission_classes = [AllowAny]
    throttle_scope = 'shared_link_upload'

    def get_throttles(self):
        from rest_framework.throttling import ScopedRateThrottle
        return [ScopedRateThrottle()]

    MAX_FILES_PER_REQUEST = 10

    def post(self, request, token):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from .services import filing

        shared_link = get_object_or_404(SharedLink, token=token)

        if not shared_link.can_upload:
            return Response(
                {'error': 'Ο σύνδεσμος δεν δέχεται μεταφορτώσεις'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not shared_link_auth_ok(shared_link, request):
            return Response({'error': 'Απαιτείται έλεγχος κωδικού'},
                            status=status.HTTP_401_UNAUTHORIZED)

        email = request.data.get('email', '')
        if shared_link.requires_email and not email:
            return Response({'error': 'Απαιτείται email'}, status=status.HTTP_400_BAD_REQUEST)

        client = shared_link.upload_target_client
        if not client:
            return Response({'error': 'Μη έγκυρος σύνδεσμος'}, status=status.HTTP_410_GONE)

        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        if not files:
            return Response({'error': 'Δεν επιλέχθηκε αρχείο'}, status=status.HTTP_400_BAD_REQUEST)
        if len(files) > self.MAX_FILES_PER_REQUEST:
            return Response(
                {'error': f'Μέχρι {self.MAX_FILES_PER_REQUEST} αρχεία ανά αποστολή'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Σεβασμός του ορίου uploads και μέσα στο ίδιο αίτημα
        if shared_link.max_uploads:
            remaining = shared_link.max_uploads - shared_link.upload_count
            if len(files) > remaining:
                return Response(
                    {'error': f'Απομένουν μόνο {remaining} διαθέσιμες μεταφορτώσεις'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Προαιρετική αντιστοίχιση σε item αιτήματος εγγράφων
        request_item = None
        request_item_id = request.data.get('request_item_id')
        if request_item_id:
            from .models import DocumentRequestItem
            request_item = DocumentRequestItem.objects.filter(
                pk=request_item_id,
                request__shared_link=shared_link,
                request__status='open',
                is_received=False,
            ).select_related('request').first()
            if request_item is None:
                return Response(
                    {'error': 'Μη έγκυρο ή ήδη παραληφθέν ζητούμενο έγγραφο'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        sender = email or 'πελάτη'
        uploaded = []
        uploaded_docs = []
        errors = []
        for f in files:
            try:
                # on_existing='keep': τα uploads πελατών δεν εκτοπίζουν ΠΟΤΕ
                # υπάρχοντα έγγραφα του γραφείου ως «νέα έκδοση»
                doc = filing.create_client_document(
                    client=client,
                    uploaded_file=f,
                    category=(
                        (request_item.category if request_item else '')
                        or shared_link.upload_category or 'general'
                    ),
                    user=None,
                    description=f'Μεταφόρτωση από {sender} μέσω portal',
                    on_existing='keep',
                )
            except DjangoValidationError as e:
                errors.append({'filename': f.name, 'error': '; '.join(e.messages)})
                continue
            entry = {
                'filename': doc.original_filename,
                'stored_as': doc.filename,
                'file_size_display': doc.file_size_display,
            }
            if doc.afm_mismatch:
                entry['warning'] = 'Το ΑΦΜ στο έγγραφο δεν αντιστοιχεί στον πελάτη'
            uploaded.append(entry)
            uploaded_docs.append(doc)

        if uploaded and request_item:
            self._mark_item_received(request_item, uploaded_docs[0])

        if uploaded:
            self._dispatch_upload_notification(shared_link, uploaded_docs)
            shared_link.record_upload(count=len(uploaded))
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = (
                x_forwarded_for.split(',')[0].strip()
                if x_forwarded_for else request.META.get('REMOTE_ADDR')
            )
            SharedLinkAccess.objects.create(
                shared_link=shared_link,
                ip_address=ip_address,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                email_provided=email,
                action='upload',
            )

        return Response({
            'success': bool(uploaded),
            'uploaded': uploaded,
            'errors': errors,
            'message': (
                f'Μεταφορτώθηκαν {len(uploaded)} αρχεία'
                if uploaded else 'Δεν μεταφορτώθηκε κανένα αρχείο'
            ),
        }, status=status.HTTP_201_CREATED if uploaded else status.HTTP_400_BAD_REQUEST)


    def _mark_item_received(self, request_item, document):
        """
        Race-safe παραλαβή item: conditional UPDATE — σε double-submit το
        δεύτερο update γυρίζει 0 rows και απλώς δεν ξαναμαρκάρει (το αρχείο
        έχει ανέβει κανονικά, δεν είναι σφάλμα για τον πελάτη).
        """
        from django.utils import timezone
        from .models import DocumentRequest, DocumentRequestItem

        updated = DocumentRequestItem.objects.filter(
            pk=request_item.pk, is_received=False
        ).update(
            is_received=True,
            received_document=document,
            received_at=timezone.now(),
        )
        if not updated:
            return
        # Auto-complete όταν δεν απομένει κανένα εκκρεμές item
        pending = DocumentRequestItem.objects.filter(
            request_id=request_item.request_id, is_received=False
        ).exists()
        if not pending:
            DocumentRequest.objects.filter(
                pk=request_item.request_id, status='open'
            ).update(status='completed', completed_at=timezone.now())

    def _dispatch_upload_notification(self, shared_link, documents):
        """Ειδοποίηση γραφείου για νέα έγγραφα — ποτέ δεν ρίχνει το upload."""
        from django.conf import settings as dj_settings
        from django.db import transaction

        doc_ids = [d.pk for d in documents]

        # Sync fallback χωρίς broker (runserver/tests) — ίδιο pattern με το OCR
        sync_mode = getattr(dj_settings, 'PORTAL_EMAIL_SYNC', dj_settings.DEBUG)

        def _send():
            from .tasks import notify_portal_upload
            try:
                notify_portal_upload.delay(shared_link.pk, doc_ids)
            except Exception:
                if sync_mode:
                    try:
                        notify_portal_upload(shared_link.pk, doc_ids)
                    except Exception:
                        logger.warning('notify_portal_upload sync fallback failed',
                                       exc_info=True)
                else:
                    logger.warning('notify_portal_upload dispatch failed', exc_info=True)

        transaction.on_commit(_send)


# ============================================
# FAVORITES VIEWSET
# ============================================

class FavoriteViewSet(viewsets.ViewSet):
    """ViewSet for user favorites"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List user's favorite documents"""
        favorites = DocumentFavorite.objects.filter(
            user=request.user
        ).select_related('document', 'document__client')

        serializer = DocumentFavoriteSerializer(favorites, many=True, context={'request': request})
        return Response(serializer.data)

    def create(self, request):
        """Add document to favorites"""
        document_id = request.data.get('document_id')
        note = request.data.get('note', '')

        if not document_id:
            return Response({'error': 'Απαιτείται document_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            document = ClientDocument.objects.get(id=document_id)
        except ClientDocument.DoesNotExist:
            return Response({'error': 'Το έγγραφο δεν βρέθηκε'}, status=status.HTTP_404_NOT_FOUND)

        favorite, created = DocumentFavorite.objects.get_or_create(
            user=request.user,
            document=document,
            defaults={'note': note}
        )

        if not created:
            return Response({'message': 'Το έγγραφο είναι ήδη στα αγαπημένα'})

        return Response({
            'message': 'Προστέθηκε στα αγαπημένα',
            'favorite_id': favorite.id
        }, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        """Remove document from favorites"""
        try:
            favorite = DocumentFavorite.objects.get(user=request.user, document_id=pk)
            favorite.delete()
            return Response({'message': 'Αφαιρέθηκε από τα αγαπημένα'})
        except DocumentFavorite.DoesNotExist:
            return Response({'error': 'Δεν βρέθηκε στα αγαπημένα'}, status=status.HTTP_404_NOT_FOUND)


# ============================================
# COLLECTION VIEWSET
# ============================================

class CollectionViewSet(viewsets.ModelViewSet):
    """ViewSet for document collections"""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        return DocumentCollection.objects.filter(
            Q(owner=self.request.user) | Q(is_shared=True)
        ).prefetch_related('documents')

    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentCollectionListSerializer
        return DocumentCollectionSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], url_path='documents')
    def add_documents(self, request, pk=None):
        """Add documents to collection"""
        collection = self.get_object()
        if collection.owner != request.user:
            return Response({'error': 'Δεν έχετε δικαίωμα επεξεργασίας'}, status=status.HTTP_403_FORBIDDEN)

        document_ids = request.data.get('document_ids', [])
        added = 0
        for doc_id in document_ids:
            try:
                doc = ClientDocument.objects.get(id=doc_id)
                collection.documents.add(doc)
                added += 1
            except ClientDocument.DoesNotExist:
                continue

        return Response({
            'message': f'Προστέθηκαν {added} έγγραφα',
            'added_count': added
        })

    @action(detail=True, methods=['delete'], url_path='documents/(?P<doc_id>[^/.]+)')
    def remove_document(self, request, pk=None, doc_id=None):
        """Remove document from collection"""
        collection = self.get_object()
        if collection.owner != request.user:
            return Response({'error': 'Δεν έχετε δικαίωμα επεξεργασίας'}, status=status.HTTP_403_FORBIDDEN)

        collection.documents.remove(doc_id)
        return Response({'message': 'Το έγγραφο αφαιρέθηκε'})


# ============================================
# DASHBOARD / STATS
# ============================================

class FileManagerStatsView(APIView):
    """Get file manager statistics"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Total documents
        total_docs = ClientDocument.objects.filter(is_current=True).count()

        # Size stats
        total_size = ClientDocument.objects.filter(is_current=True).aggregate(
            total=Sum('file_size'))['total'] or 0

        # By category
        by_category = ClientDocument.objects.filter(is_current=True).values(
            'document_category'
        ).annotate(count=Count('id')).order_by('-count')

        # By file type
        by_type = ClientDocument.objects.filter(is_current=True).values(
            'file_type'
        ).annotate(count=Count('id')).order_by('-count')[:10]

        # Recent uploads (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_count = ClientDocument.objects.filter(
            is_current=True,
            uploaded_at__gte=week_ago
        ).count()

        # Shared links
        active_links = SharedLink.objects.filter(is_active=True).count()

        # Favorites count for user
        favorites_count = DocumentFavorite.objects.filter(user=request.user).count()

        # Collections count for user
        collections_count = DocumentCollection.objects.filter(owner=request.user).count()

        return Response({
            'total_documents': total_docs,
            'total_size': total_size,
            'total_size_display': self._format_size(total_size),
            'recent_uploads_count': recent_count,
            'active_shared_links': active_links,
            'favorites_count': favorites_count,
            'collections_count': collections_count,
            'by_category': list(by_category),
            'by_file_type': list(by_type)
        })

    def _format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class RecentDocumentsView(APIView):
    """Get recent documents"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.query_params.get('limit', 20)), 50)

        recent = ClientDocument.objects.filter(is_current=True).select_related(
            'client', 'obligation', 'uploaded_by'
        ).order_by('-uploaded_at')[:limit]

        serializer = DocumentListSerializer(recent, many=True, context={'request': request})
        return Response(serializer.data)


class BrowseFoldersView(APIView):
    """Browse folder structure"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get distinct clients with documents
        clients_with_docs = ClientProfile.objects.filter(
            documents__isnull=False
        ).distinct().annotate(
            doc_count=Count('documents', filter=Q(documents__is_current=True))
        ).order_by('eponimia')

        client_id = request.query_params.get('client_id')
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        if client_id:
            # Get years for specific client
            client = get_object_or_404(ClientProfile, id=client_id)
            docs = ClientDocument.objects.filter(client=client, is_current=True)

            if year:
                docs = docs.filter(year=int(year))
                if month:
                    # Get documents for specific month
                    docs = docs.filter(month=int(month))
                    serializer = DocumentListSerializer(docs, many=True, context={'request': request})
                    return Response({
                        'type': 'documents',
                        'client': {'id': client.id, 'eponimia': client.eponimia},
                        'year': year,
                        'month': month,
                        'documents': serializer.data
                    })
                else:
                    # Get months for year
                    months = docs.values('month').annotate(
                        count=Count('id')
                    ).order_by('month')
                    return Response({
                        'type': 'months',
                        'client': {'id': client.id, 'eponimia': client.eponimia},
                        'year': year,
                        'months': list(months)
                    })
            else:
                # Get years
                years = docs.values('year').annotate(
                    count=Count('id')
                ).order_by('-year')
                return Response({
                    'type': 'years',
                    'client': {'id': client.id, 'eponimia': client.eponimia},
                    'years': list(years)
                })

        # Return client list
        return Response({
            'type': 'clients',
            'clients': [{
                'id': c.id,
                'eponimia': c.eponimia,
                'afm': c.afm,
                'document_count': c.doc_count
            } for c in clients_with_docs]
        })
