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

def can_access_thefile(request, the_file, user=None):
    """
    Object-level access policy για CRM συνημμένα (common.TheFile), βάσει
    του πραγματικού content_object (owner/department/co_owner) μέσω της
    canonical CRM πολιτικής `clarify_permission`.

    Fail closed: μη authenticated χρήστης, dangling GenericForeignKey, ή
    content_object που δεν υποστηρίζει την πολιτική → False. Ο `?mt=`
    token ΔΕΝ παραχωρεί πρόσβαση — απλώς ταυτοποιεί τον χρήστη, και η
    πολιτική εκτελείται κανονικά για αυτόν.
    """
    if user is None:
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
        return bool(clarify_permission(_RequestForUser(request, user), obj))
    except AttributeError:
        # content_object χωρίς owner/department ή request χωρίς role flags
        # (π.χ. χωρίς το middleware) → fail closed
        return False


class _RequestForUser:
    """
    Ελαφρύ shim ώστε το `clarify_permission` να κρίνει τον ΠΡΑΓΜΑΤΙΚΟ
    χρήστη του αιτήματος, ακόμη κι όταν αυτός προκύπτει από ?mt= token
    και όχι από session (οπότε το `request.user` είναι anonymous).

    Τα role flags (is_chief/is_superoperator/is_operator/department_id)
    τα θέτει το UserMiddleware μόνο σε session requests. Για token-based
    χρήστη δεν υπάρχουν, οπότε δίνονται **False/None** — δηλαδή fail
    closed: τα privileged shortcuts δεν ενεργοποιούνται ποτέ μέσω token,
    και μένει μόνο ο έλεγχος owner/co_owner.
    """

    __slots__ = ('_request', 'user')

    def __init__(self, request, user):
        self._request = request
        self.user = _UserWithDefaultRoleFlags(user)

    def __getattr__(self, item):
        return getattr(self._request, item)


class _UserWithDefaultRoleFlags:
    """Proxy χρήστη με ασφαλή defaults για τα role flags του middleware."""

    _DEFAULTS = {
        'is_chief': False,
        'is_superoperator': False,
        'is_operator': False,
        'is_manager': False,
        'is_accountant': False,
        'is_task_operator': False,
        'is_department_head': False,
        'department_id': None,
    }

    __slots__ = ('_user',)

    def __init__(self, user):
        object.__setattr__(self, '_user', user)

    def __getattr__(self, item):
        user = object.__getattribute__(self, '_user')
        try:
            return getattr(user, item)
        except AttributeError:
            if item in _UserWithDefaultRoleFlags._DEFAULTS:
                return _UserWithDefaultRoleFlags._DEFAULTS[item]
            raise

    def __eq__(self, other):
        user = object.__getattribute__(self, '_user')
        if isinstance(other, _UserWithDefaultRoleFlags):
            other = object.__getattribute__(other, '_user')
        return user == other

    def __hash__(self):
        return hash(object.__getattribute__(self, '_user'))


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


def _effective_user(request, storage_name):
    """
    Ο χρήστης για λογαριασμό του οποίου γίνεται το αίτημα.

    Προτεραιότητα στο session (`request.user`). Αν δεν υπάρχει session —
    η τυπική περίπτωση του React frontend, όπου το JWT ζει σε storage και
    ΔΕΝ στέλνεται σε <img src>/<a href>/window.open — χρησιμοποιείται ο
    χρήστης του `?mt=` token, εφόσον το token είναι έγκυρο ΓΙΑ ΑΥΤΟ το
    path και ο χρήστης είναι ακόμη ενεργός.

    Το token ΔΕΝ παραχωρεί πρόσβαση: το authorization τρέχει κανονικά
    για τον χρήστη που επιστρέφεται.
    """
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated and user.is_active:
        return user
    token = request.GET.get('mt') if hasattr(request, 'GET') else None
    if token:
        from common.utils.media_tokens import token_user
        resolved = token_user(token, storage_name)
        if resolved is not None:
            return resolved
    return user


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

    user = _effective_user(request, storage_name)
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
        # content_object. Το ?mt= token ΔΕΝ παρακάμπτει την πολιτική —
        # ταυτοποιεί χρήστη και η πολιτική τρέχει κανονικά γι' αυτόν.
        # 404 (όχι 403) για μη-πρόσβαση ώστε να μην αποκαλύπτεται η
        # ύπαρξη του αρχείου.
        if not can_access_thefile(request, crm_file, user=user):
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
