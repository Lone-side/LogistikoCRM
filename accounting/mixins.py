# accounting/mixins.py
"""
RBAC mixins: φιλτράρισμα querysets ανά ανάθεση πελάτη (assigned_users).

Ενεργοποιείται μόνο όταν settings.ENFORCE_CLIENT_ASSIGNMENT=True.
Superusers και χρήστες με accounting.view_all_clients βλέπουν πάντα τα πάντα.
"""

from django.conf import settings


def user_sees_all_clients(user):
    """True αν ο χρήστης εξαιρείται από το φιλτράρισμα ανάθεσης."""
    if not getattr(settings, 'ENFORCE_CLIENT_ASSIGNMENT', False):
        return True
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.has_perm('accounting.view_all_clients')


class ClientScopedQuerysetMixin:
    """
    Περιορίζει το queryset στους πελάτες που είναι ανατεθειμένοι στον χρήστη.

    client_field: το lookup path προς το assigned_users M2M —
    'assigned_users' για ClientProfile, 'client__assigned_users' για
    μοντέλα με FK στον πελάτη.
    """

    client_field = 'client__assigned_users'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user_sees_all_clients(user):
            return queryset
        return queryset.filter(**{self.client_field: user}).distinct()

    def permission_denied(self, request, message=None, code=None):
        # Καταγραφή απορρίψεων πρόσβασης για συμμόρφωση
        if request.user and request.user.is_authenticated:
            from common.models import AuditLog
            AuditLog.log(
                user=request.user,
                action='permission_denied',
                description=f'{request.method} {request.path}',
                severity='medium',
                request=request,
            )
        super().permission_denied(request, message=message, code=code)
