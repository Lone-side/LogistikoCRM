# mydata/encryption.py
"""
Encryption utilities για ευαίσθητα δεδομένα (myDATA, SMTP, κωδικοί πελατών).

Χρησιμοποιεί Fernet (symmetric encryption) από το cryptography package.

Κλειδιά (με σειρά προτεραιότητας):
- DATA_ENCRYPTION_KEY_CURRENT: το ενεργό κλειδί (Fernet key). Νέες
  κρυπτογραφήσεις γίνονται ΠΑΝΤΑ με αυτό.
- DATA_ENCRYPTION_KEY_PREVIOUS: προηγούμενο κλειδί, μόνο για αποκρυπτογράφηση
  κατά τη διάρκεια rotation.
- Legacy: SHA-256(SECRET_KEY) — μόνο για αποκρυπτογράφηση παλιών δεδομένων.
  Αν δεν έχει οριστεί DATA_ENCRYPTION_KEY_CURRENT, χρησιμοποιείται και για
  κρυπτογράφηση (με warning).

Rotation: python manage.py rotate_encryption_key
"""

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

logger = logging.getLogger(__name__)

_warned_legacy = False


def _legacy_fernet_key() -> bytes:
    """
    Παλιό (legacy) Fernet key παραγόμενο από το Django SECRET_KEY.

    Διατηρείται ΜΟΝΟ για αποκρυπτογράφηση δεδομένων που γράφτηκαν πριν
    την εισαγωγή του DATA_ENCRYPTION_KEY_CURRENT.
    """
    secret = settings.SECRET_KEY.encode('utf-8')
    key_hash = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(key_hash)


def _configured_key(name: str) -> Optional[bytes]:
    """Διαβάζει και επικυρώνει ένα Fernet key από τα settings."""
    value = getattr(settings, name, None) or None
    if not value:
        return None
    key = value.encode('utf-8') if isinstance(value, str) else value
    Fernet(key)  # validation — ρίχνει ValueError σε άκυρο κλειδί
    return key


def _get_fernet() -> MultiFernet:
    """
    MultiFernet: κρυπτογράφηση με το πρώτο key (CURRENT ή legacy fallback),
    αποκρυπτογράφηση με όλα (CURRENT → PREVIOUS → legacy).
    """
    global _warned_legacy
    keys = []
    current = _configured_key('DATA_ENCRYPTION_KEY_CURRENT')
    if current:
        keys.append(current)
    else:
        if not _warned_legacy:
            logger.warning(
                "DATA_ENCRYPTION_KEY_CURRENT δεν έχει οριστεί — χρήση legacy "
                "κλειδιού από SECRET_KEY. Όρισε ανεξάρτητο κλειδί "
                "(python scripts/generate_fernet_key.py)."
            )
            _warned_legacy = True
    previous = _configured_key('DATA_ENCRYPTION_KEY_PREVIOUS')
    if previous:
        keys.append(previous)
    keys.append(_legacy_fernet_key())
    return MultiFernet([Fernet(k) for k in keys])


def encrypt_value(plain_text: str) -> str:
    """
    Κρυπτογραφεί ένα string value.

    Args:
        plain_text: Το κείμενο προς κρυπτογράφηση

    Returns:
        Base64-encoded encrypted string

    Raises:
        ValueError: Αν το plain_text είναι κενό
    """
    if not plain_text:
        raise ValueError("Cannot encrypt empty value")

    try:
        fernet = _get_fernet()
        encrypted = fernet.encrypt(plain_text.encode('utf-8'))
        return encrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        raise


def decrypt_value(encrypted_text: str) -> str:
    """
    Αποκρυπτογραφεί ένα encrypted string.

    Args:
        encrypted_text: Base64-encoded encrypted string

    Returns:
        Decrypted plain text

    Raises:
        ValueError: Αν αποτύχει η αποκρυπτογράφηση
    """
    if not encrypted_text:
        raise ValueError("Cannot decrypt empty value")

    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(encrypted_text.encode('utf-8'))
        return decrypted.decode('utf-8')
    except InvalidToken:
        logger.error("Decryption failed - invalid token (possibly wrong SECRET_KEY)")
        raise ValueError(
            "Αποτυχία αποκρυπτογράφησης. "
            "Πιθανή αλλαγή SECRET_KEY ή κατεστραμμένα δεδομένα."
        )
    except Exception as e:
        logger.error(f"Decryption error: {e}")
        raise


def is_encrypted(value: str) -> bool:
    """
    Ελέγχει αν ένα value είναι ήδη encrypted.

    Fernet encrypted strings έχουν συγκεκριμένο format:
    - Ξεκινούν με 'gAAAAA'
    - Είναι base64-encoded
    """
    if not value:
        return False

    # Fernet tokens start with version byte 0x80 which is 'gA' in base64
    return value.startswith('gAAAAA')


def safe_decrypt(encrypted_text: Optional[str]) -> Optional[str]:
    """
    Safe version of decrypt - returns None on error instead of raising.

    Χρήσιμο για cases όπου θέλουμε graceful degradation.
    """
    if not encrypted_text:
        return None

    try:
        return decrypt_value(encrypted_text)
    except Exception as e:
        logger.warning(f"Safe decrypt failed: {e}")
        return None


class EncryptedFieldMixin:
    """
    Mixin για encrypted model fields.

    Usage in models:
        class MyModel(EncryptedFieldMixin, models.Model):
            _encrypted_field = models.TextField()

            @property
            def field(self):
                return self.get_decrypted('_encrypted_field')

            @field.setter
            def field(self, value):
                self.set_encrypted('_encrypted_field', value)
    """

    def get_decrypted(self, field_name: str) -> Optional[str]:
        """Get decrypted value of an encrypted field."""
        encrypted = getattr(self, field_name, None)
        if not encrypted:
            return None
        return safe_decrypt(encrypted)

    def set_encrypted(self, field_name: str, plain_value: str):
        """Set encrypted value for a field."""
        if plain_value:
            setattr(self, field_name, encrypt_value(plain_value))
        else:
            setattr(self, field_name, '')
