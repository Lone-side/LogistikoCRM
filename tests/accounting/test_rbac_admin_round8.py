# tests/accounting/test_rbac_admin_round8.py
"""
Γύρος 8 (review PR #178) — regression tests για:
- ClientProfileAdmin.get_search_results: κανένα global queryset σε
  αναζήτηση ΑΦΜ/τηλεφώνου/email/επωνυμίας (ισχύει και για autocomplete)
- ClientDocumentAdmin: scoped queryset, object-level permissions,
  scoped FK επιλογές, mark_as_current μόνο σε προσβάσιμα έγγραφα
- Read endpoints (dashboard/reports/vat-summary/email history/templates):
  απαιτούν view_* model permission, όχι μόνο IsAuthenticated
- IsLocalRequest: σε production (VOIP_ALLOW_LOCALHOST=False) request από
  loopback proxy χωρίς X-API-Key απορρίπτεται
"""

from datetime import date

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from accounting.admin.clients import ClientDocumentAdmin, ClientProfileAdmin
from accounting.models import ClientDocument, ClientProfile, MonthlyObligation, ObligationType


def make_role_user(username, role, clients=(), is_staff=False):
    user = User.objects.create_user(
        username=username, password='x', is_active=True, is_staff=is_staff,
    )
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


class Round8Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456789', eponimia='ΠΕΛΑΤΗΣ Α ΑΕ', email='a@example.gr',
            kinito_tilefono='6912345678',
        )
        cls.client_b = ClientProfile.objects.create(
            afm='987654321', eponimia='ΞΕΝΟΣ ΠΕΛΑΤΗΣ ΕΠΕ', email='foreign@example.gr',
            kinito_tilefono='6998765432',
        )
        cls.accountant = make_role_user(
            'logistis8', 'Λογιστής', [cls.client_a], is_staff=True,
        )
        cls.factory = RequestFactory()

    def admin_request(self, user, params=None):
        request = self.factory.get('/el/456-admin/', params or {})
        request.user = user
        return request


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class AdminSearchScopingTest(Round8Base):
    """Το Admin search (και autocomplete) δεν ξαναφέρνει ξένους πελάτες."""

    def setUp(self):
        self.model_admin = ClientProfileAdmin(ClientProfile, AdminSite())

    def _search(self, term):
        request = self.admin_request(self.accountant)
        base = self.model_admin.get_queryset(request)
        qs, _ = self.model_admin.get_search_results(request, base, term)
        return list(qs.values_list('afm', flat=True))

    def test_search_foreign_afm_returns_nothing(self):
        self.assertEqual(self._search('987654321'), [])

    def test_search_foreign_phone_returns_nothing(self):
        self.assertEqual(self._search('6998765432'), [])

    def test_search_foreign_email_returns_nothing(self):
        self.assertEqual(self._search('foreign@example.gr'), [])

    def test_search_foreign_eponimia_returns_nothing(self):
        self.assertEqual(self._search('ΞΕΝΟΣ'), [])

    def test_search_own_afm_still_works(self):
        self.assertEqual(self._search('123456789'), ['123456789'])

    def test_autocomplete_view_excludes_foreign(self):
        self.client.force_login(self.accountant)
        resp = self.client.get(
            '/el/456-admin/autocomplete/',
            {
                'term': '987654321',
                'app_label': 'accounting',
                'model_name': 'clientdocument',
                'field_name': 'client',
            },
        )
        if resp.status_code == 200:
            texts = str(resp.json())
            self.assertNotIn('987654321', texts)
        else:
            # 403/404 (χωρίς δικαίωμα ή μη-autocomplete πεδίο) = fail-closed
            self.assertIn(resp.status_code, (403, 404))


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ClientDocumentAdminScopingTest(Round8Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.doc_a = ClientDocument.objects.create(
            client=cls.client_a, year=2026, month=6,
            file=SimpleUploadedFile('a.pdf', b'%PDF-1.4 a'),
            original_filename='a.pdf',
        )
        cls.doc_b = ClientDocument.objects.create(
            client=cls.client_b, year=2026, month=6,
            file=SimpleUploadedFile('b.pdf', b'%PDF-1.4 b'),
            original_filename='b.pdf',
        )

    def setUp(self):
        self.model_admin = ClientDocumentAdmin(ClientDocument, AdminSite())

    def test_changelist_excludes_foreign_documents(self):
        request = self.admin_request(self.accountant)
        pks = set(self.model_admin.get_queryset(request).values_list('pk', flat=True))
        self.assertIn(self.doc_a.pk, pks)
        self.assertNotIn(self.doc_b.pk, pks)

    def test_object_permissions_denied_for_foreign_document(self):
        request = self.admin_request(self.accountant)
        self.assertFalse(self.model_admin.has_view_permission(request, self.doc_b))
        self.assertFalse(self.model_admin.has_change_permission(request, self.doc_b))
        self.assertFalse(self.model_admin.has_delete_permission(request, self.doc_b))

    def test_direct_change_url_foreign_document_denied(self):
        self.client.force_login(self.accountant)
        resp = self.client.get(
            f'/el/456-admin/accounting/clientdocument/{self.doc_b.pk}/change/'
        )
        # Django admin: εκτός queryset/χωρίς perm → redirect/403/404, όχι 200
        self.assertIn(resp.status_code, (302, 403, 404))

    def test_mark_as_current_ignores_foreign_versions(self):
        # Scoped χρήστης δεν βλέπει το ξένο έγγραφο στο action queryset
        request = self.admin_request(self.accountant)
        scoped = self.model_admin.get_queryset(request).filter(pk=self.doc_b.pk)
        self.assertEqual(scoped.count(), 0)

    def test_fk_choices_limited_to_accessible_clients(self):
        request = self.admin_request(self.accountant)
        field = self.model_admin.formfield_for_foreignkey(
            ClientDocument._meta.get_field('client'), request,
        )
        pks = set(field.queryset.values_list('pk', flat=True))
        self.assertIn(self.client_a.pk, pks)
        self.assertNotIn(self.client_b.pk, pks)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ReadEndpointPermsTest(Round8Base):
    """Authenticated χρήστης χωρίς group (αλλά με ανάθεση) δεν διαβάζει τίποτα."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.no_group = User.objects.create_user('nogroup8', password='x', is_active=True)
        cls.client_a.assigned_users.add(cls.no_group)

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_read_endpoints_require_view_perms(self):
        urls = [
            '/accounting/api/dashboard/stats/',
            '/accounting/api/reports/stats/',
            '/accounting/api/reports/vat-summary/',
            '/accounting/api/v1/email/history/',
        ]
        for url in urls:
            with self.subTest(url=url):
                resp = self.api(self.no_group).get(url)
                self.assertEqual(resp.status_code, 403)

    def test_email_templates_get_requires_view_perm(self):
        resp = self.api(self.no_group).get('/accounting/api/v1/email/templates/')
        self.assertEqual(resp.status_code, 403)

    def test_accountant_still_reads_dashboard(self):
        resp = self.api(self.accountant).get('/accounting/api/dashboard/stats/')
        self.assertEqual(resp.status_code, 200)


class LocalhostBypassTest(TestCase):
    """Σε production το loopback REMOTE_ADDR δεν αρκεί — θέλει X-API-Key."""

    def _post_call(self):
        return APIClient().post(
            '/accounting/api/v1/calls/',
            {'phone_number': '2101234567', 'direction': 'inbound'},
            REMOTE_ADDR='127.0.0.1',
        )

    @override_settings(VOIP_ALLOW_LOCALHOST=False)
    def test_loopback_without_api_key_denied_in_production(self):
        resp = self._post_call()
        self.assertIn(resp.status_code, (401, 403))

    @override_settings(VOIP_ALLOW_LOCALHOST=True)
    def test_loopback_allowed_with_dev_flag(self):
        resp = self._post_call()
        self.assertNotIn(resp.status_code, (401, 403))

    @override_settings(VOIP_ALLOW_LOCALHOST=True)
    def test_zero_address_no_longer_trusted(self):
        resp = APIClient().post(
            '/accounting/api/v1/calls/',
            {'phone_number': '2101234567', 'direction': 'inbound'},
            REMOTE_ADDR='0.0.0.0',
        )
        self.assertIn(resp.status_code, (401, 403))
