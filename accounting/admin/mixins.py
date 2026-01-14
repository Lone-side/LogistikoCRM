# -*- coding: utf-8 -*-
"""
Shared admin mixins and inline classes for accounting app.
"""
import os

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, escape

from ..models import (
    VoIPCall,
    Ticket,
    ClientDocument,
    EmailLog,
)


# ============================================================================
# INLINES - VoIP Call History for ClientProfile
# ============================================================================

class VoIPCallInline(admin.TabularInline):
    """Inline για εμφάνιση ιστορικού κλήσεων στην καρτέλα πελάτη"""
    model = VoIPCall
    extra = 0
    max_num = 0  # No adding from here
    can_delete = False
    fields = ['started_at', 'direction', 'status', 'duration_display', 'resolution', 'notes']
    readonly_fields = ['started_at', 'direction', 'status', 'duration_display', 'resolution']
    ordering = ['-started_at']
    verbose_name = 'Κλήση'
    verbose_name_plural = '📞 Ιστορικό Κλήσεων'

    def duration_display(self, obj):
        if obj.duration_seconds:
            mins, secs = divmod(obj.duration_seconds, 60)
            return f"{mins}:{secs:02d}"
        return "-"
    duration_display.short_description = 'Διάρκεια'

    def has_add_permission(self, request, obj=None):
        return False


class TicketInline(admin.TabularInline):
    """Enhanced inline για εμφάνιση tickets στην καρτέλα πελάτη"""
    model = Ticket
    extra = 0
    max_num = 0
    can_delete = True  # Allow delete from client page
    fields = ['ticket_link', 'title_short', 'phone_number', 'status_badge', 'priority_badge', 'assigned_display', 'created_at', 'days_open']
    readonly_fields = ['ticket_link', 'title_short', 'phone_number', 'status_badge', 'priority_badge', 'assigned_display', 'created_at', 'days_open']
    ordering = ['-created_at']
    verbose_name = 'Ticket'
    verbose_name_plural = '🎫 Tickets'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('call', 'assigned_to')

    def ticket_link(self, obj):
        url = reverse('admin:accounting_ticket_change', args=[obj.pk])
        return format_html(
            '<a href="{}" style="color: #667eea; font-weight: 600;">#{}</a>',
            url, obj.pk
        )
    ticket_link.short_description = '#'

    def title_short(self, obj):
        title = escape(obj.title)
        return title[:35] + '...' if len(obj.title) > 35 else title
    title_short.short_description = 'Τίτλος'

    def phone_number(self, obj):
        if obj.call and obj.call.phone_number:
            return format_html(
                '<span style="font-family: monospace; color: #2563eb;">📞 {}</span>',
                obj.call.phone_number
            )
        return format_html('<span style="color: #999;">—</span>')
    phone_number.short_description = 'Τηλέφωνο'

    def status_badge(self, obj):
        colors = {
            'open': '#dc2626',
            'assigned': '#d97706',
            'in_progress': '#2563eb',
            'resolved': '#059669',
            'closed': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        label = obj.get_status_display().replace('🔴 ', '').replace('👤 ', '').replace('⏳ ', '').replace('✅ ', '').replace('🔒 ', '')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 8px; '
            'border-radius: 10px; font-size: 11px;">{}</span>',
            color, label
        )
    status_badge.short_description = 'Κατάσταση'

    def priority_badge(self, obj):
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444',
            'urgent': '#991b1b',
        }
        icons = {
            'low': '🟢',
            'medium': '🟡',
            'high': '🟠',
            'urgent': '🔴',
        }
        color = colors.get(obj.priority, '#6b7280')
        icon = icons.get(obj.priority, '')
        return format_html(
            '<span style="background: {}; color: white; padding: 2px 6px; '
            'border-radius: 4px; font-size: 10px;">{}</span>',
            color, icon
        )
    priority_badge.short_description = 'Προτ.'

    def assigned_display(self, obj):
        if obj.assigned_to:
            name = obj.assigned_to.get_full_name() or obj.assigned_to.username
            return format_html('<span style="font-size: 11px;">{}</span>', name[:15])
        return format_html('<span style="color: #999; font-size: 11px;">—</span>')
    assigned_display.short_description = 'Ανατεθ.'

    def days_open(self, obj):
        days = obj.days_since_created
        if days == 0:
            return format_html('<span style="color: #10b981; font-size: 11px;">Σήμερα</span>')
        elif days <= 3:
            return format_html('<span style="color: #f59e0b; font-size: 11px;">{}d</span>', days)
        else:
            return format_html('<span style="color: #ef4444; font-size: 11px; font-weight: bold;">{}d</span>', days)
    days_open.short_description = 'Ηλικία'

    def has_add_permission(self, request, obj=None):
        return False


class ClientProfileDocumentInline(admin.TabularInline):
    """Inline για όλα τα documents ενός πελάτη"""
    model = ClientDocument
    extra = 0
    fields = ['document_category', 'file', 'filename', 'uploaded_at', 'obligation']
    readonly_fields = ['filename', 'uploaded_at']
    ordering = ['-uploaded_at']
    verbose_name = 'Έγγραφο'
    verbose_name_plural = 'Έγγραφα Πελάτη'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('obligation', 'obligation__obligation_type')


class ClientDocumentInline(admin.TabularInline):
    """
    Enhanced inline για documents στο MonthlyObligation detail view.
    Με preview, folder buttons και versioning info.
    """
    model = ClientDocument
    extra = 1
    fields = [
        'document_category',
        'file',
        'version_badge',
        'file_info',
        'description',
        'action_buttons'
    ]
    readonly_fields = ['version_badge', 'file_info', 'action_buttons']
    verbose_name = 'Έγγραφο'
    verbose_name_plural = '📎 Συνημμένα Έγγραφα'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(is_current=True).select_related('client', 'uploaded_by')

    def version_badge(self, obj):
        """Εμφάνιση έκδοσης με badge"""
        if not obj.pk:
            return '-'
        if obj.version > 1:
            return format_html(
                '<span style="background: #667eea; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px;">v{}</span>',
                obj.version
            )
        return format_html(
            '<span style="background: #28a745; color: white; padding: 2px 8px; '
            'border-radius: 10px; font-size: 11px;">v1</span>'
        )
    version_badge.short_description = 'Έκδοση'

    def file_info(self, obj):
        """Πληροφορίες αρχείου"""
        if not obj.pk or not obj.file:
            return '-'
        return format_html(
            '<span style="font-size: 12px; color: #666;">'
            '{} | {} | {}</span>',
            obj.file_type.upper() if obj.file_type else '?',
            obj.file_size_display,
            obj.uploaded_at.strftime('%d/%m/%Y') if obj.uploaded_at else ''
        )
    file_info.short_description = 'Πληροφορίες'

    def action_buttons(self, obj):
        """Κουμπιά ενεργειών: Preview, Download, Folder"""
        if not obj.pk or not obj.file:
            return '-'

        # Build buttons
        buttons = []

        # Preview button (για PDF και εικόνες)
        if obj.file_type and obj.file_type.lower() in ['pdf', 'jpg', 'jpeg', 'png', 'gif']:
            preview_url = reverse('accounting:api_document_preview', args=[obj.id])
            buttons.append(format_html(
                '<button type="button" onclick="showPreview({})" '
                'style="background: #667eea; color: white; border: none; padding: 3px 8px; '
                'border-radius: 4px; cursor: pointer; font-size: 11px; margin-right: 3px;" '
                'title="Προεπισκόπηση">👁️</button>',
                obj.id
            ))

        # Download button
        if obj.file:
            buttons.append(format_html(
                '<a href="{}" target="_blank" '
                'style="background: #28a745; color: white; border: none; padding: 3px 8px; '
                'border-radius: 4px; text-decoration: none; font-size: 11px; margin-right: 3px;" '
                'title="Λήψη">⬇️</a>',
                obj.file.url
            ))

        # Folder button
        folder_url = reverse('accounting:open_document_folder', args=[obj.id])
        buttons.append(format_html(
            '<a href="{}" target="_blank" '
            'style="background: #ffc107; color: #333; border: none; padding: 3px 8px; '
            'border-radius: 4px; text-decoration: none; font-size: 11px;" '
            'title="Άνοιγμα φακέλου">📁</a>',
            folder_url
        ))

        return format_html(''.join([str(b) for b in buttons]))
    action_buttons.short_description = 'Ενέργειες'


class EmailLogInline(admin.TabularInline):
    """Inline view of sent emails for obligations"""
    model = EmailLog
    fk_name = 'obligation'
    extra = 0
    max_num = 10
    readonly_fields = ['sent_at', 'recipient_email', 'subject', 'status_badge', 'sent_by', 'view_body_link']
    fields = ['sent_at', 'recipient_email', 'subject', 'status_badge', 'sent_by', 'view_body_link']
    ordering = ['-sent_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def status_badge(self, obj):
        colors = {
            'sent': '#10b981',
            'failed': '#ef4444',
            'pending': '#f59e0b'
        }
        icons = {
            'sent': '✅',
            'failed': '❌',
            'pending': '⏳'
        }
        color = colors.get(obj.status, '#666')
        icon = icons.get(obj.status, '?')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; border-radius: 4px;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_badge.short_description = 'Κατάσταση'

    def view_body_link(self, obj):
        return format_html(
            '<a href="{}">👁️ View</a>',
            reverse('admin:accounting_emaillog_change', args=[obj.pk])
        )
    view_body_link.short_description = 'Περιεχόμενο'
