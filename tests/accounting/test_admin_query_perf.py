# -*- coding: utf-8 -*-
"""
Admin changelist query-performance regression
==============================================
Κλειδώνει τις βελτιστοποιήσεις get_queryset/select_related/prefetch των admin:
- ClientProfileAdmin: το documents_count διαβάζει το annotation _documents_count
  (όχι query/γραμμή) και επιστρέφει σωστή τιμή.
- Το changelist queryset για N πελάτες δεν κάνει N+1 (σταθερό πλήθος queries).

Δεν κάνει render template (αποφυγή του Python 3.14 test-client template bug) —
δουλεύει απευθείας στο queryset/methods του admin.
"""
from datetime import date

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from accounting.admin.clients import ClientProfileAdmin
from accounting.models import (
    ClientProfile, ClientDocument, MonthlyObligation, ObligationType,
)


class ClientProfileAdminQueryTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="staff", password="x", is_staff=True, is_superuser=True
        )
        otype = ObligationType.objects.create(
            name="ΦΠΑ", code="VAT", frequency="monthly", deadline_type="last_day"
        )
        # Τρεις πελάτες· ο πρώτος με 2 έγγραφα, οι άλλοι χωρίς.
        for i, afm in enumerate(["123456783", "094160855", "111111114"]):
            c = ClientProfile.objects.create(
                afm=afm, eponimia=f"Πελάτης {i}", eidos_ipoxreou="company"
            )
            MonthlyObligation.objects.create(
                client=c, obligation_type=otype, year=2027, month=i + 1,
                deadline=date(2027, i + 1, 28),
            )
            if i == 0:
                cls.client_with_docs = c
                for n in range(2):
                    ClientDocument.objects.create(
                        client=c, document_category="general",
                        file=f"clients/doc_{n}.pdf",
                    )

    def _admin(self):
        ma = ClientProfileAdmin(ClientProfile, AdminSite())
        request = RequestFactory().get("/admin/accounting/clientprofile/")
        request.user = self.staff
        return ma, request

    def test_documents_count_uses_annotation_value(self):
        ma, request = self._admin()
        qs = ma.get_queryset(request)
        obj = qs.get(pk=self.client_with_docs.pk)
        # Το annotation υπάρχει και είναι σωστό.
        self.assertEqual(obj._documents_count, 2)
        # Το display method δεν κάνει επιπλέον query και δείχνει το 2.
        with self.assertNumQueries(0):
            html = ma.documents_count(obj)
        self.assertIn("2", str(html))

    def test_changelist_queryset_is_not_n_plus_1(self):
        ma, request = self._admin()
        qs = ma.get_queryset(request)
        # Υλοποίηση όλων των rows + κλήση των display methods που "ακουμπούν"
        # related δεδομένα. Με select_related (user, obligation_settings) +
        # annotate (_documents_count) η βασική γραμμή είναι 1 query· τα prefetch
        # του M2M προσθέτουν σταθερό μικρό πλήθος (obligation_types, profiles),
        # ΑΝΕΞΑΡΤΗΤΑ από το πλήθος πελατών — όχι ~3*N.
        with self.assertNumQueries(3):
            rows = list(qs)
            for obj in rows:
                ma.documents_count(obj)
                ma.obligations_status(obj)
                ma.portal_status(obj)
        self.assertEqual(len(rows), 3)
