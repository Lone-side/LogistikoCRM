# accounting/admin/scoping.py
"""
Κοινό client scoping για ModelAdmin classes με FK προς ClientProfile.

Πολιτική: scoped staff χρήστες βλέπουν μόνο εγγραφές ανατεθειμένων πελατών.
Εγγραφές χωρίς πελάτη (nullable FK — κλήσεις/tickets/email logs) είναι κοινό
triage queue και μένουν ορατές σε όλους όταν allow_unassigned=True.
"""

from django.db.models import Q


class ClientScopedAdminMixin:
    """Βάλε το ΠΡΙΝ το admin.ModelAdmin στα bases. Το get_queryset της
    κλάσης (αν υπάρχει) πρέπει να καλεί super().get_queryset(request)."""

    client_scope_field = 'client'
    allow_unassigned = False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        from accounting.mixins import user_sees_all_clients
        if user_sees_all_clients(request.user):
            return qs
        cond = Q(**{f'{self.client_scope_field}__assigned_users': request.user})
        if self.allow_unassigned:
            cond |= Q(**{f'{self.client_scope_field}__isnull': True})
        return qs.filter(cond).distinct()

    def _scoped_can_touch(self, request, obj):
        if obj is None:
            return True
        from accounting.mixins import user_sees_all_clients
        if user_sees_all_clients(request.user):
            return True
        client = obj
        for part in self.client_scope_field.split('__'):
            client = getattr(client, part, None)
            if client is None:
                return self.allow_unassigned
        from accounting.services.access import user_can_access_client
        return user_can_access_client(request.user, client)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and \
            self._scoped_can_touch(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and \
            self._scoped_can_touch(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and \
            self._scoped_can_touch(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'client':
            from accounting.services.access import accessible_clients
            kwargs['queryset'] = accessible_clients(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
