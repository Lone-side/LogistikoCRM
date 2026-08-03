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

from common.utils.media_tokens import verify_media_token


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
    crm_file = TheFile.objects.filter(file=storage_name).only('id').first()
    if crm_file is not None:
        # CRM συνημμένα: κρατάμε την προηγούμενη πολιτική (session ή token
        # δεμένο στο path) — το CRM app έχει το δικό του owner scoping.
        if authenticated:
            return
        token = request.GET.get('mt', '')
        if token and verify_media_token(token, storage_name):
            return
        raise PermissionDenied('Δεν επιτρέπεται η πρόσβαση στο αρχείο.')

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
