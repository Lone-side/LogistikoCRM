"""Το συμβόλαιο των API mounts.

Ιστορικό: ο ίδιος DRF router ήταν mounted ΔΥΟ φορές — στο `api/` και στο
`api/v1/` — οπότε κάθε resource υπήρχε σε δύο διευθύνσεις. Πρακτικό ρίσκο:
προσθέτεις permission/throttle στη μία διαδρομή και ξεχνάς την άλλη.

Τα tests εδώ κλειδώνουν ότι:
  1. κάθε router resource είναι προσβάσιμο στο `api/v1/` (αυτό χρησιμοποιεί
     το frontend και όλη η υπόλοιπη σουίτα),
  2. το legacy `api/` mount ΔΕΝ επανέρχεται σιωπηλά,
  3. τα ρητά (μη-router) endpoints όπως `api/auth/` και `api/search/` ΔΕΝ
     επηρεάστηκαν από την αφαίρεση.
"""
from django.test import TestCase
from django.urls import NoReverseMatch, resolve, reverse
from django.urls.exceptions import Resolver404

# Resources που εγγράφονται στον κοινό router (accounting/urls.py).
ROUTER_RESOURCES = [
    'documents',
    'clients',
    'obligations',
    'obligation-types',
    'document-requests',
    'voip-calls',
    'voip-call-logs',
    'settings/obligation-types',
    'settings/obligation-profiles',
    'settings/obligation-groups',
]

# Resources του router_v2 — υπήρχαν ΠΑΝΤΑ μόνο στο v1.
ROUTER_V2_RESOURCES = ['calls', 'tickets']

# Ρητά δηλωμένα paths: δεν περνούν από router, δεν έπρεπε να επηρεαστούν.
EXPLICIT_PATHS = [
    '/accounting/api/auth/login/',
    '/accounting/api/search/',
]


class ApiV1MountTest(TestCase):
    """Ό,τι χρησιμοποιεί το frontend πρέπει να υπάρχει στο v1."""

    def test_every_router_resource_resolves_under_v1(self):
        for resource in ROUTER_RESOURCES + ROUTER_V2_RESOURCES:
            url = f'/accounting/api/v1/{resource}/'
            with self.subTest(resource=resource):
                try:
                    resolve(url)
                except Resolver404:
                    self.fail(f'{url} δεν αναλύεται — έσπασε το v1 mount')


class LegacyApiMountRemovedTest(TestCase):
    """Το διπλό mount δεν πρέπει να επανέλθει.

    Αν κάποιος ξαναπροσθέσει `path("api/", include(router.urls))`, αυτά
    κοκκινίζουν και εξηγούν γιατί.
    """

    def test_router_resources_are_not_served_without_v1(self):
        for resource in ROUTER_RESOURCES:
            url = f'/accounting/api/{resource}/'
            with self.subTest(resource=resource):
                with self.assertRaises(
                    Resolver404,
                    msg=(
                        f'{url} αναλύεται ξανά — ο router ξαναμπήκε στο '
                        '"api/". Κάθε resource θα έχει πάλι δύο διευθύνσεις '
                        'και τα permissions πρέπει να συντηρούνται δύο φορές.'
                    ),
                ):
                    resolve(url)

    def test_router_url_names_resolve_to_v1(self):
        """Διπλό mount σήμαινε διπλά url names — το reverse() γινόταν λαχείο.

        Τα names είναι namespaced κάτω από `accounting:`.
        """
        for basename in ('client-list', 'document-list', 'obligation-list'):
            name = f'accounting:{basename}'
            with self.subTest(name=name):
                try:
                    url = reverse(name)
                except NoReverseMatch:
                    self.fail(f'το {name} δεν αντιστρέφεται')
                self.assertIn(
                    '/api/v1/', url,
                    f'το reverse("{name}") έδωσε {url} — αναμένεται v1',
                )


class ExplicitPathsUnaffectedTest(TestCase):
    """Τα ρητά endpoints κάτω από api/ δεν είναι router — μένουν ως έχουν."""

    def test_explicit_api_paths_still_resolve(self):
        for url in EXPLICIT_PATHS:
            with self.subTest(url=url):
                try:
                    resolve(url)
                except Resolver404:
                    self.fail(
                        f'{url} δεν αναλύεται — η αφαίρεση του router mount '
                        'δεν έπρεπε να αγγίξει ρητά paths'
                    )
