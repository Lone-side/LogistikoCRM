# -*- coding: utf-8 -*-
"""
Regression tests: permission gating στα custom Django Admin actions.

Ρίζα του προβλήματος: ένα `@admin.action` χωρίς `permissions=[...]` /
`allowed_permissions` είναι εκτελέσιμο από ΚΑΘΕ staff χρήστη που βλέπει
το changelist — δηλαδή και από read-only ρόλο (Βοηθός). Έτσι ένας
χρήστης με μόνο `view_*` μπορούσε να αλλάξει status, να στείλει email
και να ΔΙΑΓΡΑΨΕΙ κλήσεις/tickets.

Κάθε test κάνει πραγματικό POST στο admin changelist endpoint (όχι μόνο
έλεγχο του dropdown), ώστε να αποδεικνύεται ότι δεν υπάρχει server-side
bypass.
"""

from django.contrib.admin.sites import site
from django.contrib.auth.models import Permission, User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounting.models import (
    ClientProfile,
    MonthlyObligation,
    ObligationType,
    ScheduledEmail,
    Ticket,
    VoIPCall,
)


def perm(codename):
    return Permission.objects.get(
        codename=codename, content_type__app_label='accounting')


def make_staff(username, *codenames):
    user = User.objects.create_user(username, password='x', is_staff=True)
    for codename in codenames:
        user.user_permissions.add(perm(codename))
    return User.objects.get(pk=user.pk)  # καθαρό permission cache


def changelist_url(model):
    return reverse(
        f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')


def post_action(test_case, model, action, objects):
    """POST απευθείας στο changelist endpoint.

    `secure=True`: σε production config το SECURE_SSL_REDIRECT θα γύριζε
    301 και το action δεν θα έτρεχε ποτέ — τα αρνητικά tests θα περνούσαν
    κενά. Ο έλεγχος status 200 εγγυάται ότι το request όντως έφτασε στο
    changelist και το action ΑΠΟΡΡΙΦΘΗΚΕ από το permission gate, όχι από
    redirect/404.
    """
    response = test_case.client.post(
        changelist_url(model),
        {'action': action,
         '_selected_action': [str(obj.pk) for obj in objects]},
        follow=True, secure=True,
    )
    test_case.assertEqual(response.status_code, 200)
    return response


def post_action_raw(test_case, model, action, objects):
    """POST χωρίς assertion status — για fail-closed actions που γυρίζουν 403."""
    return test_case.client.post(
        changelist_url(model),
        {'action': action,
         '_selected_action': [str(obj.pk) for obj in objects]},
        secure=True,
    )


def available_actions(model, user):
    """Τα action names που το admin προσφέρει στον χρήστη."""
    from django.test import RequestFactory
    request = RequestFactory().get(changelist_url(model), secure=True)
    request.user = user
    return list(site._registry[model].get_actions(request).keys())



class _OwnedMixin:
    """Shared owner client + assigned-staff factory.

    Το cross-side access check των cascade deletes απαιτεί ανάθεση, οπότε
    τα positive-deletion tests πρέπει να τρέχουν με ανατεθειμένο χρήστη
    και αντικείμενα δεμένα σε πελάτη — ώστε να περνούν ΚΑΙ με
    ENFORCE_CLIENT_ASSIGNMENT=True (production config), όχι μόνο με το
    flag off. Οι assertions παραμένουν ίδιες.
    """
    def setUp(self):
        super().setUp()
        self.owner = ClientProfile.objects.create(
            afm='094014201', eponimia='OWNER')
        self._call_seq = 0

    def _su(self, username, *perms):
        user = make_staff(username, *perms)
        self.owner.assigned_users.add(user)
        return user

    def _mk_call(self, **extra):
        self._call_seq += 1
        params = dict(
            call_id=f'OWN-{self._call_seq}', phone_number='2101234567',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=self.owner)
        params.update(extra)
        return VoIPCall.objects.create(**params)


class AdminActionPermissionTestMixin:
    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm='094014201', eponimia='ΠΕΛΑΤΗΣ Α')
        self.client_b = ClientProfile.objects.create(
            afm='998877665', eponimia='ΠΕΛΑΤΗΣ Β')
        self.obligation_type = ObligationType.objects.create(
            name='ΦΠΑ', code='FPA')


class ObligationActionPermissionTest(AdminActionPermissionTestMixin, TestCase):
    """mark_as_completed / mark_as_pending → change_monthlyobligation."""

    def _obligation(self, client_profile, status='pending'):
        return MonthlyObligation.objects.create(
            client=client_profile, obligation_type=self.obligation_type,
            year=2026, month=1, deadline=timezone.now().date(), status=status)

    def test_readonly_staff_cannot_see_mark_as_completed(self):
        user = make_staff('obl_ro', 'view_monthlyobligation')
        actions = available_actions(MonthlyObligation, user)
        self.assertNotIn('mark_as_completed', actions)
        self.assertNotIn('mark_as_pending', actions)

    def test_readonly_staff_post_cannot_complete_obligation(self):
        """Το αποδεδειγμένο exploit #1 — άμεσο POST, όχι μόνο UI."""
        user = make_staff('obl_ro_post', 'view_monthlyobligation')
        obligation = self._obligation(self.client_a)
        self.client.force_login(user)

        post_action(self, MonthlyObligation,
                    'mark_as_completed', [obligation])

        obligation.refresh_from_db()
        self.assertEqual(obligation.status, 'pending')
        self.assertIsNone(obligation.completed_date)
        self.assertIsNone(obligation.completed_by)

    def test_readonly_staff_post_cannot_reset_obligation(self):
        user = make_staff('obl_ro_reset', 'view_monthlyobligation')
        obligation = self._obligation(self.client_a, status='completed')
        self.client.force_login(user)

        post_action(self, MonthlyObligation,
                    'mark_as_pending', [obligation])

        obligation.refresh_from_db()
        self.assertEqual(obligation.status, 'completed')

    def test_authorised_staff_can_complete_obligation(self):
        user = make_staff('obl_rw', 'view_monthlyobligation',
                          'change_monthlyobligation')
        # Ανάθεση ώστε το test να ισχύει και με ENFORCE_CLIENT_ASSIGNMENT=True
        # (όπως τρέχει το security-smoke job)
        self.client_a.assigned_users.add(user)
        obligation = self._obligation(self.client_a)
        self.client.force_login(user)

        self.assertIn('mark_as_completed',
                      available_actions(MonthlyObligation, user))
        post_action(self, MonthlyObligation,
                    'mark_as_completed', [obligation])

        obligation.refresh_from_db()
        self.assertEqual(obligation.status, 'completed')
        self.assertEqual(obligation.completed_by, user)


class ObligationScopingStillEnforcedTest(AdminActionPermissionTestMixin,
                                         TestCase):
    """Το permission gate ΔΕΝ αντικαθιστά το client scoping."""

    def test_scoped_user_cannot_touch_foreign_client_obligation(self):
        from django.test import override_settings

        user = make_staff('obl_scoped', 'view_monthlyobligation',
                          'change_monthlyobligation')
        self.client_a.assigned_users.add(user)
        mine = MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.obligation_type,
            year=2026, month=2, deadline=timezone.now().date(),
            status='pending')
        foreign = MonthlyObligation.objects.create(
            client=self.client_b, obligation_type=self.obligation_type,
            year=2026, month=2, deadline=timezone.now().date(),
            status='pending')
        self.client.force_login(user)

        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            post_action(self, MonthlyObligation,
                        'mark_as_completed', [mine, foreign])

        mine.refresh_from_db()
        foreign.refresh_from_db()
        self.assertEqual(mine.status, 'completed')
        self.assertEqual(foreign.status, 'pending')


class ObligationSendEmailPermissionTest(AdminActionPermissionTestMixin,
                                        TestCase):
    """send_completion_email → dedicated accounting.send_client_email."""

    def _completed_obligation(self):
        self.client_a.email = 'pelatis@example.com'
        self.client_a.save(update_fields=['email'])
        return MonthlyObligation.objects.create(
            client=self.client_a, obligation_type=self.obligation_type,
            year=2026, month=3, deadline=timezone.now().date(),
            status='completed')

    def test_view_only_staff_cannot_send_completion_email(self):
        user = make_staff('obl_mail_ro', 'view_monthlyobligation')
        obligation = self._completed_obligation()
        self.client.force_login(user)

        self.assertNotIn('send_completion_email',
                         available_actions(MonthlyObligation, user))
        post_action(self, MonthlyObligation,
                    'send_completion_email', [obligation])

        self.assertEqual(len(mail.outbox), 0)

    def test_change_permission_alone_does_not_allow_sending(self):
        """Το change_* ΔΕΝ πρέπει να δίνει δικαίωμα αποστολής."""
        user = make_staff('obl_mail_change', 'view_monthlyobligation',
                          'change_monthlyobligation')
        obligation = self._completed_obligation()
        self.client.force_login(user)

        self.assertNotIn('send_completion_email',
                         available_actions(MonthlyObligation, user))
        post_action(self, MonthlyObligation,
                    'send_completion_email', [obligation])

        self.assertEqual(len(mail.outbox), 0)

    def test_staff_with_send_permission_sees_action(self):
        user = make_staff('obl_mail_rw', 'view_monthlyobligation',
                          'send_client_email')
        self.client_a.assigned_users.add(user)
        self.assertIn('send_completion_email',
                      available_actions(MonthlyObligation, user))


class ScheduledEmailActionPermissionTest(TestCase):
    """send_now → send_client_email · cancel_emails → change_scheduledemail."""

    def _pending_email(self):
        return ScheduledEmail.objects.create(
            recipient_email='pelatis@example.com', subject='Θέμα',
            body_html='<p>Κείμενο</p>', send_at=timezone.now(),
            status='pending')

    def test_view_only_staff_cannot_send_now(self):
        user = make_staff('mail_ro', 'view_scheduledemail')
        scheduled = self._pending_email()
        self.client.force_login(user)

        self.assertNotIn('send_now', available_actions(ScheduledEmail, user))
        post_action(self, ScheduledEmail, 'send_now', [scheduled])

        scheduled.refresh_from_db()
        self.assertEqual(scheduled.status, 'pending')
        self.assertIsNone(scheduled.sent_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_view_only_staff_cannot_cancel_emails(self):
        user = make_staff('mail_ro_cancel', 'view_scheduledemail')
        scheduled = self._pending_email()
        self.client.force_login(user)

        self.assertNotIn('cancel_emails',
                         available_actions(ScheduledEmail, user))
        post_action(self, ScheduledEmail, 'cancel_emails', [scheduled])

        scheduled.refresh_from_db()
        self.assertEqual(scheduled.status, 'pending')

    def test_change_permission_allows_cancel_but_not_send(self):
        user = make_staff('mail_change', 'view_scheduledemail',
                          'change_scheduledemail')
        scheduled = self._pending_email()
        self.client.force_login(user)

        actions = available_actions(ScheduledEmail, user)
        self.assertIn('cancel_emails', actions)
        self.assertNotIn('send_now', actions)

        post_action(self, ScheduledEmail, 'cancel_emails', [scheduled])
        scheduled.refresh_from_db()
        self.assertEqual(scheduled.status, 'cancelled')
        self.assertEqual(len(mail.outbox), 0)

    def test_send_permission_alone_does_not_expose_send_now(self):
        # Γύρος Β: το send_now μεταβάλλει το ScheduledEmail — απαιτεί ΚΑΙ
        # change_scheduledemail (βλ. SendNowRequiresBothPermsTest)
        user = make_staff('mail_send', 'view_scheduledemail',
                          'send_client_email')
        self.assertNotIn('send_now', available_actions(ScheduledEmail, user))


class VoIPCallActionPermissionTest(TestCase):
    """VoIPCall: mark_as_* → change · delete_* → delete (+ ticket perms)."""

    def _call(self):
        return VoIPCall.objects.create(
            phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now())

    def test_view_only_staff_cannot_delete_calls(self):
        """Το αποδεδειγμένο exploit #2 — άμεσο POST."""
        user = make_staff('call_ro', 'view_voipcall')
        call = self._call()
        self.client.force_login(user)

        self.assertNotIn('delete_without_tickets',
                         available_actions(VoIPCall, user))
        post_action(self, VoIPCall, 'delete_without_tickets', [call])

        self.assertEqual(VoIPCall.objects.filter(pk=call.pk).count(), 1)

    def test_view_only_staff_cannot_change_call_resolution(self):
        user = make_staff('call_ro_change', 'view_voipcall')
        call = self._call()
        self.client.force_login(user)

        post_action(self, VoIPCall, 'mark_as_closed', [call])

        call.refresh_from_db()
        self.assertNotEqual(call.resolution, 'closed')

    def test_delete_without_change_ticket_is_not_enough(self):
        """Η ενέργεια τροποποιεί tickets (call=None) → χρειάζεται change_ticket."""
        user = make_staff('call_del_only', 'view_voipcall', 'delete_voipcall')
        call = self._call()
        self.client.force_login(user)

        self.assertNotIn('delete_without_tickets',
                         available_actions(VoIPCall, user))
        post_action(self, VoIPCall, 'delete_without_tickets', [call])
        self.assertEqual(VoIPCall.objects.filter(pk=call.pk).count(), 1)

    def test_cascade_delete_requires_delete_ticket(self):
        user = make_staff('call_cascade_no', 'view_voipcall',
                          'delete_voipcall')
        self.assertNotIn('delete_with_tickets',
                         available_actions(VoIPCall, user))

        # Το queryset-level gate απαιτεί πλέον και change_ticket
        # (η διαγραφή κλήσης τροποποιεί το ticket μέσω SET_NULL)
        full = make_staff('call_cascade_yes', 'view_voipcall',
                          'delete_voipcall', 'delete_ticket',
                          'change_ticket')
        self.assertIn('delete_with_tickets', available_actions(VoIPCall, full))

    def test_authorised_staff_can_delete_calls(self):
        user = make_staff('call_rw', 'view_voipcall', 'delete_voipcall',
                          'change_ticket')
        call = self._call()
        self.client.force_login(user)

        self.assertIn('delete_without_tickets',
                      available_actions(VoIPCall, user))
        post_action(self, VoIPCall, 'delete_without_tickets', [call])

        self.assertEqual(VoIPCall.objects.filter(pk=call.pk).count(), 0)

    def test_authorised_staff_can_change_call_resolution(self):
        user = make_staff('call_change', 'view_voipcall', 'change_voipcall')
        call = self._call()
        self.client.force_login(user)

        post_action(self, VoIPCall, 'mark_as_follow_up', [call])

        call.refresh_from_db()
        self.assertEqual(call.resolution, 'follow_up')


class TicketActionPermissionTest(TestCase):
    """Ticket: mark_as_* → change_ticket · delete_* → delete_ticket."""

    def _ticket(self, client_profile=None):
        return Ticket.objects.create(
            client=client_profile, title='Δοκιμή',
            description='Περιγραφή', status='open')

    def test_view_only_staff_cannot_change_ticket_status(self):
        user = make_staff('tk_ro', 'view_ticket')
        ticket = self._ticket()
        self.client.force_login(user)

        self.assertNotIn('mark_as_resolved', available_actions(Ticket, user))
        post_action(self, Ticket, 'mark_as_resolved', [ticket])

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'open')
        self.assertIsNone(ticket.resolved_at)

    def test_view_only_staff_cannot_delete_tickets(self):
        user = make_staff('tk_ro_del', 'view_ticket')
        ticket = self._ticket()
        self.client.force_login(user)

        post_action(self, Ticket, 'delete_without_calls', [ticket])

        self.assertEqual(Ticket.objects.filter(pk=ticket.pk).count(), 1)

    def test_cascade_delete_requires_delete_voipcall(self):
        partial = make_staff('tk_casc_no', 'view_ticket', 'delete_ticket')
        self.assertNotIn('delete_with_calls', available_actions(Ticket, partial))

        # Το queryset-level gate απαιτεί πλέον και change_voipcall
        # (το pre_delete signal του Ticket τροποποιεί την κλήση)
        full = make_staff('tk_casc_yes', 'view_ticket', 'delete_ticket',
                          'delete_voipcall', 'change_voipcall')
        self.assertIn('delete_with_calls', available_actions(Ticket, full))

    def test_authorised_staff_can_resolve_and_delete(self):
        user = make_staff('tk_rw', 'view_ticket', 'change_ticket',
                          'delete_ticket', 'change_voipcall')
        ticket = self._ticket()
        self.client.force_login(user)

        post_action(self, Ticket, 'mark_as_resolved', [ticket])
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'resolved')

        post_action(self, Ticket, 'delete_without_calls', [ticket])
        self.assertEqual(Ticket.objects.filter(pk=ticket.pk).count(), 0)


class ExportActionsUnchangedTest(AdminActionPermissionTestMixin, TestCase):
    """Τα export actions δεν αλλάζουν συμπεριφορά."""

    def test_export_still_requires_export_permission(self):
        without = make_staff('exp_no', 'view_monthlyobligation')
        self.assertNotIn('export_obligations_csv',
                         available_actions(MonthlyObligation, without))

        with_perm = make_staff('exp_yes', 'view_monthlyobligation',
                               'export_clientprofile')
        self.assertIn('export_obligations_csv',
                      available_actions(MonthlyObligation, with_perm))


class ClientProfileActionPermissionTest(TestCase):
    """mark_active / mark_inactive → change_clientprofile."""

    def setUp(self):
        self.profile = ClientProfile.objects.create(
            afm='094014201', eponimia='ΠΕΛΑΤΗΣ Α', is_active=True)

    def test_view_only_staff_cannot_see_actions(self):
        user = make_staff('cp_ro', 'view_clientprofile')
        actions = available_actions(ClientProfile, user)
        self.assertNotIn('mark_active', actions)
        self.assertNotIn('mark_inactive', actions)

    def test_view_only_staff_post_cannot_deactivate(self):
        user = make_staff('cp_ro_post', 'view_clientprofile')
        self.client.force_login(user)

        post_action(self, ClientProfile, 'mark_inactive', [self.profile])

        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_active)

    def test_view_only_staff_post_cannot_activate(self):
        user = make_staff('cp_ro_act', 'view_clientprofile')
        self.profile.is_active = False
        self.profile.save(update_fields=['is_active'])
        self.client.force_login(user)

        post_action(self, ClientProfile, 'mark_active', [self.profile])

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_active)

    def test_authorised_staff_can_toggle_active(self):
        user = make_staff('cp_rw', 'view_clientprofile',
                          'change_clientprofile')
        self.profile.assigned_users.add(user)
        self.client.force_login(user)

        self.assertIn('mark_inactive', available_actions(ClientProfile, user))
        post_action(self, ClientProfile, 'mark_inactive', [self.profile])

        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_active)


class CascadeDeleteRealityTest(_OwnedMixin, TestCase):
    """Τα cascade actions διαγράφουν ΠΡΑΓΜΑΤΙΚΑ και τα δύο μοντέλα.

    Το Ticket.call είναι SET_NULL — πριν το fix, το «Διαγραφή με tickets»
    άφηνε τα tickets ορφανά και το «Διαγραφή με κλήσεις» άφηνε τα tickets
    ζωντανά (το σχόλιο «cascade» ήταν λάθος).
    """

    def _pair(self):
        call = self._mk_call()
        ticket = Ticket.objects.create(
            client=self.owner, call=call, title='Δοκιμή',
            description='Περιγραφή', status='open')
        return call, ticket

    def test_delete_with_tickets_removes_both_rows(self):
        user = self._su('casc_call', 'view_voipcall', 'delete_voipcall',
                          'delete_ticket', 'change_ticket')
        call, ticket = self._pair()
        call_id, ticket_id = call.pk, ticket.pk
        self.client.force_login(user)

        post_action(self, VoIPCall, 'delete_with_tickets', [call])

        self.assertFalse(VoIPCall.objects.filter(pk=call_id).exists())
        self.assertFalse(Ticket.objects.filter(pk=ticket_id).exists())

    def test_delete_with_calls_removes_both_rows(self):
        user = self._su('casc_tk', 'view_ticket', 'delete_ticket',
                          'delete_voipcall', 'change_voipcall')
        call, ticket = self._pair()
        call_id, ticket_id = call.pk, ticket.pk
        self.client.force_login(user)

        post_action(self, Ticket, 'delete_with_calls', [ticket])

        self.assertFalse(Ticket.objects.filter(pk=ticket_id).exists())
        self.assertFalse(VoIPCall.objects.filter(pk=call_id).exists())

    def test_cascade_with_single_permission_deletes_nothing(self):
        """Μόνο delete_voipcall (χωρίς delete_ticket) → τίποτα δεν χάνεται."""
        user = make_staff('casc_half', 'view_voipcall', 'delete_voipcall',
                          'change_ticket')
        call, ticket = self._pair()
        self.client.force_login(user)

        self.assertNotIn('delete_with_tickets',
                         available_actions(VoIPCall, user))
        post_action(self, VoIPCall, 'delete_with_tickets', [call])

        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())

    def test_cascade_atomic_no_partial_delete(self):
        """Αποτυχία στο δεύτερο βήμα → rollback, κανένα row δεν χάνεται."""
        from unittest.mock import patch

        user = self._su('casc_atomic', 'view_voipcall', 'delete_voipcall',
                          'delete_ticket', 'change_ticket')
        call, ticket = self._pair()
        self.client.force_login(user)

        real_delete = VoIPCall.objects.filter(pk=call.pk).__class__.delete

        def boom(qs):
            if qs.model is VoIPCall:
                raise RuntimeError('προσομοίωση αποτυχίας')
            return real_delete(qs)

        with patch('django.db.models.QuerySet.delete', boom):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    changelist_url(VoIPCall),
                    {'action': 'delete_with_tickets',
                     '_selected_action': [str(call.pk)]},
                    secure=True)

        # Τα tickets διαγράφηκαν ΠΡΙΝ την αποτυχία των κλήσεων — το
        # atomic πρέπει να τα έχει επαναφέρει
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())


class BuiltinDeletePathsTest(_OwnedMixin, TestCase):
    """Built-in delete_selected / object delete_view: ο χρήστης χωρίς το
    permission του ΔΕΥΤΕΡΟΥ μοντέλου δεν διαγράφει/μεταβάλλει τίποτα."""

    def _pair(self):
        call = self._mk_call()
        ticket = Ticket.objects.create(
            client=self.owner, call=call, title='Δοκιμή',
            description='Περιγραφή', status='open')
        return call, ticket

    def test_builtin_delete_selected_call_requires_change_ticket(self):
        """delete_voipcall χωρίς change_ticket: το SET_NULL θα άλλαζε το
        Ticket → η διαγραφή απορρίπτεται."""
        user = make_staff('bi_call', 'view_voipcall', 'delete_voipcall')
        call, ticket = self._pair()
        self.client.force_login(user)

        self.assertNotIn('delete_selected', available_actions(VoIPCall, user))
        post_action(self, VoIPCall, 'delete_selected', [call])

        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())
        ticket.refresh_from_db()
        self.assertEqual(ticket.call_id, call.pk)

    def test_builtin_delete_selected_ticket_requires_change_voipcall(self):
        """delete_ticket χωρίς change_voipcall: το signal θα άλλαζε το
        VoIPCall → η διαγραφή απορρίπτεται."""
        user = make_staff('bi_tk', 'view_ticket', 'delete_ticket')
        call, ticket = self._pair()
        self.client.force_login(user)

        self.assertNotIn('delete_selected', available_actions(Ticket, user))
        post_action(self, Ticket, 'delete_selected', [ticket])

        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())

    def test_builtin_delete_selected_with_both_perms_works(self):
        user = self._su('bi_ok', 'view_ticket', 'delete_ticket',
                          'change_voipcall')
        call, ticket = self._pair()
        self.client.force_login(user)

        self.assertIn('delete_selected', available_actions(Ticket, user))
        # Το built-in ζητά επιβεβαίωση — δεύτερο POST με post=yes
        self.client.post(
            changelist_url(Ticket),
            {'action': 'delete_selected',
             '_selected_action': [str(ticket.pk)], 'post': 'yes'},
            secure=True)

        self.assertFalse(Ticket.objects.filter(pk=ticket.pk).exists())
        # SET_NULL/signal: η κλήση επιβιώνει, χωρίς δείκτη σε ticket
        call.refresh_from_db()
        self.assertFalse(call.ticket_created)

    def test_standard_object_delete_view_gated(self):
        user = make_staff('bi_obj', 'view_voipcall', 'delete_voipcall')
        call, ticket = self._pair()
        self.client.force_login(user)

        url = reverse('admin:accounting_voipcall_delete', args=[call.pk])
        response = self.client.post(url, {'post': 'yes'}, secure=True)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())

    def test_object_delete_without_linked_row_needs_only_own_perm(self):
        """Ticket ΧΩΡΙΣ κλήση: αρκεί το delete_ticket (obj-aware gate)."""
        user = make_staff('bi_solo', 'view_ticket', 'delete_ticket')
        ticket = Ticket.objects.create(
            title='Μόνο του', description='-', status='open')
        self.client.force_login(user)

        url = reverse('admin:accounting_ticket_delete', args=[ticket.pk])
        self.client.post(url, {'post': 'yes'}, secure=True)

        self.assertFalse(Ticket.objects.filter(pk=ticket.pk).exists())


class TicketDeleteViewDeleteCallTest(_OwnedMixin, TestCase):
    """TicketAdmin.delete_view με delete_call=1."""

    def _pair(self):
        call = self._mk_call()
        ticket = Ticket.objects.create(
            client=self.owner, call=call, title='Δοκιμή',
            description='Περιγραφή', status='open')
        return call, ticket

    def _delete_url(self, ticket):
        return reverse('admin:accounting_ticket_delete', args=[ticket.pk])

    def test_delete_call_without_delete_voipcall_denied(self):
        """Αρνητικό: delete_ticket + change_voipcall, ΟΧΙ delete_voipcall."""
        user = self._su('dv_no', 'view_ticket', 'delete_ticket',
                          'change_voipcall')
        call, ticket = self._pair()
        self.client.force_login(user)

        response = self.client.post(
            self._delete_url(ticket), {'delete_call': '1', 'post': 'yes'},
            secure=True)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())

    def test_delete_call_with_both_perms_removes_both_rows(self):
        user = self._su('dv_yes', 'view_ticket', 'delete_ticket',
                          'delete_voipcall', 'change_voipcall')
        call, ticket = self._pair()
        call_id, ticket_id = call.pk, ticket.pk
        self.client.force_login(user)

        self.client.post(
            self._delete_url(ticket), {'delete_call': '1', 'post': 'yes'},
            secure=True)

        self.assertFalse(Ticket.objects.filter(pk=ticket_id).exists())
        self.assertFalse(VoIPCall.objects.filter(pk=call_id).exists())

    def test_delete_call_scoped_foreign_client_denied(self):
        """Scoping: ticket ξένου πελάτη → ούτε με όλα τα permissions."""
        from django.test import override_settings

        user = make_staff('dv_scope', 'view_ticket', 'delete_ticket',
                          'delete_voipcall', 'change_voipcall')
        foreign = ClientProfile.objects.create(
            afm='998877665', eponimia='ΞΕΝΟΣ')
        call, ticket = self._pair()
        ticket.client = foreign
        ticket.save(update_fields=['client'])
        self.client.force_login(user)

        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            self.client.post(
                self._delete_url(ticket),
                {'delete_call': '1', 'post': 'yes'}, secure=True)

        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())


class SendNowRequiresBothPermsTest(TestCase):
    """send_now → send_client_email AND change_scheduledemail.

    Το send_now μεταβάλλει το ScheduledEmail (status/sent_at,
    mark_as_failed) — το send permission μόνο του δεν αρκεί.
    """

    def _pending_email(self):
        return ScheduledEmail.objects.create(
            recipient_email='pelatis@example.com', subject='Θέμα',
            body_html='<p>Κείμενο</p>', send_at=timezone.now(),
            status='pending')

    def test_send_permission_alone_is_not_enough(self):
        user = make_staff('sn_half', 'view_scheduledemail',
                          'send_client_email')
        scheduled = self._pending_email()
        self.client.force_login(user)

        self.assertNotIn('send_now', available_actions(ScheduledEmail, user))
        post_action(self, ScheduledEmail, 'send_now', [scheduled])

        scheduled.refresh_from_db()
        self.assertEqual(scheduled.status, 'pending')
        self.assertEqual(len(mail.outbox), 0)

    def test_both_permissions_expose_send_now(self):
        user = make_staff('sn_full', 'view_scheduledemail',
                          'send_client_email', 'change_scheduledemail')
        self.assertIn('send_now', available_actions(ScheduledEmail, user))


class VoIPCallLogAuditTrailTest(TestCase):
    """Τα VoIPCallLog (audit trail) επιβιώνουν της διαγραφής κλήσης."""

    def test_call_delete_preserves_logs(self):
        from accounting.models import VoIPCallLog

        user = make_staff('log_keep', 'view_voipcall', 'delete_voipcall',
                          'change_ticket')
        call = VoIPCall.objects.create(
            phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now())
        log = VoIPCallLog.objects.create(
            call=call, action='started', description='έναρξη')
        self.client.force_login(user)

        post_action(self, VoIPCall, 'delete_without_tickets', [call])

        self.assertFalse(VoIPCall.objects.filter(pk=call.pk).exists())
        log.refresh_from_db()
        self.assertIsNone(log.call_id)
        self.assertEqual(log.action, 'started')


class TicketDeleteSignalRollbackTest(_OwnedMixin, TestCase):
    """Αποτυχία ΒΔ στο pre_delete signal → rollback, το ticket επιβιώνει.

    Πριν το fix, το signal κατάπινε ΚΑΘΕ exception: το ticket διαγραφόταν
    και η κλήση έμενε με ticket_created=True προς ανύπαρκτο ticket.
    """

    def test_call_update_failure_rolls_back_ticket_delete(self):
        from unittest.mock import patch
        from django.db import DatabaseError

        user = self._su('sig_rb', 'view_ticket', 'delete_ticket',
                          'change_voipcall')
        call = self._mk_call(ticket_created=True)
        ticket = Ticket.objects.create(
            client=self.owner, call=call, title='Δοκιμή',
            description='-', status='open')
        self.client.force_login(user)

        with patch.object(VoIPCall, 'save',
                          side_effect=DatabaseError('προσομοίωση')):
            with self.assertRaises(DatabaseError):
                self.client.post(
                    changelist_url(Ticket),
                    {'action': 'delete_without_calls',
                     '_selected_action': [str(ticket.pk)]},
                    secure=True)

        # Rollback: το ticket ΔΕΝ διαγράφηκε, η κλήση συνεπής
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
        call.refresh_from_db()
        self.assertTrue(call.ticket_created)


class VoIPCallLogSnapshotTest(TestCase):
    """Snapshot πεδία: γεμίζουν στη δημιουργία, επιβιώνουν της διαγραφής."""

    def _call(self, client_profile=None):
        return VoIPCall.objects.create(
            phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now(),
            client=client_profile, call_id='ABC123')

    def test_snapshot_populated_on_create(self):
        from accounting.models import VoIPCallLog

        owner = ClientProfile.objects.create(
            afm='094014201', eponimia='ΠΕΛΑΤΗΣ Α')
        call = self._call(owner)
        log = VoIPCallLog.objects.create(
            call=call, action='started', description='έναρξη')

        self.assertEqual(log.client_id, owner.pk)
        self.assertEqual(log.call_reference, 'ABC123')
        self.assertEqual(log.phone_number, '2101234567')

    def test_snapshot_survives_call_delete_and_str_is_safe(self):
        from accounting.models import VoIPCallLog

        owner = ClientProfile.objects.create(
            afm='094014201', eponimia='ΠΕΛΑΤΗΣ Α')
        call = self._call(owner)
        log = VoIPCallLog.objects.create(call=call, action='started')

        call.delete()
        log.refresh_from_db()

        self.assertIsNone(log.call_id)
        self.assertEqual(log.client_id, owner.pk)
        self.assertEqual(log.phone_number, '2101234567')
        self.assertIn('2101234567', str(log))  # κανένα exception

    def test_str_without_phone_uses_reference(self):
        from accounting.models import VoIPCallLog

        log = VoIPCallLog.objects.create(
            call=None, call_reference='ABC123', action='started')
        self.assertIn('Διαγραμμένη κλήση ABC123', str(log))

    def test_call_link_shows_deleted_call_without_exception(self):
        from accounting.models import VoIPCallLog

        call = self._call()
        log = VoIPCallLog.objects.create(call=call, action='started')
        call.delete()
        log.refresh_from_db()

        admin_instance = site._registry[VoIPCallLog]
        text = admin_instance.call_link(log)
        self.assertIn('διαγραμμένη κλήση', text)
        self.assertIn('2101234567', text)

    def test_serializer_call_display_null_safe(self):
        from accounting.models import VoIPCallLog
        from accounting.serializers import VoIPCallLogSerializer

        call = self._call()
        log = VoIPCallLog.objects.create(call=call, action='started')
        call.delete()
        log.refresh_from_db()

        data = VoIPCallLogSerializer(log).data
        self.assertEqual(data['call_display'], '2101234567')


class VoIPCallLogScopingTest(TestCase):
    """Fail-closed scoping μέσω snapshot client (ENFORCE_CLIENT_ASSIGNMENT)."""

    def setUp(self):
        from accounting.models import VoIPCallLog

        self.owner = ClientProfile.objects.create(
            afm='094014201', eponimia='ΠΕΛΑΤΗΣ Α')
        self.other = ClientProfile.objects.create(
            afm='998877665', eponimia='ΠΕΛΑΤΗΣ Β')
        call = VoIPCall.objects.create(
            phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now(), client=self.owner)
        self.orphan_log = VoIPCallLog.objects.create(
            call=call, action='started')
        call.delete()
        self.orphan_log.refresh_from_db()
        # Legacy orphan: ούτε call ούτε client snapshot
        self.legacy_log = VoIPCallLog.objects.create(
            call=None, action='ended', description='legacy')

    def _visible_ids(self, user):
        from accounting.models import VoIPCallLog
        from django.test import RequestFactory

        request = RequestFactory().get('/', secure=True)
        request.user = user
        admin_instance = site._registry[VoIPCallLog]
        return set(admin_instance.get_queryset(request)
                   .values_list('id', flat=True))

    def test_assigned_user_sees_orphan_log_of_own_client(self):
        from django.test import override_settings

        user = make_staff('log_owner', 'view_voipcalllog')
        self.owner.assigned_users.add(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            visible = self._visible_ids(user)
        self.assertIn(self.orphan_log.pk, visible)
        self.assertNotIn(self.legacy_log.pk, visible)

    def test_foreign_user_does_not_see_orphan_log(self):
        from django.test import override_settings

        user = make_staff('log_foreign', 'view_voipcalllog')
        self.other.assigned_users.add(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            visible = self._visible_ids(user)
        self.assertNotIn(self.orphan_log.pk, visible)
        self.assertNotIn(self.legacy_log.pk, visible)

    def test_superuser_sees_legacy_orphan_logs(self):
        from django.test import override_settings

        superuser = User.objects.create_superuser('log_super', password='x')
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            visible = self._visible_ids(superuser)
        self.assertIn(self.orphan_log.pk, visible)
        self.assertIn(self.legacy_log.pk, visible)


class AdminDeletionAuditLogTest(_OwnedMixin, TestCase):
    """Τα custom deletes γράφουν επίσημα admin LogEntry deletion records."""

    def _pair(self):
        call = self._mk_call()
        ticket = Ticket.objects.create(
            client=self.owner, call=call, title='Δοκιμή',
            description='-', status='open')
        return call, ticket

    def _deletion_entries(self, model, object_id):
        from django.contrib.admin.models import DELETION, LogEntry
        from django.contrib.contenttypes.models import ContentType

        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(model),
            object_id=str(object_id), action_flag=DELETION)

    def test_delete_view_with_call_writes_two_log_entries(self):
        user = self._su('al_dv', 'view_ticket', 'delete_ticket',
                          'delete_voipcall', 'change_voipcall')
        call, ticket = self._pair()
        self.client.force_login(user)

        self.client.post(
            reverse('admin:accounting_ticket_delete', args=[ticket.pk]),
            {'delete_call': '1', 'post': 'yes'}, secure=True)

        self.assertFalse(Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertFalse(VoIPCall.objects.filter(pk=call.pk).exists())
        self.assertEqual(self._deletion_entries(Ticket, ticket.pk).count(), 1)
        self.assertEqual(self._deletion_entries(VoIPCall, call.pk).count(), 1)

    def test_delete_with_tickets_logs_both_models(self):
        user = self._su('al_cwt', 'view_voipcall', 'delete_voipcall',
                          'delete_ticket', 'change_ticket')
        call, ticket = self._pair()
        self.client.force_login(user)

        post_action(self, VoIPCall, 'delete_with_tickets', [call])

        self.assertEqual(self._deletion_entries(VoIPCall, call.pk).count(), 1)
        self.assertEqual(self._deletion_entries(Ticket, ticket.pk).count(), 1)

    def test_delete_without_tickets_logs_only_calls(self):
        """Το ticket αποσυνδέεται — ΔΕΝ πρέπει να γραφτεί deletion entry."""
        user = self._su('al_cnt', 'view_voipcall', 'delete_voipcall',
                          'change_ticket')
        call, ticket = self._pair()
        self.client.force_login(user)

        post_action(self, VoIPCall, 'delete_without_tickets', [call])

        self.assertEqual(self._deletion_entries(VoIPCall, call.pk).count(), 1)
        self.assertEqual(self._deletion_entries(Ticket, ticket.pk).count(), 0)
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())

    def test_delete_without_calls_logs_only_tickets(self):
        user = self._su('al_tnc', 'view_ticket', 'delete_ticket',
                          'change_voipcall')
        call, ticket = self._pair()
        self.client.force_login(user)

        post_action(self, Ticket, 'delete_without_calls', [ticket])

        self.assertEqual(self._deletion_entries(Ticket, ticket.pk).count(), 1)
        self.assertEqual(self._deletion_entries(VoIPCall, call.pk).count(), 0)
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())

    def test_delete_with_calls_logs_both_models(self):
        user = self._su('al_twc', 'view_ticket', 'delete_ticket',
                          'delete_voipcall', 'change_voipcall')
        call, ticket = self._pair()
        self.client.force_login(user)

        post_action(self, Ticket, 'delete_with_calls', [ticket])

        self.assertEqual(self._deletion_entries(Ticket, ticket.pk).count(), 1)
        self.assertEqual(self._deletion_entries(VoIPCall, call.pk).count(), 1)

    def test_rollback_leaves_no_misleading_log_entries(self):
        """Αποτυχία μέσα στο atomic → ούτε rows ούτε deletion entries."""
        from unittest.mock import patch

        user = self._su('al_rb', 'view_voipcall', 'delete_voipcall',
                          'delete_ticket', 'change_ticket')
        call, ticket = self._pair()
        self.client.force_login(user)

        real_delete = VoIPCall.objects.filter(pk=call.pk).__class__.delete

        def boom(qs):
            if qs.model is VoIPCall:
                raise RuntimeError('προσομοίωση αποτυχίας')
            return real_delete(qs)

        with patch('django.db.models.QuerySet.delete', boom):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    changelist_url(VoIPCall),
                    {'action': 'delete_with_tickets',
                     '_selected_action': [str(call.pk)]},
                    secure=True)

        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertEqual(self._deletion_entries(VoIPCall, call.pk).count(), 0)
        self.assertEqual(self._deletion_entries(Ticket, ticket.pk).count(), 0)


class TicketDeleteSignalNonDatabaseErrorTest(_OwnedMixin, TestCase):
    """Το signal κάνει fail closed για ΚΑΘΕ exception, όχι μόνο DatabaseError."""

    def test_runtime_error_rolls_back_ticket_delete(self):
        from unittest.mock import patch

        user = self._su('sig_rt', 'view_ticket', 'delete_ticket',
                          'change_voipcall')
        call = self._mk_call(ticket_created=True)
        ticket = Ticket.objects.create(
            client=self.owner, call=call, title='Δοκιμή',
            description='-', status='open')
        self.client.force_login(user)

        with patch.object(VoIPCall, 'save',
                          side_effect=RuntimeError('προσομοίωση')):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    changelist_url(Ticket),
                    {'action': 'delete_without_calls',
                     '_selected_action': [str(ticket.pk)]},
                    secure=True)

        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
        call.refresh_from_db()
        self.assertTrue(call.ticket_created)


# ============================================================================
# Γύρος Δ — adversarial review PR #179
# ============================================================================

class VoIPCallLogXSSTest(TestCase):
    """logs_display: το user-controlled description ΔΕΝ γίνεται ενεργό HTML."""

    def test_malicious_description_is_escaped(self):
        from accounting.models import VoIPCallLog

        call = VoIPCall.objects.create(
            call_id='XSS-1', phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now())
        payload = '<img src=x onerror=alert(1)>'
        VoIPCallLog.objects.create(
            call=call, action='ticket_created',
            description=f'Ticket #1 created: {payload}')

        admin_instance = site._registry[VoIPCall]
        html = str(admin_instance.logs_display(call))

        # Το payload εμφανίζεται escaped, όχι ως ενεργό tag
        self.assertNotIn('<img src=x onerror=alert(1)>', html)
        self.assertIn('&lt;img', html)
        self.assertIn('onerror=alert(1)&gt;', html)


class VoIPCallLogViewSetScopingTest(TestCase):
    """API `voip-call-logs`: model permission + snapshot-client scoping."""

    def setUp(self):
        from accounting.models import VoIPCallLog

        self.owner = ClientProfile.objects.create(
            afm='094014201', eponimia='ΠΕΛΑΤΗΣ Α')
        self.other = ClientProfile.objects.create(
            afm='998877665', eponimia='ΠΕΛΑΤΗΣ Β')
        own_call = VoIPCall.objects.create(
            call_id='VL-OWN', phone_number='2101111111', direction='incoming',
            status='missed', started_at=timezone.now(), client=self.owner)
        foreign_call = VoIPCall.objects.create(
            call_id='VL-FOREIGN', phone_number='2102222222',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=self.other)
        self.own_log = VoIPCallLog.objects.create(
            call=own_call, action='started')
        self.foreign_log = VoIPCallLog.objects.create(
            call=foreign_call, action='started')
        # Legacy orphan χωρίς client snapshot
        self.orphan_log = VoIPCallLog.objects.create(
            call=None, action='ended')

    def _list_ids(self, user):
        self.client.force_login(user)
        resp = self.client.get('/accounting/api/v1/voip-call-logs/', secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        results = data['results'] if isinstance(data, dict) else data
        return {row['id'] for row in results}

    def test_read_only_user_without_perm_forbidden(self):
        user = make_staff('vl_noperm')  # χωρίς view_voipcalllog
        self.client.force_login(user)
        resp = self.client.get('/accounting/api/v1/voip-call-logs/', secure=True)
        self.assertEqual(resp.status_code, 403)

    def test_assigned_user_sees_only_own_client_logs(self):
        from django.test import override_settings

        user = make_staff('vl_assigned', 'view_voipcalllog')
        self.owner.assigned_users.add(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            ids = self._list_ids(user)
        self.assertIn(self.own_log.pk, ids)
        self.assertNotIn(self.foreign_log.pk, ids)
        self.assertNotIn(self.orphan_log.pk, ids)  # client=None fail closed

    def test_foreign_user_cannot_retrieve_detail(self):
        from django.test import override_settings

        user = make_staff('vl_foreign', 'view_voipcalllog')
        self.other.assigned_users.add(user)
        self.client.force_login(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            resp = self.client.get(
                f'/accounting/api/v1/voip-call-logs/{self.own_log.pk}/',
                secure=True)
        self.assertEqual(resp.status_code, 404)

    def test_orphan_log_not_visible_to_scoped_user_detail(self):
        from django.test import override_settings

        user = make_staff('vl_orphan', 'view_voipcalllog')
        self.owner.assigned_users.add(user)
        self.client.force_login(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            resp = self.client.get(
                f'/accounting/api/v1/voip-call-logs/{self.orphan_log.pk}/',
                secure=True)
        self.assertEqual(resp.status_code, 404)

    def test_superuser_sees_all_including_orphan(self):
        from django.test import override_settings

        superuser = User.objects.create_superuser('vl_super', password='x')
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            ids = self._list_ids(superuser)
        self.assertEqual(
            ids, {self.own_log.pk, self.foreign_log.pk, self.orphan_log.pk})

    def test_global_access_user_sees_all(self):
        from django.test import override_settings

        user = make_staff('vl_global', 'view_voipcalllog', 'view_all_clients')
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            ids = self._list_ids(user)
        self.assertIn(self.foreign_log.pk, ids)
        self.assertIn(self.orphan_log.pk, ids)


class VoIPCallLogImmutableTest(TestCase):
    """VoIPCallLog immutable audit record — κανένα write path από admin."""

    def _log(self):
        from accounting.models import VoIPCallLog
        owner = ClientProfile.objects.create(
            afm='094014201', eponimia='ΠΕΛΑΤΗΣ Α')
        call = VoIPCall.objects.create(
            phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now(), client=owner,
            call_id='IMM-ABC123')
        return VoIPCallLog.objects.create(call=call, action='started',
                                          description='αρχικό')

    def test_change_view_post_cannot_mutate_any_field(self):
        from accounting.models import VoIPCallLog

        # Χρήστης ΜΕ change permission — δεν πρέπει να αλλάξει τίποτα
        user = User.objects.create_superuser('imm_admin', password='x')
        # superuser για να φτάσει το POST· ο έλεγχος είναι has_change=False
        log = self._log()
        before = VoIPCallLog.objects.get(pk=log.pk)
        self.client.force_login(user)

        url = reverse('admin:accounting_voipcalllog_change', args=[log.pk])
        other = ClientProfile.objects.create(afm='111111111', eponimia='Ξ')
        resp = self.client.post(url, {
            'client': str(other.pk),
            'phone_number': '9999999999',
            'call_reference': 'HACKED',
            'description': 'tampered',
            'action': 'ended',
        }, secure=True)

        self.assertIn(resp.status_code, (403, 302))
        after = VoIPCallLog.objects.get(pk=log.pk)
        self.assertEqual(after.client_id, before.client_id)
        self.assertEqual(after.phone_number, before.phone_number)
        self.assertEqual(after.call_reference, before.call_reference)
        self.assertEqual(after.description, before.description)
        self.assertEqual(after.action, before.action)

    def test_admin_declares_no_add_change_delete(self):
        from accounting.models import VoIPCallLog

        admin_instance = site._registry[VoIPCallLog]
        req_user = User.objects.create_superuser('imm_check', password='x')
        from django.test import RequestFactory
        request = RequestFactory().get('/', secure=True)
        request.user = req_user
        self.assertFalse(admin_instance.has_add_permission(request))
        self.assertFalse(admin_instance.has_change_permission(request))
        self.assertFalse(admin_instance.has_delete_permission(request))

    def test_serializer_has_no_write_path(self):
        from accounting.serializers import VoIPCallLogSerializer

        log = self._log()
        ser = VoIPCallLogSerializer(
            log, data={'description': 'tampered', 'action': 'ended'},
            partial=True)
        ser.is_valid()  # description/action είναι read-only ή αγνοούνται
        # Το ViewSet είναι ReadOnlyModelViewSet — καμία create/update route.
        # Επιβεβαίωση ότι τα κρίσιμα πεδία δεν είναι writable:
        writable = {
            name for name, f in ser.fields.items() if not f.read_only}
        self.assertNotIn('client', writable)
        self.assertNotIn('phone_number', writable)
        self.assertNotIn('call_reference', writable)


class CrossClientCascadeDeleteTest(TestCase):
    """Finding 3: cascade deletes fail-closed σε ξένα/unassigned related rows."""

    def setUp(self):
        self.mine = ClientProfile.objects.create(
            afm='094014201', eponimia='ΔΙΚΟΣ')
        self.theirs = ClientProfile.objects.create(
            afm='998877665', eponimia='ΞΕΝΟΣ')

    def _deletion_entries(self, model, object_id):
        from django.contrib.admin.models import DELETION, LogEntry
        from django.contrib.contenttypes.models import ContentType
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(model),
            object_id=str(object_id), action_flag=DELETION)

    _seq = 0

    def _call(self, client_profile):
        CrossClientCascadeDeleteTest._seq += 1
        return VoIPCall.objects.create(
            call_id=f'CALL-{CrossClientCascadeDeleteTest._seq}',
            phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now(), client=client_profile)

    def _ticket(self, client_profile, call=None):
        return Ticket.objects.create(
            client=client_profile, call=call, title='t',
            description='-', status='open')

    def test_unassigned_call_with_foreign_ticket_fails_closed(self):
        """Σενάριο 1: unassigned call (κοινά ορατή) + ticket ξένου πελάτη."""
        from django.test import override_settings

        user = make_staff('cc1', 'view_voipcall', 'delete_voipcall',
                          'delete_ticket', 'change_ticket')
        self.mine.assigned_users.add(user)
        call = self._call(None)  # unassigned → ορατή στον scoped χρήστη
        foreign_ticket = self._ticket(self.theirs, call=call)

        self.client.force_login(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            resp = post_action_raw(
                self, VoIPCall, 'delete_with_tickets', [call])
        self.assertEqual(resp.status_code, 403)

        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())
        self.assertTrue(Ticket.objects.filter(pk=foreign_ticket.pk).exists())
        self.assertEqual(self._deletion_entries(VoIPCall, call.pk).count(), 0)
        self.assertEqual(
            self._deletion_entries(Ticket, foreign_ticket.pk).count(), 0)

    def test_own_ticket_with_foreign_call_fails_closed(self):
        """Σενάριο 2: ticket προσβάσιμου πελάτη + call ξένου πελάτη."""
        from django.test import override_settings

        user = make_staff('cc2', 'view_ticket', 'delete_ticket',
                          'delete_voipcall', 'change_voipcall')
        self.mine.assigned_users.add(user)
        foreign_call = self._call(self.theirs)
        ticket = self._ticket(self.mine, call=foreign_call)

        self.client.force_login(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            resp = post_action_raw(self, Ticket, 'delete_with_calls', [ticket])
        self.assertEqual(resp.status_code, 403)

        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertTrue(VoIPCall.objects.filter(pk=foreign_call.pk).exists())

    def test_inconsistent_ticket_client_differs_from_call(self):
        """Σενάριο 3: legacy ασυνέπεια ticket.client != call.client."""
        from django.test import override_settings

        user = make_staff('cc3', 'view_voipcall', 'delete_voipcall',
                          'delete_ticket', 'change_ticket')
        self.mine.assigned_users.add(user)
        call = self._call(self.mine)          # δικιά μου κλήση
        ticket = self._ticket(self.theirs, call=call)  # ticket ξένου πελάτη

        self.client.force_login(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            resp = post_action_raw(
                self, VoIPCall, 'delete_with_tickets', [call])
        self.assertEqual(resp.status_code, 403)

        # Fail closed: το ξένο ticket μπλοκάρει ΟΛΗ την ενέργεια
        self.assertTrue(VoIPCall.objects.filter(pk=call.pk).exists())
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())

    def test_mixed_bulk_one_allowed_one_foreign_no_partial(self):
        """Σενάριο 4: mixed selection — καμία μερική επιτυχία."""
        from django.test import override_settings

        # Και οι δύο κλήσεις ΟΡΑΤΕΣ στον scoped χρήστη (η μία assigned,
        # η άλλη unassigned/triage), αλλά η unassigned έχει ticket ξένου
        # πελάτη → όλο το batch fail closed, καμία μερική διαγραφή.
        user = make_staff('cc4', 'view_voipcall', 'delete_voipcall',
                          'delete_ticket', 'change_ticket')
        self.mine.assigned_users.add(user)
        good = self._call(self.mine)
        good_ticket = self._ticket(self.mine, call=good)
        unassigned = self._call(None)          # ορατή (triage)
        foreign_ticket = self._ticket(self.theirs, call=unassigned)

        self.client.force_login(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            resp = post_action_raw(
                self, VoIPCall, 'delete_with_tickets', [good, unassigned])
        self.assertEqual(resp.status_code, 403)

        # Τίποτα δεν διαγράφεται (fail closed για ολόκληρο το batch)
        self.assertTrue(VoIPCall.objects.filter(pk=good.pk).exists())
        self.assertTrue(VoIPCall.objects.filter(pk=unassigned.pk).exists())
        self.assertTrue(Ticket.objects.filter(pk=good_ticket.pk).exists())
        self.assertTrue(Ticket.objects.filter(pk=foreign_ticket.pk).exists())

    def test_delete_without_calls_foreign_call_fails_closed(self):
        """Σενάριο 5-variant: το ticket μου, η κλήση του (mutated) → 403."""
        from django.test import override_settings

        user = make_staff('cc5', 'view_ticket', 'delete_ticket',
                          'change_voipcall')
        self.mine.assigned_users.add(user)
        foreign_call = self._call(self.theirs)
        foreign_call.ticket_created = True
        foreign_call.save(update_fields=['ticket_created'])
        ticket = self._ticket(self.mine, call=foreign_call)

        self.client.force_login(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            resp = post_action_raw(
                self, Ticket, 'delete_without_calls', [ticket])
        self.assertEqual(resp.status_code, 403)

        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
        foreign_call.refresh_from_db()
        self.assertTrue(foreign_call.ticket_created)  # αμετάβλητη

    def test_see_all_user_can_cascade_delete_foreign(self):
        """Θετικό control: see-all χρήστης δεν μπλοκάρεται."""
        from django.test import override_settings

        user = make_staff('cc6', 'view_voipcall', 'delete_voipcall',
                          'delete_ticket', 'change_ticket', 'view_all_clients')
        call = self._call(self.theirs)
        ticket = self._ticket(self.theirs, call=call)

        self.client.force_login(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            post_action(self, VoIPCall, 'delete_with_tickets', [call])

        self.assertFalse(VoIPCall.objects.filter(pk=call.pk).exists())
        self.assertFalse(Ticket.objects.filter(pk=ticket.pk).exists())

    def test_delete_view_foreign_call_fails_closed(self):
        """delete_view delete_call=1 με κλήση ξένου πελάτη → 403, τίποτα."""
        from django.test import override_settings

        user = make_staff('cc7', 'view_ticket', 'delete_ticket',
                          'delete_voipcall', 'change_voipcall')
        self.mine.assigned_users.add(user)
        foreign_call = self._call(self.theirs)
        ticket = self._ticket(self.mine, call=foreign_call)

        self.client.force_login(user)
        url = reverse('admin:accounting_ticket_delete', args=[ticket.pk])
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            resp = self.client.post(
                url, {'delete_call': '1', 'post': 'yes'}, secure=True)

        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Ticket.objects.filter(pk=ticket.pk).exists())
        self.assertTrue(VoIPCall.objects.filter(pk=foreign_call.pk).exists())


class VoIPCallLogMigrationWindowTest(TestCase):
    """Finding 3.8: το catch-up backfill του 10026 πιάνει snapshot-less
    logs που δημιούργησε παλιό application code στο deployment window."""

    def _mig(self):
        from importlib import import_module
        return import_module(
            'accounting.migrations.10026_voipcalllog_call_set_null')

    def test_catch_up_backfills_snapshotless_log(self):
        from django.apps import apps as django_apps
        from accounting.models import VoIPCallLog

        owner = ClientProfile.objects.create(afm='094014201', eponimia='O')
        call = VoIPCall.objects.create(
            call_id='WIN-1', phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now(), client=owner)
        log = VoIPCallLog.objects.create(call=call, action='started')
        # Προσομοίωση παλιού code: snapshot κενό (bypass του save())
        VoIPCallLog.objects.filter(pk=log.pk).update(
            call_reference='', phone_number='', client=None)

        mod = self._mig()
        mod._catch_up_backfill(django_apps, None)

        log.refresh_from_db()
        self.assertEqual(log.call_reference, 'WIN-1')
        self.assertEqual(log.phone_number, '2101234567')
        self.assertEqual(log.client_id, owner.pk)
        # Το validation δεν πρέπει να σκάσει πλέον
        mod._validate(django_apps, None)

    def test_validation_aborts_on_snapshotless_log(self):
        from django.apps import apps as django_apps
        from accounting.models import VoIPCallLog

        call = VoIPCall.objects.create(
            call_id='WIN-2', phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now())
        log = VoIPCallLog.objects.create(call=call, action='started')
        VoIPCallLog.objects.filter(pk=log.pk).update(call_reference='')

        mod = self._mig()
        with self.assertRaises(RuntimeError):
            mod._validate(django_apps, None)

    def test_audit_command_fail_closed(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from accounting.models import VoIPCallLog

        call = VoIPCall.objects.create(
            call_id='WIN-3', phone_number='2101234567', direction='incoming',
            status='missed', started_at=timezone.now())
        log = VoIPCallLog.objects.create(call=call, action='started')
        VoIPCallLog.objects.filter(pk=log.pk).update(call_reference='')

        with self.assertRaises(CommandError):
            call_command('audit_voipcalllog_snapshots', '--fail-on-findings')

    def test_audit_accepts_unassigned_call_with_null_snapshot(self):
        """
        Εύρημα του migration rehearsal σε PostgreSQL 14: unassigned κλήση
        (client=None — π.χ. από τον Fritz monitor) με σωστά-NULL snapshot
        client σημειωνόταν ως client-mismatch, επειδή σε SQL το
        `NULL = NULL` δεν είναι TRUE και το exclude κρατούσε τη γραμμή.
        Το deploy gate (--fail-on-findings) θα κοκκίνιζε μόνιμα σε κάθε
        εγκατάσταση με unassigned κλήσεις. NULL == NULL είναι ταύτιση.
        """
        from django.core.management import call_command
        from accounting.models import VoIPCallLog

        call = VoIPCall.objects.create(
            call_id='UNASSIGNED-1', phone_number='2101234567',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=None)
        VoIPCallLog.objects.create(call=call, action='started')

        # Δεν πρέπει να σηκώσει CommandError — καμία ασυνέπεια.
        call_command('audit_voipcalllog_snapshots', '--fail-on-findings')

        # Ο πραγματικός mismatch (snapshot NULL ενώ η κλήση ΕΧΕΙ πελάτη)
        # εξακολουθεί να πιάνεται.
        from django.core.management.base import CommandError
        owner = ClientProfile.objects.create(
            afm='094014201', eponimia='AUDIT-OWNER')
        owned = VoIPCall.objects.create(
            call_id='OWNED-1', phone_number='2101234567',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=owner)
        log = VoIPCallLog.objects.create(call=owned, action='started')
        VoIPCallLog.objects.filter(pk=log.pk).update(client=None)
        with self.assertRaises(CommandError):
            call_command('audit_voipcalllog_snapshots', '--fail-on-findings')


class DeletionCounterAccuracyTest(_OwnedMixin, TestCase):
    """Finding 4: τα εμφανιζόμενα counts δεν φουσκώνουν από related rows."""

    def test_delete_with_tickets_count_ignores_related_logs(self):
        from django.contrib.messages import get_messages
        from accounting.models import VoIPCallLog

        user = self._su('cnt_call', 'view_voipcall', 'delete_voipcall',
                        'delete_ticket', 'change_ticket')
        call = self._mk_call()
        ticket = Ticket.objects.create(
            client=self.owner, call=call, title='t', description='-',
            status='open')
        # Related audit rows (SET_NULL) — ΔΕΝ πρέπει να μετρηθούν
        for i in range(3):
            VoIPCallLog.objects.create(call=call, action='started')
        self.client.force_login(user)

        resp = self.client.post(
            changelist_url(VoIPCall),
            {'action': 'delete_with_tickets',
             '_selected_action': [str(call.pk)]},
            follow=True, secure=True)

        msgs = ' '.join(str(m) for m in get_messages(resp.wsgi_request))
        # Ακριβώς 1 κλήση + 1 ticket — όχι φουσκωμένο από τα 3 logs
        self.assertIn('1 κλήσεις και 1 tickets', msgs)
        self.assertFalse(VoIPCall.objects.filter(pk=call.pk).exists())
        self.assertFalse(Ticket.objects.filter(pk=ticket.pk).exists())
        # Τα logs επιβιώνουν (audit trail, SET_NULL)
        self.assertEqual(VoIPCallLog.objects.filter(call__isnull=True).count(), 3)

    def test_delete_without_tickets_reports_detached_count(self):
        from django.contrib.messages import get_messages

        user = self._su('cnt_det', 'view_voipcall', 'delete_voipcall',
                        'change_ticket')
        call = self._mk_call()
        Ticket.objects.create(
            client=self.owner, call=call, title='t', description='-',
            status='open')
        self.client.force_login(user)

        resp = self.client.post(
            changelist_url(VoIPCall),
            {'action': 'delete_without_tickets',
             '_selected_action': [str(call.pk)]},
            follow=True, secure=True)

        msgs = ' '.join(str(m) for m in get_messages(resp.wsgi_request))
        self.assertIn('1 κλήσεις', msgs)
        self.assertIn('1 tickets αποσυνδέθηκαν', msgs)


class VoIPCallLogClientResyncTest(TestCase):
    """
    Current-attribution contract (εύρημα ανεξάρτητου review στο `5e518a8`):
    όσο υπάρχει η κλήση, ΚΑΘΕ VoIPCallLog της πρέπει να έχει snapshot
    client ίδιο με την κλήση. Τα change_call_client() και
    sync_ticket_call_client() άλλαζαν το VoIPCall.client ΧΩΡΙΣ να
    συγχρονίζουν τα ήδη υπάρχοντα logs — ο νέος scoped owner δεν έβλεπε
    το ιστορικό πριν την αντιστοίχιση, και το audit gate
    (--fail-on-findings) κοκκίνιζε με client-mismatch.
    """

    def setUp(self):
        from accounting.models import VoIPCall, VoIPCallLog

        self.owner = ClientProfile.objects.create(
            afm='094014201', eponimia='ΠΕΛΑΤΗΣ Α')
        self.other = ClientProfile.objects.create(
            afm='998877665', eponimia='ΠΕΛΑΤΗΣ Β')
        # Unassigned κλήση με προϋπάρχον log — και τα δύο client=None
        self.call = VoIPCall.objects.create(
            call_id='RESYNC-1', phone_number='2109999999',
            direction='incoming', status='missed',
            started_at=timezone.now(), client=None)
        self.started_log = VoIPCallLog.objects.create(
            call=self.call, action='started')
        self.assertIsNone(self.started_log.client_id)

    def _audit_clean(self):
        from django.core.management import call_command
        call_command('audit_voipcalllog_snapshots', '--fail-on-findings')

    def test_change_call_client_resyncs_existing_logs(self):
        """Το repro του review: unassigned → owner, το παλιό log ακολουθεί."""
        from accounting.services.call_assignment import change_call_client

        change_call_client(self.call, self.owner,
                           log_action='client_matched')

        self.started_log.refresh_from_db()
        self.assertEqual(self.started_log.client_id, self.owner.pk)
        # Και το νέο client_matched log είναι σωστό
        from accounting.models import VoIPCallLog
        for log in VoIPCallLog.objects.filter(call=self.call):
            self.assertEqual(log.client_id, self.owner.pk)
        self._audit_clean()

    def test_scoped_owner_sees_full_history_after_match(self):
        """ENFORCE_CLIENT_ASSIGNMENT=True: ο owner βλέπει ΟΛΟ το ιστορικό."""
        from django.test import override_settings
        from accounting.services.call_assignment import change_call_client

        change_call_client(self.call, self.owner,
                           log_action='client_matched')

        user = make_staff('resync_owner', 'view_voipcalllog')
        self.owner.assigned_users.add(user)
        self.client.force_login(user)
        with override_settings(ENFORCE_CLIENT_ASSIGNMENT=True):
            resp = self.client.get(
                '/accounting/api/v1/voip-call-logs/', secure=True)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        results = data['results'] if isinstance(data, dict) else data
        ids = {row['id'] for row in results}
        self.assertIn(self.started_log.pk, ids,
                      'το προ-αντιστοίχισης log λείπει από το ιστορικό '
                      'του scoped owner')

    def test_reassignment_moves_all_logs_off_old_client(self):
        """Α→Β: κανένα log δεν μένει scoped στον Α."""
        from accounting.models import VoIPCallLog
        from accounting.services.call_assignment import change_call_client

        change_call_client(self.call, self.owner)
        VoIPCallLog.objects.create(call=self.call, action='answered')
        change_call_client(self.call, self.other)

        self.assertFalse(
            VoIPCallLog.objects.filter(
                call=self.call, client=self.owner).exists(),
            'log παρέμεινε scoped στον παλιό πελάτη')
        self.assertEqual(
            VoIPCallLog.objects.filter(
                call=self.call, client=self.other).count(),
            VoIPCallLog.objects.filter(call=self.call).count())
        self._audit_clean()

    def test_sync_ticket_call_client_resyncs_logs(self):
        """Από την πλευρά του ticket: unassigned κλήση → πελάτης ticket."""
        from accounting.models import Ticket
        from accounting.services.call_assignment import sync_ticket_call_client

        ticket = Ticket.objects.create(
            client=self.owner, call=self.call, title='τ', description='-',
            status='open')
        sync_ticket_call_client(ticket)

        self.call.refresh_from_db()
        self.started_log.refresh_from_db()
        self.assertEqual(self.call.client_id, self.owner.pk)
        self.assertEqual(self.started_log.client_id, self.owner.pk)
        self._audit_clean()

    def test_deletion_after_change_keeps_last_consistent_snapshot(self):
        """Διαγραφή μετά την αλλαγή: το log κρατά τον τελευταίο πελάτη."""
        from accounting.services.call_assignment import change_call_client

        change_call_client(self.call, self.owner)
        self.call.delete()

        self.started_log.refresh_from_db()
        self.assertIsNone(self.started_log.call_id)
        self.assertEqual(self.started_log.client_id, self.owner.pk)
        self.assertEqual(self.started_log.call_reference, 'RESYNC-1')
        self._audit_clean()

    def test_rollback_when_log_resync_fails(self):
        """Αποτυχία συγχρονισμού logs → rollback ΚΑΙ της αλλαγής πελάτη."""
        from unittest import mock
        from django.db import DatabaseError
        from accounting.models import VoIPCallLog
        from accounting.services.call_assignment import change_call_client

        real_filter = VoIPCallLog.objects.filter

        def failing_filter(*args, **kwargs):
            qs = real_filter(*args, **kwargs)
            if kwargs.get('call') is not None:
                broken = mock.MagicMock(wraps=qs)
                broken.update.side_effect = DatabaseError('resync failed')
                return broken
            return qs

        with mock.patch.object(
                type(VoIPCallLog.objects), 'filter',
                side_effect=failing_filter):
            with self.assertRaises(DatabaseError):
                change_call_client(self.call, self.owner)

        self.call.refresh_from_db()
        self.started_log.refresh_from_db()
        self.assertIsNone(self.call.client_id,
                          'η αλλαγή πελάτη ΔΕΝ έγινε rollback')
        self.assertIsNone(self.started_log.client_id)
