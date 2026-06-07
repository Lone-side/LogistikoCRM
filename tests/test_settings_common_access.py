# -*- coding: utf-8 -*-
"""
Access-control regression — settings & common management endpoints
==================================================================
Audit στα μέχρι πρότινος μη-ελεγμένα apps βρήκε management endpoints με
IsAuthenticated/login_required (όχι IsStaffUser/staff) → προσβάσιμα από πελάτες,
με αποκορύφωμα cross-tenant AFM leak (FolderStructurePreview) και destructive
user_transfer. Τα tests κλειδώνουν: πελάτης → ΟΧΙ 200· staff → επιτρέπεται.
"""
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounting.models import ClientProfile
from accounting.permissions import IsStaffUser
from settings.api import (
    FilingSystemSettingsView, FolderStructurePreviewView, DocumentCategoriesView,
)
from settings.api_views import (
    BackupSettingsAPIView, BackupListAPIView, BackupCreateAPIView,
    BackupDownloadAPIView, BackupRestoreAPIView, BackupUploadRestoreAPIView,
)


class SettingsApiPermissionTest(APITestCase):
    def test_all_settings_api_views_require_staff(self):
        views = [
            FilingSystemSettingsView, FolderStructurePreviewView, DocumentCategoriesView,
            BackupSettingsAPIView, BackupListAPIView, BackupCreateAPIView,
            BackupDownloadAPIView, BackupRestoreAPIView, BackupUploadRestoreAPIView,
        ]
        for cls in views:
            self.assertIn(IsStaffUser, cls.permission_classes, f'{cls.__name__} χωρίς IsStaffUser')


class SettingsApiClientForbiddenTest(APITestCase):
    def setUp(self):
        self.cp = ClientProfile.objects.create(
            afm='123456783', eponimia='Πελάτης Α', eidos_ipoxreou='company'
        )
        self.user = self.cp.create_portal_user(password='PassA123!')
        self.staff = User.objects.create_user('staff', password='x', is_staff=True, is_superuser=True)

    def test_client_forbidden_folder_preview_idor(self):
        # Το πιο σοβαρό: ο πελάτης ζητούσε client_id άλλου και έπαιρνε ΑΦΜ+επωνυμία.
        self.client.force_authenticate(self.user)
        resp = self.client.get(reverse('settings:folder_preview_api'), {'client_id': self.cp.id})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_client_forbidden_backup_list_and_filing(self):
        self.client.force_authenticate(self.user)
        for name in ('settings:backup_list_api', 'settings:backup_settings_api', 'settings:filing_settings_api'):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN, name)

    def test_staff_allowed(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.get(reverse('settings:folder_preview_api'))
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class CommonManagementUrlsStaffGatedTest(APITestCase):
    """Τα user_transfer/copy_department/debug/toggle-default-sorting είναι staff-gated."""

    def setUp(self):
        self.cp = ClientProfile.objects.create(
            afm='094160855', eponimia='Πελάτης Β', eidos_ipoxreou='company'
        )
        self.user = self.cp.create_portal_user(password='PassB123!')

    def test_client_cannot_reach_management_views(self):
        # staff_member_required → non-staff παίρνει redirect στο login (302), όχι 200.
        self.client.force_login(self.user)
        for name in ('user_transfer', 'copy_department', 'toggle_default_sorting'):
            resp = self.client.get(reverse(name))
            self.assertNotEqual(resp.status_code, status.HTTP_200_OK, name)
