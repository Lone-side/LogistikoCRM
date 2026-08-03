# -*- coding: utf-8 -*-
"""
Προστατευμένο σερβίρισμα MEDIA αρχείων σε παραγωγή — document-aware.

Πολιτική (γύρος 14 — fail closed):
- Αρχεία ClientDocument / MonthlyObligation.attachment (φάκελος clients/):
  ΜΟΝΟ συνδεδεμένος ενεργός χρήστης με το αντίστοιχο view permission ΚΑΙ
  πρόσβαση στον πελάτη (accessible_* helpers). Superuser/view_all_clients
  περνούν μέσω των ίδιων helpers. Το session από μόνο του ΔΕΝ αρκεί, και
  ο γενικός signed token (?mt=) ΔΕΝ παρακάμπτει το client assignment.
- Αρχεία common.TheFile (CRM συνημμένα, docs/): συνδεδεμένος ενεργός
  χρήστης (το CRM κρατά το δικό του owner-scoped μοντέλο) ή έγκυρο
  signed token (?mt=) για το συγκεκριμένο path.
- Path που δεν αντιστοιχίζεται σε γνωστό μοντέλο: 404 (fail closed).
- Οι δημόσιες προβολές shared links ΔΕΝ περνούν από εδώ — έχουν δικό
  τους shared-link-aware endpoint (PublicSharedLinkPreviewView) που
  ελέγχει την κατάσταση του link στη βάση σε κάθε request.

Το σερβίρισμα γίνεται είτε μέσω nginx X-Accel-Redirect
(MEDIA_ACCEL_REDIRECT=True), είτε ως FileResponse fallback.
"""
import mimetypes
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse

def can_access_thefile(request, the_file):
    """
    Object-level access policy για CRM συνημμένα (common.TheFile), βάσει
    του πραγματικού content_object (owner/department/co_owner) μέσω της
    canonical CRM πολιτικής `clarify_permission`.

    Fail closed: μη authenticated χρήστης, dangling GenericForeignKey, ή
    content_object που δεν υποστηρίζει την πολιτική → False. Ο γενικός
    `?mt=` token ΔΕΝ δίνει πρόσβαση σε CRM attachment.
    """
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and user.is_active):
        return False
    if user.is_superuser:
        return True
    try:
        obj = the_file.content_object
    except Exception:
        return False
    if obj is None:
        # Dangling GFK ή άγνωστο/μη υποστηριζόμενο target → fail closed
        return False
    try:
        from crm.utils.clarify_permission import clarify_permission
        return bool(clarify_permission(request, obj))
    except AttributeError:
        # content_object χωρίς owner/department ή request χωρίς role flags
        # (π.χ. χωρίς το middleware) → fail closed
        return False


def _resolve_media_path(path):
    """Επιστρέφει το απόλυτο path μέσα στο MEDIA_ROOT ή Http404 σε traversal."""
    media_root = Path(settings.MEDIA_ROOT).resolve()
    try:
        full_path = (media_root / path).resolve()
    except (ValueError, OSError):
        raise Http404
    if media_root != full_path and media_root not in full_path.parents:
        raise Http404
    return full_path


def _canonical_storage_name(path, full_path):
    """
    Η canonical σχετική μορφή του path ως storage name (όπως γράφεται στο
    FileField) — από το resolved απόλυτο path, ώστε '..'/encoding tricks
    να μην ξεγελούν την αντιστοίχιση με τη βάση.
    """
    media_root = Path(settings.MEDIA_ROOT).resolve()
    return full_path.relative_to(media_root).as_posix()


def _authorize(request, storage_name):
    """
    Document-aware authorization. Επιστρέφει σιωπηλά αν επιτρέπεται,
    αλλιώς PermissionDenied (ανώνυμος) ή Http404 (ξένο/άγνωστο — χωρίς
    enumeration).
    """
    from accounting.models import ClientDocument, MonthlyObligation
    from accounting.services.access import (
        accessible_documents, accessible_obligations,
    )

    user = getattr(request, 'user', None)
    authenticated = bool(user and user.is_authenticated and user.is_active)

    doc = ClientDocument.objects.filter(file=storage_name).only('id').first()
    if doc is not None:
        if not authenticated:
            raise PermissionDenied('Δεν επιτρέπεται η πρόσβαση στο αρχείο.')
        if not user.has_perm('accounting.view_clientdocument'):
            raise Http404
        if not accessible_documents(user).filter(pk=doc.pk).exists():
            raise Http404
        return

    obligation = MonthlyObligation.objects.filter(
        attachment=storage_name
    ).only('id').first()
    if obligation is not None:
        if not authenticated:
            raise PermissionDenied('Δεν επιτρέπεται η πρόσβαση στο αρχείο.')
        if not user.has_perm('accounting.view_monthlyobligation'):
            raise Http404
        if not accessible_obligations(user).filter(pk=obligation.pk).exists():
            raise Http404
        return

    from common.models import TheFile
    crm_file = (
        TheFile.objects.filter(file=storage_name)
        .select_related('content_type').first()
    )
    if crm_file is not None:
        # CRM συνημμένα: object-level authorization βάσει του πραγματικού
        # content_object. Ο γενικός ?mt= token ΔΕΝ παρακάμπτει πλέον την
        # πολιτική. 404 (όχι 403) για μη-πρόσβαση ώστε να μην αποκαλύπτεται
        # η ύπαρξη του αρχείου.
        if not can_access_thefile(request, crm_file):
            raise Http404
        return

    # Fail closed: path χωρίς αντιστοίχιση σε επιτρεπόμενο μοντέλο
    raise Http404


def serve_protected_media(request, path):
    full_path = _resolve_media_path(path)
    storage_name = _canonical_storage_name(path, full_path)

    _authorize(request, storage_name)

    if not full_path.is_file():
        raise Http404

    if getattr(settings, 'MEDIA_ACCEL_REDIRECT', False):
        # Το nginx σερβίρει το αρχείο από το internal location
        response = HttpResponse()
        prefix = getattr(settings, 'MEDIA_ACCEL_PREFIX', '/protected-media/')
        response['X-Accel-Redirect'] = prefix + quote(storage_name)
        # Άδειο Content-Type ώστε να το καθορίσει το nginx από την κατάληξη
        del response['Content-Type']
        return response

    content_type, _ = mimetypes.guess_type(str(full_path))
    return FileResponse(
        open(full_path, 'rb'),
        content_type=content_type or 'application/octet-stream',
    )
