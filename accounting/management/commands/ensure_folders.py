# -*- coding: utf-8 -*-
"""
Δημιουργία δέντρου φακέλων αρχειοθέτησης για όλους τους ενεργούς πελάτες.

Χρήση:
    python manage.py ensure_folders               # τρέχον έτος
    python manage.py ensure_folders --year 2027   # συγκεκριμένο έτος
    python manage.py ensure_folders --afm 123456789  # μόνο ένας πελάτης
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounting.models import ClientProfile
from accounting.services import filing


class Command(BaseCommand):
    help = 'Δημιουργεί (idempotent) τους φακέλους αρχειοθέτησης πελατών για ένα έτος'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Έτος (default: τρέχον)')
        parser.add_argument('--afm', type=str, help='Μόνο για τον πελάτη με αυτό το ΑΦΜ')

    def handle(self, *args, **options):
        year = options['year'] or timezone.now().year

        clients = ClientProfile.objects.filter(is_active=True)
        if options['afm']:
            clients = clients.filter(afm=options['afm'])
            if not clients.exists():
                raise CommandError(f"Δεν βρέθηκε ενεργός πελάτης με ΑΦΜ {options['afm']}")

        ok = 0
        failed = 0
        for client in clients:
            path = filing.ensure_folders(client, year=year)
            if path:
                ok += 1
                self.stdout.write(f"✅ {client.afm} {client.eponimia} → {path}")
            else:
                failed += 1
                self.stderr.write(f"❌ {client.afm} {client.eponimia}")

        self.stdout.write(self.style.SUCCESS(
            f"Έτος {year}: {ok} πελάτες OK" + (f", {failed} αποτυχίες" if failed else "")
        ))
