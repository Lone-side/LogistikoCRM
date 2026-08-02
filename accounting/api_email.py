# -*- coding: utf-8 -*-
"""
accounting/api_email.py
Author: Claude
Description: REST API for email sending - templates, send, obligation notifications
"""

from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

from .models import (
    ClientProfile, MonthlyObligation, EmailTemplate, EmailLog, ClientDocument,
    EmailSettings
)
from .services.email_service import EmailService
from .services.access import (
    accessible_clients, accessible_obligations, check_model_perms,
    require_model_perms,
)

PERM_DENIED = {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'}


# ============================================
# EMAIL SERIALIZERS
# ============================================

class EmailTemplateSerializer(serializers.ModelSerializer):
    """Serializer for EmailTemplate"""
    obligation_type_name = serializers.CharField(
        source='obligation_type.name',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'name', 'description', 'subject', 'body_html',
            'obligation_type', 'obligation_type_name',
            'is_active', 'created_at', 'updated_at'
        ]


class EmailLogSerializer(serializers.ModelSerializer):
    """Serializer for EmailLog"""
    template_name = serializers.CharField(
        source='template_used.name',
        read_only=True,
        allow_null=True
    )
    client_name = serializers.CharField(
        source='client.onoma',
        read_only=True,
        allow_null=True
    )
    client_afm = serializers.CharField(
        source='client.afm',
        read_only=True,
        allow_null=True
    )
    obligation_type = serializers.CharField(
        source='obligation.obligation_type.name',
        read_only=True,
        allow_null=True
    )
    sent_by_name = serializers.CharField(
        source='sent_by.get_full_name',
        read_only=True,
        allow_null=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )

    class Meta:
        model = EmailLog
        fields = [
            'id', 'recipient_email', 'recipient_name',
            'client', 'client_name', 'client_afm',
            'obligation', 'obligation_type',
            'template_used', 'template_name',
            'subject', 'body', 'status', 'status_display', 'error_message',
            'sent_at', 'sent_by', 'sent_by_name'
        ]


class SendEmailSerializer(serializers.Serializer):
    """Serializer for sending email"""
    client_id = serializers.IntegerField()
    subject = serializers.CharField(max_length=500)
    body = serializers.CharField()
    template_id = serializers.IntegerField(required=False, allow_null=True)
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )

    def validate_client_id(self, value):
        # Χωρίς global lookup εδώ — θα αποκάλυπτε την ύπαρξη ξένου πελάτη.
        # Το scoped fetch + έλεγχος email γίνεται στο view (404 αν εκτός ανάθεσης).
        return value

    def validate_template_id(self, value):
        if value:
            try:
                EmailTemplate.objects.get(id=value, is_active=True)
            except EmailTemplate.DoesNotExist:
                raise serializers.ValidationError('Το πρότυπο email δεν βρέθηκε.')
        return value


class SendObligationNoticeSerializer(serializers.Serializer):
    """Serializer for sending obligation notice"""
    obligation_id = serializers.IntegerField()
    template_type = serializers.ChoiceField(
        choices=['reminder', 'completion', 'overdue'],
        default='completion'
    )
    template_id = serializers.IntegerField(required=False, allow_null=True)
    include_attachment = serializers.BooleanField(default=True)
    attachment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )

    def validate_obligation_id(self, value):
        # Χωρίς global lookup — scoped έλεγχος στο view (404 αν εκτός ανάθεσης)
        return value


class CompleteAndNotifySerializer(serializers.Serializer):
    """Serializer for complete obligation and send notification"""
    document_id = serializers.IntegerField(required=False, allow_null=True)
    file = serializers.FileField(required=False, allow_null=True)
    save_to_client_folder = serializers.BooleanField(default=True)
    send_email = serializers.BooleanField(default=False)
    attach_to_email = serializers.BooleanField(default=False)
    email_template_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    time_spent = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )


class BulkCompleteNotifySerializer(serializers.Serializer):
    """Serializer for bulk complete with notification"""
    obligation_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    send_notifications = serializers.BooleanField(default=False)


# ============================================
# EMAIL TEMPLATE ENDPOINTS
# ============================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def email_templates(request):
    """
    GET /api/v1/email/templates/
    List all active email templates

    POST /api/v1/email/templates/
    Create a new email template
    """
    if request.method == 'GET':
        templates = EmailTemplate.objects.filter(is_active=True).order_by('name')
        serializer = EmailTemplateSerializer(templates, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        if not check_model_perms(request, 'accounting.add_emailtemplate'):
            return Response(PERM_DENIED, status=status.HTTP_403_FORBIDDEN)
        serializer = EmailTemplateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def email_template_detail(request, template_id):
    """
    GET /api/v1/email/templates/{id}/
    Get single email template with preview

    PUT /api/v1/email/templates/{id}/
    Update an email template

    DELETE /api/v1/email/templates/{id}/
    Soft-delete an email template (set is_active=False)
    """
    try:
        template = EmailTemplate.objects.get(id=template_id)
    except EmailTemplate.DoesNotExist:
        return Response(
            {'error': 'Το πρότυπο δεν βρέθηκε.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'GET':
        if not template.is_active:
            return Response(
                {'error': 'Το πρότυπο δεν βρέθηκε.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = EmailTemplateSerializer(template)
        return Response({
            **serializer.data,
            'available_variables': EmailTemplate.get_available_variables()
        })

    elif request.method == 'PUT':
        if not check_model_perms(request, 'accounting.change_emailtemplate'):
            return Response(PERM_DENIED, status=status.HTTP_403_FORBIDDEN)
        serializer = EmailTemplateSerializer(template, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        if not check_model_perms(request, 'accounting.delete_emailtemplate'):
            return Response(PERM_DENIED, status=status.HTTP_403_FORBIDDEN)
        # Soft delete - set is_active=False
        template.is_active = False
        template.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preview_email(request):
    """
    POST /api/v1/email/preview/
    Preview email with template and context

    Body: {
        "template_id": 1,
        "obligation_id": 123  (optional)
        "client_id": 456  (if no obligation_id)
    }
    """
    template_id = request.data.get('template_id')
    obligation_id = request.data.get('obligation_id')
    client_id = request.data.get('client_id')

    if not template_id:
        return Response(
            {'error': 'Απαιτείται template_id.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        template = EmailTemplate.objects.get(id=template_id, is_active=True)
    except EmailTemplate.DoesNotExist:
        return Response(
            {'error': 'Το πρότυπο δεν βρέθηκε.'},
            status=status.HTTP_404_NOT_FOUND
        )

    obligation = None
    client = None

    if obligation_id:
        try:
            obligation = accessible_obligations(request.user).get(id=obligation_id)
            client = obligation.client
        except MonthlyObligation.DoesNotExist:
            return Response(
                {'error': 'Η υποχρέωση δεν βρέθηκε.'},
                status=status.HTTP_404_NOT_FOUND
            )
    elif client_id:
        try:
            client = accessible_clients(request.user).get(id=client_id)
        except ClientProfile.DoesNotExist:
            return Response(
                {'error': 'Ο πελάτης δεν βρέθηκε.'},
                status=status.HTTP_404_NOT_FOUND
            )

    preview = EmailService.preview_email(
        template=template,
        obligation=obligation,
        client=client,
        user=request.user
    )

    return Response(preview)


# ============================================
# SEND EMAIL ENDPOINTS
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_model_perms('accounting.send_client_email')
def send_email(request):
    """
    POST /api/v1/email/send/
    Send email to client

    Body: {
        "client_id": 123,
        "subject": "Θέμα",
        "body": "Κείμενο email (HTML)",
        "template_id": 1,  (optional)
        "attachment_ids": [1, 2, 3]  (optional - document IDs)
    }
    """
    serializer = SendEmailSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    client_id = serializer.validated_data['client_id']
    subject = serializer.validated_data['subject']
    body = serializer.validated_data['body']
    template_id = serializer.validated_data.get('template_id')
    attachment_ids = serializer.validated_data.get('attachment_ids', [])

    client = accessible_clients(request.user).filter(id=client_id).first()
    if client is None:
        return Response({'error': 'Ο πελάτης δεν βρέθηκε.'}, status=status.HTTP_404_NOT_FOUND)
    if not client.email:
        return Response({'error': 'Ο πελάτης δεν έχει email.'}, status=status.HTTP_400_BAD_REQUEST)
    template = None
    if template_id:
        template = EmailTemplate.objects.get(id=template_id)

    # Get attachments
    attachments = []
    if attachment_ids:
        documents = ClientDocument.objects.filter(
            id__in=attachment_ids,
            client=client
        )
        for doc in documents:
            if doc.file:
                attachments.append(doc.file)

    # Send email
    success, result = EmailService.send_email(
        recipient_email=client.email,
        subject=subject,
        body=body,
        client=client,
        template=template,
        user=request.user,
        attachments=attachments
    )

    if success:
        return Response({
            'success': True,
            'message': f'Το email στάλθηκε στο {client.email}.',
            'email_log_id': result.id
        })
    else:
        return Response({
            'success': False,
            'message': 'Αποτυχία αποστολής email.',
            'error': str(result)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_model_perms('accounting.send_client_email')
def send_obligation_notice(request):
    """
    POST /api/v1/email/send-obligation-notice/
    Send obligation reminder/completion/overdue notice

    Body: {
        "obligation_id": 123,
        "template_type": "completion",  // reminder | completion | overdue
        "template_id": 1,  (optional - override template)
        "include_attachment": true,
        "attachment_ids": [1, 2]  (optional - additional document IDs)
    }
    """
    serializer = SendObligationNoticeSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    obligation_id = serializer.validated_data['obligation_id']
    template_type = serializer.validated_data['template_type']
    template_id = serializer.validated_data.get('template_id')
    include_attachment = serializer.validated_data['include_attachment']
    attachment_ids = serializer.validated_data.get('attachment_ids', [])

    obligation = accessible_obligations(request.user).filter(id=obligation_id).first()
    if obligation is None:
        return Response({'error': 'Η υποχρέωση δεν βρέθηκε.'}, status=status.HTTP_404_NOT_FOUND)
    client = obligation.client
    if not client.email:
        return Response({'error': 'Ο πελάτης δεν έχει email.'}, status=status.HTTP_400_BAD_REQUEST)

    # Get template
    if template_id:
        template = EmailTemplate.objects.get(id=template_id, is_active=True)
    else:
        # Find appropriate template based on type
        template = EmailTemplate.get_template_for_obligation(obligation)
        if not template:
            return Response({
                'success': False,
                'message': 'Δεν βρέθηκε πρότυπο email.'
            }, status=status.HTTP_400_BAD_REQUEST)

    # Render template
    subject, body = EmailService.render_template(
        template=template,
        obligation=obligation,
        user=request.user
    )

    # Collect attachments - use new unified document system
    attachments = []
    if include_attachment:
        # Get attachments from obligation's documents
        email_attachments = obligation.get_email_attachments()
        attachments.extend(email_attachments)

    # Also include any specifically selected documents
    if attachment_ids:
        documents = ClientDocument.objects.filter(
            id__in=attachment_ids,
            client=client,
            is_current=True
        )
        for doc in documents:
            if doc.file and doc.file.path not in attachments:
                attachments.append(doc.file.path)

    # Send email
    success, result = EmailService.send_email(
        recipient_email=client.email,
        subject=subject,
        body=body,
        client=client,
        obligation=obligation,
        template=template,
        user=request.user,
        attachments=attachments
    )

    if success:
        return Response({
            'success': True,
            'message': f'Το email στάλθηκε στο {client.email}.',
            'email_log_id': result.id
        })
    else:
        return Response({
            'success': False,
            'message': 'Αποτυχία αποστολής email.',
            'error': str(result)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================
# COMPLETE AND NOTIFY ENDPOINT
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_model_perms('accounting.change_monthlyobligation')
def complete_and_notify(request, obligation_id):
    """
    POST /api/v1/obligations/{id}/complete-and-notify/
    Mark obligation as complete, optionally attach document and send email

    Body (multipart/form-data):
        file: <file>  (optional - upload new document)
        document_id: 123  (optional - attach existing document)
        save_to_client_folder: true  (default: true)
        send_email: false  (default: false)
        attach_to_email: false  (default: false)
        email_template_id: 1  (optional)
        notes: "Σημειώσεις"
        time_spent: 1.5
    """
    from django.utils import timezone
    import os

    try:
        obligation = accessible_obligations(request.user).get(id=obligation_id)
    except MonthlyObligation.DoesNotExist:
        return Response(
            {'error': 'Η υποχρέωση δεν βρέθηκε.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if obligation.status == 'completed':
        return Response(
            {'error': 'Η υποχρέωση είναι ήδη ολοκληρωμένη.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    client = obligation.client
    document = None
    email_sent = False
    email_error = None

    # Parse boolean fields from form data
    save_to_client_folder = request.data.get('save_to_client_folder', 'true')
    if isinstance(save_to_client_folder, str):
        save_to_client_folder = save_to_client_folder.lower() == 'true'

    send_email_flag = request.data.get('send_email', 'false')
    if isinstance(send_email_flag, str):
        send_email_flag = send_email_flag.lower() == 'true'

    if send_email_flag and not check_model_perms(request, 'accounting.send_client_email'):
        return Response(PERM_DENIED, status=status.HTTP_403_FORBIDDEN)

    attach_to_email = request.data.get('attach_to_email', 'false')
    if isinstance(attach_to_email, str):
        attach_to_email = attach_to_email.lower() == 'true'

    # Handle document attachment from existing document
    document_id = request.data.get('document_id')
    if document_id:
        try:
            document = ClientDocument.objects.get(id=document_id, client=client)
            document.obligation = obligation
            document.save()
        except ClientDocument.DoesNotExist:
            return Response(
                {'error': 'Το έγγραφο δεν βρέθηκε.'},
                status=status.HTTP_404_NOT_FOUND
            )

    # Handle file upload
    if 'file' in request.FILES and save_to_client_folder:
        uploaded_file = request.FILES['file']

        # Validate file
        allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png']
        ext = os.path.splitext(uploaded_file.name)[1].lower()

        if ext not in allowed_extensions:
            return Response(
                {'error': f'Μη επιτρεπτός τύπος αρχείου.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if uploaded_file.size > 10 * 1024 * 1024:
            return Response(
                {'error': 'Το αρχείο είναι μεγαλύτερο από 10MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Determine category
        category = 'general'
        if obligation.obligation_type:
            type_code = obligation.obligation_type.code.upper()
            if 'ΦΠΑ' in type_code:
                category = 'vat'
            elif 'ΜΥΦ' in type_code:
                category = 'myf'
            elif 'ΑΠΔ' in type_code:
                category = 'payroll'
            elif 'Ε1' in type_code or 'Ε3' in type_code:
                category = 'tax'

        document = ClientDocument.objects.create(
            client=client,
            obligation=obligation,
            file=uploaded_file,
            document_category=category,
            description=f'Υποχρέωση {obligation.obligation_type.name} {obligation.month:02d}/{obligation.year}'
        )

    # Mark obligation as completed
    obligation.status = 'completed'
    obligation.completed_date = timezone.now().date()
    obligation.completed_by = request.user

    if request.data.get('notes'):
        obligation.notes = request.data.get('notes')

    if request.data.get('time_spent'):
        try:
            obligation.time_spent = float(request.data.get('time_spent'))
        except (ValueError, TypeError):
            pass

    obligation.save()

    # Send email notification if requested
    if send_email_flag and client.email:
        template_id = request.data.get('email_template_id')

        if template_id:
            try:
                template = EmailTemplate.objects.get(id=template_id, is_active=True)
            except EmailTemplate.DoesNotExist:
                template = EmailTemplate.get_template_for_obligation(obligation)
        else:
            template = EmailTemplate.get_template_for_obligation(obligation)

        if template:
            # Collect attachments only if attach_to_email is true
            attachments = []
            if attach_to_email:
                if document and document.file:
                    attachments.append(document.file.path)
                else:
                    # Use new unified document system
                    email_attachments = obligation.get_email_attachments()
                    attachments.extend(email_attachments)

            # Render and send
            subject, body = EmailService.render_template(
                template=template,
                obligation=obligation,
                user=request.user
            )

            success, result = EmailService.send_email(
                recipient_email=client.email,
                subject=subject,
                body=body,
                client=client,
                obligation=obligation,
                template=template,
                user=request.user,
                attachments=attachments
            )

            email_sent = success
            if not success:
                email_error = str(result)

    # Prepare response
    from .api_obligations import ObligationDetailSerializer
    obligation_serializer = ObligationDetailSerializer(
        obligation, context={'request': request}
    )

    response_data = {
        'success': True,
        'message': 'Η υποχρέωση ολοκληρώθηκε.',
        'obligation': obligation_serializer.data,
    }

    if document:
        from .api_documents import DocumentSerializer
        response_data['document'] = DocumentSerializer(
            document, context={'request': request}
        ).data

    if send_email_flag:
        response_data['email_sent'] = email_sent
        if email_error:
            response_data['email_error'] = email_error

    return Response(response_data)


# ============================================
# BULK COMPLETE WITH NOTIFICATIONS
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_model_perms('accounting.change_monthlyobligation')
def bulk_complete_with_notify(request):
    """
    POST /api/v1/obligations/bulk-complete-notify/
    Mark multiple obligations as completed and optionally send notifications

    Body: {
        "obligation_ids": [1, 2, 3],
        "send_notifications": true
    }
    """
    serializer = BulkCompleteNotifySerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    obligation_ids = serializer.validated_data['obligation_ids']
    send_notifications = serializer.validated_data['send_notifications']

    if send_notifications and not check_model_perms(request, 'accounting.send_client_email'):
        return Response(PERM_DENIED, status=status.HTTP_403_FORBIDDEN)

    from django.utils import timezone

    # Get obligations that can be completed (μόνο προσβάσιμες)
    obligations = accessible_obligations(request.user).filter(
        id__in=obligation_ids,
        status__in=['pending', 'overdue']
    ).select_related('client', 'obligation_type')

    completed_count = 0
    email_results = {
        'sent': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }

    for obligation in obligations:
        # Mark as completed
        obligation.status = 'completed'
        obligation.completed_date = timezone.now().date()
        obligation.completed_by = request.user
        obligation.save()
        completed_count += 1

        # Send notification if requested
        if send_notifications:
            client = obligation.client
            if not client.email:
                email_results['skipped'] += 1
                email_results['details'].append({
                    'obligation_id': obligation.id,
                    'client': client.eponimia,
                    'status': 'skipped',
                    'message': 'Ο πελάτης δεν έχει email'
                })
                continue

            template = EmailTemplate.get_template_for_obligation(obligation)
            if not template:
                email_results['failed'] += 1
                email_results['details'].append({
                    'obligation_id': obligation.id,
                    'client': client.eponimia,
                    'status': 'failed',
                    'message': 'Δεν βρέθηκε πρότυπο'
                })
                continue

            success, result = EmailService.send_obligation_completion_email(
                obligation=obligation,
                user=request.user,
                include_attachment=True
            )

            if success:
                email_results['sent'] += 1
                email_results['details'].append({
                    'obligation_id': obligation.id,
                    'client': client.eponimia,
                    'status': 'sent',
                    'message': f'Στάλθηκε στο {client.email}'
                })
            else:
                email_results['failed'] += 1
                email_results['details'].append({
                    'obligation_id': obligation.id,
                    'client': client.eponimia,
                    'status': 'failed',
                    'message': str(result)
                })

    response_data = {
        'success': True,
        'message': f'{completed_count} υποχρεώσεις ολοκληρώθηκαν.',
        'completed_count': completed_count,
    }

    if send_notifications:
        response_data['email_results'] = email_results

    return Response(response_data)


# ============================================
# BULK COMPLETE WITH DOCUMENTS
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_model_perms('accounting.change_monthlyobligation')
def bulk_complete_with_documents(request):
    """
    POST /api/v1/obligations/bulk-complete-with-documents/
    Bulk complete obligations with individual documents for each obligation.

    Body (multipart/form-data):
        obligation_ids: JSON array of obligation IDs
        file_{obligation_id}: File for specific obligation (optional)
        save_to_folders: boolean (default: true)
        send_emails: boolean (default: false)
        attach_to_emails: boolean (default: false)
        template_id: integer (optional) - Email template to use, otherwise auto-select
    """
    from django.utils import timezone
    import json
    import os

    # Parse obligation_ids from JSON
    obligation_ids_raw = request.data.get('obligation_ids', '[]')
    if isinstance(obligation_ids_raw, str):
        try:
            obligation_ids = json.loads(obligation_ids_raw)
        except json.JSONDecodeError:
            return Response(
                {'error': 'Μη έγκυρη μορφή obligation_ids.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        obligation_ids = obligation_ids_raw

    if not obligation_ids:
        return Response(
            {'error': 'Δεν δόθηκαν υποχρεώσεις.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Parse boolean options
    save_to_folders = request.data.get('save_to_folders', 'true')
    if isinstance(save_to_folders, str):
        save_to_folders = save_to_folders.lower() == 'true'

    send_emails = request.data.get('send_emails', 'false')
    if isinstance(send_emails, str):
        send_emails = send_emails.lower() == 'true'

    if send_emails and not check_model_perms(request, 'accounting.send_client_email'):
        return Response(PERM_DENIED, status=status.HTTP_403_FORBIDDEN)

    attach_to_emails = request.data.get('attach_to_emails', 'false')
    if isinstance(attach_to_emails, str):
        attach_to_emails = attach_to_emails.lower() == 'true'

    # Parse optional template_id for email
    template_id = request.data.get('template_id')
    if isinstance(template_id, str) and template_id:
        try:
            template_id = int(template_id)
        except ValueError:
            template_id = None

    # Get override template if specified
    override_template = None
    if template_id:
        try:
            override_template = EmailTemplate.objects.get(id=template_id, is_active=True)
        except EmailTemplate.DoesNotExist:
            pass  # Will fallback to auto-select

    # Get obligations (μόνο προσβάσιμες)
    obligations = accessible_obligations(request.user).filter(
        id__in=obligation_ids,
        status__in=['pending', 'overdue']
    ).select_related('client', 'obligation_type')

    if not obligations.exists():
        return Response(
            {'error': 'Δεν βρέθηκαν υποχρεώσεις προς ολοκλήρωση.'},
            status=status.HTTP_404_NOT_FOUND
        )

    results = []
    completed_count = 0
    email_results = {
        'sent': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }

    allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png']

    for obligation in obligations:
        client = obligation.client
        document = None
        email_sent = False

        # Check for file specific to this obligation
        file_key = f'file_{obligation.id}'
        uploaded_file = request.FILES.get(file_key)

        if uploaded_file and save_to_folders:
            # Validate file
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext in allowed_extensions and uploaded_file.size <= 10 * 1024 * 1024:
                # Determine category
                category = 'general'
                if obligation.obligation_type:
                    type_code = obligation.obligation_type.code.upper()
                    if 'ΦΠΑ' in type_code:
                        category = 'vat'
                    elif 'ΜΥΦ' in type_code:
                        category = 'myf'
                    elif 'ΑΠΔ' in type_code:
                        category = 'payroll'
                    elif 'Ε1' in type_code or 'Ε3' in type_code:
                        category = 'tax'

                document = ClientDocument.objects.create(
                    client=client,
                    obligation=obligation,
                    file=uploaded_file,
                    document_category=category,
                    description=f'Υποχρέωση {obligation.obligation_type.name} {obligation.month:02d}/{obligation.year}'
                )

        # Mark obligation as completed
        obligation.status = 'completed'
        obligation.completed_date = timezone.now().date()
        obligation.completed_by = request.user
        obligation.save()
        completed_count += 1

        # Send email if requested
        if send_emails:
            if not client.email:
                email_results['skipped'] += 1
                email_results['details'].append({
                    'obligation_id': obligation.id,
                    'client': client.eponimia,
                    'status': 'skipped',
                    'message': 'Ο πελάτης δεν έχει email'
                })
            else:
                # Use override template if specified, otherwise auto-select
                template = override_template or EmailTemplate.get_template_for_obligation(obligation)
                if template:
                    # Collect attachments only if attach_to_emails is true
                    attachments = []
                    if attach_to_emails and document and document.file:
                        attachments.append(document.file)

                    # Render and send
                    subject, body = EmailService.render_template(
                        template=template,
                        obligation=obligation,
                        user=request.user
                    )

                    success, result = EmailService.send_email(
                        recipient_email=client.email,
                        subject=subject,
                        body=body,
                        client=client,
                        obligation=obligation,
                        template=template,
                        user=request.user,
                        attachments=attachments
                    )

                    if success:
                        email_results['sent'] += 1
                        email_sent = True
                        email_results['details'].append({
                            'obligation_id': obligation.id,
                            'client': client.eponimia,
                            'status': 'sent',
                            'message': f'Στάλθηκε στο {client.email}'
                        })
                    else:
                        email_results['failed'] += 1
                        email_results['details'].append({
                            'obligation_id': obligation.id,
                            'client': client.eponimia,
                            'status': 'failed',
                            'message': str(result)
                        })
                else:
                    email_results['failed'] += 1
                    email_results['details'].append({
                        'obligation_id': obligation.id,
                        'client': client.eponimia,
                        'status': 'failed',
                        'message': 'Δεν βρέθηκε πρότυπο email'
                    })

        results.append({
            'obligation_id': obligation.id,
            'client': client.eponimia,
            'document_id': document.id if document else None,
            'email_sent': email_sent
        })

    response_data = {
        'success': True,
        'message': f'{completed_count} υποχρεώσεις ολοκληρώθηκαν.',
        'completed_count': completed_count,
        'results': results,
    }

    if send_emails:
        response_data['email_results'] = email_results

    return Response(response_data)


# ============================================
# EMAIL HISTORY
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def email_history(request):
    """
    GET /api/v1/email/history/
    List sent emails with filtering

    Query params:
    - client_id: filter by client
    - obligation_id: filter by obligation
    - status: filter by status (sent, failed, pending)
    - page: page number
    - page_size: items per page
    """
    queryset = EmailLog.objects.all().select_related(
        'client', 'obligation', 'template_used', 'sent_by'
    ).order_by('-sent_at')

    # RBAC: scoped χρήστες βλέπουν μόνο ιστορικό για προσβάσιμους πελάτες
    from accounting.mixins import user_sees_all_clients
    if not user_sees_all_clients(request.user):
        queryset = queryset.filter(client__in=accessible_clients(request.user))

    # Apply filters
    client_id = request.query_params.get('client_id')
    obligation_id = request.query_params.get('obligation_id')
    email_status = request.query_params.get('status')

    if client_id:
        queryset = queryset.filter(client_id=client_id)
    if obligation_id:
        queryset = queryset.filter(obligation_id=obligation_id)
    if email_status:
        queryset = queryset.filter(status=email_status)

    # Pagination (άκυρες τιμές → defaults, με clamp)
    try:
        page = int(request.query_params.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = int(request.query_params.get('page_size', 20))
    except (ValueError, TypeError):
        page_size = 20
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    start = (page - 1) * page_size
    end = start + page_size

    total_count = queryset.count()
    emails = queryset[start:end]

    serializer = EmailLogSerializer(emails, many=True)

    return Response({
        'count': total_count,
        'page': page,
        'page_size': page_size,
        'results': serializer.data
    })


# ============================================
# EMAIL SETTINGS API
# ============================================

class EmailSettingsSerializer(serializers.ModelSerializer):
    """Serializer for EmailSettings"""
    # Don't expose password in responses
    smtp_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = EmailSettings
        fields = [
            'id', 'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
            'has_password', 'smtp_security', 'from_email', 'from_name', 'reply_to',
            'company_name', 'company_phone', 'company_website',
            'accountant_name', 'accountant_title', 'email_signature',
            'rate_limit', 'burst_limit', 'is_active',
            'last_test_at', 'last_test_success', 'last_test_error',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_test_at', 'last_test_success', 'last_test_error', 'created_at', 'updated_at']

    def get_has_password(self, obj):
        """Return whether password is set (without revealing it)"""
        return bool(obj._encrypted_smtp_password)

    def update(self, instance, validated_data):
        """Handle password update - only update if provided"""
        password = validated_data.pop('smtp_password', None)
        if password:  # Only update password if provided (not empty)
            # Use property setter which will encrypt the password
            instance.smtp_password = password
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def email_settings(request):
    """
    GET /api/v1/email/settings/
    Retrieve email settings

    PUT /api/v1/email/settings/
    Update email settings
    """
    # Get or create singleton settings
    settings_obj = EmailSettings.get_settings()

    if request.method == 'GET':
        if not check_model_perms(request, 'accounting.view_emailsettings'):
            return Response(PERM_DENIED, status=status.HTTP_403_FORBIDDEN)
        serializer = EmailSettingsSerializer(settings_obj)
        return Response(serializer.data)

    elif request.method == 'PUT':
        if not check_model_perms(request, 'accounting.change_emailsettings'):
            return Response(PERM_DENIED, status=status.HTTP_403_FORBIDDEN)
        serializer = EmailSettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_model_perms('accounting.change_emailsettings')
def email_settings_test(request):
    """
    POST /api/v1/email/settings/test/
    Test SMTP connection

    Request body (optional - uses saved settings if not provided):
    {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_username": "user@gmail.com",
        "smtp_password": "app-password",
        "smtp_security": "tls"
    }
    """
    settings_obj = EmailSettings.get_settings()

    # If request body provided, use those values for testing (without saving)
    data = request.data
    if data:
        # Temporarily update for test
        if 'smtp_host' in data:
            settings_obj.smtp_host = data['smtp_host']
        if 'smtp_port' in data:
            settings_obj.smtp_port = data['smtp_port']
        if 'smtp_username' in data:
            settings_obj.smtp_username = data['smtp_username']
        if 'smtp_password' in data and data['smtp_password']:
            settings_obj.smtp_password = data['smtp_password']
        if 'smtp_security' in data:
            settings_obj.smtp_security = data['smtp_security']

    # Test connection
    success, message = settings_obj.test_connection()

    return Response({
        'success': success,
        'message': message,
        'last_test_at': settings_obj.last_test_at,
    }, status=status.HTTP_200_OK if success else status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_model_perms('accounting.change_emailsettings')
def email_settings_send_test(request):
    """
    POST /api/v1/email/settings/send-test/
    Send a test email to verify configuration

    Request body:
    {
        "recipient_email": "test@example.com"
    }
    """
    recipient_email = request.data.get('recipient_email')
    if not recipient_email:
        return Response(
            {'error': 'Το email παραλήπτη είναι υποχρεωτικό'},
            status=status.HTTP_400_BAD_REQUEST
        )

    settings_obj = EmailSettings.get_settings()

    if not settings_obj.is_active:
        return Response(
            {'error': 'Οι ρυθμίσεις email είναι απενεργοποιημένες'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Send test email using EmailService
    from django.utils import timezone

    subject = f'Test Email - LogistikoCRM ({timezone.now().strftime("%d/%m/%Y %H:%M")})'
    body_html = f'''
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #4f46e5;">Test Email από LogistikoCRM</h2>
        <p>Αυτό είναι δοκιμαστικό email για επιβεβαίωση των ρυθμίσεων SMTP.</p>
        <hr style="border: 1px solid #e5e7eb; margin: 20px 0;">
        <h3>Ρυθμίσεις:</h3>
        <ul>
            <li><strong>SMTP Server:</strong> {settings_obj.smtp_host}:{settings_obj.smtp_port}</li>
            <li><strong>Ασφάλεια:</strong> {settings_obj.get_smtp_security_display()}</li>
            <li><strong>Από:</strong> {settings_obj.from_name} &lt;{settings_obj.from_email}&gt;</li>
        </ul>
        <hr style="border: 1px solid #e5e7eb; margin: 20px 0;">
        <p style="color: #6b7280; font-size: 12px;">
            Αποστολή: {timezone.now().strftime("%d/%m/%Y %H:%M:%S")}<br>
            Αν λάβατε αυτό το email, οι ρυθμίσεις λειτουργούν σωστά!
        </p>
    </body>
    </html>
    '''

    try:
        success, result = EmailService.send_email(
            recipient_email=recipient_email,
            subject=subject,
            body=body_html,
            user=request.user
        )

        if success:
            return Response({
                'success': True,
                'message': f'Test email στάλθηκε επιτυχώς στο {recipient_email}'
            })
        else:
            return Response({
                'success': False,
                'message': f'Αποτυχία αποστολής: {result}'
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({
            'success': False,
            'message': f'Σφάλμα: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
