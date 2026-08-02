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
        'app_all': ['accounting', 'mydata', 'inventory'],
        'extra': ['view_all_clients', 'view_client_credential_secret'],
    },
    'Λογιστής': {
        'codenames': [
            'add_clientprofile', 'change_clientprofile', 'view_clientprofile',
            'add_clientdocument', 'change_clientdocument', 'view_clientdocument',
            'delete_clientdocument',
            'add_monthlyobligation', 'change_monthlyobligation', 'view_monthlyobligation',
            'delete_monthlyobligation',
            'add_clientcredential', 'change_clientcredential', 'view_clientcredential',
            'delete_clientcredential',
            'view_client_credential_secret',
            # Υποχρεώσεις: προφίλ/τύποι/αναθέσεις
            'view_obligationprofile', 'view_obligationtype', 'view_obligationgroup',
            'add_clientobligation', 'change_clientobligation', 'view_clientobligation',
            # Email: templates + αποστολή σε πελάτες
            'add_emailtemplate', 'change_emailtemplate', 'view_emailtemplate',
            'view_emaillog', 'send_client_email',
            # Shared links / αιτήματα εγγράφων / tickets / VoIP
            'add_sharedlink', 'change_sharedlink', 'view_sharedlink', 'delete_sharedlink',
            'add_documenttag', 'change_documenttag', 'view_documenttag', 'delete_documenttag',
            'add_documentrequest', 'change_documentrequest', 'view_documentrequest',
            'delete_documentrequest',
            'add_ticket', 'change_ticket', 'view_ticket', 'delete_ticket',
            'add_voipcall', 'change_voipcall', 'view_voipcall', 'view_voipcalllog',
            # myDATA
            'add_mydatacredentials', 'change_mydatacredentials', 'view_mydatacredentials',
            'delete_mydatacredentials',
            'view_vatrecord', 'view_vatsynclog',
            'add_vatperiodresult', 'change_vatperiodresult', 'view_vatperiodresult',
        ],
    },
    'Βοηθός': {
        'codenames': [
            'view_clientprofile', 'view_clientdocument',
            'view_monthlyobligation', 'view_clientcredential',
            'view_obligationprofile', 'view_obligationtype', 'view_obligationgroup',
            'view_clientobligation',
            'view_emailtemplate', 'view_emaillog',
            'view_sharedlink', 'view_documentrequest', 'view_documenttag',
            'view_ticket', 'view_voipcall', 'view_voipcalllog',
            'view_mydatacredentials', 'view_vatrecord', 'view_vatsynclog',
            'view_vatperiodresult',
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
