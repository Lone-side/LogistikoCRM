# Ξεχωριστό permission για μαζική εξαγωγή προσωπικών δεδομένων πελατών —
# το view_clientprofile από μόνο του δεν επιτρέπει πλέον bulk export.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "10018_send_client_email_permission"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="clientprofile",
            options={
                "permissions": [
                    ("view_all_clients", "Πρόσβαση σε όλους τους πελάτες ανεξαρτήτως ανάθεσης"),
                    ("send_client_email", "Αποστολή email σε πελάτες"),
                    ("export_clientprofile", "Μαζική εξαγωγή στοιχείων πελατών (Excel/CSV)"),
                ],
                "verbose_name": "Προφίλ Πελάτη",
                "verbose_name_plural": "Προφίλ Πελατών",
            },
        ),
    ]
