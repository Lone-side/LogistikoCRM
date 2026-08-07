"""
Backup βάσης δεδομένων + αρχείων media.

    python manage.py backup_database [--output-dir DIR] [--keep-days N] [--skip-media]

Παράγει ανά εκτέλεση:
    crm_db_{timestamp}.backup      (SQLite: αντίγραφο αρχείου)
    crm_db_{timestamp}.pgdump      (PostgreSQL: pg_dump custom format)
    crm_media_{timestamp}.tar.gz   (media files, εκτός αν --skip-media)

Η επαναφορά γίνεται με `python manage.py restore_database` — τα ονόματα
αρχείων εδώ και εκεί πρέπει να μένουν συγχρονισμένα (βλ. BACKUP_PREFIX /
MEDIA_PREFIX που μοιράζονται οι δύο εντολές).
"""
from django.core.management.base import BaseCommand, CommandError
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from django.conf import settings

# Κοινές σταθερές με το restore_database — μην τις αλλάξεις μονομερώς.
BACKUP_PREFIX = 'crm_db_'
MEDIA_PREFIX = 'crm_media_'
DB_SUFFIXES = ('.backup', '.pgdump')
MEDIA_SUFFIX = '.tar.gz'


def default_backup_dir():
    """Ο προεπιλεγμένος φάκελος backup (κοινός με το restore_database)."""
    return Path(settings.BASE_DIR) / 'backups'


class Command(BaseCommand):
    help = (
        'Backup της βάσης δεδομένων και των media με timestamp + καθαρισμός παλιών. '
        'SQLite: αντίγραφο αρχείου. PostgreSQL: pg_dump (custom format).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir', type=str, default='',
            help='Φάκελος αποθήκευσης (default: BASE_DIR/backups)'
        )
        parser.add_argument(
            '--keep-days', type=int, default=0,
            help='Διαγραφή backups παλαιότερων από Χ ημέρες (default: κράτα τα 30 τελευταία)'
        )
        parser.add_argument(
            '--skip-media', action='store_true',
            help='Παράλειψη του backup των media αρχείων'
        )

    def handle(self, *args, **options):
        # Backup directory
        if options['output_dir']:
            backup_dir = Path(options['output_dir'])
        else:
            backup_dir = default_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)

        db = settings.DATABASES['default']
        engine = db['ENGINE']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if engine == 'django.db.backends.sqlite3':
            backup_path = self._backup_sqlite(db, backup_dir, timestamp)
        elif engine in ('django.db.backends.postgresql',
                        'django.db.backends.postgresql_psycopg2'):
            backup_path = self._backup_postgres(db, backup_dir, timestamp)
        else:
            raise CommandError(
                f'Μη υποστηριζόμενη μηχανή βάσης για backup: {engine}'
            )

        self.stdout.write(self.style.SUCCESS(
            f'✅ Backup βάσης ολοκληρώθηκε: {backup_path}'
        ))

        # Media: η αποτυχία ΔΕΝ ακυρώνει το backup της βάσης, αλλά πρέπει να
        # φαίνεται καθαρά — τα έγγραφα πελατών είναι εξίσου κρίσιμα.
        if not options['skip_media']:
            try:
                media_path = self._backup_media(backup_dir, timestamp)
            except Exception as exc:  # noqa: BLE001 — θέλουμε ορατό warning
                self.stderr.write(self.style.WARNING(
                    f'⚠️ Το backup των media απέτυχε: {exc}'
                ))
            else:
                if media_path:
                    self.stdout.write(self.style.SUCCESS(
                        f'✅ Backup media ολοκληρώθηκε: {media_path}'
                    ))

        self._cleanup(backup_dir, options['keep_days'])

    def _backup_sqlite(self, db, backup_dir, timestamp):
        db_path = Path(db['NAME'])
        if not db_path.exists():
            raise CommandError(f'Δεν βρέθηκε η βάση: {db_path}')
        backup_path = backup_dir / f'{BACKUP_PREFIX}{timestamp}.backup'
        shutil.copy2(db_path, backup_path)
        return backup_path

    def _backup_postgres(self, db, backup_dir, timestamp):
        pg_dump = shutil.which('pg_dump')
        if not pg_dump:
            raise CommandError(
                'Δεν βρέθηκε το pg_dump. Εγκατάστησε το postgresql-client '
                '(περιλαμβάνεται στο production Docker image).'
            )
        backup_path = backup_dir / f'{BACKUP_PREFIX}{timestamp}.pgdump'
        cmd = [pg_dump, '--format=custom', f'--file={backup_path}']
        if db.get('HOST'):
            cmd.append(f"--host={db['HOST']}")
        if db.get('PORT'):
            cmd.append(f"--port={db['PORT']}")
        if db.get('USER'):
            cmd.append(f"--username={db['USER']}")
        cmd.append(db['NAME'])

        env = os.environ.copy()
        if db.get('PASSWORD'):
            env['PGPASSWORD'] = db['PASSWORD']

        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=1800
        )
        if result.returncode != 0:
            backup_path.unlink(missing_ok=True)
            raise CommandError(f'Το pg_dump απέτυχε: {result.stderr.strip()}')
        return backup_path

    def _backup_media(self, backup_dir, timestamp):
        """Συμπίεση του MEDIA_ROOT σε tar.gz δίπλα στο backup της βάσης."""
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            self.stdout.write(
                f'ℹ️ Δεν υπάρχει φάκελος media ({media_root}) — παραλείπεται.'
            )
            return None

        backup_path = backup_dir / f'{MEDIA_PREFIX}{timestamp}{MEDIA_SUFFIX}'
        cmd = [
            'tar', '-czf', str(backup_path),
            '-C', str(media_root.parent), media_root.name,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600
        )
        if result.returncode != 0:
            backup_path.unlink(missing_ok=True)
            raise RuntimeError(f'Το tar απέτυχε: {result.stderr.strip()}')
        return backup_path

    def _cleanup(self, backup_dir, keep_days):
        """
        Καθαρισμός παλιών backups. Τα media tarballs διαγράφονται μαζί με το
        αντίστοιχο backup βάσης (ίδιο timestamp), ώστε να μη μένουν ορφανά.
        """
        db_backups = sorted(
            [p for p in backup_dir.iterdir()
             if p.name.startswith(BACKUP_PREFIX) and p.suffix in DB_SUFFIXES],
            key=lambda p: p.stat().st_mtime,
        )

        if keep_days > 0:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=keep_days)
            doomed = [
                p for p in db_backups
                if datetime.fromtimestamp(p.stat().st_mtime) < cutoff
            ]
        elif len(db_backups) > 30:
            doomed = db_backups[:-30]
        else:
            doomed = []

        for old_backup in doomed:
            timestamp = old_backup.name[len(BACKUP_PREFIX):-len(old_backup.suffix)]
            old_backup.unlink()
            self.stdout.write(f'🗑️ Διαγράφηκε παλιό backup: {old_backup.name}')
            media_file = backup_dir / f'{MEDIA_PREFIX}{timestamp}{MEDIA_SUFFIX}'
            if media_file.exists():
                media_file.unlink()
                self.stdout.write(f'🗑️ Διαγράφηκε παλιό media backup: {media_file.name}')
