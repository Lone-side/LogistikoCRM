import logging

import requests
from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from common.utils.helpers import send_crm_email
from crm.models import LeadSource

logger = logging.getLogger(__name__)

RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'


class ContactForm(forms.Form):

    name = forms.CharField(
        label=_("Your name"),
        max_length=200
    )
    email = forms.EmailField(
        label=_("Your E-mail")
    )
    subject = forms.CharField(
        label=_("Subject"),
        max_length=200
    )
    phone = forms.CharField(
        label=_("Phone number (with country code)"),
        max_length=200
    )
    company = forms.CharField(
        label=_("Company name"),
        max_length=200
    )
    message = forms.CharField(
        label=_("Message"),
        required=False,
        widget=forms.Textarea
    )
    country = forms.CharField(
        max_length=40,
        required=False,
        widget=forms.HiddenInput
    )
    city = forms.CharField(
        max_length=40,
        required=False,
        widget=forms.HiddenInput
    )
    leadsource_token = forms.UUIDField(
        widget=forms.HiddenInput
    )

    def clean(self):
        super().clean()
        site_key = settings.GOOGLE_RECAPTCHA_SITE_KEY
        secret_key = settings.GOOGLE_RECAPTCHA_SECRET_KEY
        # Μερική configuration = configuration error, όχι σιωπηλή παράκαμψη.
        if bool(site_key) != bool(secret_key):
            raise ImproperlyConfigured(
                "Μερική reCAPTCHA configuration: τα GOOGLE_RECAPTCHA_SITE_KEY "
                "και GOOGLE_RECAPTCHA_SECRET_KEY πρέπει να είναι είτε και τα "
                "δύο ορισμένα είτε και τα δύο κενά."
            )
        if not secret_key:
            # Το reCAPTCHA δεν είναι configured — καμία απαίτηση token.
            return

        msg = _("Sorry, invalid reCAPTCHA. Please try again or send an email.")
        recaptcha_response = self.data.get("g-recaptcha-response")
        # Configured reCAPTCHA χωρίς token = απόρριψη (όχι παράκαμψη
        # του verification με απλή παράλειψη του πεδίου).
        if not recaptcha_response:
            raise forms.ValidationError(msg)

        data = {
            'secret': secret_key,
            'response': recaptcha_response
        }
        try:
            r = requests.post(
                RECAPTCHA_VERIFY_URL,
                data=data,
                timeout=settings.GOOGLE_RECAPTCHA_VERIFY_TIMEOUT,
            )
            result = r.json()
        except (requests.RequestException, ValueError) as e:
            # Timeout, network error ή malformed provider response:
            # fail closed — δεν δεχόμαστε τη φόρμα χωρίς verification.
            logger.warning("reCAPTCHA verification failed: %s", e)
            raise forms.ValidationError(msg)
        if not isinstance(result, dict):
            logger.warning(
                "reCAPTCHA verification returned malformed payload type: %s",
                type(result).__name__,
            )
            raise forms.ValidationError(msg)
        if "error-codes" in result and settings.ADMINS:
            leadsource_token = self.cleaned_data.get('leadsource_token')
            leadsource = LeadSource.objects.filter(uuid=leadsource_token).first()
            send_crm_email(
                "reCaptcha error",
                f"error-codes: {result['error-codes']}<br><br>"
                f"LeadSource token: {leadsource_token}<br><br>"
                f"LeadSource: {leadsource}",
                [adr[1] for adr in settings.ADMINS]
            )
        if not result.get('success') or "error-codes" in result:
            raise forms.ValidationError(msg)
