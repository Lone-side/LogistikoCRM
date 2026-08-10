# -*- coding: utf-8 -*-
"""
Tests για το read-only office_preflight command (office/LAN readiness).

Όλοι οι εξωτερικοί έλεγχοι (Celery, disk, loopback HTTP) γίνονται mock —
κανένα πραγματικό network probe. Το backup directory είναι tmp ώστε να
ελέγχεται η ηλικία backup ντετερμινιστικά.
"""
import os
import tempfile
import time
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings, tag
from io import StringIO

COMMAND_MODULE = 'accounting.management.commands.office_preflight'

_GREEN_ENV = {
    'DJANGO_ENV': 'production',
    'ALLOWED_HOSTS': 'crm.office.lan,192.168.1.10',
    'CSRF_TRUSTED_ORIGINS': 'https://crm.office.lan,https://192.168.1.10',
    'USE_X_FORWARDED_PROTO': 'True',
}

_CI_FERNET_KEY = 'jhgAUo9ScsDy8CjlAM8XO5cFANKz_Nb2i01amVUla0c='

_GREEN_SETTINGS = {
    'SECRET_KEY': 'x' * 60,
    'FRITZ_API_TOKEN': 'office-preflight-test-token',
    'DATA_ENCRYPTION_KEY_CURRENT': _CI_FERNET_KEY,
    'MYDATA_IS_SANDBOX': True,
}

HEALTHY = {'status': 'healthy'}


@tag('TestCase')
class OfficePreflightTest(TestCase):
    """Συμπεριφορά του office_preflight σε πράσινα και κόκκινα σενάρια."""

    @classmethod
    def setUpTestData(cls):
        for name in ('Διαχειριστής', 'Λογιστής', 'Βοηθός'):
            Group.objects.get_or_create(name=name)
        get_user_model().objects.create_superuser(
            username='preflight_admin', password='test-secret-123',
            email='pf@example.com',
        )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.backup_dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        # Φρέσκο backup ώστε το πράσινο σενάριο να είναι πράσινο
        self.fresh_backup = self.backup_dir / 'crm_db_20260809_020000.backup'
        self.fresh_backup.write_bytes(b'test')

    def run_preflight(self, env_overrides=None, settings_overrides=None,
                      probe=('ok', 200), celery=None, disk=None,
                      fail_on_findings=False, **kwargs):
        """Τρέχει το command με πλήρως ελεγχόμενο περιβάλλον."""
        env = {**_GREEN_ENV, **(env_overrides or {})}
        s = {**_GREEN_SETTINGS, **(settings_overrides or {})}
        out = StringIO()
        with mock.patch.dict(os.environ, env), \
                override_settings(**s), \
                mock.patch(f'{COMMAND_MODULE}.default_backup_dir',
                           return_value=self.backup_dir), \
                mock.patch(f'{COMMAND_MODULE}.probe_local_health',
                           return_value=probe), \
                mock.patch(f'{COMMAND_MODULE}.check_celery',
                           return_value=celery or dict(HEALTHY, workers=1)), \
                mock.patch(f'{COMMAND_MODULE}.check_disk_space',
                           return_value=disk or dict(HEALTHY,
                                                     used_percent=42.0)):
            call_command('office_preflight',
                         fail_on_findings=fail_on_findings, stdout=out,
                         **kwargs)
        return out.getvalue()

    def assert_check(self, output, level, check):
        self.assertRegex(output, rf'\[{level}\][^\n]*\s{check}:')

    # ---- πράσινο σενάριο ----

    def test_all_green(self):
        output = self.run_preflight()
        self.assertNotIn('[FAIL]', output)
        for check in ('production-mode', 'allowed-hosts', 'csrf-origins',
                      'x-forwarded-proto', 'secret-key', 'fritz-token',
                      'encryption-key', 'database', 'cache', 'celery',
                      'disk', 'migrations', 'writable-media',
                      'writable-backups', 'rbac-groups', 'superuser',
                      'backup-age', 'mydata-sandbox', 'mydata-client-creds',
                      'local-health'):
            self.assert_check(output, 'OK', check)

    def test_green_run_is_read_only(self):
        before = sorted(p.name for p in self.backup_dir.iterdir())
        self.run_preflight()
        after = sorted(p.name for p in self.backup_dir.iterdir())
        self.assertEqual(before, after)

    def test_fail_on_findings_green_passes(self):
        # Δεν πρέπει να σηκώσει CommandError όταν όλα είναι πράσινα
        self.run_preflight(fail_on_findings=True)

    # ---- fail-on-findings συμβόλαιο ----

    def test_fail_on_findings_raises(self):
        with self.assertRaises(CommandError):
            self.run_preflight(env_overrides={'ALLOWED_HOSTS': '*'},
                               fail_on_findings=True)

    def test_without_flag_reports_but_does_not_raise(self):
        output = self.run_preflight(env_overrides={'ALLOWED_HOSTS': '*'})
        self.assert_check(output, 'FAIL', 'allowed-hosts')

    # ---- επιμέρους αποτυχίες ----

    def test_wildcard_allowed_hosts_fails(self):
        output = self.run_preflight(
            env_overrides={'ALLOWED_HOSTS': 'crm.office.lan,*'})
        self.assert_check(output, 'FAIL', 'allowed-hosts')

    def test_http_csrf_origin_fails(self):
        output = self.run_preflight(
            env_overrides={'CSRF_TRUSTED_ORIGINS':
                           'https://crm.office.lan,http://192.168.1.10'})
        self.assert_check(output, 'FAIL', 'csrf-origins')

    def test_missing_forwarded_proto_fails(self):
        output = self.run_preflight(
            env_overrides={'USE_X_FORWARDED_PROTO': 'False'})
        self.assert_check(output, 'FAIL', 'x-forwarded-proto')

    def test_placeholder_secret_key_fails(self):
        output = self.run_preflight(
            settings_overrides={'SECRET_KEY':
                                'default-key-for-development'})
        self.assert_check(output, 'FAIL', 'secret-key')

    def test_invalid_fernet_key_fails(self):
        output = self.run_preflight(
            settings_overrides={'DATA_ENCRYPTION_KEY_CURRENT': 'not-a-key'})
        self.assert_check(output, 'FAIL', 'encryption-key')

    def test_missing_rbac_group_fails(self):
        Group.objects.filter(name='Βοηθός').delete()
        try:
            output = self.run_preflight()
        finally:
            Group.objects.get_or_create(name='Βοηθός')
        self.assert_check(output, 'FAIL', 'rbac-groups')
        self.assertIn('Βοηθός', output)

    def test_stale_backup_fails(self):
        stale = time.time() - 30 * 3600
        os.utime(self.fresh_backup, (stale, stale))
        output = self.run_preflight()
        self.assert_check(output, 'FAIL', 'backup-age')

    def test_no_backup_warns_not_fails(self):
        self.fresh_backup.unlink()
        output = self.run_preflight()
        self.assert_check(output, 'WARN', 'backup-age')
        self.assertNotIn('[FAIL]', output)

    def test_custom_max_backup_age(self):
        old = time.time() - 30 * 3600
        os.utime(self.fresh_backup, (old, old))
        output = self.run_preflight(max_backup_age_hours=48)
        self.assert_check(output, 'OK', 'backup-age')

    def test_mydata_production_mode_fails(self):
        output = self.run_preflight(
            settings_overrides={'MYDATA_IS_SANDBOX': False})
        self.assert_check(output, 'FAIL', 'mydata-sandbox')

    def test_active_production_client_credentials_fail_without_pii(self):
        """Fail-closed: ενεργά production credentials = FAIL, όχι WARN."""
        from accounting.models import ClientProfile
        from mydata.models import MyDataCredentials
        client = ClientProfile.objects.create(
            afm='090000045', onoma='ΔΟΚΙΜΑΣΤΙΚΗ ΕΠΕ')
        MyDataCredentials.objects.create(
            client=client, is_sandbox=False, is_active=True)
        output = self.run_preflight()
        self.assert_check(output, 'FAIL', 'mydata-client-creds')
        with self.assertRaises(CommandError):
            self.run_preflight(fail_on_findings=True)
        # Ποτέ ΑΦΜ/επωνυμία στο output
        self.assertNotIn('090000045', output)
        self.assertNotIn('ΔΟΚΙΜΑΣΤΙΚΗ', output)

    def test_inactive_production_client_credentials_warn(self):
        """Ανενεργά production credentials: WARN (όχι FAIL)."""
        from accounting.models import ClientProfile
        from mydata.models import MyDataCredentials
        client = ClientProfile.objects.create(
            afm='090000046', onoma='ΑΝΕΝΕΡΓΗ ΕΠΕ')
        MyDataCredentials.objects.create(
            client=client, is_sandbox=False, is_active=False)
        output = self.run_preflight()
        self.assert_check(output, 'WARN', 'mydata-client-creds')
        self.assertNotIn('[FAIL]', output)
        self.assertNotIn('090000046', output)
        self.assertNotIn('ΑΝΕΝΕΡΓΗ', output)

    def test_active_sandbox_credentials_ok(self):
        """Sandbox credentials δεν προκαλούν ούτε WARN."""
        from accounting.models import ClientProfile
        from mydata.models import MyDataCredentials
        client = ClientProfile.objects.create(
            afm='090000047', onoma='SANDBOX ΕΠΕ')
        MyDataCredentials.objects.create(
            client=client, is_sandbox=True, is_active=True)
        output = self.run_preflight()
        self.assert_check(output, 'OK', 'mydata-client-creds')

    def test_pending_migrations_fail(self):
        with mock.patch(
                f'{COMMAND_MODULE}.MigrationExecutor') as executor_cls:
            executor = executor_cls.return_value
            executor.migration_plan.return_value = [('app', 'fake')]
            output = self.run_preflight()
        self.assert_check(output, 'FAIL', 'migrations')

    def test_redirect_on_local_health_fails(self):
        """Regression detector για το SECURE_REDIRECT_EXEMPT."""
        output = self.run_preflight(probe=('redirect', 301))
        self.assert_check(output, 'FAIL', 'local-health')

    def test_unreachable_local_health_warns(self):
        output = self.run_preflight(probe=('unreachable', 'refused'))
        self.assert_check(output, 'WARN', 'local-health')
        self.assertNotIn('[FAIL]', output)

    def test_celery_degraded_warns(self):
        output = self.run_preflight(
            celery={'status': 'degraded', 'workers': 0})
        self.assert_check(output, 'WARN', 'celery')

    def test_celery_unavailable_fails(self):
        output = self.run_preflight(celery={'status': 'unavailable'})
        self.assert_check(output, 'FAIL', 'celery')

    def test_disk_critical_fails(self):
        output = self.run_preflight(
            disk={'status': 'critical', 'used_percent': 95.0})
        self.assert_check(output, 'FAIL', 'disk')
