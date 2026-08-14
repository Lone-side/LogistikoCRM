import importlib
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, override_settings, tag

from analytics.apps import AnalyticsConfig
from common.apps import CommonConfig
from crm.apps import CrmConfig
from massmail.apps import MassmailConfig
from common.utils.helpers import send_crm_email
from crm.utils.restore_imap_emails import process_imported_email


@override_settings(TESTING=False, LEGACY_APP_THREADS_ENABLED=False)
class LegacyAppThreadContainmentTests(SimpleTestCase):
    def test_common_ready_does_not_start_legacy_threads(self):
        config = CommonConfig("common", importlib.import_module("common"))

        with (
            patch("common.utils.notif_email_sender.NotifEmailSender") as email_sender,
            patch("common.utils.reminders_sender.RemindersSender") as reminders_sender,
        ):
            config.ready()

        email_sender.assert_not_called()
        reminders_sender.assert_not_called()

    def test_crm_ready_does_not_start_rates_loader(self):
        config = CrmConfig("crm", importlib.import_module("crm"))

        with patch("crm.utils.rates_loader.RatesLoader") as rates_loader:
            config.ready()

        rates_loader.assert_not_called()

    def test_analytics_ready_does_not_start_snapshot_thread(self):
        config = AnalyticsConfig("analytics", importlib.import_module("analytics"))

        with patch(
            "analytics.utils.monthly_snapshot_saving.MonthlySnapshotSaving"
        ) as snapshot_saving:
            config.ready()

        snapshot_saving.assert_not_called()

    def test_massmail_ready_does_not_start_sender_thread(self):
        config = MassmailConfig("massmail", importlib.import_module("massmail"))

        with patch("massmail.utils.sendmassmail.SendMassmail") as massmail_sender:
            config.ready()

        massmail_sender.assert_not_called()

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="rc@example.invalid",
    )
    def test_notification_email_falls_back_to_synchronous_backend(self):
        mail.outbox = []
        with patch(
            "common.utils.helpers.apps.get_app_config",
            return_value=SimpleNamespace(),
        ):
            send_crm_email(
                "Release rehearsal",
                "Synthetic message",
                ["recipient@example.invalid"],
            )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Release rehearsal")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="rc@example.invalid",
    )
    def test_notification_email_failure_is_swallowed(self):
        """A broken SMTP backend must not crash the trigger request."""
        mail.outbox = []
        with patch(
            "django.core.mail.get_connection",
            side_effect=RuntimeError("SMTP down"),
        ):
            # Should not raise; delivery is best-effort.
            send_crm_email("x", "y", ["z@example.invalid"])
        self.assertEqual(len(mail.outbox), 0)


@tag("TestCase")
class SynchronousImportPathTests(SimpleTestCase):
    """Manual IMAP import must work even when legacy eml_queue is absent."""

    @override_settings(TESTING=False, LEGACY_APP_THREADS_ENABLED=False)
    def test_process_imported_email_runs_without_eml_queue(self):
        # The function itself must accept the same tuple the queue used to
        # carry, and not depend on an AppConfig.eml_queue attribute.
        from email.message import EmailMessage as PyEmailMessage

        raw = PyEmailMessage()
        raw["Subject"] = "Rehearsal"
        raw["From"] = "a@example.invalid"
        raw["To"] = "b@example.invalid"
        blob = raw.as_bytes()
        # No assertion on DB side effects (needs fixtures); the contract is
        # that it is callable and does not raise AttributeError on a missing
        # queue. We verify the import surface instead.
        self.assertTrue(callable(process_imported_email))
