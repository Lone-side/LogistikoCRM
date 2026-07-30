# -*- coding: utf-8 -*-
"""
accounting/api_document_requests.py

API για Αιτήματα Εγγράφων (DocumentRequest): ο λογιστής ζητά συγκεκριμένα
έγγραφα από πελάτη μέσω portal link, με tracking και υπενθυμίσεις.

Ορατότητα: ΟΛΟΚΛΗΡΟ το γραφείο (όχι creator-scoped όπως το SharedLinkViewSet)
— τα αιτήματα είναι κοινή δουλειά, όπως οι υποχρεώσεις. Η διαχείριση του
nested link (διαγραφή/regenerate) παραμένει στον δημιουργό του.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    ClientDocument, ClientProfile, DocumentRequest, DocumentRequestItem,
    SharedLink,
)

logger = logging.getLogger(__name__)

# Anti-double-click για τη χειροκίνητη υπενθύμιση
MANUAL_REMINDER_COOLDOWN = timedelta(hours=1)


# ============================================
# SERIALIZERS
# ============================================

class DocumentRequestItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentRequestItem
        fields = ['id', 'label', 'category', 'is_received', 'received_at',
                  'received_document']
        read_only_fields = ['is_received', 'received_at', 'received_document']


class SharedLinkSummarySerializer(serializers.ModelSerializer):
    """Read-only σύνοψη link — ΔΕΝ εκθέτει διαχείριση σε μη-creators."""
    public_url = serializers.SerializerMethodField()
    is_valid = serializers.BooleanField(read_only=True)
    can_upload = serializers.BooleanField(read_only=True)

    class Meta:
        model = SharedLink
        fields = ['id', 'token', 'public_url', 'expires_at', 'is_valid',
                  'can_upload', 'upload_count', 'max_uploads']

    def get_public_url(self, obj):
        return f'/share/{obj.token}/'


class DocumentRequestSerializer(serializers.ModelSerializer):
    items = DocumentRequestItemSerializer(many=True, read_only=True)
    shared_link = SharedLinkSummarySerializer(read_only=True)
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    client_afm = serializers.CharField(source='client.afm', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    received_count = serializers.IntegerField(
        source='received_items_count', read_only=True
    )
    total_count = serializers.SerializerMethodField()
    max_reminders = serializers.SerializerMethodField()

    class Meta:
        model = DocumentRequest
        fields = [
            'id', 'client', 'client_name', 'client_afm', 'shared_link',
            'title', 'notes', 'status', 'due_date',
            'items', 'received_count', 'total_count',
            'last_reminder_sent_at', 'reminder_count', 'max_reminders',
            'completed_at', 'created_by', 'created_by_name', 'created_at',
        ]
        read_only_fields = [
            'client', 'shared_link', 'last_reminder_sent_at', 'reminder_count',
            'completed_at', 'created_by', 'created_at',
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_total_count(self, obj):
        return obj.items.count()

    def get_max_reminders(self, obj):
        from .tasks import DOCUMENT_REQUEST_MAX_REMINDERS
        return DOCUMENT_REQUEST_MAX_REMINDERS


class DocumentRequestCreateSerializer(serializers.Serializer):
    client_id = serializers.IntegerField()
    title = serializers.CharField(max_length=200)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    due_date = serializers.DateField(required=False, allow_null=True, default=None)
    items = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=30
    )
    # Link options
    expires_in_days = serializers.IntegerField(
        required=False, min_value=1, max_value=365, default=30
    )
    password = serializers.CharField(required=False, allow_blank=True, default='')
    send_email = serializers.BooleanField(required=False, default=True)

    def validate_client_id(self, value):
        if not ClientProfile.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Ο πελάτης δεν βρέθηκε')
        return value

    def validate_items(self, value):
        valid_categories = dict(ClientDocument.CATEGORY_CHOICES)
        cleaned = []
        for raw in value:
            label = (raw.get('label') or '').strip()
            if not label:
                raise serializers.ValidationError('Κάθε ζητούμενο έγγραφο χρειάζεται περιγραφή')
            category = (raw.get('category') or '').strip()
            if category and category not in valid_categories:
                raise serializers.ValidationError(f'Άγνωστη κατηγορία: {category}')
            cleaned.append({'label': label[:200], 'category': category})
        return cleaned


# ============================================
# VIEWSET
# ============================================

class DocumentRequestViewSet(viewsets.ModelViewSet):
    """
    /api/v1/document-requests/
    Create: φτιάχνει αίτημα + SharedLink (allow_upload) + αρχικό email.
    Actions: send-reminder, mark-item.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentRequestSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = (
            DocumentRequest.objects
            .select_related('client', 'shared_link', 'created_by')
            .prefetch_related('items')
        )
        client_id = self.request.query_params.get('client')
        if client_id and client_id.isdigit():
            qs = qs.filter(client_id=int(client_id))
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = DocumentRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client = ClientProfile.objects.get(pk=data['client_id'])

        with transaction.atomic():
            shared_link = SharedLink(
                client=client,
                name=data['title'][:200],
                access_level='view',
                allow_upload=True,
                max_uploads=100,
                expires_at=timezone.now() + timedelta(days=data['expires_in_days']),
                created_by=request.user,
            )
            if data['password']:
                shared_link.set_password(data['password'])
            shared_link.save()

            doc_request = DocumentRequest.objects.create(
                client=client,
                shared_link=shared_link,
                title=data['title'],
                notes=data['notes'],
                due_date=data['due_date'],
                created_by=request.user,
            )
            DocumentRequestItem.objects.bulk_create([
                DocumentRequestItem(
                    request=doc_request,
                    label=item['label'],
                    category=item['category'],
                )
                for item in data['items']
            ])

        email_scheduled = False
        if data['send_email'] and (client.email or '').strip():
            self._dispatch_initial_email(doc_request.pk)
            email_scheduled = True

        output = DocumentRequestSerializer(
            self.get_queryset().get(pk=doc_request.pk)
        )
        return Response(
            {**output.data, 'email_sent': email_scheduled},
            status=status.HTTP_201_CREATED,
        )

    def _dispatch_initial_email(self, request_id):
        """on_commit ώστε ο worker να βλέπει τα νέα rows· sync fallback σε DEBUG."""
        from django.conf import settings as dj_settings
        from .tasks import send_document_request_email

        sync_mode = getattr(dj_settings, 'PORTAL_EMAIL_SYNC', dj_settings.DEBUG)

        def _send():
            try:
                send_document_request_email.delay(request_id)
            except Exception:
                if sync_mode:
                    try:
                        send_document_request_email(request_id)
                    except Exception:
                        logger.warning('Initial request email failed', exc_info=True)
                else:
                    logger.warning('Initial request email dispatch failed', exc_info=True)

        transaction.on_commit(_send)

    @action(detail=True, methods=['post'], url_path='send-reminder')
    def send_reminder(self, request, pk=None):
        """Χειροκίνητη υπενθύμιση — αγνοεί το MAX αλλά έχει cooldown 1 ώρας."""
        from django.db.models import F
        from .tasks import _send_document_request_email

        doc_request = self.get_object()
        if doc_request.status != 'open':
            return Response(
                {'error': 'Το αίτημα δεν είναι ανοιχτό'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not doc_request.items.filter(is_received=False).exists():
            return Response(
                {'error': 'Δεν υπάρχουν εκκρεμή έγγραφα'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (doc_request.last_reminder_sent_at and
                timezone.now() - doc_request.last_reminder_sent_at < MANUAL_REMINDER_COOLDOWN):
            return Response(
                {'error': 'Στάλθηκε υπενθύμιση πριν από λιγότερο από 1 ώρα'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (doc_request.client.email or '').strip():
            return Response(
                {'error': 'Ο πελάτης δεν έχει email'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        link = doc_request.shared_link
        if link is None or not link.is_valid or not link.can_upload:
            return Response(
                {'error': 'Ο σύνδεσμος portal έχει λήξει ή απενεργοποιηθεί — '
                          'δημιούργησε νέο αίτημα'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sent = _send_document_request_email(doc_request)
        except Exception as e:
            logger.error(f'Manual reminder failed for request {pk}: {e}')
            return Response(
                {'error': 'Αποτυχία αποστολής email'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        if not sent:
            return Response(
                {'error': 'Το email δεν στάλθηκε — έλεγξε email πελάτη και σύνδεσμο'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        DocumentRequest.objects.filter(pk=doc_request.pk).update(
            last_reminder_sent_at=timezone.now(),
            reminder_count=F('reminder_count') + 1,
        )
        return Response({'success': True, 'message': 'Η υπενθύμιση στάλθηκε'})

    @action(detail=True, methods=['post'], url_path='mark-item')
    def mark_item(self, request, pk=None):
        """Χειροκίνητο μαρκάρισμα item (π.χ. το έγγραφο ήρθε δια ζώσης)."""
        doc_request = self.get_object()
        item_id = request.data.get('item_id')
        is_received = bool(request.data.get('is_received', True))

        item = doc_request.items.filter(pk=item_id).first()
        if item is None:
            return Response(
                {'error': 'Το ζητούμενο έγγραφο δεν βρέθηκε'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if is_received:
            DocumentRequestItem.objects.filter(pk=item.pk).update(
                is_received=True, received_at=timezone.now()
            )
            if not doc_request.items.filter(is_received=False).exists():
                DocumentRequest.objects.filter(
                    pk=doc_request.pk, status='open'
                ).update(status='completed', completed_at=timezone.now())
        else:
            DocumentRequestItem.objects.filter(pk=item.pk).update(
                is_received=False, received_at=None, received_document=None
            )
            # Αν είχε ολοκληρωθεί, ξανανοίγει
            DocumentRequest.objects.filter(
                pk=doc_request.pk, status='completed'
            ).update(status='open', completed_at=None)

        return Response(
            DocumentRequestSerializer(self.get_queryset().get(pk=doc_request.pk)).data
        )
