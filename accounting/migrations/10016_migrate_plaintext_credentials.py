# Data migration: μεταφορά plaintext κωδικών ClientProfile -> ClientCredential
# (κρυπτογραφημένοι με Fernet). Reverse = no-op (ποτέ ξανά plaintext).

from django.db import migrations

# (πεδίο username, πεδίο κωδικού, service)
LEGACY_FIELDS = [
    ('onoma_xristi_taxisnet', 'kodikos_taxisnet', 'TAXISNET'),
    ('onoma_xristi_ika_ergodoti', 'kodikos_ika_ergodoti', 'EFKA'),
    ('onoma_xristi_gemi', 'kodikos_gemi', 'GEMI'),
]


def migrate_credentials(apps, schema_editor):
    from mydata.encryption import encrypt_value

    ClientProfile = apps.get_model('accounting', 'ClientProfile')
    ClientCredential = apps.get_model('accounting', 'ClientCredential')

    to_create = []
    for client in ClientProfile.objects.all().iterator():
        for username_field, secret_field, service in LEGACY_FIELDS:
            username = (getattr(client, username_field, '') or '').strip()
            secret = (getattr(client, secret_field, '') or '').strip()
            if not username and not secret:
                continue
            to_create.append(ClientCredential(
                client=client,
                service=service,
                label='',
                username=username,
                _secret_encrypted=encrypt_value(secret) if secret else '',
            ))
    if to_create:
        ClientCredential.objects.bulk_create(to_create)


def reverse_noop(apps, schema_editor):
    # Δεν επαναφέρουμε ποτέ plaintext κωδικούς.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "10015_clientcredential_assigned_users"),
    ]

    operations = [
        migrations.RunPython(migrate_credentials, reverse_noop),
    ]
