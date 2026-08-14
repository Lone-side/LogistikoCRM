from tendo.singleton import SingleInstanceException
from django.apps import AppConfig
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class MassmailConfig(AppConfig):
    name = 'massmail'
    verbose_name = _("Mass mail")
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        if not settings.LEGACY_APP_THREADS_ENABLED:
            return

        from massmail.utils.sendmassmail import SendMassmail
        try:
            self.smm = SendMassmail()       # NOQA
            self.smm.start()
        except SingleInstanceException:
            pass
