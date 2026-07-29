#!/bin/bash
#
# Automated backup script for LogistikoCRM
#
# ΣΗΜΕΙΩΣΗ: Αν τρέχει Celery beat, το backup γίνεται ήδη αυτόματα
# (task accounting.tasks.backup_database_task, καθημερινά 02:00).
# Αυτό το script χρειάζεται ΜΟΝΟ σε deployments χωρίς Celery.
#
# Example crontab entry (daily backup at 2 AM):
# 0 2 * * * /path/to/LogistikoCRM/scripts/backup_cron.sh >> /var/log/logistikocrm_backup.log 2>&1
#

set -e  # Exit on error

# Configuration — override με environment variables ή άλλαξε τα defaults
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(dirname "$SCRIPT_DIR")}"
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/venv}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/logistikocrm}"
KEEP_DAYS="${KEEP_DAYS:-30}"

# Activate virtual environment
source "${VENV_DIR}/bin/activate"

# Change to project directory
cd "${PROJECT_DIR}"

# Run backup
echo "========================================"
echo "Starting backup: $(date)"
echo "========================================"

python manage.py backup_database \
    --output-dir "${BACKUP_DIR}" \
    --keep-days "${KEEP_DAYS}"

echo "Backup completed: $(date)"
echo ""

# Optional: Send notification email on success
# echo "Backup completed successfully" | mail -s "LogistikoCRM Backup Success" admin@example.com
