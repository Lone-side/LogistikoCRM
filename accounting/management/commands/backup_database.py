from django.core.management.base import BaseCommand, CommandError
import shutil
from datetime import datetime
from pathlib import Path
from django.conf import settings


class Command(BaseCommand):
    help = 'Backup της βάσης δεδομένων (SQLite αντίγραφο με timestamp + καθαρισμός παλιών)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir', type=str, default='',
            help='Φάκελος αποθήκευσης (default: BASE_DIR/backups)'
        )
        parser.add_argument(
            '--keep-days', type=int, default=0,
            help='Διαγραφή backups παλαιότερων από Χ ημέρες (default: κράτα τα 30 τελευταία)'
        )

    def handle(self, *args, **options):
        # Backup directory
        if options['output_dir']:
            backup_dir = Path(options['output_dir'])
        else:
            backup_dir = settings.BASE_DIR / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Database path
        db_path = Path(settings.DATABASES['default']['NAME'])
        if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError(
                'Το backup με αντιγραφή αρχείου υποστηρίζει μόνο SQLite. '
                'Για PostgreSQL χρησιμοποίησε pg_dump.'
            )
        if not db_path.exists():
            raise CommandError(f'Δεν βρέθηκε η βάση: {db_path}')

        # Backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f'crm_db_{timestamp}.backup'

        # Copy database
        shutil.copy2(db_path, backup_path)
        self.stdout.write(self.style.SUCCESS(
            f'✅ Backup ολοκληρώθηκε: {backup_path}'
        ))

        # Cleanup παλιών backups
        backups = sorted(backup_dir.glob('*.backup'))
        if options['keep_days'] > 0:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=options['keep_days'])
            for old_backup in backups:
                if datetime.fromtimestamp(old_backup.stat().st_mtime) < cutoff:
                    old_backup.unlink()
                    self.stdout.write(f'🗑️ Διαγράφηκε παλιό backup: {old_backup.name}')
        elif len(backups) > 30:
            for old_backup in backups[:-30]:
                old_backup.unlink()
                self.stdout.write(f'🗑️ Διαγράφηκε παλιό backup: {old_backup.name}')
