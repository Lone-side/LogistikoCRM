# -*- coding: utf-8 -*-
"""
Γύρος 16 — final authorization & data-integrity closeout.

Καλύπτει:
1. Κεντρικό ClientDocument invariant (client == obligation.client_id,
   client == previous_version.client_id) σε model, filing service, API, admin.
2. Κοινός resolver email attachments (view_clientdocument, same-client,
   is_current, exact-set) — καμία αποστολή/μεταβολή πριν όλους τους ελέγχους.
3. myDATA dashboard credential aggregates gating + dedicated sync_vatdata
   permission για sync-first calculation + audit event.
4. DocumentRequest.create permission matrix (add_documentrequest +
   add_sharedlink πάντα, send_client_email μόνο όταν send_email=true).
5. Καμία διαρροή raw exception text στα Invoice send/cancel responses.

Κάθε test αποτυγχάνει πριν το fix και ελέγχει side effects (row counts,
obligation status, outbox, audit rows).
"""
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounting.models import (
    ClientDocument, ClientProfile, EmailTemplate, MonthlyObligation,
    ObligationType,
)
from tests.accounting.secure_client import SecureAPIClient, SecureClient

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='round16_test_')


def make_role_user(username, role, clients=(), **extra):
    user = User.objects.create_user(username=username, password='x', **extra)
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


def make_perm_user(username, codenames, clients=(), app_label='accounting'):
    user = User.objects.create_user(username=username, password='x')
    for codename in codenames:
        app = app_label
        if '.' in codename:
            app, codename = codename.split('.', 1)
        user.user_permissions.add(Permission.objects.get(
            codename=codename, content_type__app_label=app))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


def _doc(client, obligation=None, previous_version=None, is_current=True,
         name='f.pdf'):
    """Δημιουργεί ClientDocument παρακάμπτοντας το save-invariant μόνο όταν
    χρειάζεται καθαρή εγγραφή (π.χ. same-client)."""
    doc = ClientDocument(
        client=client, obligation=obligation,
        previous_version=previous_version, is_current=is_current,
        original_filename=name, filename=name, file_type='pdf', file_size=6)
    doc.file.save(name, ContentFile(b'%PDF-1'), save=False)
    doc.save()
    return doc


# ---------------------------------------------------------------------------
# 1. Κεντρικό ClientDocument invariant
# ---------------------------------------------------------------------------
@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ClientDocumentInvariantTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.ob_type = ObligationType.objects.create(name='ΦΠΑ16', is_active=True)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')
        self.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company',
            email='b@example.com')
        self.ob_b = MonthlyObligation.objects.create(
            client=self.client_b, obligation_type=self.ob_type, month=1,
            year=2026, deadline=timezone.now().date())

    def test_model_clean_rejects_cross_client_obligation(self):
        doc = ClientDocument(client=self.client_a, obligation=self.ob_b,
                             original_filename='x.pdf', filename='x.pdf',
                             file_type='pdf', file_size=1)
        with self.assertRaises(ValidationError):
            doc.clean()

    def test_model_save_rejects_cross_client_obligation(self):
        before = ClientDocument.objects.count()
        doc = ClientDocument(client=self.client_a, obligation=self.ob_b,
                             original_filename='x.pdf', filename='x.pdf',
                             file_type='pdf', file_size=1)
        doc.file.save('x.pdf', ContentFile(b'%PDF-1'), save=False)
        with self.assertRaises(ValidationError):
            doc.save()
        # Καμία εγγραφή δεν γράφτηκε
        self.assertEqual(ClientDocument.objects.count(), before)

    def test_model_save_rejects_cross_client_previous_version(self):
        prev = _doc(self.client_b)  # previous_version ανήκει στον Β
        doc = ClientDocument(client=self.client_a, previous_version=prev,
                             original_filename='y.pdf', filename='y.pdf',
                             file_type='pdf', file_size=1)
        doc.file.save('y.pdf', ContentFile(b'%PDF-1'), save=False)
        with self.assertRaises(ValidationError):
            doc.save()

    def test_same_client_obligation_allowed(self):
        ob_a = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.ob_type, month=2,
            year=2026, deadline=timezone.now().date())
        doc = _doc(self.client_a, obligation=ob_a)
        self.assertEqual(doc.obligation_id, ob_a.id)

    def test_filing_service_rejects_mismatch(self):
        """
        Ο cross-client έλεγχος ισχύει ΚΑΙ για πλήρως εξουσιοδοτημένο
        χρήστη — δεν είναι υποπροϊόν του permission check.
        (Γύρος 21: το permission προηγείται πλέον του parsing, οπότε το
        σενάριο τρέχει με χρήστη που έχει add_clientdocument· η ουσία του
        test — ValidationError + κανένα νέο row — μένει ίδια.)
        """
        from accounting.services import filing
        user = make_perm_user(
            'r16_invariant', ['add_clientdocument', 'change_clientdocument'],
            [self.client_a, self.client_b])
        before = ClientDocument.objects.count()
        upload = SimpleUploadedFile('r.pdf', b'%PDF-1', content_type='application/pdf')
        with self.assertRaises(ValidationError):
            filing.create_client_document(
                client=self.client_a, uploaded_file=upload,
                obligation=self.ob_b, user=user)
        self.assertEqual(ClientDocument.objects.count(), before)


# ---------------------------------------------------------------------------
# 1b. API: attach_to_obligation + generic update + filter errors
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA)
class DocumentApiInvariantTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.ob_type = ObligationType.objects.create(name='ΦΠΑ16b', is_active=True)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        self.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company')
        # Χρήστης με πρόσβαση και στους δύο πελάτες + πλήρη doc perms
        self.user = make_perm_user(
            'docapi', ['view_clientprofile', 'view_clientdocument',
                       'change_clientdocument', 'add_clientdocument',
                       'view_monthlyobligation'],
            [self.client_a, self.client_b])
        self.api = SecureAPIClient()
        self.api.force_authenticate(self.user)
        self.doc_a = _doc(self.client_a)
        self.ob_b = MonthlyObligation.objects.create(
            client=self.client_b, obligation_type=self.ob_type, month=1,
            year=2026, deadline=timezone.now().date())

    def test_attach_to_obligation_cross_client_404_no_mutation(self):
        resp = self.api.post(
            f'/accounting/api/v1/documents/{self.doc_a.id}/attach-to-obligation/',
            {'obligation_id': self.ob_b.id}, format='multipart')
        self.assertEqual(resp.status_code, 404, resp.content)
        self.doc_a.refresh_from_db()
        self.assertIsNone(self.doc_a.obligation_id)

    def test_attach_to_obligation_same_client_ok(self):
        # Γύρος 19: το attach απαιτεί συμβατή περίοδο document↔obligation
        now = timezone.now()
        ob_a = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.ob_type,
            month=now.month, year=now.year, deadline=now.date())
        resp = self.api.post(
            f'/accounting/api/v1/documents/{self.doc_a.id}/attach-to-obligation/',
            {'obligation_id': ob_a.id}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.doc_a.refresh_from_db()
        self.assertEqual(self.doc_a.obligation_id, ob_a.id)

    def test_generic_update_cross_client_obligation_rejected(self):
        resp = self.api.patch(
            f'/accounting/api/v1/documents/{self.doc_a.id}/',
            {'obligation': self.ob_b.id}, format='multipart')
        self.assertIn(resp.status_code, (400, 404), resp.content)
        self.doc_a.refresh_from_db()
        self.assertIsNone(self.doc_a.obligation_id)

    def test_invalid_year_filter_400_not_500(self):
        resp = self.api.get('/accounting/api/v1/documents/?year=notanumber')
        self.assertEqual(resp.status_code, 400, resp.content)


# ---------------------------------------------------------------------------
# 2. Email attachment resolver
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailAttachmentResolverTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')
        self.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company',
            email='b@example.com')
        self.doc_a = _doc(self.client_a)
        self.doc_b = _doc(self.client_b)
        # stale (μη τρέχουσα) έκδοση του client_a
        self.doc_a_old = _doc(self.client_a, is_current=False, name='old.pdf')

    def _send(self, user, payload):
        from django.core import mail
        mail.outbox = []
        c = SecureClient()
        c.force_login(User.objects.get(pk=user.pk))
        resp = c.post('/accounting/api/v1/email/send/', data=payload,
                      content_type='application/json')
        return resp, len(mail.outbox)

    def test_foreign_attachment_rejected_no_send(self):
        user = make_perm_user(
            'em_full', ['send_client_email', 'view_clientprofile',
                        'view_clientdocument'], [self.client_a])
        user.is_staff = True
        user.save()
        resp, sent = self._send(user, {
            'client_id': self.client_a.id, 'subject': 'S', 'body': 'B',
            'attachment_ids': [self.doc_b.id]})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(sent, 0)

    def test_stale_version_attachment_rejected(self):
        user = make_perm_user(
            'em_stale', ['send_client_email', 'view_clientprofile',
                         'view_clientdocument'], [self.client_a])
        user.is_staff = True
        user.save()
        resp, sent = self._send(user, {
            'client_id': self.client_a.id, 'subject': 'S', 'body': 'B',
            'attachment_ids': [self.doc_a_old.id]})
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(sent, 0)

    def test_without_view_clientdocument_403(self):
        user = make_perm_user(
            'em_noview', ['send_client_email', 'view_clientprofile'],
            [self.client_a])
        user.is_staff = True
        user.save()
        resp, sent = self._send(user, {
            'client_id': self.client_a.id, 'subject': 'S', 'body': 'B',
            'attachment_ids': [self.doc_a.id]})
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(sent, 0)

    def test_valid_current_own_attachment_ok(self):
        user = make_perm_user(
            'em_ok', ['send_client_email', 'view_clientprofile',
                      'view_clientdocument'], [self.client_a])
        user.is_staff = True
        user.save()
        resp, sent = self._send(user, {
            'client_id': self.client_a.id, 'subject': 'S', 'body': 'B',
            'attachment_ids': [self.doc_a.id]})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(sent, 1)


# ---------------------------------------------------------------------------
# 2b. complete_and_notify — invalid template → 404, καμία ολοκλήρωση
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CompleteAndNotifyTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.ob_type = ObligationType.objects.create(name='ΦΠΑ16c', is_active=True)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')
        self.ob = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.ob_type, month=1,
            year=2026, deadline=timezone.now().date(), status='pending')
        self.manager = make_role_user('cn_mgr', 'Διαχειριστής', [self.client_a])

    def test_invalid_template_404_no_completion(self):
        from django.core import mail
        mail.outbox = []
        c = SecureAPIClient()
        c.force_authenticate(self.manager)
        resp = c.post(
            f'/accounting/api/v1/obligations/{self.ob.id}/complete-and-notify/',
            {'send_email': 'true', 'email_template_id': 999999}, format='multipart')
        self.assertEqual(resp.status_code, 404, resp.content)
        self.ob.refresh_from_db()
        self.assertEqual(self.ob.status, 'pending')
        self.assertEqual(len(mail.outbox), 0)


# ---------------------------------------------------------------------------
# 3. myDATA dashboard aggregates + sync_vatdata permission
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class MyDataSyncPermTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='ΦΠΑ ΑΕ', eidos_ipoxreou='company')

    def api(self, user):
        c = SecureAPIClient()
        c.force_authenticate(user)
        return c

    def _period(self):
        from mydata.models import VATPeriodResult
        return VATPeriodResult.objects.create(
            client=self.client_a, year=2026, period=1, period_type='monthly')

    def test_dashboard_hides_credential_aggregates_without_perm(self):
        user = make_perm_user(
            'md_nocred', ['view_clientprofile', 'mydata.view_vatrecord'],
            [self.client_a])
        resp = self.api(user).get('/accounting/api/mydata/dashboard/')
        self.assertEqual(resp.status_code, 200, resp.content)
        overview = resp.json().get('overview', {})
        self.assertIn('clients_with_credentials', overview)
        self.assertIsNone(overview.get('clients_with_credentials'))
        self.assertIsNone(overview.get('verified_credentials'))

    def test_dashboard_shows_aggregates_with_perm(self):
        user = make_perm_user(
            'md_cred', ['view_clientprofile', 'mydata.view_vatrecord',
                        'mydata.view_mydatacredentials'],
            [self.client_a])
        resp = self.api(user).get('/accounting/api/mydata/dashboard/')
        self.assertEqual(resp.status_code, 200, resp.content)
        overview = resp.json().get('overview', {})
        self.assertIsNotNone(overview.get('clients_with_credentials'))

    def test_sync_first_requires_sync_vatdata_403(self):
        period = self._period()
        # change_vatperiodresult αλλά ΧΩΡΙΣ sync_vatdata
        user = make_perm_user(
            'md_nosync', ['view_clientprofile',
                          'mydata.change_vatperiodresult',
                          'mydata.view_vatperiodresult'], [self.client_a])
        resp = self.api(user).post(
            f'/accounting/api/mydata/periods/{period.id}/calculate/',
            {'sync_first': True}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_sync_first_with_perm_writes_audit(self):
        from common.models import AuditLog
        period = self._period()
        user = make_perm_user(
            'md_sync', ['view_clientprofile',
                        'mydata.change_vatperiodresult',
                        'mydata.view_vatperiodresult',
                        'mydata.sync_vatdata'], [self.client_a])
        before = AuditLog.objects.filter(model_name='MyDataSync').count()
        with mock.patch(
                'mydata.views.VATPeriodResultViewSet._sync_period_months',
                return_value=None):
            resp = self.api(user).post(
                f'/accounting/api/mydata/periods/{period.id}/calculate/',
                {'sync_first': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        after = AuditLog.objects.filter(model_name='MyDataSync').count()
        self.assertEqual(after, before + 1)
        # Το audit description δεν περιέχει ολόκληρο ΑΦΜ
        entry = AuditLog.objects.filter(
            model_name='MyDataSync').latest('id')
        self.assertNotIn(self.client_a.afm, entry.description)

    def test_simple_calculate_allowed_without_sync_perm(self):
        period = self._period()
        user = make_perm_user(
            'md_simple', ['view_clientprofile',
                          'mydata.change_vatperiodresult',
                          'mydata.view_vatperiodresult'], [self.client_a])
        resp = self.api(user).post(
            f'/accounting/api/mydata/periods/{period.id}/calculate/',
            {'sync_first': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)


# ---------------------------------------------------------------------------
# 4. DocumentRequest.create permission matrix
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PORTAL_EMAIL_SYNC=True)
class DocumentRequestCreatePermTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')

    def api(self, user):
        c = SecureAPIClient()
        c.force_authenticate(user)
        return c

    def _payload(self, **over):
        data = {'client_id': self.client_a.id, 'title': 'Αίτημα',
                'items': [{'label': 'Τιμολόγιο', 'category': ''}],
                'send_email': False}
        data.update(over)
        return data

    def test_create_requires_add_sharedlink(self):
        from accounting.models import DocumentRequest
        # add_documentrequest αλλά ΧΩΡΙΣ add_sharedlink
        user = make_perm_user(
            'dr_nolink', ['view_clientprofile', 'add_documentrequest',
                          'view_documentrequest'], [self.client_a])
        before = DocumentRequest.objects.count()
        resp = self.api(user).post(
            '/accounting/api/v1/document-requests/', self._payload(),
            format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(DocumentRequest.objects.count(), before)

    def test_send_email_true_requires_send_client_email(self):
        from accounting.models import DocumentRequest
        from django.core import mail
        mail.outbox = []
        user = make_perm_user(
            'dr_noemail', ['view_clientprofile', 'add_documentrequest',
                           'add_sharedlink', 'view_documentrequest'],
            [self.client_a])
        before = DocumentRequest.objects.count()
        resp = self.api(user).post(
            '/accounting/api/v1/document-requests/',
            self._payload(send_email=True), format='json')
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(DocumentRequest.objects.count(), before)
        self.assertEqual(len(mail.outbox), 0)

    def test_create_no_email_flag_no_send_perm_needed(self):
        from accounting.models import DocumentRequest
        user = make_perm_user(
            'dr_ok', ['view_clientprofile', 'add_documentrequest',
                      'add_sharedlink', 'view_documentrequest'],
            [self.client_a])
        resp = self.api(user).post(
            '/accounting/api/v1/document-requests/', self._payload(),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(DocumentRequest.objects.filter(
            client=self.client_a).count(), 1)


# ---------------------------------------------------------------------------
# 5. Invoice send/cancel — καμία διαρροή raw exception
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MYDATA_ISSUER_VAT='999863881')
class InvoiceErrorLeakTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company')
        cls.manager = make_role_user('inv_mgr', 'Διαχειριστής', [cls.client_a],
                                     is_staff=True)

    def _invoice(self):
        from inventory.models import Invoice, InvoiceItem
        inv = Invoice.objects.create(
            counterpart=self.client_a, is_outgoing=True,
            invoice_type='1.1', number='101',
            issue_date=timezone.now().date(), total_net=100, total_vat=24,
            total_gross=124)
        InvoiceItem.objects.create(
            invoice=inv, line_number=1, description='Υπηρεσία',
            quantity=1, unit='SRV', unit_price=100, net_value=100,
            vat_category=1, vat_amount=24)
        return inv

    def test_send_already_sent_controlled_message_no_traceback(self):
        """Ελεγχόμενο guard message (400), χωρίς raw traceback/exception class."""
        from inventory.models import Invoice
        inv = self._invoice()
        Invoice.objects.filter(pk=inv.pk).update(
            mydata_sent=True, mydata_mark=400000000000001)
        c = SecureAPIClient()
        c.force_authenticate(self.manager)
        with mock.patch('mydata.services.MyDataClient'):
            resp = c.post(f'/accounting/api/mydata/invoices/{inv.id}/send/',
                          {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        # controlled Greek guard message
        self.assertIn('ήδη', resp.json()['error'])
        # κανένα traceback marker / exception class / stack path
        body = str(resp.content)
        for marker in ('Traceback', 'ValueError', 'File \\"', 'site-packages'):
            self.assertNotIn(marker, body)

    def test_send_valueerror_no_internal_leak(self):
        """Απρόσμενο ValueError → 400 χωρίς traceback markers στο response."""
        inv = self._invoice()
        c = SecureAPIClient()
        c.force_authenticate(self.manager)
        with mock.patch('mydata.services.MyDataService') as MockSvc:
            MockSvc.return_value.submit_invoice.side_effect = ValueError(
                'controlled guard message')
            resp = c.post(f'/accounting/api/mydata/invoices/{inv.id}/send/',
                          {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        body = str(resp.content)
        for marker in ('Traceback', 'File \\"', 'site-packages'):
            self.assertNotIn(marker, body)
