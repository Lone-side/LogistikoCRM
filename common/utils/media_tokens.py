# -*- coding: utf-8 -*-
"""
Signed tokens για προστατευμένη πρόσβαση στα MEDIA αρχεία.

Σε παραγωγή τα /media/ URLs δεν σερβίρονται πια δημόσια: κάθε URL
συνοδεύεται από υπογεγραμμένο token (?mt=...) δεμένο με το συγκεκριμένο
αρχείο και με λήξη (MEDIA_TOKEN_MAX_AGE). Έτσι τα file_url που εκθέτει
το API δουλεύουν σε <a href>/<img>/window.open (χωρίς JWT header),
αλλά δεν είναι μαντέψιμα/μοιράσιμα επ' αόριστον.
"""
from urllib.parse import quote

from django.conf import settings
from django.core import signing

MEDIA_TOKEN_SALT = 'common.protected-media'


def make_media_token(path):
    """Δημιουργεί token για ένα storage path (σχετικό ως προς MEDIA_ROOT)."""
    return signing.dumps({'p': path}, salt=MEDIA_TOKEN_SALT)


def verify_media_token(token, path):
    """Επαληθεύει token για το συγκεκριμένο path. Επιστρέφει bool."""
    max_age = getattr(settings, 'MEDIA_TOKEN_MAX_AGE', 4 * 3600)
    try:
        data = signing.loads(token, salt=MEDIA_TOKEN_SALT, max_age=max_age)
    except signing.BadSignature:
        return False
    return data.get('p') == path


def signed_media_url(file_field, request=None):
    """
    Επιστρέφει το URL ενός FileField με signed token.
    Με request επιστρέφει absolute URI, αλλιώς σχετικό.
    """
    if not file_field:
        return None
    url = f"{file_field.url}?mt={quote(make_media_token(file_field.name))}"
    if request is not None:
        return request.build_absolute_uri(url)
    return url
