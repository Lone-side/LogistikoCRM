# accounting/services/credentials.py
"""
Helpers για τους κρυπτογραφημένους κωδικούς πελατών (ClientCredential).
"""

from accounting.models import ClientCredential

# Mapping παλιών πεδίων/στηλών Excel -> (service, attribute)
LEGACY_CREDENTIAL_FIELDS = {
    'onoma_xristi_taxisnet': (ClientCredential.Service.TAXISNET, 'username'),
    'kodikos_taxisnet': (ClientCredential.Service.TAXISNET, 'secret'),
    'onoma_xristi_ika_ergodoti': (ClientCredential.Service.EFKA, 'username'),
    'kodikos_ika_ergodoti': (ClientCredential.Service.EFKA, 'secret'),
    'onoma_xristi_gemi': (ClientCredential.Service.GEMI, 'username'),
    'kodikos_gemi': (ClientCredential.Service.GEMI, 'secret'),
}


def extract_legacy_credentials(row_data):
    """
    Αφαιρεί (pop) τα παλιά credential πεδία από ένα dict δεδομένων import
    και τα επιστρέφει ομαδοποιημένα ανά service:
    {service: {'username': ..., 'secret': ...}}
    """
    grouped = {}
    for field, (service, attr) in LEGACY_CREDENTIAL_FIELDS.items():
        value = row_data.pop(field, None)
        if value:
            grouped.setdefault(service, {})[attr] = str(value)
    return grouped


def store_client_credentials(client, grouped, updated_by=None):
    """
    Αποθηκεύει credentials ενός πελάτη (κρυπτογραφημένα).

    grouped: {service: {'username': ..., 'secret': ...}}
    """
    count = 0
    for service, values in grouped.items():
        cred, _ = ClientCredential.objects.get_or_create(
            client=client, service=service, label='',
        )
        if 'username' in values:
            cred.username = values['username']
        if 'secret' in values:
            cred.secret = values['secret']
        cred.updated_by = updated_by
        cred.save()
        count += 1
    return count
