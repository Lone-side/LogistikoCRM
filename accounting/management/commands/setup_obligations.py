from django.core.management.base import BaseCommand
from accounting.models import ObligationGroup, ObligationProfile, ObligationType

# ---------------------------------------------------------------------------
# Default catalog: ονομασίες διαθέσιμες για χειροκίνητη επιλογή ανά πελάτη.
#
# ΣΚΟΠΙΜΑ ΧΩΡΙΣ frequency/deadline_type/profiles: η περιοδικότητα και η
# προθεσμία ρυθμίζονται από τον λογιστή όταν ενεργοποιηθεί ο τύπος (βλ.
# skill obligation-engine — καμία επινοημένη προθεσμία). Μέχρι τότε το
# generate_monthly_obligations ΔΕΝ δημιουργεί υποχρεώσεις για αυτούς
# (get_deadline_for_month => None => καταγράφεται 'No deadline' και
# παραλείπεται) — fail-safe, όχι σιωπηλή αυτόματη γέννηση.
#
# Το deduplication γίνεται ΜΕ ΒΑΣΗ ΤΟ ΟΝΟΜΑ (unique): τύπος που υπάρχει
# ήδη (π.χ. ΑΠΔ ΤΕΚΑ από το βασικό σετ, ή τροποποιημένος από χρήστη)
# ΔΕΝ ξαναδημιουργείται και δεν αλλοιώνεται.
# ---------------------------------------------------------------------------
DEFAULT_CATALOG = [
    # (name, code) — codes σταθερά ASCII slugs, priority = 100 + index
    ('ΑΠΔ (Κοινών)', 'APD_KOINON'),
    ('Intrastat Αποστολές', 'INTRASTAT_DISPATCH'),
    ('Intrastat Αφίξεις', 'INTRASTAT_ARRIVAL'),
    ('VIES Αποστολές', 'VIES_DISPATCH'),
    ('VIES Αφίξεις', 'VIES_ARRIVAL'),
    ('Απόδοση Τέλους Πλαστικής Σακούλας', 'PLASTIC_BAG_FEE_RETURN'),
    ('Απόδοση Τέλους Διαμονής', 'STAY_FEE_RETURN'),
    ('Παρακράτηση φόρου για μερίσματα', 'WHT_DIVIDENDS'),
    ('Παρακράτηση φόρου για Τόκους', 'WHT_INTEREST'),
    ('Παρακράτηση φόρου για Δικαιώματα', 'WHT_ROYALTIES'),
    ('Παρακρατούμενοι φόροι (Επαγγ. Δραστηριότητα)', 'WHT_BUSINESS'),
    ('Παρακρατούμενοι φόροι (Μισθωτών)', 'WHT_PAYROLL'),
    ('Περιοδική Φ.Π.Α. (Μήνα)', 'VAT_PERIODIC_MONTH'),
    ('Περιοδική Φ.Π.Α. (Τριμήνου)', 'VAT_PERIODIC_QUARTER'),
    ('Φόρος 3% Εργολάβων, Ενοικιαστών Προσόδων', 'TAX3_CONTRACTORS'),
    ('Έντυπο Ε1', 'FORM_E1'),
    ('Έντυπο Ε2', 'FORM_E2'),
    ('Έντυπο Ε3', 'FORM_E3'),
    ('Έντυπο Ε2 (Ν.Π.)', 'FORM_E2_NP'),
    ('Έντυπο Ε3 (Ν.Π.)', 'FORM_E3_NP'),
    ('Φ.Ε.Ν.Π.', 'FENP'),
    ('ΑΠΔ (Οικοδομοτεχνικών)', 'APD_CONSTRUCTION'),
    ('ΑΠΔ ΤΕΚΑ', 'APD_TEKA_CATALOG'),  # υπάρχει ήδη — name-dedupe skip
    ('ΑΠΔ ΤΕΚΑ (Οικοδομοτεχνικών)', 'APD_TEKA_CONSTRUCTION'),
    ('Απογραφική δήλωση χρησιμοποιούμενων αδειών εργαζομένων',
     'LEAVE_USAGE_DECL'),
    ('Απολογιστική δήλωση αλλαγών ωραρίου και οργάνωσης χρόνου εργασίας',
     'WORKTIME_CHANGE_DECL'),
    ('Απολογιστική δήλωση νόμιμης υπερωριακής απασχόλησης',
     'OVERTIME_DECL'),
    ('Δήλωση απόδοσης τέλους ανακύκλωσης', 'RECYCLING_FEE_DECL'),
    ('Δήλωση απόδοσης Τέλους Ανθεκτικότητας στην Κλιματική Κρίση',
     'CLIMATE_RESILIENCE_FEE'),
    ('Δήλωση Βραχυχρόνιων Μισθώσεων', 'SHORT_TERM_RENTALS'),
    ('Δήλωση Έναρξης Ασφάλισης Παροχής Υπηρεσιών σε e-ΕΦΚΑ (μπλοκάκια)',
     'EFKA_FREELANCE_START'),
    ('Δήλωση Ενδοκοινοτικής Απόκτησης Μεταφορικού Μέσου',
     'INTRA_EU_VEHICLE_ACQ'),
    ('Δήλωση Μέσων Πληρωμών (POS) για Χρήστες (Επιχείρησης)',
     'POS_MEANS_DECL'),
    ('Δήλωση Μίσθωσης Ακινήτων', 'PROPERTY_LEASE_DECL'),
    ('Δικαίωμα υδροληψίας', 'WATER_RIGHTS'),
    ('Ειδικός Φόρος Πολυτελείας', 'LUXURY_TAX'),
    ('Ειδικός Φόρος Τηλεοπτικών Διαφημίσεων', 'TV_AD_TAX'),
    ('Εισφορά 2% Διαδικτύου', 'INTERNET_FEE_2PCT'),
    ('Κατ’ αποκοπή καταβολή φόρου', 'LUMP_SUM_TAX'),
    ('Καταβολή Ασφαλιστικών Εισφορών', 'SOCIAL_CONTRIB_PAYMENT'),
    ('Κατάσταση Συμφωνητικών', 'CONTRACTS_STATEMENT'),
    ('Παρακρατούμενοι και Προκαταβλητέοι Φόροι Δικηγόρων',
     'LAWYERS_WHT_PREPAID'),
    ('Παρακρατούμενοι Φόροι (Φορείς Γεν. Κυβέρνησης)', 'WHT_GOV_ENTITIES'),
    ('Περιβαλλοντική εισφορά για τα πλαστικά προϊόντα',
     'PLASTIC_PRODUCTS_ENV_FEE'),
    ('Τέλος διαφήμισης', 'AD_FEE'),
    ('Τέλος Κινητής και Καρτοκινητής Τηλεφωνίας', 'MOBILE_TELEPHONY_FEE'),
    ('Τέλος Παρεπιδημούντων/Ακαθάριστων Εσόδων (Μήνας)',
     'VISITORS_GROSS_MONTH'),
    ('Τέλος Παρεπιδημούντων/Ακαθάριστων Εσόδων (Τρίμηνο)',
     'VISITORS_GROSS_QUARTER'),
    ('Τέλος Συνδρομητών Σταθερής Τηλεφωνίας', 'FIXED_TELEPHONY_FEE'),
    ('Φόρος 35% Τυχερών Παιγνίων μέσω διαδικτύου', 'GAMING_TAX_35'),
    ('Φόρος και Εισφορά Αλληλεγγύης πληρωμάτων Εμπορικού Ναυτικού',
     'SEAMEN_TAX_SOLIDARITY'),
    ('Ψηφιακό Τέλος Συναλλαγής', 'DIGITAL_TRANSACTION_FEE'),
]


class Command(BaseCommand):
    help = 'Αρχικοποίηση Υποχρεώσεων Λογιστικού'

    def handle(self, *args, **kwargs):
        self.stdout.write('Δημιουργία Ομάδων Υποχρεώσεων...')
        self.create_groups()

        self.stdout.write('Δημιουργία Profiles Υποχρεώσεων...')
        self.create_profiles()

        self.stdout.write('Δημιουργία Τύπων Υποχρεώσεων...')
        self.create_obligation_types()

        self.stdout.write('Δημιουργία Default Catalog...')
        self.create_default_catalog()

        self.stdout.write(self.style.SUCCESS('✅ Ολοκληρώθηκε!'))

    def create_default_catalog(self):
        """
        Ονομασίες διαθέσιμες για χειροκίνητη επιλογή — χωρίς κανόνα
        περιοδικότητας/προθεσμίας (βλ. σχόλιο στο DEFAULT_CATALOG).
        """
        created_count = existing_count = 0
        for index, (name, code) in enumerate(DEFAULT_CATALOG):
            obj, created = ObligationType.objects.get_or_create(
                name=name,
                defaults={
                    'code': code,
                    'frequency': '',
                    'deadline_type': '',
                    'priority': 100 + index,
                    'description': (
                        'Default catalog — ορίστε περιοδικότητα/προθεσμία '
                        'πριν την αυτόματη δημιουργία υποχρεώσεων.'
                    ),
                },
            )
            if created:
                created_count += 1
            else:
                existing_count += 1
        self.stdout.write(
            f'  ✓ Catalog: {created_count} νέοι, '
            f'{existing_count} υπήρχαν ήδη (ανέγγιχτοι)')

    def create_groups(self):
        """Δημιουργία ομάδων αλληλοαποκλεισμού"""
        ObligationGroup.objects.get_or_create(
            name='ΦΠΑ',
            defaults={'description': 'Μόνο μία επιλογή ΦΠΑ (Μηνιαίο ή Τρίμηνο)'}
        )
        self.stdout.write('  ✓ Ομάδα ΦΠΑ')

    def create_profiles(self):
        """Δημιουργία profiles υποχρεώσεων"""
        ObligationProfile.objects.get_or_create(
            name='Μισθοδοσία',
            defaults={'description': 'Υποχρεώσεις εργοδοτών με μισθωτούς'}
        )
        self.stdout.write('  ✓ Profile Μισθοδοσία')
        
        ObligationProfile.objects.get_or_create(
            name='Ενδοκοινοτικές',
            defaults={'description': 'Ενδοκοινοτικές συναλλαγές'}
        )
        self.stdout.write('  ✓ Profile Ενδοκοινοτικές')

    def create_obligation_types(self):
        """Δημιουργία όλων των τύπων υποχρεώσεων"""
        
        vat_group = ObligationGroup.objects.get(name='ΦΠΑ')
        misthodosía_profile = ObligationProfile.objects.get(name='Μισθοδοσία')
        endokoinotikes_profile = ObligationProfile.objects.get(name='Ενδοκοινοτικές')
        
        obligations = [
            # === ΟΜΑΔΑ ΦΠΑ (Αλληλοαποκλειόμενα) ===
            {
                'name': 'ΦΠΑ Μηνιαίο',
                'code': 'VAT_MONTHLY',
                'frequency': 'monthly',
                'deadline_type': 'last_day_prev',
                'exclusion_group': vat_group,
                'priority': 10,
                'description': 'Μηνιαία δήλωση ΦΠΑ - προθεσμία τελευταία προηγούμενου μήνα'
            },
            {
                'name': 'ΦΠΑ Τρίμηνο',
                'code': 'VAT_QUARTERLY',
                'frequency': 'quarterly',
                'deadline_type': 'last_day_next',
                'applicable_months': '4,7,10,1',
                'exclusion_group': vat_group,
                'priority': 11,
                'description': 'Τριμηνιαία δήλωση ΦΠΑ - προθεσμία τελευταία επόμενου μήνα'
            },
            
            # === ΕΙΔΙΚΕΣ ΕΠΙΒΑΡΥΝΣΕΙΣ (Ανεξάρτητες) ===
            {
                'name': 'Πλαστικές Σακούλες',
                'code': 'PLASTIC_BAGS',
                'frequency': 'follows_vat',
                'deadline_type': 'last_day',
                'priority': 20,
                'description': 'Ακολουθεί το ΦΠΑ του πελάτη'
            },
            {
                'name': 'Πλαστικά Προϊόντα',
                'code': 'PLASTIC_PRODUCTS',
                'frequency': 'follows_vat',
                'deadline_type': 'last_day',
                'priority': 21,
                'description': 'Ακολουθεί το ΦΠΑ του πελάτη'
            },
            {
                'name': '0.05%',
                'code': 'RATE_005',
                'frequency': 'follows_vat',
                'deadline_type': 'last_day',
                'priority': 22,
                'description': 'Ακολουθεί το ΦΠΑ του πελάτη'
            },
            
            # === ΠΑΡΑΚΡΑΤΟΥΜΕΝΟΙ ===
            {
                'name': 'Παρακρατούμενη 20%',
                'code': 'WITHHOLD_20',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'priority': 30,
                'description': 'Παρακρατούμενος φόρος 20%'
            },
            {
                'name': 'Παρακρατούμενη 3%',
                'code': 'WITHHOLD_3',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'priority': 31,
                'description': 'Παρακρατούμενος φόρος 3%'
            },
# === PROFILE ΕΝΔΟΚΟΙΝΟΤΙΚΕΣ ===
            {
                'name': 'Ενδοκοινοτικές',
                'code': 'INTRA_EU',
                'frequency': 'monthly',
                'deadline_type': 'specific_day',
                'deadline_day': 26,
                'profile': endokoinotikes_profile,
                'priority': 40,
                'description': 'Ενδοκοινοτικές συναλλαγές'
            },
            {
                'name': 'VIES',
                'code': 'VIES',
                'frequency': 'monthly',
                'deadline_type': 'specific_day',
                'deadline_day': 26,
                'profile': endokoinotikes_profile,
                'priority': 41,
                'description': 'VIES Declaration'
            },
            
            # === ΤΙΜΟΛΟΓΙΑ/ΣΥΜΦΩΝΗΤΙΚΑ ===
            {
                'name': 'Τιμολόγια',
                'code': 'INVOICES',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'priority': 50,
                'description': 'Έλεγχος τιμολογίων'
            },
            {
                'name': 'Συμφωνητικά',
                'code': 'CONTRACTS',
                'frequency': 'quarterly',
                'deadline_type': 'specific_day',
                'deadline_day': 20,
                'applicable_months': '3,6,9,12',
                'priority': 51,
                'description': 'Τριμηνιαία συμφωνητικά'
            },
            
            # === PROFILE ΜΙΣΘΟΔΟΣΙΑ ===
            {
                'name': 'ΑΠΔ ΕΦΚΑ',
                'code': 'APD_EFKA',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'profile': misthodosía_profile,
                'priority': 60,
                'description': 'Αναλυτική Περιοδική Δήλωση ΕΦΚΑ'
            },
            {
                'name': 'ΑΠΔ ΤΕΚΑ',
                'code': 'APD_TEKA',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'profile': misthodosía_profile,
                'priority': 61,
                'description': 'Αναλυτική Περιοδική Δήλωση ΤΕΚΑ'
            },
            {
                'name': 'ΑΠΟΔ Μισθοδοσίας',
                'code': 'APOD_PAYROLL',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'profile': misthodosía_profile,
                'priority': 62,
                'description': 'Αποδοχές Μισθοδοσίας'
            },
            {
                'name': 'Άδειες',
                'code': 'LEAVES',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'profile': misthodosía_profile,
                'priority': 63,
                'description': 'Καταχώρηση αδειών'
            },
{
                'name': 'ΟΑΕΔ Προγράμματα',
                'code': 'OAED_PROGRAMS',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'profile': misthodosía_profile,
                'priority': 64,
                'description': 'Επιδοτούμενα προγράμματα ΟΑΕΔ'
            },
            {
                'name': 'ΔΥΠΑ',
                'code': 'DYPA',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'priority': 64.5,
                'description': 'Δήλωση Υπαλλήλων Προγραμμάτων Απασχόλησης - Απαιτεί Μισθοδοσία'
            },
            {
                'name': 'Πίνακας Αδειών',
                'code': 'LEAVE_TABLE',
                'frequency': 'annual',
                'deadline_type': 'specific_day',
                'deadline_day': 31,
                'applicable_months': '1',
                'profile': misthodosía_profile,
                'priority': 65,
                'description': 'Ετήσιος πίνακας αδειών - 31 Ιανουαρίου'
            },
            
            # === ΑΛΛΕΣ ΥΠΟΧΡΕΩΣΕΙΣ ===
            {
                'name': 'ΕΦΚΑ Μη Μισθωτών',
                'code': 'EFKA_SELF_EMPLOYED',
                'frequency': 'monthly',
                'deadline_type': 'specific_day',
                'deadline_day': 21,
                'priority': 70,
                'description': 'Εισφορές ελεύθερων επαγγελματιών'
            },
            {
                'name': 'Ρύθμιση',
                'code': 'SETTLEMENT',
                'frequency': 'monthly',
                'deadline_type': 'specific_day',
                'deadline_day': 15,
                'priority': 71,
                'description': 'Έλεγχος & πληρωμή ρυθμίσεων'
            },
            {
                'name': 'Φόρος Διαμονής',
                'code': 'ACCOMMODATION_TAX',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'priority': 72,
                'description': 'Φόρος διαμονής ξενοδοχείων/Airbnb'
            },
            {
                'name': 'Παρεπιδημούντων',
                'code': 'VISITORS_TAX',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
                'priority': 73,
                'description': 'Φόρος παρεπιδημούντων'
            },
            {
                'name': 'Πόθεν Έσχες',
                'code': 'POTHEN_ESXES',
                'frequency': 'annual',
                'deadline_type': 'specific_day',
                'deadline_day': 30,
                'applicable_months': '6',
                'priority': 74,
                'description': 'Ετήσια δήλωση Πόθεν Έσχες - 30 Ιουνίου'
            },
        ]
        
        for obl_data in obligations:
            # Το ObligationType.profiles είναι ManyToMany — δεν μπορεί να
            # περάσει ως kwarg στο get_or_create (FieldError σε καθαρή
            # βάση). Αφαιρείται από τα defaults και συνδέεται μετά.
            profile = obl_data.pop('profile', None)
            obj, created = ObligationType.objects.get_or_create(
                code=obl_data['code'],
                defaults=obl_data
            )
            if profile is not None:
                # add(): idempotent — ισχύει και για προϋπάρχοντα rows
                # από παλιές μερικές εκτελέσεις χωρίς το link.
                obj.profiles.add(profile)
            if created:
                self.stdout.write(f'  ✓ {obj.name}')
            else:
                self.stdout.write(f'  → {obj.name} (υπήρχε ήδη)')