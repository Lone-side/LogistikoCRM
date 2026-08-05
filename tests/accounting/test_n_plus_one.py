# -*- coding: utf-8 -*-
"""
Regression tests για N+1 queries: ο αριθμός των queries πρέπει να μένει
σταθερός όταν αυξάνονται οι γραμμές της λίστας.
"""
from django.contrib.auth.models import User
from tests.utils.helpers import grant_accounting_model_perms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounting.models import (
    ClientDocument, ClientObligation, ClientProfile, MonthlyObligation,
    ObligationProfile, ObligationType,
)


def make_clients(n, start=0):
    """Δημιουργεί n πελάτες με obligation settings + έγγραφο ο καθένας."""
    obligation_type = ObligationType.objects.first() or ObligationType.objects.create(
        name='ΦΠΑ', code='FPA', frequency='monthly'
    )
    profile = ObligationProfile.objects.first() or ObligationProfile.objects.create(
        name='Βασικό'
    )
    profile.obligation_types.add(obligation_type)

    for i in range(start, start + n):
        client = ClientProfile.objects.create(
            afm=f'{100000000 + i}', eponimia=f'ΠΕΛΑΤΗΣ {i}'
        )
        # Signal μπορεί να το έχει ήδη δημιουργήσει
        settings_obj, _ = ClientObligation.objects.get_or_create(
            client=client, defaults={'is_active': True}
        )
        settings_obj.is_active = True
        settings_obj.save()
        settings_obj.obligation_types.add(obligation_type)
        settings_obj.obligation_profiles.add(profile)
        ClientDocument.objects.create(
            client=client,
            file=SimpleUploadedFile(f'doc{i}.pdf', b'%PDF-1.4'),
            filename=f'doc{i}.pdf',
        )
        MonthlyObligation.objects.create(
            client=client, obligation_type=obligation_type,
            year=2026, month=7, deadline=timezone.now().date(),
        )


class QueryCountBase(TestCase):
    def _count_queries(self, url):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def assert_flat_queries(self, url, grow):
        """Ο αριθμός queries δεν πρέπει να αυξάνεται με τις γραμμές."""
        baseline = self._count_queries(url)
        grow()
        after = self._count_queries(url)
        self.assertEqual(
            after, baseline,
            f'N+1: {baseline} queries με λίγες γραμμές, {after} με περισσότερες',
        )


class ClientAdminChangelistQueriesTest(QueryCountBase):
    """Το «400+ queries» εύρημα: changelist πελατών στο admin."""

    def setUp(self):
        admin = User.objects.create_superuser('admin', 'a@a.gr', 'x')
        self.client.force_login(admin)
        make_clients(3)

    def test_changelist_query_count_is_flat(self):
        from django.urls import reverse
        self.assert_flat_queries(
            reverse('admin:accounting_clientprofile_changelist'),
            grow=lambda: make_clients(5, start=10),
        )


class DocumentApiListQueriesTest(QueryCountBase):
    """DocumentViewSet list: σταθερά queries ανεξαρτήτως πλήθους εγγράφων."""

    def setUp(self):
        user = grant_accounting_model_perms(User.objects.create_user('tester', password='x', is_staff=True))
        self.client.force_login(user)
        make_clients(3)

    def test_document_list_query_count_is_flat(self):
        self.assert_flat_queries(
            '/accounting/api/v1/documents/',
            grow=lambda: make_clients(5, start=20),
        )
