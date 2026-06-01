# -*- coding: utf-8 -*-
"""
Client Portal scoping mixins
============================
Reusable mixin που περιορίζει το queryset ενός DRF ViewSet ώστε ένας client
χρήστης να βλέπει ΜΟΝΟ τα δεδομένα του δικού του πελάτη, ενώ το staff βλέπει
τα πάντα (αμετάβλητη συμπεριφορά).
"""
from accounting.portal import is_client_user, get_client_profile


class ClientScopedQuerysetMixin:
    """
    Mixin για ModelViewSet.

    Ορισμός στο viewset:
        client_scope_field = 'client'   # dotted path από το model προς ClientProfile
                                         # (π.χ. 'client' ή '' αν το ίδιο το model
                                         #  ΕΙΝΑΙ το ClientProfile)

    Συμπεριφορά get_queryset:
      - staff/superuser  → super().get_queryset() (όλα, όπως πριν)
      - client user      → filter ώστε client_scope_field.user == request.user
      - μη συνδεδεμένος client (χωρίς ClientProfile) → άδειο queryset (ασφαλές)
    """

    client_scope_field = 'client'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = getattr(self.request, 'user', None)

        # ΜΟΝΟ οι επιβεβαιωμένοι client users περιορίζονται. Όλοι οι άλλοι
        # (staff, superuser, internal services με API key / localhost) παίρνουν
        # το αρχικό queryset — η πρόσβασή τους ελέγχεται ήδη από τα
        # permission_classes του viewset. Έτσι δεν σπάμε π.χ. τον Fritz!Box
        # monitor (authenticates ως AnonymousUser μέσω API key).
        if is_client_user(user):
            profile = get_client_profile(user)
            if profile is None:
                return queryset.none()

            field = self.client_scope_field
            if field in ('', None):
                # Το ίδιο το model είναι το ClientProfile.
                return queryset.filter(pk=profile.pk)
            return queryset.filter(**{f'{field}': profile})

        return queryset
