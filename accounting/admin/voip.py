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
from django.utils.html import format_html, format_html_join, escape
from django.contrib import admin
from .scoping import ClientScopedAdminMixin
from django.http import HttpResponse
from django.contrib import messages

from ..models import (
    VoIPCall,
    VoIPCallLog,
    Ticket,
)

logger = logging.getLogger(__name__)

def _require_access(request, objects, *, strict):
    """Fail closed object/client access validation για cascade deletes.

    Το Django model permission δεν αρκεί: τα cascade actions αγγίζουν και
    τα δύο μοντέλα μέσω global queries (Ticket.filter(call__in=...),
    VoIPCall.filter(id__in=...)). Ένας scoped χρήστης θα μπορούσε έτσι να
    διαγράψει/τροποποιήσει αντικείμενο ξένου πελάτη ή ασυνεπές legacy row.

    - strict=False (PRIMARY, ήδη changelist-scoped): επιτρέπει
      unassigned (client=None, triage) ή ανατεθειμένο· ξένος → 403.
    - strict=True (CROSS-SIDE, το άλλο μοντέλο μέσω της σχέσης): ΜΟΝΟ
      ανατεθειμένο. client=None (ambiguous ownership / legacy orphan) ή
      ξένος → 403 — καμία σιωπηλή cascade-διαγραφή/μεταβολή.

    See-all χρήστες/superusers περνούν πάντα. Καμία μερική επιτυχία:
    η πρώτη μη προσβάσιμη εγγραφή ρίχνει PermissionDenied πριν από κάθε
    delete/mutation.
    """
    from django.core.exceptions import PermissionDenied
    from accounting.mixins import user_sees_all_clients
    from accounting.services.access import user_can_access_client
    if user_sees_all_clients(request.user):
        return
    for obj in objects:
        client = obj.client
        if client is None:
            if strict:
                # Καμία εσωτερική λεπτομέρεια (id/ΑΦΜ) στο μήνυμα
                raise PermissionDenied(
                    'Η ενέργεια αγγίζει συνδεδεμένα αντικείμενα χωρίς '
                    'σαφή ανάθεση και απορρίφθηκε.')
            continue
        if not user_can_access_client(request.user, client):
            raise PermissionDenied(
                'Η ενέργεια περιλαμβάνει αντικείμενα εκτός της '
                'ανάθεσής σας και απορρίφθηκε.')


def _lock_calls_then_tickets(ticket_ids):
    """
    Κλειδώνει το Call–Ticket ζεύγος με την ΕΝΙΑΙΑ global σειρά:
    ΠΡΩΤΑ VoIPCall, ΜΕΤΑ Ticket.

    Γιατί: τα VoIPCall admin paths (και το change_call_client) κλειδώνουν
    call → ticket, ενώ τα Ticket paths κλείδωναν ticket → call. Με
    ταυτόχρονη διαγραφή του ίδιου ζεύγους από τα δύο admin, το ΑΒ/ΒΑ
    αναπαράχθηκε σε PostgreSQL 14: «deadlock detected». Εδώ οι κλήσεις
    κλειδώνονται μέσω του reverse join (η ανάγνωση των ticket rows στο
    join ΔΕΝ τα κλειδώνει), μετά κλειδώνονται τα tickets.

    TOCTOU: αν κάποιο locked ticket απέκτησε στο μεταξύ κλήση που ΔΕΝ
    κλειδώσαμε, fail closed (PermissionDenied) — καμία μερική μεταβολή,
    ο χρήστης απλώς ξαναδοκιμάζει. Δεν ξανακλειδώνουμε calls μετά τα
    tickets: αυτό θα ξανάνοιγε την αντιστροφή.

    Επιστρέφει (calls, tickets): calls = ΜΟΝΟ όσες αναφέρονται ακόμη από
    τα locked tickets, tickets = τα locked tickets.
    """
    from django.core.exceptions import PermissionDenied
    calls = list(VoIPCall.objects.select_for_update()
                 .filter(ticket__pk__in=ticket_ids))
    tickets = list(Ticket.objects.select_for_update()
                   .filter(pk__in=ticket_ids))
    locked_call_ids = {c.pk for c in calls}
    if any(t.call_id and t.call_id not in locked_call_ids
           for t in tickets):
        raise PermissionDenied(
            'Η σύνδεση κλήσης-ticket άλλαξε κατά τη διάρκεια της '
            'ενέργειας — δοκιμάστε ξανά.')
    linked_ids = {t.call_id for t in tickets if t.call_id}
    calls = [c for c in calls if c.pk in linked_ids]
    return calls, tickets


def _log_admin_deletions(request, queryset):
    """Επίσημα admin LogEntry deletion records — ΜΟΝΟ για όσα διαγράφονται.

    Καλείται ΠΡΙΝ το delete(), μέσα στο ίδιο transaction.atomic():
    σε rollback δεν μένουν ούτε rows ούτε παραπλανητικά log entries.
    """
    from django.contrib.admin.models import DELETION, LogEntry
    if queryset.exists():
        LogEntry.objects.log_actions(
            request.user.pk, queryset, DELETION, single_object=False)



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
        # ΑΣΦΑΛΕΙΑ: το log.description περιέχει user-controlled περιεχόμενο
        # (π.χ. το title του ticket μέσω create_ticket). ΠΟΤΕ f-string +
        # format_html(html) — αυτό κάνει mark_safe χωρίς escaping → stored
        # XSS. Χρήση format_html_join με placeholders: κάθε argument
        # (action, timestamp, description) γίνεται escaped.
        logs = obj.logs.all().order_by('-created_at')[:10]
        rows = format_html_join(
            '',
            '<div style="border-left: 3px solid #2563eb; padding: 8px; '
            'margin: 5px 0;"><strong>{}</strong><br>'
            '<small style="color: #666;">{} - {}</small></div>',
            (
                (log.get_action_display(),
                 log.created_at.strftime('%d/%m %H:%M'),
                 log.description)
                for log in logs
            ),
        )
        return format_html(
            '<div style="max-height: 300px; overflow-y: auto;">{}</div>', rows)
    logs_display.short_description = 'Ιστορικό'

    # Actions
    def mark_as_closed(self, request, queryset):
        updated = queryset.update(resolution='closed')
        self.message_user(request, f'✅ {updated} κλήσεις σημειώθηκαν ως κλειστές!')
        logger.info(f"{request.user} marked {updated} calls as closed")
    mark_as_closed.short_description = '✅ Κλείσιμο'
    mark_as_closed.allowed_permissions = ('change',)

    def mark_as_follow_up(self, request, queryset):
        updated = queryset.update(resolution='follow_up')
        self.message_user(request, f'📞 {updated} κλήσεις χρειάζονται follow-up!')
        logger.info(f"{request.user} marked {updated} calls as follow_up")
    mark_as_follow_up.short_description = '📞 Follow-up'
    mark_as_follow_up.allowed_permissions = ('change',)

    def mark_as_pending(self, request, queryset):
        updated = queryset.update(resolution='pending')
        self.message_user(request, f'⏳ {updated} κλήσεις σημειώθηκαν ως εκρεμμότητες!')
        logger.info(f"{request.user} marked {updated} calls as pending")
    mark_as_pending.short_description = '⏳ Εκκρεμεί'
    mark_as_pending.allowed_permissions = ('change',)

    def has_export_permission(self, request):
        # Τηλέφωνα + επωνυμίες πελατών — θέλει το ξεχωριστό export permission
        return request.user.has_perm('accounting.export_clientprofile')

    def has_delete_permission(self, request, obj=None):
        # Η διαγραφή κλήσης ΤΡΟΠΟΠΟΙΕΙ το συνδεδεμένο Ticket (SET_NULL
        # στο Ticket.call) — καλύπτει και τα built-in delete_selected /
        # object delete_view. Χωρίς ticket, αρκεί το delete_voipcall.
        base = super().has_delete_permission(request, obj)
        if not base:
            return False
        if obj is not None and not (
                hasattr(obj, 'ticket') and obj.ticket is not None):
            return True
        return request.user.has_perm('accounting.change_ticket')

    def has_delete_cascade_tickets_permission(self, request):
        # Η ενέργεια διαγράφει κλήσεις ΚΑΙ τα tickets τους — AND των δύο
        # delete permissions μέσω custom handler (τα πολλαπλά
        # allowed_permissions στο Django λειτουργούν ως OR)
        return (self.has_delete_permission(request)
                and request.user.has_perm('accounting.delete_ticket'))

    def has_delete_detach_tickets_permission(self, request):
        # Διαγράφει κλήσεις και ΤΡΟΠΟΠΟΙΕΙ tickets (call=None)
        return (self.has_delete_permission(request)
                and request.user.has_perm('accounting.change_ticket'))

    def delete_queryset(self, request, queryset):
        # built-in delete_selected: η διαγραφή κλήσεων ΜΕΤΑΒΑΛΛΕΙ (SET_NULL)
        # τα συνδεδεμένα tickets — cross-side strict validation, atomic
        from django.db import transaction
        call_ids = list(queryset.values_list('pk', flat=True))
        with transaction.atomic():
            calls = list(VoIPCall.objects.select_for_update()
                         .filter(pk__in=call_ids))
            tickets = list(Ticket.objects.select_for_update()
                           .filter(call_id__in=call_ids))
            _require_access(request, calls, strict=False)
            _require_access(request, tickets, strict=True)
            super().delete_queryset(
                request, VoIPCall.objects.filter(pk__in=call_ids))

    def delete_model(self, request, obj):
        # standard object delete view: cross-side validation ΠΑΝΩ στο
        # locked row (TOCTOU) — το obj φορτώθηκε από τον Django πριν το
        # transaction, οπότε το obj.client μπορεί να έχει αλλάξει.
        from django.db import transaction
        with transaction.atomic():
            locked_call = (VoIPCall.objects.select_for_update()
                           .filter(pk=obj.pk).first())
            if locked_call is None:
                return  # η κλήση εξαφανίστηκε ενδιάμεσα — no-op fail closed
            tickets = list(Ticket.objects.select_for_update()
                           .filter(call_id=locked_call.pk))
            _require_access(request, [locked_call], strict=False)
            _require_access(request, tickets, strict=True)
            super().delete_model(request, locked_call)

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
        """Διαγραφή κλήσεων ΚΑΙ των tickets τους.

        Το Ticket.call είναι SET_NULL — η διαγραφή της κλήσης ΔΕΝ
        διαγράφει το ticket· τα tickets διαγράφονται ρητά, στην ίδια
        συναλλαγή (καμία μερική διαγραφή).
        """
        from django.db import transaction
        call_ids = list(queryset.values_list('pk', flat=True))
        with transaction.atomic():
            # Lock και τις δύο πλευρές πριν από validation/delete (TOCTOU)
            calls = list(VoIPCall.objects.select_for_update()
                         .filter(pk__in=call_ids))
            tickets = (Ticket.objects.select_for_update()
                       .filter(call_id__in=call_ids))
            tickets_list = list(tickets)
            # Fail closed: κάθε κλήση ΚΑΙ κάθε ticket πρέπει να είναι
            # προσβάσιμο — αλλιώς 403 χωρίς καμία διαγραφή
            _require_access(request, calls, strict=False)
            _require_access(request, tickets_list, strict=True)
            # Ακριβή counts από τα locked lists — ΟΧΙ το .delete()[0]
            # (που περιλαμβάνει cascade-related rows)
            call_count = len(calls)
            ticket_count = len(tickets_list)
            _log_admin_deletions(request, tickets)
            _log_admin_deletions(
                request, VoIPCall.objects.filter(pk__in=call_ids))
            tickets.delete()
            VoIPCall.objects.filter(pk__in=call_ids).delete()
        self.message_user(
            request,
            f'{call_count} κλήσεις και {ticket_count} tickets διαγράφηκαν',
            messages.SUCCESS
        )
    delete_with_tickets.short_description = 'Διαγραφή με tickets'
    # Cascade: διαγράφει ΚΑΙ Tickets → απαιτούνται και τα δύο delete perms
    delete_with_tickets.allowed_permissions = ('delete_cascade_tickets',)

    def delete_without_tickets(self, request, queryset):
        """Διαγραφή κλήσεων χωρίς τα tickets (αποσύνδεση πρώτα)"""
        from django.db import transaction
        call_ids = list(queryset.values_list('pk', flat=True))
        with transaction.atomic():
            calls = list(VoIPCall.objects.select_for_update()
                         .filter(pk__in=call_ids))
            # Τα tickets ΜΕΤΑΒΑΛΛΟΝΤΑΙ (call=None) — απαιτούν κι αυτά access
            tickets = (Ticket.objects.select_for_update()
                       .filter(call_id__in=call_ids))
            tickets_list = list(tickets)
            _require_access(request, calls, strict=False)
            _require_access(request, tickets_list, strict=True)
            count = len(calls)
            detached = len(tickets_list)
            # Deletion log ΜΟΝΟ για τις κλήσεις — τα tickets αποσυνδέονται
            _log_admin_deletions(
                request, VoIPCall.objects.filter(pk__in=call_ids))
            # Αποσύνδεση tickets πρώτα
            Ticket.objects.filter(call_id__in=call_ids).update(call=None)
            # Ενημέρωση ticket_created
            VoIPCall.objects.filter(pk__in=call_ids).update(
                ticket_created=False)
            VoIPCall.objects.filter(pk__in=call_ids).delete()
        self.message_user(
            request,
            f'{count} κλήσεις διαγράφηκαν· {detached} tickets '
            f'αποσυνδέθηκαν (διατηρήθηκαν)',
            messages.SUCCESS
        )
    delete_without_tickets.short_description = 'Διαγραφή χωρίς tickets'
    # Αποσυνδέει tickets (change_ticket) και διαγράφει κλήσεις
    delete_without_tickets.allowed_permissions = ('delete_detach_tickets',)

    # Custom delete view
    def save_model(self, request, obj, form, change):
        from django.db import transaction
        from accounting.services.call_assignment import change_call_client
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if change and 'client' in getattr(form, 'changed_data', []):
                # Κεντρικό service: atomic invariant κλήσης-ticket (bound
                # mismatch/unassign το έχει ήδη απορρίψει το clean() στη
                # φόρμα — εδώ γίνεται το claim του unassigned ticket)
                change_call_client(obj, obj.client, user=request.user)

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
    # Scoping μέσω του snapshot client — επιβιώνει της διαγραφής της
    # κλήσης. Fail closed: logs χωρίς client (legacy orphans ή κλήσεις
    # χωρίς αντιστοίχιση) βλέπουν ΜΟΝΟ see-all χρήστες/superusers.
    client_scope_field = "client"
    allow_unassigned = False
    """VoIP Call Logs - Audit Trail"""

    list_display = ['call_link', 'action_badge', 'description_short', 'created_at_formatted']
    list_filter = ['action', 'created_at']
    search_fields = ['phone_number', 'call_reference', 'description']
    # Read-only audit record ΜΕΣΩ των Admin routes: ΚΑΘΕ πεδίο (incl.
    # snapshots) readonly. Δεν πρόκειται για database-level immutability —
    # application code (save()/QuerySet.update()/raw SQL) μπορεί ακόμη να
    # γράψει· η προστασία αφορά τις υποστηριζόμενες Admin/API διαδρομές.
    readonly_fields = [
        'call', 'client', 'call_reference', 'phone_number',
        'action', 'description', 'created_at',
    ]

    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Read-only μέσω admin: crafted POST στο change view → 403
        # (η προβολή γίνεται μέσω view permission). ΔΕΝ αποτρέπει
        # application-level save()/update() — βλ. σχόλιο readonly_fields.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def call_link(self, obj):
        if obj.call_id is None:
            # Η κλήση έχει διαγραφεί — το log διατηρείται ως audit trail
            label = obj.phone_number or obj.call_reference or ''
            if label:
                return f'📞 (διαγραμμένη κλήση: {label})'
            return '📞 (διαγραμμένη κλήση)'
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
    mark_as_assigned.allowed_permissions = ('change',)

    def mark_as_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'⏳ {updated} tickets marked as in progress')
    mark_as_in_progress.short_description = '⏳ In Progress'
    mark_as_in_progress.allowed_permissions = ('change',)

    def mark_as_resolved(self, request, queryset):
        updated = 0
        for ticket in queryset:
            ticket.mark_as_resolved()
            updated += 1
        self.message_user(request, f'✅ {updated} tickets resolved')
    mark_as_resolved.short_description = '✅ Resolved'
    mark_as_resolved.allowed_permissions = ('change',)

    def mark_as_closed(self, request, queryset):
        updated = 0
        for ticket in queryset:
            ticket.mark_as_closed()
            updated += 1
        self.message_user(request, f'🔒 {updated} tickets closed')
    mark_as_closed.short_description = '🔒 Closed'
    mark_as_closed.allowed_permissions = ('change',)

    def has_export_permission(self, request):
        # Επωνυμίες πελατών στο CSV — θέλει το ξεχωριστό export permission
        return request.user.has_perm('accounting.export_clientprofile')

    def has_delete_permission(self, request, obj=None):
        # Το pre_delete signal του Ticket ΤΡΟΠΟΠΟΙΕΙ το συνδεδεμένο
        # VoIPCall (ticket_created=False) — καλύπτει και τα built-in
        # delete_selected / object delete_view. Χωρίς κλήση, αρκεί το
        # delete_ticket.
        base = super().has_delete_permission(request, obj)
        if not base:
            return False
        if obj is not None and obj.call_id is None:
            return True
        return request.user.has_perm('accounting.change_voipcall')

    def has_delete_cascade_calls_permission(self, request):
        # Η ενέργεια διαγράφει tickets ΚΑΙ τις κλήσεις τους — AND μέσω
        # custom handler (τα πολλαπλά allowed_permissions είναι OR)
        return (self.has_delete_permission(request)
                and request.user.has_perm('accounting.delete_voipcall'))

    def delete_queryset(self, request, queryset):
        # built-in delete_selected: το pre_delete signal ΜΕΤΑΒΑΛΛΕΙ τις
        # συνδεδεμένες κλήσεις — cross-side strict validation, atomic.
        # Ενιαία σειρά κλειδώματος call → ticket (deadlock fix).
        from django.db import transaction
        ticket_ids = list(queryset.values_list('pk', flat=True))
        with transaction.atomic():
            calls, tickets = _lock_calls_then_tickets(ticket_ids)
            _require_access(request, tickets, strict=False)
            _require_access(request, calls, strict=True)
            super().delete_queryset(
                request, Ticket.objects.filter(pk__in=ticket_ids))

    def delete_model(self, request, obj):
        # standard object delete view: cross-side validation ΠΑΝΩ στο
        # locked row (TOCTOU). Το call_id προκύπτει ΜΟΝΟ από το locked
        # ticket — όχι από το stale obj που φόρτωσε ο Django.
        # Ενιαία σειρά κλειδώματος call → ticket (deadlock fix).
        from django.db import transaction
        with transaction.atomic():
            calls, tickets = _lock_calls_then_tickets([obj.pk])
            if not tickets:
                return  # εξαφανίστηκε ενδιάμεσα — no-op fail closed
            locked_ticket = tickets[0]
            _require_access(request, [locked_ticket], strict=False)
            _require_access(request, calls, strict=True)
            super().delete_model(request, locked_ticket)

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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Το call FK περιορίζεται σε κλήσεις προσβάσιμων πελατών ή
        # unassigned — scoped χρήστης δεν βλέπει/επιλέγει ξένες κλήσεις
        if db_field.name == 'call':
            from django.db.models import Q
            from accounting.mixins import user_sees_all_clients
            from accounting.services.access import accessible_clients
            if not user_sees_all_clients(request.user):
                kwargs['queryset'] = VoIPCall.objects.filter(
                    Q(client__isnull=True)
                    | Q(client__in=accessible_clients(request.user))
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change and not obj.assigned_to:
            obj.assigned_to = request.user
        super().save_model(request, obj, form, change)

    # Bulk delete actions
    def delete_with_calls(self, request, queryset):
        """Διαγραφή tickets ΚΑΙ των κλήσεών τους.

        Το Ticket.call είναι SET_NULL — η διαγραφή των κλήσεων ΔΕΝ
        διαγράφει τα tickets· διαγράφονται και τα δύο ρητά, στην ίδια
        συναλλαγή (καμία μερική διαγραφή).
        """
        from django.db import transaction
        ticket_ids = list(queryset.values_list('pk', flat=True))
        with transaction.atomic():
            # Ενιαία σειρά κλειδώματος call → ticket (deadlock fix)
            calls_list, tickets = _lock_calls_then_tickets(ticket_ids)
            call_ids = [c.pk for c in calls_list]
            # Fail closed: κάθε ticket ΚΑΙ κάθε κλήση προσβάσιμα
            _require_access(request, tickets, strict=False)
            _require_access(request, calls_list, strict=True)
            # Ακριβή counts από τα locked lists (όχι το inflated .delete()[0])
            ticket_count = len(tickets)
            call_count = len(calls_list)
            _log_admin_deletions(
                request, Ticket.objects.filter(pk__in=ticket_ids))
            _log_admin_deletions(
                request, VoIPCall.objects.filter(id__in=call_ids))
            Ticket.objects.filter(pk__in=ticket_ids).delete()
            VoIPCall.objects.filter(id__in=call_ids).delete()
        self.message_user(
            request,
            f'{ticket_count} tickets και {call_count} κλήσεις διαγράφηκαν',
            messages.SUCCESS
        )
    delete_with_calls.short_description = 'Διαγραφή με κλήσεις'
    # Διαγράφει ΚΑΙ VoIPCall rows → απαιτούνται και τα δύο delete perms
    delete_with_calls.allowed_permissions = ('delete_cascade_calls',)

    def delete_without_calls(self, request, queryset):
        """Διαγραφή tickets χωρίς τις κλήσεις (signal θα ενημερώσει calls)"""
        from django.db import transaction
        ticket_ids = list(queryset.values_list('pk', flat=True))
        with transaction.atomic():
            # Το pre_delete signal ΤΡΟΠΟΠΟΙΕΙ τις συνδεδεμένες κλήσεις →
            # απαιτούν κι αυτές access. Ενιαία σειρά κλειδώματος
            # call → ticket (deadlock fix).
            calls, tickets = _lock_calls_then_tickets(ticket_ids)
            _require_access(request, tickets, strict=False)
            _require_access(request, calls, strict=True)
            count = len(tickets)
            # Deletion log ΜΟΝΟ για τα tickets — οι κλήσεις διατηρούνται
            _log_admin_deletions(
                request, Ticket.objects.filter(pk__in=ticket_ids))
            Ticket.objects.filter(pk__in=ticket_ids).delete()
        self.message_user(
            request,
            f'{count} tickets διαγράφηκαν (κλήσεις διατηρήθηκαν)',
            messages.SUCCESS
        )
    delete_without_calls.short_description = 'Διαγραφή χωρίς κλήσεις'
    delete_without_calls.allowed_permissions = ('delete',)

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
            if obj is not None:
                from django.core.exceptions import PermissionDenied
                from django.db import transaction
                with transaction.atomic():
                    # TOCTOU-safe: ΚΑΘΕ authorization & το call_id
                    # προκύπτουν ΜΟΝΟ από το locked state, ποτέ από το
                    # stale obj. Ενιαία σειρά κλειδώματος call → ticket
                    # (deadlock fix).
                    calls, tickets = _lock_calls_then_tickets([object_id])
                    locked_ticket = tickets[0] if tickets else None
                    if locked_ticket is None:
                        raise PermissionDenied
                    locked_call = calls[0] if calls else None
                    ticket_qs = Ticket.objects.filter(pk=locked_ticket.pk)
                    call_qs = (
                        VoIPCall.objects.filter(pk=locked_call.pk)
                        if locked_call is not None
                        else VoIPCall.objects.none())

                    # Re-check permissions ΠΑΝΩ στο locked state:
                    # delete_ticket (+ scoping + change_voipcall αν υπάρχει
                    # κλήση) μέσω has_delete_permission, ΚΑΙ client access
                    if not self.has_delete_permission(request, locked_ticket):
                        raise PermissionDenied
                    _require_access(request, [locked_ticket], strict=False)

                    obj_repr, obj_pk = str(locked_ticket), locked_ticket.pk
                    if locked_call is not None:
                        # Η επιλογή διαγράφει ΚΑΙ την κλήση → delete_voipcall
                        # + client access της τρέχουσας κλήσης
                        if not request.user.has_perm(
                                'accounting.delete_voipcall'):
                            raise PermissionDenied
                        _require_access(request, [locked_call], strict=True)
                        _log_admin_deletions(request, ticket_qs)
                        _log_admin_deletions(request, call_qs)
                        ticket_qs.delete()
                        call_qs.delete()
                        msg = 'Ticket και κλήση διαγράφηκαν'
                    else:
                        # Η σχέση αφαιρέθηκε ταυτόχρονα — διαγράφουμε ΜΟΝΟ
                        # το ticket, ποτέ κάποιο stale call
                        _log_admin_deletions(request, ticket_qs)
                        ticket_qs.delete()
                        msg = 'Ticket διαγράφηκε (η κλήση δεν υπάρχει πλέον)'
                self.message_user(request, msg, messages.SUCCESS)
                return self.response_delete(request, obj_repr, obj_pk)

        return super().delete_view(request, object_id, extra_context)
