# -*- coding: utf-8 -*-
"""
accounting/api_obligation_profiles.py
Author: Claude
Description: REST API for Client Obligation Profiles and Monthly Generation

Endpoints:
- GET  /api/v1/clients/obligation-status/        - Get all clients with obligation status
- GET  /api/v1/clients/{id}/obligation-profile/  - Get client's obligation profile
- PUT  /api/v1/clients/{id}/obligation-profile/  - Update client's obligation profile
- GET  /api/v1/obligation-types/grouped/         - Get obligation types grouped by category
- GET  /api/v1/obligation-profiles/              - Get reusable obligation profiles
- POST /api/v1/obligations/generate-month/       - Generate monthly obligations from profiles
- POST /api/v1/obligations/bulk-assign/          - Bulk assign obligations to clients
"""

from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from .models import (
    ClientProfile,
    ClientObligation,
    ObligationType,
    ObligationGroup,
    ObligationProfile,
    MonthlyObligation,
)


# ============================================
# SERIALIZERS
# ============================================

class ObligationTypeGroupedSerializer(serializers.ModelSerializer):
    """Serializer for ObligationType with group info"""
    group_name = serializers.CharField(source='exclusion_group.name', read_only=True, default='Χωρίς ομάδα')
    group_id = serializers.IntegerField(source='exclusion_group.id', read_only=True, default=None)

    class Meta:
        model = ObligationType
        fields = ['id', 'name', 'code', 'frequency', 'group_id', 'group_name', 'deadline_type', 'deadline_day']


class ObligationProfileSerializer(serializers.ModelSerializer):
    """Serializer for ObligationProfile (reusable bundles)"""
    obligation_types = ObligationTypeGroupedSerializer(source='obligations', many=True, read_only=True)

    class Meta:
        model = ObligationProfile
        fields = ['id', 'name', 'description', 'obligation_types']


class ClientObligationProfileSerializer(serializers.Serializer):
    """Serializer for client's obligation profile response"""
    client_id = serializers.IntegerField()
    obligation_type_ids = serializers.ListField(child=serializers.IntegerField())
    obligation_types = ObligationTypeGroupedSerializer(many=True)
    obligation_profile_ids = serializers.ListField(child=serializers.IntegerField())
    obligation_profiles = ObligationProfileSerializer(many=True)


# ============================================
# CLIENT OBLIGATION STATUS ENDPOINT
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def clients_obligation_status(request):
    from accounting.services.access import accessible_clients
    """
    GET /api/v1/clients/obligation-status/
    Returns all clients with their obligation profile status

    Query params:
    - active_only: true/false (default: true)

    Response:
    [
        {
            id: 1,
            afm: "123456789",
            eponimia: "ΕΤΑΙΡΕΙΑ ΑΕ",
            is_active: true,
            has_obligation_profile: true,
            obligation_types_count: 5,
            obligation_profile_names: ["Μισθοδοσία", "ΦΠΑ"]
        },
        ...
    ]
    """
    active_only = request.query_params.get('active_only', 'true').lower() == 'true'

    # Get clients
    clients_qs = accessible_clients(request.user)
    if active_only:
        clients_qs = clients_qs.filter(is_active=True)

    # Prefetch obligation data - related_name is 'obligation_settings'
    clients_qs = clients_qs.select_related().prefetch_related(
        'obligation_settings',
        'obligation_settings__obligation_types',
        'obligation_settings__obligation_profiles'
    )

    result = []
    for client in clients_qs:
        obligation_types_count = 0
        profile_names = []
        has_profile = False
        obligation_types_detail = []  # Detailed info with groups
        groups_used = set()  # Track which groups are used

        # Check if client has obligation_settings using try/except (safer for OneToOne)
        try:
            client_obl = client.obligation_settings
            if client_obl and client_obl.is_active:
                has_profile = True
                # Get all obligation types (individual + from profiles)
                all_types = client_obl.get_all_obligation_types()
                obligation_types_count = len(all_types)

                # Get profile names
                for profile in client_obl.obligation_profiles.all():
                    profile_names.append(profile.name)

                # Get detailed obligation types with groups
                for ot in all_types:
                    group_name = None
                    group_id = None
                    if ot.exclusion_group:
                        group_name = ot.exclusion_group.name
                        group_id = ot.exclusion_group.id
                        groups_used.add(group_name)

                    obligation_types_detail.append({
                        'id': ot.id,
                        'name': ot.name,
                        'code': ot.code,
                        'frequency': ot.frequency,
                        'group_id': group_id,
                        'group_name': group_name,
                    })
        except ClientObligation.DoesNotExist:
            pass

        result.append({
            'id': client.id,
            'afm': client.afm,
            'eponimia': client.eponimia,
            'is_active': client.is_active,
            'has_obligation_profile': has_profile,
            'obligation_types_count': obligation_types_count,
            'obligation_profile_names': profile_names,
            'obligation_types': obligation_types_detail,  # Detailed types with groups
            'groups_used': list(groups_used),  # Quick list of group names
        })

    return Response(result)


# ============================================
# CLIENT OBLIGATION PROFILE ENDPOINTS
# ============================================

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def client_obligation_profile(request, client_id):
    """
    GET /api/v1/clients/{id}/obligation-profile/
    Returns the client's obligation profile (which obligations they have)

    PUT /api/v1/clients/{id}/obligation-profile/
    Updates the client's obligation profile
    Body: { obligation_type_ids: [1,2,3], obligation_profile_ids: [1] }
    """
    from accounting.services.access import get_accessible_client_or_404
    client = get_accessible_client_or_404(request.user, client_id, request=request)

    # Get or create the ClientObligation record
    client_obligation, created = ClientObligation.objects.get_or_create(
        client=client,
        defaults={'is_active': True}
    )

    if request.method == 'GET':
        # Get individual obligation types
        obligation_types = list(client_obligation.obligation_types.filter(is_active=True))
        obligation_type_ids = [ot.id for ot in obligation_types]

        # Get profiles
        profiles = list(client_obligation.obligation_profiles.all())
        profile_ids = [p.id for p in profiles]

        # Serialize
        types_serializer = ObligationTypeGroupedSerializer(obligation_types, many=True)
        profiles_serializer = ObligationProfileSerializer(profiles, many=True)

        return Response({
            'client_id': client_id,
            'obligation_type_ids': obligation_type_ids,
            'obligation_types': types_serializer.data,
            'obligation_profile_ids': profile_ids,
            'obligation_profiles': profiles_serializer.data,
        })

    elif request.method == 'PUT':
        from accounting.services.access import check_model_perms
        if not check_model_perms(request, 'accounting.change_clientobligation'):
            return Response(
                {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        obligation_type_ids = request.data.get('obligation_type_ids', [])
        obligation_profile_ids = request.data.get('obligation_profile_ids', [])

        # Update obligation types
        if obligation_type_ids is not None:
            obligation_types = ObligationType.objects.filter(
                id__in=obligation_type_ids,
                is_active=True
            )
            client_obligation.obligation_types.set(obligation_types)

        # Update profiles
        if obligation_profile_ids is not None:
            profiles = ObligationProfile.objects.filter(id__in=obligation_profile_ids)
            client_obligation.obligation_profiles.set(profiles)

        client_obligation.is_active = True
        client_obligation.save()

        return Response({
            'success': True,
            'message': 'Το προφίλ υποχρεώσεων ενημερώθηκε επιτυχώς.'
        })


# ============================================
# OBLIGATION TYPES GROUPED ENDPOINT
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obligation_types_grouped(request):
    """
    GET /api/v1/obligation-types/grouped/
    Returns obligation types grouped by their exclusion_group (category)

    Response:
    [
        {
            group_id: 1,
            group_name: "Φορολογικά",
            types: [{ id, name, code, frequency }, ...]
        },
        ...
    ]
    """
    # Get all groups
    groups = ObligationGroup.objects.all().order_by('name')

    # Get all active types
    types = list(ObligationType.objects.filter(is_active=True).select_related('exclusion_group').order_by('priority', 'name'))

    # Group types by their exclusion_group
    result = []

    # Track which types have been added to avoid orphaned FK issues
    added_type_ids = set()

    # First, add groups with their types
    for group in groups:
        group_types = [t for t in types if t.exclusion_group_id == group.id]
        if group_types:
            for t in group_types:
                added_type_ids.add(t.id)
            result.append({
                'group_id': group.id,
                'group_name': group.name,
                'types': ObligationTypeGroupedSerializer(group_types, many=True).data
            })

    # Add ALL remaining types (including those with orphaned exclusion_group or None)
    # This catches: types with exclusion_group=None AND types with invalid/orphaned exclusion_group_id
    remaining_types = [t for t in types if t.id not in added_type_ids]
    if remaining_types:
        result.append({
            'group_id': None,
            'group_name': 'Λοιπά',
            'types': ObligationTypeGroupedSerializer(remaining_types, many=True).data
        })

    return Response(result)


# ============================================
# OBLIGATION PROFILES ENDPOINT
# ============================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obligation_profiles_list(request):
    """
    GET /api/v1/obligation-profiles/
    Returns all reusable obligation profiles
    """
    profiles = ObligationProfile.objects.all().prefetch_related('obligation_types')
    serializer = ObligationProfileSerializer(profiles, many=True)
    return Response(serializer.data)


# ============================================
# GENERATE MONTHLY OBLIGATIONS ENDPOINT
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_month_obligations(request):
    from accounting.services.access import accessible_clients, require_model_perms  # noqa: F401
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.add_monthlyobligation'):
        return Response(
            {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    """
    POST /api/v1/obligations/generate-month/
    Generate monthly obligations for clients based on their obligation profiles

    Body: {
        month: 1,           # Required: 1-12
        year: 2025,         # Required
        client_ids: [1,2,3] # Optional: if empty, generate for ALL active clients
    }

    Response: {
        created_count: 25,
        skipped_count: 5,
        clients_processed: 10,
        details: [
            { client_id: 1, client_name: "...", created: ["ΦΠΑ", "ΑΠΔ"], skipped: ["ΕΝΦΙΑ"] }
        ]
    }
    """
    month = request.data.get('month')
    year = request.data.get('year')
    client_ids = request.data.get('client_ids', [])

    # Validation
    if not month or not year:
        return Response(
            {'error': 'Απαιτούνται μήνας και έτος.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        month = int(month)
        year = int(year)
    except (ValueError, TypeError):
        return Response(
            {'error': 'Μη έγκυρος μήνας ή έτος.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if month < 1 or month > 12:
        return Response(
            {'error': 'Ο μήνας πρέπει να είναι 1-12.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if year < 1900 or year > 2100:
        return Response(
            {'error': 'Το έτος πρέπει να είναι από 1900 έως 2100.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get clients
    if client_ids:
        clients = accessible_clients(request.user).filter(id__in=client_ids, is_active=True)
    else:
        clients = accessible_clients(request.user).filter(is_active=True)

    if not clients.exists():
        return Response(
            {'error': 'Δεν βρέθηκαν ενεργοί πελάτες.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    created_count = 0
    skipped_count = 0
    details = []

    with transaction.atomic():
        for client in clients:
            client_created = []
            client_skipped = []

            # Get client's obligation settings
            try:
                client_obligation = ClientObligation.objects.get(client=client, is_active=True)
            except ClientObligation.DoesNotExist:
                # Client has no obligation profile configured
                details.append({
                    'client_id': client.id,
                    'client_name': client.eponimia,
                    'created': [],
                    'skipped': [],
                    'note': 'Δεν έχει ρυθμιστεί προφίλ υποχρεώσεων'
                })
                continue

            # Get all obligation types for this client
            all_types = client_obligation.get_all_obligation_types()

            for obligation_type in all_types:
                # Check if this type applies to this month
                if not obligation_type.applies_to_month(month):
                    continue

                # Check if obligation already exists
                existing = MonthlyObligation.objects.filter(
                    client=client,
                    obligation_type=obligation_type,
                    year=year,
                    month=month
                ).exists()

                if existing:
                    client_skipped.append(obligation_type.name)
                    skipped_count += 1
                    continue

                # Calculate deadline
                deadline = obligation_type.get_deadline_for_month(year, month)
                if not deadline:
                    from calendar import monthrange
                    last_day = monthrange(year, month)[1]
                    deadline = timezone.datetime(year, month, last_day).date()

                # Create the obligation
                MonthlyObligation.objects.create(
                    client=client,
                    obligation_type=obligation_type,
                    year=year,
                    month=month,
                    deadline=deadline,
                    status='pending'
                )

                client_created.append(obligation_type.name)
                created_count += 1

            if client_created or client_skipped:
                details.append({
                    'client_id': client.id,
                    'client_name': client.eponimia,
                    'created': client_created,
                    'skipped': client_skipped
                })

    return Response({
        'success': True,
        'created_count': created_count,
        'skipped_count': skipped_count,
        'clients_processed': clients.count(),
        'details': details,
        'message': f'Δημιουργήθηκαν {created_count} υποχρεώσεις. Παραλείφθηκαν {skipped_count} (υπήρχαν ήδη).'
    }, status=status.HTTP_201_CREATED)


# ============================================
# BULK ASSIGN OBLIGATIONS TO CLIENTS
# ============================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_assign_obligations(request):
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_clientobligation'):
        return Response(
            {'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    """
    POST /api/v1/obligations/bulk-assign/
    Bulk assign obligation types and profiles to multiple clients

    Body: {
        client_ids: [1, 2, 3],              # Required: client IDs
        obligation_type_ids: [1, 2, 3],     # Optional: individual obligation types
        obligation_profile_ids: [1, 2],     # Optional: obligation profiles
        mode: 'add' | 'replace'             # Optional: 'add' (default) or 'replace'
    }

    Response: {
        success: true,
        created_count: 5,
        updated_count: 2,
        message: "..."
    }
    """
    client_ids = request.data.get('client_ids', [])
    obligation_type_ids = request.data.get('obligation_type_ids', [])
    obligation_profile_ids = request.data.get('obligation_profile_ids', [])
    mode = request.data.get('mode', 'add')  # 'add' or 'replace'

    # Validation
    if not client_ids:
        return Response(
            {'error': 'Δεν επιλέχθηκαν πελάτες.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not obligation_type_ids and not obligation_profile_ids:
        return Response(
            {'error': 'Επιλέξτε τουλάχιστον έναν τύπο ή προφίλ υποχρεώσεων.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get clients
    from accounting.services.access import accessible_clients
    clients = accessible_clients(request.user).filter(id__in=client_ids)
    if not clients.exists():
        return Response(
            {'error': 'Δεν βρέθηκαν οι επιλεγμένοι πελάτες.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get obligation types
    obligation_types = ObligationType.objects.filter(
        id__in=obligation_type_ids,
        is_active=True
    ) if obligation_type_ids else ObligationType.objects.none()

    # Get profiles
    profiles = ObligationProfile.objects.filter(
        id__in=obligation_profile_ids
    ) if obligation_profile_ids else ObligationProfile.objects.none()

    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for client in clients:
            # Get or create ClientObligation
            client_obligation, created = ClientObligation.objects.get_or_create(
                client=client,
                defaults={'is_active': True}
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

            # Update based on mode
            if mode == 'replace':
                # Replace all
                client_obligation.obligation_types.set(obligation_types)
                client_obligation.obligation_profiles.set(profiles)
            else:
                # Add to existing
                for ot in obligation_types:
                    client_obligation.obligation_types.add(ot)
                for p in profiles:
                    client_obligation.obligation_profiles.add(p)

            client_obligation.is_active = True
            client_obligation.save()

    return Response({
        'success': True,
        'created_count': created_count,
        'updated_count': updated_count,
        'clients_processed': clients.count(),
        'message': f'Ανατέθηκαν υποχρεώσεις σε {clients.count()} πελάτες. ({created_count} νέα, {updated_count} ενημερωμένα)'
    })
