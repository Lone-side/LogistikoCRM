# -*- coding: utf-8 -*-
"""
accounting/serializers.py
Author: ddiplas
Version: 2.3 - FIXED: call_id is now writable for VoIP monitor
Description: Unified serializers for Accounting app (Clients, Obligations, VoIP)
"""
from rest_framework import serializers
from .models import (
    ClientProfile,
    MonthlyObligation,
    ObligationType,
    VoIPCall,
    VoIPCallLog,
    ClientDocument,
)

# ============================================
# CLIENT SERIALIZER
# ============================================

class ClientSerializer(serializers.ModelSerializer):
    total_obligations = serializers.SerializerMethodField()

    class Meta:
        model = ClientProfile
        fields = [
            'id', 'afm', 'eponimia', 'email', 'kinito_tilefono',
            'tilefono_oikias_1', 'tilefono_oikias_2',
            'tilefono_epixeirisis_1', 'tilefono_epixeirisis_2',
            'is_active', 'total_obligations',
            # GSIS fields
            'doy', 'nomiki_morfi',
            'diefthinsi_epixeirisis', 'arithmos_epixeirisis',
            'poli_epixeirisis', 'tk_epixeirisis',
            'imerominia_enarksis',
        ]

    def get_total_obligations(self, obj):
        # Προτίμησε annotation από το view (αποφυγή N+1 σε λίστες)
        annotated = getattr(obj, '_obligations_count', None)
        if annotated is not None:
            return annotated
        return obj.monthly_obligations.count()


# ============================================
# OBLIGATION SERIALIZERS
# ============================================

class ObligationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObligationType
        fields = '__all__'


class MonthlyObligationSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    type_name = serializers.CharField(source='obligation_type.name', read_only=True)
    
    class Meta:
        model = MonthlyObligation
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


# ============================================
# VOIP SERIALIZERS
# ============================================

class VoIPCallSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    duration_formatted = serializers.CharField(read_only=True)
    
    class Meta:
        model = VoIPCall
        fields = [
            'id', 'call_id', 'client', 'client_name',
            'direction', 'phone_number', 'status',
            'started_at', 'ended_at', 'duration_seconds',
            'duration_formatted', 'notes',
            'ticket_created', 'ticket_id', 'client_email',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'duration_formatted', 'ticket_created', 'ticket_id'
        ]
        # CRITICAL: call_id is NOT read-only!
        # VoIP monitor must be able to set it with unique timestamp-based IDs
        
        extra_kwargs = {
            'call_id': {'required': True},  # VoIP monitor always sends this
            'client': {'required': False},  # Auto-matched by phone number
            'ticket': {'required': False},  # Created later by Celery task
            'ended_at': {'required': False},  # Set when call ends
            'duration_seconds': {'required': False},  # Calculated from timestamps
            'notes': {'required': False},
            'client_email': {'required': False},
        }


class VoIPCallLogSerializer(serializers.ModelSerializer):
    call_display = serializers.SerializerMethodField()

    def get_call_display(self, obj):
        # Null-safe: μετά τη διαγραφή της κλήσης χρησιμοποιείται το snapshot
        if obj.call_id is not None:
            return obj.call.phone_number
        return obj.phone_number or obj.call_reference or None

    class Meta:
        model = VoIPCallLog
        fields = [
            'id', 'call', 'call_display',
            'action', 'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


# accounting/serializers.py - Προσθήκη

# accounting/serializers.py - Αντικατέστησε ΜΟΝΟ το ClientDocumentSerializer

class ClientDocumentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.eponimia', read_only=True)
    obligation_type = serializers.CharField(source='obligation.obligation_type.name', read_only=True)
    file_url = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_document_category_display', read_only=True)
    
    file_size_display = serializers.CharField(read_only=True)
    uploaded_by = serializers.CharField(
        source='uploaded_by.get_full_name', read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = ClientDocument
        fields = [
            'id', 'client', 'client_name', 'obligation', 'obligation_type',
            'file', 'file_url', 'filename', 'original_filename', 'file_type',
            'file_size', 'file_size_display',
            'document_category', 'category_display', 'description',
            'year', 'month', 'version', 'is_current',
            'ocr_status', 'afm_mismatch',
            'uploaded_at', 'uploaded_by',
        ]
        read_only_fields = ['filename', 'file_type', 'uploaded_at', 'category_display',
                            'ocr_status', 'afm_mismatch']
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None