# tests/accounting/test_rbac_round12.py
"""
Γύρος 12 — τελικός ανεξάρτητος έλεγχος:
- SharedLinkViewSet: created_by read-only, current-access scoping (ο
  δημιουργός που έχασε την ανάθεση δεν βλέπει/αλλάζει πλέον το link),
  see-all admin βλέπει όλα, PATCH σε ξένο client/document χωρίς enumeration
- DocumentRequestAdmin: shared_link FK περιορισμένο + server-side validation
  cross-client, inline received_document χωρίς shared admin state
- ClientCredentialViewSet: πανομοιότυπο 404 για ξένο και ανύπαρκτο πελάτη
- scrub_audit_pii: σωστό ελληνικό IBAN (27 χαρακτήρες), lowercase, με κενά
"""

import io

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings

from accounting.models import (
    ClientDocument, ClientProfile, DocumentRequest, SharedLink,
)
from common.models import AuditLog
from tests.accounting.secure_client import SecureAPIClient as APIClient
from tests.accounting.secure_client import SecureClient

LINKS_URL = '/accounting/api/v1/file-manager/shared-links/'


def make_role_user(username, role, clients=(), **extra):
    user = User.objects.create_user(username=username, password='x', **extra)
    user.groups.add(Group.objects.get(name=role))
    for c in clients:
        c.assigned_users.add(user)
    return User.objects.get(pk=user.pk)


class Round12Base(TestCase):
    client_class = SecureClient

    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.client_a = ClientProfile.objects.create(
            afm='123456789', eponimia='ΠΕΛΑΤΗΣ Α ΑΕ', email='a@example.gr',
        )
        cls.client_b = ClientProfile.objects.create(
            afm='987654321', eponimia='ΠΕΛΑΤΗΣ Β ΕΠΕ', email='b@example.gr',
        )
        cls.doc_a = ClientDocument.objects.create(
            client=cls.client_a, original_filename='a.pdf', filename='a.pdf',
        )
        cls.doc_b = ClientDocument.objects.create(
            client=cls.client_b, original_filename='b.pdf', filename='b.pdf',
        )
        cls.accountant = make_role_user('logistis12', 'Λογιστής', [cls.client_a])
        cls.manager = make_role_user('dioikitis12', 'Διαχειριστής')

    def api(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class SharedLinkScopingTest(Round12Base):
    def _make_link(self, client=None, document=None, created_by=None, name='link'):
        return SharedLink.objects.create(
            client=client, document=document, name=name,
            access_level='view', created_by=created_by,
        )

    def test_patch_created_by_is_ignored(self):
        link = self._make_link(client=self.client_a, created_by=self.accountant)
        other = User.objects.create_user(username='allos12', password='x')
        resp = self.api(self.accountant).patch(
            f'{LINKS_URL}{link.pk}/', {'created_by': other.pk}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        link.refresh_from_db()
        self.assertEqual(link.created_by, self.accountant)

    def test_creator_who_lost_assignment_loses_all_access(self):
        link = self._make_link(client=self.client_a, created_by=self.accountant)
        self.client_a.assigned_users.remove(self.accountant)
        api = self.api(User.objects.get(pk=self.accountant.pk))
        list_resp = api.get(LINKS_URL)
        self.assertEqual(list_resp.status_code, 200)
        ids = [item['id'] for item in list_resp.json().get('results', list_resp.json() if isinstance(list_resp.json(), list) else [])]
        self.assertNotIn(link.pk, ids)
        self.assertEqual(api.get(f'{LINKS_URL}{link.pk}/').status_code, 404)
        self.assertEqual(
            api.patch(f'{LINKS_URL}{link.pk}/', {'name': 'x'}, format='json').status_code,
            404,
        )
        self.assertEqual(api.delete(f'{LINKS_URL}{link.pk}/').status_code, 404)
        self.assertEqual(
            api.post(f'{LINKS_URL}{link.pk}/regenerate-token/').status_code, 404,
        )
        self.assertEqual(
            api.get(f'{LINKS_URL}{link.pk}/access-logs/').status_code, 404,
        )

    def test_document_only_link_visible_while_accessible(self):
        link = self._make_link(document=self.doc_a, created_by=self.accountant)
        api = self.api(self.accountant)
        self.assertEqual(api.get(f'{LINKS_URL}{link.pk}/').status_code, 200)
        self.client_a.assigned_users.remove(self.accountant)
        api = self.api(User.objects.get(pk=self.accountant.pk))
        self.assertEqual(api.get(f'{LINKS_URL}{link.pk}/').status_code, 404)

    def test_foreign_client_link_hidden_even_if_created_by_user(self):
        link = self._make_link(client=self.client_b, created_by=self.accountant)
        api = self.api(self.accountant)
        resp = api.get(LINKS_URL)
        data = resp.json()
        items = data.get('results', data if isinstance(data, list) else [])
        self.assertNotIn(link.pk, [item['id'] for item in items])
        self.assertEqual(api.get(f'{LINKS_URL}{link.pk}/').status_code, 404)

    def test_see_all_manager_sees_links_of_others(self):
        link = self._make_link(client=self.client_a, created_by=self.accountant)
        resp = self.api(self.manager).get(f'{LINKS_URL}{link.pk}/')
        self.assertEqual(resp.status_code, 200)

    def test_patch_to_foreign_client_or_document_rejected(self):
        link = self._make_link(client=self.client_a, created_by=self.accountant)
        api = self.api(self.accountant)
        resp = api.patch(
            f'{LINKS_URL}{link.pk}/', {'client': self.client_b.pk}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        resp2 = api.patch(
            f'{LINKS_URL}{link.pk}/', {'document': self.doc_b.pk}, format='json',
        )
        self.assertEqual(resp2.status_code, 400)
        # Ίδια συμπεριφορά για ανύπαρκτα ids — όχι enumeration
        resp3 = api.patch(
            f'{LINKS_URL}{link.pk}/', {'client': 999999}, format='json',
        )
        self.assertEqual(resp3.status_code, 400)
        link.refresh_from_db()
        self.assertEqual(link.client, self.client_a)
        self.assertIsNone(link.document)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class DocumentRequestAdminScopingTest(Round12Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff_accountant = make_role_user(
            'logistis12adm', 'Λογιστής', [cls.client_a], is_staff=True,
        )
        cls.link_a = SharedLink.objects.create(
            client=cls.client_a, name='link a', access_level='view',
            created_by=cls.staff_accountant,
        )
        cls.link_b = SharedLink.objects.create(
            client=cls.client_b, name='link b', access_level='view',
            created_by=cls.staff_accountant,
        )
        cls.doclink_b = SharedLink.objects.create(
            document=cls.doc_b, name='doclink b', access_level='view',
            created_by=cls.staff_accountant,
        )
        cls.factory = RequestFactory()

    def _model_admin(self):
        from django.contrib import admin as django_admin
        return django_admin.site._registry[DocumentRequest]

    def _request(self, user):
        request = self.factory.get('/456-admin/accounting/documentrequest/')
        request.user = user
        return request

    def test_shared_link_fk_choices_exclude_foreign_links(self):
        model_admin = self._model_admin()
        field = DocumentRequest._meta.get_field('shared_link')
        formfield = model_admin.formfield_for_foreignkey(
            field, self._request(self.staff_accountant),
        )
        qs = formfield.queryset
        self.assertIn(self.link_a, qs)
        self.assertNotIn(self.link_b, qs)
        self.assertNotIn(self.doclink_b, qs)

    def test_form_rejects_cross_client_shared_link(self):
        model_admin = self._model_admin()
        form_class = model_admin.get_form(self._request(self.manager))
        form = form_class(data={
            'client': self.client_a.pk,
            'shared_link': self.link_b.pk,
            'title': 'Αίτημα',
            'status': 'pending',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('shared_link', form.errors)

    def test_form_rejects_cross_client_document_link(self):
        model_admin = self._model_admin()
        form_class = model_admin.get_form(self._request(self.manager))
        form = form_class(data={
            'client': self.client_a.pk,
            'shared_link': self.doclink_b.pk,
            'title': 'Αίτημα',
            'status': 'pending',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('shared_link', form.errors)

    def test_inline_received_document_scoped_without_shared_state(self):
        from accounting.admin.clients import DocumentRequestItemInline
        from django.contrib import admin as django_admin
        inline = None
        for candidate in self._model_admin().inlines:
            if candidate is DocumentRequestItemInline:
                inline = candidate(DocumentRequest, django_admin.site)
        self.assertIsNotNone(inline)

        req_a = DocumentRequest.objects.create(
            client=self.client_a, title='Α', created_by=self.staff_accountant,
        )
        req_b = DocumentRequest.objects.create(
            client=self.client_b, title='Β', created_by=self.staff_accountant,
        )
        request = self._request(self.manager)
        formset_a = inline.get_formset(request, obj=req_a)
        formset_b = inline.get_formset(request, obj=req_b)
        # Κανένα request-specific state στο shared inline instance
        self.assertFalse(hasattr(inline, '_parent_request'))
        qs_a = formset_a.form.base_fields['received_document'].queryset
        qs_b = formset_b.form.base_fields['received_document'].queryset
        # Το πρώτο formset δεν «μολύνεται» από το δεύτερο
        self.assertIn(self.doc_a, qs_a)
        self.assertNotIn(self.doc_b, qs_a)
        self.assertIn(self.doc_b, qs_b)
        self.assertNotIn(self.doc_a, qs_b)

    def test_inline_crafted_post_with_foreign_document_rejected(self):
        from accounting.admin.clients import DocumentRequestItemInline
        from django.contrib import admin as django_admin
        inline = DocumentRequestItemInline(DocumentRequest, django_admin.site)
        req_a = DocumentRequest.objects.create(
            client=self.client_a, title='Α2', created_by=self.staff_accountant,
        )
        formset_class = inline.get_formset(self._request(self.manager), obj=req_a)
        prefix = formset_class.get_default_prefix()
        data = {
            f'{prefix}-TOTAL_FORMS': '1',
            f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
            f'{prefix}-0-label': 'Έγγραφο',
            f'{prefix}-0-category': '',
            # Crafted: έγγραφο ξένου πελάτη (εκτός του περιορισμένου queryset)
            f'{prefix}-0-received_document': str(self.doc_b.pk),
        }
        formset = formset_class(data, instance=req_a)
        self.assertFalse(formset.is_valid())


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class CredentialEnumerationTest(Round12Base):
    def _urls(self, client_pk):
        base = f'/accounting/api/v1/clients/{client_pk}/credentials/'
        return base

    def test_foreign_and_nonexistent_client_identical_404(self):
        api = self.api(self.accountant)
        for url_pk in (self.client_b.pk, 999999):
            base = self._urls(url_pk)
            list_resp = api.get(base)
            create_resp = api.post(
                base, {'service': 'TAXISNET', 'username': 'u'}, format='json',
            )
            detail_resp = api.get(f'{base}1/')
            reveal_resp = api.post(f'{base}1/reveal/', {}, format='json')
            for resp in (list_resp, create_resp, detail_resp, reveal_resp):
                self.assertEqual(
                    resp.status_code, 404,
                    f'{resp.request["PATH_INFO"]} → {resp.status_code}',
                )
        # Πανομοιότυπο body μεταξύ ξένου και ανύπαρκτου
        foreign = api.get(self._urls(self.client_b.pk)).json()
        missing = api.get(self._urls(999999)).json()
        self.assertEqual(foreign, missing)

    def test_assigned_client_still_works(self):
        api = self.api(self.accountant)
        base = self._urls(self.client_a.pk)
        self.assertEqual(api.get(base).status_code, 200)
        create = api.post(
            base, {'service': 'TAXISNET', 'username': 'u', 'secret': 's3cret'},
            format='json',
        )
        self.assertEqual(create.status_code, 201)

    def test_denied_audit_has_no_pii(self):
        api = self.api(self.accountant)
        api.get(self._urls(self.client_b.pk))
        for log in AuditLog.objects.order_by('-id')[:5]:
            self.assertNotIn(self.client_b.afm, log.description or '')


class ScrubIbanTest(TestCase):
    """Σωστό ελληνικό IBAN (27 χαρακτήρες) σε όλα τα text πεδία."""

    IBAN = 'GR1601101250000000012300695'  # 27 χαρακτήρες
    IBAN_SPACED = 'GR16 0110 1250 0000 0001 2300 695'

    def _scrub(self):
        call_command('scrub_audit_pii', '--apply', stdout=io.StringIO())

    def _log(self, description='', object_repr='', changes=None):
        return AuditLog.objects.create(
            action='update', description=description,
            object_repr=object_repr, changes=changes or {},
        )

    def test_full_iban_in_description_masked(self):
        log = self._log(description=f'Ενημέρωση IBAN {self.IBAN} πελάτη')
        self._scrub()
        log.refresh_from_db()
        self.assertNotIn(self.IBAN, log.description)
        self.assertIn('0695', log.description)

    def test_lowercase_iban_masked(self):
        log = self._log(description=f'iban: {self.IBAN.lower()}')
        self._scrub()
        log.refresh_from_db()
        self.assertNotIn(self.IBAN.lower(), log.description)

    def test_spaced_iban_masked_entirely(self):
        log = self._log(object_repr=f'Λογ/σμός {self.IBAN_SPACED}')
        self._scrub()
        log.refresh_from_db()
        self.assertNotIn(self.IBAN_SPACED, log.object_repr)
        # Δεν μένει μεγάλο αναγνωρίσιμο τμήμα (π.χ. τα πρώτα 12+)
        self.assertNotIn('GR16 0110 1250', log.object_repr)
        self.assertIn('695', log.object_repr)

    def test_structured_changes_iban_masked(self):
        log = self._log(changes={'iban': {'old': self.IBAN, 'new': ''}})
        self._scrub()
        log.refresh_from_db()
        self.assertNotIn(self.IBAN, str(log.changes))
        self.assertTrue(log.changes['iban']['old'].endswith('0695'))

    def test_already_masked_value_untouched(self):
        masked = '•' * 23 + '0695'
        log = self._log(description=f'IBAN {masked}',
                        changes={'iban': {'old': masked, 'new': ''}})
        self._scrub()
        log.refresh_from_db()
        self.assertEqual(log.changes['iban']['old'], masked)
        self.assertIn(masked, log.description)

    def test_unrelated_numbers_untouched(self):
        log = self._log(description='Τιμολόγιο #20260803 ποσό 1234.56')
        self._scrub()
        log.refresh_from_db()
        self.assertIn('20260803', log.description)
        self.assertIn('1234.56', log.description)


# =============================================================================
# Ευρήματα ανεξάρτητου sweep (γύρος 12β)
# =============================================================================

@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class NotificationsScopingTest(Round12Base):
    """notifications endpoints: view perm + scoping — όχι σκέτο auth/staff."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from datetime import date, timedelta
        from accounting.models import MonthlyObligation, ObligationType
        cls.otype = ObligationType.objects.create(code='ΦΠΑ12', name='ΦΠΑ12')
        yesterday = date.today() - timedelta(days=1)
        cls.obl_b = MonthlyObligation.objects.create(
            client=cls.client_b, obligation_type=cls.otype,
            year=yesterday.year, month=yesterday.month, deadline=yesterday,
            status='pending',
        )

    def test_api_requires_view_monthlyobligation(self):
        nobody = User.objects.create_user(username='n12', password='x')
        resp = self.api(nobody).get('/accounting/api/v1/notifications/')
        self.assertEqual(resp.status_code, 403)

    def test_api_scoped_no_foreign_client_names(self):
        resp = self.api(self.accountant).get('/accounting/api/v1/notifications/')
        self.assertEqual(resp.status_code, 200)
        body = str(resp.json())
        self.assertNotIn(self.client_b.eponimia, body)

    def test_legacy_view_scoped_and_needs_perm(self):
        staff_nobody = User.objects.create_user(
            username='sn12', password='x', is_staff=True,
        )
        self.client.force_login(staff_nobody)
        self.assertEqual(
            self.client.get('/accounting/notifications/').status_code, 403,
        )
        staff_accountant = make_role_user(
            'logistis12leg', 'Λογιστής', [self.client_a], is_staff=True,
        )
        self.client.force_login(staff_accountant)
        resp = self.client.get('/accounting/notifications/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.client_b.eponimia, resp.content.decode())


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class ObligationAdminScopingTest(Round12Base):
    """MonthlyObligation/ClientObligation admins: client scoping + perms
    στα custom views (bulk-assign, generate)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from datetime import date
        from accounting.models import (
            ClientObligation, MonthlyObligation, ObligationType,
        )
        cls.otype = ObligationType.objects.create(code='ΑΠΔ12', name='ΑΠΔ12')
        cls.mobl_b = MonthlyObligation.objects.create(
            client=cls.client_b, obligation_type=cls.otype,
            year=2026, month=7, deadline=date(2026, 7, 20),
        )
        cls.cobl_b, _ = ClientObligation.objects.get_or_create(client=cls.client_b)
        cls.staff_accountant = make_role_user(
            'logistis12obl', 'Λογιστής', [cls.client_a], is_staff=True,
        )
        cls.factory = RequestFactory()

    def _request(self, user, method='get', data=None):
        request = getattr(self.factory, method)('/456-admin/', data or {})
        request.user = user
        return request

    def test_monthly_obligation_admin_scoped(self):
        from django.contrib import admin as django_admin
        from accounting.models import MonthlyObligation
        model_admin = django_admin.site._registry[MonthlyObligation]
        qs = model_admin.get_queryset(self._request(self.staff_accountant))
        self.assertNotIn(self.mobl_b, qs)
        self.assertFalse(
            model_admin.has_change_permission(
                self._request(self.staff_accountant), self.mobl_b,
            )
        )
        # See-all βλέπει τα πάντα
        manager = make_role_user('dio12obl', 'Διαχειριστής', is_staff=True)
        self.assertIn(
            self.mobl_b,
            model_admin.get_queryset(self._request(manager)),
        )

    def test_client_obligation_admin_scoped(self):
        from django.contrib import admin as django_admin
        from accounting.models import ClientObligation
        model_admin = django_admin.site._registry[ClientObligation]
        qs = model_admin.get_queryset(self._request(self.staff_accountant))
        self.assertNotIn(self.cobl_b, qs)

    def test_bulk_assign_requires_change_perm(self):
        from django.contrib import admin as django_admin
        from django.core.exceptions import PermissionDenied
        from accounting.models import ClientObligation
        model_admin = django_admin.site._registry[ClientObligation]
        staff_nobody = User.objects.create_user(
            username='sn12b', password='x', is_staff=True,
        )
        with self.assertRaises(PermissionDenied):
            model_admin.bulk_assign_view(self._request(staff_nobody))

    def test_generate_requires_add_perm(self):
        from django.contrib import admin as django_admin
        from django.core.exceptions import PermissionDenied
        from accounting.models import MonthlyObligation
        model_admin = django_admin.site._registry[MonthlyObligation]
        staff_nobody = User.objects.create_user(
            username='sn12g', password='x', is_staff=True,
        )
        with self.assertRaises(PermissionDenied):
            model_admin.generate_obligations_view(self._request(staff_nobody))

    def test_bulk_assign_form_clients_scoped(self):
        from accounting.forms import BulkAssignForm, GenerateObligationsForm
        form = BulkAssignForm(user=self.staff_accountant)
        self.assertIn(self.client_a, form.fields['clients'].queryset)
        self.assertNotIn(self.client_b, form.fields['clients'].queryset)
        # Crafted POST με ξένο πελάτη απορρίπτεται server-side
        posted = BulkAssignForm(
            {'assign_mode': 'add', 'clients': [self.client_b.pk]},
            user=self.staff_accountant,
        )
        self.assertFalse(posted.is_valid())
        self.assertIn('clients', posted.errors)
        gen_form = GenerateObligationsForm(user=self.staff_accountant)
        self.assertNotIn(self.cobl_b, gen_form.fields['clients'].queryset)


@override_settings(ENFORCE_CLIENT_ASSIGNMENT=True)
class VoipTicketEmailAdminScopingTest(Round12Base):
    """VoIP/Ticket/Email admins: scoped σε πελάτη, unassigned κοινό triage."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from django.utils import timezone as tz
        from accounting.models import VoIPCall, Ticket
        cls.call_b = VoIPCall.objects.create(
            call_id='r12-call-b', phone_number='2101234567', client=cls.client_b,
            direction='inbound', status='missed', started_at=tz.now(),
        )
        cls.call_unassigned = VoIPCall.objects.create(
            call_id='r12-call-un', phone_number='2107654321', direction='inbound', status='missed',
            started_at=tz.now(),
        )
        cls.ticket_b = Ticket.objects.create(
            title='Ξένο ticket', client=cls.client_b,
        )
        cls.staff_accountant = make_role_user(
            'logistis12v', 'Λογιστής', [cls.client_a], is_staff=True,
        )
        cls.factory = RequestFactory()

    def _request(self, user):
        request = self.factory.get('/456-admin/')
        request.user = user
        return request

    def test_voip_admin_scoped_with_unassigned_visible(self):
        from django.contrib import admin as django_admin
        from accounting.models import VoIPCall
        model_admin = django_admin.site._registry[VoIPCall]
        qs = model_admin.get_queryset(self._request(self.staff_accountant))
        self.assertNotIn(self.call_b, qs)
        self.assertIn(self.call_unassigned, qs)

    def test_ticket_admin_scoped(self):
        from django.contrib import admin as django_admin
        from accounting.models import Ticket
        model_admin = django_admin.site._registry[Ticket]
        qs = model_admin.get_queryset(self._request(self.staff_accountant))
        self.assertNotIn(self.ticket_b, qs)
