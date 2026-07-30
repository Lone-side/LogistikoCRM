from django.core.management.base import BaseCommand, CommandError
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from django.conf import settings


class Command(BaseCommand):
    help = (
        'Backup της βάσης δεδομένων με timestamp + καθαρισμός παλιών. '
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

    def handle(self, *args, **options):
        # Backup directory
        if options['output_dir']:
            backup_dir = Path(options['output_dir'])
        else:
            backup_dir = settings.BASE_DIR / 'backups'
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
            f'✅ Backup ολοκληρώθηκε: {backup_path}'
        ))
        self._cleanup(backup_dir, options['keep_days'])

    def _backup_sqlite(self, db, backup_dir, timestamp):
        db_path = Path(db['NAME'])
        if not db_path.exists():
            raise CommandError(f'Δεν βρέθηκε η βάση: {db_path}')
        backup_path = backup_dir / f'crm_db_{timestamp}.backup'
        shutil.copy2(db_path, backup_path)
        return backup_path

    def _backup_postgres(self, db, backup_dir, timestamp):
        pg_dump = shutil.which('pg_dump')
        if not pg_dump:
            raise CommandError(
                'Δεν βρέθηκε το pg_dump. Εγκατάστησε το postgresql-client '
                '(περιλαμβάνεται στο production Docker image).'
            )
        backup_path = backup_dir / f'crm_db_{timestamp}.pgdump'
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

    def _cleanup(self, backup_dir, keep_days):
        backups = sorted(
            list(backup_dir.glob('*.backup')) + list(backup_dir.glob('*.pgdump')),
            key=lambda p: p.stat().st_mtime,
        )
        if keep_days > 0:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=keep_days)
            for old_backup in backups:
                if datetime.fromtimestamp(old_backup.stat().st_mtime) < cutoff:
                    old_backup.unlink()
                    self.stdout.write(f'🗑️ Διαγράφηκε παλιό backup: {old_backup.name}')
        elif len(backups) > 30:
            for old_backup in backups[:-30]:
                old_backup.unlink()
                self.stdout.write(f'🗑️ Διαγράφηκε παλιό backup: {old_backup.name}')
