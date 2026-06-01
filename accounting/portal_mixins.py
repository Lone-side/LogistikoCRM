# -*- coding: utf-8 -*-
"""
Client Portal scoping mixins
============================
Reusable mixin που περιορίζει το queryset ενός DRF ViewSet ώστε ένας client
χρήστης να βλέπει ΜΟΝΟ τα δεδομένα του δικού του πελάτη, ενώ το staff βλέπει
τα πάντα (αμετάβλητη συμπεριφορά).
"""
from rest_framework.exceptions import PermissionDenied

from accounting.portal import is_client_user, get_client_profile


class ClientScopedQuerysetMixin:
    """
    Mixin για ModelViewSet.

    Ορισμός στο viewset:
        client_scope_field = 'client'   # dotted path από το model προς ClientProfile
                                         # (π.χ. 'client' ή '' αν το ίδιο το model
                                         #  ΕΙΝΑΙ το ClientProfile)

    Συμπεριφορά get_queryset (DEFAULT-DENY / fail-closed):
      - staff/superuser          → super().get_queryset() (όλα, όπως πριν)
      - client user              → filter ώστε client_scope_field.user == user
      - client χωρίς προφίλ      → άδειο queryset
      - μη authenticated (π.χ.   → super().get_queryset() — internal services
        Fritz!Box API key)         (Fritz!Box monitor) που περνούν από τα
                                     permission_classes (IsVoIPMonitor/IsLocal)
      - authenticated αλλά ΟΥΤΕ  → άδειο queryset (fail-closed). Δεν εμπιστευό-
        staff ΟΥΤΕ client          μαστε άγνωστους authenticated χρήστες με
                                     πλήρη πρόσβαση σε δεδομένα πελατών.
    """

    client_scope_field = 'client'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = getattr(self.request, 'user', None)

        # Staff/superuser: πλήρης πρόσβαση (αμετάβλητο).
        if user is not None and (user.is_staff or user.is_superuser):
            return queryset

        # Client portal user: scope στα δικά του δεδομένα.
        if is_client_user(user):
            profile = get_client_profile(user)
            if profile is None:
                return queryset.none()
            field = self.client_scope_field
            if field in ('', None):
                # Το ίδιο το model ΕΙΝΑΙ το ClientProfile.
                return queryset.filter(pk=profile.pk)
            return queryset.filter(**{f'{field}': profile})

        # Μη authenticated (AnonymousUser): internal services που πέρασαν από τα
        # permission_classes (IsVoIPMonitor/IsLocalRequest). Πλήρες queryset.
        if user is None or not user.is_authenticated:
            return queryset

        # Authenticated αλλά ούτε staff ούτε client → fail-closed.
        return queryset.none()

    # Read-only για client portal users: όλες οι μεταβολές (POST/PUT/PATCH/DELETE)
    # πρέπει να γίνονται από staff. Αυτό αποτρέπει π.χ. έναν πελάτη να κάνει
    # POST obligation/document με client=<άλλος_πελάτης>.
    SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')

    def _deny_client_writes(self):
        user = getattr(self.request, 'user', None)
        if is_client_user(user) and self.request.method not in self.SAFE_METHODS:
            raise PermissionDenied('Οι πελάτες έχουν πρόσβαση μόνο για ανάγνωση.')

    def create(self, request, *args, **kwargs):
        self._deny_client_writes()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._deny_client_writes()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._deny_client_writes()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._deny_client_writes()
        return super().destroy(request, *args, **kwargs)
