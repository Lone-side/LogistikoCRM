# -*- coding: utf-8 -*-
"""
Regression tests για το P0 της readiness αναφοράς (main@e691b43):

Το FolderStructurePreviewView (settings/api.py) επέτρεπε σε κάθε
authenticated χρήστη να κάνει `GET .../api/filing/folder-preview/?client_id=<X>`
και να λάβει το πλήρες ΑΦΜ + επωνυμία *οποιουδήποτε* πελάτη — cross-client
enumeration, αφού τα client IDs είναι sequential.

Η διόρθωση εφαρμόζει τον κεντρικό μηχανισμό access του project:
`check_model_perms(request, 'accounting.view_clientprofile')` (403 αν λείπει)
+ `get_accessible_client_or_404(...)` (404 για ανύπαρκτο *και* μη ανατεθειμένο
πελάτη — fail closed, χωρίς enumeration).

Τα tests εκτελούν πραγματικά HTTP requests μέσω DRF APIClient με
ENFORCE_CLIENT_ASSIGNMENT=True (χωρίς ALLOW_UNSCOPED_CLIENT_ACCESS).
"""
from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounting.models import ClientProfile


VIEW_CLIENT_PERM = 'accounting.view_clientprofile'


def _view_client_permission():
    return Permission.objects.get(
        content_type__app_label='accounting', codename='view_clientprofile')


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class FolderPreviewAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Ρόλοι (για το Βοηθός case)
        from django.core.management import call_command
        call_command('setup_roles', verbosity=0)

        cls.client_a = ClientProfile.objects.create(
            afm='090000045', eponimia='ΠΕΛΑΤΗΣ Α ΑΕ')
        cls.client_b = ClientProfile.objects.create(
            afm='094014201', eponimia='ΠΕΛΑΤΗΣ Β ΕΠΕ')
        cls.client_c = ClientProfile.objects.create(
            afm='800000006', eponimia='ΠΕΛΑΤΗΣ Γ ΟΕ')

        perm = _view_client_permission()

        # 1) view perm + ανατεθειμένος στον Α
        cls.assigned_with_perm = User.objects.create_user(
            'assigned_perm', password='x', is_staff=True)
        cls.assigned_with_perm.user_permissions.add(perm)
        cls.client_a.assigned_users.add(cls.assigned_with_perm)

        # 3) ανατεθειμένος στον Α αλλά ΧΩΡΙΣ view perm
        cls.assigned_no_perm = User.objects.create_user(
            'assigned_noperm', password='x', is_staff=True)
        cls.client_a.assigned_users.add(cls.assigned_no_perm)

        # 5) Βοηθός (read-only role με view_clientprofile) ανατεθειμένος στον Α
        cls.assistant_assigned = User.objects.create_user(
            'assist_assigned', password='x', is_staff=True)
        cls.assistant_assigned.groups.add(Group.objects.get(name='Βοηθός'))
        cls.client_a.assigned_users.add(cls.assistant_assigned)

        # 5b) Βοηθός ΧΩΡΙΣ ανάθεση στον Α
        cls.assistant_unassigned = User.objects.create_user(
            'assist_unassigned', password='x', is_staff=True)
        cls.assistant_unassigned.groups.add(Group.objects.get(name='Βοηθός'))

    def setUp(self):
        self.url = reverse('settings:folder_preview_api')

    def api(self, user=None):
        c = APIClient()
        if user is not None:
            c.force_authenticate(user)
        return c

    def _assert_no_client_identity(self, response, client):
        body = response.content.decode('utf-8', 'replace')
        self.assertNotIn(client.afm, body,
                         'LEAK: ΑΦΜ ξένου πελάτη στην απόκριση')
        self.assertNotIn('ΠΕΛΑΤΗΣ Β', body,
                         'LEAK: επωνυμία ξένου πελάτη στην απόκριση')
        self.assertNotIn('ΠΕΛΑΤΗΣ Γ', body,
                         'LEAK: επωνυμία ξένου πελάτη στην απόκριση')

    # 1
    def test_assigned_with_perm_gets_200(self):
        r = self.api(self.assigned_with_perm).get(
            self.url, {'client_id': self.client_a.pk})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn(self.client_a.afm, r.content.decode('utf-8'))

    # 2
    def test_perm_but_not_assigned_gets_404_no_leak(self):
        r = self.api(self.assigned_with_perm).get(
            self.url, {'client_id': self.client_b.pk})
        self.assertEqual(r.status_code, 404, r.content)
        self._assert_no_client_identity(r, self.client_b)

    # 3
    def test_assigned_without_perm_gets_403(self):
        r = self.api(self.assigned_no_perm).get(
            self.url, {'client_id': self.client_a.pk})
        self.assertEqual(r.status_code, 403, r.content)
        self._assert_no_client_identity(r, self.client_a)

    # 4
    def test_unauthenticated_rejected(self):
        r = self.api().get(self.url, {'client_id': self.client_a.pk})
        self.assertIn(r.status_code, (401, 403), r.content)
        self._assert_no_client_identity(r, self.client_a)

    # 5
    def test_assistant_assigned_with_view_perm_gets_200(self):
        r = self.api(self.assistant_assigned).get(
            self.url, {'client_id': self.client_a.pk})
        self.assertEqual(r.status_code, 200, r.content)

    def test_assistant_unassigned_gets_404_no_leak(self):
        r = self.api(self.assistant_unassigned).get(
            self.url, {'client_id': self.client_a.pk})
        self.assertEqual(r.status_code, 404, r.content)
        body = r.content.decode('utf-8', 'replace')
        self.assertNotIn(self.client_a.afm, body)

    # 6 — enumeration: διαδοχικά ξένα IDs → κανένα client-identifying στοιχείο
    def test_enumeration_returns_no_client_identity(self):
        api = self.api(self.assigned_with_perm)  # ανατεθειμένος ΜΟΝΟ στον Α
        for foreign in (self.client_b, self.client_c):
            r = api.get(self.url, {'client_id': foreign.pk})
            self.assertEqual(r.status_code, 404, r.content)
            self._assert_no_client_identity(r, foreign)
        # και ανύπαρκτο id: ίδια fail-closed απόκριση (χωρίς διάκριση)
        r = api.get(self.url, {'client_id': 999999})
        self.assertEqual(r.status_code, 404, r.content)

    # Το demo structure (χωρίς client_id) παραμένει προσβάσιμο, χωρίς
    # δεδομένα πραγματικού πελάτη.
    def test_demo_structure_no_real_client(self):
        r = self.api(self.assigned_no_perm).get(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.content.decode('utf-8', 'replace')
        self.assertNotIn(self.client_a.afm, body)
        self.assertNotIn(self.client_b.afm, body)
