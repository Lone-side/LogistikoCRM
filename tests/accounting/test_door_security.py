from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from accounting.models import DoorAccessLog


@override_settings(
    # These tests assert real authorization status codes (403/405/429/503/502).
    # Under DJANGO_ENV=production the production settings set
    # SECURE_SSL_REDIRECT=True, which turns every plain-http request into a 301
    # redirect that *masks* the real authorization response. SSL-redirect
    # behavior is covered separately by test_final_hardening.py; here we disable
    # the redirect so the door permission/throttle/audit logic is exercised
    # directly regardless of the runtime environment.
    SECURE_SSL_REDIRECT=False,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "door-security-tests",
        }
    }
)
class DoorSecurityTests(TestCase):
    legacy_mutations = (
        "/accounting/open-door/",
        "/accounting/door-control/",
    )
    api_mutations = (
        "/accounting/api/v1/door/open/",
        "/accounting/api/v1/door/pulse/",
    )

    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.staff_without_permission = user_model.objects.create_user(
            username="door_staff", password="test-pass", is_staff=True
        )
        cls.superuser_without_explicit_permission = user_model.objects.create_user(
            username="door_admin",
            password="test-pass",
            is_staff=True,
            is_superuser=True,
        )
        cls.authorized_user = user_model.objects.create_user(
            username="door_operator", password="test-pass"
        )
        permission = Permission.objects.get(
            content_type__app_label="accounting", codename="open_office_door"
        )
        cls.authorized_user.user_permissions.add(permission)

    def setUp(self):
        cache.clear()
        self.device_response = Mock(status_code=200)
        self.device_response.json.return_value = {"POWER": "ON"}

    def test_staff_and_superuser_status_do_not_authorize_legacy_mutations(self):
        for user in (self.staff_without_permission, self.superuser_without_explicit_permission):
            client = Client()
            client.force_login(user)
            for url in self.legacy_mutations:
                with self.subTest(user=user.username, url=url), patch(
                    "accounting.views.door.requests.get"
                ) as device_call:
                    response = client.post(url)
                    self.assertEqual(response.status_code, 403)
                    device_call.assert_not_called()

    def test_staff_and_superuser_status_do_not_authorize_api_mutations(self):
        for user in (self.staff_without_permission, self.superuser_without_explicit_permission):
            client = APIClient()
            client.force_authenticate(user)
            for url in self.api_mutations:
                with self.subTest(user=user.username, url=url), patch(
                    "accounting.api_door.requests.get"
                ) as device_call:
                    response = client.post(url, {}, format="json")
                    self.assertEqual(response.status_code, 403)
                    device_call.assert_not_called()

    def test_explicit_permission_authorizes_every_mutation_path(self):
        legacy_client = Client()
        legacy_client.force_login(self.authorized_user)
        for url in self.legacy_mutations:
            with self.subTest(url=url), patch(
                "accounting.views.door.requests.get", return_value=self.device_response
            ):
                self.assertEqual(legacy_client.post(url).status_code, 200)

        api_client = APIClient()
        api_client.force_authenticate(self.authorized_user)
        for url in self.api_mutations:
            pulse_configured = Mock(status_code=200)
            pulse_configured.json.return_value = {"PulseTime1": {"Set": 5}}
            responses = (
                [pulse_configured, self.device_response]
                if url.endswith('/pulse/') else [self.device_response]
            )
            with self.subTest(url=url), patch(
                "accounting.api_door.requests.get", side_effect=responses
            ):
                self.assertEqual(api_client.post(url, {}, format="json").status_code, 200)
        self.assertEqual(DoorAccessLog.objects.count(), 4)
        self.assertFalse(
            DoorAccessLog.objects.exclude(result="success").exists()
        )

    def test_mutations_reject_get(self):
        legacy_client = Client()
        legacy_client.force_login(self.authorized_user)
        api_client = APIClient()
        api_client.force_authenticate(self.authorized_user)
        self.assertEqual(legacy_client.get(self.legacy_mutations[0]).status_code, 405)
        legacy_client.force_login(self.staff_without_permission)
        with patch(
            "accounting.views.door.requests.get", return_value=self.device_response
        ):
            self.assertEqual(legacy_client.get(self.legacy_mutations[1]).status_code, 200)
        for url in self.api_mutations:
            with self.subTest(url=url):
                self.assertEqual(api_client.get(url).status_code, 405)

    def test_legacy_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.authorized_user)
        for url in self.legacy_mutations:
            with self.subTest(url=url), patch(
                "accounting.views.door.requests.get"
            ) as device_call:
                self.assertEqual(client.post(url).status_code, 403)
                device_call.assert_not_called()

    @patch("accounting.door_security.DOOR_MUTATION_RATE", 2)
    def test_throttle_is_shared_across_legacy_and_api_and_keys_by_ip(self):
        legacy_client = Client()
        legacy_client.force_login(self.authorized_user)
        api_client = APIClient()
        api_client.force_authenticate(self.authorized_user)

        with patch(
            "accounting.views.door.requests.get", return_value=self.device_response
        ), patch("accounting.api_door.requests.get", return_value=self.device_response):
            first = legacy_client.post(self.legacy_mutations[0], REMOTE_ADDR="10.0.0.8")
            second = api_client.post(
                self.api_mutations[0], {}, format="json", REMOTE_ADDR="10.0.0.8"
            )
            limited = api_client.post(
                self.api_mutations[1], {}, format="json", REMOTE_ADDR="10.0.0.8"
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(limited.status_code, 429)

    def test_every_mutation_attempt_creates_sanitized_audit_event(self):
        client = Client()
        client.force_login(self.authorized_user)
        with patch(
            "accounting.views.door.requests.get", return_value=self.device_response
        ):
            response = client.post(
                self.legacy_mutations[0],
                {"password": "must-not-be-logged"},
                HTTP_AUTHORIZATION="Bearer must-not-be-logged",
            )

        self.assertEqual(response.status_code, 200)
        log = DoorAccessLog.objects.get()
        self.assertEqual(log.user, self.authorized_user)
        self.assertEqual(log.action, "toggle")
        self.assertEqual(log.result, "success")
        self.assertNotIn("must-not-be-logged", str(log.response_data))

    @override_settings(REST_FRAMEWORK={"NUM_PROXIES": 1})
    def test_proxy_aware_client_ip_keeps_peer_for_audit(self):
        client = Client()
        client.force_login(self.authorized_user)
        with patch(
            "accounting.views.door.requests.get", return_value=self.device_response
        ):
            response = client.post(
                self.legacy_mutations[0],
                REMOTE_ADDR="172.20.0.5",
                HTTP_X_FORWARDED_FOR="198.51.100.24",
            )

        self.assertEqual(response.status_code, 200)
        log = DoorAccessLog.objects.get()
        self.assertEqual(str(log.ip_address), "198.51.100.24")
        self.assertEqual(log.response_data["peer_ip"], "172.20.0.5")

    @override_settings(
        DEBUG=False,
        TESTING=False,
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.db.DatabaseCache",
                "LOCATION": "django_cache_table",
            }
        },
    )
    def test_production_without_atomic_throttle_fails_closed(self):
        client = Client()
        client.force_login(self.authorized_user)
        with patch("accounting.views.door.requests.get") as device_call:
            response = client.post(self.legacy_mutations[0])

        self.assertEqual(response.status_code, 503)
        device_call.assert_not_called()
        self.assertEqual(DoorAccessLog.objects.get().result, "denied")

    def test_setup_roles_grants_door_permission_to_administrators(self):
        call_command("setup_roles", verbosity=0)
        administrators = Group.objects.get(name="Διαχειριστής")
        self.assertTrue(
            administrators.permissions.filter(
                content_type__app_label="accounting",
                codename="open_office_door",
            ).exists()
        )

    def test_pulse_rejects_non_positive_duration_without_touching_device(self):
        client = APIClient()
        client.force_authenticate(self.authorized_user)
        with patch("accounting.api_door.requests.get") as device_call:
            response = client.post(
                self.api_mutations[1], {"duration": -1}, format="json"
            )
        self.assertEqual(response.status_code, 400)
        device_call.assert_not_called()
        self.assertEqual(DoorAccessLog.objects.get().result, "failed")

    def test_pulse_rejects_sub_decisecond_duration_without_touching_device(self):
        client = APIClient()
        client.force_authenticate(self.authorized_user)
        with patch("accounting.api_door.requests.get") as device_call:
            response = client.post(
                self.api_mutations[1], {"duration": 0.05}, format="json"
            )

        self.assertEqual(response.status_code, 400)
        device_call.assert_not_called()
        self.assertEqual(DoorAccessLog.objects.get().result, "failed")

    def test_pulse_accepts_minimum_safe_decisecond(self):
        client = APIClient()
        client.force_authenticate(self.authorized_user)
        configured = Mock(status_code=200)
        configured.json.return_value = {"PulseTime1": {"Set": 1}}

        with patch(
            "accounting.api_door.requests.get",
            side_effect=[configured, self.device_response],
        ) as device_call:
            response = client.post(
                self.api_mutations[1], {"duration": 0.1}, format="json"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(device_call.call_count, 2)
        self.assertIn("PulseTime1%201", device_call.call_args_list[0].args[0])

    def test_pulse_does_not_energize_when_duration_ack_is_invalid(self):
        client = APIClient()
        client.force_authenticate(self.authorized_user)
        invalid_ack = Mock(status_code=200)
        invalid_ack.json.return_value = {"PulseTime1": {"Set": 50}}

        with patch(
            "accounting.api_door.requests.get", return_value=invalid_ack
        ) as device_call:
            response = client.post(
                self.api_mutations[1], {"duration": 1}, format="json"
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(device_call.call_count, 1)
        self.assertIn("PulseTime1", device_call.call_args.args[0])
        self.assertEqual(DoorAccessLog.objects.get().result, "failed")

    def test_pulse_does_not_energize_when_configuration_is_non_200(self):
        client = APIClient()
        client.force_authenticate(self.authorized_user)
        failed_configuration = Mock(status_code=500)

        with patch(
            "accounting.api_door.requests.get", return_value=failed_configuration
        ) as device_call:
            response = client.post(self.api_mutations[1], {}, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(device_call.call_count, 1)

    def test_pulse_never_succeeds_without_exact_power_on_ack(self):
        client = APIClient()
        client.force_authenticate(self.authorized_user)

        non_200 = Mock(status_code=500)
        malformed = Mock(status_code=200)
        malformed.json.side_effect = ValueError('malformed json')
        missing_power = Mock(status_code=200)
        missing_power.json.return_value = {"Status": "ok"}
        power_off = Mock(status_code=200)
        power_off.json.return_value = {"POWER": "OFF"}

        for final_response in (non_200, malformed, missing_power, power_off):
            with self.subTest(final_response=final_response):
                DoorAccessLog.objects.all().delete()
                configured = Mock(status_code=200)
                configured.json.return_value = {"PulseTime1": {"Set": 5}}
                with patch(
                    "accounting.api_door.requests.get",
                    side_effect=[configured, final_response],
                ) as device_call:
                    response = client.post(self.api_mutations[1], {}, format="json")

                self.assertEqual(response.status_code, 502)
                self.assertEqual(device_call.call_count, 2)
                self.assertFalse(
                    DoorAccessLog.objects.filter(result="success").exists()
                )

    def test_pulse_device_exceptions_return_non_success_http_status(self):
        client = APIClient()
        client.force_authenticate(self.authorized_user)

        cases = (
            (requests.exceptions.Timeout(), 504, "timeout"),
            (requests.exceptions.ConnectionError(), 503, "offline"),
            (RuntimeError("unexpected device failure"), 500, "failed"),
        )
        for device_error, expected_status, expected_result in cases:
            with self.subTest(expected_status=expected_status):
                DoorAccessLog.objects.all().delete()
                with patch(
                    "accounting.api_door.requests.get", side_effect=device_error
                ) as device_call:
                    response = client.post(self.api_mutations[1], {}, format="json")

                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(device_call.call_count, 1)
                self.assertEqual(DoorAccessLog.objects.get().result, expected_result)
                self.assertFalse(
                    DoorAccessLog.objects.filter(result="success").exists()
                )

    def test_denied_and_rate_limited_mutations_are_audited(self):
        denied_client = Client()
        denied_client.force_login(self.staff_without_permission)
        denied = denied_client.post(self.legacy_mutations[0], REMOTE_ADDR="10.0.0.9")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(DoorAccessLog.objects.get().result, "denied")

        DoorAccessLog.objects.all().delete()
        cache.clear()
        api_client = APIClient()
        api_client.force_authenticate(self.authorized_user)
        with patch("accounting.door_security.DOOR_MUTATION_RATE", 0):
            limited = api_client.post(
                self.api_mutations[0], {}, format="json", REMOTE_ADDR="10.0.0.10"
            )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(DoorAccessLog.objects.get().result, "rate_limited")


class DoorPermissionMigrationTest(TransactionTestCase):
    reset_sequences = True
    migrate_from = ("accounting", "10026_voipcalllog_call_set_null")
    migrate_to = ("accounting", "10027_door_open_permission")

    def _migrate(self, targets):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(targets)
        executor.loader.build_graph()
        return executor.loader.project_state(targets).apps

    def test_upgrade_preserves_access_for_existing_administrators(self):
        old_apps = self._migrate([self.migrate_from])
        User = old_apps.get_model("auth", "User")
        GroupModel = old_apps.get_model("auth", "Group")
        superuser = User.objects.create(
            username="legacy-superuser", is_superuser=True, is_active=True
        )
        GroupModel.objects.get_or_create(name="Διαχειριστής")

        new_apps = self._migrate([self.migrate_to])
        PermissionModel = new_apps.get_model("auth", "Permission")
        User = new_apps.get_model("auth", "User")
        GroupModel = new_apps.get_model("auth", "Group")
        permission = PermissionModel.objects.get(
            content_type__app_label="accounting",
            codename="open_office_door",
        )

        self.assertTrue(
            User.objects.get(pk=superuser.pk).user_permissions.filter(
                pk=permission.pk
            ).exists()
        )
        self.assertTrue(
            GroupModel.objects.get(name="Διαχειριστής").permissions.filter(
                pk=permission.pk
            ).exists()
        )

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()
