# -*- coding: utf-8 -*-
"""
Regression tests για το setup_obligations σε ΚΑΘΑΡΗ βάση.

Το command απέτυχε σε κάθε καθαρή εγκατάσταση με FieldError: περνούσε
'profile': <ObligationProfile> ως direct kwarg στο
ObligationType.objects.get_or_create, ενώ το πεδίο είναι το ManyToMany
`profiles` (schema drift μετά τη συγγραφή του command). Εντοπίστηκε στο
office runtime acceptance (PR #202) — εδώ αποδεικνύεται και κλειδώνει:

1. Clean-install: το command τρέχει χωρίς exception σε άδεια βάση.
2. Σωστές M2M σχέσεις: το προβλεπόμενο mapping τύπων ↔ profiles.
3. Idempotency: δεύτερη εκτέλεση χωρίς duplicates ή exception.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, tag

from accounting.models import (
    ObligationGroup,
    ObligationProfile,
    ObligationType,
)

# Το προβλεπόμενο mapping του command (πηγή: τα data dicts του
# setup_obligations — ενημερώνεται μαζί τους).
MISTHODOSIA_CODES = {
    'APD_EFKA', 'APD_TEKA', 'APOD_PAYROLL', 'LEAVES',
    'OAED_PROGRAMS', 'LEAVE_TABLE',
}
ENDOKOINOTIKES_CODES = {'INTRA_EU', 'VIES'}
EXPECTED_TYPE_COUNT = 23


def run_setup_obligations():
    out = StringIO()
    call_command('setup_obligations', stdout=out)
    return out.getvalue()


@tag('TestCase')
class SetupObligationsCleanInstallTest(TestCase):
    """Το command πρέπει να δουλεύει σε πραγματικά καθαρή βάση."""

    def test_clean_install_succeeds(self):
        """Fail-before: FieldError 'profile' σε καθαρή βάση."""
        output = run_setup_obligations()
        self.assertIn('Ολοκληρώθηκε', output)
        self.assertEqual(ObligationGroup.objects.count(), 1)
        self.assertEqual(ObligationProfile.objects.count(), 2)
        self.assertEqual(ObligationType.objects.count(), EXPECTED_TYPE_COUNT)

    def test_m2m_profile_mapping(self):
        """Η προβλεπόμενη αντιστοίχιση profiles διατηρείται (M2M)."""
        run_setup_obligations()
        misthodosia = ObligationProfile.objects.get(name='Μισθοδοσία')
        endokoinotikes = ObligationProfile.objects.get(name='Ενδοκοινοτικές')

        self.assertEqual(
            set(ObligationType.objects.filter(
                profiles=misthodosia).values_list('code', flat=True)),
            MISTHODOSIA_CODES,
        )
        self.assertEqual(
            set(ObligationType.objects.filter(
                profiles=endokoinotikes).values_list('code', flat=True)),
            ENDOKOINOTIKES_CODES,
        )
        # Τύποι χωρίς profile στο data δεν αποκτούν κανένα
        self.assertEqual(
            ObligationType.objects.get(code='DYPA').profiles.count(), 0)
        self.assertEqual(
            ObligationType.objects.get(code='VAT_MONTHLY').profiles.count(), 0)

    def test_vat_exclusion_group_wired(self):
        run_setup_obligations()
        vat_group = ObligationGroup.objects.get(name='ΦΠΑ')
        for code in ('VAT_MONTHLY', 'VAT_QUARTERLY'):
            self.assertEqual(
                ObligationType.objects.get(code=code).exclusion_group,
                vat_group, msg=code)

    def test_double_run_is_idempotent(self):
        """Δύο εκτελέσεις: χωρίς exception, duplicates ή διπλά M2M links."""
        run_setup_obligations()
        output = run_setup_obligations()
        self.assertIn('Ολοκληρώθηκε', output)
        self.assertEqual(ObligationGroup.objects.count(), 1)
        self.assertEqual(ObligationProfile.objects.count(), 2)
        self.assertEqual(ObligationType.objects.count(), EXPECTED_TYPE_COUNT)
        misthodosia = ObligationProfile.objects.get(name='Μισθοδοσία')
        for code in MISTHODOSIA_CODES:
            self.assertEqual(
                ObligationType.objects.get(
                    code=code).profiles.filter(pk=misthodosia.pk).count(),
                1, msg=code)

    def test_existing_type_gains_missing_profile_link(self):
        """
        Τύπος που προϋπάρχει ΧΩΡΙΣ profile link (π.χ. από παλιά μερική
        εκτέλεση πριν το fix) αποκτά το σωστό link στο επόμενο run.
        """
        ObligationType.objects.create(
            name='ΑΠΔ ΕΦΚΑ', code='APD_EFKA',
            frequency='monthly', deadline_type='last_day')
        run_setup_obligations()
        misthodosia = ObligationProfile.objects.get(name='Μισθοδοσία')
        self.assertTrue(
            ObligationType.objects.get(code='APD_EFKA')
            .profiles.filter(pk=misthodosia.pk).exists())
