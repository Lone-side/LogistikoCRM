# -*- coding: utf-8 -*-
"""
Tests για τις «γρήγορες νίκες»:
- send_obligation_reminders: βρίσκει το ελληνικό template, στέλνει και σε
  in_progress, δεν ξαναστέλνει καθημερινά (cooldown)
- Ρυθμίσεις ειδοποιήσεων ανά χρήστη (API GET/PUT)
- backup_database command με --output-dir/--keep-days
"""
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounting.models import (
    ClientProfile, EmailTemplate, MonthlyObligation, ObligationType, ScheduledEmail,
)
from accounting.tasks import send_obligation_reminders
from settings.models import UserNotificationSettings


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ObligationReminderTaskTest(TestCase):
    def setUp(self):
        self.client_profile = ClientProfile.objects.create(
            afm='123456783',
            eponimia='ΠΕΛΑΤΗΣ ΤΕΣΤ',
            eidos_ipoxreou='company',
            email='pelatis@example.com',
        )
        self.obligation_type = ObligationType.objects.create(code='ΦΠΑ', name='ΦΠΑ')
        today = timezone.now().date()
        self.obligation = MonthlyObligation.objects.create(
            client=self.client_profile,
            obligation_type=self.obligation_type,
            year=today.year, month=today.month,
            deadline=today + timedelta(days=3),
            status='pending',
        )

    def test_uses_greek_seeded_template(self):
        """Το seeded «Υπενθύμιση Προθεσμίας» πρέπει να βρίσκεται και να στέλνεται HTML."""
        # Με --keepdb στο CI, προηγούμενα TransactionTestCase κάνουν truncate
        # τα migration seeds — ξανατρέχουμε το seeding του 0025 αν λείπει
        if not EmailTemplate.objects.filter(name='Υπενθύμιση Προθεσμίας').exists():
            from importlib import import_module
            from django.apps import apps as global_apps
            seed = import_module('accounting.migrations.0025_default_email_templates')
            seed.create_default_templates(global_apps, None)
        self.assertTrue(
            EmailTemplate.objects.filter(name='Υπενθύμιση Προθεσμίας').exists(),
            'Λείπει το seeded template — έλεγξε το migration 0025',
        )
        result = send_obligation_reminders()
        self.assertIn('Sent 1', result)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('Υπενθύμιση Προθεσμίας', message.subject)
        self.assertIn('ΦΠΑ', message.subject)
        # HTML alternative υπάρχει (όχι σκέτο plaintext)
        self.assertTrue(message.alternatives)

    def test_in_progress_obligations_get_reminders(self):
        self.obligation.status = 'in_progress'
        self.obligation.save()
        result = send_obligation_reminders()
        self.assertIn('Sent 1', result)

    def test_cooldown_prevents_daily_spam(self):
        send_obligation_reminders()
        self.assertEqual(len(mail.outbox), 1)
        # Δεύτερο τρέξιμο την ίδια μέρα → τίποτα νέο
        result = send_obligation_reminders()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('skipped', result)
        # Καταγράφηκε με σύνδεση στην υποχρέωση
        self.assertTrue(
            ScheduledEmail.objects.filter(obligations=self.obligation, status='sent').exists()
        )


class NotificationSettingsAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('staff1', 's@test.com', 'pass12345', is_staff=True)
        self.client.force_login(self.user)

    def test_get_creates_defaults(self):
        resp = self.client.get('/accounting/api/v1/notifications/settings/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['email_reminders'])
        self.assertFalse(data['weekly_summary'])

    def test_put_updates_per_user(self):
        resp = self.client.put(
            '/accounting/api/v1/notifications/settings/',
            data='{"weekly_summary": true, "missed_calls": false}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        obj = UserNotificationSettings.objects.get(user=self.user)
        self.assertTrue(obj.weekly_summary)
        self.assertFalse(obj.missed_calls)
        # Άλλος χρήστης έχει τα δικά του defaults
        other = User.objects.create_user('staff2', 's2@test.com', 'pass12345', is_staff=True)
        self.client.force_login(other)
        resp2 = self.client.get('/accounting/api/v1/notifications/settings/')
        self.assertFalse(resp2.json()['weekly_summary'])


class BackupCommandTest(TestCase):
    def test_backup_with_output_dir_and_keep_days(self):
        tmp = tempfile.mkdtemp(prefix='backup_test_')
        try:
            # Το test DB είναι SQLite in-memory ή αρχείο ανάλογα με settings —
            # σε in-memory το command πρέπει να αποτύχει καθαρά, αλλιώς να γράψει αρχείο
            from django.conf import settings as dj_settings
            db_name = str(dj_settings.DATABASES['default']['NAME'])
            if ':memory:' in db_name or 'memorydb' in db_name or not db_name:
                self.skipTest('Το test DB είναι in-memory — δεν υπάρχει αρχείο για backup')
            try:
                call_command('backup_database', '--output-dir', tmp, '--keep-days', '30')
            except CommandError as e:
                # π.χ. δεν υπάρχει pg_dump στο περιβάλλον
                self.skipTest(f'Backup μη διαθέσιμο εδώ: {e}')
            import os
            # SQLite → .backup, PostgreSQL (CI) → .pgdump
            backups = [
                f for f in os.listdir(tmp) if f.endswith(('.backup', '.pgdump'))
            ]
            self.assertEqual(len(backups), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
