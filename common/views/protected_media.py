# -*- coding: utf-8 -*-
"""
Προστατευμένο σερβίρισμα MEDIA αρχείων σε παραγωγή.

Πρόσβαση επιτρέπεται μόνο σε:
- συνδεδεμένους (session) ενεργούς χρήστες, ή
- αιτήματα με έγκυρο signed token (?mt=...) — βλ. common/utils/media_tokens.

Το σερβίρισμα γίνεται είτε μέσω nginx X-Accel-Redirect
(MEDIA_ACCEL_REDIRECT=True — μηδενικό φορτίο στο Django), είτε ως
FileResponse fallback όταν δεν υπάρχει nginx μπροστά.
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


def serve_protected_media(request, path):
    full_path = _resolve_media_path(path)

    user = getattr(request, 'user', None)
    allowed = bool(user and user.is_authenticated and user.is_active)
    if not allowed:
        token = request.GET.get('mt', '')
        allowed = bool(token) and verify_media_token(token, path)
    if not allowed:
        raise PermissionDenied('Δεν επιτρέπεται η πρόσβαση στο αρχείο.')

    if not full_path.is_file():
        raise Http404

    if getattr(settings, 'MEDIA_ACCEL_REDIRECT', False):
        # Το nginx σερβίρει το αρχείο από το internal location
        response = HttpResponse()
        prefix = getattr(settings, 'MEDIA_ACCEL_PREFIX', '/protected-media/')
        response['X-Accel-Redirect'] = prefix + quote(path)
        # Άδειο Content-Type ώστε να το καθορίσει το nginx από την κατάληξη
        del response['Content-Type']
        return response

    content_type, _ = mimetypes.guess_type(str(full_path))
    return FileResponse(
        open(full_path, 'rb'),
        content_type=content_type or 'application/octet-stream',
    )
