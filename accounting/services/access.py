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
