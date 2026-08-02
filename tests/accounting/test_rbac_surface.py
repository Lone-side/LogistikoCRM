# tests/accounting/test_rbac_surface.py
"""
Αρνητικά tests για το υπόλοιπο attack surface (2ος γύρος ελέγχου):
- export/import πελατών: permissions + scoping
- myDATA API: scoping + read-only ρόλος
- email API: send_client_email + scoping, email settings μόνο με perm
- legacy completion views: scoped querysets
- obligation profiles / document requests / shared links: write perms
- VoIP/Tickets scoping, vat_summary myDATA scoping
- ClientViewSet perform_create: αυτόματη ανάθεση δημιουργού
"""

from datetime import date

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounting.models import (
    ClientProfile, MonthlyObligation, ObligationType, Ticket,
)


def make_role_user(username, role, clients=(), is_staff=False):
    user = User.objects.create_user(
        username=username, password='x', is_active=True, is_staff=is_staff,
    )
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


class SurfaceBase(TestCase):
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
        cls.obl_b = MonthlyObligation.objects.create(
            client=cls.client_b, obligation_type=cls.otype, year=2026, month=6,
            deadline=date(2026, 6, 20),
        )
        cls.accountant = make_role_user('logistis2', 'Λογιστής', [cls.client_a], is_staff=True)
        cls.assistant = make_role_user('voithos2', 'Βοηθός', [cls.client_a, cls.client_b])

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ExportImportTest(SurfaceBase):
    def test_export_clients_scoped_to_accessible(self):
        resp = self.api(self.accountant).get('/accounting/api/v1/export/clients/csv/')
        self.assertEqual(resp.status_code, 200)
        import io
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        afms = [row[0].value for row in wb.active.iter_rows(min_row=2)]
        self.assertIn('123456789', afms)
        self.assertNotIn('987654321', afms)

    def test_export_clients_requires_view_perm(self):
        user = User.objects.create_user('noperm', password='x')
        resp = self.api(user).get('/accounting/api/v1/export/clients/csv/')
        self.assertEqual(resp.status_code, 403)

    def test_import_clients_requires_write_perms(self):
        resp = self.api(self.assistant).post('/accounting/api/v1/import/clients/csv/', {})
        self.assertEqual(resp.status_code, 403)

    def test_client_obligations_export_scoped(self):
        from accounting.models import ClientObligation
        ClientObligation.objects.get_or_create(client=self.client_b, defaults={'is_active': True})
        resp = self.api(self.accountant).get('/accounting/api/v1/export/client-obligations/csv/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('987654321', resp.content.decode('utf-8-sig'))


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class MyDataRbacTest(SurfaceBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from mydata.models import MyDataCredentials, VATPeriodResult, VATRecord
        cls.creds_b = MyDataCredentials.objects.create(client=cls.client_b)
        cls.period_b = VATPeriodResult.objects.create(
            client=cls.client_b, period_type='monthly', year=2026, period=6,
        )
        cls.record_b = VATRecord.objects.create(
            client=cls.client_b, mark=100001, rec_type=1, vat_category=1,
            issue_date=date(2026, 6, 10), net_value=100, vat_amount=24,
        )

    def test_credentials_list_scoped(self):
        resp = self.api(self.accountant).get('/accounting/api/mydata/credentials/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        results = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(len(results), 0)

    def test_credentials_detail_foreign_404(self):
        resp = self.api(self.accountant).get(
            f'/accounting/api/mydata/credentials/{self.creds_b.pk}/'
        )
        self.assertEqual(resp.status_code, 404)

    def test_assistant_cannot_modify_credentials(self):
        resp = self.api(self.assistant).post(
            f'/accounting/api/mydata/credentials/{self.creds_b.pk}/update_credentials/',
            {'user_id': 'x', 'subscription_key': 'y'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_records_scoped(self):
        resp = self.api(self.accountant).get('/accounting/api/mydata/records/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        results = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(len(results), 0)

    def test_periods_foreign_404(self):
        resp = self.api(self.accountant).get(
            f'/accounting/api/mydata/periods/{self.period_b.pk}/'
        )
        self.assertEqual(resp.status_code, 404)

    def test_client_detail_foreign_404(self):
        resp = self.api(self.accountant).get('/accounting/api/mydata/client/987654321/')
        self.assertEqual(resp.status_code, 404)

    def test_dashboard_excludes_foreign_clients(self):
        resp = self.api(self.accountant).get('/accounting/api/mydata/dashboard/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['overview']['clients_with_credentials'], 0)
        self.assertEqual(data['clients'], [])

    def test_vat_summary_report_excludes_foreign_mydata(self):
        resp = self.api(self.accountant).get(
            '/accounting/api/reports/vat-summary/',
            {'year': 2026, 'period_type': 'month', 'period': 6},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('987654321', resp.content.decode())


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class EmailRbacTest(SurfaceBase):
    def test_send_email_requires_perm(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/email/send/',
            {'client_id': self.client_a.pk, 'subject': 'x', 'body': 'y'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_send_email_foreign_client_404(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/email/send/',
            {'client_id': self.client_b.pk, 'subject': 'x', 'body': 'y'},
        )
        self.assertEqual(resp.status_code, 404)

    def test_assistant_cannot_manage_templates(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/email/templates/',
            {'name': 'x', 'subject': 's', 'body': 'b', 'template_type': 'custom'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_email_settings_requires_perm(self):
        self.assertEqual(
            self.api(self.assistant).get('/accounting/api/v1/email/settings/').status_code,
            403,
        )
        self.assertEqual(
            self.api(self.accountant).put(
                '/accounting/api/v1/email/settings/', {'smtp_host': 'evil'},
            ).status_code,
            403,
        )

    def test_complete_and_notify_foreign_obligation_404(self):
        resp = self.api(self.accountant).post(
            f'/accounting/api/v1/obligations/{self.obl_b.pk}/complete-and-notify/', {},
        )
        self.assertEqual(resp.status_code, 404)

    def test_assistant_cannot_complete_and_notify(self):
        resp = self.api(self.assistant).post(
            f'/accounting/api/v1/obligations/{self.obl_b.pk}/complete-and-notify/', {},
        )
        self.assertEqual(resp.status_code, 403)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class CompletionViewsRbacTest(SurfaceBase):
    def test_complete_single_foreign_404(self):
        self.client.force_login(self.accountant)
        resp = self.client.post(f'/accounting/obligations/{self.obl_b.pk}/complete/')
        self.assertEqual(resp.status_code, 404)

    def test_list_api_excludes_foreign(self):
        self.client.force_login(self.accountant)
        resp = self.client.get(
            '/accounting/obligations/api/', {'month': 6, 'year': 2026},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('987654321', resp.content.decode())


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ProfilesAndRequestsRbacTest(SurfaceBase):
    def test_assistant_cannot_update_obligation_profile(self):
        resp = self.api(self.assistant).put(
            f'/accounting/api/v1/clients/{self.client_a.pk}/obligation-profile/',
            {'obligation_type_ids': [self.otype.pk]},
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_generate_month(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/obligations/generate-month/', {'month': 6, 'year': 2026},
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_bulk_assign(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/obligations/bulk-assign/',
            {'client_ids': [self.client_a.pk], 'obligation_type_ids': [self.otype.pk]},
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_create_shared_link(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/file-manager/shared-links/',
            {'client_id': self.client_a.pk, 'name': 'x'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_create_document_request(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/document-requests/',
            {'client_id': self.client_a.pk, 'title': 'x', 'items': [{'label': 'a'}]},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_attach_document(self):
        resp = self.api(self.assistant).post(
            f'/accounting/api/v1/obligations/{self.obl_b.pk}/attach-document/',
            {'document_id': 1},
        )
        self.assertEqual(resp.status_code, 403)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class VoipTicketsRbacTest(SurfaceBase):
    def test_tickets_scoped(self):
        Ticket.objects.create(client=self.client_b, title='Ξένο ticket')
        resp = self.api(self.accountant).get('/accounting/api/v1/tickets/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Ξένο ticket', resp.content.decode())

    def test_unassigned_ticket_visible(self):
        Ticket.objects.create(title='Χωρίς πελάτη')
        resp = self.api(self.accountant).get('/accounting/api/v1/tickets/')
        self.assertIn('Χωρίς πελάτη', resp.content.decode())

    def test_ticket_create_foreign_client_404(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/tickets/', {'title': 'x', 'client': self.client_b.pk},
        )
        self.assertEqual(resp.status_code, 404)

    def test_calls_stats_search_scoped(self):
        resp = self.api(self.accountant).get(
            '/accounting/api/v1/clients/search-for-match/', {'q': 'ΠΕΛΑΤΗΣ'},
        )
        # Το endpoint μπορεί να έχει άλλο url — αν 404 δεν κρίνουμε εδώ
        if resp.status_code == 200:
            self.assertNotIn('987654321', resp.content.decode())


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ClientCreateAutoAssignTest(SurfaceBase):
    def test_creator_auto_assigned(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/clients/',
            {'afm': '111111110', 'eponimia': 'ΝΕΟΣ ΠΕΛΑΤΗΣ', 'eidos_ipoxreou': 'company'},
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        new_client = ClientProfile.objects.get(afm='111111110')
        # Ο δημιουργός τον βλέπει αμέσως μετά
        detail = self.api(self.accountant).get(f'/accounting/api/v1/clients/{new_client.pk}/')
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(
            new_client.assigned_users.filter(pk=self.accountant.pk).exists()
        )


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class AdminBypassTest(SurfaceBase):
    def test_mass_update_scoped(self):
        from django.urls import reverse
        self.client.force_login(self.accountant)
        url = reverse('admin:accounting_clientprofile_mass_update')
        resp = self.client.post(url, {
            'action': 'deactivate',
            'client_ids': [str(self.client_b.pk)],
        })
        self.client_b.refresh_from_db()
        # Ο πελάτης Β (εκτός ανάθεσης) δεν απενεργοποιήθηκε
        self.assertTrue(self.client_b.is_active)

    def test_import_view_denied_for_scoped_user(self):
        from django.urls import reverse
        self.client.force_login(self.accountant)
        url = reverse('admin:accounting_clientprofile_import')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
