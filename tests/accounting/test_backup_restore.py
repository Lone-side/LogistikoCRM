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
import io
import os
import shutil
import sqlite3
import subprocess
import tarfile
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

    # ------------- backup: media failure = failure, όχι μισό backup ------ #

    def test_backup_fails_when_media_archiving_fails(self):
        """Αποτυχία tar στο backup → CommandError, όχι warning + exit 0."""
        with mock.patch(
            'accounting.management.commands.backup_database.subprocess.run',
            return_value=_FakeProc(1, 'tar: δεν μπόρεσε να γράψει'),
        ):
            with self.assertRaises(CommandError) as ctx:
                self._backup()
        self.assertIn('media', str(ctx.exception).lower())

    def test_partial_backup_is_demoted_and_not_selectable(self):
        """
        Ημιτελές backup δεν πρέπει να μοιάζει πλήρες.

        Αν έμενε ως crm_db_*, το --latest θα το επέλεγε και το γραφείο θα
        ανακάλυπτε την απουσία των εγγράφων τη μέρα που θα τα χρειαζόταν.
        """
        with mock.patch(
            'accounting.management.commands.backup_database.subprocess.run',
            return_value=_FakeProc(1, 'tar failed'),
        ):
            with self.assertRaises(CommandError):
                self._backup()

        self.assertEqual(
            list(self.backup_dir.glob('crm_db_*')), [],
            'ημιτελές backup έμεινε με κανονικό όνομα crm_db_*')
        self.assertTrue(
            list(self.backup_dir.glob('partial_crm_db_*')),
            'το ημιτελές backup δεν μετονομάστηκε σε partial_*')

        # Και δεν επιλέγεται από --latest
        with override_settings(DATABASES=_sqlite_settings(self.db_path)):
            with self.assertRaises(CommandError) as ctx:
                call_command('restore_database', '--latest', '--yes',
                             '--backup-dir', str(self.backup_dir),
                             stdout=StringIO())
        self.assertIn('Δεν υπάρχουν backups', str(ctx.exception))

    def test_backup_fails_when_media_root_missing(self):
        """Χαμένο MEDIA_ROOT χωρίς --skip-media = αποτυχία, όχι σιωπή."""
        shutil.rmtree(self.media)
        with self.assertRaises(CommandError) as ctx:
            self._backup()
        self.assertIn('skip-media', str(ctx.exception))

    def test_backup_media_root_missing_ok_with_skip_media(self):
        """Με ρητό --skip-media το database-only backup επιτρέπεται."""
        shutil.rmtree(self.media)
        self._backup('--skip-media')
        self.assertTrue(list(self.backup_dir.glob('crm_db_*.backup')))
        self.assertEqual(list(self.backup_dir.glob('crm_media_*')), [])

    # ------------- restore: media πρώτα, βάση ανέπαφη σε αποτυχία -------- #

    def test_missing_media_tar_leaves_database_untouched(self):
        """Λείπει το tarball → CommandError ΠΡΙΝ αλλάξει η βάση."""
        self._backup()
        next(self.backup_dir.glob('crm_media_*.tar.gz')).unlink()

        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO pelates VALUES ('998765432', 'ΜΕΤΑ')")
        conn.commit()
        conn.close()
        before = sorted(r[0] for r in self._rows())

        with self.assertRaises(CommandError) as ctx:
            self._restore('--latest')
        self.assertIn('skip-media', str(ctx.exception))
        self.assertEqual(
            sorted(r[0] for r in self._rows()), before,
            'η βάση άλλαξε παρότι έλειπε το media backup')

    def test_corrupt_media_tar_leaves_database_and_media_untouched(self):
        self._backup()
        next(self.backup_dir.glob('crm_media_*.tar.gz')).write_bytes(b'not gzip')

        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO pelates VALUES ('998765432', 'ΜΕΤΑ')")
        conn.commit()
        conn.close()
        before = sorted(r[0] for r in self._rows())
        doc = self.media / 'clients' / 'τιμολόγιο.txt'

        with self.assertRaises(CommandError):
            self._restore('--latest')

        self.assertEqual(sorted(r[0] for r in self._rows()), before,
                         'η βάση άλλαξε από κατεστραμμένο media archive')
        self.assertTrue(doc.exists(), 'τα media χάθηκαν')
        self.assertEqual(doc.read_text(encoding='utf-8'), 'ΦΠΑ Ιανουαρίου')

    def test_unsafe_archive_is_rejected_before_touching_anything(self):
        """
        Archive με absolute path / «..» / symlink προς τα έξω απορρίπτεται.

        Ένα backup μπορεί να έρχεται από άλλο μηχάνημα ή να έχει πειραχθεί:
        χωρίς έλεγχο, η αποσυμπίεση γράφει οπουδήποτε στον server.
        """
        self._backup('--skip-media')
        db_file = next(self.backup_dir.glob('crm_db_*.backup'))
        timestamp = db_file.name[len('crm_db_'):-len('.backup')]
        media_tar = self.backup_dir / f'crm_media_{timestamp}.tar.gz'

        outside = self.tmp / 'ΕΞΩ.txt'
        outside.write_text('αρχικό', encoding='utf-8')
        payload = self.tmp / 'payload.txt'
        payload.write_text('κακόβουλο', encoding='utf-8')

        data = payload.read_bytes()

        def write_archive(arcname):
            # ΟΧΙ tar.add(): κανονικοποιεί το αρχικό «/». Ένας επιτιθέμενος
            # γράφει το header απευθείας, οπότε έτσι το γράφουμε κι εμείς.
            with tarfile.open(media_tar, 'w:gz') as tar:
                info = tarfile.TarInfo(arcname)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))

        for arcname in ('/etc/κακό.txt', 'media/../../ΕΞΩ.txt'):
            with self.subTest(arcname=arcname):
                write_archive(arcname)
                with self.assertRaises(CommandError) as ctx:
                    self._restore('--latest')
                msg = str(ctx.exception)
                self.assertIn('ασφαλ', msg.lower() + msg)
                self.assertEqual(outside.read_text(encoding='utf-8'), 'αρχικό',
                                 'γράφτηκε αρχείο ΕΚΤΟΣ MEDIA_ROOT')

        # symlink που δείχνει εκτός MEDIA_ROOT
        with tarfile.open(media_tar, 'w:gz') as tar:
            info = tarfile.TarInfo('media/evil-link')
            info.type = tarfile.SYMTYPE
            info.linkname = '/etc/passwd'
            tar.addfile(info)
        with self.assertRaises(CommandError):
            self._restore('--latest')

    def test_skip_media_allows_database_only_restore(self):
        """Ρητό --skip-media: επαναφορά μόνο βάσης, media αμετάβλητα."""
        self._backup('--skip-media')
        doc = self.media / 'clients' / 'τιμολόγιο.txt'
        doc.write_text('ΑΛΛΑΓΜΕΝΟ', encoding='utf-8')

        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO pelates VALUES ('998765432', 'ΜΕΤΑ')")
        conn.commit()
        conn.close()

        self._restore('--latest', '--skip-media')

        self.assertEqual([r[0] for r in self._rows()], ['ΑΡΧΙΚΟΣ ΑΕ'])
        self.assertEqual(doc.read_text(encoding='utf-8'), 'ΑΛΛΑΓΜΕΝΟ',
                         'το --skip-media άγγιξε τα media')

    # ------------- συνέπεια: αποτυχία μετά το DB restore ---------------- #

    def test_media_swap_failure_rolls_back_database_and_media(self):
        """
        Το κρίσιμο σενάριο συνέπειας.

        Η βάση έχει ήδη επανέλθει και μετά αποτυγχάνει το swap των media.
        Χωρίς rollback, βάση και έγγραφα θα έμεναν σε διαφορετικές χρονικές
        στιγμές — σιωπηλά.
        """
        self._backup()
        doc = self.media / 'clients' / 'τιμολόγιο.txt'

        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO pelates VALUES ('998765432', 'ΜΕΤΑ ΤΟ BACKUP')")
        conn.commit()
        conn.close()
        db_before = sorted(r[0] for r in self._rows())
        doc.write_text('ΤΡΕΧΟΝ ΠΕΡΙΕΧΟΜΕΝΟ', encoding='utf-8')

        real_move = shutil.move

        def move_that_fails_on_final_swap(src, dst, *a, **kw):
            # Αποτυγχάνει ΜΟΝΟ η μετακίνηση του staged φακέλου στη θέση του
            # MEDIA_ROOT. Το rollback (previous -> MEDIA_ROOT) πρέπει να
            # μπορεί να δουλέψει, αλλιώς το test δεν ελέγχει το rollback.
            if '.restore_staging_' in str(src):
                raise OSError('προσομοιωμένη αποτυχία swap')
            return real_move(src, dst, *a, **kw)

        with mock.patch(
            'accounting.management.commands.restore_database.shutil.move',
            side_effect=move_that_fails_on_final_swap,
        ):
            with self.assertRaises(CommandError) as ctx:
                self._restore('--latest')

        message = str(ctx.exception)
        self.assertIn('rollback', message.lower())
        self.assertEqual(
            sorted(r[0] for r in self._rows()), db_before,
            'η ΒΑΣΗ δεν επανήλθε μετά την αποτυχία του media swap')
        self.assertTrue(doc.exists(), 'τα media δεν επανήλθαν')
        self.assertEqual(doc.read_text(encoding='utf-8'), 'ΤΡΕΧΟΝ ΠΕΡΙΕΧΟΜΕΝΟ')


    # ------------- retention ημιτελών backups --------------------------- #

    def test_partial_backups_are_capped(self):
        """
        Τα partial_* δεν περνούν από τον κανονικό καθαρισμό (σκόπιμα), οπότε
        χωρίς δικό τους όριο μια μόνιμη αποτυχία των media γεμίζει τον δίσκο.

        Τα αρχεία φτιάχνονται απευθείας, με ρητά διαφορετικά timestamps και
        mtimes: αν στηριζόμασταν σε διαδοχικά backups, όλα θα έπεφταν στο
        ίδιο δευτερόλεπτο και θα πατούσαν το ένα το άλλο — το test θα
        περνούσε χωρίς να έχει ελέγξει τίποτα.
        """
        from accounting.management.commands.backup_database import (
            Command as BackupCommand, MAX_PARTIAL_BACKUPS, PARTIAL_PREFIX,
        )

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        created = []
        for i in range(MAX_PARTIAL_BACKUPS + 3):
            path = self.backup_dir / f'{PARTIAL_PREFIX}20260101_1200{i:02d}.pgdump'
            path.write_bytes(b'partial dump')
            os.utime(path, (1_700_000_000 + i * 60, 1_700_000_000 + i * 60))
            created.append(path)

        cmd = BackupCommand()
        cmd.stdout = StringIO()
        cmd._prune_partials(self.backup_dir)

        remaining = sorted(p.name for p in
                           self.backup_dir.glob(f'{PARTIAL_PREFIX}*'))
        self.assertEqual(
            len(remaining), MAX_PARTIAL_BACKUPS,
            f'έμειναν {len(remaining)} ημιτελή backups αντί για '
            f'{MAX_PARTIAL_BACKUPS}: {remaining}')
        self.assertEqual(
            remaining, sorted(p.name for p in created[-MAX_PARTIAL_BACKUPS:]),
            'δεν κρατήθηκαν τα MAX_PARTIAL_BACKUPS νεότερα')

    # ------------- ατομική επαναφορά SQLite ----------------------------- #

    def test_sqlite_restore_is_atomic_on_copy_failure(self):
        """
        Αποτυχία στη μέση της αντιγραφής δεν πρέπει να αφήνει μισή βάση.

        Με απευθείας copy2 πάνω στο ζωντανό αρχείο, ένας γεμάτος δίσκος
        αφήνει κατεστραμμένη βάση ΚΑΙ χωρίς επιστροφή. Με temp file +
        os.replace, το αρχείο ή είναι το παλιό ή το νέο.
        """
        self._backup('--skip-media')

        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO pelates VALUES ('998765432', 'ΜΕΤΑ')")
        conn.commit()
        conn.close()
        before = sorted(r[0] for r in self._rows())
        size_before = self.db_path.stat().st_size

        real_copy2 = shutil.copy2

        def copy_that_fails_on_restore_temp(src, dst, *a, **kw):
            if '.restore_' in str(dst):
                raise OSError('προσομοιωμένος γεμάτος δίσκος')
            return real_copy2(src, dst, *a, **kw)

        with mock.patch(
            'accounting.management.commands.restore_database.shutil.copy2',
            side_effect=copy_that_fails_on_restore_temp,
        ):
            with self.assertRaises(CommandError):
                self._restore('--latest', '--skip-media')

        self.assertEqual(sorted(r[0] for r in self._rows()), before,
                         'η βάση άλλαξε παρότι η αντιγραφή απέτυχε')
        self.assertEqual(self.db_path.stat().st_size, size_before)
        leftovers = list(self.tmp.glob('.test_db.sqlite3.restore_*'))
        self.assertEqual(leftovers, [], f'έμεινε προσωρινό αρχείο: {leftovers}')

    # ------------- sentinel: δεν υπήρχαν προηγούμενα media --------------- #

    def test_rollback_removes_new_media_when_none_existed_before(self):
        """
        Αν δεν υπήρχαν media πριν, το rollback πρέπει να τα ΑΦΑΙΡΕΣΕΙ.

        Με σκέτο `None` για «δεν υπήρχαν προηγούμενα», το rollback δεν
        ξεχώριζε αυτή την περίπτωση από το «το swap δεν έτρεξε ποτέ» και
        άφηνε πίσω media που δεν αντιστοιχούν στη βάση μετά το rollback.
        """
        from accounting.management.commands.restore_database import (
            Command as RestoreCommand,
        )

        self._backup()
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO pelates VALUES ('998765432', 'ΜΕΤΑ ΤΟ BACKUP')")
        conn.commit()
        conn.close()
        db_before = sorted(r[0] for r in self._rows())

        # Καμία προηγούμενη κατάσταση media.
        shutil.rmtree(self.media)

        real_swap = RestoreCommand._swap_media

        def swap_then_fail(cmd, staged_media, state):
            real_swap(cmd, staged_media, state)
            raise OSError('προσομοιωμένη αποτυχία μετά το swap')

        with mock.patch.object(RestoreCommand, '_swap_media', swap_then_fail):
            with self.assertRaises(CommandError) as ctx:
                self._restore('--latest')

        self.assertIn('rollback', str(ctx.exception).lower())
        self.assertFalse(
            self.media.exists(),
            'το rollback άφησε πίσω media ενώ πριν δεν υπήρχαν')
        self.assertEqual(sorted(r[0] for r in self._rows()), db_before,
                         'η βάση δεν επανήλθε')

    def test_state_recorded_before_stdout_write_after_move(self):
        """
        Το state πρέπει να γράφεται ΑΜΕΣΩΣ μετά τη μετακίνηση των παλιών
        media, πριν από οποιαδήποτε άλλη ενέργεια που μπορεί να αποτύχει.

        Αν το stdout.write σκάσει (κλειστό stream, σπασμένο pipe) ενώ τα
        παλιά media έχουν ήδη μετακινηθεί, το rollback πρέπει να ξέρει πού
        βρίσκονται. Αλλιώς μένουν σε φάκελο `media_before_restore_*` που
        κανείς δεν ψάχνει, με τη βάση γυρισμένη πίσω.
        """
        from accounting.management.commands.restore_database import (
            Command as RestoreCommand,
        )

        staging = self.tmp / 'staged_media'
        (staging / 'clients').mkdir(parents=True)
        (staging / 'clients' / 'νέο.txt').write_text('ΝΕΟ', encoding='utf-8')

        class ExplodingStdout:
            def write(self, *a, **kw):
                raise OSError('σπασμένο pipe')

        cmd = RestoreCommand()
        cmd.stdout = ExplodingStdout()
        state = {}

        with override_settings(MEDIA_ROOT=str(self.media)):
            with self.assertRaises(OSError):
                cmd._swap_media(staging, state)

            previous = state.get('previous')
            self.assertIsNotNone(
                previous,
                'το state δεν καταγράφηκε πριν το stdout.write — το rollback '
                'δεν μπορεί να βρει τα παλιά media')
            self.assertTrue(Path(previous).exists(),
                            f'η καταγεγραμμένη διαδρομή δεν υπάρχει: {previous}')

            # Και είναι όντως αρκετό για πλήρες rollback.
            cmd.stdout = StringIO()
            with override_settings(DATABASES=_sqlite_settings(self.db_path)):
                with self.assertRaises(CommandError):
                    cmd._rollback_all(('sqlite', None), previous,
                                      OSError('σπασμένο pipe'))

        doc = self.media / 'clients' / 'τιμολόγιο.txt'
        self.assertTrue(doc.exists(), 'τα παλιά media δεν επανήλθαν')
        self.assertEqual(doc.read_text(encoding='utf-8'), 'ΦΠΑ Ιανουαρίου')

    def test_rollback_distinguishes_no_previous_media_from_no_swap(self):
        """
        Το ουσιώδες του sentinel: δύο καταστάσεις, αντίθετο rollback.

        Άμεσος έλεγχος στο _rollback_all γιατί μόνο έτσι φαίνεται ότι το
        `None` («το swap δεν έτρεξε») και το NO_PREVIOUS_MEDIA («έτρεξε, αλλά
        δεν υπήρχαν προηγούμενα») δεν είναι πια η ίδια τιμή.
        """
        from accounting.management.commands.restore_database import (
            NO_PREVIOUS_MEDIA, Command as RestoreCommand,
        )

        cmd = RestoreCommand()
        cmd.stdout = StringIO()
        exc = OSError('αποτυχία')

        # (α) Το swap δεν έτρεξε ποτέ → τα media μένουν ως έχουν.
        with override_settings(MEDIA_ROOT=str(self.media),
                               DATABASES=_sqlite_settings(self.db_path)):
            with self.assertRaises(CommandError):
                cmd._rollback_all(('sqlite', None), None, exc)
        self.assertTrue(self.media.exists(),
                        'το rollback έσβησε media που δεν είχε αγγίξει')

        # (β) Το swap έβαλε νέα media εκεί που δεν υπήρχε τίποτα → αφαίρεση.
        with override_settings(MEDIA_ROOT=str(self.media),
                               DATABASES=_sqlite_settings(self.db_path)):
            with self.assertRaises(CommandError):
                cmd._rollback_all(('sqlite', None), NO_PREVIOUS_MEDIA, exc)
        self.assertFalse(self.media.exists(),
                         'τα νέα media έμειναν πίσω μετά το rollback')

    # ------------- fail closed αντί για unfiltered extractall ----------- #

    def test_extraction_fails_closed_without_tar_filter(self):
        """
        Χωρίς υποστήριξη `filter='data'` η εντολή ΠΡΕΠΕΙ να αποτύχει.

        Το παλιό fallback έπιανε το TypeError και ξανακαλούσε το extractall
        χωρίς φίλτρο — δηλαδή ακριβώς η ανασφαλής αποσυμπίεση, σιωπηλά.
        Το side_effect εδώ αποτυγχάνει μόνο στην πρώτη κλήση: αν υπήρχε
        fallback, η δεύτερη θα πετύχαινε και η εντολή θα τερμάτιζε κανονικά.
        """
        self._backup()
        doc = self.media / 'clients' / 'τιμολόγιο.txt'
        doc.write_text('ΤΡΕΧΟΝ', encoding='utf-8')

        real_extractall = tarfile.TarFile.extractall
        calls = []

        def extractall_without_filter(tar_self, *a, **kw):
            calls.append(kw)
            if len(calls) == 1:
                raise TypeError("extractall() got an unexpected keyword "
                                "argument 'filter'")
            return real_extractall(tar_self, *a, **kw)

        with mock.patch.object(tarfile.TarFile, 'extractall',
                               extractall_without_filter):
            with self.assertRaises(CommandError):
                self._restore('--latest')

        self.assertEqual(len(calls), 1,
                         'έγινε δεύτερη, αφιλτράριστη αποσυμπίεση')
        self.assertEqual(doc.read_text(encoding='utf-8'), 'ΤΡΕΧΟΝ',
                         'τα media άλλαξαν παρά την αποτυχία')


class _FakeProc:
    """Ελάχιστο stand-in για CompletedProcess."""

    def __init__(self, returncode, stderr=''):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ''


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
