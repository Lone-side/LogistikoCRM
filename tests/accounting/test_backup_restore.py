# -*- coding: utf-8 -*-
"""
Tests για το ζεύγος backup_database / restore_database.

Το κρίσιμο που κλειδώνουν εδώ είναι το **συμβόλαιο ονομάτων**: ό,τι παράγει
το backup πρέπει να μπορεί να το βρει και να το επαναφέρει το restore.
Παλαιότερα οι δύο εντολές ζούσαν σε διαφορετικά apps με ασύμβατα ονόματα
(`crm_db_*.backup` vs `backup_*.sqlite3`) και διαφορετικούς φακέλους, οπότε
η επαναφορά ήταν αδύνατη — χωρίς να το πιάνει κανένα test.

Τα tests είναι ερμητικά: στήνουν δικό τους αρχείο SQLite και δικό τους
MEDIA_ROOT μέσω override_settings, ώστε να μην αγγίζουν την πραγματική
βάση των tests (που στο CI είναι PostgreSQL).
"""
import shutil
import sqlite3
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


def _sqlite_settings(db_path):
    return {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(db_path),
            'USER': '', 'PASSWORD': '', 'HOST': '', 'PORT': '',
        }
    }


class BackupRestoreContractTests(SimpleTestCase):
    """Ερμητικά tests πάνω σε δικό μας SQLite + MEDIA_ROOT."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='bkrt_'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.backup_dir = self.tmp / 'backups'
        self.media = self.tmp / 'media'
        (self.media / 'clients').mkdir(parents=True)
        # Ελληνικό περιεχόμενο — θέλουμε να επιβεβαιώσουμε UTF-8 round-trip
        (self.media / 'clients' / 'τιμολόγιο.txt').write_text(
            'ΦΠΑ Ιανουαρίου', encoding='utf-8'
        )

        self.db_path = self.tmp / 'test_db.sqlite3'
        conn = sqlite3.connect(self.db_path)
        conn.execute('CREATE TABLE pelates (afm TEXT, onoma TEXT)')
        conn.execute("INSERT INTO pelates VALUES ('094014201', 'ΑΡΧΙΚΟΣ ΑΕ')")
        conn.commit()
        conn.close()

    def _rows(self):
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute('SELECT onoma FROM pelates').fetchall()
        finally:
            conn.close()

    def _backup(self, *extra):
        with override_settings(
            DATABASES=_sqlite_settings(self.db_path), MEDIA_ROOT=str(self.media)
        ):
            out = StringIO()
            call_command(
                'backup_database', '--output-dir', str(self.backup_dir),
                *extra, stdout=out, stderr=StringIO()
            )
            return out.getvalue()

    def _restore(self, *args):
        with override_settings(
            DATABASES=_sqlite_settings(self.db_path), MEDIA_ROOT=str(self.media)
        ):
            out = StringIO()
            call_command(
                'restore_database', *args,
                '--backup-dir', str(self.backup_dir), '--yes',
                stdout=out, stderr=StringIO()
            )
            return out.getvalue()

    # -------------------------------------------------------------- #

    def test_backup_produces_db_and_media_files(self):
        self._backup()
        names = sorted(p.name for p in self.backup_dir.iterdir())
        self.assertEqual(len(names), 2, names)
        self.assertTrue(any(n.startswith('crm_db_') and n.endswith('.backup')
                            for n in names), names)
        self.assertTrue(any(n.startswith('crm_media_') and n.endswith('.tar.gz')
                            for n in names), names)

    def test_restore_finds_what_backup_produced(self):
        """Το συμβόλαιο ονομάτων: το restore βλέπει το αρχείο του backup."""
        self._backup('--skip-media')
        listing = self._restore_list()
        produced = next(p.name for p in self.backup_dir.iterdir())
        self.assertIn(produced, listing)

    def _restore_list(self):
        with override_settings(DATABASES=_sqlite_settings(self.db_path)):
            out = StringIO()
            call_command('restore_database', '--list',
                         '--backup-dir', str(self.backup_dir), stdout=out)
            return out.getvalue()

    def test_database_round_trip_reverts_changes(self):
        self._backup('--skip-media')

        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO pelates VALUES ('998765432', 'ΜΕΤΑ ΤΟ BACKUP ΕΠΕ')")
        conn.commit()
        conn.close()
        self.assertEqual(len(self._rows()), 2)

        self._restore('--latest', '--skip-media')

        rows = self._rows()
        self.assertEqual([r[0] for r in rows], ['ΑΡΧΙΚΟΣ ΑΕ'])

    def test_media_round_trip_restores_deleted_file(self):
        self._backup()
        doc = self.media / 'clients' / 'τιμολόγιο.txt'
        doc.unlink()
        self.assertFalse(doc.exists())

        self._restore('--latest')

        self.assertTrue(doc.exists())
        self.assertEqual(doc.read_text(encoding='utf-8'), 'ΦΠΑ Ιανουαρίου')

    def test_restore_accepts_timestamp_and_filename(self):
        self._backup('--skip-media')
        produced = next(p for p in self.backup_dir.iterdir())
        timestamp = produced.name[len('crm_db_'):-len(produced.suffix)]

        # Και τα δύο πρέπει να δουλεύουν, χωρίς εξαίρεση
        self._restore(timestamp, '--skip-media')
        self._restore(produced.name, '--skip-media')

    def test_sqlite_backup_rejected_on_postgres(self):
        """Guard: λάθος μηχανή βάσης απορρίπτεται πριν αγγίξει τα δεδομένα."""
        self._backup('--skip-media')
        pg = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'irrelevant', 'USER': '', 'PASSWORD': '',
                'HOST': '', 'PORT': '',
            }
        }
        with override_settings(DATABASES=pg):
            with self.assertRaises(CommandError) as ctx:
                call_command('restore_database', '--latest',
                             '--backup-dir', str(self.backup_dir), '--yes',
                             stdout=StringIO())
        self.assertIn('SQLite', str(ctx.exception))

    def test_unknown_backup_name_is_a_clean_error(self):
        self._backup('--skip-media')
        with override_settings(DATABASES=_sqlite_settings(self.db_path)):
            with self.assertRaises(CommandError):
                call_command('restore_database', 'δεν-υπάρχει',
                             '--backup-dir', str(self.backup_dir), '--yes',
                             stdout=StringIO())

    def test_cleanup_removes_media_alongside_database(self):
        """Τα media tarballs δεν πρέπει να μένουν ορφανά μετά τον καθαρισμό."""
        import os
        import time

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        old_ts = '20200101_000000'
        old_db = self.backup_dir / f'crm_db_{old_ts}.backup'
        old_media = self.backup_dir / f'crm_media_{old_ts}.tar.gz'
        old_db.write_bytes(b'old')
        old_media.write_bytes(b'old')
        ancient = time.time() - 90 * 86400
        os.utime(old_db, (ancient, ancient))
        os.utime(old_media, (ancient, ancient))

        # keep-days=30 → το 90 ημερών ζευγάρι πρέπει να φύγει ολόκληρο
        self._backup('--keep-days', '30')

        self.assertFalse(old_db.exists(), 'το παλιό backup βάσης έμεινε')
        self.assertFalse(old_media.exists(), 'το media tarball έμεινε ορφανό')
