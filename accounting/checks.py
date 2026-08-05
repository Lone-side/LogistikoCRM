# -*- coding: utf-8 -*-
"""
Django system checks του accounting app.

E001: Σε production (DEBUG=False) το python-magic/libmagic ΠΡΕΠΕΙ να
λειτουργεί — αλλιώς ο έλεγχος πραγματικού περιεχομένου των uploads
(dangerous-content check του filing service) δεν εκτελείται και μένει
μόνο extension-based validation. Fail closed: blocking Error, όχι
σιωπηλό downgrade.

Σε development (DEBUG=True) παραμένει Warning, εκτός αν οριστεί ρητά
REQUIRE_LIBMAGIC=True στα settings.
"""
from django.conf import settings
from django.core.checks import Error, Warning as CheckWarning, register


def _magic_works():
    """Πραγματικός λειτουργικός έλεγχος: το detection πρέπει να αναγνωρίζει
    σωστά γνωστό PDF ΚΑΙ γνωστό HTML — όχι απλώς truthy αποτέλεσμα."""
    try:
        import magic
        pdf = magic.from_buffer(b'%PDF-1.4 probe', mime=True)
        html = magic.from_buffer(
            b'<!DOCTYPE html><html><body>x</body></html>', mime=True)
        return pdf == 'application/pdf' and html == 'text/html'
    except Exception:
        return False


@register()
def check_libmagic_available(app_configs, **kwargs):
    if _magic_works():
        return []
    msg = (
        'Το python-magic/libmagic δεν λειτουργεί — ο έλεγχος πραγματικού '
        'περιεχομένου των uploads ΔΕΝ θα εκτελείται (μόνο extension check). '
        'Εγκατάσταση: pip install python-magic + libmagic1.'
    )
    hard_fail = (not settings.DEBUG) or getattr(
        settings, 'REQUIRE_LIBMAGIC', False)
    if hard_fail:
        return [Error(msg, id='accounting.E001')]
    return [CheckWarning(msg, id='accounting.W001')]
