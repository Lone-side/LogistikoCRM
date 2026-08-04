# -*- coding: utf-8 -*-
"""
Έλεγχος ιστορικών ασυνεπειών στα ClientDocument rows.

Το model save guard δεν καλύπτει παλιά rows, QuerySet.update, bulk
operations ή direct SQL — αυτό το command σαρώνει τη βάση και αναφέρει:

1. document.client_id != obligation.client_id
2. document.client_id != previous_version.client_id
3. Σπασμένες αλυσίδες previous_version (self-reference)
4. Περισσότερα από ένα current documents στην ίδια version chain
   (previous_version με is_current=True ενώ υπάρχει νεότερη current έκδοση)

Report-only by design: ΔΕΝ γίνεται αυτόματη επανάθεση ξένων documents σε
άλλον πελάτη — η διόρθωση είναι χειροκίνητη, βάσει των πραγματικών
παραστατικών (fail closed). Στα logs μπαίνουν ΜΟΝΟ internal IDs — ποτέ
πλήρες ΑΦΜ ή ονόματα αρχείων.

Χρήση σε deployment checks: --fail-on-findings → exit code != 0 (CommandError).
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from accounting.models import ClientDocument


class Command(BaseCommand):
    help = ("Αναφέρει ClientDocument rows που παραβιάζουν τα cross-client "
            "invariants (report-only, χειροκίνητη διόρθωση)")

    def add_arguments(self, parser):
        parser.add_argument(
            '--fail-on-findings', action='store_true',
            help='Exit με σφάλμα αν βρεθούν ασυνέπειες (για CI/deploy checks)',
        )

    def handle(self, *args, **options):
        findings = []

        # 1. Cross-client obligation
        for doc in (ClientDocument.objects
                    .filter(obligation__isnull=False)
                    .exclude(obligation__client_id=F('client_id'))
                    .values('id', 'client_id', 'obligation_id',
                            'obligation__client_id')):
            findings.append(
                f"cross-client-obligation: document id={doc['id']} "
                f"client id={doc['client_id']} ↔ obligation "
                f"id={doc['obligation_id']} (client id="
                f"{doc['obligation__client_id']})"
            )

        # 2. Cross-client previous_version
        for doc in (ClientDocument.objects
                    .filter(previous_version__isnull=False)
                    .exclude(previous_version__client_id=F('client_id'))
                    .values('id', 'client_id', 'previous_version_id',
                            'previous_version__client_id')):
            findings.append(
                f"cross-client-previous-version: document id={doc['id']} "
                f"client id={doc['client_id']} ↔ previous id="
                f"{doc['previous_version_id']} (client id="
                f"{doc['previous_version__client_id']})"
            )

        # 3. Self-referencing chain
        for doc in (ClientDocument.objects
                    .filter(previous_version_id=F('id'))
                    .values('id')):
            findings.append(
                f"broken-chain-self-reference: document id={doc['id']}")

        # 4. Δύο (ή περισσότερα) current στην ίδια αλυσίδα: previous_version
        # που παραμένει is_current=True ενώ έχει νεότερη έκδοση
        for doc in (ClientDocument.objects
                    .filter(previous_version__isnull=False,
                            previous_version__is_current=True)
                    .values('id', 'previous_version_id')):
            findings.append(
                f"multiple-current-in-chain: document id={doc['id']} και "
                f"previous id={doc['previous_version_id']}"
            )

        if not findings:
            self.stdout.write(self.style.SUCCESS(
                'Κανένα invariant finding — όλα τα ClientDocument συνεπή.'))
            return

        self.stdout.write(self.style.WARNING(
            f'Βρέθηκαν {len(findings)} ασυνέπειες (χειροκίνητη διόρθωση):'))
        for line in findings:
            self.stdout.write(f'  - {line}')

        if options['fail_on_findings']:
            raise CommandError(
                f'{len(findings)} ClientDocument invariant findings')
