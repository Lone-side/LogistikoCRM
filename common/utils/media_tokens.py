# -*- coding: utf-8 -*-
"""
Signed tokens για προστατευμένη πρόσβαση στα MEDIA αρχεία.

Σε παραγωγή τα /media/ URLs δεν σερβίρονται δημόσια. Το API εκθέτει
`file_url` με υπογεγραμμένο token (?mt=...) ώστε να δουλεύουν σε
<a href> / <img src> / window.open — δηλαδή σε αιτήματα του browser που
ΔΕΝ μεταφέρουν το JWT header (το JWT ζει σε storage, όχι σε cookie).

ΜΟΝΤΕΛΟ ΑΣΦΑΛΕΙΑΣ
------------------
Το token είναι δεμένο **και με το path και με τον χρήστη**:

    {'p': <storage path>, 'u': <user id>}

Δεν είναι bearer token: **δεν παραχωρεί από μόνο του πρόσβαση**. Απλώς
δηλώνει «αυτό το αίτημα γίνεται για λογαριασμό του χρήστη U». Το
`serve_protected_media` εκτελεί ΚΑΝΟΝΙΚΑ ολόκληρο το authorization για
τον U σε κάθε request (view permission + client assignment). Συνέπειες:

* Διαρροή του URL δεν δίνει τίποτα παραπάνω από όσα δικαιούται ο U,
  μόνο για το συγκεκριμένο αρχείο, και μόνο μέχρι MEDIA_TOKEN_MAX_AGE.
* Ανάκληση ανάθεσης πελάτη ισχύει ΑΜΕΣΩΣ — δεν «παγώνει» στο token.
* Token χωρίς χρήστη (παλιάς μορφής) απορρίπτεται: fail closed.
"""
from urllib.parse import quote

from django.conf import settings
from django.core import signing

MEDIA_TOKEN_SALT = 'common.protected-media'


def make_media_token(path, user):
    """
    Δημιουργεί token για ένα storage path (σχετικό ως προς MEDIA_ROOT),
    δεμένο με τον συγκεκριμένο χρήστη.
    """
    user_id = getattr(user, 'pk', None)
    if user_id is None:
        raise ValueError(
            'make_media_token απαιτεί authenticated χρήστη — τα media '
            'tokens είναι δεμένα με χρήστη (δεν είναι bearer tokens).'
        )
    return signing.dumps({'p': path, 'u': user_id}, salt=MEDIA_TOKEN_SALT)


def resolve_media_token(token, path):
    """
    Επιστρέφει το user id του token αν είναι έγκυρο ΓΙΑ ΤΟ ΣΥΓΚΕΚΡΙΜΕΝΟ
    path, αλλιώς None.

    ΔΕΝ αποφασίζει πρόσβαση — μόνο ταυτότητα. Ο caller οφείλει να τρέξει
    το κανονικό authorization για τον χρήστη που επιστρέφεται.
    """
    if not token:
        return None
    max_age = getattr(settings, 'MEDIA_TOKEN_MAX_AGE', 4 * 3600)
    try:
        data = signing.loads(token, salt=MEDIA_TOKEN_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
    if data.get('p') != path:
        return None
    user_id = data.get('u')
    if user_id is None:
        # Token παλιάς μορφής (μόνο path) — δεν ταυτοποιεί χρήστη.
        return None
    return user_id


def token_user(token, path):
    """
    Επιστρέφει το User instance του token (ενεργό), αλλιώς None.
    Fail closed: ανύπαρκτος ή ανενεργός χρήστης → None.
    """
    user_id = resolve_media_token(token, path)
    if user_id is None:
        return None
    from django.contrib.auth import get_user_model
    return get_user_model().objects.filter(
        pk=user_id, is_active=True).first()


def signed_media_url(file_field, request=None, user=None):
    """
    Επιστρέφει το URL ενός FileField με signed token δεμένο στον χρήστη.

    Ο χρήστης λαμβάνεται από το `user` ή από το `request.user`. Χωρίς
    authenticated χρήστη επιστρέφεται το σκέτο URL (χωρίς token) — το
    οποίο θα απαιτήσει session, δηλαδή fail closed αντί για token που
    θα δούλευε για οποιονδήποτε.
    """
    if not file_field:
        return None
    if user is None and request is not None:
        user = getattr(request, 'user', None)
    url = file_field.url
    if user is not None and getattr(user, 'is_authenticated', False):
        url = f"{url}?mt={quote(make_media_token(file_field.name, user))}"
    if request is not None:
        return request.build_absolute_uri(url)
    return url
