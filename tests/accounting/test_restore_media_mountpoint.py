# -*- coding: utf-8 -*-
"""
Regression tests: restore_database με MEDIA_ROOT σε Docker volume mountpoint.

Σε compose εγκατάσταση το MEDIA_ROOT είναι mountpoint και δεν μπορεί να
μετονομαστεί — το media swap πρέπει να γίνεται σε επίπεδο περιεχομένων,
με το safety αντίγραφο ΜΕΣΑ στο volume (.before_restore_*) ώστε να
επιβιώνει από θάνατο του container. Χωρίς αυτό, το documented restore
runbook (DEPLOYMENT.md) αποτύγχανε σε ΚΑΘΕ docker εγκατάσταση με
'Device or resource busy'.

Το mountpoint προσομοιώνεται με patch του os.path.ismount — κανένα
πραγματικό mount δεν χρειάζεται.
"""
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management.base import CommandError
from django.test import TestCase, override_settings, tag

from accounting.management.commands.restore_database import (
    NO_PREVIOUS_MEDIA,
    Command,
)

MODULE = 'accounting.management.commands.restore_database'


@tag('TestCase')
class MediaMountpointSwapTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.media_root = root / 'media'
        self.media_root.mkdir()
        (self.media_root / 'clients').mkdir()
        (self.media_root / 'clients' / 'παλιό_αρχείο.txt').write_text(
            'παλιά δεδομένα', encoding='utf-8')
        self.staged = root / 'staged'
        self.staged.mkdir()
        (self.staged / 'clients').mkdir()
        (self.staged / 'clients' / 'νέο_αρχείο.txt').write_text(
            'νέα δεδομένα', encoding='utf-8')
        self.cmd = Command()
        self.cmd.stdout = mock.Mock()

    def _swap_as_mountpoint(self, state):
        with override_settings(MEDIA_ROOT=str(self.media_root)), \
                mock.patch(f'{MODULE}.os.path.ismount', return_value=True):
            self.cmd._swap_media(self.staged, state)

    def test_mountpoint_swap_uses_contents_mode(self):
        """Fail-before: στο παλιό code το swap κάνει move τον ΙΔΙΟ τον
        MEDIA_ROOT — με mountpoint θα σκάσει/θα άφηνε λάθος layout."""
        state = {}
        self._swap_as_mountpoint(state)
        # Ο MEDIA_ROOT ΥΠΑΡΧΕΙ ακόμη (δεν μετονομάστηκε) με τα νέα δεδομένα
        self.assertTrue(self.media_root.exists())
        self.assertEqual(
            (self.media_root / 'clients' / 'νέο_αρχείο.txt').read_text(
                encoding='utf-8'),
            'νέα δεδομένα')
        # Το safety αντίγραφο ζει ΜΕΣΑ στο volume
        previous = state['previous']
        self.assertEqual(Path(previous).parent, self.media_root)
        self.assertEqual(
            (Path(previous) / 'clients' / 'παλιό_αρχείο.txt').read_text(
                encoding='utf-8'),
            'παλιά δεδομένα')

    def test_mountpoint_rollback_restores_previous_media(self):
        state = {}
        self._swap_as_mountpoint(state)
        with override_settings(MEDIA_ROOT=str(self.media_root)), \
                mock.patch.object(self.cmd, '_rollback_database'):
            with self.assertRaises(CommandError) as ctx:
                self.cmd._rollback_all(
                    ('postgres', Path(self.tmp.name) / 'safety.pgdump'),
                    state['previous'], RuntimeError('boom'))
        self.assertIn('αυτόματο rollback', str(ctx.exception))
        # Τα παλιά media επέστρεψαν, τα νέα και το .before_restore_ έφυγαν
        self.assertEqual(
            (self.media_root / 'clients' / 'παλιό_αρχείο.txt').read_text(
                encoding='utf-8'),
            'παλιά δεδομένα')
        self.assertFalse(list(self.media_root.glob('.before_restore_*')))

    def test_plain_dir_mode_unchanged(self):
        """Χωρίς mountpoint η υπάρχουσα συμπεριφορά μένει ίδια (rename)."""
        state = {}
        with override_settings(MEDIA_ROOT=str(self.media_root)), \
                mock.patch(f'{MODULE}.os.path.ismount', return_value=False):
            self.cmd._swap_media(self.staged, state)
        previous = Path(state['previous'])
        self.assertEqual(previous.parent, self.media_root.parent)
        self.assertTrue(previous.name.startswith('media_before_restore_'))
        self.assertEqual(
            (self.media_root / 'clients' / 'νέο_αρχείο.txt').read_text(
                encoding='utf-8'),
            'νέα δεδομένα')

    def test_empty_mountpoint_swap_and_rollback(self):
        """
        Κενός mountpoint MEDIA_ROOT: το mountpoint υπάρχει ΠΑΝΤΑ (ποτέ
        NO_PREVIOUS_MEDIA σε docker) — το «κενό» καταγράφεται ως άδειο
        .before_restore_ dir, και το rollback επαναφέρει το κενό.
        """
        import shutil
        for child in self.media_root.iterdir():
            shutil.rmtree(child)
        state = {}
        self._swap_as_mountpoint(state)
        # Contents-mode με άδειο safety dir (όχι NO_PREVIOUS_MEDIA)
        self.assertIsNot(state['previous'], NO_PREVIOUS_MEDIA)
        self.assertEqual(Path(state['previous']).parent, self.media_root)
        self.assertEqual(list(Path(state['previous']).iterdir()), [])
        with override_settings(MEDIA_ROOT=str(self.media_root)), \
                mock.patch.object(self.cmd, '_rollback_database'):
            with self.assertRaises(CommandError) as ctx:
                self.cmd._rollback_all(
                    ('postgres', Path(self.tmp.name) / 's.pgdump'),
                    state['previous'], RuntimeError('boom'))
        self.assertIn('αυτόματο rollback', str(ctx.exception))
        # Πίσω στο κενό: ούτε νέα media ούτε .before_restore_ dir
        self.assertEqual(list(self.media_root.iterdir()), [])
