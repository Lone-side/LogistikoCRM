# accounting/api_credentials.py
"""
API κωδικών πελατών (ClientCredential).

Αρχές:
- Το secret ΔΕΝ επιστρέφεται ποτέ σε list/retrieve — μόνο masked ένδειξη.
- Αποκάλυψη μόνο μέσω POST /reveal/ με permission
  accounting.view_client_credential_secret και υποχρεωτικό AuditLog.
- Όλες οι αλλαγές καταγράφονται στο AuditLog (χωρίς τιμές).
"""

from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.models import AuditLog

from .mixins import ClientScopedQuerysetMixin
from .models import ClientCredential, ClientProfile
from .permissions import CanAccessClient


class ClientCredentialSerializer(serializers.ModelSerializer):
    """Serializer κωδικών — το secret είναι write-only, ποτέ στο response."""

    secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        style={'input_type': 'password'},
    )
    has_secret = serializers.BooleanField(read_only=True)
    secret_masked = serializers.SerializerMethodField()
    service_display = serializers.CharField(source='get_service_display', read_only=True)
    updated_by_name = serializers.CharField(
        source='updated_by.username', read_only=True, default=None,
    )

    class Meta:
        model = ClientCredential
        fields = [
            'id', 'service', 'service_display', 'label', 'username',
            'secret', 'secret_masked', 'has_secret',
            'created_at', 'updated_at', 'updated_by_name',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_secret_masked(self, obj):
        return '••••••••' if obj.has_secret else ''

    def create(self, validated_data):
        secret = validated_data.pop('secret', None)
        instance = ClientCredential(**validated_data)
        if secret:
            instance.secret = secret
        instance.save()
        return instance

    def update(self, instance, validated_data):
        secret = validated_data.pop('secret', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if secret is not None:
            # Κενό string = καθαρισμός κωδικού, μη-κενό = νέος κωδικός
            instance.secret = secret or None
        instance.save()
        return instance


class ClientCredentialViewSet(ClientScopedQuerysetMixin, viewsets.ModelViewSet):
    """
    Nested endpoint: /api/v1/clients/{client_pk}/credentials/

    - list/retrieve: masked (ποτέ το secret)
    - create/update/delete: με audit log
    - POST {id}/reveal/: αποκάλυψη secret με ειδικό permission + audit
    """

    serializer_class = ClientCredentialSerializer
    permission_classes = [IsAuthenticated, CanAccessClient]
    client_field = 'client__assigned_users'
    pagination_class = None

    def get_queryset(self):
        # Το queryset attribute λείπει επίτηδες — πάντα scoped στον πελάτη του URL
        self.queryset = ClientCredential.objects.filter(
            client_id=self.kwargs['client_pk']
        ).select_related('updated_by')
        return super().get_queryset()

    def _get_client(self):
        from django.shortcuts import get_object_or_404
        client = get_object_or_404(ClientProfile, pk=self.kwargs['client_pk'])
        self.check_object_permissions(self.request, client)
        return client

    def perform_create(self, serializer):
        client = self._get_client()
        instance = serializer.save(client=client, updated_by=self.request.user)
        AuditLog.log(
            user=self.request.user, action='create', obj=instance,
            changes={'service': instance.service,
                     'secret_set': instance.has_secret},
            description='Δημιουργία κωδικού πελάτη',
            severity='medium', request=self.request,
        )

    def perform_update(self, serializer):
        secret_changed = 'secret' in serializer.validated_data
        instance = serializer.save(updated_by=self.request.user)
        AuditLog.log(
            user=self.request.user, action='update', obj=instance,
            changes={'service': instance.service,
                     'secret_changed': secret_changed},
            description='Ενημέρωση κωδικού πελάτη',
            severity='medium', request=self.request,
        )

    def perform_destroy(self, instance):
        AuditLog.log(
            user=self.request.user, action='delete', obj=instance,
            changes={'service': instance.service},
            description='Διαγραφή κωδικού πελάτη',
            severity='high', request=self.request,
        )
        instance.delete()

    @action(detail=True, methods=['post'])
    def reveal(self, request, client_pk=None, pk=None):
        """Αποκάλυψη secret — απαιτεί ειδικό permission, πάντα με audit."""
        if not request.user.has_perm('accounting.view_client_credential_secret'):
            AuditLog.log(
                user=request.user, action='permission_denied',
                description=f'Απόπειρα αποκάλυψης κωδικού (credential {pk})',
                severity='high', request=request,
            )
            return Response(
                {'detail': 'Δεν έχετε δικαίωμα αποκάλυψης κωδικών.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        credential = self.get_object()
        # Το audit γράφεται ΠΡΙΝ επιστραφεί η τιμή
        AuditLog.log(
            user=request.user, action='view', obj=credential,
            description=f'Αποκάλυψη κωδικού {credential.get_service_display()} '
                        f'για πελάτη {credential.client.afm}',
            severity='high', request=request,
        )
        return Response({'secret': credential.secret or ''})
