# -*- coding: utf-8 -*-
"""
Regression tests για το BackupSettingsAPIView: άκυρο max_backups
πρέπει να επιστρέφει 400 — όχι 500.
"""
from django.contrib.auth.models import Permission, User
from django.test import TestCase

from settings.models import BackupSettings

# Το settings/backup_urls.py γίνεται include στο accounting/urls.py
URL = '/accounting/api/settings/backup/settings/'


class BackupSettingsMaxBackupsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='backup_admin', password='pass')
        self.user.user_permissions.add(
            Permission.objects.get(codename='change_backupsettings')
        )
        self.client.force_login(self.user)

    def test_non_integer_max_backups_returns_400(self):
        response = self.client.patch(
            URL, data={'max_backups': 'abc'}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_out_of_range_max_backups_returns_400(self):
        response = self.client.patch(
            URL, data={'max_backups': 0}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            URL, data={'max_backups': 5000}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_valid_max_backups_saved(self):
        response = self.client.patch(
            URL, data={'max_backups': '12'}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BackupSettings.get_settings().max_backups, 12)
