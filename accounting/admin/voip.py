# -*- coding: utf-8 -*-
"""
VoIP and Ticket admin classes for accounting app.

Contains:
- VoIPCallAdmin
- VoIPCallLogAdmin
- TicketAdmin
"""
import csv
import logging
from datetime import datetime

from django.urls import reverse
from django.utils.html import format_html, escape
from django.contrib import admin
from .scoping import ClientScopedAdminMixin
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.contrib.admin.utils import get_deleted_objects
from django.db import router
from django.contrib import messages

from ..models import (
    VoIPCall,
    VoIPCallLog,
    Ticket,
)

logger = logging.getLogger(__name__)


@admin.register(VoIPCall)
class VoIPCallAdmin(ClientScopedAdminMixin, admin.ModelAdmin):
    allow_unassigned = True
    list_select_related = ('client',)

    """Complete VoIP Admin"""

    list_display = [
        'call_id_colored',
        'phone_number_link',
        'client_link',
        'direction_icon',
        'status_badge',
        'resolution_badge',
        'duration_display',
        'started_at_formatted',
        'ticket_badge',
    ]

    list_filter = [
        'status',
        'direction',
        'resolution',
        'started_at',
        'ticket_created',
        ('client', admin.RelatedOnlyFieldListFilter),
    ]

    search_fields = ['phone_number', 'client__eponimia', 'client_email', 'call_id', 'notes']
    readonly_fields = ['call_id', 'duration_formatted', 'created_at', 'updated_at', 'logs_display']

    actions = [
        'mark_as_closed',
        'mark_as_follow_up',
        'mark_as_pending',
        'delete_with_tickets',
        'delete_without_tickets',
        'export_calls_csv',
    ]

    fieldsets = (
        ('📞 Κλήση - Βασικά', {
            'fields': ('call_id', 'phone_number', 'direction', 'status'),
        }),
        ('👤 Πελάτης', {
            'fields': ('client', 'client_email'),
        }),
        ('⏱️ Χρονισμός', {
            'fields': ('started_at', 'ended_at', 'duration_seconds', 'duration_formatted'),
        }),
        ('📝 Σημειώσεις & Ευστάθεια', {
            'fields': ('notes', 'resolution'),
        }),
        ('🎫 Τίκετ', {
            'fields': ('ticket_created', 'ticket_id'),
        }),
        ('📊 Ιστορικό', {
            'fields': ('logs_display', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    ordering = ['-started_at']
    date_hierarchy = 'started_at'
    list_per_page = 50

    # Display methods
    def call_id_colored(self, obj):
        return format_html(
            '<span style="background-color: #e3f2fd; padding: 6px 12px; border-radius: 4px; font-family: monospace; font-weight: 600;">{}</span>',
            obj.call_id
        )
    call_id_colored.short_description = '📱 Call ID'

    def phone_number_link(self, obj):
        return format_html(
            '<a href="tel:{}" style="color: #2563eb; text-decoration: none; font-weight: 600;">📞 {}</a>',
            escape(obj.phone_number),
            escape(obj.phone_number)
        )
    phone_number_link.short_description = '🔔 Αριθμός'

    def client_link(self, obj):
        if obj.client:
            url = reverse('admin:accounting_clientprofile_change', args=[obj.client.id])
            return format_html(
                '<a href="{}" style="color: #059669; font-weight: 600;">👤 {}</a>',
                url,
                escape(obj.client.eponimia)
            )
        return format_html('<span style="color: #999;">—</span>')
    client_link.short_description = '👤 Πελάτης'

    def direction_icon(self, obj):
        if obj.direction == 'incoming':
            return format_html('<span style="font-size: 1.2em;">📲</span> Εισερχόμενη')
        return format_html('<span style="font-size: 1.2em;">☎️</span> Εξερχόμενη')
    direction_icon.short_description = 'Κατεύθυνση'

    def status_badge(self, obj):
        colors = {
            'missed': ('#dc2626', '❌', 'Αναπάντητη'),
            'completed': ('#16a34a', '✅', 'Ολοκληρώθηκε'),
            'active': ('#2563eb', '🔵', 'Ενεργή'),
            'failed': ('#ea580c', '⚠️', 'Αποτυχία'),
        }
        color, icon, label = colors.get(obj.status, ('#999', '❓', obj.status))
        return format_html(
            '<span style="background: {}; color: white; padding: 6px 12px; border-radius: 20px; font-weight: 600;">{} {}</span>',
            color, icon, label
        )
    status_badge.short_description = 'Κατάσταση'

    def resolution_badge(self, obj):
        if not obj.resolution:
            return format_html('<span style="color: #999;">—</span>')

        colors = {
            'pending': ('#f59e0b', '⏳', 'Εκρεμμότητα'),
            'closed': ('#10b981', '✅', 'Κλειστή'),
            'follow_up': ('#3b82f6', '📞', 'Follow-up'),
        }
        color, icon, label = colors.get(obj.resolution, ('#999', '?', obj.resolution))
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 12px; font-weight: 600;">{} {}</span>',
            color, icon, label
        )
    resolution_badge.short_description = 'Ευστάθεια'

    def duration_display(self, obj):
        return format_html(
            '<span style="background: #f3f4f6; padding: 6px 12px; border-radius: 4px; font-weight: 600;">⏱️ {}</span>',
            obj.duration_formatted
        )
    duration_display.short_description = 'Διάρκεια'

    def started_at_formatted(self, obj):
        return obj.started_at.strftime('%d/%m/%Y\n%H:%M:%S')
    started_at_formatted.short_description = '📅 Ημερ/Ώρα'

    def ticket_badge(self, obj):
        if obj.ticket_created:
            return format_html(
                '<span style="background: #dcfce7; color: #15803d; padding: 4px 10px; border-radius: 4px; font-weight: 600;">🎫 ΝΑΙ</span>'
            )
        return format_html(
            '<span style="background: #fee2e2; color: #991b1b; padding: 4px 10px; border-radius: 4px; font-weight: 600;">✗ ΌΧΙ</span>'
        )
    ticket_badge.short_description = 'Τίκετ'

    def logs_display(self, obj):
        logs = obj.logs.all().order_by('-created_at')[:10]
        html = '<div style="max-height: 300px; overflow-y: auto;">'
        for log in logs:
            html += f'<div style="border-left: 3px solid #2563eb; padding: 8px; margin: 5px 0;"><strong>{log.get_action_display()}</strong><br><small style="color: #666;">{log.created_at.strftime("%d/%m %H:%M")} - {log.description}</small></div>'
        html += '</div>'
        return format_html(html)
    logs_display.short_description = 'Ιστορικό'

    # Actions
    def mark_as_closed(self, request, queryset):
        updated = queryset.update(resolution='closed')
        self.message_user(request, f'✅ {updated} κλήσεις σημειώθηκαν ως κλειστές!')
        logger.info(f"{request.user} marked {updated} calls as closed")
    mark_as_closed.short_description = '✅ Κλείσιμο'

    def mark_as_follow_up(self, request, queryset):
        updated = queryset.update(resolution='follow_up')
        self.message_user(request, f'📞 {updated} κλήσεις χρειάζονται follow-up!')
        logger.info(f"{request.user} marked {updated} calls as follow_up")
    mark_as_follow_up.short_description = '📞 Follow-up'

    def mark_as_pending(self, request, queryset):
        updated = queryset.update(resolution='pending')
        self.message_user(request, f'⏳ {updated} κλήσεις σημειώθηκαν ως εκρεμμότητες!')
        logger.info(f"{request.user} marked {updated} calls as pending")
    mark_as_pending.short_description = '⏳ Εκκρεμεί'

    def has_export_permission(self, request):
        # Τηλέφωνα + επωνυμίες πελατών — θέλει το ξεχωριστό export permission
        return request.user.has_perm('accounting.export_clientprofile')

    def export_calls_csv(self, request, queryset):
        """Export to CSV"""
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="calls_{datetime.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Αριθμός', 'Πελάτης', 'Κατεύθυνση', 'Κατάσταση', 'Ευστάθεια', 'Διάρκεια', 'Ημερομηνία'])

        for call in queryset:
            writer.writerow([
                call.phone_number,
                call.client.eponimia if call.client else '—',
                call.get_direction_display(),
                call.get_status_display(),
                call.get_resolution_display() if call.resolution else '—',
                call.duration_formatted,
                call.started_at.strftime('%d/%m/%Y %H:%M'),
            ])

        logger.info(f"{request.user} exported {queryset.count()} calls to CSV")
        return response
    export_calls_csv.short_description = '📊 Export CSV'
    export_calls_csv.allowed_permissions = ('export',)

    # Bulk delete actions
    def delete_with_tickets(self, request, queryset):
        """Διαγραφή κλήσεων μαζί με τα tickets τους (CASCADE)"""
        count = queryset.count()
        ticket_count = Ticket.objects.filter(call__in=queryset).count()
        queryset.delete()
        self.message_user(
            request,
            f'{count} κλήσεις και {ticket_count} tickets διαγράφηκαν',
            messages.SUCCESS
        )
    delete_with_tickets.short_description = 'Διαγραφή με tickets'

    def delete_without_tickets(self, request, queryset):
        """Διαγραφή κλήσεων χωρίς τα tickets (αποσύνδεση πρώτα)"""
        count = queryset.count()
        # Αποσύνδεση tickets πρώτα
        Ticket.objects.filter(call__in=queryset).update(call=None)
        # Ενημέρωση ticket_created
        queryset.update(ticket_created=False)
        queryset.delete()
        self.message_user(
            request,
            f'{count} κλήσεις διαγράφηκαν (tickets διατηρήθηκαν)',
            messages.SUCCESS
        )
    delete_without_tickets.short_description = 'Διαγραφή χωρίς tickets'

    # Custom delete view
    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, object_id)
        extra_context = extra_context or {}

        # Check for related ticket
        has_ticket = hasattr(obj, 'ticket') and obj.ticket is not None
        if has_ticket:
            extra_context['has_related_ticket'] = True
            extra_context['ticket_id'] = obj.ticket.id

        return super().delete_view(request, object_id, extra_context)


@admin.register(VoIPCallLog)
class VoIPCallLogAdmin(ClientScopedAdminMixin, admin.ModelAdmin):
    client_scope_field = "call__client"
    allow_unassigned = True
    """VoIP Call Logs - Audit Trail"""

    list_display = ['call_link', 'action_badge', 'description_short', 'created_at_formatted']
    list_filter = ['action', 'created_at']
    search_fields = ['call__phone_number', 'description']
    readonly_fields = ['call', 'action', 'description', 'created_at']

    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def call_link(self, obj):
        url = reverse('admin:accounting_voipcall_change', args=[obj.call.id])
        return format_html(
            '<a href="{}" style="color: #2563eb; font-weight: 600;">📞 {}</a>',
            url,
            escape(obj.call.phone_number)
        )
    call_link.short_description = 'Κλήση'

    def action_badge(self, obj):
        colors = {
            'started': '#3b82f6',
            'ended': '#10b981',
            'ticket_created': '#f59e0b',
            'client_matched': '#8b5cf6',
            'status_changed': '#06b6d4',
        }
        color = colors.get(obj.action, '#666')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 4px; font-weight: 600;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_badge.short_description = 'Ενέργεια'

    def description_short(self, obj):
        desc = escape(obj.description)
        return desc[:80] + '...' if len(obj.description) > 80 else desc
    description_short.short_description = 'Περιγραφή'

    def created_at_formatted(self, obj):
        return obj.created_at.strftime('%d/%m/%Y %H:%M:%S')
    created_at_formatted.short_description = 'Χρόνος'


@admin.register(Ticket)
class TicketAdmin(ClientScopedAdminMixin, admin.ModelAdmin):
    allow_unassigned = True
    list_select_related = ('client', 'call', 'assigned_to')

    """Professional Ticket Admin"""

    list_display = [
        'ticket_id_display',
        'title_short',
        'client_link',
        'call_link',
        'status_badge',
        'priority_badge',
        'assigned_to_display',
        'created_at_formatted',
        'days_open'
    ]

    list_filter = [
        'status',
        'priority',
        'created_at',
        'assigned_to',
        ('client', admin.RelatedOnlyFieldListFilter),
    ]

    search_fields = [
        'title',
        'description',
        'call__phone_number',
        'client__eponimia',
        'notes'
    ]

    readonly_fields = [
        'created_at',
        'assigned_at',
        'resolved_at',
        'closed_at',
        'call_info',
    ]

    fieldsets = (
        ('🎫 Ticket Info', {
            'fields': ('call', 'call_info', 'title', 'description')
        }),
        ('👤 Client & Assignment', {
            'fields': ('client', 'assigned_to')
        }),
        ('📊 Status', {
            'fields': ('status', 'priority')
        }),
        ('📝 Notes', {
            'fields': ('notes',)
        }),
        ('📅 Timestamps', {
            'fields': ('created_at', 'assigned_at', 'resolved_at', 'closed_at'),
            'classes': ('collapse',)
        }),
        ('🔔 Notifications', {
            'fields': ('email_sent', 'follow_up_scheduled')
        }),
    )

    actions = [
        'mark_as_assigned',
        'mark_as_in_progress',
        'mark_as_resolved',
        'mark_as_closed',
        'delete_with_calls',
        'delete_without_calls',
        'export_tickets_csv',
    ]

    ordering = ['-created_at']

    # Display methods
    def ticket_id_display(self, obj):
        return format_html(
            '<span style="background: #667eea; color: white; padding: 6px 12px; border-radius: 4px; font-weight: 600;">#{}</span>',
            obj.id
        )
    ticket_id_display.short_description = '🎫'

    def title_short(self, obj):
        title = escape(obj.title)
        return title[:50] + '...' if len(obj.title) > 50 else title
    title_short.short_description = 'Τίτλος'

    def client_link(self, obj):
        if obj.client:
            url = reverse('admin:accounting_clientprofile_change', args=[obj.client.id])
            return format_html('<a href="{}">{}</a>', url, escape(obj.client.eponimia))
        return '—'
    client_link.short_description = 'Πελάτης'

    def call_link(self, obj):
        if obj.call:
            url = reverse('admin:accounting_voipcall_change', args=[obj.call.id])
            return format_html('<a href="{}">{}</a>', url, f'Call #{obj.call.id}')
        return '—'
    call_link.short_description = 'Κλήση'

    def call_info(self, obj):
        if obj.call:
            return format_html(
                '📞 {}<br>↔️ {}<br>🕐 {}<br>⏱️ {}',
                escape(obj.call.phone_number),
                escape(obj.call.get_direction_display()),
                obj.call.started_at.strftime('%d/%m/%Y %H:%M'),
                escape(obj.call.duration_formatted)
            )
        return '—'
    call_info.short_description = 'Call Details'

    def status_badge(self, obj):
        colors = {
            'open': '#ef4444',
            'assigned': '#f59e0b',
            'in_progress': '#3b82f6',
            'resolved': '#10b981',
            'closed': '#6b7280',
        }
        color = colors.get(obj.status, '#666')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 12px; font-weight: 600;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Κατάσταση'

    def priority_badge(self, obj):
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444',
            'urgent': '#991b1b',
        }
        color = colors.get(obj.priority, '#666')
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 8px; border-radius: 4px;">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = 'Προτεραιότητα'

    def assigned_to_display(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.get_full_name() or obj.assigned_to.username
        return '—'
    assigned_to_display.short_description = 'Ανατεθειμένο'

    def created_at_formatted(self, obj):
        return obj.created_at.strftime('%d/%m/%Y %H:%M')
    created_at_formatted.short_description = 'Δημιουργήθηκε'

    def days_open(self, obj):
        days = obj.days_since_created
        if days == 0:
            color = '#10b981'
            text = 'Σήμερα'
        elif days <= 3:
            color = '#f59e0b'
            text = f'{days} ημέρες'
        else:
            color = '#ef4444'
            text = f'{days} ημέρες'

        return format_html(
            '<span style="color: {}; font-weight: 600;">{}</span>',
            color, text
        )
    days_open.short_description = 'Διάρκεια'

    # Actions
    def mark_as_assigned(self, request, queryset):
        updated = queryset.update(status='assigned')
        self.message_user(request, f'✅ {updated} tickets marked as assigned')
    mark_as_assigned.short_description = '✅ Assigned'

    def mark_as_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'⏳ {updated} tickets marked as in progress')
    mark_as_in_progress.short_description = '⏳ In Progress'

    def mark_as_resolved(self, request, queryset):
        updated = 0
        for ticket in queryset:
            ticket.mark_as_resolved()
            updated += 1
        self.message_user(request, f'✅ {updated} tickets resolved')
    mark_as_resolved.short_description = '✅ Resolved'

    def mark_as_closed(self, request, queryset):
        updated = 0
        for ticket in queryset:
            ticket.mark_as_closed()
            updated += 1
        self.message_user(request, f'🔒 {updated} tickets closed')
    mark_as_closed.short_description = '🔒 Closed'

    def has_export_permission(self, request):
        # Επωνυμίες πελατών στο CSV — θέλει το ξεχωριστό export permission
        return request.user.has_perm('accounting.export_clientprofile')

    def export_tickets_csv(self, request, queryset):
        """Export to CSV"""
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="tickets_{datetime.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow(['ID', 'Τίτλος', 'Πελάτης', 'Κατάσταση', 'Προτεραιότητα', 'Ανατεθειμένο', 'Δημιουργήθηκε', 'Ημέρες Ανοιχτό'])

        for ticket in queryset:
            writer.writerow([
                ticket.id,
                ticket.title,
                ticket.client.eponimia if ticket.client else '—',
                ticket.get_status_display(),
                ticket.get_priority_display(),
                ticket.assigned_to.get_full_name() if ticket.assigned_to else '—',
                ticket.created_at.strftime('%d/%m/%Y %H:%M'),
                ticket.days_since_created
            ])

        self.message_user(request, f'✅ Εξήχθησαν {queryset.count()} tickets')
        return response
    export_tickets_csv.short_description = '📊 Export CSV'
    export_tickets_csv.allowed_permissions = ('export',)

    def save_model(self, request, obj, form, change):
        if not change and not obj.assigned_to:
            obj.assigned_to = request.user
        super().save_model(request, obj, form, change)

    # Bulk delete actions
    def delete_with_calls(self, request, queryset):
        """Διαγραφή tickets μαζί με τις κλήσεις τους"""
        call_ids = list(queryset.values_list('call_id', flat=True))
        count = queryset.count()
        # Διαγραφή κλήσεων (cascade θα διαγράψει και τα tickets)
        VoIPCall.objects.filter(id__in=call_ids).delete()
        self.message_user(
            request,
            f'{count} tickets και κλήσεις διαγράφηκαν',
            messages.SUCCESS
        )
    delete_with_calls.short_description = 'Διαγραφή με κλήσεις'

    def delete_without_calls(self, request, queryset):
        """Διαγραφή tickets χωρίς τις κλήσεις (signal θα ενημερώσει calls)"""
        count = queryset.count()
        queryset.delete()
        self.message_user(
            request,
            f'{count} tickets διαγράφηκαν (κλήσεις διατηρήθηκαν)',
            messages.SUCCESS
        )
    delete_without_calls.short_description = 'Διαγραφή χωρίς κλήσεις'

    # Custom delete view
    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, object_id)
        extra_context = extra_context or {}

        # Check for related call
        has_call = obj and obj.call_id is not None
        if has_call:
            extra_context['has_related_call'] = True
            extra_context['call_phone'] = obj.call.phone_number if obj.call else ''

        # Handle POST with delete_call checkbox
        if request.method == 'POST' and request.POST.get('delete_call') == '1':
            if obj and obj.call:
                call = obj.call
                obj.call = None
                obj.save()
                call.delete()
                self.message_user(request, 'Ticket και κλήση διαγράφηκαν', messages.SUCCESS)
                return self.response_delete(request, obj.__str__(), obj.pk)

        return super().delete_view(request, object_id, extra_context)
