# -*- coding: utf-8 -*-
"""
Auto-recalc μετά το sync: το mydata_sync_vat πρέπει, μετά τον συγχρονισμό
records, να ξαναϋπολογίζει τις ΜΗ κλειδωμένες περιόδους που επικαλύπτουν το
εύρος — ώστε οι αποθηκευμένες τιμές να μη μένουν stale. Οι κλειδωμένες ΔΕΝ
αγγίζονται.

Το API client mock-άρεται (request_vat_info → άδειο) ώστε να μη χτυπά δίκτυο·
ο recalc τρέχει στο τέλος και πιάνει τα ΥΠΑΡΧΟΝΤΑ records.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.test import TestCase

from accounting.models import ClientProfile
from mydata.models import MyDataCredentials, VATRecord, VATPeriodResult


class AutoRecalcAfterSyncTest(TestCase):
    def setUp(self):
        self.client_p = ClientProfile.objects.create(
            afm='159053680', eponimia='ΔΟΚΙΜΗ ΑΕ', eidos_ipoxreou='company')
        self.creds = MyDataCredentials(client=self.client_p, is_active=True)
        self.creds.user_id = 'u'
        self.creds.subscription_key = 'k'
        self.creds.save()
        # Output record Ιανουαρίου 2026 (ΦΠΑ 24.00)
        VATRecord.objects.create(
            client=self.client_p, mark=400000000000001, issue_date=date(2026, 1, 10),
            is_cancelled=False, rec_type=1, inv_type='ΕΚΡΟΕΣ_303', vat_category=1,
            net_value=Decimal('100.00'), vat_amount=Decimal('24.00'), income_code='303')

    def _run_sync(self, **extra):
        """Τρέχει το command με mocked API (κανένα νέο record από το δίκτυο)."""
        mock_client = MagicMock()
        mock_client.request_vat_info.return_value = iter([])
        args = ['--client', '159053680', '--year', '2026', '--month', '1', '--no-clear']
        for k, v in extra.items():
            if v is True:
                args.append(f'--{k}')
        with patch('mydata.models.MyDataCredentials.get_api_client', return_value=mock_client):
            call_command('mydata_sync_vat', *args)

    def test_unlocked_overlapping_period_is_recalculated(self):
        period = VATPeriodResult.objects.create(
            client=self.client_p, period_type='monthly', year=2026, period=1,
            is_locked=False, vat_output=Decimal('0.00'))  # stale
        self._run_sync()
        period.refresh_from_db()
        self.assertEqual(period.vat_output, Decimal('24.00'))

    def test_locked_period_is_not_touched(self):
        period = VATPeriodResult.objects.create(
            client=self.client_p, period_type='monthly', year=2026, period=1,
            is_locked=True, vat_output=Decimal('0.00'))  # finalized, must stay
        # --force ώστε να προσπεραστεί ο locked guard και να φτάσει στο recalc step
        self._run_sync(force=True)
        period.refresh_from_db()
        self.assertEqual(period.vat_output, Decimal('0.00'))

    def test_non_overlapping_period_is_not_recalculated(self):
        # Περίοδος Απριλίου — εκτός του συγχρονισμένου εύρους (Ιαν) → δεν αγγίζεται.
        period = VATPeriodResult.objects.create(
            client=self.client_p, period_type='monthly', year=2026, period=4,
            is_locked=False, vat_output=Decimal('5.00'))
        self._run_sync()
        period.refresh_from_db()
        self.assertEqual(period.vat_output, Decimal('5.00'))
