"""
Καθαρίζει τα παλιά VATRecord rows ώστε το επόμενο sync να ξαναχτίσει
τις εγγραφές με τα νέα πεδία (income_code, expense_category).

Λόγος: Πριν τα 0004/0005 migrations, οι VATRecord είχαν empty
income_code/expense_category. Το νέο parsing του mydata/client.py
δημιουργεί ξεχωριστές γραμμές ανά κωδικό ΑΑΔΕ. Επειδή το
update_or_create κλειδώνει σε (client, mark, expense_category, income_code),
οι παλιές γραμμές με empty codes δεν θα αντιστοιχιστούν με τις νέες
και θα παραμείνουν ως ορφανά duplicates — με αποτέλεσμα να διπλασιάζονται
τα αθροίσματα στο VATPeriodResult.calculate_from_records.

Η ασφαλέστερη επιδιόρθωση: σβήνουμε όλα τα VATRecord και κάνουμε
full re-sync από το myDATA (το AADE έχει το source of truth).
Επίσης μηδενίζουμε το last_calculated_at των VATPeriodResult που
δεν είναι κλειδωμένα ώστε να ξαναϋπολογιστούν.
"""

from django.db import migrations


def clear_vat_records(apps, schema_editor):
    VATRecord = apps.get_model('mydata', 'VATRecord')
    VATPeriodResult = apps.get_model('mydata', 'VATPeriodResult')

    VATRecord.objects.all().delete()

    VATPeriodResult.objects.filter(is_locked=False).update(last_calculated_at=None)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("mydata", "0005_alter_vatrecord_unique_together_and_more"),
    ]

    operations = [
        migrations.RunPython(clear_vat_records, reverse_noop),
    ]
