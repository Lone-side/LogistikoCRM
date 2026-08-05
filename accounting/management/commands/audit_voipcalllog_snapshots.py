# -*- coding: utf-8 -*-
"""
Post-migration / περιοδικός audit των VoIPCallLog snapshots (fail-closed).

Επαληθεύει ότι τα snapshot πεδία (client/call_reference/phone_number)
είναι επαρκή ώστε ένα log να διατηρεί attribution ΚΑΙ μετά τη διαγραφή
της κλήσης του (SET_NULL). Αναφέρει ΜΟΝΟ counts + internal IDs — ποτέ
πλήρη τηλέφωνα, ΑΦΜ ή άλλα PII.

Findings (fail-closed με --fail-on-findings):
  1. missing-call-reference: log με κλήση αλλά κενό call_reference
     (θα έμενε χωρίς αναγνωριστικό αν διαγραφεί η κλήση).
  2. orphan-without-attribution: log χωρίς κλήση ΚΑΙ χωρίς κανένα snapshot
     (client/call_reference/phone_number όλα κενά) — μη αποδοτέο.
  3. client-mismatch: log με ενεργή κλήση όπου call.client_id διαφέρει
     από το snapshot client_id (ασυνέπεια — η πολιτική απαιτεί ταύτιση
     όσο υπάρχει η κλήση).
"""

from django.core.management.base import BaseCommand
from django.db.models import F


class Command(BaseCommand):
    help = ("Fail-closed audit των VoIPCallLog snapshots (attribution "
            "μετά τη διαγραφή κλήσης). Μόνο internal IDs, χωρίς PII.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--fail-on-findings', action='store_true',
            help='Exit με σφάλμα αν βρεθούν ασυνέπειες (για CI/deploy gate)',
        )
        parser.add_argument(
            '--limit', type=int, default=50,
            help='Μέγιστος αριθμός IDs ανά κατηγορία στο output',
        )

    def handle(self, *args, **options):
        from accounting.models import VoIPCallLog

        limit = options['limit']
        findings = []

        # 1. log με κλήση αλλά κενό call_reference
        missing = list(
            VoIPCallLog.objects.filter(call__isnull=False, call_reference='')
            .values_list('id', flat=True)[:limit + 1])
        if missing:
            findings.append(('missing-call-reference', missing))

        # 2. orphan χωρίς κανένα attribution
        orphan = list(
            VoIPCallLog.objects.filter(
                call__isnull=True, call_reference='',
                phone_number='', client__isnull=True)
            .values_list('id', flat=True)[:limit + 1])
        if orphan:
            findings.append(('orphan-without-attribution', orphan))

        # 3. client mismatch όσο υπάρχει η κλήση
        mismatch = list(
            VoIPCallLog.objects.filter(call__isnull=False)
            .exclude(client_id=F('call__client_id'))
            .values_list('id', flat=True)[:limit + 1])
        if mismatch:
            findings.append(('client-mismatch', mismatch))

        if not findings:
            self.stdout.write(self.style.SUCCESS(
                'VoIPCallLog snapshots: OK (καμία ασυνέπεια).'))
            return

        for kind, ids in findings:
            shown = ids[:limit]
            more = '…(+)' if len(ids) > limit else ''
            self.stdout.write(self.style.WARNING(
                f'{kind}: {len(shown)}{more} VoIPCallLog ids={shown}{more}'))

        if options['fail_on_findings']:
            from django.core.management.base import CommandError
            raise CommandError(
                'VoIPCallLog snapshot audit απέτυχε — βλ. findings παραπάνω.')
