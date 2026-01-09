# -*- coding: utf-8 -*-
"""
Backup utilities for LogistikoCRM.

Provides functions to create and restore backups of database and media files.
"""
import os
import json
import shutil
import zipfile
import logging
from datetime import datetime
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)

# Μέγιστο μέγεθος backup αρχείου (500MB)
MAX_BACKUP_SIZE = 500 * 1024 * 1024

# Απαιτούμενα αρχεία στο backup ZIP
REQUIRED_BACKUP_FILES = ['database.json']


def create_backup(user=None, include_media=True, notes=''):
    """
    Δημιουργεί backup της βάσης και των media files.

    Args:
        user: Ο χρήστης που δημιουργεί το backup
        include_media: Αν θα συμπεριληφθούν τα media files
        notes: Σημειώσεις για το backup

    Returns:
        BackupHistory instance ή None σε περίπτωση σφάλματος
    """
    from .models import BackupSettings, BackupHistory

    backup_settings = BackupSettings.get_settings()
    backup_dir = backup_settings.get_backup_dir()

    # Δημιουργία φακέλου αν δεν υπάρχει
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'backup_{timestamp}.zip'
    file_path = os.path.join(backup_dir, filename)

    try:
        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Database dump
            db_dump = _dump_database()
            zipf.writestr('database.json', db_dump)

            # 2. Metadata
            metadata = {
                'created_at': datetime.now().isoformat(),
                'created_by': user.username if user else 'system',
                'django_version': settings.VERSION if hasattr(settings, 'VERSION') else 'unknown',
                'includes_media': include_media,
                'notes': notes,
            }
            zipf.writestr('metadata.json', json.dumps(metadata, indent=2, ensure_ascii=False))

            # 3. Media files (optional)
            if include_media and hasattr(settings, 'MEDIA_ROOT') and os.path.exists(settings.MEDIA_ROOT):
                media_root = settings.MEDIA_ROOT
                for root, dirs, files in os.walk(media_root):
                    # Skip backup folder itself
                    if 'backups' in root:
                        continue
                    for file in files:
                        file_path_full = os.path.join(root, file)
                        arcname = os.path.join('media', os.path.relpath(file_path_full, media_root))
                        zipf.write(file_path_full, arcname)

        # Δημιουργία record στο ιστορικό
        file_size = os.path.getsize(file_path)
        backup_record = BackupHistory.objects.create(
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            includes_db=True,
            includes_media=include_media,
            created_by=user,
            notes=notes
        )

        # Cleanup παλιών backups
        _cleanup_old_backups(backup_settings)

        logger.info(f"Backup created: {filename} ({file_size} bytes)")
        return backup_record

    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        # Διαγραφή ατελούς αρχείου
        if os.path.exists(file_path):
            os.remove(file_path)
        raise


def validate_backup_file(file_path):
    """
    Επικυρώνει ότι το αρχείο είναι έγκυρο backup ZIP.

    Args:
        file_path: Path προς το αρχείο

    Returns:
        tuple: (is_valid, error_message)
    """
    # Έλεγχος ύπαρξης
    if not os.path.exists(file_path):
        return False, "Το αρχείο δεν υπάρχει"

    # Έλεγχος μεγέθους
    file_size = os.path.getsize(file_path)
    if file_size > MAX_BACKUP_SIZE:
        return False, f"Το αρχείο υπερβαίνει το μέγιστο όριο ({MAX_BACKUP_SIZE // (1024*1024)}MB)"

    # Έλεγχος ότι είναι valid ZIP
    if not zipfile.is_zipfile(file_path):
        return False, "Το αρχείο δεν είναι έγκυρο ZIP"

    try:
        with zipfile.ZipFile(file_path, 'r') as zipf:
            # Έλεγχος για corrupted ZIP
            bad_file = zipf.testzip()
            if bad_file:
                return False, f"Corrupted αρχείο στο ZIP: {bad_file}"

            # Έλεγχος για απαιτούμενα αρχεία
            namelist = zipf.namelist()
            for required in REQUIRED_BACKUP_FILES:
                if required not in namelist:
                    return False, f"Λείπει απαιτούμενο αρχείο: {required}"

            # Έλεγχος για path traversal attacks (../)
            for name in namelist:
                if '..' in name or name.startswith('/'):
                    return False, f"Μη έγκυρο path στο ZIP: {name}"

            # Επικύρωση database.json format
            try:
                db_content = zipf.read('database.json').decode('utf-8')
                json.loads(db_content)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                return False, f"Μη έγκυρο database.json: {e}"

    except zipfile.BadZipFile:
        return False, "Κατεστραμμένο ZIP αρχείο"

    return True, None


def restore_backup(backup_id, user=None, mode='replace', create_safety_backup=True):
    """
    Επαναφέρει backup.

    ΣΗΜΑΝΤΙΚΟ: Αυτή η συνάρτηση διατηρεί τους superusers κατά το restore
    για να αποφευχθεί το πρόβλημα απώλειας πρόσβασης στο σύστημα.

    Args:
        backup_id: ID του BackupHistory record
        user: Ο χρήστης που κάνει restore
        mode: 'replace' (αντικατάσταση) ή 'merge' (συγχώνευση)
        create_safety_backup: Δημιουργία backup πριν το restore (default: True)

    Returns:
        dict με status και πληροφορίες

    Λειτουργία:
        1. Δημιουργεί safety backup (αν create_safety_backup=True)
        2. Διατηρεί τους τρέχοντες superusers σε memory
        3. Εκτελεί flush της βάσης
        4. Φορτώνει groups.json fixture (απαραίτητο για dependencies)
        5. Φορτώνει τα δεδομένα από το backup
        6. Επαναφέρει τους superusers αν δεν υπάρχουν στο backup
    """
    from .models import BackupHistory
    from django.utils import timezone

    result = {
        'success': False,
        'safety_backup_id': None,
        'error': None
    }

    try:
        backup = BackupHistory.objects.get(pk=backup_id)
    except BackupHistory.DoesNotExist:
        result['error'] = f"Backup {backup_id} not found"
        logger.error(result['error'])
        return result

    if not backup.file_exists():
        result['error'] = f"Backup file not found: {backup.file_path}"
        logger.error(result['error'])
        return result

    # Επικύρωση του backup αρχείου
    is_valid, error_msg = validate_backup_file(backup.file_path)
    if not is_valid:
        result['error'] = f"Invalid backup file: {error_msg}"
        logger.error(result['error'])
        return result

    # Δημιουργία safety backup πριν το restore (για replace mode)
    safety_backup = None
    if create_safety_backup and mode == 'replace':
        logger.info("Creating safety backup before restore...")
        try:
            safety_backup = create_backup(
                user=user,
                include_media=False,
                notes=f"Safety backup πριν restore από: {backup.filename}"
            )
            result['safety_backup_id'] = safety_backup.id
            logger.info(f"Safety backup created: {safety_backup.filename}")
        except Exception as e:
            logger.warning(f"Failed to create safety backup: {e}")
            # Συνεχίζουμε ακόμα και αν αποτύχει το safety backup

    try:
        with zipfile.ZipFile(backup.file_path, 'r') as zipf:
            # 1. Restore database
            if 'database.json' in zipf.namelist():
                db_data = zipf.read('database.json').decode('utf-8')
                _restore_database(db_data, mode=mode)

            # 2. Restore media files
            if backup.includes_media:
                media_files = [f for f in zipf.namelist() if f.startswith('media/')]
                for media_file in media_files:
                    # Skip directories
                    if media_file.endswith('/'):
                        continue
                    target_path = os.path.join(
                        settings.MEDIA_ROOT,
                        media_file.replace('media/', '', 1)
                    )
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)

                    if mode == 'replace' or not os.path.exists(target_path):
                        with zipf.open(media_file) as src, open(target_path, 'wb') as dst:
                            dst.write(src.read())

        # Ενημέρωση record
        backup.restored_at = timezone.now()
        backup.restored_by = user
        backup.restore_mode = mode
        backup.save()

        logger.info(f"Backup restored: {backup.filename} (mode: {mode})")
        result['success'] = True
        return result

    except Exception as e:
        logger.error(f"Backup restore failed: {e}")
        result['error'] = str(e)
        return result


def _dump_database():
    """
    Δημιουργεί JSON dump της βάσης.
    """
    output = StringIO()
    call_command(
        'dumpdata',
        '--natural-foreign',
        '--natural-primary',
        '--exclude=contenttypes',
        '--exclude=sessions',
        '--exclude=admin.logentry',
        '--indent=2',
        stdout=output
    )
    return output.getvalue()


def _restore_database(json_data, mode='replace'):
    """
    Επαναφέρει τη βάση από JSON dump.

    Args:
        json_data: JSON string με τα δεδομένα
        mode: 'replace' ή 'merge'
    """
    import tempfile
    from common.utils.helpers import USER_MODEL

    # Γράψε σε temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        f.write(json_data)
        temp_path = f.name

    try:
        if mode == 'replace':
            # ΠΡΙΝ το flush: Διατήρηση superusers για safety
            superusers_backup = []
            try:
                User = USER_MODEL
                for su in User.objects.filter(is_superuser=True):
                    superusers_backup.append({
                        'username': su.username,
                        'email': su.email,
                        'password': su.password,  # Ήδη hashed
                        'first_name': su.first_name,
                        'last_name': su.last_name,
                        'is_staff': su.is_staff,
                        'is_active': su.is_active,
                    })
                logger.info(f"Backed up {len(superusers_backup)} superusers before flush")
            except Exception as e:
                logger.warning(f"Failed to backup superusers: {e}")

            # Διαγραφή υπαρχόντων δεδομένων
            call_command('flush', '--no-input')

            # Φόρτωση βασικών fixtures (Groups) πρώτα
            try:
                call_command('loaddata', 'groups.json', verbosity=0)
                logger.info("Loaded groups fixture before restore")
            except Exception as e:
                logger.warning(f"Failed to load groups fixture: {e}")

        # Φόρτωση δεδομένων από backup
        call_command('loaddata', temp_path)

        # Επαναφορά superusers αν δεν υπάρχουν
        if mode == 'replace' and superusers_backup:
            User = USER_MODEL
            restored_count = 0
            for su_data in superusers_backup:
                # Έλεγχος αν υπάρχει ήδη από το backup
                if not User.objects.filter(username=su_data['username']).exists():
                    User.objects.create(
                        username=su_data['username'],
                        email=su_data['email'],
                        password=su_data['password'],
                        first_name=su_data['first_name'],
                        last_name=su_data['last_name'],
                        is_superuser=True,
                        is_staff=su_data['is_staff'],
                        is_active=su_data['is_active'],
                    )
                    restored_count += 1
                    logger.info(f"Restored missing superuser: {su_data['username']}")

            if restored_count > 0:
                logger.info(f"Restored {restored_count} superusers after backup restore")

    finally:
        os.unlink(temp_path)


def _cleanup_old_backups(backup_settings):
    """
    Διαγράφει παλιά backups αν ξεπεραστεί το όριο.
    """
    from .models import BackupHistory

    if backup_settings.max_backups <= 0:
        return

    backups = BackupHistory.objects.order_by('-created_at')
    if backups.count() > backup_settings.max_backups:
        old_backups = backups[backup_settings.max_backups:]
        for backup in old_backups:
            if backup.file_exists():
                try:
                    os.remove(backup.file_path)
                except OSError:
                    pass
            backup.delete()
        logger.info(f"Cleaned up {len(old_backups)} old backups")


def get_backup_list():
    """
    Επιστρέφει λίστα με τα διαθέσιμα backups.
    """
    from .models import BackupHistory

    return BackupHistory.objects.all().values(
        'id', 'filename', 'file_size', 'includes_db', 'includes_media',
        'created_at', 'created_by__username', 'restored_at', 'notes'
    )
