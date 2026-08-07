"""
Επαναφορά βάσης δεδομένων + media από backup που παρήγαγε το
`python manage.py backup_database`.

    python manage.py restore_database --latest
    python manage.py restore_database 20260807_134442
    python manage.py restore_database crm_db_20260807_134442.backup
    python manage.py restore_database --list

⚠️ ΠΡΟΣΟΧΗ: αντικαθιστά την τρέχουσα βάση. Πριν την αντικατάσταση κρατά
αντίγραφο ασφαλείας της υπάρχουσας βάσης/media, ώστε μια λάθος επαναφορά
να είναι αναστρέψιμη.
"""
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from accounting.management.commands.backup_database import (
    BACKUP_PREFIX, DB_SUFFIXES, MEDIA_PREFIX, MEDIA_SUFFIX, default_backup_dir,
)


class Command(BaseCommand):
    help = 'Επαναφορά βάσης δεδομένων και media από backup.'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup', type=str, nargs='?', default='',
            help='Timestamp (π.χ. 20260807_134442) ή όνομα αρχείου backup.'
        )
        parser.add_argument(
            '--backup-dir', type=str, default='',
            help='Φάκελος backups (default: BASE_DIR/backups)'
        )
        parser.add_argument(
            '--latest', action='store_true',
            help='Επαναφορά του πιο πρόσφατου backup.'
        )
        parser.add_argument(
            '--list', action='store_true', dest='list_backups',
            help='Εμφάνιση των διαθέσιμων backups και έξοδος.'
        )
        parser.add_argument(
            '--skip-media', action='store_true',
            help='Παράλειψη επαναφοράς των media αρχείων.'
        )
        parser.add_argument(
            '--yes', action='store_true',
            help='Χωρίς ερώτηση επιβεβαίωσης (ΕΠΙΚΙΝΔΥΝΟ).'
        )

    # ------------------------------------------------------------------ #

    def handle(self, *args, **options):
        backup_dir = (
            Path(options['backup_dir']) if options['backup_dir']
            else default_backup_dir()
        )
        if not backup_dir.exists():
            raise CommandError(f'Δεν βρέθηκε ο φάκελος backups: {backup_dir}')

        available = self._available(backup_dir)

        if options['list_backups']:
            self._print_list(backup_dir, available)
            return

        if not available:
            raise CommandError(f'Δεν υπάρχουν backups στο {backup_dir}')

        db_file = self._select(available, options)
        timestamp = db_file.name[len(BACKUP_PREFIX):-len(db_file.suffix)]

        self._check_engine_matches(db_file)

        if not options['yes']:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️ Θα αντικατασταθεί η τρέχουσα βάση από το {db_file.name}.\n'
            ))
            if input('Γράψε "YES" για συνέχεια: ') != 'YES':
                self.stdout.write('Η επαναφορά ακυρώθηκε.')
                return

        self.stdout.write(self.style.SUCCESS(f'🔄 Επαναφορά: {db_file.name}'))
        self._restore_database(db_file)
        self.stdout.write(self.style.SUCCESS('✅ Η βάση επαναφέρθηκε'))

        if not options['skip_media']:
            media_file = backup_dir / f'{MEDIA_PREFIX}{timestamp}{MEDIA_SUFFIX}'
            if media_file.exists():
                try:
                    self._restore_media(media_file)
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(self.style.WARNING(
                        f'⚠️ Η επαναφορά των media απέτυχε: {exc}'
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS('✅ Τα media επαναφέρθηκαν'))
            else:
                self.stdout.write(
                    f'ℹ️ Δεν υπάρχει media backup για το {timestamp} — παραλείπεται.'
                )

        self.stdout.write(self.style.SUCCESS('\n✅ Ολοκληρώθηκε.'))

    # ------------------------------------------------------------------ #

    def _available(self, backup_dir):
        """Τα διαθέσιμα backups βάσης, από το παλαιότερο στο νεότερο."""
        return sorted(
            [p for p in backup_dir.iterdir()
             if p.name.startswith(BACKUP_PREFIX) and p.suffix in DB_SUFFIXES],
            key=lambda p: p.name,
        )

    def _print_list(self, backup_dir, available):
        if not available:
            self.stdout.write(f'Δεν υπάρχουν backups στο {backup_dir}')
            return
        self.stdout.write(f'Διαθέσιμα backups στο {backup_dir}:')
        for path in available:
            timestamp = path.name[len(BACKUP_PREFIX):-len(path.suffix)]
            media = backup_dir / f'{MEDIA_PREFIX}{timestamp}{MEDIA_SUFFIX}'
            size = path.stat().st_size / (1024 * 1024)
            flag = ' + media' if media.exists() else ''
            self.stdout.write(f'  {path.name}  ({size:.1f} MB){flag}')

    def _select(self, available, options):
        """Επιλογή του backup προς επαναφορά από τα ορίσματα."""
        if options['latest']:
            return available[-1]

        wanted = options['backup']
        if not wanted:
            raise CommandError(
                'Δώσε timestamp/όνομα αρχείου, ή --latest. '
                'Δες τα διαθέσιμα με --list.'
            )

        for path in available:
            timestamp = path.name[len(BACKUP_PREFIX):-len(path.suffix)]
            if wanted in (path.name, path.stem, timestamp):
                return path

        raise CommandError(
            f'Δεν βρέθηκε backup «{wanted}». Δες τα διαθέσιμα με --list.'
        )

    def _check_engine_matches(self, db_file):
        """
        Ένα .backup (SQLite) δεν επαναφέρεται σε PostgreSQL και αντίστροφα —
        απόρριψε το νωρίς αντί να αφήσεις μισοεπαναφερμένη βάση.
        """
        engine = settings.DATABASES['default']['ENGINE']
        is_sqlite = engine == 'django.db.backends.sqlite3'
        if is_sqlite and db_file.suffix != '.backup':
            raise CommandError(
                f'Το {db_file.name} είναι PostgreSQL dump, αλλά η τρέχουσα '
                f'βάση είναι SQLite.'
            )
        if not is_sqlite and db_file.suffix != '.pgdump':
            raise CommandError(
                f'Το {db_file.name} είναι SQLite backup, αλλά η τρέχουσα '
                f'βάση είναι PostgreSQL.'
            )

    # ------------------------------------------------------------------ #

    def _restore_database(self, db_file):
        db = settings.DATABASES['default']
        if db['ENGINE'] == 'django.db.backends.sqlite3':
            self._restore_sqlite(db, db_file)
        else:
            self._restore_postgres(db, db_file)

    def _restore_sqlite(self, db, db_file):
        db_path = Path(db['NAME'])
        connections.close_all()

        if db_path.exists():
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safety = db_path.with_name(f'{db_path.name}.before_restore_{stamp}')
            shutil.copy2(db_path, safety)
            self.stdout.write(f'📋 Η τρέχουσα βάση φυλάχθηκε στο: {safety}')

        shutil.copy2(db_file, db_path)

    def _restore_postgres(self, db, db_file):
        pg_restore = shutil.which('pg_restore')
        if not pg_restore:
            raise CommandError(
                'Δεν βρέθηκε το pg_restore. Εγκατάστησε το postgresql-client.'
            )
        connections.close_all()

        cmd = [pg_restore, '--clean', '--if-exists', '--format=custom',
               f"--dbname={db['NAME']}"]
        if db.get('HOST'):
            cmd.append(f"--host={db['HOST']}")
        if db.get('PORT'):
            cmd.append(f"--port={db['PORT']}")
        if db.get('USER'):
            cmd.append(f"--username={db['USER']}")
        cmd.append(str(db_file))

        env = os.environ.copy()
        if db.get('PASSWORD'):
            env['PGPASSWORD'] = db['PASSWORD']

        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=3600
        )
        if result.returncode != 0:
            raise CommandError(f'Το pg_restore απέτυχε: {result.stderr.strip()}')

    def _restore_media(self, media_file):
        media_root = Path(settings.MEDIA_ROOT)

        if media_root.exists():
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safety = media_root.parent / f'{media_root.name}_before_restore_{stamp}'
            shutil.move(str(media_root), str(safety))
            self.stdout.write(f'📋 Τα τρέχοντα media φυλάχθηκαν στο: {safety}')

        media_root.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['tar', '-xzf', str(media_file), '-C', str(media_root.parent)]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600
        )
        if result.returncode != 0:
            raise RuntimeError(f'Η αποσυμπίεση tar απέτυχε: {result.stderr.strip()}')
