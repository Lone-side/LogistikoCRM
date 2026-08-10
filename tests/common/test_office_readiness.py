# -*- coding: utf-8 -*-
"""
Regression tests για το Local Office Operational Readiness profile.

Καλύπτει:

1. SECURE_REDIRECT_EXEMPT για τα anonymous health endpoints: με
   DJANGO_ENV=production το SECURE_SSL_REDIRECT γίνεται True και το
   container healthcheck (plain HTTP απευθείας στο gunicorn) έπαιρνε 301
   σε https → TLS handshake σε plaintext socket → ο web container έμενε
   μόνιμα unhealthy.

2. Δομή του docker-compose.office.yml overlay: τα published ports του
   nginx δένουν ΜΟΝΟ στο ${OFFICE_BIND_IP} (LAN interface), κανένα
   service δεν εκθέτει db/redis/web στο host, και το X-Forwarded-Proto
   ενεργοποιείται υποχρεωτικά.

3. .env.office.example: χωρίς πραγματικά secrets (tripwire), sandbox
   myDATA, RBAC enforcement, https-only origins, χωρίς wildcard hosts.

4. nginx/office.conf: TLS termination με parity στα location blocks του
   nginx/nginx.conf ώστε να μην αποκλίνουν σιωπηλά τα δύο configs.
"""
import re
from pathlib import Path

import yaml
from django.conf import settings
from django.test import TestCase, override_settings, tag

from tests.settings.test_runtime_config import _load_settings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# CI-only Fernet key — ίδιο με το security-smoke job στο tests.yml,
# δεν χρησιμοποιείται πουθενά πραγματικά.
_CI_FERNET_KEY = 'jhgAUo9ScsDy8CjlAM8XO5cFANKz_Nb2i01amVUla0c='

_PRODUCTION_ENV = {
    'DJANGO_ENV': 'production',
    'DEBUG': 'False',
    'FRITZ_API_TOKEN': 'office-tests-fritz-token',
    'DATA_ENCRYPTION_KEY_CURRENT': _CI_FERNET_KEY,
    'ENFORCE_CLIENT_ASSIGNMENT': 'True',
}


@tag('TestCase')
class ProductionRedirectExemptTest(TestCase):
    """Τα anonymous health endpoints πρέπει να εξαιρούνται του redirect."""

    def test_production_settings_define_redirect_exempt(self):
        """DJANGO_ENV=production ⇒ redirect ενεργό ΚΑΙ exempt λίστα."""
        s = _load_settings(_PRODUCTION_ENV, as_test_run=False)
        self.assertTrue(s.SECURE_SSL_REDIRECT)
        self.assertEqual(s.SECURE_REDIRECT_EXEMPT, s.HEALTH_CHECK_EXEMPT_URLS)
        self.assertIn(r'^api/health/$', s.SECURE_REDIRECT_EXEMPT)

    def test_detailed_endpoint_is_not_exempt(self):
        """Το admin-only detailed endpoint μένει πίσω από HTTPS."""
        s = _load_settings(_PRODUCTION_ENV, as_test_run=False)
        for pattern in s.SECURE_REDIRECT_EXEMPT:
            self.assertIsNone(
                re.match(pattern, 'api/health/detailed/'),
                msg=f'pattern {pattern!r} ταιριάζει το detailed endpoint',
            )

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=settings.HEALTH_CHECK_EXEMPT_URLS,
    )
    def test_health_endpoints_answer_plain_http(self):
        """Insecure request στα health endpoints δεν παίρνει 301."""
        for path in ('/api/health/', '/api/health/ready/',
                     '/api/health/live/'):
            response = self.client.get(path, secure=False)
            self.assertNotEqual(response.status_code, 301, msg=path)
            self.assertIn(response.status_code, (200, 503), msg=path)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=settings.HEALTH_CHECK_EXEMPT_URLS,
    )
    def test_other_paths_still_redirect(self):
        """Το exempt αφορά ΜΟΝΟ τα health endpoints — τίποτα άλλο."""
        for path in ('/api/health/detailed/', '/api/clients/',
                     '/contact_form/x/'):
            response = self.client.get(path, secure=False)
            self.assertEqual(response.status_code, 301, msg=path)

    def test_compose_healthcheck_url_is_exempt(self):
        """Το healthcheck URL του prod compose ταιριάζει στη λίστα."""
        compose = yaml.safe_load(
            (BASE_DIR / 'docker-compose.prod.yml').read_text(encoding='utf-8')
        )
        test_cmd = ' '.join(compose['services']['web']['healthcheck']['test'])
        match = re.search(r'http://localhost:8000(/[^"\')\s]+)', test_cmd)
        self.assertIsNotNone(match, msg=test_cmd)
        path = match.group(1).lstrip('/')
        self.assertTrue(
            any(re.match(p, path) for p in settings.HEALTH_CHECK_EXEMPT_URLS),
            msg=f'healthcheck path {path!r} δεν εξαιρείται από το redirect',
        )


class _OfficeOverrideLoader(yaml.SafeLoader):
    """SafeLoader που δέχεται τα Compose merge tags (!override/!reset)."""


for _tag in ('!override', '!reset'):
    _OfficeOverrideLoader.add_constructor(
        _tag,
        lambda loader, node, _t=_tag: (
            loader.construct_sequence(node)
            if isinstance(node, yaml.SequenceNode) else
            loader.construct_mapping(node)
            if isinstance(node, yaml.MappingNode) else
            loader.construct_scalar(node)
        ),
    )


@tag('TestCase')
class OfficeComposeStructureTest(TestCase):
    """Το overlay δένει το nginx ΜΟΝΟ στη LAN IP και τίποτα άλλο."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.overlay_text = (
            BASE_DIR / 'docker-compose.office.yml'
        ).read_text(encoding='utf-8')
        cls.overlay = yaml.load(cls.overlay_text, Loader=_OfficeOverrideLoader)
        cls.prod = yaml.safe_load(
            (BASE_DIR / 'docker-compose.prod.yml').read_text(encoding='utf-8')
        )

    def test_nginx_ports_bind_only_to_office_ip(self):
        ports = self.overlay['services']['nginx']['ports']
        self.assertTrue(ports)
        for port in ports:
            self.assertTrue(
                port.startswith('${OFFICE_BIND_IP'),
                msg=f'port {port!r} δεν δένει στο OFFICE_BIND_IP',
            )
            self.assertIn(':?', port, msg='το OFFICE_BIND_IP πρέπει να είναι υποχρεωτικό')

    def test_nginx_ports_use_override_tag(self):
        """Χωρίς !override το Compose ΠΡΟΣΘΕΤΕΙ στο 0.0.0.0:80 του prod."""
        self.assertRegex(self.overlay_text, r'ports:\s*!override')

    def test_overlay_exposes_no_other_service(self):
        for name, service in self.overlay['services'].items():
            if name == 'nginx':
                continue
            self.assertNotIn('ports', service, msg=name)
        self.assertNotIn('db', self.overlay['services'])
        self.assertNotIn('redis', self.overlay['services'])

    def test_overlay_mounts_office_conf_and_certs(self):
        volumes = self.overlay['services']['nginx']['volumes']
        self.assertIn(
            './nginx/office.conf:/etc/nginx/conf.d/default.conf:ro', volumes)
        self.assertIn('./certs/office.crt:/etc/nginx/certs/office.crt:ro',
                      volumes)
        self.assertIn('./certs/office.key:/etc/nginx/certs/office.key:ro',
                      volumes)

    def _merged_volumes(self):
        """
        Προσομοίωση του Compose merge για volumes: append των overlay
        entries πάνω στα prod (τα volumes ΔΕΝ φέρουν !override tag στο
        overlay, οπότε ο merged κατάλογος = prod + overlay). Έτσι το
        test καλύπτει το ΤΕΛΙΚΟ merged configuration χωρίς να απαιτεί
        docker CLI στο CI.
        """
        merged = {}
        for source in (self.prod, self.overlay):
            for name, service in source.get('services', {}).items():
                merged.setdefault(name, []).extend(
                    service.get('volumes', []))
        return merged

    def test_ca_private_key_never_mounted_in_any_container(self):
        """
        Το CA private key (office-ca.key) δεν επιτρέπεται να υπάρχει σε
        ΚΑΝΕΝΑ container — ούτε μέσω απευθείας mount ούτε μέσω mount
        ολόκληρου του ./certs φακέλου (που τον περιέχει).
        """
        for service, volumes in self._merged_volumes().items():
            for volume in volumes:
                source = str(volume).split(':', 1)[0]
                self.assertNotIn('office-ca.key', source,
                                 msg=f'{service}: {volume}')
                self.assertNotRegex(
                    source, r'(^|/)certs/?$',
                    msg=f'{service}: mount ολόκληρου του certs dir '
                        f'({volume}) εκθέτει το CA private key',
                )

    def test_only_nginx_mounts_cert_material(self):
        """Cert mounts μόνο στο nginx — ποτέ σε app/web containers."""
        for service, volumes in self._merged_volumes().items():
            if service == 'nginx':
                continue
            for volume in volumes:
                self.assertNotIn('certs', str(volume).split(':', 1)[0],
                                 msg=f'{service}: {volume}')

    def test_overlay_forces_x_forwarded_proto(self):
        env = self.overlay['services']['web']['environment']
        self.assertEqual(env['USE_X_FORWARDED_PROTO'], 'True')

    def test_prod_db_redis_still_unexposed(self):
        """Regression: το prod file πάνω στο οποίο βασιζόμαστε."""
        for name in ('db', 'redis', 'web', 'celery', 'celery-beat'):
            self.assertNotIn('ports', self.prod['services'][name], msg=name)


def _parse_env_example(path):
    """Απλό KEY=VALUE parse (χωρίς python-dotenv, μόνο για tests)."""
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        values[key.strip()] = value.strip()
    return values


@tag('TestCase')
class OfficeEnvExampleTest(TestCase):
    """Το .env.office.example: ασφαλή defaults, μηδέν πραγματικά secrets."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = _parse_env_example(BASE_DIR / '.env.office.example')

    def test_required_keys_present(self):
        for key in ('DJANGO_ENV', 'SECRET_KEY', 'DB_PASSWORD',
                    'DATA_ENCRYPTION_KEY_CURRENT', 'FRITZ_API_TOKEN',
                    'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS',
                    'ENFORCE_CLIENT_ASSIGNMENT',
                    'ALLOW_UNSCOPED_CLIENT_ACCESS', 'MYDATA_IS_SANDBOX',
                    'OFFICE_BIND_IP', 'OFFICE_HOSTNAME', 'SITE_URL',
                    'USE_X_FORWARDED_PROTO'):
            self.assertIn(key, self.env, msg=key)

    def test_secret_values_are_empty(self):
        """Tripwire: secrets στο template = διαρροή στο repo."""
        for key in ('SECRET_KEY', 'DB_PASSWORD', 'FRITZ_API_TOKEN',
                    'DATA_ENCRYPTION_KEY_CURRENT',
                    'DATA_ENCRYPTION_KEY_PREVIOUS', 'EMAIL_HOST_PASSWORD'):
            self.assertEqual(self.env.get(key, ''), '', msg=key)

    def test_security_posture_values(self):
        self.assertEqual(self.env['DJANGO_ENV'], 'production')
        self.assertEqual(self.env['ENFORCE_CLIENT_ASSIGNMENT'], 'True')
        self.assertEqual(self.env['ALLOW_UNSCOPED_CLIENT_ACCESS'], 'False')
        self.assertEqual(self.env['MYDATA_IS_SANDBOX'], 'True')
        self.assertEqual(self.env['USE_X_FORWARDED_PROTO'], 'True')

    def test_no_wildcard_hosts_and_https_origins(self):
        self.assertNotIn('*', self.env['ALLOWED_HOSTS'])
        origins = [o.strip() for o in
                   self.env['CSRF_TRUSTED_ORIGINS'].split(',') if o.strip()]
        self.assertTrue(origins)
        for origin in origins:
            self.assertTrue(origin.startswith('https://'), msg=origin)
        self.assertTrue(self.env['SITE_URL'].startswith('https://'))

    def test_bind_ip_is_not_wildcard(self):
        self.assertNotIn(self.env['OFFICE_BIND_IP'], ('0.0.0.0', '', '*'))


@tag('TestCase')
class OfficeNginxParityTest(TestCase):
    """Το office.conf δεν πρέπει να αποκλίνει από το nginx.conf."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prod_conf = (
            BASE_DIR / 'nginx' / 'nginx.conf').read_text(encoding='utf-8')
        cls.office_conf = (
            BASE_DIR / 'nginx' / 'office.conf').read_text(encoding='utf-8')

    def test_every_prod_location_exists_in_office(self):
        prod_locations = re.findall(r'^\s*(location[^{]+)\{',
                                    self.prod_conf, re.MULTILINE)
        self.assertTrue(prod_locations)
        for location in prod_locations:
            self.assertIn(location.strip(), self.office_conf,
                          msg=location.strip())

    def test_office_tls_server(self):
        self.assertIn('listen 443 ssl', self.office_conf)
        self.assertIn('ssl_certificate /etc/nginx/certs/office.crt',
                      self.office_conf)
        self.assertIn('ssl_certificate_key /etc/nginx/certs/office.key',
                      self.office_conf)

    def test_office_http_only_redirects(self):
        http_server = self.office_conf.split('listen 443')[0]
        self.assertIn('return 301 https://$host$request_uri', http_server)
        self.assertNotIn('proxy_pass', http_server)

    def test_protected_media_stays_internal(self):
        match = re.search(
            r'location /protected-media/ \{([^}]*)\}', self.office_conf)
        self.assertIsNotNone(match)
        self.assertIn('internal;', match.group(1))

    def test_body_size_parity(self):
        prod_size = re.search(r'client_max_body_size\s+(\S+);', self.prod_conf)
        office_size = re.search(
            r'client_max_body_size\s+(\S+);', self.office_conf)
        self.assertEqual(prod_size.group(1), office_size.group(1))


@tag('TestCase')
class DockerfileNonRootCollectstaticTest(TestCase):
    """
    Το collectstatic ΠΡΕΠΕΙ να τρέχει μετά το USER app στο app stage.

    Αν τρέξει ως root, το django.setup() ψήνει root-owned tendo singleton
    lockfiles (/tmp/-app-manage-*.lock) μέσα στο image και ΚΑΘΕ runtime
    process του μη-root user αποτυγχάνει με PermissionError — το
    production image δεν μπορεί να εκκινήσει καθόλου (crash loop).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        dockerfile = (BASE_DIR / 'Dockerfile').read_text(encoding='utf-8')
        # Μόνο το app stage (μέχρι το επόμενο FROM)
        cls.app_stage = dockerfile.split('AS app', 1)[1].split('FROM', 1)[0]

    def test_collectstatic_runs_after_user_app(self):
        user_pos = self.app_stage.find('USER app')
        collectstatic_pos = self.app_stage.find('collectstatic')
        self.assertGreater(user_pos, -1, msg='λείπει το USER app')
        self.assertGreater(collectstatic_pos, -1,
                           msg='λείπει το collectstatic')
        self.assertGreater(
            collectstatic_pos, user_pos,
            msg='το collectstatic τρέχει ως root — ψήνει root-owned '
                'tendo locks και το runtime crash-άρει ως user app',
        )

    def test_build_time_locks_are_cleaned(self):
        self.assertIn('rm -f /tmp/*.lock', self.app_stage)
