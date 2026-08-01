# accounting/management/commands/setup_roles.py
"""
Δημιουργία/ενημέρωση των βασικών ρόλων (Django groups) του γραφείου.

Idempotent — μπορεί να τρέχει σε κάθε deploy.

Ρόλοι:
- Διαχειριστής: όλα τα accounting permissions + view_all_clients + reveal κωδικών
- Λογιστής: CRUD σε πελάτες/έγγραφα/υποχρεώσεις/κωδικούς (μόνο ανατεθειμένους
  όταν ENFORCE_CLIENT_ASSIGNMENT=True) + reveal κωδικών
- Βοηθός: μόνο ανάγνωση, χωρίς αποκάλυψη κωδικών
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

ROLES = {
    'Διαχειριστής': {
        'app_all': ['accounting'],
        'extra': ['view_all_clients', 'view_client_credential_secret'],
    },
    'Λογιστής': {
        'codenames': [
            'add_clientprofile', 'change_clientprofile', 'view_clientprofile',
            'add_clientdocument', 'change_clientdocument', 'view_clientdocument',
            'delete_clientdocument',
            'add_monthlyobligation', 'change_monthlyobligation', 'view_monthlyobligation',
            'add_clientcredential', 'change_clientcredential', 'view_clientcredential',
            'view_client_credential_secret',
        ],
    },
    'Βοηθός': {
        'codenames': [
            'view_clientprofile', 'view_clientdocument',
            'view_monthlyobligation', 'view_clientcredential',
        ],
    },
}


class Command(BaseCommand):
    help = "Δημιουργεί/ενημερώνει τους βασικούς ρόλους (groups) του γραφείου"

    def handle(self, *args, **options):
        for role_name, spec in ROLES.items():
            group, created = Group.objects.get_or_create(name=role_name)
            perms = Permission.objects.none()

            if 'app_all' in spec:
                perms = Permission.objects.filter(
                    content_type__app_label__in=spec['app_all']
                )
            if 'codenames' in spec:
                perms = Permission.objects.filter(codename__in=spec['codenames'])
            if 'extra' in spec:
                perms = perms | Permission.objects.filter(codename__in=spec['extra'])

            group.permissions.set(perms.distinct())
            verb = 'Δημιουργήθηκε' if created else 'Ενημερώθηκε'
            self.stdout.write(self.style.SUCCESS(
                f"{verb} ρόλος «{role_name}» με {group.permissions.count()} permissions"
            ))

        self.stdout.write(
            "Ανάθεσε χρήστες στους ρόλους από το admin (Χρήστες → Groups) "
            "και πελάτες σε χρήστες (Προφίλ Πελάτη → Ανάθεση)."
        )
