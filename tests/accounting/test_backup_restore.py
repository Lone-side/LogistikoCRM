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
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
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

    # ---------------- media: αποτυχία = αποτυχία, με rollback ------------ #

    def test_media_failure_is_a_command_error_not_silent_success(self):
        """
        Κατεστραμμένο media tarball πρέπει να ΑΠΟΤΥΓΧΑΝΕΙ την εντολή.

        Παλαιότερα έβγαινε warning και exit 0: το cron και ο operator
        έβλεπαν «επιτυχία» ενώ τα έγγραφα πελατών δεν είχαν επανέλθει.
        """
        self._backup()
        media_tar = next(self.backup_dir.glob('crm_media_*.tar.gz'))
        media_tar.write_bytes(b'not a gzip tarball')

        with self.assertRaises(CommandError) as ctx:
            self._restore('--latest')
        self.assertIn('media', str(ctx.exception).lower())

    def test_media_rolled_back_when_extraction_fails(self):
        """
        Σε αποτυχία tar, τα προηγούμενα media επιστρέφουν στη θέση τους.

        Χωρίς rollback το γραφείο θα έμενε ΧΩΡΙΣ έγγραφα: ούτε τα παλιά
        (μετακινημένα στην άκρη) ούτε τα νέα (δεν αποσυμπιέστηκαν).
        """
        self._backup()
        doc = self.media / 'clients' / 'τιμολόγιο.txt'
        self.assertTrue(doc.exists())

        media_tar = next(self.backup_dir.glob('crm_media_*.tar.gz'))
        media_tar.write_bytes(b'not a gzip tarball')

        with self.assertRaises(CommandError):
            self._restore('--latest')

        self.assertTrue(
            doc.exists(),
            'ΑΠΩΛΕΙΑ ΔΕΔΟΜΕΝΩΝ: τα media δεν επέστρεψαν μετά την αποτυχία')
        self.assertEqual(doc.read_text(encoding='utf-8'), 'ΦΠΑ Ιανουαρίου')


@unittest.skipUnless(
    connection.vendor == 'postgresql',
    'Απαιτεί PostgreSQL (pg_dump/pg_restore) — παραλείπεται σε SQLite.',
)
class PostgresRestoreSafetyTests(SimpleTestCase):
    """
    ΠΡΑΓΜΑΤΙΚΟ round-trip σε PostgreSQL, σε **αναλώσιμη** βάση.

    Δεν αγγίζει ποτέ την test database: φτιάχνει δική της βάση
    `restore_rt_<pid>`, δουλεύει εκεί και τη διαγράφει στο τέλος.

    Καλύπτει τα τρία σημεία που κάνουν μια επαναφορά ασφαλή ή επικίνδυνη:
      1. πραγματικό safety pg_dump ΠΡΙΝ την επαναφορά,
      2. abort αν το safety dump δεν μπορεί να ληφθεί,
      3. --single-transaction: αποτυχία = καμία αλλαγή, όχι μισή βάση.
    """

    databases = set()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db_name = f'restore_rt_{os.getpid()}'
        cls.base = dict(settings.DATABASES['default'])
        cls._admin_sql(f'DROP DATABASE IF EXISTS {cls.db_name}')
        cls._admin_sql(f'CREATE DATABASE {cls.db_name}')

    @classmethod
    def tearDownClass(cls):
        cls._admin_sql(f'DROP DATABASE IF EXISTS {cls.db_name}')
        super().tearDownClass()

    @classmethod
    def _admin_sql(cls, sql):
        import psycopg2
        conn = psycopg2.connect(
            dbname='postgres',
            user=cls.base.get('USER') or None,
            password=cls.base.get('PASSWORD') or None,
            host=cls.base.get('HOST') or None,
            port=cls.base.get('PORT') or None,
        )
        conn.autocommit = True
        try:
            conn.cursor().execute(sql)
        finally:
            conn.close()

    def _db_settings(self):
        cfg = dict(self.base)
        cfg['NAME'] = self.db_name
        return {'default': cfg}

    def _sql(self, sql, fetch=False):
        import psycopg2
        conn = psycopg2.connect(
            dbname=self.db_name,
            user=self.base.get('USER') or None,
            password=self.base.get('PASSWORD') or None,
            host=self.base.get('HOST') or None,
            port=self.base.get('PORT') or None,
        )
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return cur.fetchall() if fetch else None
        finally:
            conn.close()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='pgrt_'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.backup_dir = self.tmp / 'backups'
        self._sql('DROP TABLE IF EXISTS pelates')
        self._sql('CREATE TABLE pelates (afm TEXT, onoma TEXT)')
        self._sql("INSERT INTO pelates VALUES ('094014201', 'ΑΡΧΙΚΟΣ ΑΕ')")

    def _rows(self):
        return sorted(r[0] for r in self._sql('SELECT onoma FROM pelates', True))

    def _run(self, command, *args):
        with override_settings(DATABASES=self._db_settings()):
            return call_command(
                command, *args, stdout=StringIO(), stderr=StringIO())

    def test_real_round_trip_reverts_changes(self):
        self._run('backup_database', '--output-dir', str(self.backup_dir),
                  '--skip-media')
        self.assertTrue(list(self.backup_dir.glob('crm_db_*.pgdump')))

        self._sql("INSERT INTO pelates VALUES ('998765432', 'ΜΕΤΑ ΤΟ BACKUP')")
        self.assertEqual(len(self._rows()), 2)

        self._run('restore_database', '--latest', '--yes', '--skip-media',
                  '--backup-dir', str(self.backup_dir))

        self.assertEqual(self._rows(), ['ΑΡΧΙΚΟΣ ΑΕ'])

    def test_safety_dump_is_taken_before_restore(self):
        """Πραγματικό pg_dump της τρέχουσας βάσης, όχι απλή δήλωση."""
        self._run('backup_database', '--output-dir', str(self.backup_dir),
                  '--skip-media')
        self._run('restore_database', '--latest', '--yes', '--skip-media',
                  '--backup-dir', str(self.backup_dir))

        safety = list(self.backup_dir.glob('pre_restore_*.pgdump'))
        self.assertEqual(len(safety), 1, 'δεν δημιουργήθηκε safety dump')
        self.assertGreater(
            safety[0].stat().st_size, 0, 'το safety dump είναι κενό')

    def test_aborts_when_safety_dump_cannot_be_taken(self):
        """Χωρίς pg_dump δεν ξεκινά καθόλου restore — καλύτερα τίποτα."""
        self._run('backup_database', '--output-dir', str(self.backup_dir),
                  '--skip-media')
        before = self._rows()

        real_which = shutil.which

        def fake_which(name, *a, **kw):
            return None if name == 'pg_dump' else real_which(name, *a, **kw)

        with mock.patch(
            'accounting.management.commands.restore_database.shutil.which',
            side_effect=fake_which,
        ):
            with self.assertRaises(CommandError) as ctx:
                self._run('restore_database', '--latest', '--yes',
                          '--skip-media', '--backup-dir', str(self.backup_dir))

        self.assertIn('pg_dump', str(ctx.exception))
        self.assertEqual(self._rows(), before, 'η βάση άλλαξε παρά το abort')

    def test_restore_uses_single_transaction(self):
        """
        Το pg_restore ΠΡΕΠΕΙ να τρέχει με --single-transaction.

        Χωρίς αυτό, σφάλμα στη μέση αφήνει τη βάση μισοεπαναφερμένη: το
        --clean έχει ήδη κάνει DROP και τα δεδομένα δεν έχουν μπει.

        Ο έλεγχος γίνεται στο ίδιο το command line και όχι μέσω
        κατεστραμμένου dump: ένα άκυρο αρχείο απορρίπτεται ήδη στο parsing
        του header, δηλαδή ΠΡΙΝ εκτελεστεί οτιδήποτε — οπότε δεν ξεχωρίζει
        αν το flag υπάρχει ή όχι.
        """
        self._run('backup_database', '--output-dir', str(self.backup_dir),
                  '--skip-media')

        real_run = subprocess.run
        seen = []

        def capture(cmd, *a, **kw):
            if cmd and 'pg_restore' in str(cmd[0]):
                seen.append(cmd)
            return real_run(cmd, *a, **kw)

        with mock.patch(
            'accounting.management.commands.restore_database.subprocess.run',
            side_effect=capture,
        ):
            self._run('restore_database', '--latest', '--yes', '--skip-media',
                      '--backup-dir', str(self.backup_dir))

        self.assertTrue(seen, 'δεν κλήθηκε καθόλου το pg_restore')
        self.assertIn(
            '--single-transaction', seen[0],
            'το pg_restore τρέχει ΧΩΡΙΣ --single-transaction: μια αποτυχία '
            'στη μέση θα άφηνε τη βάση μισοεπαναφερμένη.')

    def test_corrupt_dump_leaves_database_untouched(self):
        """
        Κατεστραμμένο dump: αποτυχία με σαφές μήνυμα, χωρίς απώλεια.

        Σημείωση εγκυρότητας: αυτό περνά και χωρίς --single-transaction
        (το άκυρο αρχείο κόβεται στο parsing). Το flag ελέγχεται χωριστά
        στο test_restore_uses_single_transaction.
        """
        self._sql("INSERT INTO pelates VALUES ('998765432', 'ΑΚΕΡΑΙΑ Β')")
        before = self._rows()

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        (self.backup_dir / 'crm_db_29991231_235959.pgdump').write_bytes(
            b'PGDMP corrupted payload, not a real custom-format dump')

        with self.assertRaises(CommandError) as ctx:
            self._run('restore_database', '--latest', '--yes', '--skip-media',
                      '--backup-dir', str(self.backup_dir))

        self.assertIn('pg_restore', str(ctx.exception))
        self.assertEqual(
            self._rows(), before,
            'ΑΠΩΛΕΙΑ ΔΕΔΟΜΕΝΩΝ: η βάση άλλαξε παρά την αποτυχία του restore')
