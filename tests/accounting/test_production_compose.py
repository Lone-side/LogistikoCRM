from pathlib import Path

import yaml
from django.test import SimpleTestCase


class ProductionComposeStartupTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        compose_path = Path(__file__).resolve().parents[2] / "docker-compose.prod.yml"
        cls.compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    def test_workers_wait_for_migrated_healthy_web(self):
        services = self.compose["services"]

        self.assertEqual(
            services["celery"]["depends_on"]["web"]["condition"],
            "service_healthy",
        )
        self.assertEqual(
            services["celery-beat"]["depends_on"]["web"]["condition"],
            "service_healthy",
        )

    def test_production_disables_legacy_app_threads(self):
        self.assertEqual(
            self.compose["x-django-env"]["LEGACY_APP_THREADS_ENABLED"],
            "False",
        )

    def test_nginx_waits_for_healthy_web(self):
        self.assertEqual(
            self.compose["services"]["nginx"]["depends_on"]["web"]["condition"],
            "service_healthy",
        )
