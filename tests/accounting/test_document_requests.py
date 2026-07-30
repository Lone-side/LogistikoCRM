# -*- coding: utf-8 -*-
"""
Tests για τα Αιτήματα Εγγράφων (DocumentRequest) και τις ειδοποιήσεις
νέων εγγράφων από το portal.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from accounting.models import (
    ClientProfile, DocumentRequest, DocumentRequestItem, SharedLink,
)
from settings.models import UserNotificationSettings

PDF = b'%PDF-1.4 test content'


def make_client(afm='123456783', email='pelatis@example.com'):
    return ClientProfile.objects.create(
        afm=afm, eponimia='ΠΕΛΑΤΗΣ ΑΕ', eidos_ipoxreou='company', email=email,
    )


def make_link(client, user, **overrides):
    defaults = dict(
        client=client,
        name='Portal test',
        access_level='view',
        allow_upload=True,
        max_uploads=100,
        expires_at=timezone.now() + timedelta(days=30),
        created_by=user,
    )
    defaults.update(overrides)
    return SharedLink.objects.create(**defaults)


def make_request(client, link, user, items=('Τιμολόγια αγορών', 'Extrait τράπεζας')):
    doc_request = DocumentRequest.objects.create(
        client=client, shared_link=link, title='Δικαιολογητικά Ιουλίου',
        created_by=user,
    )
    for label in items:
        DocumentRequestItem.objects.create(request=doc_request, label=label)
    return doc_request


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PORTAL_EMAIL_SYNC=True,
)
class PortalDocumentRequestTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'staff1', 'staff1@office.gr', 'pass12345', is_staff=True
        )
        self.client_profile = make_client()
        self.link = make_link(self.client_profile, self.user)
        self.request_obj = make_request(self.client_profile, self.link, self.user)

    def _portal_get(self):
        return self.client.get(f'/accounting/share/{self.link.token}/')

    def _upload(self, item_id=None, filename='doc.pdf'):
        data = {'files': SimpleUploadedFile(filename, PDF)}
        if item_id is not None:
            data['request_item_id'] = item_id
        # execute=True: τρέχουν τα on_commit callbacks (ειδοποιήσεις email)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                f'/accounting/share/{self.link.token}/upload/', data
            )

    def test_portal_content_includes_open_request(self):
        resp = self._portal_get()
        self.assertEqual(resp.status_code, 200)
        dr = resp.json()['document_request']
        self.assertEqual(dr['title'], 'Δικαιολογητικά Ιουλίου')
        self.assertEqual(len(dr['items']), 2)
        self.assertFalse(dr['items'][0]['is_received'])

    def test_portal_content_no_request(self):
        self.request_obj.status = 'cancelled'
        self.request_obj.save()
        resp = self._portal_get()
        self.assertIsNone(resp.json()['document_request'])

    def test_upload_with_item_marks_received(self):
        item = self.request_obj.items.first()
        resp = self._upload(item_id=item.pk)
        self.assertEqual(resp.status_code, 201, resp.content)

        item.refresh_from_db()
        self.assertTrue(item.is_received)
        self.assertIsNotNone(item.received_at)
        self.assertIsNotNone(item.received_document)
        # Το αίτημα παραμένει ανοιχτό — υπάρχει ακόμα εκκρεμές item
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, 'open')

    def test_upload_last_item_completes_request(self):
        items = list(self.request_obj.items.all())
        self._upload(item_id=items[0].pk)
        self._upload(item_id=items[1].pk, filename='doc2.pdf')

        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, 'completed')
        self.assertIsNotNone(self.request_obj.completed_at)

    def test_upload_with_foreign_item_rejected(self):
        other_link = make_link(self.client_profile, self.user)
        other_request = make_request(self.client_profile, other_link, self.user)
        foreign_item = other_request.items.first()
        resp = self._upload(item_id=foreign_item.pk)
        self.assertEqual(resp.status_code, 400)

    def test_upload_with_received_item_rejected(self):
        item = self.request_obj.items.first()
        DocumentRequestItem.objects.filter(pk=item.pk).update(
            is_received=True, received_at=timezone.now()
        )
        resp = self._upload(item_id=item.pk)
        self.assertEqual(resp.status_code, 400)

    def test_item_category_overrides_link_category(self):
        item = self.request_obj.items.first()
        item.category = 'vat'
        item.save()
        self._upload(item_id=item.pk)
        item.refresh_from_db()
        self.assertEqual(item.received_document.document_category, 'vat')

    def test_upload_sends_notification_to_link_creator(self):
        self._upload()
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('ΠΕΛΑΤΗΣ ΑΕ', message.subject)
        self.assertIn('staff1@office.gr', message.to)

    def test_notification_includes_optin_staff_dedup(self):
        optin = User.objects.create_user('optin', 'optin@office.gr', 'pass12345')
        UserNotificationSettings.objects.create(user=optin, new_files=True)
        # Χρήστης χωρίς opt-in ΔΕΝ λαμβάνει
        User.objects.create_user('other', 'other@office.gr', 'pass12345')

        self._upload()
        self.assertEqual(len(mail.outbox), 1)
        recipients = mail.outbox[0].to
        self.assertIn('staff1@office.gr', recipients)
        self.assertIn('optin@office.gr', recipients)
        self.assertNotIn('other@office.gr', recipients)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PORTAL_EMAIL_SYNC=True,
)
class DocumentRequestAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'staff1', 'staff1@office.gr', 'pass12345', is_staff=True
        )
        self.client.force_login(self.user)
        self.client_profile = make_client()

    def _create(self, **overrides):
        payload = {
            'client_id': self.client_profile.pk,
            'title': 'Δικαιολογητικά Ιουλίου',
            'items': [
                {'label': 'Τιμολόγια αγορών', 'category': 'vat'},
                {'label': 'Extrait τράπεζας'},
            ],
        }
        payload.update(overrides)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                '/accounting/api/v1/document-requests/', payload,
                content_type='application/json',
            )

    def test_create_makes_link_and_sends_email(self):
        resp = self._create()
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data['total_count'], 2)
        self.assertTrue(data['email_sent'])
        self.assertTrue(data['shared_link']['can_upload'])

        # Το αρχικό email στάλθηκε στον πελάτη με το portal link
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('pelatis@example.com', mail.outbox[0].to)
        # Το portal URL (με το token) βρίσκεται στο HTML μέρος (href)
        html_body = mail.outbox[0].alternatives[0][0]
        self.assertIn(data['shared_link']['token'], html_body)

    def test_create_without_client_email_flags_not_sent(self):
        self.client_profile.email = ''
        self.client_profile.save()
        resp = self._create()
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.json()['email_sent'])
        self.assertEqual(len(mail.outbox), 0)

    def test_visible_to_other_office_users(self):
        self._create()
        other = User.objects.create_user('other', 'o@office.gr', 'pass12345')
        self.client.force_login(other)
        resp = self.client.get('/accounting/api/v1/document-requests/')
        data = resp.json()
        results = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(results), 1)

    def test_invalid_item_category_rejected(self):
        resp = self._create(items=[{'label': 'Χ', 'category': 'nonexistent'}])
        self.assertEqual(resp.status_code, 400)

    def test_send_reminder_and_cooldown(self):
        request_id = self._create().json()['id']
        mail.outbox = []

        resp = self.client.post(
            f'/accounting/api/v1/document-requests/{request_id}/send-reminder/'
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(mail.outbox), 1)

        # Cooldown 1 ώρας για anti-double-click
        resp2 = self.client.post(
            f'/accounting/api/v1/document-requests/{request_id}/send-reminder/'
        )
        self.assertEqual(resp2.status_code, 400)

    def test_send_reminder_expired_link_400(self):
        request_id = self._create().json()['id']
        SharedLink.objects.update(expires_at=timezone.now() - timedelta(days=1))
        resp = self.client.post(
            f'/accounting/api/v1/document-requests/{request_id}/send-reminder/'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('λήξει', resp.json()['error'])

    def test_mark_item_manually_completes(self):
        data = self._create().json()
        item_ids = [i['id'] for i in data['items']]
        for item_id in item_ids:
            resp = self.client.post(
                f"/accounting/api/v1/document-requests/{data['id']}/mark-item/",
                {'item_id': item_id}, content_type='application/json',
            )
            self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'completed')

        # Un-mark ξανανοίγει το αίτημα
        resp = self.client.post(
            f"/accounting/api/v1/document-requests/{data['id']}/mark-item/",
            {'item_id': item_ids[0], 'is_received': False},
            content_type='application/json',
        )
        self.assertEqual(resp.json()['status'], 'open')

    def test_requires_authentication(self):
        self.client.logout()
        resp = self.client.get('/accounting/api/v1/document-requests/')
        self.assertIn(resp.status_code, (401, 403))


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PORTAL_EMAIL_SYNC=True,
)
class ReminderTaskTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff1', 's@office.gr', 'pass12345')
        self.client_profile = make_client()
        self.link = make_link(self.client_profile, self.user)
        self.request_obj = make_request(self.client_profile, self.link, self.user)

    def _run(self):
        from accounting.tasks import send_document_request_reminders
        return send_document_request_reminders()

    def test_sends_to_eligible_and_updates_state(self):
        result = self._run()
        self.assertIn('1', result)
        self.assertEqual(len(mail.outbox), 1)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.reminder_count, 1)
        self.assertIsNotNone(self.request_obj.last_reminder_sent_at)

    def test_cooldown_respected(self):
        DocumentRequest.objects.filter(pk=self.request_obj.pk).update(
            last_reminder_sent_at=timezone.now() - timedelta(days=1)
        )
        self._run()
        self.assertEqual(len(mail.outbox), 0)

        # Μετά από 4 μέρες ξαναστέλνει
        DocumentRequest.objects.filter(pk=self.request_obj.pk).update(
            last_reminder_sent_at=timezone.now() - timedelta(days=4)
        )
        self._run()
        self.assertEqual(len(mail.outbox), 1)

    def test_max_reminders_respected(self):
        from accounting.tasks import DOCUMENT_REQUEST_MAX_REMINDERS
        DocumentRequest.objects.filter(pk=self.request_obj.pk).update(
            reminder_count=DOCUMENT_REQUEST_MAX_REMINDERS
        )
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    def test_skips_completed_and_expired_and_no_email(self):
        # Completed
        DocumentRequest.objects.filter(pk=self.request_obj.pk).update(status='completed')
        self._run()
        self.assertEqual(len(mail.outbox), 0)

        # Expired link
        DocumentRequest.objects.filter(pk=self.request_obj.pk).update(status='open')
        SharedLink.objects.filter(pk=self.link.pk).update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        self._run()
        self.assertEqual(len(mail.outbox), 0)

        # Χωρίς email πελάτη
        SharedLink.objects.filter(pk=self.link.pk).update(
            expires_at=timezone.now() + timedelta(days=10)
        )
        self.client_profile.email = ''
        self.client_profile.save()
        self._run()
        self.assertEqual(len(mail.outbox), 0)


class NotificationsEndpointTest(TestCase):
    def test_portal_upload_notification_within_48h(self):
        from accounting.models import SharedLinkAccess

        user = User.objects.create_user('staff1', 's@office.gr', 'pass12345')
        self.client.force_login(user)
        client_profile = make_client()
        link = make_link(client_profile, user)

        access = SharedLinkAccess.objects.create(
            shared_link=link, action='upload', ip_address='127.0.0.1'
        )
        resp = self.client.get('/accounting/api/v1/notifications/')
        self.assertEqual(resp.status_code, 200)
        types = [n['type'] for n in resp.json()['notifications']]
        self.assertIn('portal_upload', types)

        # Παλιό access (3 μέρες) δεν εμφανίζεται
        SharedLinkAccess.objects.filter(pk=access.pk).update(
            accessed_at=timezone.now() - timedelta(days=3)
        )
        resp = self.client.get('/accounting/api/v1/notifications/')
        types = [n['type'] for n in resp.json()['notifications']]
        self.assertNotIn('portal_upload', types)
