# -*- coding: utf-8 -*-
"""
Client-related admin classes for accounting app.

Contains:
- ClientProfileAdmin
- ClientDocumentAdmin
- ArchiveConfigurationAdmin
"""
import io
import os
import csv
import tempfile
from datetime import datetime

from django.urls import reverse, path
from django.utils.html import format_html
from django.contrib import admin
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.core.management import call_command

from ..models import (
    ClientProfile,
    ClientDocument,
    ArchiveConfiguration,
    ClientObligation,
)


# ============================================
# CUSTOM FILTERS
# ============================================

class HasObligationsFilter(admin.SimpleListFilter):
    """Φίλτρο για πελάτες με/χωρίς ρυθμισμένες υποχρεώσεις"""
    title = 'Ρυθμίσεις Υποχρεώσεων'
    parameter_name = 'has_obligations'

    def lookups(self, request, model_admin):
        return (
            ('yes', '✅ Με υποχρεώσεις'),
            ('no', '⚠️ Χωρίς υποχρεώσεις'),
            ('active', '🟢 Ενεργές υποχρεώσεις'),
            ('inactive', '🔴 Ανενεργές υποχρεώσεις'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            # Πελάτες που έχουν ClientObligation
            return queryset.filter(obligation_settings__isnull=False)
        if self.value() == 'no':
            # Πελάτες που ΔΕΝ έχουν ClientObligation
            return queryset.filter(obligation_settings__isnull=True)
        if self.value() == 'active':
            # Πελάτες με ενεργό ClientObligation
            return queryset.filter(obligation_settings__is_active=True)
        if self.value() == 'inactive':
            # Πελάτες με ανενεργό ClientObligation
            return queryset.filter(obligation_settings__is_active=False)
        return queryset
from ..export_import import export_clients_to_excel, export_clients_summary_to_excel
from .mixins import VoIPCallInline, TicketInline, ClientProfileDocumentInline


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    # VoIP Call History, Tickets & Documents Inline
    inlines = [VoIPCallInline, TicketInline, ClientProfileDocumentInline]

    list_display = [
        'afm',
        'eponimia',
        'eidos_ipoxreou',
        'katigoria_vivlion',
        'is_active',
        'obligations_status',
        'tickets_count',
        'documents_count',
        'created_at',
        'folder_link',
        'pdf_report_link',
    ]

    @admin.display(description='Υποχρεώσεις')
    def obligations_status(self, obj):
        """Εμφάνιση κατάστασης υποχρεώσεων πελάτη"""
        try:
            client_obl = obj.obligation_settings
            if client_obl.is_active:
                count = len(client_obl.get_all_obligation_types())
                return format_html(
                    '<span style="background: #28a745; color: white; padding: 2px 8px; '
                    'border-radius: 10px; font-size: 11px;" title="Ενεργές υποχρεώσεις">'
                    '✅ {} τύποι</span>',
                    count
                )
            else:
                return format_html(
                    '<span style="background: #ffc107; color: #000; padding: 2px 8px; '
                    'border-radius: 10px; font-size: 11px;" title="Ανενεργές υποχρεώσεις">'
                    '⏸️ Ανενεργό</span>'
                )
        except ClientObligation.DoesNotExist:
            return format_html(
                '<a href="{}" style="background: #dc3545; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px; text-decoration: none;" '
                'title="Κλικ για ρύθμιση υποχρεώσεων">'
                '⚠️ Χωρίς</a>',
                reverse('admin:accounting_clientobligation_add') + f'?client={obj.id}'
            )

    @admin.display(description='PDF')
    def pdf_report_link(self, obj):
        """Link to download PDF report for client"""
        url = reverse('accounting:client_report_pdf', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
            'color: white; padding: 3px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; '
            'font-weight: 600;">📥 PDF</a>',
            url
        )

    @admin.display(description='📁 Φάκελος')
    def folder_link(self, obj):
        """Link to client files/archive view"""
        url = reverse('accounting:client_files', args=[obj.id])
        return format_html(
            '<a href="{}" target="_blank" style="background: #417690; '
            'color: white; padding: 3px 8px; border-radius: 4px; text-decoration: none; font-size: 11px; '
            'font-weight: 600;">📁 Αρχεία</a>',
            url
        )

    @admin.display(description='Έγγραφα')
    def documents_count(self, obj):
        """Count of client documents"""
        count = obj.documents.count()
        if count > 0:
            return format_html('<span style="color: #28a745; font-weight: bold;">{}</span>', count)
        return '-'

    @admin.display(description='🎫 Tickets')
    def tickets_count(self, obj):
        """Count of client tickets with status breakdown"""
        total = obj.voip_tickets.count()
        if total == 0:
            return format_html('<span style="color: #999;">—</span>')

        # Count open tickets (open, assigned, in_progress)
        open_count = obj.voip_tickets.filter(status__in=['open', 'assigned', 'in_progress']).count()

        if open_count > 0:
            # Has open tickets - show warning style with link
            url = reverse('admin:accounting_ticket_changelist') + f'?client__id__exact={obj.id}&status__in=open,assigned,in_progress'
            return format_html(
                '<a href="{}" style="background: #ef4444; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px; text-decoration: none; font-weight: bold;" '
                'title="{} ανοιχτά από {} συνολικά">{} 🔴</a>',
                url, open_count, total, open_count
            )
        else:
            # All closed - show success style
            url = reverse('admin:accounting_ticket_changelist') + f'?client__id__exact={obj.id}'
            return format_html(
                '<a href="{}" style="background: #10b981; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px; text-decoration: none;" '
                'title="{} tickets (όλα κλειστά)">{} ✅</a>',
                url, total, total
            )

    list_filter = [
        HasObligationsFilter,  # Νέο φίλτρο υποχρεώσεων
        'eidos_ipoxreou',
        'katigoria_vivlion',
        'agrotis',
        'is_active'
    ]

    search_fields = [
        'afm',
        'eponimia',
        'onoma',
        'email',
        'kinito_tilefono',
        'tilefono_oikias_1',
        'tilefono_epixeirisis_1',
        'doy'
    ]

    list_editable = ['is_active']

    actions = [
        'export_selected',
        'export_all',
        'export_summary',
        'export_to_csv',
        'mark_active',
        'mark_inactive',
    ]

    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('afm', 'doy', 'eponimia', 'onoma', 'onoma_patros', 'is_active')
        }),
        ('Ταυτοποίηση', {
            'fields': ('arithmos_taftotitas', 'eidos_taftotitas', 'prosopikos_arithmos',
                      'amka', 'am_ika', 'arithmos_gemi', 'arithmos_dypa'),
            'classes': ('collapse',)
        }),
        ('Προσωπικά Στοιχεία', {
            'fields': ('imerominia_gennisis', 'imerominia_gamou', 'filo'),
            'classes': ('collapse',)
        }),
        ('Διεύθυνση Κατοικίας', {
            'fields': ('diefthinsi_katoikias', 'arithmos_katoikias', 'poli_katoikias',
                      'dimos_katoikias', 'nomos_katoikias', 'tk_katoikias',
                      'tilefono_oikias_1', 'tilefono_oikias_2', 'kinito_tilefono'),
            'classes': ('collapse',)
        }),
        ('Διεύθυνση Επιχείρησης', {
            'fields': ('diefthinsi_epixeirisis', 'arithmos_epixeirisis', 'poli_epixeirisis',
                      'dimos_epixeirisis', 'nomos_epixeirisis', 'tk_epixeirisis',
                      'tilefono_epixeirisis_1', 'tilefono_epixeirisis_2', 'email'),
            'classes': ('collapse',)
        }),
        ('Τραπεζικά', {
            'fields': ('trapeza', 'iban'),
            'classes': ('collapse',)
        }),
        ('Επιχειρηματικά', {
            'fields': ('eidos_ipoxreou', 'katigoria_vivlion', 'nomiki_morfi',
                      'agrotis', 'imerominia_enarksis')
        }),
        ('Διαπιστευτήρια', {
            'fields': ('onoma_xristi_taxisnet', 'kodikos_taxisnet',
                      'onoma_xristi_ika_ergodoti', 'kodikos_ika_ergodoti',
                      'onoma_xristi_gemi', 'kodikos_gemi'),
            'classes': ('collapse',)
        }),
        ('Λοιπά', {
            'fields': ('afm_sizigou', 'afm_foreas', 'am_klidi'),
            'classes': ('collapse',)
        }),
    )

    # ============================================
    # ENHANCED AUTOCOMPLETE SEARCH
    # ============================================

    def get_search_results(self, request, queryset, search_term):
        """
        Βελτιωμένο search για autocomplete με smart matching
        """
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )

        if not search_term:
            return queryset, use_distinct

        from django.db.models import Q

        search_term_clean = search_term.strip()

        if search_term_clean.isdigit():
            phone_search = self.model.objects.filter(
                Q(afm__icontains=search_term_clean) |
                Q(kinito_tilefono__icontains=search_term_clean) |
                Q(tilefono_oikias_1__icontains=search_term_clean) |
                Q(tilefono_oikias_2__icontains=search_term_clean) |
                Q(tilefono_epixeirisis_1__icontains=search_term_clean) |
                Q(tilefono_epixeirisis_2__icontains=search_term_clean)
            )
            queryset |= phone_search
            use_distinct = True

        elif '@' in search_term_clean:
            email_search = self.model.objects.filter(
                Q(email__icontains=search_term_clean)
            )
            queryset |= email_search
            use_distinct = True

        else:
            text_search = self.model.objects.filter(
                Q(eponimia__icontains=search_term_clean) |
                Q(onoma__icontains=search_term_clean) |
                Q(onoma_patros__icontains=search_term_clean) |
                Q(doy__icontains=search_term_clean) |
                Q(poli_katoikias__icontains=search_term_clean) |
                Q(poli_epixeirisis__icontains=search_term_clean)
            )
            queryset |= text_search
            use_distinct = True

        return queryset, use_distinct

    # ============================================
    # EXPORT ACTIONS
    # ============================================

    def export_selected(self, request, queryset):
        """Export επιλεγμένων πελατών με ΟΛΑ τα πεδία (52 fields)"""
        return export_clients_to_excel(queryset)
    export_selected.short_description = '📥 Export Επιλεγμένων (Πλήρες - 52 πεδία)'

    def export_all(self, request, queryset):
        """Export όλων των πελατών με ΟΛΑ τα πεδία (52 fields)"""
        return export_clients_to_excel()  # No queryset = όλοι
    export_all.short_description = '📥 Export ΟΛΩΝ (Πλήρες - 52 πεδία)'

    def export_summary(self, request, queryset):
        """Export συνοπτικής λίστας (11 basic fields)"""
        return export_clients_summary_to_excel(queryset)
    export_summary.short_description = '📄 Export Επιλεγμένων (Σύνοψη - 11 πεδία)'

    def export_to_csv(self, request, queryset):
        """Export to CSV - Enhanced με περισσότερα πεδία"""
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="clients_{datetime.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)

        # ENHANCED HEADERS - 25 πεδία αντί για 11
        writer.writerow([
            'ΑΦΜ',
            'ΔΟΥ',
            'Επωνυμία',
            'Όνομα',
            'Όνομα Πατρός',
            'Είδος Υπόχρεου',
            'Κατηγορία Βιβλίων',
            'Νομική Μορφή',
            'Αγρότης',
            'Email',
            'Κινητό',
            'Τηλ. Οικίας',
            'Τηλ. Επιχείρησης',
            'Διεύθυνση Κατοικίας',
            'Πόλη Κατοικίας',
            'ΤΚ Κατοικίας',
            'Διεύθυνση Επιχείρησης',
            'Πόλη Επιχείρησης',
            'ΤΚ Επιχείρησης',
            'Τράπεζα',
            'IBAN',
            'ΑΜΚΑ',
            'ΑΜ ΙΚΑ',
            'Ενεργός',
            'Δημιουργήθηκε'
        ])

        for client in queryset.select_related():
            writer.writerow([
                client.afm,
                client.doy or '',
                client.eponimia,
                client.onoma or '',
                client.onoma_patros or '',
                client.get_eidos_ipoxreou_display(),
                client.get_katigoria_vivlion_display() if client.katigoria_vivlion else '',
                client.nomiki_morfi or '',
                'ΝΑΙ' if client.agrotis else 'ΟΧΙ',
                client.email or '',
                client.kinito_tilefono or '',
                client.tilefono_oikias_1 or '',
                client.tilefono_epixeirisis_1 or '',
                client.diefthinsi_katoikias or '',
                client.poli_katoikias or '',
                client.tk_katoikias or '',
                client.diefthinsi_epixeirisis or '',
                client.poli_epixeirisis or '',
                client.tk_epixeirisis or '',
                client.trapeza or '',
                client.iban or '',
                client.amka or '',
                client.am_ika or '',
                'Ναι' if client.is_active else 'Όχι',
                client.created_at.strftime('%d/%m/%Y %H:%M') if client.created_at else ''
            ])

        self.message_user(request, f'✅ Εξήχθησαν {queryset.count()} πελάτες σε CSV (25 πεδία)', messages.SUCCESS)
        return response
    export_to_csv.short_description = '📊 Export σε CSV'


    def mark_active(self, request, queryset):
        """Ενεργοποίηση πελατών"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'✅ Ενεργοποιήθηκαν {updated} πελάτες', messages.SUCCESS)
    mark_active.short_description = '✅ Ενεργοποίηση'

    def mark_inactive(self, request, queryset):
        """Απενεργοποίηση πελατών"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'⚠️ Απενεργοποιήθηκαν {updated} πελάτες', messages.WARNING)
    mark_inactive.short_description = '❌ Απενεργοποίηση'

    # ============================================
    # CUSTOM URLS
    # ============================================

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import/', self.admin_site.admin_view(self.import_view),
                 name='accounting_clientprofile_import'),
            path('download-template/', self.admin_site.admin_view(self.download_template),
                 name='accounting_clientprofile_template'),
            path('mass-update/', self.admin_site.admin_view(self.mass_update_view),
                 name='accounting_clientprofile_mass_update'),
        ]
        return custom_urls + urls

    def import_view(self, request):
        """Import view για Excel"""
        if request.method == 'POST' and 'excel_file' in request.FILES:
            excel_file = request.FILES['excel_file']

            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                for chunk in excel_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            try:
                out = io.StringIO()
                call_command('import_clients', tmp_path, stdout=out)

                output = out.getvalue()

                if '✅' in output or 'Ολοκληρώθηκε' in output:
                    messages.success(request, output)
                else:
                    messages.warning(request, output)

            except Exception as e:
                messages.error(request, f'❌ Σφάλμα: {str(e)}')
            finally:
                os.unlink(tmp_path)

            return redirect('..')

        context = {
            'title': 'Import Πελατών από Excel',
            'has_permission': True,
        }
        return render(request, 'admin/accounting/import_clients.html', context)

    def download_template(self, request):
        """Download template Excel"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                tmp_path = tmp.name

            call_command('create_excel_template', tmp_path)

            with open(tmp_path, 'rb') as f:
                response = HttpResponse(
                    f.read(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="Template_Pelaton_{datetime.now().strftime("%Y%m%d")}.xlsx"'

            os.unlink(tmp_path)
            return response

        except Exception as e:
            messages.error(request, f'❌ Σφάλμα: {str(e)}')
            return redirect('..')

    def mass_update_view(self, request):
        """Μαζική ενημέρωση πελατών"""
        if request.method == 'POST':
            action = request.POST.get('action')
            client_ids = request.POST.getlist('client_ids')

            clients = ClientProfile.objects.filter(id__in=client_ids)

            if action == 'activate':
                clients.update(is_active=True)
                messages.success(request, f'✅ Ενεργοποιήθηκαν {clients.count()} πελάτες')
            elif action == 'deactivate':
                clients.update(is_active=False)
                messages.warning(request, f'⚠️ Απενεργοποιήθηκαν {clients.count()} πελάτες')
            elif action == 'change_category':
                new_category = request.POST.get('new_category')
                clients.update(katigoria_vivlion=new_category)
                messages.success(request, f'✅ Αλλαγή κατηγορίας σε {clients.count()} πελάτες')
            elif action == 'change_type':
                new_type = request.POST.get('new_type')
                clients.update(eidos_ipoxreou=new_type)
                messages.success(request, f'✅ Αλλαγή τύπου σε {clients.count()} πελάτες')

            return redirect('..')

        context = {
            'title': 'Μαζική Ενημέρωση Πελατών',
            'clients': ClientProfile.objects.all(),
            'has_permission': True,
        }
        return render(request, 'admin/accounting/mass_update.html', context)

    def changelist_view(self, request, extra_context=None):
        """Προσθήκη buttons στο changelist"""
        extra_context = extra_context or {}
        extra_context.update({
            'show_import_export': True,
        })
        return super().changelist_view(request, extra_context)


@admin.register(ClientDocument)
class ClientDocumentAdmin(admin.ModelAdmin):
    """
    Admin για έγγραφα πελατών με υποστήριξη versioning.
    """
    list_display = [
        'filename',
        'client_link',
        'document_category',
        'period_display',
        'version_display',
        'file_size_display',
        'uploaded_at',
        'open_folder_button',
    ]
    list_filter = [
        'document_category',
        'file_type',
        'is_current',
        'year',
        ('uploaded_at', admin.DateFieldListFilter),
    ]
    search_fields = [
        'client__eponimia',
        'client__afm',
        'filename',
        'original_filename',
        'description'
    ]
    raw_id_fields = ['client', 'obligation', 'previous_version']
    readonly_fields = [
        'filename',
        'original_filename',
        'file_type',
        'file_size',
        'version',
        'is_current',
        'uploaded_at',
        'uploaded_by',
        'folder_path_display',
        'version_history',
    ]
    list_per_page = 50
    date_hierarchy = 'uploaded_at'

    fieldsets = (
        ('Αρχείο', {
            'fields': ('file', 'original_filename', 'filename', 'file_type', 'file_size')
        }),
        ('Σχέσεις', {
            'fields': ('client', 'obligation', 'document_category')
        }),
        ('Περίοδος', {
            'fields': ('year', 'month')
        }),
        ('Versioning', {
            'fields': ('version', 'is_current', 'previous_version', 'version_history'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('description', 'uploaded_at', 'uploaded_by', 'folder_path_display'),
            'classes': ('collapse',)
        }),
    )

    actions = ['show_all_versions', 'mark_as_current']

    # === Custom Display Methods ===

    @admin.display(description='Πελάτης')
    def client_link(self, obj):
        """Link στον πελάτη"""
        if obj.client:
            url = reverse('admin:accounting_clientprofile_change', args=[obj.client.id])
            return format_html('<a href="{}">{}</a>', url, obj.client.eponimia[:30])
        return '-'

    @admin.display(description='Περίοδος')
    def period_display(self, obj):
        """Εμφάνιση περιόδου ΜΜ/ΕΕΕΕ"""
        return f"{obj.month:02d}/{obj.year}"

    @admin.display(description='Έκδοση')
    def version_display(self, obj):
        """Εμφάνιση έκδοσης με status"""
        if obj.is_current:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">v{} ✓</span>',
                obj.version
            )
        return format_html(
            '<span style="color: #999;">v{}</span>',
            obj.version
        )

    @admin.display(description='Μέγεθος')
    def file_size_display(self, obj):
        """Human-readable file size"""
        return obj.file_size_display

    @admin.display(description='📁')
    def open_folder_button(self, obj):
        """Button για άνοιγμα φακέλου"""
        if obj.folder_path:
            # URL για view που θα επιστρέψει το path
            url = reverse('accounting:open_document_folder', args=[obj.id])
            return format_html(
                '<a href="{}" target="_blank" title="Άνοιγμα φακέλου: {}" '
                'style="background: #417690; color: white; padding: 2px 6px; '
                'border-radius: 3px; text-decoration: none; font-size: 10px;">📁</a>',
                url, obj.folder_path
            )
        return '-'

    @admin.display(description='Folder Path')
    def folder_path_display(self, obj):
        """Εμφάνιση πλήρους path"""
        if obj.folder_path:
            return format_html(
                '<code style="background: #f4f4f4; padding: 4px 8px; '
                'border-radius: 3px; font-size: 11px;">{}</code>',
                obj.folder_path
            )
        return '-'

    @admin.display(description='Ιστορικό Εκδόσεων')
    def version_history(self, obj):
        """Εμφάνιση όλων των εκδόσεων"""
        versions = obj.get_all_versions()
        if len(versions) <= 1:
            return 'Μόνο μία έκδοση'

        html = '<ul style="margin: 0; padding-left: 20px;">'
        for v in versions:
            status = '✓ Τρέχουσα' if v.is_current else ''
            url = reverse('admin:accounting_clientdocument_change', args=[v.id])
            html += f'<li><a href="{url}">v{v.version}</a> - {v.uploaded_at.strftime("%d/%m/%Y %H:%M")} {status}</li>'
        html += '</ul>'
        return format_html(html)

    # === Actions ===

    @admin.action(description='📜 Εμφάνιση όλων των εκδόσεων')
    def show_all_versions(self, request, queryset):
        """Φιλτράρισμα για εμφάνιση όλων των εκδόσεων"""
        # Redirect στο changelist με φίλτρο
        messages.info(request, f'Επιλέξατε {queryset.count()} έγγραφα')

    @admin.action(description='✓ Ορισμός ως τρέχουσα έκδοση')
    def mark_as_current(self, request, queryset):
        """Ορίζει τα επιλεγμένα ως τρέχουσες εκδόσεις"""
        for doc in queryset:
            # Βρες όλες τις εκδόσεις του ίδιου αρχείου
            ClientDocument.objects.filter(
                client=doc.client,
                obligation=doc.obligation,
                document_category=doc.document_category,
                year=doc.year,
                month=doc.month,
            ).update(is_current=False)

            # Όρισε αυτό ως τρέχον
            doc.is_current = True
            doc.save(update_fields=['is_current'])

        messages.success(request, f'✅ Ορίστηκαν {queryset.count()} ως τρέχουσες εκδόσεις')

    # === Override save_model for versioning ===

    def save_model(self, request, obj, form, change):
        """
        Κατά το save, ελέγχουμε αν υπάρχει ήδη αρχείο και ρωτάμε για versioning.
        """
        # Αν είναι νέο document
        if not change:
            obj.uploaded_by = request.user

            # Έλεγχος αν υπάρχει ήδη αρχείο για αυτόν τον συνδυασμό
            existing = ClientDocument.check_existing(
                client=obj.client,
                obligation=obj.obligation,
                category=obj.document_category if obj.document_category != 'general' else None
            )

            if existing and 'confirm_replace' not in request.POST:
                # Θα χειριστεί στο response_add
                pass

        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        """Default: εμφάνιση μόνο τρεχουσών εκδόσεων εκτός αν φιλτράρει"""
        qs = super().get_queryset(request)
        # Αν δεν υπάρχει φίλτρο is_current, δείξε μόνο τις τρέχουσες
        if 'is_current__exact' not in request.GET:
            qs = qs.filter(is_current=True)
        return qs.select_related('client', 'obligation', 'uploaded_by')


@admin.register(ArchiveConfiguration)
class ArchiveConfigurationAdmin(admin.ModelAdmin):
    list_display = ['obligation_type', 'filename_pattern', 'folder_pattern', 'create_subfolder']
    list_filter = ['create_subfolder', 'allow_multiple_files']
    search_fields = ['obligation_type__name', 'obligation_type__code']
