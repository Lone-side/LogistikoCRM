# -*- coding: utf-8 -*-
"""
seed_demo — Δημιουργία επαναλήψιμων demo δεδομένων για παρουσιάσεις/έλεγχο.

Φτιάχνει:
  - έναν demo πελάτη με λογαριασμό portal (username = ΑΦΜ, γνωστός κωδικός)
  - υποχρεώσεις με ανάμεικτη κατάσταση (pending + completed)
  - VAT records ΔΥΟ ετών (εκροές + εισροές) ώστε ο year-selector να έχει δεδομένα
  - υπολογισμένα VATPeriodResult

Idempotent: η επανεκτέλεση δεν δημιουργεί διπλότυπα.

Usage:
    python manage.py seed_demo            # δημιουργία/ενημέρωση
    python manage.py seed_demo --reset    # καθάρισμα demo δεδομένων & εκ νέου
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounting.models import ClientProfile, MonthlyObligation, ObligationType
from mydata.models import VATRecord, VATPeriodResult

DEMO_AFM = '099000117'          # έγκυρο checksum
DEMO_PASSWORD = 'Demo2025!'
DEMO_NAME = 'DOKIMI PORTAL AE'


class Command(BaseCommand):
    help = 'Δημιουργία επαναλήψιμων demo δεδομένων (πελάτης portal + VAT + υποχρεώσεις)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Διαγραφή των demo δεδομένων πριν την εκ νέου δημιουργία',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self._reset()

        client = self._ensure_client()
        self._ensure_portal_user(client)
        self._ensure_obligations(client)
        self._ensure_vat(client)

        # ASCII markers μόνο: το Windows console (cp1253) σκάει σε emoji/checkmarks.
        self.stdout.write(self.style.SUCCESS('\n[OK] Demo δεδομένα έτοιμα'))
        self.stdout.write('=' * 50)
        self.stdout.write(f'  Πελάτης : {DEMO_NAME}')
        self.stdout.write(f'  ΑΦΜ     : {DEMO_AFM}')
        self.stdout.write(f'  Username: {DEMO_AFM}')
        self.stdout.write(f'  Password: {DEMO_PASSWORD}')
        self.stdout.write('=' * 50)
        self.stdout.write('  Portal: /login -> tab «ΦΠΑ» / «Υποχρεώσεις»')

    # ------------------------------------------------------------------ #
    def _reset(self):
        client = ClientProfile.objects.filter(afm=DEMO_AFM).first()
        if not client:
            return
        VATRecord.objects.filter(client=client).delete()
        VATPeriodResult.objects.filter(client=client).delete()
        MonthlyObligation.objects.filter(client=client).delete()
        user = client.user
        # Ξεκούμπωμα πριν τη διαγραφή για να μη μείνει ορφανός FK.
        client.user = None
        client.save(update_fields=['user'])
        if user:
            user.delete()
        client.delete()
        self.stdout.write(self.style.WARNING('  (reset: διαγράφηκαν παλιά demo δεδομένα)'))

    def _ensure_client(self) -> ClientProfile:
        client, created = ClientProfile.objects.get_or_create(
            afm=DEMO_AFM,
            defaults={
                'eponimia': DEMO_NAME,
                'eidos_ipoxreou': 'company',
                'email': 'demo@portal.gr',
                'kinito_tilefono': '6900000000',
            },
        )
        self.stdout.write(
            ('  + ' if created else '  = ') + f'Πελάτης {DEMO_AFM}')
        return client

    def _ensure_portal_user(self, client: ClientProfile):
        # Reuse the model helper (handles group membership + staff-group removal).
        user = client.create_portal_user(password=DEMO_PASSWORD)
        # Σε επανεκτέλεση χωρίς reset, εξασφάλισε γνωστό κωδικό.
        if not user.check_password(DEMO_PASSWORD):
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=['password'])
        self.stdout.write('  = Λογαριασμός portal')

    def _ensure_obligations(self, client: ClientProfile):
        otype, _ = ObligationType.objects.get_or_create(
            code='VAT',
            defaults={
                'name': 'Φόρος Προστιθέμενης Αξίας',
                'frequency': 'monthly',
                'deadline_type': 'last_day',
            },
        )
        today = timezone.now().date()
        # Μία ολοκληρωμένη (περασμένος μήνας) + δύο εκκρεμείς (μελλοντικοί).
        plan = [
            (today.replace(day=1) - timedelta(days=20), 'completed'),
            (today + timedelta(days=15), 'pending'),
            (today + timedelta(days=45), 'pending'),
        ]
        for d, status_val in plan:
            MonthlyObligation.objects.get_or_create(
                client=client,
                obligation_type=otype,
                year=d.year,
                month=d.month,
                defaults={
                    'deadline': d,
                    'status': status_val,
                    'completed_date': d if status_val == 'completed' else None,
                },
            )
        self.stdout.write('  = Υποχρεώσεις (ανάμεικτη κατάσταση)')

    def _ensure_vat(self, client: ClientProfile):
        this_year = timezone.now().year
        prev_year = this_year - 1
        # (mark, year, month, rec_type, net, vat)
        rows = [
            (400100001, this_year, 5, 1, '1000.00', '240.00'),  # εκροή
            (400100002, this_year, 5, 1, '500.00', '120.00'),   # εκροή
            (400100003, this_year, 5, 2, '300.00', '72.00'),    # εισροή
            (400100004, prev_year, 11, 1, '800.00', '192.00'),  # εκροή (περσι)
            (400100005, prev_year, 11, 2, '200.00', '48.00'),   # εισροή (περσι)
        ]
        for mark, yr, mo, rec_type, net, vat in rows:
            VATRecord.objects.get_or_create(
                client=client,
                mark=mark,
                expense_category='361' if rec_type == 2 else '',
                income_code='',
                defaults={
                    'issue_date': date(yr, mo, 10),
                    'rec_type': rec_type,
                    'inv_type': '1.1' if rec_type == 1 else 'ΕΙΣΡΟΕΣ_361',
                    'vat_category': 1,
                    'net_value': Decimal(net),
                    'vat_amount': Decimal(vat),
                    'is_cancelled': False,
                },
            )

        # Period results για κάθε έτος (recalculate από τα records).
        for yr, mo in [(this_year, 5), (prev_year, 11)]:
            period, _ = VATPeriodResult.objects.get_or_create(
                client=client, period_type='monthly', year=yr, period=mo,
            )
            if not period.is_locked:
                period.calculate_from_records(save=True)
        self.stdout.write(f'  = VAT records ({prev_year} + {this_year}) + περίοδοι')
