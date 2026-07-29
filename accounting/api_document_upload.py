# -*- coding: utf-8 -*-
"""
Document Upload API with Versioning Support
Author: LogistikoCRM
Version: 1.0
Description: API endpoints για upload εγγράφων με υποστήριξη versioning.
"""

import os
import json
import logging
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from .models import (
    ClientDocument, ClientProfile, MonthlyObligation, get_client_folder
)

logger = logging.getLogger(__name__)


# =============================================================================
# CHECK EXISTING DOCUMENT
# =============================================================================

@staff_member_required
@require_GET
def check_existing_document(request):
    """
    Ελέγχει αν υπάρχει ήδη έγγραφο για τον συγκεκριμένο συνδυασμό.

    Query params:
        - client_id: ID πελάτη (required)
        - obligation_id: ID υποχρέωσης (optional)
        - category: Κατηγορία εγγράφου (optional)
        - year: Έτος (optional)
        - month: Μήνας (optional)

    Returns:
        JSON με πληροφορίες για υπάρχον έγγραφο ή null
    """
    client_id = request.GET.get('client_id')
    obligation_id = request.GET.get('obligation_id')
    category = request.GET.get('category')
    year = request.GET.get('year')
    month = request.GET.get('month')

    if not client_id:
        return JsonResponse({
            'error': 'client_id is required'
        }, status=400)

    try:
        # Build query
        qs = ClientDocument.objects.filter(
            client_id=client_id,
            is_current=True
        )

        if obligation_id:
            qs = qs.filter(obligation_id=obligation_id)
        if category and category != 'general':
            qs = qs.filter(document_category=category)
        if year:
            qs = qs.filter(year=int(year))
        if month:
            qs = qs.filter(month=int(month))

        existing = qs.select_related('uploaded_by').first()

        if existing:
            return JsonResponse({
                'exists': True,
                'document': {
                    'id': existing.id,
                    'filename': existing.filename,
                    'original_filename': existing.original_filename,
                    'version': existing.version,
                    'file_size': existing.file_size,
                    'file_size_display': existing.file_size_display,
                    'category': existing.document_category,
                    'uploaded_at': existing.uploaded_at.strftime('%d/%m/%Y %H:%M'),
                    'uploaded_by': existing.uploaded_by.get_full_name() if existing.uploaded_by else None,
                    'url': existing.file.url if existing.file else None,
                }
            })
        else:
            return JsonResponse({
                'exists': False,
                'document': None
            })

    except Exception as e:
        logger.error(f"Error checking existing document: {e}", exc_info=True)
        return JsonResponse({
            'error': str(e)
        }, status=500)


# =============================================================================
# UPLOAD DOCUMENT WITH VERSIONING
# =============================================================================

@staff_member_required
@require_POST
def upload_document_with_version(request):
    """
    Upload εγγράφου με υποστήριξη versioning.

    POST params:
        - file: Το αρχείο
        - client_id: ID πελάτη (required)
        - obligation_id: ID υποχρέωσης (optional)
        - category: Κατηγορία εγγράφου (optional, default: 'general')
        - year: Έτος (optional)
        - month: Μήνας (optional)
        - description: Περιγραφή (optional)
        - version_action: 'replace' | 'new_version' | 'auto' (default: 'auto')

    Returns:
        JSON με πληροφορίες του νέου εγγράφου
    """
    if 'file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'Δεν επιλέχθηκε αρχείο'
        }, status=400)

    uploaded_file = request.FILES['file']
    client_id = request.POST.get('client_id')
    obligation_id = request.POST.get('obligation_id')
    category = request.POST.get('category', 'general')
    year = request.POST.get('year')
    month = request.POST.get('month')
    description = request.POST.get('description', '')
    version_action = request.POST.get('version_action', 'auto')

    if not client_id:
        return JsonResponse({
            'success': False,
            'error': 'client_id is required'
        }, status=400)

    # Validation βάσει FilingSystemSettings (καταλήξεις/μέγεθος)
    from django.core.exceptions import ValidationError
    from common.utils.file_validation import sanitize_filename
    from .services import filing

    try:
        filing.validate_upload(uploaded_file)
        uploaded_file.name = sanitize_filename(uploaded_file.name)
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': '; '.join(e.messages)
        }, status=400)

    try:
        client = get_object_or_404(ClientProfile, id=client_id)
        obligation = None
        if obligation_id:
            obligation = get_object_or_404(MonthlyObligation, id=obligation_id)

        # Determine year/month
        if not year or not month:
            if obligation:
                year = obligation.year
                month = obligation.month
            else:
                now = datetime.now()
                year = year or now.year
                month = month or now.month

        year = int(year)
        month = int(month)

        # Check for existing document
        existing = ClientDocument.check_existing(
            client=client,
            obligation=obligation,
            category=category if category != 'general' else None
        )

        if existing and existing.year == year and existing.month == month:
            # Handle based on version_action
            if version_action == 'new_version':
                # Create new version
                new_doc = existing.create_new_version(
                    new_file=uploaded_file,
                    user=request.user
                )
                return JsonResponse({
                    'success': True,
                    'action': 'new_version',
                    'message': f'Δημιουργήθηκε νέα έκδοση (v{new_doc.version})',
                    'document': _document_to_dict(new_doc),
                    'previous_version': {
                        'id': existing.id,
                        'version': existing.version,
                    }
                })

            elif version_action == 'replace':
                # Delete old and create new (same version number)
                old_path = existing.file.path if existing.file else None

                # Create new document with version 1
                new_doc = ClientDocument(
                    client=client,
                    obligation=obligation,
                    file=uploaded_file,
                    original_filename=uploaded_file.name,
                    document_category=category,
                    year=year,
                    month=month,
                    version=1,
                    is_current=True,
                    description=description,
                    uploaded_by=request.user,
                )

                # Delete old file and document
                if old_path and os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception as e:
                        logger.warning(f"Could not delete old file {old_path}: {e}")

                existing.delete()
                new_doc.save()

                return JsonResponse({
                    'success': True,
                    'action': 'replaced',
                    'message': 'Το αρχείο αντικαταστάθηκε',
                    'document': _document_to_dict(new_doc),
                })

            else:  # auto - return info that file exists
                return JsonResponse({
                    'success': False,
                    'action': 'exists',
                    'message': 'Υπάρχει ήδη αρχείο για αυτόν τον συνδυασμό',
                    'existing_document': _document_to_dict(existing),
                    'requires_decision': True,
                }, status=409)  # Conflict

        else:
            # No existing document - create new
            new_doc = ClientDocument(
                client=client,
                obligation=obligation,
                file=uploaded_file,
                original_filename=uploaded_file.name,
                document_category=category,
                year=year,
                month=month,
                version=1,
                is_current=True,
                description=description,
                uploaded_by=request.user,
            )
            new_doc.save()

            return JsonResponse({
                'success': True,
                'action': 'created',
                'message': 'Το αρχείο αποθηκεύτηκε επιτυχώς',
                'document': _document_to_dict(new_doc),
            })

    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# FILE PREVIEW
# =============================================================================

@staff_member_required
@require_GET
def document_preview(request, document_id):
    """
    Επιστρέφει πληροφορίες για preview εγγράφου.

    Returns:
        JSON με URL και metadata για preview
    """
    document = get_object_or_404(ClientDocument, id=document_id)

    # Determine preview type
    preview_type = 'unknown'
    can_preview = False

    if document.file_type:
        ext = document.file_type.lower()
        if ext == 'pdf':
            preview_type = 'pdf'
            can_preview = True
        elif ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            preview_type = 'image'
            can_preview = True

    return JsonResponse({
        'id': document.id,
        'filename': document.filename,
        'file_type': document.file_type,
        'preview_type': preview_type,
        'can_preview': can_preview,
        'url': document.file.url if document.file else None,
        'file_size': document.file_size,
        'file_size_display': document.file_size_display,
        'uploaded_at': document.uploaded_at.strftime('%d/%m/%Y %H:%M'),
        'version': document.version,
        'client_name': document.client.eponimia if document.client else None,
    })


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _document_to_dict(doc):
    """Convert ClientDocument to dictionary for JSON response"""
    return {
        'id': doc.id,
        'filename': doc.filename,
        'original_filename': doc.original_filename,
        'file_type': doc.file_type,
        'file_size': doc.file_size,
        'file_size_display': doc.file_size_display,
        'category': doc.document_category,
        'year': doc.year,
        'month': doc.month,
        'version': doc.version,
        'is_current': doc.is_current,
        'url': doc.file.url if doc.file else None,
        'folder_path': doc.folder_path,
        'uploaded_at': doc.uploaded_at.strftime('%d/%m/%Y %H:%M'),
        'uploaded_by': doc.uploaded_by.get_full_name() if doc.uploaded_by else None,
    }
