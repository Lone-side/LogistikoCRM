# tests/accounting/test_final_hardening.py
"""
Τελικός γύρος security hardening:
- export_clientprofile permission: ποιος μπορεί να κάνει μαζικά exports
- scoping στα exports (μόνο ανατεθειμένοι πελάτες)
- standalone Fernet key generation (χωρίς Django settings)
- custom actions με ΔΥΟ απαιτούμενα permissions: το ένα μόνο δεν αρκεί
- scrub_audit_pii: dry-run + πραγματικός καθαρισμός legacy PII
"""

import importlib.util
import io
from datetime import date
from pathlib import Path

from django.contrib.auth.models import Group, Permission, User
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from accounting.models import ClientProfile, MonthlyObligation, ObligationType
from common.models import AuditLog

EXPORT_URL = '/accounting/api/v1/export/clients/csv/'


def make_role_user(username, role, clients=(), **extra):
    user = User.objects.create_user(username=username, password='x', **extra)
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


class HardeningBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456789', eponimia='ΠΕΛΑΤΗΣ Α ΑΕ', email='a@example.gr',
        )
        cls.client_b = ClientProfile.objects.create(
            afm='987654321', eponimia='ΠΕΛΑΤΗΣ Β ΕΠΕ', email='b@example.gr',
        )
        cls.accountant = make_role_user('logistis_h', 'Λογιστής', [cls.client_a])
        cls.assistant = make_role_user(
            'voithos_h', 'Βοηθός', [cls.client_a, cls.client_b],
        )

    def api(self, user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ExportPermissionTest(HardeningBase):
    """Το view_clientprofile ΔΕΝ αρκεί για μαζική εξαγωγή PII."""

    def test_assistant_export_clients_403(self):
        resp = self.api(self.assistant).get(EXPORT_URL)
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_export_clients_401(self):
        resp = self.api().get(EXPORT_URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_view_only_user_without_export_perm_403(self):
        # Χρήστης με view_clientprofile αλλά ΧΩΡΙΣ export_clientprofile
        user = User.objects.create_user(username='vieweronly', password='x')
        perm = Permission.objects.get(
            codename='view_clientprofile',
            content_type__app_label='accounting',
        )
        user.user_permissions.add(perm)
        self.client_a.assigned_users.add(user)
        user = User.objects.get(pk=user.pk)
        resp = self.api(user).get(EXPORT_URL)
        self.assertEqual(resp.status_code, 403)

    def test_accountant_export_scoped_to_assigned_clients(self):
        import openpyxl
        resp = self.api(self.accountant).get(EXPORT_URL)
        self.assertEqual(resp.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        afms = {row[0].value for row in wb.active.iter_rows(min_row=2)}
        self.assertIn('123456789', afms)
        self.assertNotIn('987654321', afms)

    def test_assistant_reports_export_download_403(self):
        resp = self.api(self.assistant).get(
            '/accounting/api/reports/export/download/?type=clients'
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_client_obligations_export_403(self):
        resp = self.api(self.assistant).get(
            '/accounting/api/v1/export/client-obligations/csv/'
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_vat_summary_json_ok_but_xlsx_403(self):
        json_resp = self.api(self.assistant).get(
            '/accounting/api/reports/vat-summary/'
        )
        self.assertEqual(json_resp.status_code, 200)
        xlsx_resp = self.api(self.assistant).get(
            '/accounting/api/reports/vat-summary/?format=xlsx'
        )
        self.assertEqual(xlsx_resp.status_code, 403)

    def test_assistant_legacy_voip_export_403(self):
        # staff Βοηθός (το view είναι staff_member_required, Django view →
        # session login, όχι DRF force_authenticate)
        staff_assistant = make_role_user(
            'voithos_staff_h', 'Βοηθός', [self.client_a], is_staff=True,
        )
        self.client.force_login(staff_assistant)
        resp = self.client.get('/accounting/voip/export/csv/')
        self.assertEqual(resp.status_code, 403)

    def test_assistant_legacy_excel_export_403(self):
        staff_assistant = make_role_user(
            'voithos_staff_h2', 'Βοηθός', [self.client_a], is_staff=True,
        )
        self.client.force_login(staff_assistant)
        resp = self.client.get('/accounting/export-excel/')
        self.assertEqual(resp.status_code, 403)

    def test_roles_have_expected_export_perm(self):
        self.assertTrue(self.accountant.has_perm('accounting.export_clientprofile'))
        self.assertFalse(self.assistant.has_perm('accounting.export_clientprofile'))


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class AdminExportActionTest(HardeningBase):
    """Τα admin export actions εμφανίζονται μόνο σε όσους έχουν το export perm."""

    def _admin_actions_for(self, user):
        from django.contrib import admin as django_admin
        from accounting.models import ClientProfile as CP
        model_admin = django_admin.site._registry[CP]
        request = RequestFactory().get('/456-admin/accounting/clientprofile/')
        request.user = user
        return set(model_admin.get_actions(request).keys())

    def test_assistant_staff_has_no_export_actions(self):
        staff_assistant = make_role_user(
            'voithos_admin_h', 'Βοηθός', [self.client_a], is_staff=True,
        )
        actions = self._admin_actions_for(staff_assistant)
        for name in ('export_selected', 'export_all', 'export_summary',
                     'export_to_csv'):
            self.assertNotIn(name, actions)

    def test_accountant_staff_has_export_actions(self):
        staff_accountant = make_role_user(
            'logistis_admin_h', 'Λογιστής', [self.client_a], is_staff=True,
        )
        actions = self._admin_actions_for(staff_accountant)
        self.assertIn('export_selected', actions)
        self.assertIn('export_to_csv', actions)


class FernetKeyScriptTest(TestCase):
    """Το standalone script παράγει έγκυρο Fernet key χωρίς Django settings."""

    def test_generate_key_is_valid_fernet(self):
        from cryptography.fernet import Fernet
        script = (
            Path(__file__).resolve().parents[2] / 'scripts' / 'generate_fernet_key.py'
        )
        spec = importlib.util.spec_from_file_location('generate_fernet_key', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        key = module.generate_key()
        # Έγκυρο κλειδί: το Fernet το δέχεται και κάνει roundtrip
        f = Fernet(key.encode())
        self.assertEqual(f.decrypt(f.encrypt(b'ok')), b'ok')

    def test_script_has_no_django_import(self):
        script = (
            Path(__file__).resolve().parents[2] / 'scripts' / 'generate_fernet_key.py'
        )
        source = script.read_text(encoding='utf-8')
        self.assertNotIn('import django', source)
        self.assertNotIn('from django', source)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class SinglePermissionActionTest(HardeningBase):
    """Custom actions με δύο απαιτούμενα permissions: το ένα μόνο → 403."""

    def _user_with_perms(self, username, *codenames):
        user = User.objects.create_user(username=username, password='x')
        for codename in codenames:
            user.user_permissions.add(Permission.objects.get(
                codename=codename, content_type__app_label='accounting',
            ))
        self.client_a.assigned_users.add(user)
        return User.objects.get(pk=user.pk)

    def _make_call(self):
        from accounting.models import VoIPCall
        from django.utils import timezone
        return VoIPCall.objects.create(
            phone_number='2101234567', client=self.client_a,
            direction='inbound', status='missed', started_at=timezone.now(),
        )

    def test_create_ticket_with_only_add_ticket_403(self):
        call = self._make_call()
        user = self._user_with_perms('only_add_ticket', 'add_ticket')
        resp = self.api(user).post(
            f'/accounting/api/v1/calls/{call.id}/create_ticket/', {},
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_ticket_with_only_view_voipcall_403(self):
        call = self._make_call()
        user = self._user_with_perms('only_view_call', 'view_voipcall')
        resp = self.api(user).post(
            f'/accounting/api/v1/calls/{call.id}/create_ticket/', {},
        )
        self.assertEqual(resp.status_code, 403)

    def test_create_ticket_with_both_perms_ok(self):
        call = self._make_call()
        user = self._user_with_perms(
            'both_perms', 'add_ticket', 'view_voipcall',
        )
        resp = self.api(user).post(
            f'/accounting/api/v1/calls/{call.id}/create_ticket/', {},
        )
        self.assertIn(resp.status_code, (200, 201))

    def test_reveal_with_only_view_clientcredential_403(self):
        from accounting.models import ClientCredential
        cred = ClientCredential.objects.create(
            client=self.client_a, service='taxisnet', username='u',
        )
        user = self._user_with_perms('only_view_cred', 'view_clientcredential')
        resp = self.api(user).post(
            f'/accounting/api/v1/clients/{self.client_a.id}/credentials/'
            f'{cred.id}/reveal/', {},
        )
        self.assertEqual(resp.status_code, 403)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class GsisSettingsAccessTest(HardeningBase):
    """Οι ρυθμίσεις GSIS (credentials γραφείου) μόνο για Διαχειριστή."""

    def test_accountant_cannot_read_gsis_status(self):
        resp = self.api(self.accountant).get('/accounting/api/v1/gsis/status/')
        self.assertEqual(resp.status_code, 403)

    def test_accountant_cannot_update_gsis_settings(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/gsis/settings/',
            {'afm': '123456789', 'username': 'u', 'password': 'p'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_read_gsis_status(self):
        admin = make_role_user('dioik_gsis', 'Διαχειριστής')
        resp = self.api(admin).get('/accounting/api/v1/gsis/status/')
        self.assertEqual(resp.status_code, 200)


class ScrubAuditPiiTest(TestCase):
    """scrub_audit_pii: μασκάρει legacy PII χωρίς να σβήνει events."""

    def _legacy_rows(self):
        # Παλιό payload με πλήρεις τιμές (όπως έγραφε το API πριν το masking)
        full_values = AuditLog.objects.create(
            username='old', action='update', model_name='ClientProfile',
            changes={
                'afm': {'old': '123456789', 'new': '987654321'},
                'amka': {'old': '12345678901', 'new': '10987654321'},
                'iban': {'old': 'GR1601101250000000012300695', 'new': ''},
                'kinito_tilefono': {'old': '6912345678', 'new': '6998765432'},
                'diefthinsi_katoikias': {'old': 'Οδός Παράδειγμα 1', 'new': 'Οδός Νέα 2'},
                'eponimia': {'old': 'ΠΑΛΙΑ ΑΕ', 'new': 'ΝΕΑ ΑΕ'},  # όχι PII key
            },
            description='Αλλαγή στοιχείων πελάτη ΑΦΜ 123456789, τηλ 6912345678, '
                        'email old@example.gr',
        )
        already_clean = AuditLog.objects.create(
            username='new', action='update', model_name='ClientProfile',
            changes={'afm': {'old': '•••••6789', 'new': '•••••4321'}},
            description='Αλλαγή προσωπικών δεδομένων πελάτη',
        )
        return full_values, already_clean

    def test_dry_run_changes_nothing(self):
        full_values, _ = self._legacy_rows()
        out = io.StringIO()
        call_command('scrub_audit_pii', stdout=out)
        full_values.refresh_from_db()
        self.assertEqual(full_values.changes['afm']['old'], '123456789')
        self.assertIn('123456789', full_values.description)
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertIn('με αλλαγές=1', out.getvalue())

    def test_apply_masks_pii_and_keeps_events(self):
        full_values, already_clean = self._legacy_rows()
        out = io.StringIO()
        call_command('scrub_audit_pii', '--apply', stdout=out)

        total = AuditLog.objects.count()
        self.assertEqual(total, 2)  # δεν διαγράφηκε τίποτα

        full_values.refresh_from_db()
        # ΑΦΜ/ΑΜΚΑ/IBAN/τηλέφωνα: masked με last-4
        self.assertEqual(full_values.changes['afm']['old'], '•••••6789')
        self.assertEqual(full_values.changes['amka']['new'], '•••••••4321')
        self.assertTrue(full_values.changes['iban']['old'].endswith('0695'))
        self.assertNotIn('GR16', full_values.changes['iban']['old'])
        self.assertEqual(full_values.changes['kinito_tilefono']['old'][-4:], '5678')
        self.assertNotIn('691234', full_values.changes['kinito_tilefono']['old'])
        # Διεύθυνση: μόνο ένδειξη αλλαγής
        self.assertEqual(
            full_values.changes['diefthinsi_katoikias'], {'changed': True}
        )
        # Μη-PII πεδίο μένει άθικτο
        self.assertEqual(full_values.changes['eponimia']['old'], 'ΠΑΛΙΑ ΑΕ')
        # Description: κανένα πλήρες ΑΦΜ/τηλέφωνο/email
        self.assertNotIn('123456789', full_values.description)
        self.assertNotIn('6912345678', full_values.description)
        self.assertNotIn('old@example.gr', full_values.description)
        self.assertIn('6789', full_values.description)  # last-4 διατηρείται

        # Ήδη καθαρή εγγραφή: αμετάβλητη
        clean_before = already_clean.changes
        already_clean.refresh_from_db()
        self.assertEqual(already_clean.changes, clean_before)

    def test_apply_is_idempotent(self):
        self._legacy_rows()
        call_command('scrub_audit_pii', '--apply', stdout=io.StringIO())
        out = io.StringIO()
        call_command('scrub_audit_pii', '--apply', stdout=out)
        self.assertIn('με αλλαγές=0', out.getvalue())
