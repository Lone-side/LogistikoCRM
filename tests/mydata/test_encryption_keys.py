# -*- coding: utf-8 -*-
"""
Tests για το ανεξάρτητο encryption key (DATA_ENCRYPTION_KEY_CURRENT)
και το rotation (MultiFernet: CURRENT -> PREVIOUS -> legacy SECRET_KEY).
"""
from io import StringIO

from cryptography.fernet import Fernet
from django.core.management import call_command
from django.test import TestCase, override_settings

from mydata import encryption

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()


class EncryptionKeyTest(TestCase):
    def test_legacy_roundtrip_without_current_key(self):
        encrypted = encryption.encrypt_value('δοκιμή')
        self.assertTrue(encryption.is_encrypted(encrypted))
        self.assertEqual(encryption.decrypt_value(encrypted), 'δοκιμή')

    @override_settings(DATA_ENCRYPTION_KEY_CURRENT=KEY_A)
    def test_current_key_roundtrip(self):
        encrypted = encryption.encrypt_value('secret')
        self.assertEqual(encryption.decrypt_value(encrypted), 'secret')

    def test_legacy_data_still_decrypts_after_current_key_set(self):
        legacy_encrypted = encryption.encrypt_value('παλιό-secret')
        with override_settings(DATA_ENCRYPTION_KEY_CURRENT=KEY_A):
            self.assertEqual(encryption.decrypt_value(legacy_encrypted), 'παλιό-secret')

    def test_previous_key_decrypts_after_rotation(self):
        with override_settings(DATA_ENCRYPTION_KEY_CURRENT=KEY_A):
            encrypted_with_a = encryption.encrypt_value('x')
        with override_settings(
            DATA_ENCRYPTION_KEY_CURRENT=KEY_B, DATA_ENCRYPTION_KEY_PREVIOUS=KEY_A,
        ):
            self.assertEqual(encryption.decrypt_value(encrypted_with_a), 'x')


class RotateCommandTest(TestCase):
    def _make_credential(self):
        from accounting.models import ClientCredential, ClientProfile
        client = ClientProfile.objects.create(
            afm='123456789', eponimia='ΔΟΚΙΜΗ', eidos_ipoxreou='company',
        )
        cred = ClientCredential(client=client, service='TAXISNET', username='u')
        cred.secret = 'rotate-me'
        cred.save()
        return cred

    def test_generate_prints_key(self):
        out = StringIO()
        call_command('rotate_encryption_key', '--generate', stdout=out)
        key_line = out.getvalue().strip().splitlines()[0]
        Fernet(key_line.encode())  # έγκυρο Fernet key

    def test_requires_current_key(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('rotate_encryption_key')

    def test_rotate_reencrypts_with_current(self):
        cred = self._make_credential()  # legacy key
        old_token = cred._secret_encrypted
        with override_settings(DATA_ENCRYPTION_KEY_CURRENT=KEY_A):
            out = StringIO()
            call_command('rotate_encryption_key', stdout=out)
            cred.refresh_from_db()
            self.assertNotEqual(cred._secret_encrypted, old_token)
            self.assertEqual(cred.secret, 'rotate-me')
            # Πλέον αποκρυπτογραφείται με ΜΟΝΟ το νέο κλειδί
            self.assertEqual(
                Fernet(KEY_A.encode()).decrypt(cred._secret_encrypted.encode()).decode(),
                'rotate-me',
            )

    def test_dry_run_changes_nothing(self):
        cred = self._make_credential()
        old_token = cred._secret_encrypted
        with override_settings(DATA_ENCRYPTION_KEY_CURRENT=KEY_A):
            call_command('rotate_encryption_key', '--dry-run', stdout=StringIO())
        cred.refresh_from_db()
        self.assertEqual(cred._secret_encrypted, old_token)
