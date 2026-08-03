# accounting/forms.py

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    ClientProfile,
    ClientObligation,
    ObligationType,
    ObligationGroup,
    ObligationProfile,
    MonthlyObligation,
)


# ============================================================================
# ADMIN FORMS
# ============================================================================

MONTH_CHOICES = [
    (1, 'Ιανουάριος'),
    (2, 'Φεβρουάριος'),
    (3, 'Μάρτιος'),
    (4, 'Απρίλιος'),
    (5, 'Μάιος'),
    (6, 'Ιούνιος'),
    (7, 'Ιούλιος'),
    (8, 'Αύγουστος'),
    (9, 'Σεπτέμβριος'),
    (10, 'Οκτώβριος'),
    (11, 'Νοέμβριος'),
    (12, 'Δεκέμβριος'),
]


class GenerateObligationsForm(forms.Form):
    """Βελτιωμένη φόρμα δημιουργίας μηνιαίων υποχρεώσεων"""
    year = forms.IntegerField(
        label='Έτος',
        initial=timezone.now().year,
        min_value=2020,
        max_value=2030,
        widget=forms.NumberInput(attrs={'class': 'vIntegerField', 'style': 'width: 100px;'})
    )
    month = forms.ChoiceField(
        label='Μήνας',
        choices=MONTH_CHOICES,
        initial=timezone.now().month,
        widget=forms.Select(attrs={'class': 'vSelectField'})
    )

    # Νέο: Επιλογή πελατών (προαιρετικό - αν κενό = όλοι)
    clients = forms.ModelMultipleChoiceField(
        queryset=ClientObligation.objects.filter(is_active=True).select_related('client'),
        widget=admin.widgets.FilteredSelectMultiple('Πελάτες', False),
        label='Επιλογή Πελατών',
        required=False,
        help_text='Αφήστε κενό για όλους τους πελάτες με ενεργές υποχρεώσεις'
    )

    # Νέο: Επιλογή συγκεκριμένων τύπων (προαιρετικό)
    obligation_types = forms.ModelMultipleChoiceField(
        queryset=ObligationType.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        label='Τύποι Υποχρεώσεων',
        required=False,
        help_text='Αφήστε κενό για όλους τους τύπους που έχει ο κάθε πελάτης'
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # RBAC: μόνο ClientObligations ανατεθειμένων πελατών
        if user is not None:
            from accounting.services.access import accessible_clients
            self.fields['clients'].queryset = (
                self.fields['clients'].queryset.filter(
                    client__in=accessible_clients(user)
                )
            )

    def clean_month(self):
        """Μετατροπή σε integer"""
        return int(self.cleaned_data['month'])


ASSIGN_MODE_CHOICES = [
    ('add', '➕ Προσθήκη στις υπάρχουσες'),
    ('replace', '🔄 Αντικατάσταση υπαρχουσών'),
]


class BulkAssignForm(forms.Form):
    """Βελτιωμένη φόρμα μαζικής ανάθεσης υποχρεώσεων"""

    # Νέο: Mode επιλογής
    assign_mode = forms.ChoiceField(
        label='Τρόπος Ανάθεσης',
        choices=ASSIGN_MODE_CHOICES,
        initial='add',
        widget=forms.RadioSelect,
        help_text='Προσθήκη: διατηρεί τις υπάρχουσες υποχρεώσεις. Αντικατάσταση: αφαιρεί τις παλιές.'
    )

    clients = forms.ModelMultipleChoiceField(
        queryset=ClientProfile.objects.filter(is_active=True),
        widget=admin.widgets.FilteredSelectMultiple('Πελάτες', False),
        label='Επιλογή Πελατών',
        required=True
    )
    obligation_profiles = forms.ModelMultipleChoiceField(
        queryset=ObligationProfile.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label='Profiles Υποχρεώσεων',
        required=False
    )
    obligation_types = forms.ModelMultipleChoiceField(
        queryset=ObligationType.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        label='Μεμονωμένες Υποχρεώσεις',
        required=False
    )

    # Νέο: Δημιουργία υποχρεώσεων αμέσως
    generate_current_month = forms.BooleanField(
        label='Δημιουργία υποχρεώσεων τρέχοντος μήνα',
        required=False,
        initial=False,
        help_text='Αν επιλεγεί, θα δημιουργηθούν αυτόματα οι υποχρεώσεις για τον τρέχοντα μήνα'
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # RBAC: scoped χρήστης επιλέγει (και υποβάλλει) μόνο ανατεθειμένους
        # πελάτες — server-side, όχι μόνο στο widget
        if user is not None:
            from accounting.services.access import accessible_clients
            self.fields['clients'].queryset = (
                self.fields['clients'].queryset.filter(
                    pk__in=accessible_clients(user)
                )
            )

    def clean(self):
        cleaned_data = super().clean()
        profiles = cleaned_data.get('obligation_profiles')
        types = cleaned_data.get('obligation_types')

        if not profiles and not types:
            raise ValidationError(
                '⚠️ Πρέπει να επιλέξετε τουλάχιστον ένα Profile ή έναν τύπο υποχρέωσης!'
            )

        return cleaned_data


class ClientObligationForm(forms.ModelForm):
    """Custom form με validation για ΦΠΑ και όλα τα exclusion groups"""
    class Meta:
        model = ClientObligation
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        obligation_types = cleaned_data.get('obligation_types')

        if obligation_types:
            # ✅ ENHANCED VALIDATION: Έλεγχος για όλα τα exclusion groups
            exclusion_groups = {}
            for obl_type in obligation_types:
                if obl_type.exclusion_group:
                    group_name = obl_type.exclusion_group.name
                    if group_name not in exclusion_groups:
                        exclusion_groups[group_name] = []
                    exclusion_groups[group_name].append(obl_type.name)

            # Αν υπάρχει group με >1 υποχρέωση, error
            for group_name, type_names in exclusion_groups.items():
                if len(type_names) > 1:
                    raise forms.ValidationError(
                        f'❌ Δεν μπορείτε να επιλέξετε ταυτόχρονα: {", ".join(type_names)} '
                        f'(ανήκουν στην ομάδα αλληλοαποκλεισμού "{group_name}")'
                    )

            # Legacy ΦΠΑ validation (για backward compatibility)
            type_names = [t.name for t in obligation_types]
            has_monthly = any('ΦΠΑ Μηνιαίο' in name or 'ΦΠΑ ΜΗΝΙΑΙΟ' in name.upper() for name in type_names)
            has_quarterly = any('ΦΠΑ Τρίμηνο' in name or 'ΦΠΑ ΤΡΙΜΗΝΟ' in name.upper() for name in type_names)

            if has_monthly and has_quarterly:
                raise forms.ValidationError(
                    '❌ Δεν μπορείτε να επιλέξετε ταυτόχρονα ΦΠΑ Μηνιαίο και ΦΠΑ Τρίμηνο!'
                )

        return cleaned_data


class ObligationGroupForm(forms.ModelForm):
    """Custom form για ObligationGroup με checkboxes"""
    obligation_types = forms.ModelMultipleChoiceField(
        queryset=ObligationType.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Υποχρεώσεις στην Ομάδα',
        help_text='Επιλέξτε τις υποχρεώσεις που ανήκουν σε αυτήν την ομάδα αλληλοαποκλεισμού'
    )

    class Meta:
        model = ObligationGroup
        fields = ['name', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial['obligation_types'] = self.instance.obligationtype_set.all()


class ObligationProfileForm(forms.ModelForm):
    """Custom form για ObligationProfile με checkboxes"""
    obligation_types = forms.ModelMultipleChoiceField(
        queryset=ObligationType.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Υποχρεώσεις στο Profile',
        help_text='Επιλέξτε τις υποχρεώσεις που ενεργοποιούνται μαζί με αυτό το profile'
    )

    class Meta:
        model = ObligationProfile
        fields = ['name', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial['obligation_types'] = self.instance.obligation_types.all()


# ============================================================================
# MONTHLY OBLIGATION FORM
# ============================================================================

class MonthlyObligationAdminForm(forms.ModelForm):
    """Custom form για το Admin με έλεγχο duplicates"""

    class Meta:
        model = MonthlyObligation
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()

        # Μόνο για νέες εγγραφές
        if not self.instance.pk:
            client = cleaned_data.get('client')
            obligation_type = cleaned_data.get('obligation_type')
            year = cleaned_data.get('year')
            month = cleaned_data.get('month')

            if all([client, obligation_type, year, month]):
                exists = MonthlyObligation.objects.filter(
                    client=client,
                    obligation_type=obligation_type,
                    year=year,
                    month=month
                ).exists()

                if exists:
                    raise ValidationError({
                        '__all__': [
                            f'⚠️ Υπάρχει ήδη υποχρέωση "{obligation_type}" '
                            f'για τον πελάτη "{client}" '
                            f'για {month}/{year}!'
                        ]
                    })

        return cleaned_data
