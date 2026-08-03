# tests/accounting/test_rbac_round9.py
"""
Αρνητικά tests για τα ευρήματα του 9ου γύρου review:
1. Διαγραφή πελάτη/υποχρέωσης: όχι με σκέτο is_staff — απαιτείται
   delete_* permission + ρόλος Διαχειριστή (see-all).
2. Εναλλακτικά read endpoints (search, file manager, obligation status,
   email preview, document preview/check-existing) απαιτούν view_* perms.
3. assigned → unassigned σε κλήσεις/tickets μόνο από see-all χρήστες.
4. VAT summary: το myDATA κομμάτι βρίσκει περιόδους 'monthly'/'quarterly'.
5. VAT period unlock μόνο από Διαχειριστή, όχι σκέτο is_staff.
6. setup_roles: permissions μόνο από τα apps των ρόλων.
"""

from datetime import date

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounting.models import (
    ClientProfile, MonthlyObligation, ObligationType, Ticket, VoIPCall,
)


def make_role_user(username, role, clients=(), is_staff=False):
    user = User.objects.create_user(
        username=username, password='x', is_active=True, is_staff=is_staff,
    )
    if role:
        user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


class Round9Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456789', eponimia='ΠΕΛΑΤΗΣ Α ΑΕ', email='a@example.gr',
        )
        cls.client_b = ClientProfile.objects.create(
            afm='987654321', eponimia='ΠΕΛΑΤΗΣ Β ΕΠΕ', email='b@example.gr',
        )
        cls.otype = ObligationType.objects.create(code='ΦΠΑ', name='ΦΠΑ')
        cls.obl_a = MonthlyObligation.objects.create(
            client=cls.client_a, obligation_type=cls.otype, year=2026, month=6,
            deadline=date(2026, 6, 20),
        )
        # Staff Λογιστής με ανατεθειμένο τον Α — ο "επικίνδυνος" ρόλος
        cls.accountant = make_role_user(
            'logistis9', 'Λογιστής', [cls.client_a], is_staff=True,
        )
        # Διαχειριστής (view_all_clients) — επιτρεπόμενος για τα admin actions
        cls.manager = make_role_user('dioik9', 'Διαχειριστής', is_staff=True)
        # Χρήστης χωρίς κανένα group αλλά με "ξεχασμένη" ανάθεση πελάτη
        cls.orphan = make_role_user('orphan9', None, [cls.client_a], is_staff=True)

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class DestroyPermissionsTest(Round9Base):
    """Εύρημα 1: διαγραφή πελάτη όχι με σκέτο is_staff."""

    def test_staff_accountant_cannot_delete_assigned_client(self):
        resp = self.api(self.accountant).delete(
            f'/accounting/api/v1/clients/{self.client_a.pk}/'
        )
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(ClientProfile.objects.filter(pk=self.client_a.pk).exists())

    def test_manager_can_delete_client(self):
        resp = self.api(self.manager).delete(
            f'/accounting/api/v1/clients/{self.client_b.pk}/'
        )
        self.assertEqual(resp.status_code, 204)

    def test_staff_accountant_cannot_delete_obligation(self):
        # Ο Λογιστής έχει delete_monthlyobligation αλλά όχι see-all —
        # η διαγραφή ιστορικού παραμένει ενέργεια Διαχειριστή
        resp = self.api(self.accountant).delete(
            f'/accounting/api/v1/obligations/{self.obl_a.pk}/'
        )
        self.assertEqual(resp.status_code, 403)

    def test_manager_can_delete_obligation(self):
        resp = self.api(self.manager).delete(
            f'/accounting/api/v1/obligations/{self.obl_a.pk}/'
        )
        self.assertEqual(resp.status_code, 204)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class AltReadEndpointsPermsTest(Round9Base):
    """Εύρημα 2: χρήστης χωρίς ρόλο (με ανάθεση) δεν διαβάζει από
    εναλλακτικές διαδρομές."""

    def test_global_search_returns_empty_without_view_perms(self):
        resp = self.api(self.orphan).get('/accounting/api/v1/search/?q=ΠΕΛΑΤΗΣ')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total'], 0)
        for category in ('clients', 'obligations', 'tickets', 'calls'):
            self.assertEqual(data['results'][category], [])

    def test_global_search_works_with_role(self):
        resp = self.api(self.accountant).get('/accounting/api/v1/search/?q=ΠΕΛΑΤΗΣ')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()['results']['clients']), 1)

    def test_legacy_search_requires_view_perms(self):
        self.client.force_login(self.orphan)
        resp = self.client.get('/accounting/api/search/?q=ΠΕΛΑΤΗΣ')
        self.assertEqual(resp.status_code, 403)

    def test_file_manager_stats_requires_view_perm(self):
        resp = self.api(self.orphan).get('/accounting/api/v1/file-manager/stats/')
        self.assertEqual(resp.status_code, 403)

    def test_recent_documents_requires_view_perm(self):
        resp = self.api(self.orphan).get('/accounting/api/v1/file-manager/recent/')
        self.assertEqual(resp.status_code, 403)

    def test_browse_folders_requires_view_perm(self):
        resp = self.api(self.orphan).get('/accounting/api/v1/file-manager/browse/')
        self.assertEqual(resp.status_code, 403)

    def test_clients_obligation_status_requires_view_perms(self):
        resp = self.api(self.orphan).get('/accounting/api/v1/clients/obligation-status/')
        self.assertEqual(resp.status_code, 403)

    def test_obligation_profile_get_requires_view_perm(self):
        resp = self.api(self.orphan).get(
            f'/accounting/api/v1/clients/{self.client_a.pk}/obligation-profile/'
        )
        self.assertEqual(resp.status_code, 403)

    def test_email_preview_requires_view_perms(self):
        resp = self.api(self.orphan).post(
            '/accounting/api/v1/email/preview/', {'template_id': 1}, format='json'
        )
        self.assertEqual(resp.status_code, 403)

    def test_check_existing_document_requires_view_perm(self):
        self.client.force_login(self.orphan)
        resp = self.client.get(
            f'/accounting/api/v1/documents/check-existing/?client_id={self.client_a.pk}'
        )
        self.assertEqual(resp.status_code, 403)

    def test_document_preview_requires_view_perm(self):
        self.client.force_login(self.orphan)
        resp = self.client.get('/accounting/api/v1/documents/999/preview/')
        self.assertEqual(resp.status_code, 403)

    def test_suggest_metadata_requires_add_perm(self):
        self.client.force_login(self.orphan)
        resp = self.client.post('/accounting/api/v1/documents/suggest/')
        self.assertEqual(resp.status_code, 403)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class UnassignTransitionTest(Round9Base):
    """Εύρημα 3: assigned → unassigned μόνο από see-all χρήστες."""

    def _make_call(self, client):
        return VoIPCall.objects.create(
            call_id='r9-call-1', phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now(), client=client,
        )

    def test_accountant_cannot_unassign_ticket(self):
        ticket = Ticket.objects.create(client=self.client_a, title='Δικό μου ticket')
        resp = self.api(self.accountant).patch(
            f'/accounting/api/v1/tickets/{ticket.pk}/',
            {'client_id': None}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        ticket.refresh_from_db()
        self.assertEqual(ticket.client_id, self.client_a.pk)

    def test_manager_can_unassign_ticket(self):
        ticket = Ticket.objects.create(client=self.client_a, title='Ticket διαχ.')
        resp = self.api(self.manager).patch(
            f'/accounting/api/v1/tickets/{ticket.pk}/',
            {'client_id': None}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.client_id)

    def test_accountant_cannot_unassign_call(self):
        call = self._make_call(self.client_a)
        resp = self.api(self.accountant).patch(
            f'/accounting/api/v1/calls/{call.pk}/',
            {'client_id': None}, format='json',
        )
        self.assertEqual(resp.status_code, 403)
        call.refresh_from_db()
        self.assertEqual(call.client_id, self.client_a.pk)

    def test_manager_can_unassign_call(self):
        call = self._make_call(self.client_a)
        resp = self.api(self.manager).patch(
            f'/accounting/api/v1/calls/{call.pk}/',
            {'client_id': None}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        call.refresh_from_db()
        self.assertIsNone(call.client_id)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class VatSummaryMyDataTest(Round9Base):
    """Εύρημα 4: το VAT summary βρίσκει πραγματικές περιόδους myDATA."""

    def test_monthly_period_appears_in_report(self):
        from mydata.models import VATPeriodResult
        VATPeriodResult.objects.create(
            client=self.client_a, period_type='monthly', year=2026, period=6,
            vat_output=240, vat_input=100,
        )
        resp = self.api(self.accountant).get(
            '/accounting/api/reports/vat-summary/?year=2026&period_type=month&period=6'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        rows = [c for c in data['clients'] if c['client_afm'] == '123456789']
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].get('has_mydata'))
        self.assertEqual(data['totals']['vat_output'], 240.0)
        self.assertEqual(data['totals']['vat_input'], 100.0)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class VatPeriodUnlockTest(Round9Base):
    """Εύρημα 5α: unlock περιόδου μόνο από Διαχειριστή."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from mydata.models import VATPeriodResult
        cls.period_a = VATPeriodResult.objects.create(
            client=cls.client_a, period_type='monthly', year=2026, period=5,
        )
        cls.period_a.lock()

    def test_staff_accountant_cannot_unlock(self):
        resp = self.api(self.accountant).post(
            f'/accounting/api/mydata/periods/{self.period_a.pk}/unlock/'
        )
        self.assertEqual(resp.status_code, 403)
        self.period_a.refresh_from_db()
        self.assertTrue(self.period_a.is_locked)

    def test_manager_can_unlock(self):
        resp = self.api(self.manager).post(
            f'/accounting/api/mydata/periods/{self.period_a.pk}/unlock/'
        )
        self.assertEqual(resp.status_code, 200)
        self.period_a.refresh_from_db()
        self.assertFalse(self.period_a.is_locked)


class SetupRolesAppLabelTest(TestCase):
    """Εύρημα 5δ: τα permissions των ρόλων μόνο από τα σωστά apps."""

    def test_role_permissions_scoped_to_role_apps(self):
        call_command('setup_roles', verbosity=0)
        # Γύρος 13: ο Διαχειριστής παίρνει και τα backup permissions
        # του settings app (view/change_backupsettings, can_*_backup)
        allowed = {'accounting', 'mydata', 'inventory', 'settings'}
        for role in ('Διαχειριστής', 'Λογιστής', 'Βοηθός'):
            group = Group.objects.get(name=role)
            labels = set(
                group.permissions.values_list('content_type__app_label', flat=True)
            )
            self.assertTrue(
                labels <= allowed,
                f'{role}: permissions εκτός role apps: {labels - allowed}',
            )
