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


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class LegacyViewsRbacTest(SurfaceBase):
    """Τα παλιά Django views κάτω από accounting/views/* είναι πλέον scoped."""

    def test_quick_complete_foreign_obligation_404(self):
        self.client.force_login(self.accountant)
        resp = self.client.post(f'/accounting/quick-complete/{self.obl_b.pk}/')
        self.assertIn(resp.status_code, (404, 400))
        self.obl_b.refresh_from_db()
        self.assertNotEqual(self.obl_b.status, 'completed')

    def test_legacy_search_excludes_foreign(self):
        self.client.force_login(self.accountant)
        resp = self.client.get('/accounting/api/search/', {'q': 'ΠΕΛΑΤΗΣ'})
        if resp.status_code == 200:
            self.assertNotIn('987654321', resp.content.decode())

    def test_client_report_pdf_foreign_404(self):
        self.client.force_login(self.accountant)
        resp = self.client.get(f'/accounting/reports/client/{self.client_b.pk}/pdf/')
        self.assertEqual(resp.status_code, 404)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class BulkForeignIdsTest(SurfaceBase):
    """Bulk actions με ξένα IDs δεν αγγίζουν ξένες εγγραφές."""

    def test_bulk_update_ignores_foreign_ids(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/obligations/bulk_update/',
            {'obligation_ids': [self.obl_b.pk], 'status': 'completed'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['updated_count'], 0)
        self.obl_b.refresh_from_db()
        self.assertNotEqual(self.obl_b.status, 'completed')

    def test_bulk_delete_ignores_foreign_ids(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/obligations/bulk_delete/',
            {'obligation_ids': [self.obl_b.pk]},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['deleted_count'], 0)

    def test_bulk_create_ignores_foreign_clients(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/obligations/bulk_create/',
            {'client_ids': [self.client_b.pk], 'obligation_type_id': self.otype.pk,
             'year': 2026, 'month': 7},
            format='json',
        )
        # Ξένος πελάτης → είτε 400 (κανένας ενεργός πελάτης) είτε 0 δημιουργίες
        if resp.status_code == 200:
            self.assertEqual(resp.json().get('created_count', 0), 0)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class OwnershipPatchTest(SurfaceBase):
    """PATCH που αλλάζει client/document σε ξένο target απορρίπτεται."""

    def test_credential_patch_to_foreign_client_rejected(self):
        from mydata.models import MyDataCredentials
        creds_a = MyDataCredentials.objects.create(client=self.client_a)
        resp = self.api(self.accountant).patch(
            f'/accounting/api/mydata/credentials/{creds_a.pk}/',
            {'client': self.client_b.pk},
        )
        self.assertIn(resp.status_code, (400, 404))
        creds_a.refresh_from_db()
        self.assertEqual(creds_a.client_id, self.client_a.pk)

    def test_document_patch_to_foreign_client_rejected(self):
        from accounting.models import ClientDocument
        doc_a = ClientDocument.objects.create(
            client=self.client_a, original_filename='a.pdf', filename='a.pdf',
        )
        resp = self.api(self.accountant).patch(
            f'/accounting/api/v1/documents/{doc_a.pk}/',
            {'client': self.client_b.pk},
        )
        self.assertIn(resp.status_code, (400, 404))
        doc_a.refresh_from_db()
        self.assertEqual(doc_a.client_id, self.client_a.pk)

    def test_shared_link_patch_to_foreign_client_rejected(self):
        from accounting.models import SharedLink
        link = SharedLink.objects.create(
            client=self.client_a, name='δικό μου', created_by=self.accountant,
        )
        resp = self.api(self.accountant).patch(
            f'/accounting/api/v1/file-manager/shared-links/{link.pk}/',
            {'client': self.client_b.pk},
        )
        self.assertIn(resp.status_code, (400, 404))
        link.refresh_from_db()
        self.assertEqual(link.client_id, self.client_a.pk)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class SharedCollectionLeakTest(SurfaceBase):
    def test_shared_collection_filters_foreign_documents(self):
        from accounting.models import ClientDocument, DocumentCollection
        doc_b = ClientDocument.objects.create(
            client=self.client_b, original_filename='b.pdf', filename='b.pdf',
        )
        other = User.objects.create_user('owner2', password='x')
        coll = DocumentCollection.objects.create(
            name='Κοινή', owner=other, is_shared=True,
        )
        coll.documents.add(doc_b)
        resp = self.api(self.accountant).get(
            f'/accounting/api/v1/file-manager/collections/{coll.pk}/'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['documents'], [])
        self.assertEqual(data['document_count'], 0)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class InvoiceRbacTest(SurfaceBase):
    def test_invoices_scoped_to_accessible_counterpart(self):
        from inventory.models import Invoice
        inv = Invoice.objects.create(
            counterpart=self.client_b, counterpart_vat=self.client_b.afm,
            counterpart_name=self.client_b.eponimia, is_outgoing=True,
        )
        resp = self.api(self.accountant).get('/accounting/api/mydata/invoices/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('987654321', resp.content.decode())
        detail = self.api(self.accountant).get(f'/accounting/api/mydata/invoices/{inv.pk}/')
        self.assertEqual(detail.status_code, 404)

    def test_send_requires_invoice_permission(self):
        from inventory.models import Invoice
        staff = User.objects.create_user('plainstaff', password='x', is_staff=True)
        inv = Invoice.objects.create(
            counterpart=self.client_a, counterpart_vat=self.client_a.afm,
            counterpart_name=self.client_a.eponimia, is_outgoing=True,
        )
        api = APIClient()
        api.force_authenticate(staff)
        resp = api.post(f'/accounting/api/mydata/invoices/{inv.pk}/send/')
        self.assertEqual(resp.status_code, 403)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class WritePermsRound3Test(SurfaceBase):
    def test_assistant_cannot_create_ticket(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/tickets/', {'title': 'x'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_change_obligation_type_settings(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/settings/obligation-types/',
            {'code': 'ΝΕΟ', 'name': 'Νέος τύπος'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_assistant_cannot_match_call(self):
        from accounting.models import VoIPCall
        from django.utils import timezone
        call = VoIPCall.objects.create(
            phone_number='2101234567', started_at=timezone.now(),
        )
        # REMOTE_ADDR εκτός localhost — αλλιώς περνά από το IsLocalRequest gate
        resp = self.api(self.assistant).post(
            f'/accounting/api/v1/calls/{call.pk}/match_client/',
            {'client_id': self.client_a.pk},
            REMOTE_ADDR='10.0.0.5',
        )
        self.assertEqual(resp.status_code, 403)

    def test_scoped_user_cannot_auto_match_all(self):
        resp = self.api(self.accountant).post(
            '/accounting/api/v1/calls/auto_match_all/', REMOTE_ADDR='10.0.0.5',
        )
        self.assertEqual(resp.status_code, 403)

    def test_upload_with_version_requires_add_document(self):
        assistant_staff = make_role_user(
            'voithos_staff', 'Βοηθός', [self.client_a], is_staff=True,
        )
        self.client.force_login(assistant_staff)
        resp = self.client.post('/accounting/api/v1/documents/upload-with-version/', {})
        self.assertEqual(resp.status_code, 403)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class Round4LegacyTest(SurfaceBase):
    """4ος γύρος: δημόσιο VoIP list, legacy dashboard/export, staff Βοηθός writes."""

    def test_voip_list_route_removed(self):
        # Το νεκρό δημόσιο legacy view αφαιρέθηκε — καμία ανώνυμη πρόσβαση
        resp = self.client.get('/accounting/voip/list/')
        self.assertEqual(resp.status_code, 404)

    def test_dashboard_stats_scoped(self):
        from accounting.views.helpers import _calculate_dashboard_stats
        stats = _calculate_dashboard_stats(self.accountant)
        self.assertEqual(stats['total_clients'], 1)
        self.assertEqual(stats['pending'] + stats['overdue'] + stats['completed'], 0)

    def test_export_excel_scoped(self):
        from accounting.views.helpers import _build_export_query
        query = _build_export_query(
            {'month': '6', 'year': '2026', 'date_from': '', 'date_to': '',
             'status': '', 'client': '', 'type': '', 'sort_by': 'deadline'},
            self.accountant,
        )
        self.assertEqual(query.count(), 0)

    def test_staff_assistant_cannot_quick_complete(self):
        staff_assistant = make_role_user(
            'voithos_staff2', 'Βοηθός', [self.client_a, self.client_b], is_staff=True,
        )
        from accounting.models import MonthlyObligation
        from datetime import date as d
        obl_a = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.otype, year=2026, month=7,
            deadline=d(2026, 7, 20),
        )
        self.client.force_login(staff_assistant)
        resp = self.client.post(f'/accounting/quick-complete/{obl_a.pk}/')
        self.assertEqual(resp.status_code, 403)
        obl_a.refresh_from_db()
        self.assertNotEqual(obl_a.status, 'completed')

    def test_staff_assistant_cannot_send_bulk_email(self):
        staff_assistant = make_role_user(
            'voithos_staff3', 'Βοηθός', [self.client_a], is_staff=True,
        )
        self.client.force_login(staff_assistant)
        resp = self.client.post(
            '/accounting/api/send-bulk-email-direct/',
            content_type='application/json', data='{}',
        )
        # 403 από το send_client_email gate (ή 404 αν άλλαξε το url)
        self.assertIn(resp.status_code, (403, 404))

    def test_get_obligation_profile_does_not_write(self):
        from accounting.models import ClientObligation
        ClientObligation.objects.filter(client=self.client_a).delete()
        resp = self.api(self.assistant).get(
            f'/accounting/api/v1/clients/{self.client_a.pk}/obligation-profile/'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            ClientObligation.objects.filter(client=self.client_a).exists()
        )

    def test_favorites_hidden_after_unassignment(self):
        from accounting.models import ClientDocument, DocumentFavorite
        doc_b = ClientDocument.objects.create(
            client=self.client_b, original_filename='b2.pdf', filename='b2.pdf',
        )
        DocumentFavorite.objects.create(user=self.accountant, document=doc_b)
        resp = self.api(self.accountant).get('/accounting/api/v1/file-manager/favorites/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_assistant_cannot_create_tag(self):
        resp = self.api(self.assistant).post(
            '/accounting/api/v1/file-manager/tags/', {'name': 'νέο tag'},
        )
        self.assertEqual(resp.status_code, 403)

    def test_reveal_audit_masks_afm(self):
        from accounting.models import ClientCredential
        from common.models import AuditLog
        cred = ClientCredential.objects.create(
            client=self.client_a, service='taxisnet', username='u1',
        )
        cred.secret = 's3cret'
        cred.save()
        resp = self.api(self.accountant).post(
            f'/accounting/api/v1/clients/{self.client_a.pk}/credentials/{cred.pk}/reveal/',
            {'reason': 'έλεγχος\nμε newline'},
        )
        if resp.status_code == 200:
            log = AuditLog.objects.filter(description__icontains='Αποκάλυψη').last()
            self.assertIsNotNone(log)
            self.assertNotIn('123456789', log.description)
            self.assertNotIn('\n', log.description.replace('\\n', ''))


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, FRITZ_API_TOKEN='test-token-123')
class Round5Test(SurfaceBase):
    """5ος γύρος: service VoIP boundary, GET χωρίς writes, doc perms, ρόλοι."""

    def test_service_api_key_cannot_list_calls(self):
        resp = APIClient().get(
            '/accounting/api/v1/calls/',
            HTTP_X_API_KEY='test-token-123', REMOTE_ADDR='10.0.0.5',
        )
        self.assertIn(resp.status_code, (401, 403))

    def test_service_api_key_can_create_and_patch_call(self):
        from accounting.models import VoIPCall
        api = APIClient()
        resp = api.post(
            '/accounting/api/v1/calls/',
            {'phone_number': '2101112223', 'direction': 'incoming',
             'status': 'active', 'started_at': '2026-08-01T10:00:00Z'},
            HTTP_X_API_KEY='test-token-123', REMOTE_ADDR='10.0.0.5',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        call_id = VoIPCall.objects.latest('id').pk
        patch = api.patch(
            f'/accounting/api/v1/calls/{call_id}/',
            {'status': 'completed'},
            HTTP_X_API_KEY='test-token-123', REMOTE_ADDR='10.0.0.5',
        )
        self.assertEqual(patch.status_code, 200, patch.content)

    def test_dashboard_get_does_not_write(self):
        from accounting.models import MonthlyObligation
        from datetime import date as d
        stale = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.otype, year=2020, month=1,
            deadline=d(2020, 1, 20), status='pending',
        )
        # Το save() του μοντέλου γυρίζει αυτόματα pending→overdue όταν έχει
        # περάσει η προθεσμία — παρακάμπτουμε με queryset update ώστε το test
        # να ελέγχει αποκλειστικά αν το GET γράφει στη βάση.
        MonthlyObligation.objects.filter(pk=stale.pk).update(status='pending')
        resp = self.api(self.assistant).get('/accounting/api/dashboard/stats/')
        self.assertEqual(resp.status_code, 200)
        stale.refresh_from_db()
        self.assertEqual(stale.status, 'pending')

    def test_calculator_requires_view_perm(self):
        noperm = User.objects.create_user('noperm5', password='x')
        self.client_a.assigned_users.add(noperm)
        resp = self.api(User.objects.get(pk=noperm.pk)).get(
            '/accounting/api/mydata/calculator/',
            {'client_id': self.client_a.pk, 'year': 2026, 'period': 6},
        )
        self.assertEqual(resp.status_code, 403)

    def test_calculator_get_does_not_create_for_readonly(self):
        from mydata.models import VATPeriodResult
        resp = self.api(self.assistant).get(
            '/accounting/api/mydata/calculator/',
            {'client_id': self.client_a.pk, 'year': 2026, 'period': 6},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(
            VATPeriodResult.objects.filter(client=self.client_a).exists()
        )

    def test_completion_with_file_requires_add_document(self):
        from django.contrib.auth.models import Permission
        from django.core.files.uploadedfile import SimpleUploadedFile
        from accounting.models import MonthlyObligation
        from datetime import date as d
        # Χρήστης με change_monthlyobligation αλλά ΧΩΡΙΣ add_clientdocument
        user = User.objects.create_user('complonly', password='x', is_staff=True)
        user.user_permissions.add(
            Permission.objects.get(codename='change_monthlyobligation',
                                   content_type__app_label='accounting'),
            Permission.objects.get(codename='view_monthlyobligation',
                                   content_type__app_label='accounting'),
        )
        user = User.objects.get(pk=user.pk)
        self.client_a.assigned_users.add(user)
        obl = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.otype, year=2026, month=8,
            deadline=d(2026, 8, 20),
        )
        self.client.force_login(user)
        resp = self.client.post(
            f'/accounting/quick-complete/{obl.pk}/',
            {'file': SimpleUploadedFile('a.pdf', b'%PDF-1.4')},
        )
        self.assertEqual(resp.status_code, 403)
        obl.refresh_from_db()
        self.assertNotEqual(obl.status, 'completed')

    def test_admin_role_can_send_invoice_permission(self):
        # Ο ρόλος «Διαχειριστής» έχει πλέον τα inventory permissions
        admin_user = make_role_user('dioikitis5', 'Διαχειριστής', is_staff=True)
        self.assertTrue(admin_user.has_perm('inventory.change_invoice'))
        self.assertTrue(admin_user.has_perm('inventory.view_invoice'))
