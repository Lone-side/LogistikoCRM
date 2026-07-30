# -*- coding: utf-8 -*-
"""
Tests για settings/backup_utils: validation, create/restore roundtrip,
και rollback του restore όταν αποτύχει το loaddata στη μέση.
"""
import json
import os
import tempfile
import zipfile

from django.test import TestCase
from unittest.mock import patch

from accounting.models import ClientProfile
from settings.backup_utils import (
    _restore_database, create_backup, restore_backup, validate_backup_file,
)
from settings.models import BackupHistory, BackupSettings


class ValidateBackupFileTest(TestCase):
    def _make_zip(self, files: dict) -> str:
        fd, path = tempfile.mkstemp(suffix='.zip')
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with zipfile.ZipFile(path, 'w') as zipf:
            for name, content in files.items():
                zipf.writestr(name, content)
        return path

    def test_missing_file(self):
        is_valid, error = validate_backup_file('/nonexistent/backup.zip')
        self.assertFalse(is_valid)

    def test_not_a_zip(self):
        fd, path = tempfile.mkstemp(suffix='.zip')
        os.write(fd, b'not a zip at all')
        os.close(fd)
        self.addCleanup(os.remove, path)
        is_valid, error = validate_backup_file(path)
        self.assertFalse(is_valid)
        self.assertIn('ZIP', error)

    def test_missing_database_json(self):
        path = self._make_zip({'metadata.json': '{}'})
        is_valid, error = validate_backup_file(path)
        self.assertFalse(is_valid)
        self.assertIn('database.json', error)

    def test_invalid_database_json(self):
        path = self._make_zip({'database.json': 'όχι json'})
        is_valid, error = validate_backup_file(path)
        self.assertFalse(is_valid)

    def test_path_traversal_rejected(self):
        path = self._make_zip({
            'database.json': '[]',
            '../evil.txt': 'x',
        })
        is_valid, error = validate_backup_file(path)
        self.assertFalse(is_valid)

    def test_valid_backup(self):
        path = self._make_zip({'database.json': '[]'})
        is_valid, error = validate_backup_file(path)
        self.assertTrue(is_valid)
        self.assertIsNone(error)


class RestoreDatabaseRollbackTest(TestCase):
    """Αποτυχία στη μέση του restore δεν πρέπει να αφήνει άδεια βάση."""

    def test_failed_loaddata_rolls_back_flush(self):
        client = ClientProfile.objects.create(
            afm='123456789', eponimia='ΠΕΛΑΤΗΣ ΑΕ'
        )

        # Σπασμένο JSON: το loaddata σκάει ΑΦΟΥ έχει τρέξει το flush
        with self.assertRaises(Exception):
            _restore_database('[{"model": "broken', mode='replace')

        # Rollback: τα δεδομένα πριν το restore είναι ακόμα εκεί
        self.assertTrue(ClientProfile.objects.filter(pk=client.pk).exists())

    def test_merge_mode_loads_without_flush(self):
        client = ClientProfile.objects.create(
            afm='123456789', eponimia='ΠΕΛΑΤΗΣ ΑΕ'
        )
        fixture = json.dumps([{
            'model': 'auth.group',
            'fields': {'name': 'Δοκιμαστική Ομάδα'},
        }])

        _restore_database(fixture, mode='merge')

        from django.contrib.auth.models import Group
        self.assertTrue(ClientProfile.objects.filter(pk=client.pk).exists())
        self.assertTrue(Group.objects.filter(name='Δοκιμαστική Ομάδα').exists())


class BackupRoundtripTest(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        patcher = patch.object(
            BackupSettings, 'get_backup_dir', return_value=self.tmpdir
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_create_backup_produces_valid_zip_and_record(self):
        ClientProfile.objects.create(afm='123456789', eponimia='ΠΕΛΑΤΗΣ ΑΕ')

        record = create_backup(include_media=False, notes='δοκιμή')

        self.assertIsInstance(record, BackupHistory)
        self.assertTrue(os.path.exists(record.file_path))
        is_valid, error = validate_backup_file(record.file_path)
        self.assertTrue(is_valid, error)

        with zipfile.ZipFile(record.file_path) as zipf:
            data = json.loads(zipf.read('database.json'))
        self.assertTrue(
            any(obj['model'] == 'accounting.clientprofile' for obj in data)
        )

    def test_restore_backup_unknown_id_returns_error(self):
        result = restore_backup(999999, create_safety_backup=False)
        self.assertFalse(result['success'])
        self.assertIn('not found', result['error'])

    def test_restore_backup_missing_file_returns_error(self):
        record = BackupHistory.objects.create(
            filename='gone.zip',
            file_path=os.path.join(self.tmpdir, 'gone.zip'),
            file_size=0,
        )
        result = restore_backup(record.pk, create_safety_backup=False)
        self.assertFalse(result['success'])
