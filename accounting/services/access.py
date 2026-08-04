# accounting/services/access.py
"""
Κεντρικοί helpers πρόσβασης (RBAC) — μία πηγή αλήθειας για το scoping.

Κανόνες:
- Όταν user_sees_all_clients(user) είναι True (flag off, superuser ή
  accounting.view_all_clients) όλα τα helpers είναι no-ops.
- Out-of-scope αντικείμενα επιστρέφουν 404 (όχι 403) ώστε να μην
  αποκαλύπτεται η ύπαρξή τους, με καταγραφή permission_denied στο AuditLog.
- Έγγραφα/υποχρεώσεις χωρίς client είναι ορατά μόνο σε see-all χρήστες.
"""

from django.http import Http404

from accounting.mixins import user_sees_all_clients


def _audit_deny(user, request, description):
    from common.models import AuditLog
    AuditLog.log(
        user=user if getattr(user, 'is_authenticated', False) else None,
        action='permission_denied',
        description=description,
        severity='medium',
        request=request,
    )


def accessible_clients(user):
    """Queryset πελατών στους οποίους έχει πρόσβαση ο χρήστης."""
    from accounting.models import ClientProfile
    qs = ClientProfile.objects.all()
    if user_sees_all_clients(user):
        return qs
    return qs.filter(assigned_users=user).distinct()


def accessible_documents(user):
    from accounting.models import ClientDocument
    qs = ClientDocument.objects.all()
    if user_sees_all_clients(user):
        return qs
    return qs.filter(client__assigned_users=user).distinct()


def accessible_obligations(user):
    from accounting.models import MonthlyObligation
    qs = MonthlyObligation.objects.all()
    if user_sees_all_clients(user):
        return qs
    return qs.filter(client__assigned_users=user).distinct()


def user_can_access_client(user, client):
    if user_sees_all_clients(user):
        return True
    if client is None:
        return False
    return client.assigned_users.filter(pk=user.pk).exists()


def _get_or_404(qs, pk, user, request, label):
    try:
        return qs.get(pk=pk)
    except (qs.model.DoesNotExist, ValueError, TypeError):
        if not user_sees_all_clients(user) and qs.model.objects.filter(pk=pk).exists():
            _audit_deny(user, request, f'{label} id={pk}: εκτός ανάθεσης')
        raise Http404(f'{label} not found')


def get_accessible_client_or_404(user, pk, request=None):
    return _get_or_404(accessible_clients(user), pk, user, request, 'ClientProfile')


def get_accessible_document_or_404(user, pk, request=None):
    return _get_or_404(accessible_documents(user), pk, user, request, 'ClientDocument')


def check_model_perms(request, *perms):
    """
    Inline έλεγχος model permissions μέσα σε view (για views με πολλά
    HTTP methods όπου το decorator δεν αρκεί). Επιστρέφει True/False
    και καταγράφει την απόρριψη στο AuditLog.
    """
    if request.user.has_perms(perms):
        return True
    _audit_deny(request.user, request, f'{request.method} {request.path}: λείπουν δικαιώματα {sorted(perms)}')
    return False


def require_model_perms(*perms):
    """
    Decorator για function-based DRF views: 403 αν λείπει έστω ένα από τα
    Django model permissions (π.χ. 'accounting.view_clientprofile').
    Superusers περνούν πάντα (has_perms → True). Καταγράφει την απόρριψη.
    """
    from functools import wraps

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from rest_framework.response import Response
            user = request.user
            if not user.has_perms(perms):
                _audit_deny(user, request, f'{request.method} {request.path}: λείπουν δικαιώματα {sorted(perms)}')
                return Response(
                    {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
                    status=403,
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class AttachmentResolutionError(Exception):
    """Σφάλμα επίλυσης email attachments (permission ή invalid/foreign ID)."""

    def __init__(self, message, *, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def resolve_email_attachment_documents(request, client, attachment_ids):
    """
    Κοινός, αυστηρός resolver email attachments (fail closed):
    - απαιτεί accounting.view_clientdocument,
    - δέχεται ΜΟΝΟ list/tuple/set από IDs (όχι σκέτο string — θα γινόταν
      iteration χαρακτήρων),
    - duplicate IDs: επιτρέπονται και αφαιρούνται (κάθε έγγραφο
      επισυνάπτεται ακριβώς μία φορά) — τεκμηριωμένη πολιτική,
    - δέχεται μόνο documents του συγκεκριμένου client, μόνο is_current=True,
    - exact-set validation: κάθε ζητούμενο ID πρέπει να βρεθεί,
    - κάθε document πρέπει να έχει πραγματικό/αναγνώσιμο αρχείο στο storage,
    - σε οποιοδήποτε άκυρο/ξένο/stale ID → απόρριψη ΟΛΟΥ του request,
      ΧΩΡΙΣ να αποκαλύπτεται ποιο συγκεκριμένο ID ήταν το πρόβλημα.

    Επιστρέφει λίστα ClientDocument. Ρίχνει AttachmentResolutionError
    (με status_code 403/400) πριν από κάθε αποστολή/μεταβολή.
    """
    from accounting.models import ClientDocument
    if not attachment_ids:
        return []
    if isinstance(attachment_ids, (str, bytes)) \
            or not isinstance(attachment_ids, (list, tuple, set)):
        raise AttachmentResolutionError('Μη έγκυρα συνημμένα.', status_code=400)
    if not check_model_perms(request, 'accounting.view_clientdocument'):
        raise AttachmentResolutionError(
            'Δεν έχετε δικαίωμα επισύναψης εγγράφων.', status_code=403)
    # Κανονικοποίηση σε μοναδικά int IDs (deduplication policy)
    try:
        wanted = {int(i) for i in attachment_ids}
    except (TypeError, ValueError):
        raise AttachmentResolutionError('Μη έγκυρα συνημμένα.', status_code=400)
    docs = list(ClientDocument.objects.filter(
        id__in=wanted, client=client, is_current=True))
    if len(docs) != len(wanted):
        raise AttachmentResolutionError(
            'Μη έγκυρα ή ξένα συνημμένα.', status_code=400)
    # Κάθε row πρέπει να δείχνει σε υπαρκτό αρχείο — αλλιώς όλο το request
    # απορρίπτεται ΠΡΙΝ από completion/EmailLog/αποστολή
    for doc in docs:
        try:
            if not doc.file or not doc.file.storage.exists(doc.file.name):
                raise AttachmentResolutionError(
                    'Κάποιο συνημμένο δεν είναι διαθέσιμο.', status_code=400)
        except AttachmentResolutionError:
            raise
        except Exception:
            raise AttachmentResolutionError(
                'Κάποιο συνημμένο δεν είναι διαθέσιμο.', status_code=400)
    return docs


def parse_strict_bool(value, field_name, default=False):
    """
    Αυστηρό boolean parsing για flags που προκαλούν mutation ή external
    calls (sync_first, send_email, attach_to_email, ...). ΟΧΙ raw truthiness:
    δέχεται true/false/"true"/"false"/"1"/"0"/1/0· οτιδήποτε άλλο →
    DRF ValidationError (400, ποτέ 500).
    """
    from rest_framework import serializers as drf_serializers
    if value is None:
        return default
    try:
        return drf_serializers.BooleanField().to_internal_value(value)
    except drf_serializers.ValidationError:
        raise drf_serializers.ValidationError(
            {field_name: 'Μη έγκυρη boolean τιμή.'})


def mask_pii_value(value):
    """
    Μάσκαρε τιμή PII για audit log: κρατά μόνο τα 4 τελευταία ψηφία/χαρακτήρες.
    π.χ. IBAN GR1234567890 → ••••7890, ΑΜΚΑ → ••••••45.
    """
    if value is None or value == '':
        return value
    text = str(value)
    if len(text) <= 4:
        return '•' * len(text)
    return '•' * (len(text) - 4) + text[-4:]


def get_accessible_obligation_or_404(user, pk, request=None):
    return _get_or_404(accessible_obligations(user), pk, user, request, 'MonthlyObligation')
