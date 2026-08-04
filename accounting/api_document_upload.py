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

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from common.utils.media_tokens import signed_media_url
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
    # RBAC: ανάγνωση στοιχείων εγγράφου απαιτεί view_clientdocument
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.view_clientdocument'):
        return JsonResponse(
            {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'}, status=403
        )

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
        # Build query (μόνο έγγραφα ανατεθειμένων πελατών)
        from accounting.services.access import accessible_documents
        qs = accessible_documents(request.user).filter(
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
                    'url': signed_media_url(existing.file) if existing.file else None,
                }
            })
        else:
            return JsonResponse({
                'exists': False,
                'document': None
            })

    except (TypeError, ValueError):
        return JsonResponse({'error': 'Μη έγκυρες παράμετροι.'}, status=400)
    except Exception:
        logger.exception("Error checking existing document")
        return JsonResponse(
            {'error': 'Σφάλμα κατά τον έλεγχο υπάρχοντος εγγράφου.'},
            status=500)


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
    # Upload/νέα έκδοση = write: απαιτείται add_clientdocument
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse({
            'success': False,
            'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'
        }, status=403)

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

    # Ενιαία διαδρομή αρχειοθέτησης (validation βάσει ρυθμίσεων + ονομασία + versioning)
    from django.core.exceptions import ValidationError
    from .services import filing

    try:
        from accounting.services.access import (
            get_accessible_client_or_404, get_accessible_obligation_or_404,
        )
        client = get_accessible_client_or_404(request.user, client_id, request=request)
        obligation = None
        if obligation_id:
            obligation = get_accessible_obligation_or_404(
                request.user, obligation_id, request=request
            )

        # Determine year/month
        if not year or not month:
            if obligation:
                year = obligation.year
                month = obligation.month
            else:
                now = datetime.now()
                year = year or now.year
                month = month or now.month

        try:
            year = int(year)
            month = int(month)
        except (TypeError, ValueError):
            return JsonResponse({
                'success': False,
                'error': 'Μη έγκυρο έτος ή μήνας.'
            }, status=400)
        if not (2000 <= year <= 2100) or not (1 <= month <= 12):
            return JsonResponse({
                'success': False,
                'error': 'Μη έγκυρο έτος ή μήνας.'
            }, status=400)

        # Exact conflict key — ίδια σημασιολογία με το filing service
        existing = ClientDocument.check_existing(
            client=client, obligation=obligation, category=category,
            year=year, month=month,
        )
        has_conflict = existing is not None

        if has_conflict and version_action not in ('new_version', 'replace'):
            # auto - return info that file exists
            return JsonResponse({
                'success': False,
                'action': 'exists',
                'message': 'Υπάρχει ήδη αρχείο για αυτόν τον συνδυασμό',
                'existing_document': _document_to_dict(existing),
                'requires_decision': True,
            }, status=409)  # Conflict

        previous_version = (
            {'id': existing.id, 'version': existing.version} if has_conflict else None
        )

        try:
            new_doc = filing.create_client_document(
                client=client,
                uploaded_file=uploaded_file,
                category=category,
                obligation=obligation,
                year=year,
                month=month,
                user=request.user,
                description=description,
                on_existing='replace' if version_action == 'replace' else 'version',
            )
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': '; '.join(e.messages)
            }, status=400)

        if has_conflict and version_action == 'replace':
            action, message = 'replaced', 'Το αρχείο αντικαταστάθηκε'
        elif has_conflict:
            action, message = 'new_version', f'Δημιουργήθηκε νέα έκδοση (v{new_doc.version})'
        else:
            action, message = 'created', 'Το αρχείο αποθηκεύτηκε επιτυχώς'

        response = {
            'success': True,
            'action': action,
            'message': message,
            'document': _document_to_dict(new_doc),
        }
        if action == 'new_version':
            response['previous_version'] = previous_version
        return JsonResponse(response)

    except PermissionDenied:
        # Το permission matrix του filing (create/version/replace) —
        # π.χ. add-only χρήστης που προσπαθεί version/replace
        return JsonResponse({
            'success': False,
            'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'
        }, status=403)
    except Exception:
        logger.exception("Error uploading document")
        return JsonResponse({
            'success': False,
            'error': 'Σφάλμα κατά τη μεταφόρτωση του εγγράφου.'
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
    from accounting.services.access import check_model_perms, get_accessible_document_or_404
    if not check_model_perms(request, 'accounting.view_clientdocument'):
        return JsonResponse(
            {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'}, status=403
        )
    document = get_accessible_document_or_404(request.user, document_id, request=request)

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
        'url': signed_media_url(document.file) if document.file else None,
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
        'url': signed_media_url(doc.file) if doc.file else None,
        # ΟΧΙ folder_path/file.path: absolute filesystem paths δεν εκτίθενται
        # σε JSON, και το file.path δεν υπάρχει σε μη-local storage backends
        'uploaded_at': doc.uploaded_at.strftime('%d/%m/%Y %H:%M'),
        'uploaded_by': doc.uploaded_by.get_full_name() if doc.uploaded_by else None,
    }


# =============================================================================
# SMART SUGGESTIONS (κατηγορία / ΑΦΜ / όνομα) ΠΡΙΝ ΤΟ UPLOAD
# =============================================================================

@staff_member_required
@require_POST
def suggest_document_metadata(request):
    """
    POST /api/v1/documents/suggest/
    Δέχεται αρχείο (+ προαιρετικά client_id) και επιστρέφει προτάσεις
    ΧΩΡΙΣ να αποθηκεύσει τίποτα:
        - suggested_category: από λέξεις-κλειδιά στο περιεχόμενο/όνομα
        - detected_afm / afm_matches_client
        - suggested_filename: βάσει Κανόνα Ονοματολογίας ρυθμίσεων
    """
    from django.core.exceptions import ValidationError
    from common.utils.afm import find_afm_candidates
    from settings.models import FilingSystemSettings
    from .services import filing, text_extraction

    # RBAC: το suggest τρέχει μόνο ως προετοιμασία upload — απαιτεί το
    # ίδιο permission με το upload (add_clientdocument)
    from accounting.services.access import accessible_clients, check_model_perms
    if not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(
            {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'}, status=403
        )

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'Δεν επιλέχθηκε αρχείο'}, status=400)

    uploaded_file = request.FILES['file']
    try:
        filing.validate_upload(uploaded_file)
    except ValidationError as e:
        return JsonResponse({'error': '; '.join(e.messages)}, status=400)

    client = None
    client_id = request.POST.get('client_id')
    if client_id:
        # Μόνο προσβάσιμος πελάτης — όχι global lookup (θα αποκάλυπτε
        # ΑΦΜ match/όνομα ξένου πελάτη μέσω του suggested_filename)
        client = accessible_clients(request.user).filter(id=client_id).first()

    # Εξαγωγή in-memory, μόνο πρώτες σελίδες
    text, _status = text_extraction.extract_text_from_file(
        uploaded_file, uploaded_file.name, max_pages=5
    )
    uploaded_file.seek(0)

    suggested_category = text_extraction.suggest_category(text, uploaded_file.name)
    detected = find_afm_candidates(text)
    detected_afm = detected[0] if detected else None
    afm_matches_client = None
    if client and detected:
        afm_matches_client = client.afm in detected

    suggested_filename = uploaded_file.name
    try:
        filing_settings = FilingSystemSettings.get_settings()
        suggested_filename = filing_settings.generate_filename(
            uploaded_file.name,
            client=client,
            category=suggested_category or request.POST.get('category') or None,
        )
    except Exception as e:
        logger.warning(f"Suggest filename failed: {e}")

    return JsonResponse({
        'suggested_category': suggested_category,
        'detected_afm': detected_afm,
        'afm_matches_client': afm_matches_client,
        'suggested_filename': suggested_filename,
        'has_text': bool(text),
    })
