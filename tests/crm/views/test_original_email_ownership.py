# -*- coding: utf-8 -*-
"""
Regression tests για το P1-1: ownership στα original-email endpoints.

Πριν το fix, τα `view_original_email` / `download_original_email` ήταν
προστατευμένα ΜΟΝΟ με `staff_member_required`: το `ea_id`/`uid` (ή το
`object_id` ενός ξένου CrmEmail) περνούσαν κατευθείαν σε
`EmailAccount.objects.get(...)` και ακολουθούσε IMAP fetch — δηλαδή κάθε
staff χρήστης μπορούσε να διαβάσει/κατεβάσει το mailbox άλλου χρήστη.

Τα tests χρησιμοποιούν πραγματικά Django HTTP requests με **mocked IMAP
backend** (`get_crmimap`) ώστε να αποδεικνύεται ότι σε απόρριψη ΔΕΝ γίνεται
καμία σύνδεση/ανάκτηση IMAP.

python manage.py test tests.crm.views.test_original_email_ownership
"""
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test import tag
from django.urls import reverse

from common.utils.helpers import USER_MODEL
from crm.models import CrmEmail
from massmail.models import EmailAccount
from tests.base_test_classes import BaseTestCase

GLOBAL_SALES = 9      # common/fixtures/groups.json
BOOKKEEPING = 11

RAW_EML = (
    b"From: sender@example.com\r\n"
    b"To: owner@example.com\r\n"
    b"Subject: SECRET-SUBJECT-DO-NOT-LEAK\r\n"
    b"Message-ID: <mid-owner@example.com>\r\n"
    b"Date: Mon, 1 Jun 2026 10:00:00 +0000\r\n"
    b"\r\n"
    b"SECRET-BODY-DO-NOT-LEAK\r\n"
)


def _imap_ok_mock(uid: int):
    """MagicMock CrmIMAP που επιστρέφει έγκυρο μήνυμα για το δοσμένο uid."""
    from unittest.mock import MagicMock
    crmimap = MagicMock()
    crmimap.error = None
    data = [(f"1 (UID {uid} BODY[] ".encode() + b"{100}", RAW_EML), b")"]
    crmimap.uid_fetch.return_value = ('OK', data, '')
    return crmimap


@tag('TestCase')
class OriginalEmailOwnershipTest(BaseTestCase):
    """Ο έλεγχος ιδιοκτησίας mailbox γίνεται ΠΡΙΝ από κάθε IMAP πρόσβαση."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner = USER_MODEL.objects.get(username="Andrew.Manager.Global")
        # Ίδιο department με τον owner — αποδεικνύει ότι το department
        # ΑΠΟ ΜΟΝΟ ΤΟΥ δεν παραχωρεί πρόσβαση (είναι περιοριστικό, όχι
        # παραχωρητικό, σύμφωνα με select_emails_import.py).
        cls.same_dept_stranger = USER_MODEL.objects.get(
            username="Marina.Co-worker.Global")
        cls.other_dept_stranger = USER_MODEL.objects.get(
            username="Masha.Co-worker.Bookkeeping")
        cls.superuser = USER_MODEL.objects.get(username="Adam.Admin")

        global_sales = Group.objects.get(pk=GLOBAL_SALES)
        cls.ea = EmailAccount.objects.create(
            name="Owner mailbox",
            email_host="smtp.example.com",
            imap_host="imap.example.com",
            email_host_user="owner@example.com",
            email_host_password="x",
            email_port=465,
            from_email="owner@example.com",
            owner=cls.owner,
            department=global_sales,
            main=True,
        )
        cls.eml = CrmEmail.objects.create(
            subject="SECRET-SUBJECT-DO-NOT-LEAK",
            content="SECRET-BODY-DO-NOT-LEAK",
            uid=42,
            imap_host="imap.example.com",
            email_host_user="owner@example.com",
            message_id="<mid-owner@example.com>",
            incoming=True,
            owner=cls.owner,
            department=global_sales,
        )

    def setUp(self):
        print("Run Test Method:", self._testMethodName)
        self.view_url = reverse('view_original_email', args=(self.eml.id,))
        self.view_uid_url = reverse(
            'view_original_email_uid', args=(self.ea.id, 42))
        self.download_url = reverse(
            'download_original_email', args=(self.eml.id,))

    def _assert_no_leak(self, response):
        body = response.content.decode('utf-8', 'replace')
        for secret in ("SECRET-SUBJECT-DO-NOT-LEAK", "SECRET-BODY-DO-NOT-LEAK",
                       "owner@example.com", "imap.example.com",
                       "Owner mailbox"):
            self.assertNotIn(secret, body, f"LEAK: «{secret}» στην απόκριση")

    # ------------------------------------------------------------------
    # 1. Owner — νόμιμη πρόσβαση
    # ------------------------------------------------------------------
    def test_owner_can_view_own_email(self):
        self.client.force_login(self.owner)
        with patch('crm.views.view_original_email.get_crmimap') as gci:
            gci.return_value = _imap_ok_mock(42)
            response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200, response.reason_phrase)
        gci.assert_called_once()
        self.assertEqual(gci.call_args[0][0].pk, self.ea.pk)

    def test_owner_can_view_own_mailbox_by_ea_id_uid(self):
        self.client.force_login(self.owner)
        with patch('crm.views.view_original_email.get_crmimap') as gci:
            gci.return_value = _imap_ok_mock(42)
            response = self.client.get(self.view_uid_url)
        self.assertEqual(response.status_code, 200, response.reason_phrase)
        gci.assert_called_once()

    def test_owner_can_download_own_email(self):
        self.client.force_login(self.owner)
        with patch('crm.views.download_original_email.get_crmimap') as gci:
            crmimap = _imap_ok_mock(42)
            crmimap.uid_fetch.return_value = ('OK', [(b'1 (UID 42', RAW_EML)], '')
            gci.return_value = crmimap
            response = self.client.get(self.download_url)
        self.assertEqual(response.status_code, 200, response.reason_phrase)
        self.assertEqual(response['Content-Type'], 'message/rfc822')
        gci.assert_called_once()

    # ------------------------------------------------------------------
    # 2. Ξένος staff χρήστης — άρνηση ΧΩΡΙΣ IMAP
    # ------------------------------------------------------------------
    def test_stranger_cannot_view_foreign_email(self):
        for user in (self.same_dept_stranger, self.other_dept_stranger):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                with patch('crm.views.view_original_email.get_crmimap') as gci:
                    response = self.client.get(self.view_url)
                self.assertEqual(response.status_code, 404, response.reason_phrase)
                gci.assert_not_called()          # καμία IMAP σύνδεση
                self._assert_no_leak(response)

    def test_stranger_cannot_view_foreign_mailbox_by_ea_id(self):
        self.client.force_login(self.other_dept_stranger)
        with patch('crm.views.view_original_email.get_crmimap') as gci:
            response = self.client.get(self.view_uid_url)
        self.assertEqual(response.status_code, 404, response.reason_phrase)
        gci.assert_not_called()
        self._assert_no_leak(response)

    def test_stranger_cannot_download_foreign_email(self):
        for user in (self.same_dept_stranger, self.other_dept_stranger):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                with patch('crm.views.download_original_email.get_crmimap') as gci:
                    response = self.client.get(self.download_url)
                self.assertEqual(response.status_code, 404, response.reason_phrase)
                gci.assert_not_called()
                self._assert_no_leak(response)

    # ------------------------------------------------------------------
    # 3. Ανύπαρκτο account/email — ίδια εξωτερική συμπεριφορά
    # ------------------------------------------------------------------
    def test_nonexistent_account_same_as_foreign(self):
        self.client.force_login(self.other_dept_stranger)
        missing_url = reverse('view_original_email_uid', args=(99999, 42))
        with patch('crm.views.view_original_email.get_crmimap') as gci:
            missing = self.client.get(missing_url)
            foreign = self.client.get(self.view_uid_url)
        self.assertEqual(missing.status_code, foreign.status_code)
        self.assertEqual(missing.status_code, 404)
        gci.assert_not_called()

    def test_nonexistent_email_same_as_foreign(self):
        self.client.force_login(self.other_dept_stranger)
        missing_url = reverse('download_original_email', args=(99999,))
        with patch('crm.views.download_original_email.get_crmimap') as gci:
            missing = self.client.get(missing_url)
            foreign = self.client.get(self.download_url)
        self.assertEqual(missing.status_code, foreign.status_code)
        self.assertEqual(missing.status_code, 404)
        gci.assert_not_called()

    # ------------------------------------------------------------------
    # 4. Άκυρο/ξένο UID — απόρριψη χωρίς data leak
    # ------------------------------------------------------------------
    def test_foreign_uid_on_foreign_account_rejected(self):
        """Ξένο account + αυθαίρετο uid: άρνηση πριν καν κοιταχτεί το uid."""
        self.client.force_login(self.other_dept_stranger)
        for uid in (1, 42, 999999):
            with self.subTest(uid=uid):
                url = reverse('view_original_email_uid', args=(self.ea.id, uid))
                with patch('crm.views.view_original_email.get_crmimap') as gci:
                    response = self.client.get(url)
                self.assertEqual(response.status_code, 404)
                gci.assert_not_called()
                self._assert_no_leak(response)

    def test_invalid_uid_on_own_account_no_leak(self):
        """Δικό μου account, uid που δεν επιστρέφει μήνυμα: καθαρό error."""
        self.client.force_login(self.owner)
        url = reverse('view_original_email_uid', args=(self.ea.id, 777))
        from unittest.mock import MagicMock
        with patch('crm.views.view_original_email.get_crmimap') as gci:
            crmimap = MagicMock()
            crmimap.error = None
            crmimap.uid_fetch.return_value = ('NO', [None], '')
            gci.return_value = crmimap
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8', 'replace')
        self.assertIn('Error', body)
        self.assertNotIn("SECRET-BODY-DO-NOT-LEAK", body)

    # ------------------------------------------------------------------
    # 5. Superuser — διατήρηση νόμιμης πρόσβασης
    # ------------------------------------------------------------------
    def test_superuser_keeps_access(self):
        self.client.force_login(self.superuser)
        with patch('crm.views.view_original_email.get_crmimap') as gci:
            gci.return_value = _imap_ok_mock(42)
            response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200, response.reason_phrase)
        gci.assert_called_once()

    # ------------------------------------------------------------------
    # 6. Shared account: co_owner κατά την πραγματική πολιτική
    # ------------------------------------------------------------------
    def test_co_owner_has_access(self):
        """co_owner είναι το πεδίο shared πρόσβασης του EmailAccount."""
        self.ea.co_owner = self.same_dept_stranger
        self.ea.save(update_fields=['co_owner'])
        self.client.force_login(self.same_dept_stranger)
        with patch('crm.views.view_original_email.get_crmimap') as gci:
            gci.return_value = _imap_ok_mock(42)
            response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 200, response.reason_phrase)
        gci.assert_called_once()

    def test_co_owner_of_other_department_still_denied_when_scoped(self):
        """
        Το department λειτουργεί περιοριστικά: co_owner άλλου department
        δεν αποκτά πρόσβαση όσο είναι κλειδωμένος στο δικό του department
        (ίδια λογική με select_emails_import.py).
        """
        self.ea.co_owner = self.other_dept_stranger
        self.ea.save(update_fields=['co_owner'])
        self.client.force_login(self.other_dept_stranger)
        session = self.client.session
        session['department_id'] = BOOKKEEPING
        session.save()
        with patch('crm.views.view_original_email.get_crmimap') as gci:
            response = self.client.get(self.view_url)
        self.assertEqual(response.status_code, 404, response.reason_phrase)
        gci.assert_not_called()


@tag('TestCase')
class OriginalEmailPreFixRegressionTest(BaseTestCase):
    """
    Αποδεικνύει τη ΔΙΑΦΟΡΑ πριν/μετά το fix.

    Καλεί απευθείας τον resolver `get_ea_eml_uid` (α) με τη ΔΙΟΡΘΩΜΕΝΗ
    λογική → Http404 πριν από κάθε IMAP, και (β) με την ΠΑΛΙΑ, unscoped
    λογική (αναπαράσταση του pre-fix κώδικα) → επιστρέφει το ξένο
    EmailAccount, δηλαδή ο κώδικας θα προχωρούσε σε IMAP fetch.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner = USER_MODEL.objects.get(username="Andrew.Manager.Global")
        cls.stranger = USER_MODEL.objects.get(
            username="Masha.Co-worker.Bookkeeping")
        cls.ea = EmailAccount.objects.create(
            name="Owner mailbox", email_host="smtp.example.com",
            imap_host="imap.example.com", email_host_user="owner@example.com",
            email_host_password="x", email_port=465,
            from_email="owner@example.com", owner=cls.owner,
            department=Group.objects.get(pk=GLOBAL_SALES), main=True,
        )

    def setUp(self):
        print("Run Test Method:", self._testMethodName)

    def test_pre_fix_logic_would_reach_foreign_account(self):
        """ΠΡΙΝ το fix: unscoped lookup επέστρεφε το ξένο account."""
        pre_fix_ea = EmailAccount.objects.filter(id=self.ea.id).first()
        self.assertIsNotNone(
            pre_fix_ea,
            'Η παλιά (unscoped) λογική έβρισκε το ξένο account — ο κώδικας '
            'θα προχωρούσε σε IMAP fetch για λογαριασμό ξένου χρήστη.')
        self.assertEqual(pre_fix_ea.pk, self.ea.pk)

    def test_post_fix_logic_denies_same_lookup(self):
        """ΜΕΤΑ το fix: ο ίδιος χρήστης/lookup δίνει Http404."""
        from django.http import Http404
        from crm.views.view_original_email import get_ea_eml_uid
        with self.assertRaises(Http404):
            get_ea_eml_uid(self.stranger, None, self.ea.id, 42)

    def test_post_fix_owner_still_resolves(self):
        from crm.views.view_original_email import get_ea_eml_uid
        ea, eml, uid, err = get_ea_eml_uid(self.owner, None, self.ea.id, 42)
        self.assertEqual(ea.pk, self.ea.pk)
        self.assertFalse(err)
