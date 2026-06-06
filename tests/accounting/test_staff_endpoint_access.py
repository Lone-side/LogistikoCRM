# -*- coding: utf-8 -*-
"""
Access-control regression — staff/management endpoints είναι default-deny για πελάτες
====================================================================================
Κανόνας (CLAUDE.md): κάθε staff/management endpoint ΠΡΕΠΕΙ να απαιτεί IsStaffUser.
Πριν το hardening, μια ομάδα endpoints (obligation profiles, GSIS, obligation
documents, door status) είχε ΜΟΝΟ IsAuthenticated, ώστε κάθε συνδεδεμένος πελάτης
περνούσε — με αποκορύφωμα cross-tenant write (PUT obligation-profile) και GSIS
credential write. Αυτά τα tests κλειδώνουν τη συμπεριφορά: πελάτης → 403, staff → όχι 403.
"""
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import ClientProfile, ClientObligation, ObligationType


class StaffEndpointAccessTest(APITestCase):
    def setUp(self):
        self.client_a = ClientProfile.objects.create(
            afm="123456783", eponimia="Πελάτης Α ΑΕ", eidos_ipoxreou="company"
        )
        self.client_b = ClientProfile.objects.create(
            afm="094160855", eponimia="Πελάτης Β ΑΕ", eidos_ipoxreou="company"
        )
        self.user_a = self.client_a.create_portal_user(password="PassA123!")
        self.staff = User.objects.create_user(
            username="staffer", password="StaffPass123!", is_staff=True
        )
        self.otype = ObligationType.objects.create(
            name="ΦΠΑ", code="VAT", frequency="monthly", deadline_type="last_day"
        )

    # ----- GET endpoints: πελάτης → 403 -----
    def test_client_forbidden_on_management_gets(self):
        self.client.force_authenticate(user=self.user_a)
        staff_only_gets = [
            "/accounting/api/v1/clients/obligation-status/",
            f"/accounting/api/v1/clients/{self.client_b.id}/obligation-profile/",
            "/accounting/api/v1/obligation-types/grouped/",
            "/accounting/api/v1/obligation-profiles/",
            "/accounting/api/v1/gsis/status/",
            "/accounting/api/v1/door/status/",
        ]
        for url in staff_only_gets:
            resp = self.client.get(url)
            self.assertEqual(
                resp.status_code, status.HTTP_403_FORBIDDEN,
                f"{url} → {resp.status_code} (αναμενόταν 403)",
            )

    # ----- POST endpoints: πελάτης → 403 -----
    def test_client_forbidden_on_management_posts(self):
        self.client.force_authenticate(user=self.user_a)
        staff_only_posts = [
            ("/accounting/api/v1/obligations/generate-month/", {"month": 5, "year": 2027}),
            ("/accounting/api/v1/obligations/bulk-assign/",
             {"client_ids": [self.client_b.id], "obligation_type_ids": [self.otype.id]}),
            ("/accounting/api/v1/afm-lookup/", {"afm": "123456789"}),
            ("/accounting/api/v1/gsis/settings/",
             {"afm": "123456789", "username": "x", "password": "y"}),
            ("/accounting/api/v1/gsis/test/", {}),
        ]
        for url, body in staff_only_posts:
            resp = self.client.post(url, body, format="json")
            self.assertEqual(
                resp.status_code, status.HTTP_403_FORBIDDEN,
                f"{url} → {resp.status_code} (αναμενόταν 403)",
            )

    # ----- Ο κρίσιμος IDOR: πελάτης δεν γράφει το profile άλλου πελάτη -----
    def test_client_cannot_write_other_client_obligation_profile(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.put(
            f"/accounting/api/v1/clients/{self.client_b.id}/obligation-profile/",
            {"obligation_type_ids": [self.otype.id], "obligation_profile_ids": []},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # Το προφίλ του client_b δεν τροποποιήθηκε: ο τύπος ΦΠΑ ΔΕΝ προστέθηκε.
        # (ένα signal δημιουργεί κενό ClientObligation στη δημιουργία του πελάτη,
        #  οπότε ελέγχουμε ότι παραμένει χωρίς obligation types — δεν πέρασε το write.)
        cob = ClientObligation.objects.filter(client=self.client_b).first()
        if cob is not None:
            self.assertEqual(cob.obligation_types.count(), 0)

    # ----- Sanity: staff ΔΕΝ παίρνει 403 στα ίδια endpoints -----
    def test_staff_allowed_on_management_endpoints(self):
        self.client.force_authenticate(user=self.staff)
        for url in [
            "/accounting/api/v1/clients/obligation-status/",
            "/accounting/api/v1/obligation-types/grouped/",
            "/accounting/api/v1/obligation-profiles/",
            "/accounting/api/v1/gsis/status/",
        ]:
            resp = self.client.get(url)
            self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN, url)

    # ----- Obligation-document endpoints: πελάτης → 403 -----
    def test_client_forbidden_on_obligation_documents(self):
        from datetime import date
        from accounting.models import MonthlyObligation
        obl_b = MonthlyObligation.objects.create(
            client=self.client_b, obligation_type=self.otype,
            year=2027, month=5, deadline=date(2027, 5, 31),
        )
        self.client.force_authenticate(user=self.user_a)
        # read documents of another client's obligation
        resp = self.client.get(f"/accounting/api/v1/obligations/{obl_b.id}/documents/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # attach to another client's obligation
        resp = self.client.post(
            f"/accounting/api/v1/obligations/{obl_b.id}/attach-document/",
            {"document_id": 1}, format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
