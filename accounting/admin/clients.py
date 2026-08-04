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
import logging
import tempfile
from datetime import datetime

from django.urls import reverse, path
from django.utils.html import format_html
from django import forms
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


logger = logging.getLogger(__name__)


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    filter_horizontal = ('assigned_users',)
    # VoIP Call History, Tickets & Documents Inline
    inlines = [VoIPCallInline, TicketInline, ClientProfileDocumentInline]

    list_display = [
        'afm',
        'eponimia',
        'eidos_ipoxreou',
        'katigoria_vivlion',
        'is_active',
        'obligations_status',
        'documents_count',
        'created_at',
        'folder_link',
        'pdf_report_link',
    ]

    def get_queryset(self, request):
        # Χωρίς αυτά το changelist κάνει 4-6 queries ανά πελάτη
        # (obligation_settings, τύποι ανά profile, documents count)
        from django.db.models import Count
        from accounting.mixins import user_sees_all_clients
        qs = super().get_queryset(request)
        if not user_sees_all_clients(request.user):
            qs = qs.filter(assigned_users=request.user).distinct()
        return qs.select_related(
            'obligation_settings'
        ).prefetch_related(
            'obligation_settings__obligation_types',
            'obligation_settings__obligation_profiles__obligation_types',
        ).annotate(_documents_count=Count('documents', distinct=True))

    def _user_can_touch(self, request, obj):
        from accounting.services.access import user_can_access_client
        return obj is None or user_can_access_client(request.user, obj)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and self._user_can_touch(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self._user_can_touch(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self._user_can_touch(request, obj)

    def get_readonly_fields(self, request, obj=None):
        # Την ανάθεση πελατών την αλλάζουν μόνο διαχειριστές (see-all χρήστες)
        from accounting.mixins import user_sees_all_clients
        readonly = list(super().get_readonly_fields(request, obj))
        if not user_sees_all_clients(request.user) and 'assigned_users' not in readonly:
            readonly.append('assigned_users')
        return readonly

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Όπως στο API: scoped χρήστης που δημιουργεί πελάτη τον παίρνει
        # αυτόματα ως ανάθεση, αλλιώς δεν θα τον έβλεπε καν μετά το save.
        # (Το assigned_users είναι readonly για scoped χρήστες, οπότε δεν
        # μπορεί να οριστεί αυθαίρετα από τη φόρμα.)
        from accounting.mixins import user_sees_all_clients
        if not change and not user_sees_all_clients(request.user):
            obj.assigned_users.add(request.user)

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
        count = getattr(obj, '_documents_count', None)
        if count is None:
            count = obj.documents.count()
        if count > 0:
            return format_html('<span style="color: #28a745; font-weight: bold;">{}</span>', count)
        return '-'

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
        ('Ανάθεση (RBAC)', {
            'fields': ('assigned_users',),
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

        # Όλα τα search branches ξεκινούν από το scoped queryset — ποτέ από
        # self.model.objects, αλλιώς scoped χρήστης ξαναφέρνει ξένους πελάτες
        # με αναζήτηση ΑΦΜ/τηλεφώνου/email (και μέσω autocomplete).
        base_qs = self.get_queryset(request)

        if search_term_clean.isdigit():
            phone_search = base_qs.filter(
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
            email_search = base_qs.filter(
                Q(email__icontains=search_term_clean)
            )
            queryset |= email_search
            use_distinct = True

        else:
            text_search = base_qs.filter(
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
    # Όλα τα exports απαιτούν το accounting.export_clientprofile — το σκέτο
    # view_clientprofile δεν επιτρέπει μαζική εξαγωγή ΑΦΜ/ΑΜΚΑ/IBAN κλπ.

    def has_export_permission(self, request):
        return request.user.has_perm('accounting.export_clientprofile')

    def export_selected(self, request, queryset):
        """Export επιλεγμένων πελατών με ΟΛΑ τα πεδία (52 fields)"""
        return export_clients_to_excel(queryset)
    export_selected.short_description = '📥 Export Επιλεγμένων (Πλήρες - 52 πεδία)'
    export_selected.allowed_permissions = ('export',)

    def export_all(self, request, queryset):
        """Export όλων των προσβάσιμων πελατών με ΟΛΑ τα πεδία (52 fields)"""
        # Scoped queryset: όχι όλο το πελατολόγιο για scoped χρήστες
        return export_clients_to_excel(self.get_queryset(request))
    export_all.short_description = '📥 Export ΟΛΩΝ (Πλήρες - 52 πεδία)'
    export_all.allowed_permissions = ('export',)

    def export_summary(self, request, queryset):
        """Export συνοπτικής λίστας (11 basic fields)"""
        return export_clients_summary_to_excel(queryset)
    export_summary.short_description = '📄 Export Επιλεγμένων (Σύνοψη - 11 πεδία)'
    export_summary.allowed_permissions = ('export',)

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
    export_to_csv.allowed_permissions = ('export',)


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
        """Import view για Excel — μόνο για χρήστες που βλέπουν όλους τους πελάτες
        (το import δημιουργεί/ενημερώνει πελάτες μαζικά, εκτός scoping)."""
        from django.core.exceptions import PermissionDenied
        from accounting.mixins import user_sees_all_clients
        # Το view_all_clients από μόνο του ΔΕΝ είναι write permission —
        # το import δημιουργεί/ενημερώνει πελάτες μαζικά
        if not user_sees_all_clients(request.user):
            raise PermissionDenied
        if not (
            request.user.has_perm('accounting.add_clientprofile')
            and request.user.has_perm('accounting.change_clientprofile')
        ):
            raise PermissionDenied
        if request.method == 'POST' and 'excel_file' in request.FILES:
            excel_file = request.FILES['excel_file']
            if not excel_file.name.lower().endswith(('.xlsx', '.xls')):
                messages.error(request, '❌ Μόνο αρχεία Excel (.xlsx, .xls)')
                return redirect('..')
            # Η εισαγωγή credentials από το αρχείο απαιτεί τα αντίστοιχα
            # credential permissions (το command γράφει ClientCredential)
            if not (
                request.user.has_perm('accounting.add_clientcredential')
                and request.user.has_perm('accounting.change_clientcredential')
            ):
                messages.error(
                    request,
                    '❌ Η εισαγωγή από Excel μπορεί να περιλαμβάνει κωδικούς '
                    'πελατών — απαιτούνται δικαιώματα credentials.',
                )
                return redirect('..')

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

            except Exception:
                logger.exception('Σφάλμα εισαγωγής πελατών από admin')
                messages.error(request, '❌ Σφάλμα κατά την εισαγωγή του αρχείου')
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

        except Exception:
            logger.exception('Σφάλμα εισαγωγής πελατών από admin')
            messages.error(request, '❌ Σφάλμα κατά την εισαγωγή του αρχείου')
            return redirect('..')

    def mass_update_view(self, request):
        """Μαζική ενημέρωση πελατών (μόνο στους προσβάσιμους)"""
        from django.core.exceptions import PermissionDenied
        if not self.has_change_permission(request):
            raise PermissionDenied
        if request.method == 'POST':
            action = request.POST.get('action')
            client_ids = request.POST.getlist('client_ids')

            clients = self.get_queryset(request).filter(id__in=client_ids)

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
            'clients': self.get_queryset(request),
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


class ClientDocumentAdminForm(forms.ModelForm):
    """Server-side validation του client/obligation/previous_version
    invariant — τα raw_id dropdowns από μόνα τους δεν αρκούν (crafted
    POST μπορεί να στείλει ID άλλου πελάτη)."""
    class Meta:
        model = ClientDocument
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        client = cleaned.get('client')
        obligation = cleaned.get('obligation')
        previous = cleaned.get('previous_version')
        if client is not None and obligation is not None \
                and obligation.client_id != client.id:
            raise forms.ValidationError(
                'Η υποχρέωση ανήκει σε διαφορετικό πελάτη από το έγγραφο.')
        if client is not None and previous is not None \
                and previous.client_id != client.id:
            raise forms.ValidationError(
                'Η προηγούμενη έκδοση ανήκει σε διαφορετικό πελάτη.')
        return cleaned


@admin.register(ClientDocument)
class ClientDocumentAdmin(admin.ModelAdmin):
    """
    Admin για έγγραφα πελατών με υποστήριξη versioning.
    """
    form = ClientDocumentAdminForm
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

            # Έλεγχος αν υπάρχει ήδη αρχείο (ΚΟΙΝΟΣ exact-conflict helper)
            from accounting.services import filing as _filing
            try:
                existing = ClientDocument.check_existing(
                    client=obj.client,
                    obligation=obj.obligation,
                    category=obj.document_category,
                    year=obj.year, month=obj.month,
                )
            except _filing.MultipleCurrentDocumentsError:
                from django.core.exceptions import ValidationError as _VErr
                raise _VErr(
                    'Υπάρχουν πολλαπλά τρέχοντα έγγραφα για αυτόν τον '
                    'συνδυασμό — απαιτείται χειροκίνητη διόρθωση.')

            if existing and 'confirm_replace' not in request.POST:
                # Θα χειριστεί στο response_add
                pass

        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        """Structural πεδία (μέρη του exact logical key) ΔΕΝ αλλάζουν από
        το admin σε υπάρχον έγγραφο — attach/detach μόνο μέσω των
        transactional services (αλλιώς θα παρακάμπτονταν locks/conflict
        checks). Το DB constraint είναι το τελικό δίχτυ."""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly += ['client', 'obligation', 'document_category',
                         'year', 'month', 'slot', 'previous_version']
        return readonly

    def get_queryset(self, request):
        """Default: μόνο τρέχουσες εκδόσεις + RBAC scoping ανά πελάτη"""
        from accounting.mixins import user_sees_all_clients
        qs = super().get_queryset(request)
        # Αν δεν υπάρχει φίλτρο is_current, δείξε μόνο τις τρέχουσες
        if 'is_current__exact' not in request.GET:
            qs = qs.filter(is_current=True)
        if not user_sees_all_clients(request.user):
            qs = qs.filter(client__assigned_users=request.user).distinct()
        return qs.select_related('client', 'obligation', 'uploaded_by')

    def _user_can_touch(self, request, obj):
        from accounting.services.access import user_can_access_client
        return obj is None or user_can_access_client(request.user, obj.client)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and self._user_can_touch(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self._user_can_touch(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self._user_can_touch(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Περιορισμός FK επιλογών σε προσβάσιμους πελάτες/αντικείμενα —
        # ισχύει και για validation των raw_id τιμών στο POST.
        from accounting.services.access import (
            accessible_clients, accessible_documents, accessible_obligations,
        )
        if db_field.name == 'client':
            kwargs['queryset'] = accessible_clients(request.user)
        elif db_field.name == 'obligation':
            kwargs['queryset'] = accessible_obligations(request.user)
        elif db_field.name == 'previous_version':
            kwargs['queryset'] = accessible_documents(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ArchiveConfiguration)
class ArchiveConfigurationAdmin(admin.ModelAdmin):
    list_display = ['obligation_type', 'filename_pattern', 'folder_pattern', 'create_subfolder']
    list_filter = ['create_subfolder', 'allow_multiple_files']
    search_fields = ['obligation_type__name', 'obligation_type__code']


# ============================================
# ΑΙΤΗΜΑΤΑ ΕΓΓΡΑΦΩΝ
# ============================================
from accounting.models import DocumentRequest, DocumentRequestItem  # noqa: E402


class DocumentRequestItemInlineFormSet(forms.BaseInlineFormSet):
    """Server-side έλεγχος: το received_document πρέπει να ανήκει στον
    πελάτη του DocumentRequest — και σε crafted POST, όχι μόνο στο dropdown."""

    def clean(self):
        super().clean()
        parent = self.instance
        parent_client_id = getattr(parent, 'client_id', None)
        for form in self.forms:
            if not getattr(form, 'cleaned_data', None) or form.cleaned_data.get('DELETE'):
                continue
            doc = form.cleaned_data.get('received_document')
            if doc is not None and parent_client_id and doc.client_id != parent_client_id:
                form.add_error(
                    'received_document',
                    'Το έγγραφο δεν ανήκει στον πελάτη του αιτήματος.',
                )


class DocumentRequestItemInline(admin.TabularInline):
    model = DocumentRequestItem
    extra = 1
    fields = ['label', 'category', 'is_received', 'received_document', 'received_at']
    readonly_fields = ['received_at']
    formset = DocumentRequestItemInlineFormSet

    def get_formset(self, request, obj=None, **kwargs):
        # ΟΧΙ instance state στο shared inline admin (cross-request leakage
        # σε ταυτόχρονα requests) — το queryset μπαίνει στο formset class που
        # δημιουργείται εδώ ανά request.
        formset = super().get_formset(request, obj, **kwargs)
        from accounting.services.access import accessible_documents
        qs = accessible_documents(request.user).select_related('client')
        if obj is not None:
            qs = qs.filter(client=obj.client)
        formset.form.base_fields['received_document'].queryset = qs
        return formset


class DocumentRequestAdminForm(forms.ModelForm):
    """Server-side cross-client έλεγχος: το shared_link πρέπει να αφορά τον
    ίδιο πελάτη με το αίτημα (και μέσω document link) — ισχύει και σε
    crafted POST, όχι μόνο στο dropdown filtering."""

    class Meta:
        model = DocumentRequest
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        link = cleaned.get('shared_link')
        client = cleaned.get('client')
        if link is not None and client is not None:
            link_client_id = link.client_id or (
                link.document.client_id if link.document_id else None
            )
            if link_client_id is not None and link_client_id != client.pk:
                self.add_error(
                    'shared_link',
                    'Το shared link δεν αντιστοιχεί στον πελάτη του αιτήματος.',
                )
        return cleaned


@admin.register(DocumentRequest)
class DocumentRequestAdmin(admin.ModelAdmin):
    form = DocumentRequestAdminForm
    list_display = ['title', 'client', 'status', 'due_date',
                    'reminder_count', 'created_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'client__eponimia', 'client__afm']
    inlines = [DocumentRequestItemInline]
    readonly_fields = ['last_reminder_sent_at', 'reminder_count',
                       'completed_at', 'created_at']

    def get_queryset(self, request):
        from accounting.mixins import user_sees_all_clients
        qs = super().get_queryset(request).select_related('client', 'created_by')
        if not user_sees_all_clients(request.user):
            qs = qs.filter(client__assigned_users=request.user).distinct()
        return qs

    def _user_can_touch(self, request, obj):
        from accounting.services.access import user_can_access_client
        return obj is None or user_can_access_client(request.user, obj.client)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and self._user_can_touch(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self._user_can_touch(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self._user_can_touch(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        from accounting.services.access import accessible_clients
        if db_field.name == 'client':
            kwargs['queryset'] = accessible_clients(request.user)
        elif db_field.name == 'shared_link':
            # Μόνο links προσβάσιμων πελατών (και μέσω document) — αλλιώς
            # scoped staff θα έδενε αίτημα πελάτη Α με link πελάτη Β
            from django.db.models import Q
            from accounting.models import SharedLink
            accessible = accessible_clients(request.user)
            kwargs['queryset'] = SharedLink.objects.select_related(
                'client', 'document__client'
            ).filter(
                Q(client__in=accessible)
                | Q(client__isnull=True, document__client__in=accessible)
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ============================================
# CLIENT CREDENTIALS (κρυπτογραφημένοι κωδικοί)
# ============================================

from ..models import ClientCredential  # noqa: E402


@admin.register(ClientCredential)
class ClientCredentialAdmin(admin.ModelAdmin):
    """Admin κωδικών πελατών — το secret δεν εμφανίζεται ποτέ."""
    list_display = ['client', 'service', 'label', 'username',
                    'has_secret_display', 'updated_at', 'updated_by']
    list_filter = ['service']
    search_fields = ['client__eponimia', 'client__afm', 'username']
    autocomplete_fields = ['client']
    exclude = ['_secret_encrypted']
    readonly_fields = ['created_at', 'updated_at', 'updated_by']

    def get_queryset(self, request):
        from accounting.mixins import user_sees_all_clients
        qs = super().get_queryset(request)
        if not user_sees_all_clients(request.user):
            qs = qs.filter(client__assigned_users=request.user).distinct()
        return qs

    def _user_can_touch(self, request, obj):
        from accounting.services.access import user_can_access_client
        return obj is None or user_can_access_client(request.user, obj.client)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and self._user_can_touch(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self._user_can_touch(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self._user_can_touch(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Στο add form ο scoped χρήστης επιλέγει μόνο ανατεθειμένους πελάτες
        from accounting.services.access import accessible_clients
        if db_field.name == 'client':
            kwargs['queryset'] = accessible_clients(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description='Έχει κωδικό', boolean=True)
    def has_secret_display(self, obj):
        return obj.has_secret
