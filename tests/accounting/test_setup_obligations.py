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
BASE_TYPE_COUNT = 23
# Default catalog: 52 ονομασίες, εκ των οποίων η «ΑΠΔ ΤΕΚΑ» υπάρχει ήδη
# στο βασικό σετ (name-dedupe) => 51 νέοι τύποι.
CATALOG_NEW_COUNT = 51
EXPECTED_TYPE_COUNT = BASE_TYPE_COUNT + CATALOG_NEW_COUNT


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


@tag('TestCase')
class DefaultCatalogTest(TestCase):
    """Το default catalog: πλήρες σε clean install, idempotent, ανέγγιχτο
    ό,τι προϋπάρχει, χωρίς επινοημένους κανόνες."""

    def test_catalog_names_have_no_internal_duplicates(self):
        from accounting.management.commands.setup_obligations import (
            DEFAULT_CATALOG,
        )
        names = [name for name, _ in DEFAULT_CATALOG]
        codes = [code for _, code in DEFAULT_CATALOG]
        self.assertEqual(len(names), 52)
        self.assertEqual(len(set(names)), 52)
        self.assertEqual(len(set(codes)), 52)

    def test_clean_install_creates_full_catalog(self):
        from accounting.management.commands.setup_obligations import (
            DEFAULT_CATALOG,
        )
        run_setup_obligations()
        self.assertEqual(ObligationType.objects.count(), EXPECTED_TYPE_COUNT)
        for name, _ in DEFAULT_CATALOG:
            self.assertTrue(
                ObligationType.objects.filter(name=name).exists(), msg=name)

    def test_apd_teka_name_dedupe_keeps_existing_row(self):
        """Η «ΑΠΔ ΤΕΚΑ» υπάρχει στο βασικό σετ — μία εγγραφή, με το
        αρχικό code/profile, ΟΧΙ το catalog code."""
        run_setup_obligations()
        rows = ObligationType.objects.filter(name='ΑΠΔ ΤΕΚΑ')
        self.assertEqual(rows.count(), 1)
        row = rows.get()
        self.assertEqual(row.code, 'APD_TEKA')
        self.assertEqual(row.frequency, 'monthly')
        self.assertFalse(
            ObligationType.objects.filter(code='APD_TEKA_CATALOG').exists())

    def test_second_run_changes_nothing(self):
        run_setup_obligations()
        first = dict(ObligationType.objects.values_list('name', 'code'))
        run_setup_obligations()
        second = dict(ObligationType.objects.values_list('name', 'code'))
        self.assertEqual(first, second)
        self.assertEqual(ObligationType.objects.count(), EXPECTED_TYPE_COUNT)

    def test_user_modified_row_preserved(self):
        """Τύπος με ίδιο όνομα που ρύθμισε ήδη ο χρήστης δεν αλλοιώνεται."""
        ObligationType.objects.create(
            name='Έντυπο Ε1', code='CUSTOM_E1',
            frequency='annual', deadline_type='specific_day',
            deadline_day=31, applicable_months='7', priority=5)
        run_setup_obligations()
        row = ObligationType.objects.get(name='Έντυπο Ε1')
        self.assertEqual(row.code, 'CUSTOM_E1')
        self.assertEqual(row.frequency, 'annual')
        self.assertEqual(row.deadline_day, 31)
        self.assertEqual(row.priority, 5)
        self.assertEqual(ObligationType.objects.count(), EXPECTED_TYPE_COUNT)

    def test_catalog_types_have_no_invented_schedule_or_profiles(self):
        """Χωρίς περιοδικότητα/προθεσμία/profiles/exclusion — η ρύθμιση
        ανήκει στον λογιστή (skill obligation-engine)."""
        from accounting.management.commands.setup_obligations import (
            DEFAULT_CATALOG,
        )
        run_setup_obligations()
        base_names = {'ΑΠΔ ΤΕΚΑ'}
        for name, _ in DEFAULT_CATALOG:
            if name in base_names:
                continue
            row = ObligationType.objects.get(name=name)
            self.assertEqual(row.frequency, '', msg=name)
            self.assertEqual(row.deadline_type, '', msg=name)
            self.assertIsNone(row.exclusion_group, msg=name)
            self.assertEqual(row.profiles.count(), 0, msg=name)
            self.assertTrue(row.is_active, msg=name)

    def test_unconfigured_catalog_type_never_autogenerates(self):
        """get_deadline_for_month => None: η γεννήτρια τον παραλείπει —
        καμία αυτόματη υποχρέωση χωρίς ρύθμιση."""
        run_setup_obligations()
        row = ObligationType.objects.get(name='Έντυπο Ε1')
        self.assertIsNone(row.get_deadline_for_month(2026, 8))

    def test_catalog_available_for_client_selection(self):
        """Οι νέοι τύποι εμφανίζονται στο queryset επιλογής και μπορούν
        να επιλεγούν χειροκίνητα σε πελάτη (ClientObligation M2M)."""
        from accounting.models import ClientObligation, ClientProfile
        run_setup_obligations()
        # Το queryset του selection endpoint (api_obligation_profiles):
        selectable = set(
            ObligationType.objects.filter(is_active=True)
            .values_list('name', flat=True))
        self.assertIn('Έντυπο Ε1', selectable)
        self.assertIn('Ψηφιακό Τέλος Συναλλαγής', selectable)

        client = ClientProfile.objects.create(
            afm='090000045', onoma='ΔΟΚΙΜΗ ΕΠΕ')
        settings_row, _ = ClientObligation.objects.get_or_create(
            client=client)
        chosen = ObligationType.objects.get(name='Έντυπο Ε1')
        settings_row.obligation_types.add(chosen)
        self.assertIn(chosen, settings_row.get_all_obligation_types())
