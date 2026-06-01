# -*- coding: utf-8 -*-
"""
Production safety guards (settings.py): in production (DEBUG=False) the app MUST
refuse to start with default/placeholder secrets. These tests load settings.py
in a subprocess with controlled env so the module-level guard executes.
"""
import os
import subprocess
import sys

from django.test import SimpleTestCase

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_settings(env_overrides):
    """Import webcrm.settings in a clean subprocess; return (rc, stderr)."""
    env = dict(os.environ)
    env.update(env_overrides)
    # Ensure a clean import (no inherited DJANGO_SETTINGS_MODULE side effects).
    code = (
        "import django.conf, importlib;"
        "import webcrm.settings as s;"
        "print('LOADED_OK')"
    )
    proc = subprocess.run(
        [sys.executable, '-c', code],
        cwd=BASE_DIR, env=env, capture_output=True, text=True,
    )
    return proc.returncode, (proc.stdout + proc.stderr)


class ProductionGuardTest(SimpleTestCase):
    def test_default_secret_key_blocks_startup_in_production(self):
        rc, out = _load_settings({
            'DEBUG': 'False',
            'SECRET_KEY': 'default-key-for-development',
            'FRITZ_API_TOKEN': 'a-real-token',
        })
        self.assertNotEqual(rc, 0, f'Expected failure, got success:\n{out}')
        self.assertIn('SECRET_KEY', out)
        self.assertIn('ImproperlyConfigured', out)

    def test_placeholder_fritz_token_blocks_startup_in_production(self):
        rc, out = _load_settings({
            'DEBUG': 'False',
            'SECRET_KEY': 'a-real-strong-secret-key-value',
            'FRITZ_API_TOKEN': 'change-this-token-in-production',
        })
        self.assertNotEqual(rc, 0, f'Expected failure, got success:\n{out}')
        self.assertIn('FRITZ_API_TOKEN', out)

    def test_proper_secrets_start_in_production(self):
        rc, out = _load_settings({
            'DEBUG': 'False',
            'SECRET_KEY': 'a-real-strong-secret-key-value',
            'FRITZ_API_TOKEN': 'a-real-fritz-token',
        })
        self.assertEqual(rc, 0, f'Expected success, got failure:\n{out}')
        self.assertIn('LOADED_OK', out)

    def test_debug_mode_allows_defaults(self):
        # In dev (DEBUG=True) defaults are fine — no guard.
        rc, out = _load_settings({
            'DEBUG': 'True',
            'SECRET_KEY': 'default-key-for-development',
        })
        self.assertEqual(rc, 0, f'Expected success in DEBUG, got failure:\n{out}')
