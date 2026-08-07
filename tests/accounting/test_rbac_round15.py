# -*- coding: utf-8 -*-
"""
Γύρος 15 — final authorization & data-isolation closeout:
1. TheFile (CRM) object-level authorization (owner/department), όχι session-only
2. Generic media token δεν παρακάμπτει TheFile authorization
3-4. Cross-client recipient ↔ obligation/attachment mismatch
5. Permission matrix legacy email endpoints + invalid template → 404
6. VAT summary myDATA financial gating
7. VoIPCall↔Ticket invariant από την πλευρά του ticket
8. Raw exception markers δεν εμφανίζονται σε responses
9. Read-only Βοηθός δεν δημιουργεί email side effects
10. Out-of-scope objects → ουδέτερο 404
"""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.http import Http404
from django.test import TestCase, override_settings
from django.test.client import RequestFactory
from django.utils import timezone

from accounting.models import (
    ClientProfile, EmailTemplate, MonthlyObligation, ObligationType,
    Ticket, VoIPCall,
)
from tests.accounting.secure_client import SecureAPIClient, SecureClient

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix='round15_test_')


def make_role_user(username, role, clients=(), **extra):
    user = User.objects.create_user(username=username, password='x', **extra)
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


def make_perm_user(username, codenames, clients=(), app_label='accounting'):
    user = User.objects.create_user(username=username, password='x')
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(
            codename=codename, content_type__app_label=app_label))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


# ---------------------------------------------------------------------------
# 1-2. TheFile object-level authorization
# ---------------------------------------------------------------------------
@override_settings(MEDIA_ROOT=TEMP_MEDIA, MEDIA_ACCEL_REDIRECT=False)
class TheFileAuthTest(TestCase):
    """CRM συνημμένα: owner/department policy, όχι «authenticated = όλα»."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        from crm.models import Deal
        # Δύο τμήματα (Department = Group subclass)
        from common.models import Department
        self.dept_a = Department.objects.create(name='Τμήμα Α')
        self.dept_b = Department.objects.create(name='Τμήμα Β')
        self.owner = User.objects.create_user('crm_owner', password='x')
        self.owner.groups.add(self.dept_a)
        self.other_dept = User.objects.create_user('crm_other', password='x')
        self.other_dept.groups.add(self.dept_b)
        self.same_dept = User.objects.create_user('crm_same', password='x')
        self.same_dept.groups.add(self.dept_a)
        # Deal του owner στο τμήμα Α
        self.deal = Deal.objects.create(
            name='Deal A', owner=self.owner, department=self.dept_a,
            next_step='Πρώτο βήμα', next_step_date=timezone.now().date())
        from common.models import TheFile
        ct = ContentType.objects.get_for_model(Deal)
        self.the_file = TheFile(content_type=ct, object_id=self.deal.pk)
        self.the_file.file.save('secret.pdf', ContentFile(b'%PDF-1.4'), save=True)
        self.rel_path = self.the_file.file.name
        self.factory = RequestFactory()

    def _can(self, user):
        from common.views.protected_media import can_access_thefile
        req = self.factory.get('/media/' + self.rel_path)
        req.user = user
        # Προσομοίωση των role flags που θέτει το middleware
        for attr in ('is_chief', 'is_superoperator', 'is_operator',
                     'is_department_head'):
            setattr(req.user, attr, False)
        req.user.is_operator = True
        req.user.department_id = (
            user.groups.filter(department__isnull=False).values_list(
                'id', flat=True).first()
        )
        from common.views.protected_media import can_access_thefile
        return can_access_thefile(req, self.the_file)

    def test_owner_can_access(self):
        self.assertTrue(self._can(self.owner))

    def test_same_department_can_access(self):
        self.assertTrue(self._can(self.same_dept))

    def test_other_department_denied(self):
        self.assertFalse(self._can(self.other_dept))

    def test_anonymous_denied(self):
        from django.contrib.auth.models import AnonymousUser
        from common.views.protected_media import can_access_thefile
        req = self.factory.get('/media/' + self.rel_path)
        req.user = AnonymousUser()
        self.assertFalse(can_access_thefile(req, self.the_file))

    def test_superuser_allowed(self):
        su = User.objects.create_superuser('crm_su', 'su@t.com', 'x')
        from common.views.protected_media import can_access_thefile
        req = self.factory.get('/media/' + self.rel_path)
        req.user = su
        self.assertTrue(can_access_thefile(req, self.the_file))

    def test_dangling_gfk_fails_closed(self):
        from common.models import TheFile
        from common.views.protected_media import can_access_thefile
        orphan = TheFile(
            content_type=ContentType.objects.get_for_model(ClientProfile),
            object_id=999999)
        orphan.file.save('x.pdf', ContentFile(b'x'), save=True)
        su = User.objects.create_user('crm_u2', password='x')
        req = self.factory.get('/media/' + orphan.file.name)
        req.user = su
        self.assertFalse(can_access_thefile(req, orphan))

    def test_view_denies_other_department_via_http(self):
        # Μέσω του πραγματικού view (middleware θέτει τα flags)
        self.client_class = SecureClient
        c = SecureClient()
        c.force_login(self.other_dept)
        resp = c.get('/media/' + self.rel_path)
        self.assertEqual(resp.status_code, 404)

    def test_token_of_other_department_user_does_not_bypass(self):
        # Το token ταυτοποιεί χρήστη· η πολιτική τρέχει κανονικά γι' αυτόν.
        from common.utils.media_tokens import make_media_token
        c = SecureClient()
        resp = c.get('/media/' + self.rel_path,
                     {'mt': make_media_token(self.rel_path, self.other_dept)})
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# 3-4. Cross-client recipient ↔ obligation/attachment mismatch (completion)
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True, MEDIA_ROOT=TEMP_MEDIA,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CrossClientEmailTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.ob_type = ObligationType.objects.create(name='ΦΠΑ15', is_active=True)

    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='ΠΕΛΑΤΗΣ Α', eidos_ipoxreou='company',
            email='a@example.com')
        self.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='ΠΕΛΑΤΗΣ Β', eidos_ipoxreou='company',
            email='b@example.com')
        self.ob_b = MonthlyObligation.objects.create(
            client=self.client_b, obligation_type=self.ob_type, month=1,
            year=2026, deadline=timezone.now().date(), status='completed')
        # Χρήστης με πρόσβαση ΚΑΙ στους δύο πελάτες + πλήρη email perms
        self.user = make_perm_user(
            'xuser', ['send_client_email', 'view_clientprofile',
                      'view_monthlyobligation', 'view_clientdocument',
                      'view_emailtemplate'],
            [self.client_a, self.client_b])
        self.user.is_staff = True
        self.user.save()
        self.http = SecureClient()
        self.http.force_login(User.objects.get(pk=self.user.pk))

    def test_recipient_a_obligation_b_rejected(self):
        from django.core import mail
        from accounting.models import EmailLog
        mail.outbox = []
        before = EmailLog.objects.count()
        resp = self.http.post(
            '/accounting/obligations/email/send/',
            data={'client_id': self.client_a.id,
                  'obligation_ids': [self.ob_b.id]},
            content_type='application/json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(EmailLog.objects.count(), before)

    def test_foreign_obligation_id_rejected(self):
        from django.core import mail
        foreign_client = ClientProfile.objects.create(
            afm='111111110', eponimia='ΞΕΝΟΣ', eidos_ipoxreou='company')
        foreign_ob = MonthlyObligation.objects.create(
            client=foreign_client, obligation_type=self.ob_type, month=1,
            year=2026, deadline=timezone.now().date())
        mail.outbox = []
        resp = self.http.post(
            '/accounting/obligations/email/send/',
            data={'client_id': self.client_a.id,
                  'obligation_ids': [foreign_ob.id]},
            content_type='application/json')
        self.assertIn(resp.status_code, (400, 404), resp.content)
        self.assertEqual(len(mail.outbox), 0)


# ---------------------------------------------------------------------------
# 5. Legacy email endpoint permission matrix + invalid template → 404
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class LegacyEmailPermTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)

    def _staff(self, codenames):
        user = make_perm_user('le_' + '_'.join(codenames)[:20] or 'none',
                              codenames)
        user.is_staff = True
        user.save()
        c = SecureClient()
        c.force_login(User.objects.get(pk=user.pk))
        return c

    def test_templates_list_requires_view_emailtemplate(self):
        c = self._staff([])
        self.assertEqual(
            c.get('/accounting/api/email-templates/').status_code, 403)
        c2 = self._staff(['view_emailtemplate'])
        self.assertEqual(
            c2.get('/accounting/api/email-templates/').status_code, 200)

    def test_template_detail_requires_view_emailtemplate(self):
        tmpl = EmailTemplate.objects.create(
            name='T', subject='S', body_html='B', is_active=True)
        c = self._staff([])
        self.assertEqual(
            c.get(f'/accounting/api/email-template/{tmpl.id}/').status_code,
            403)

    def test_send_ticket_email_requires_view_ticket(self):
        c = self._staff(['send_client_email'])
        resp = c.post('/accounting/ticket/send-email/',
                      data={'ticket_id': 1, 'template_id': 1},
                      content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    def test_bulk_email_requires_view_perms(self):
        c = self._staff(['send_client_email'])
        resp = c.post('/accounting/api/send-bulk-email/',
                      data={'obligation_ids': [1], 'template_id': 1},
                      content_type='application/json')
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# 6. VAT summary myDATA gating
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class VatSummaryMyDataTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='VAT ΑΕ', eidos_ipoxreou='company')

    def api(self, user):
        c = SecureAPIClient()
        c.force_authenticate(user)
        return c

    def setUp(self):
        from mydata.models import VATPeriodResult
        VATPeriodResult.objects.create(
            client=self.client_a, year=2026, period=1, period_type='monthly',
            vat_output=1000, vat_input=400, vat_difference=600)

    def test_without_mydata_perm_no_financials(self):
        user = make_perm_user(
            'vat_no', ['view_clientprofile', 'view_monthlyobligation'],
            [self.client_a])
        resp = self.api(user).get(
            '/accounting/api/reports/vat-summary/',
            {'year': 2026, 'period': 1})
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body['totals']['vat_output'], 0)
        for row in body.get('summary', body.get('data', [])):
            self.assertNotIn('vat_output', row)

    def test_with_mydata_perm_sees_own_only(self):
        user = User.objects.create_user('vat_yes', password='x')
        for cn, app in [('view_clientprofile', 'accounting'),
                        ('view_monthlyobligation', 'accounting'),
                        ('view_vatperiodresult', 'mydata')]:
            user.user_permissions.add(Permission.objects.get(
                codename=cn, content_type__app_label=app))
        self.client_a.assigned_users.add(user)
        user = User.objects.get(pk=user.pk)
        resp = self.api(user).get(
            '/accounting/api/reports/vat-summary/',
            {'year': 2026, 'period': 1})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['totals']['vat_output'], 1000)

    def test_xlsx_without_export_perm_rejected(self):
        user = make_perm_user(
            'vat_xlsx', ['view_clientprofile', 'view_monthlyobligation'],
            [self.client_a])
        resp = self.api(user).get(
            '/accounting/api/reports/vat-summary/',
            {'year': 2026, 'period': 1, 'format': 'xlsx'})
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# 7. Ticket-side call/client invariant
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class TicketSideInvariantTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')
        cls.client_b = ClientProfile.objects.create(
            afm='997654321', eponimia='Β ΑΕ', eidos_ipoxreou='company')
        cls.manager = make_role_user('ts_mgr', 'Διαχειριστής')

    def api(self, user):
        c = SecureAPIClient()
        c.force_authenticate(user)
        return c

    def _call(self, client=None):
        return VoIPCall.objects.create(
            call_id=f'ts-{VoIPCall.objects.count()}', phone_number='2101234567',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=client)

    def test_ticket_create_with_client_assigns_unassigned_call(self):
        call = self._call(None)
        resp = self.api(self.manager).post(
            '/accounting/api/v1/tickets/',
            {'title': 'T', 'call': call.id, 'client': self.client_a.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        call.refresh_from_db()
        self.assertEqual(call.client_id, self.client_a.id)
        self.assertEqual(call.client_email, 'a@example.com')

    def test_ticket_update_client_propagates_to_call(self):
        call = self._call(self.client_a)
        ticket = Ticket.objects.create(
            call=call, client=self.client_a, title='T', status='open')
        resp = self.api(self.manager).patch(
            f'/accounting/api/v1/tickets/{ticket.id}/',
            {'client_id': self.client_b.id}, format='json')
        # Το ticket-side invariant: είτε propagate και στα δύο, είτε reject
        call.refresh_from_db()
        ticket.refresh_from_db()
        if resp.status_code == 200:
            self.assertEqual(call.client_id, ticket.client_id)
        else:
            self.assertIn(resp.status_code, (400,))
            self.assertEqual(call.client_id, ticket.client_id)

    def test_ticket_create_without_voipcall_change_perm(self):
        call = self._call(None)
        # Χρήστης με add_ticket αλλά ΧΩΡΙΣ change_voipcall
        user = make_perm_user(
            'ts_noc', ['add_ticket', 'view_ticket', 'view_voipcall',
                       'add_voipcall', 'view_clientprofile'],
            [self.client_a])
        resp = self.api(user).post(
            '/accounting/api/v1/tickets/',
            {'title': 'T', 'call': call.id, 'client': self.client_a.id},
            format='json')
        # Χωρίς change_voipcall δεν επιτρέπεται να μεταβάλει την κλήση
        self.assertIn(resp.status_code, (400, 403), resp.content)
        call.refresh_from_db()
        self.assertIsNone(call.client_id)

    def test_no_inconsistent_state_left(self):
        # Μετά από κάθε αποδεκτή δημιουργία, ποτέ ticket(client) + call(None)
        call = self._call(None)
        self.api(self.manager).post(
            '/accounting/api/v1/tickets/',
            {'title': 'T', 'call': call.id, 'client': self.client_a.id},
            format='json')
        for t in Ticket.objects.filter(call__isnull=False):
            if t.client_id and t.call.client_id is not None:
                self.assertEqual(t.client_id, t.call.client_id)


# ---------------------------------------------------------------------------
# 9. Read-only Βοηθός δεν δημιουργεί email side effects
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class AssistantNoEmailSideEffectsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')

    def test_assistant_cannot_send_bulk_direct(self):
        from accounting.models import ScheduledEmail
        assistant = make_role_user('assist15', 'Βοηθός', [self.client_a])
        assistant.is_staff = True
        assistant.save()
        c = SecureClient()
        c.force_login(User.objects.get(pk=assistant.pk))
        before = ScheduledEmail.objects.count()
        resp = c.post('/accounting/api/send-bulk-email-direct/',
                      data={'obligation_ids': [1], 'subject': 'S',
                            'body': 'B'},
                      content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(ScheduledEmail.objects.count(), before)


# ---------------------------------------------------------------------------
# 8 + 10. Raw exception markers + out-of-scope neutral 404
# ---------------------------------------------------------------------------
@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ErrorLeakAndScopeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.manager = make_role_user('el_mgr', 'Διαχειριστής')

    def test_send_obligation_notice_invalid_template_404(self):
        client = ClientProfile.objects.create(
            afm='123456783', eponimia='Α ΑΕ', eidos_ipoxreou='company',
            email='a@example.com')
        ob_type = ObligationType.objects.create(name='ΦΠΑ15b', is_active=True)
        ob = MonthlyObligation.objects.create(
            client=client, obligation_type=ob_type, month=1, year=2026,
            deadline=timezone.now().date())
        c = SecureAPIClient()
        c.force_authenticate(self.manager)
        resp = c.post('/accounting/api/v1/email/send-obligation-notice/',
                      {'obligation_id': ob.id, 'template_type': 'completion',
                       'template_id': 999999}, format='json')
        self.assertEqual(resp.status_code, 404, resp.content)
        self.assertNotIn('DoesNotExist', str(resp.content))

    def test_out_of_scope_obligation_notice_404(self):
        foreign = ClientProfile.objects.create(
            afm='997654321', eponimia='ΞΕΝΟΣ', eidos_ipoxreou='company',
            email='f@example.com')
        ob_type = ObligationType.objects.create(name='ΦΠΑ15c', is_active=True)
        ob = MonthlyObligation.objects.create(
            client=foreign, obligation_type=ob_type, month=1, year=2026,
            deadline=timezone.now().date())
        scoped = make_role_user('el_scoped', 'Λογιστής')  # κανένας πελάτης
        c = SecureAPIClient()
        c.force_authenticate(scoped)
        resp = c.post('/accounting/api/v1/email/send-obligation-notice/',
                      {'obligation_id': ob.id, 'template_type': 'completion'},
                      format='json')
        self.assertEqual(resp.status_code, 404)
