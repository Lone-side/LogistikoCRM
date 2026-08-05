# mydata/management/commands/rotate_encryption_key.py
"""
Rotation του κλειδιού κρυπτογράφησης δεδομένων.

Επανακρυπτογραφεί όλα τα encrypted πεδία με το DATA_ENCRYPTION_KEY_CURRENT:
- MyDataCredentials (user_id, subscription_key)
- EmailSettings (SMTP password)
- ClientCredential (secrets πελατών)

Χρήση:
    python manage.py rotate_encryption_key --generate   # παράγει νέο κλειδί
    python manage.py rotate_encryption_key --dry-run    # δείχνει τι θα αλλάξει
    python manage.py rotate_encryption_key              # εκτελεί re-encryption
"""

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from mydata.encryption import encrypt_value, safe_decrypt


class Command(BaseCommand):
    help = "Επανακρυπτογράφηση όλων των encrypted πεδίων με το τρέχον κλειδί"

    def add_arguments(self, parser):
        parser.add_argument(
            '--generate', action='store_true',
            help='Παράγει νέο Fernet key και τερματίζει',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Δείχνει πόσες εγγραφές θα επανακρυπτογραφηθούν χωρίς αλλαγές',
        )
        parser.add_argument(
            '--skip-invalid', action='store_true',
            help='Παράλειψη εγγραφών που δεν αποκρυπτογραφούνται (default: '
                 'αποτυχία + rollback ολόκληρου του rotation)',
        )

    def handle(self, *args, **options):
        if options['generate']:
            self.stdout.write(Fernet.generate_key().decode('utf-8'))
            self.stdout.write(self.style.SUCCESS(
                "Όρισε την τιμή ως DATA_ENCRYPTION_KEY_CURRENT στο .env "
                "(και το παλιό CURRENT ως DATA_ENCRYPTION_KEY_PREVIOUS αν υπήρχε)."
            ))
            return

        if not getattr(settings, 'DATA_ENCRYPTION_KEY_CURRENT', ''):
            raise CommandError(
                "Δεν έχει οριστεί DATA_ENCRYPTION_KEY_CURRENT. "
                "Τρέξε πρώτα με --generate και όρισέ το στο .env."
            )

        dry_run = options['dry_run']
        self.skip_invalid = options['skip_invalid']
        self.skipped = []
        total = 0

        with transaction.atomic():
            total += self._rotate_mydata(dry_run)
            total += self._rotate_smtp(dry_run)
            total += self._rotate_client_credentials(dry_run)
            if dry_run:
                transaction.set_rollback(True)

        verb = "θα επανακρυπτογραφούνταν" if dry_run else "επανακρυπτογραφήθηκαν"
        self.stdout.write(self.style.SUCCESS(f"Σύνολο: {total} πεδία {verb}."))
        if self.skipped:
            self.stderr.write(self.style.WARNING(
                f"ΠΡΟΣΟΧΗ: παραλείφθηκαν {len(self.skipped)} πεδία "
                f"(--skip-invalid): {', '.join(self.skipped)}"
            ))

    def _reencrypt(self, obj, field_names, dry_run):
        """Επανακρυπτογραφεί τα δοσμένα πεδία ενός object. Επιστρέφει πλήθος.

        Fail-closed: αδυναμία αποκρυπτογράφησης → CommandError (rollback του
        transaction, exit code != 0), εκτός αν δόθηκε --skip-invalid.
        """
        changed = []
        for field in field_names:
            encrypted = getattr(obj, field, '')
            if not encrypted:
                continue
            plain = safe_decrypt(encrypted)
            if plain is None:
                label = f"{obj.__class__.__name__}#{obj.pk}.{field}"
                if not self.skip_invalid:
                    raise CommandError(
                        f"ΑΔΥΝΑΤΗ αποκρυπτογράφηση: {label}. Το rotation "
                        f"ακυρώθηκε (rollback) — κανένα κλειδί δεν πρέπει να "
                        f"αφαιρεθεί. Έλεγξε τα DATA_ENCRYPTION_KEY_* ή τρέξε "
                        f"με --skip-invalid για ρητή παράλειψη."
                    )
                self.skipped.append(label)
                self.stderr.write(self.style.WARNING(
                    f"  ΑΔΥΝΑΤΗ αποκρυπτογράφηση: {label} — παραλείπεται."
                ))
                continue
            setattr(obj, field, encrypt_value(plain))
            changed.append(field)
        if changed and not dry_run:
            obj.save(update_fields=changed)
        return len(changed)

    def _rotate_mydata(self, dry_run):
        from mydata.models import MyDataCredentials
        count = 0
        for cred in MyDataCredentials.objects.all():
            count += self._reencrypt(
                cred, ['_encrypted_user_id', '_encrypted_subscription_key'], dry_run
            )
        self.stdout.write(f"MyDataCredentials: {count} πεδία")
        return count

    def _rotate_smtp(self, dry_run):
        from accounting.models import EmailSettings
        count = 0
        for obj in EmailSettings.objects.all():
            count += self._reencrypt(obj, ['_encrypted_smtp_password'], dry_run)
        self.stdout.write(f"EmailSettings (SMTP): {count} πεδία")
        return count

    def _rotate_client_credentials(self, dry_run):
        from accounting.models import ClientCredential
        count = 0
        for obj in ClientCredential.objects.all():
            count += self._reencrypt(obj, ['_secret_encrypted'], dry_run)
        self.stdout.write(f"ClientCredential: {count} πεδία")
        return count
