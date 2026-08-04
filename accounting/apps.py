from django.apps import AppConfig


class AccountingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounting'

    def ready(self):
        # Import signals to register them
        import accounting.signals  # noqa: F401
        # Register system checks (libmagic fail-closed σε production)
        import accounting.checks  # noqa: F401
