# -*- coding: utf-8 -*-
"""
Backfill εξαγωγής κειμένου για υπάρχοντα έγγραφα πελατών.

Χρήση:
    python manage.py extract_document_text --pending-only
    python manage.py extract_document_text --limit 100
    python manage.py extract_document_text --retry-failed
"""
from django.core.management.base import BaseCommand

from accounting.models import ClientDocument
from accounting.services import text_extraction


class Command(BaseCommand):
    help = 'Εξαγωγή κειμένου (αναζήτηση/ΑΦΜ) για υπάρχοντα έγγραφα πελατών'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Μέγιστος αριθμός εγγράφων')
        parser.add_argument('--pending-only', action='store_true',
                            help='Μόνο όσα δεν έχουν επεξεργαστεί (default: όλα)')
        parser.add_argument('--retry-failed', action='store_true',
                            help='Επανεπεξεργασία και των αποτυχημένων')

    def handle(self, *args, **options):
        qs = ClientDocument.objects.order_by('id')
        if options['pending_only']:
            statuses = ['pending']
            if options['retry_failed']:
                statuses.append('failed')
            qs = qs.filter(ocr_status__in=statuses)
        if options['limit']:
            qs = qs[:options['limit']]

        done = failed = skipped = 0
        for doc in qs.iterator():
            status = text_extraction.process_document(doc)
            if status == 'done':
                done += 1
            elif status == 'failed':
                failed += 1
                self.stderr.write(f"❌ #{doc.id} {doc.filename}")
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Ολοκληρώθηκε: {done} με κείμενο, {skipped} παραλείφθηκαν, {failed} απέτυχαν"
        ))
