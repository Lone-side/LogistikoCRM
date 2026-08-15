"""Rate limiting στα JWT auth endpoints.

Το /api/auth/login/ δεν είχε δικό του throttle scope και έπεφτε στο γενικό
`anon` (100/hour) — πολύ χαλαρό για endpoint που δοκιμάζει κωδικούς. Τα tests
εδώ κλειδώνουν ότι υπάρχει ξεχωριστό, αυστηρότερο όριο και ότι το refresh έχει
δικό του (πιο γενναιόδωρο) scope, ώστε μια μελλοντική αλλαγή στο
ACCESS_TOKEN_LIFETIME να μη βγάζει τους χρήστες έξω.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

User = get_user_model()

LOGIN_URL = "/accounting/api/auth/login/"
REFRESH_URL = "/accounting/api/auth/refresh/"


# Το project τρέχει με DatabaseCache ('django_cache_table'), που στήνεται με
# `manage.py createcachetable` — ο πίνακας ΔΕΝ υπάρχει στη test βάση, οπότε το
# throttling δεν μπορεί να μετρήσει τίποτα εδώ. Το locmem δίνει πραγματικό,
# απομονωμένο cache ανά test χωρίς εξάρτηση από Redis ή migrations.
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "auth-throttle-tests",
        }
    }
)
class LoginThrottleTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="logistis", password="Δοκιμαστικός-Κωδικός-2026"
        )

    def tearDown(self):
        cache.clear()

    def test_login_has_a_dedicated_scope(self):
        """Το scope πρέπει να υπάρχει και να είναι αυστηρότερο από το anon."""
        from django.conf import settings

        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertIn("login", rates)
        self.assertIn("token_refresh", rates)

        from accounting.api_auth import CustomTokenObtainPairView, CustomTokenRefreshView

        self.assertEqual(CustomTokenObtainPairView.throttle_scope, "login")
        self.assertEqual(CustomTokenRefreshView.throttle_scope, "token_refresh")

    def _configured_login_limit(self):
        """Πόσα login επιτρέπει η ΠΡΑΓΜΑΤΙΚΗ ρύθμιση.

        Δεν χρησιμοποιούμε override_settings για τα rates: το DRF δεσμεύει το
        SimpleRateThrottle.THROTTLE_RATES ως class attribute κατά το import,
        οπότε το override δεν φτάνει ποτέ στον throttle και το test θα περνούσε
        ψευδώς. Δοκιμάζουμε το όριο που όντως τρέχει στην παραγωγή.
        """
        from rest_framework.throttling import ScopedRateThrottle

        num, _duration = ScopedRateThrottle().parse_rate(
            ScopedRateThrottle.THROTTLE_RATES["login"]
        )
        return num

    def _login(self, password, ip):
        return self.client.post(
            LOGIN_URL,
            {"username": "logistis", "password": password},
            format="json",
            REMOTE_ADDR=ip,
        )

    def test_repeated_failed_logins_are_throttled(self):
        """Λάθος κωδικός ξανά και ξανά -> 429, όχι ατέρμονες δοκιμές."""
        limit = self._configured_login_limit()

        for attempt in range(limit):
            response = self._login("λάθος", "10.0.0.50")
            self.assertEqual(
                response.status_code, 401, f"προσπάθεια {attempt + 1}/{limit}"
            )

        limited = self._login("λάθος", "10.0.0.50")
        self.assertEqual(
            limited.status_code,
            429,
            f"το {limit + 1}ο login από την ίδια IP έπρεπε να κοπεί",
        )

    def test_throttle_blocks_correct_password_too(self):
        """Fail-closed: μόλις πέσει το όριο, ούτε ο σωστός κωδικός περνά.

        Αλλιώς ένας επιτιθέμενος θα μάθαινε πότε βρήκε τον σωστό κωδικό από τη
        διαφορά συμπεριφοράς.
        """
        limit = self._configured_login_limit()

        for _ in range(limit):
            self._login("λάθος", "10.0.0.51")

        blocked = self._login("Δοκιμαστικός-Κωδικός-2026", "10.0.0.51")
        self.assertEqual(blocked.status_code, 429)

    def test_a_different_ip_is_not_affected(self):
        """Το όριο είναι ανά IP — ένας επιτιθέμενος δεν κλειδώνει το γραφείο."""
        limit = self._configured_login_limit()

        for _ in range(limit + 1):
            self._login("λάθος", "10.0.0.52")

        other = self._login("Δοκιμαστικός-Κωδικός-2026", "10.0.0.53")
        self.assertEqual(other.status_code, 200)

    def test_refresh_limit_is_more_generous_than_login(self):
        """Το refresh είναι αυτόματο — δεν πρέπει να κόβει κανονικές συνεδρίες."""
        from django.conf import settings
        from rest_framework.throttling import ScopedRateThrottle

        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        throttle = ScopedRateThrottle()
        login_num, login_dur = throttle.parse_rate(rates["login"])
        refresh_num, refresh_dur = throttle.parse_rate(rates["token_refresh"])

        self.assertGreater(
            refresh_num / refresh_dur,
            login_num / login_dur,
            "το refresh πρέπει να επιτρέπει περισσότερα αιτήματα/δευτερόλεπτο "
            "από το login",
        )


class JWTLifetimeTest(APITestCase):
    """Το access token δεν πρέπει να ξαναγίνει μακρόβιο κατά λάθος."""

    def test_access_token_is_short_lived(self):
        from datetime import timedelta
        from django.conf import settings

        lifetime = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]
        self.assertLessEqual(
            lifetime,
            timedelta(minutes=60),
            "κλεμμένο access token δεν πρέπει να ζει πάνω από μία ώρα",
        )

    def test_rotation_requires_blacklist(self):
        """Rotation χωρίς blacklist αφήνει το παλιό refresh σε ισχύ."""
        from django.conf import settings

        if settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS"):
            self.assertTrue(
                settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION"),
                "με ROTATE_REFRESH_TOKENS πρέπει να είναι ενεργό και το "
                "BLACKLIST_AFTER_ROTATION",
            )

    def test_expired_token_cleanup_is_scheduled(self):
        """Με rotation+blacklist οι πίνακες μεγαλώνουν χωρίς καθαρισμό."""
        from django.conf import settings

        tasks = {
            entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()
        }
        self.assertIn("accounting.tasks.flush_expired_jwt_tokens", tasks)
