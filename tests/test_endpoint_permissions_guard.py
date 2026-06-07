# -*- coding: utf-8 -*-
"""
Preventive guard — κανένα staff/management DRF endpoint δεν μένει με μόνο IsAuthenticated
========================================================================================
Η επαναλαμβανόμενη ευπάθεια αυτού του project: management endpoints γκαρνταρισμένα
μόνο με `IsAuthenticated` (το DRF default), άρα προσβάσιμα από κάθε συνδεδεμένο
client-portal user. Αυτό το meta-test σαρώνει ΟΛΑ τα DRF views του URLconf και
αποτυγχάνει αν βρει endpoint που δεν είναι ούτε staff-gated ούτε client-scoped
ούτε ρητά public — ώστε ένα νέο endpoint να μην ξαναγλιστρήσει.

Αν προσθέσεις *νόμιμο* public/client endpoint, βάλ' το στο ALLOWLIST_PATH_MARKERS.
"""
from django.test import SimpleTestCase
from django.urls import get_resolver
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser

from accounting.permissions import IsStaffUser, IsVoIPMonitor, IsLocalRequest
from accounting.portal_mixins import ClientScopedQuerysetMixin


# URL-path markers που είναι ΝΟΜΙΜΑ public ή client-facing (read-mostly, scoped
# στον ίδιο τον χρήστη μέσω _require_client, ή δημόσια με token/throttle).
ALLOWLIST_PATH_MARKERS = (
    'client/me/',          # portal endpoints — scoped via _require_client
    'client/set-password', 'client/request-password-reset',
    'api/auth/', 'api/token', 'api/test',
    'health',              # liveness/readiness probes
    'schema', 'docs', 'redoc',  # OpenAPI
    'public', 'shared',    # token-gated public share links
)

# Permission classes που θεωρούνται «επαρκής έλεγχος» για staff/internal.
STAFF_OR_INTERNAL = (IsStaffUser, IsAdminUser, IsVoIPMonitor, IsLocalRequest)


def _iter_drf_views():
    """(route, view_cls) για κάθε DRF endpoint στο URLconf."""
    out = []

    def walk(patterns, prefix=''):
        for p in patterns:
            route = prefix + str(getattr(p, 'pattern', ''))
            if hasattr(p, 'url_patterns'):
                walk(p.url_patterns, route)
                continue
            cb = getattr(p, 'callback', None)
            if cb is None:
                continue
            cls = getattr(cb, 'cls', None) or getattr(cb, 'view_class', None)
            if isinstance(cls, type) and issubclass(cls, APIView):
                out.append((route, cls))

    walk(get_resolver().url_patterns)
    return out


class EndpointPermissionGuardTest(SimpleTestCase):
    def test_no_management_endpoint_is_only_isauthenticated(self):
        offenders = []
        for route, cls in _iter_drf_views():
            if any(m in route for m in ALLOWLIST_PATH_MARKERS):
                continue
            # Framework-generated browsable-API root (απλώς λίστα routes, όχι data).
            if cls.__name__ == 'APIRootView':
                continue
            # Client-scoped viewsets: το queryset φιλτράρεται στον ιδιοκτήτη +
            # writes → 403 για clients. Νόμιμο IsAuthenticated.
            if issubclass(cls, ClientScopedQuerysetMixin):
                continue
            perms = tuple(getattr(cls, 'permission_classes', ()) or ())
            # Σύνθετα perms (π.χ. IsAuthenticated | IsVoIPMonitor) εμφανίζονται ως
            # OperandHolder (όχι class). Η ύπαρξη σύνθετου σημαίνει «κάποιος επιπλέον
            # έλεγχος» (VoIP/local) → δεν είναι το bare-IsAuthenticated μοτίβο.
            plain = [p for p in perms if isinstance(p, type)]
            has_composed = any(not isinstance(p, type) for p in perms)

            if not perms:
                offenders.append(f'{route}  ->  {cls.__module__}.{cls.__name__}  (no permission_classes → default IsAuthenticated)')
                continue
            if has_composed:
                continue
            if any(issubclass(p, STAFF_OR_INTERNAL) for p in plain):
                continue
            if AllowAny in plain:
                # Ρητά public — επιτρέπεται (πρέπει να είναι throttled/token-gated).
                continue
            # Ό,τι απομένει βασίζεται μόνο σε IsAuthenticated → ύποπτο.
            if plain and all(p is IsAuthenticated for p in plain):
                offenders.append(f'{route}  ->  {cls.__module__}.{cls.__name__}  perms={[p.__name__ for p in plain]}')

        self.assertEqual(
            offenders, [],
            'Management endpoints χωρίς IsStaffUser/scoping (πρόσθεσε IsStaffUser, '
            'ή allowlist αν είναι νόμιμα public/client):\n  ' + '\n  '.join(offenders),
        )
