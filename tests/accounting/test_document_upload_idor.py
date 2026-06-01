# -*- coding: utf-8 -*-
"""
SECURITY: the staff DocumentViewSet.upload @action must NOT be reachable by a
client user.

The custom @action bypasses ClientScopedQuerysetMixin's create/update/destroy
write-guard, so before the fix a client could POST /api/v1/documents/upload/
with client_id=<any> and upload documents into another client's folder (IDOR +
mass-assignment). Clients have their own scoped endpoint
(/api/client/me/documents/upload/) which forces their own client.

APIRequestFactory used to avoid the Py3.14 test-client HTML-error issue.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate
from django.core.files.uploadedfile import SimpleUploadedFile

from accounting.models import ClientProfile, ClientDocument
from accounting.api_documents import DocumentViewSet


class DocumentUploadIDORTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.upload_view = DocumentViewSet.as_view({'post': 'upload'})
        self.attacker_client = ClientProfile.objects.create(
            afm='123456783', eponimia='Α', eidos_ipoxreou='company')
        self.attacker = self.attacker_client.create_portal_user(password='x')
        self.victim = ClientProfile.objects.create(
            afm='094160855', eponimia='ΘΥΜΑ', eidos_ipoxreou='company')
        self.staff = User.objects.create_user(username='staff', password='x', is_staff=True)

    def _pdf(self):
        return SimpleUploadedFile('x.pdf', b'%PDF-1.4', content_type='application/pdf')

    def test_client_cannot_use_staff_upload_for_another_client(self):
        req = self.factory.post('/api/v1/documents/upload/', {
            'file': self._pdf(),
            'client_id': self.victim.id,  # spoof target
            'document_category': 'general',
        }, format='multipart')
        force_authenticate(req, user=self.attacker)
        resp = self.upload_view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        # Nothing written for the victim.
        self.assertFalse(ClientDocument.objects.filter(client=self.victim).exists())

    def test_client_cannot_use_staff_upload_even_for_self(self):
        # The staff bulk-upload tool is staff-only; clients use /me/ endpoint.
        req = self.factory.post('/api/v1/documents/upload/', {
            'file': self._pdf(),
            'client_id': self.attacker_client.id,
            'document_category': 'general',
        }, format='multipart')
        force_authenticate(req, user=self.attacker)
        resp = self.upload_view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_still_upload(self):
        req = self.factory.post('/api/v1/documents/upload/', {
            'file': self._pdf(),
            'client_id': self.victim.id,
            'document_category': 'general',
        }, format='multipart')
        force_authenticate(req, user=self.staff)
        resp = self.upload_view(req)
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        self.assertTrue(ClientDocument.objects.filter(client=self.victim).exists())
