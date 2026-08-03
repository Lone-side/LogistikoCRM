# -*- coding: utf-8 -*-
"""
Obligation-related admin classes for accounting app.

Contains:
- ObligationGroupAdmin
- ObligationProfileAdmin
- ObligationTypeAdmin
- ClientObligationAdmin
- MonthlyObligationAdmin
"""
import os
import csv
from datetime import datetime

from django.urls import reverse, path
from django.utils.html import format_html, escape
from django.contrib import admin
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone

from ..models import (
    ObligationGroup,
    ObligationProfile,
    ObligationType,
    ClientObligation,
    MonthlyObligation,
)
from ..forms import (
    GenerateObligationsForm,
    BulkAssignForm,
    ClientObligationForm,
    ObligationGroupForm,
    ObligationProfileForm,
)
from .mixins import ClientDocumentInline


@admin.register(ObligationGroup)
class ObligationGroupAdmin(admin.ModelAdmin):
    form = ObligationGroupForm
    list_display = ['name', 'description', 'get_obligations_count', 'get_obligations_list']
    search_fields = ['name']

    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('name', 'description')
        }),
        ('Υποχρεώσεις Αλληλοαποκλεισμού', {
            'fields': ('obligation_types',),
            'description': '⚠️ Οι υποχρεώσεις σε αυτήν την ομάδα αλληλοαποκλείονται - ένας πελάτης μπορεί να έχει μόνο μία από αυτές.'
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        ObligationType.objects.filter(exclusion_group=obj).update(exclusion_group=None)

        selected_types = form.cleaned_data.get('obligation_types', [])
        for obl_type in selected_types:
            obl_type.exclusion_group = obj
            obl_type.save()

        messages.success(request, f'✅ Ομάδα "{obj.name}" ενημερώθηκε με {len(selected_types)} υποχρεώσεις!')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('obligationtype_set')

    def get_obligations_count(self, obj):
        return len(obj.obligationtype_set.all())
    get_obligations_count.short_description = 'Πλήθος'

    def get_obligations_list(self, obj):
        obligations = list(obj.obligationtype_set.all())
        names = [o.name for o in obligations[:3]]
        if len(obligations) > 3:
            names.append('...')
        return ', '.join(names) if names else '—'
    get_obligations_list.short_description = 'Υποχρεώσεις'


@admin.register(ObligationProfile)
class ObligationProfileAdmin(admin.ModelAdmin):
    form = ObligationProfileForm
    list_display = ['name', 'description', 'get_obligation_count', 'get_obligations_list']
    search_fields = ['name', 'description']

    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('name', 'description')
        }),
        ('Υποχρεώσεις Profile', {
            'fields': ('obligation_types',),
            'description': '💡 Όταν ένας πελάτης επιλέγει αυτό το profile, όλες οι παρακάτω υποχρεώσεις ενεργοποιούνται αυτόματα.'
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Clear current types from this profile (ManyToMany)
        obj.obligation_types.clear()

        # Add selected types
        selected_types = form.cleaned_data.get('obligation_types', [])
        for obl_type in selected_types:
            obl_type.profiles.add(obj)

        messages.success(request, f'✅ Profile "{obj.name}" ενημερώθηκε με {len(selected_types)} υποχρεώσεις!')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('obligation_types')

    def get_obligation_count(self, obj):
        return len(obj.obligation_types.all())
    get_obligation_count.short_description = 'Πλήθος'

    def get_obligations_list(self, obj):
        obligations = list(obj.obligation_types.all())
        names = [o.name for o in obligations[:3]]
        if len(obligations) > 3:
            names.append('...')
        return ', '.join(names) if names else '—'
    get_obligations_list.short_description = 'Υποχρεώσεις'


@admin.register(ObligationType)
class ObligationTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'frequency', 'deadline_type', 'get_profiles', 'exclusion_group', 'is_active', 'priority']
    list_filter = ['frequency', 'is_active', 'profiles', 'exclusion_group']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('exclusion_group').prefetch_related('profiles')

    def get_profiles(self, obj):
        return ', '.join([p.name for p in obj.profiles.all()]) or '—'
    get_profiles.short_description = 'Profiles'
    search_fields = ['name', 'code']
    list_editable = ['priority', 'is_active']

    fieldsets = (
        ('Βασικά', {
            'fields': ('name', 'code', 'description', 'is_active', 'priority')
        }),
        ('Χρονικά', {
            'fields': ('frequency', 'deadline_type', 'deadline_day', 'applicable_months')
        }),
        ('Σχέσεις', {
            'fields': ('exclusion_group', 'profile')
        }),
    )


@admin.register(ClientObligation)
class ClientObligationAdmin(admin.ModelAdmin):
    form = ClientObligationForm
    list_display = ['client', 'is_active', 'created_at']
    list_filter = ['is_active', 'obligation_profiles']
    search_fields = ['client__afm', 'client__eponimia']
    filter_horizontal = ['obligation_types', 'obligation_profiles']

    fieldsets = (
        ('Πελάτης', {
            'fields': ('client', 'is_active')
        }),
        ('Υποχρεώσεις', {
            'fields': ('obligation_profiles', 'obligation_types'),
            'description': '⚠️ Προσοχή: Δεν μπορείτε να επιλέξετε ΦΠΑ Μηνιαίο ΚΑΙ Τρίμηνο ταυτόχρονα!'
        }),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        messages.success(request, f'✅ Οι υποχρεώσεις του πελάτη {obj.client.eponimia} αποθηκεύτηκαν επιτυχώς!')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-assign/', self.admin_site.admin_view(self.bulk_assign_view),
                 name='accounting_clientobligation_bulk'),
        ]
        return custom_urls + urls

    def bulk_assign_view(self, request):
        """Μαζική ανάθεση υποχρεώσεων - Βελτιωμένο με mode επιλογής"""
        from ..models import ClientProfile

        # Στατιστικά
        total_clients = ClientProfile.objects.filter(is_active=True).count()
        clients_with_obl = ClientObligation.objects.filter(is_active=True).count()

        if request.method == 'POST':
            form = BulkAssignForm(request.POST)
            if form.is_valid():
                clients = form.cleaned_data['clients']
                profiles = form.cleaned_data['obligation_profiles']
                types = form.cleaned_data['obligation_types']
                assign_mode = form.cleaned_data.get('assign_mode', 'add')
                generate_month = form.cleaned_data.get('generate_current_month', False)

                # Validate ΦΠΑ exclusion
                all_types = list(types)
                for profile in profiles:
                    all_types.extend(profile.obligation_types.all())

                type_names = [t.name for t in all_types]
                has_monthly = any('ΦΠΑ Μηνιαίο' in name or 'ΦΠΑ ΜΗΝΙΑΙΟ' in name.upper() for name in type_names)
                has_quarterly = any('ΦΠΑ Τρίμηνο' in name or 'ΦΠΑ ΤΡΙΜΗΝΟ' in name.upper() for name in type_names)

                if has_monthly and has_quarterly:
                    messages.error(request, '❌ Δεν μπορείτε να επιλέξετε ταυτόχρονα ΦΠΑ Μηνιαίο και ΦΠΑ Τρίμηνο!')
                    return render(request, 'admin/accounting/bulk_assign.html', {
                        'form': form,
                        'title': 'Μαζική Ανάθεση Υποχρεώσεων',
                        'has_permission': True,
                        'media': self.media + form.media,
                        'total_clients': total_clients,
                        'clients_with_obl': clients_with_obl,
                    })

                created_count = 0
                updated_count = 0
                obligations_created = 0

                for client in clients:
                    client_obl, created = ClientObligation.objects.get_or_create(
                        client=client,
                        defaults={'is_active': True}
                    )

                    # Αν είναι mode αντικατάστασης, καθάρισε πρώτα
                    if assign_mode == 'replace' and not created:
                        client_obl.obligation_profiles.clear()
                        client_obl.obligation_types.clear()

                    # Προσθήκη profiles και types
                    for profile in profiles:
                        client_obl.obligation_profiles.add(profile)

                    for obl_type in types:
                        client_obl.obligation_types.add(obl_type)

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                    # Δημιουργία υποχρεώσεων τρέχοντος μήνα αν ζητήθηκε
                    if generate_month:
                        from django.utils import timezone
                        year = timezone.now().year
                        month = timezone.now().month

                        for obl_type in client_obl.get_all_obligation_types():
                            if not obl_type.applies_to_month(month):
                                continue
                            deadline = obl_type.get_deadline_for_month(year, month)
                            if not deadline:
                                continue

                            _, obl_created = MonthlyObligation.objects.get_or_create(
                                client=client,
                                obligation_type=obl_type,
                                year=year,
                                month=month,
                                defaults={'deadline': deadline, 'status': 'pending'}
                            )
                            if obl_created:
                                obligations_created += 1

                # Μήνυμα επιτυχίας
                mode_text = 'αντικαταστάθηκαν' if assign_mode == 'replace' else 'ενημερώθηκαν'
                msg = f'✅ Ανατέθηκαν υποχρεώσεις σε {len(clients)} πελάτες! '
                msg += f'(Νέοι: {created_count}, {mode_text.capitalize()}: {updated_count})'

                if generate_month and obligations_created:
                    msg += f'<br>📅 Δημιουργήθηκαν {obligations_created} μηνιαίες υποχρεώσεις για τον τρέχοντα μήνα.'

                messages.success(request, format_html(msg))
                return redirect('..')
        else:
            form = BulkAssignForm()

        context = {
            'form': form,
            'title': 'Μαζική Ανάθεση Υποχρεώσεων',
            'has_permission': True,
            'media': self.media + form.media,
            'total_clients': total_clients,
            'clients_with_obl': clients_with_obl,
        }

        return render(request, 'admin/accounting/bulk_assign.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_bulk_assign'] = True
        return super().changelist_view(request, extra_context)


@admin.register(MonthlyObligation)
class MonthlyObligationAdmin(admin.ModelAdmin):
    # Inline Documents
    inlines = [ClientDocumentInline]

    # Add email action
    actions = ['mark_as_completed', 'mark_as_pending', 'export_obligations_csv', 'send_completion_email']

    list_display = [
        'id',
        'client_display',
        'obligation_type',
        'deadline_with_icon',
        'status_badge',
        'time_spent',
        'cost_display',
        'has_attachment',
        'completed_by_display',
    ]

    # Clickable links
    list_display_links = ['id', 'obligation_type']

    # Autocomplete
    autocomplete_fields = ['client', 'obligation_type']

    # Filters
    list_filter = [
        'status',
        'year',
        'month',
        'obligation_type',
        'completed_by',
        ('deadline', admin.DateFieldListFilter),
        ('client__eidos_ipoxreou', admin.ChoicesFieldListFilter),
        ('client__is_active', admin.BooleanFieldListFilter),
        ('client__katigoria_vivlion', admin.ChoicesFieldListFilter),
    ]

    # Search
    search_fields = [
        'client__afm',
        'client__eponimia',
        'client__onoma',
        'client__email',
        'client__kinito_tilefono',
        'client__tilefono_epixeirisis_1',
        'obligation_type__name',
        'obligation_type__code',
        'notes'
    ]

    list_editable = ['time_spent']
    readonly_fields = [
        'created_at',
        'updated_at',
        'completed_by',
        'completed_date',
        'calculated_cost',
        'current_attachment'
    ]
    date_hierarchy = 'deadline'
    list_per_page = 50

    fieldsets = (
        ('Βασικά', {
            'fields': ('client', 'obligation_type', 'year', 'month', 'deadline')
        }),
        ('Κατάσταση', {
            'fields': ('status', 'completed_date', 'completed_by')
        }),
        ('Χρέωση', {
            'fields': ('time_spent', 'hourly_rate', 'calculated_cost'),
        }),
        ('Σημειώσεις & Αρχεία', {
            'fields': ('notes', 'current_attachment', 'attachment'),
        }),
    )

    # ============================================
    # DISPLAY METHODS
    # ============================================

    def client_display(self, obj):
        """Πελάτης με link και επιπλέον πληροφορίες"""
        url = reverse('admin:accounting_clientprofile_change', args=[obj.client.id])

        # Badge για active/inactive
        active_badge = ''
        if not obj.client.is_active:
            active_badge = '<span style="background: #ef4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; margin-left: 5px;">ΑΝΕΝΕΡΓΟΣ</span>'

        return format_html(
            '<a href="{}" style="font-weight: 600; color: #667eea; text-decoration: none;">'
            '👤 {}'
            '</a>{}<br>'
            '<small style="color: #666;">ΑΦΜ: {} • {}</small>',
            url,
            escape(obj.client.eponimia),
            active_badge,
            escape(obj.client.afm),
            escape(obj.client.get_eidos_ipoxreou_display())
        )
    client_display.short_description = '👤 Πελάτης'
    client_display.admin_order_field = 'client__eponimia'

    def status_badge(self, obj):
        """Status με έγχρωμο badge"""
        colors = {
            'pending': ('#f59e0b', '⏳', 'Εκκρεμεί'),
            'completed': ('#10b981', '✅', 'Ολοκληρώθηκε'),
            'overdue': ('#ef4444', '🔴', 'Καθυστερεί'),
        }
        color, icon, label = colors.get(obj.status, ('#666', '?', obj.status))
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 12px; font-weight: 600; font-size: 0.85em;">{} {}</span>',
            color, icon, label
        )
    status_badge.short_description = 'Κατάσταση'
    status_badge.admin_order_field = 'status'

    def completed_by_display(self, obj):
        """Completed by με avatar-style"""
        if obj.completed_by:
            initials = ''.join([word[0].upper() for word in obj.completed_by.get_full_name().split()[:2]]) if obj.completed_by.get_full_name() else obj.completed_by.username[0].upper()
            return format_html(
                '<div style="display: inline-flex; align-items: center;">'
                '<span style="background: #667eea; color: white; width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-weight: 600; font-size: 0.75em; margin-right: 6px;">{}</span>'
                '<span style="font-size: 0.9em;">{}</span>'
                '</div>',
                initials,
                obj.completed_by.get_full_name() or obj.completed_by.username
            )
        return '—'
    completed_by_display.short_description = '✓ Από'
    completed_by_display.admin_order_field = 'completed_by'

    def current_attachment(self, obj):
        """Display current attachment"""
        if obj.attachment:
            filename = os.path.basename(obj.attachment.name)
            try:
                file_size = round(obj.attachment.size / 1024, 1)
            except Exception:
                file_size = '—'

            return format_html(
                '<div style="padding: 10px; background: #f0f8ff; border-radius: 6px; border-left: 4px solid #667eea;">'
                '<strong>📎 Τρέχον Αρχείο:</strong><br>'
                '<a href="{}" target="_blank" style="color: #667eea; font-weight: 600; text-decoration: none;">{}</a>'
                '<div style="font-size: 12px; color: #666; margin-top: 5px;">Μέγεθος: {} KB</div>'
                '</div>',
                obj.attachment.url,
                escape(filename),
                file_size
            )
        return "—"
    current_attachment.short_description = 'Συνημμένο'

    def calculated_cost(self, obj):
        """Show calculated cost"""
        try:
            if obj.cost:
                cost_value = float(obj.cost)
                return format_html(
                    '<span style="font-weight: 600; color: #059669;">€{:.2f}</span>',
                    cost_value
                )
        except (TypeError, ValueError, AttributeError):
            pass
        return "—"
    calculated_cost.short_description = 'Υπολογισμένο Κόστος'

    def cost_display(self, obj):
        """For list display"""
        try:
            if obj.cost:
                cost_value = float(obj.cost)
                return format_html(
                    '<span style="font-weight: 600; color: #059669;">€{:.2f}</span>',
                    cost_value
                )
        except (TypeError, ValueError, AttributeError):
            pass
        return "—"
    cost_display.short_description = 'Κόστος'
    cost_display.admin_order_field = 'time_spent'

    def has_attachment(self, obj):
        """Show attachment indicator in list"""
        if obj.attachment:
            return format_html('<span style="font-size: 1.2em;">📎</span>')
        return format_html('<span style="color: #ccc;">—</span>')
    has_attachment.short_description = 'Αρχείο'

    def deadline_with_icon(self, obj):
        """Deadline με χρωματιστό icon και countdown"""
        if obj.status == 'completed':
            return format_html(
                '<span style="color: #10b981; font-weight: 600;">✅ {}</span><br>'
                '<small style="color: #666;">Ολοκληρώθηκε {}</small>',
                obj.deadline.strftime('%d/%m/%Y'),
                obj.completed_date.strftime('%d/%m/%Y') if obj.completed_date else ''
            )

        days = obj.days_until_deadline
        if days < 0:
            icon = '🔴'
            color = '#dc3545'
            text = f'Καθυστερεί {abs(days)} ημέρες'
            urgency = 'ΕΠΕΙΓΟΝ!'
        elif days == 0:
            icon = '⚠️'
            color = '#ffc107'
            text = 'Λήγει ΣΗΜΕΡΑ'
            urgency = 'ΣΗΜΕΡΑ!'
        elif days <= 3:
            icon = '🟡'
            color = '#ffc107'
            text = f'Απομένουν {days} ημέρες'
            urgency = 'Προσοχή'
        else:
            icon = '🟢'
            color = '#28a745'
            text = f'Απομένουν {days} ημέρες'
            urgency = ''

        return format_html(
            '{} <span style="color: {}; font-weight: 600;">{}</span><br>'
            '<small style="color: {}; font-weight: 600;">{}</small>'
            '{}',
            icon,
            color,
            obj.deadline.strftime('%d/%m/%Y'),
            color,
            text,
            f'<br><small style="background: {color}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; font-weight: 600;">{urgency}</small>' if urgency else ''
        )
    deadline_with_icon.short_description = '📅 Προθεσμία'
    deadline_with_icon.admin_order_field = 'deadline'

    # ============================================
    # ACTIONS
    # ============================================

    @admin.action(description='✓ Ολοκλήρωση επιλεγμένων')
    def mark_as_completed(self, request, queryset):
        updated = queryset.filter(status__in=['pending', 'overdue']).update(
            status='completed',
            completed_date=timezone.now().date(),
            completed_by=request.user
        )
        self.message_user(request, f'✅ Ολοκληρώθηκαν {updated} υποχρεώσεις!', messages.SUCCESS)

    @admin.action(description='↺ Επαναφορά σε εκκρεμεί')
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(
            status='pending',
            completed_date=None,
            completed_by=None
        )
        self.message_user(request, f'↺ Επαναφέρθηκαν {updated} υποχρεώσεις!', messages.SUCCESS)

    def has_export_permission(self, request):
        # Το CSV περιέχει ΑΦΜ/επωνυμίες — θέλει το ξεχωριστό export permission
        return request.user.has_perm('accounting.export_clientprofile')

    @admin.action(description='📊 Export σε CSV', permissions=['export'])
    def export_obligations_csv(self, request, queryset):
        """Export obligations to CSV"""
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="obligations_{datetime.now().strftime("%Y%m%d")}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Πελάτης',
            'ΑΦΜ',
            'Είδος Υπόχρεου',
            'Ενεργός',
            'Υποχρέωση',
            'Κωδικός',
            'Μήνας',
            'Έτος',
            'Προθεσμία',
            'Κατάσταση',
            'Χρόνος (ώρες)',
            'Ωριαία Χρέωση (€)',
            'Κόστος (€)',
            'Ολοκληρώθηκε',
            'Από'
        ])

        for obl in queryset.select_related('client', 'obligation_type', 'completed_by'):
            writer.writerow([
                obl.client.eponimia,
                obl.client.afm,
                obl.client.get_eidos_ipoxreou_display(),
                'Ναι' if obl.client.is_active else 'Όχι',
                obl.obligation_type.name,
                obl.obligation_type.code,
                obl.month,
                obl.year,
                obl.deadline.strftime('%d/%m/%Y'),
                obl.get_status_display(),
                obl.time_spent or '',
                obl.hourly_rate or '',
                f"{obl.cost:.2f}" if obl.cost else '',
                obl.completed_date.strftime('%d/%m/%Y') if obl.completed_date else '',
                obl.completed_by.get_full_name() if obl.completed_by else ''
            ])

        self.message_user(request, f'✅ Εξήχθησαν {queryset.count()} υποχρεώσεις', messages.SUCCESS)
        return response

    @admin.action(description='📧 Αποστολή email ολοκλήρωσης')
    def send_completion_email(self, request, queryset):
        """Send completion email for selected obligations"""
        from accounting.services.email_service import EmailService

        sent = 0
        failed = 0
        skipped = 0

        for obligation in queryset.select_related('client', 'obligation_type'):
            # Only send for completed obligations
            if obligation.status != 'completed':
                skipped += 1
                continue

            # Skip if no client email
            if not obligation.client.email:
                skipped += 1
                continue

            success, result = EmailService.send_obligation_completion_email(
                obligation=obligation,
                user=request.user,
                include_attachment=True
            )

            if success:
                sent += 1
            else:
                failed += 1

        # Report results
        if sent > 0:
            self.message_user(request, f'📧 Στάλθηκαν {sent} email επιτυχώς!', messages.SUCCESS)
        if skipped > 0:
            self.message_user(request, f'⏭️ Παραλείφθηκαν {skipped} (μη ολοκληρωμένες ή χωρίς email)', messages.WARNING)
        if failed > 0:
            self.message_user(request, f'❌ Απέτυχαν {failed} email', messages.ERROR)

    def save_model(self, request, obj, form, change):
        if obj.status == 'completed' and not obj.completed_by:
            obj.completed_by = request.user
            obj.completed_date = timezone.now().date()

        # Νέο αρχείο από το (deprecated) πεδίο attachment → ClientDocument
        if 'attachment' in form.changed_data and obj.attachment:
            super().save_model(request, obj, form, change)
            try:
                import os
                from django.core.files import File
                from ..services import filing
                upload = File(obj.attachment.file, name=os.path.basename(obj.attachment.name))
                document = filing.create_client_document(
                    client=obj.client,
                    uploaded_file=upload,
                    obligation=obj,
                    user=request.user,
                )
                self.message_user(request, f'📁 Το αρχείο αρχειοθετήθηκε: {document.filename}', messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f'⚠️ Σφάλμα αρχειοθέτησης: {e}', messages.WARNING)
        else:
            super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('generate/', self.admin_site.admin_view(self.generate_obligations_view),
                 name='accounting_monthlyobligation_generate'),
        ]
        return custom_urls + urls

    def generate_obligations_view(self, request):
        """Custom view για δημιουργία μηνιαίων υποχρεώσεων - Βελτιωμένο"""
        from ..models import ClientProfile
        from ..forms import MONTH_CHOICES

        # Στατιστικά για warnings
        total_active_clients = ClientProfile.objects.filter(is_active=True).count()
        clients_with_obligations = ClientObligation.objects.filter(is_active=True).count()
        clients_without_obligations = total_active_clients - clients_with_obligations

        if request.method == 'POST':
            form = GenerateObligationsForm(request.POST)
            if form.is_valid():
                year = form.cleaned_data['year']
                month = form.cleaned_data['month']
                selected_clients = form.cleaned_data.get('clients')
                selected_types = form.cleaned_data.get('obligation_types')

                created_count = 0
                skipped_count = 0
                stats_by_type = {}

                # Αν επιλέχθηκαν συγκεκριμένοι πελάτες, χρησιμοποίησέ τους
                if selected_clients:
                    client_obligations = selected_clients
                else:
                    client_obligations = ClientObligation.objects.filter(is_active=True)

                for client_obl in client_obligations:
                    client = client_obl.client
                    obligation_types = client_obl.get_all_obligation_types()

                    # Αν επιλέχθηκαν συγκεκριμένοι τύποι, φιλτράρισε
                    if selected_types:
                        obligation_types = [t for t in obligation_types if t in selected_types]

                    for obligation_type in obligation_types:
                        if not obligation_type.applies_to_month(month):
                            continue

                        deadline = obligation_type.get_deadline_for_month(year, month)

                        if not deadline:
                            continue

                        monthly_obl, created = MonthlyObligation.objects.get_or_create(
                            client=client,
                            obligation_type=obligation_type,
                            year=year,
                            month=month,
                            defaults={
                                'deadline': deadline,
                                'status': 'pending'
                            }
                        )

                        # Στατιστικά ανά τύπο
                        type_name = obligation_type.name
                        if type_name not in stats_by_type:
                            stats_by_type[type_name] = {'created': 0, 'skipped': 0}

                        if created:
                            created_count += 1
                            stats_by_type[type_name]['created'] += 1
                        else:
                            skipped_count += 1
                            stats_by_type[type_name]['skipped'] += 1

                # Μήνυμα επιτυχίας με αναλυτικά στατιστικά
                month_name = dict(MONTH_CHOICES).get(month, month)
                msg = f'✅ Δημιουργήθηκαν {created_count} νέες υποχρεώσεις για {month_name} {year}. '
                msg += f'({skipped_count} υπήρχαν ήδη)'

                if stats_by_type:
                    msg += '<br><br><strong>Ανά τύπο:</strong><ul>'
                    for type_name, stats in sorted(stats_by_type.items()):
                        msg += f'<li>{type_name}: {stats["created"]} νέες'
                        if stats["skipped"]:
                            msg += f' ({stats["skipped"]} υπήρχαν)'
                        msg += '</li>'
                    msg += '</ul>'

                messages.success(request, format_html(msg))
                return redirect('..')
        else:
            form = GenerateObligationsForm()

        context = {
            'form': form,
            'title': 'Δημιουργία Μηνιαίων Υποχρεώσεων',
            'has_permission': True,
            'media': self.media + form.media,
            # Στατιστικά για το template
            'total_active_clients': total_active_clients,
            'clients_with_obligations': clients_with_obligations,
            'clients_without_obligations': clients_without_obligations,
        }

        return render(request, 'admin/accounting/generate_obligations.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_generate_button'] = True
        return super().changelist_view(request, extra_context)

    # ============================================
    # OPTIMIZE QUERYSET
    # ============================================

    def get_queryset(self, request):
        """Optimize queries με select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('client', 'obligation_type', 'completed_by')
