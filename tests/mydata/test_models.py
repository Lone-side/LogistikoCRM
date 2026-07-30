# -*- coding: utf-8 -*-
"""
Tests για τα mydata models: κρυπτογράφηση credentials, get_api_client,
και τα μαθηματικά ΦΠΑ του VATPeriodResult (υπολογισμός, μεταφορά
πιστωτικού, κλείδωμα περιόδου).
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import ClientProfile
from mydata.encryption import encrypt_value, is_encrypted, safe_decrypt
from mydata.client import MyDataCredentialsNotFoundError
from mydata.models import MyDataCredentials, VATPeriodResult, VATRecord


def make_client_profile(afm='123456783', name='ΠΕΛΑΤΗΣ ΑΕ'):
    return ClientProfile.objects.create(
        afm=afm, eponimia=name, eidos_ipoxreou='company'
    )


class EncryptionTest(TestCase):
    def test_roundtrip(self):
        encrypted = encrypt_value('my-secret-key')
        self.assertNotEqual(encrypted, 'my-secret-key')
        self.assertTrue(is_encrypted(encrypted))
        self.assertEqual(safe_decrypt(encrypted), 'my-secret-key')

    def test_greek_characters(self):
        encrypted = encrypt_value('μυστικό-κλειδί')
        self.assertEqual(safe_decrypt(encrypted), 'μυστικό-κλειδί')

    def test_safe_decrypt_garbage_returns_none(self):
        self.assertIsNone(safe_decrypt('gAAAAA-corrupted-data'))


class MyDataCredentialsTest(TestCase):
    def setUp(self):
        self.client_profile = make_client_profile()

    def test_properties_encrypt_transparently(self):
        creds = MyDataCredentials(client=self.client_profile)
        creds.user_id = 'aade_user'
        creds.subscription_key = 'subkey123'
        creds.save()

        creds.refresh_from_db()
        # Στη βάση: κρυπτογραφημένα
        self.assertTrue(creds._encrypted_user_id.startswith('gAAAAA'))
        self.assertTrue(creds._encrypted_subscription_key.startswith('gAAAAA'))
        # Μέσω properties: αποκρυπτογραφημένα
        self.assertEqual(creds.user_id, 'aade_user')
        self.assertEqual(creds.subscription_key, 'subkey123')
        self.assertTrue(creds.has_credentials)

    def test_setting_credentials_resets_verification(self):
        creds = MyDataCredentials(client=self.client_profile, is_verified=True)
        creds.user_id = 'new_user'
        self.assertFalse(creds.is_verified)

    def test_get_api_client_without_credentials_raises(self):
        creds = MyDataCredentials.objects.create(client=self.client_profile)
        with self.assertRaises(MyDataCredentialsNotFoundError):
            creds.get_api_client()

    def test_get_api_client_uses_sandbox_flag(self):
        creds = MyDataCredentials(client=self.client_profile, is_sandbox=True)
        creds.user_id = 'u'
        creds.subscription_key = 'k'
        creds.save()

        api = creds.get_api_client()
        self.assertTrue(api.is_sandbox)
        self.assertEqual(api.user_id, 'u')
        self.assertEqual(api.subscription_key, 'k')


class VATPeriodResultTest(TestCase):
    def setUp(self):
        self.client_profile = make_client_profile()

    def _record(self, mark, rec_type, vat, month=1, year=2026, cancelled=False):
        return VATRecord.objects.create(
            client=self.client_profile,
            mark=mark,
            issue_date=date(year, month, 15),
            rec_type=rec_type,
            inv_type='1.1',
            vat_category=1,
            net_value=Decimal(vat) * 100 / 24,
            vat_amount=Decimal(vat),
            is_cancelled=cancelled,
        )

    def test_calculate_from_records_payable(self):
        # Εκροές (έσοδα): 240 ΦΠΑ, Εισροές (έξοδα): 100 ΦΠΑ → πληρωτέο 140
        self._record(1001, rec_type=1, vat='240.00')
        self._record(1002, rec_type=2, vat='100.00')
        # Ακυρωμένο — δεν μετράει
        self._record(1003, rec_type=1, vat='999.00', cancelled=True)
        # Άλλος μήνας — δεν μετράει σε μηνιαία περίοδο Ιανουαρίου
        self._record(1004, rec_type=1, vat='50.00', month=2)

        period = VATPeriodResult.objects.create(
            client=self.client_profile, period_type='monthly', year=2026, period=1
        )
        result = period.calculate_from_records()

        self.assertEqual(result['vat_output'], Decimal('240.00'))
        self.assertEqual(result['vat_input'], Decimal('100.00'))
        self.assertEqual(result['final_result'], Decimal('140.00'))
        self.assertEqual(result['credit_to_next'], Decimal('0.00'))

    def test_calculate_with_credit_carry_forward(self):
        # Εισροές > εκροές → πιστωτικό που μεταφέρεται
        self._record(2001, rec_type=1, vat='50.00')
        self._record(2002, rec_type=2, vat='120.00')

        period = VATPeriodResult.objects.create(
            client=self.client_profile, period_type='monthly', year=2026, period=1
        )
        result = period.calculate_from_records()

        self.assertEqual(result['final_result'], Decimal('0.00'))
        self.assertEqual(result['credit_to_next'], Decimal('70.00'))

    def test_inherit_credit_from_previous_period(self):
        prev = VATPeriodResult.objects.create(
            client=self.client_profile, period_type='monthly', year=2026, period=1,
            credit_to_next=Decimal('70.00'),
        )
        self.assertIsNotNone(prev)

        current = VATPeriodResult.objects.create(
            client=self.client_profile, period_type='monthly', year=2026, period=2
        )
        inherited = current.inherit_credit_from_previous()
        self.assertEqual(inherited, Decimal('70.00'))

        # Εκροές 100 - πιστωτικό 70 → πληρωτέο 30
        self._record(3001, rec_type=1, vat='100.00', month=2)
        result = current.calculate_from_records()
        self.assertEqual(result['final_result'], Decimal('30.00'))

    def test_locked_period_refuses_recalculation(self):
        period = VATPeriodResult.objects.create(
            client=self.client_profile, period_type='monthly', year=2026, period=1
        )
        self.assertTrue(period.lock())
        with self.assertRaises(ValidationError):
            period.calculate_from_records()
        with self.assertRaises(ValidationError):
            period.inherit_credit_from_previous()

        self.assertTrue(period.unlock())
        period.calculate_from_records()  # δεν σκάει πλέον

    def test_quarterly_period_spans_three_months(self):
        for i, month in enumerate([1, 2, 3], start=1):
            self._record(4000 + i, rec_type=1, vat='10.00', month=month)
        self._record(4010, rec_type=1, vat='99.00', month=4)  # εκτός Q1

        period = VATPeriodResult.objects.create(
            client=self.client_profile, period_type='quarterly', year=2026, period=1
        )
        result = period.calculate_from_records()
        self.assertEqual(result['vat_output'], Decimal('30.00'))
