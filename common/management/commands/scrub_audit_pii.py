# common/management/commands/scrub_audit_pii.py
"""
Καθαρισμός ιστορικών AuditLog εγγραφών που περιέχουν πλήρεις τιμές PII
(ΑΦΜ, ΑΜΚΑ, IBAN, ταυτότητες, τηλέφωνα, email, διευθύνσεις).

Παλαιότερες εκδόσεις έγραφαν πλήρεις τιμές στο `changes` (old/new) και σε
descriptions. Η εντολή τις μετατρέπει σε masked μορφή (••••1234) ή σε
{"changed": true} για διευθύνσεις — ΔΕΝ διαγράφει audit events.

Χρήση:
    python manage.py scrub_audit_pii              # dry-run (προεπιλογή, δεν γράφει)
    python manage.py scrub_audit_pii --apply      # πραγματική εγγραφή

⚠️ Πριν το --apply σε παραγωγή: πάρε backup βάσης
   (python manage.py backup_database).
"""

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from accounting.services.access import mask_pii_value
from common.models import AuditLog

# Κλειδιά του `changes` που θεωρούνται PII (ό,τι κατέγραφε ιστορικά το API)
PII_CHANGE_KEYS = {
    'afm', 'amka', 'arithmos_taftotitas', 'prosopikos_arithmos', 'iban',
    'am_ika', 'arithmos_gemi', 'afm_sizigou', 'afm_foreas',
    'email', 'kinito_tilefono', 'tilefono_oikias_1', 'tilefono_oikias_2',
    'tilefono_epixeirisis_1', 'tilefono_epixeirisis_2',
}
# Διευθύνσεις: ούτε masked τιμή — μόνο ένδειξη αλλαγής
ADDRESS_CHANGE_KEYS = {
    'diefthinsi_katoikias', 'diefthinsi_epixeirisis',
    'poli_katoikias', 'poli_epixeirisis',
}

# Regex σε ελεύθερο κείμενο (description/object_repr), με σειρά από το πιο
# συγκεκριμένο στο πιο γενικό ώστε π.χ. το IBAN να μην «φαγωθεί» ως ψηφία.
TEXT_PATTERNS = [
    # Email
    re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
    # Ελληνικό IBAN: 27 χαρακτήρες συνολικά (GR + 2 check digits + 23
    # αλφαριθμητικοί), προαιρετικά με κενά ανά τετράδες, και lowercase
    re.compile(r'\bGR\d{2}(?:\s?[A-Z0-9]){23}\b', re.IGNORECASE),
    # ΑΜΚΑ (11 ψηφία)
    re.compile(r'\b\d{11}\b'),
    # Τηλέφωνα (10 ψηφία)
    re.compile(r'\b\d{10}\b'),
    # ΑΦΜ (9 ψηφία)
    re.compile(r'\b\d{9}\b'),
]


def _mask_match(match: re.Match) -> str:
    return mask_pii_value(match.group(0))


def scrub_text(text):
    """Μασκάρει PII μοτίβα σε ελεύθερο κείμενο. Επιστρέφει (νέο, άλλαξε;)."""
    if not text:
        return text, False
    new_text = text
    for pattern in TEXT_PATTERNS:
        new_text = pattern.sub(_mask_match, new_text)
    return new_text, new_text != text


def _is_masked(value) -> bool:
    return isinstance(value, str) and '•' in value


def scrub_changes(changes):
    """Μασκάρει PII τιμές στο changes JSON. Επιστρέφει (νέο dict, άλλαξε;)."""
    if not isinstance(changes, dict):
        return changes, False
    changed = False
    result = {}
    for key, value in changes.items():
        if key in ADDRESS_CHANGE_KEYS:
            if value != {'changed': True}:
                result[key] = {'changed': True}
                changed = True
            else:
                result[key] = value
        elif key in PII_CHANGE_KEYS:
            if isinstance(value, dict):
                new_value = dict(value)
                for part in ('old', 'new', 'value'):
                    inner = new_value.get(part)
                    if isinstance(inner, str) and inner and not _is_masked(inner):
                        new_value[part] = mask_pii_value(inner)
                        changed = True
                result[key] = new_value
            elif isinstance(value, str) and value and not _is_masked(value):
                result[key] = mask_pii_value(value)
                changed = True
            else:
                result[key] = value
        else:
            result[key] = value
    return result, changed


class Command(BaseCommand):
    help = (
        'Μασκάρει ιστορικές PII τιμές σε AuditLog εγγραφές. '
        'Προεπιλογή: dry-run — χρειάζεται --apply για εγγραφή. '
        'Πάρε backup βάσης πριν το --apply.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Πραγματική εγγραφή (χωρίς αυτό: dry-run, καμία αλλαγή)',
        )
        parser.add_argument(
            '--batch-size', type=int, default=500,
            help='Μέγεθος batch (default 500)',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        batch_size = max(1, options['batch_size'])

        scanned = changed_count = 0
        last_pk = 0

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN: καμία εγγραφή. Τρέξε με --apply για πραγματικό καθαρισμό '
                '(αφού πάρεις backup βάσης).'
            ))

        while True:
            batch = list(
                AuditLog.objects.filter(pk__gt=last_pk)
                .order_by('pk')[:batch_size]
            )
            if not batch:
                break
            last_pk = batch[-1].pk

            dirty = []
            for row in batch:
                scanned += 1
                row_changed = False

                new_changes, c1 = scrub_changes(row.changes)
                if c1:
                    row.changes = new_changes
                    row_changed = True

                new_desc, c2 = scrub_text(row.description)
                if c2:
                    row.description = new_desc
                    row_changed = True

                new_repr, c3 = scrub_text(row.object_repr)
                if c3:
                    row.object_repr = new_repr
                    row_changed = True

                if row_changed:
                    changed_count += 1
                    dirty.append(row)

            if dirty and apply_changes:
                with transaction.atomic():
                    AuditLog.objects.bulk_update(
                        dirty, ['changes', 'description', 'object_repr']
                    )

            self.stdout.write(
                f'  batch έως pk={last_pk}: scanned={scanned}, '
                f'με αλλαγές={changed_count}'
            )

        skipped = scanned - changed_count
        mode = 'ΕΦΑΡΜΟΣΤΗΚΑΝ' if apply_changes else 'ΘΑ ΑΛΛΑΖΑΝ (dry-run)'
        self.stdout.write(self.style.SUCCESS(
            f'Ολοκληρώθηκε: scanned={scanned}, {mode}={changed_count}, '
            f'ήδη καθαρές={skipped}'
        ))
