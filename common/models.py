import os
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import NON_FIELD_ERRORS
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext

from common.utils.helpers import get_formatted_short_date


class Base(models.Model):
    class Meta:
        abstract = True

    creation_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Creation date")
    )
    update_date = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Update date")
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE,
        verbose_name=_("Owner"),
        related_name="%(app_label)s_%(class)s_owner_related",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_modified_by_related",
        verbose_name=_("Modified By")
    )

    def add_to_workflow(self, msg: str) -> None:
        f_date = get_formatted_short_date()
        self.workflow = f'{f_date} - {msg}\n' + self.workflow  # NOQA

    def validate_unique(self, exclude=None):
        """
        Overridden to handle instance re-adding exception using a form.
        """
        if hasattr(self, 'token'):
            try:
                super().validate_unique(exclude)
            except ValidationError as e:
                if 'token' in e.error_dict:
                    obj = self.__class__.objects.get(token=self.token)
                    url = obj.get_absolute_url()
                    added = _("was added successfully.")
                    blocked = _("Re-adding blocked.")
                    class_name = self._meta.verbose_name.title()
                    msg = f'{class_name} <a href="{url}">"{self}"</a> {added}<br>{blocked}'
                    raise ValidationError(mark_safe(msg))
                raise e
        else:
            super().validate_unique(exclude)


class Base1(Base):
    class Meta:
        abstract = True

    department = models.ForeignKey(
        'auth.Group',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        verbose_name=_("Department"),
        related_name="%(app_label)s_%(class)s_department_related",
    )

    def clean(self):
        if hasattr(self, 'owner') and hasattr(self, 'department'):
            if self.department and self.owner:
                owner_departments = self.owner.groups.filter(       # NOQA
                    department__isnull=False
                )
                if self.department not in owner_departments:
                    try:
                        raise ValidationError({
                            NON_FIELD_ERRORS: _("Department and Owner do not match"),
                            'department': _("Department and Owner do not match"),
                            'owner': ""
                        })
                    except Exception:
                        raise ValidationError({
                            NON_FIELD_ERRORS: _("Department and Owner do not match"),
                        })
        super().clean()


class Base2(models.Model):
    class Meta:
        abstract = True

    name = models.CharField(max_length=70, null=False, blank=False)
    department = models.ForeignKey(
        'auth.Group',
        blank=False,
        null=False,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_department_related",
    )

    def __str__(self):
        return gettext(self.name)


class Department(Group):
    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")

    default_country = models.ForeignKey(
        'crm.Country',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Default country')
    )
    default_currency = models.ForeignKey(
        'crm.Currency',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Default currency')
    )
    works_globally = models.BooleanField(
        default=False,
        verbose_name=_("Works globally"),
        help_text=_("The department operates in foreign markets.")
    )


class Reminder(models.Model):
    class Meta:
        verbose_name = _("Reminder")
        verbose_name_plural = _("Reminders")

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name='reminders'
    )
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey(
        'content_type', 'object_id'
    )

    subject = models.CharField(
        max_length=250, null=False, blank=False,
        verbose_name=_("Subject"),
        help_text=_("Briefly, what is this reminder about?")
    )
    description = models.TextField(
        blank=True, default='',
        verbose_name=_("Description")
    )
    reminder_date = models.DateTimeField(
        verbose_name=_("Reminder date")
    )
    active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    send_notification_email = models.BooleanField(
        default=True,
        verbose_name=_("Send notification email")
    )
    creation_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Creation date")
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True, null=True,
        on_delete=models.CASCADE,
        verbose_name=_("Owner"),
        related_name="%(app_label)s_%(class)s_owner_related",
    )

    def __str__(self):
        return self.subject


class TheFile(models.Model):
    class Meta:
        verbose_name = _("File")
        verbose_name_plural = _("Files")

    file = models.FileField(
        blank=True, null=True,
        verbose_name=_("Attached file"),
        upload_to='docs/%Y/%m/%d/%H%M%S/',
        max_length=250
    )
    attached_to_deal = models.BooleanField(
        default=False,
        verbose_name=_("Attach to the deal"),
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    def __str__(self):
        if self.file.name:
            return self.file.name.split(os.sep)[-1]
        return 'File'

    def delete(self, *args, **kwargs):
        file_num = TheFile.objects.filter(file=self.file).count()
        if file_num == 1:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)


class StageBase(Base2):
    class Meta:
        abstract = True
        ordering = ['index_number']
        verbose_name = _('Stage')
        verbose_name_plural = _('Stages')

    default = models.BooleanField(
        default=False,
        verbose_name=_("Default"),
        help_text=_("Will be selected by default when creating a new task")
    )
    index_number = models.SmallIntegerField(
        null=False, blank=False,
        default=1,
        help_text=_("The sequence number of the stage. \
        The indices of other instances will be sorted automatically.")
    )


def messages_default():
    return []


class UserProfile(models.Model):
    class Meta:
        verbose_name = _("User profile")
        verbose_name_plural = _("User profiles")

    TIMEZONE_CHOICES = (
        ('Etc/GMT+12', 'UTC-12:00'),
        ('Etc/GMT+11', 'UTC-11:00'),
        ('Etc/GMT+10', 'UTC-10:00'),
        ('Pacific/Marquesas', 'UTC-09:30'),
        ('Etc/GMT+9', 'UTC-09:00'),
        ('Etc/GMT+8', 'UTC-08:00'),
        ('Etc/GMT+7', 'UTC-07:00'),
        ('Etc/GMT+6', 'UTC-06:00'),
        ('Etc/GMT+5', 'UTC-05:00'),
        ('Etc/GMT+4', 'UTC-04:00'),
        ('America/St_Johns', 'UTC-03:30'),
        ('Etc/GMT+3', 'UTC-03:00'),
        ('Etc/GMT+2', 'UTC-02:00'),
        ('Etc/GMT+1', 'UTC-01:00'),
        ('Etc/GMT0', 'UTC 00:00'),
        ('Etc/GMT-1', 'UTC+01:00'),
        ('Europe/Kiev', 'UTC+02:00'),
        ('Etc/GMT-3', 'UTC+03:00'),
        ('Asia/Tehran', 'UTC+03:30'),
        ('Etc/GMT-4', 'UTC+04:00'),
        ('Asia/Kabul', 'UTC+04:30'),
        ('Etc/GMT-5', 'UTC+05:00'),
        ('Asia/Kolkata', 'UTC+05:30'),
        ('Asia/Kathmandu', 'UTC+05:45'),
        ('Etc/GMT-6', 'UTC+06:00'),
        ('Asia/Yangon', 'UTC+06:30'),
        ('Etc/GMT-7', 'UTC+07:00'),
        ('Etc/GMT-8', 'UTC+08:00'),
        ('Australia/Eucla', 'UTC+08:45'),
        ('Etc/GMT-9', 'UTC+09:00'),
        ('Australia/Darwin', 'UTC+09:30'),
        ('Etc/GMT-10', 'UTC+10:00'),
        ('Australia/Lord_Howe', 'UTC+10:30'),
        ('Etc/GMT-11', 'UTC+11:00'),
        ('Etc/GMT-12', 'UTC+12:00'),
        ('Pacific/Chatham', 'UTC+12:45'),
        ('Etc/GMT-13', 'UTC+13:00'),
        ('Etc/GMT-14', 'UTC+14:00'),
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    pbx_number = models.CharField(
        max_length=20, default='',
        null=False, blank=True,
        verbose_name=_("Phone")
    )
    utc_timezone = models.CharField(
        max_length=19, default='',
        choices=TIMEZONE_CHOICES,
        null=False, blank=True,
        verbose_name=_("UTC time zone")
    )
    activate_timezone = models.BooleanField(
        default=False,
        verbose_name=_("Activate this time zone"),
    )
    messages = models.JSONField(
        default=messages_default,
        help_text=_("Field for temporary storage of messages to the user")
    )
    language_code = models.CharField(
        max_length=7, default='',
        null=False, blank=True,
    )

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.user})"    # NOQA
    
    def get_absolute_url(self):  
        return reverse('site:common_userprofile_change', args=(self.pk,))
    
    def save(self, *args, **kwargs):
        if not self.language_code:
            self.language_code = settings.LANGUAGE_CODE
        super().save(*args, **kwargs)

# ============================================================================
# AUDIT TRAIL SYSTEM
# ============================================================================

class AuditLog(models.Model):
    """
    Comprehensive audit trail for all critical operations
    Critical for accounting office compliance
    """
    # Ρητά BigAutoField: το migration δημιούργησε bigint id ενώ το app default είναι AutoField
    id = models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')

    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('view', 'Viewed'),
        ('export', 'Exported'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('failed_login', 'Failed Login'),
        ('permission_denied', 'Permission Denied'),
    ]

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    # Who
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    username = models.CharField(max_length=150, db_index=True)

    # What
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=255, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)

    # Generic relation
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Details
    changes = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low', db_index=True)

    # When & Where
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'user']),
            models.Index(fields=['model_name', 'action']),
            models.Index(fields=['severity', '-timestamp']),
        ]
        verbose_name = _('Audit Log Entry')
        verbose_name_plural = _('Audit Log')

    def __str__(self):
        return f'{self.timestamp:%Y-%m-%d %H:%M:%S} - {self.username} - {self.get_action_display()}'

    @classmethod
    def log(cls, user, action, obj=None, changes=None, description='', severity='low', request=None):
        """Create audit log entry"""
        username = user.username if user else 'anonymous'
        ip_address = None
        user_agent = ''

        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

        log_entry = cls(
            user=user,
            username=username,
            action=action,
            description=description,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            changes=changes or {}
        )

        if obj:
            log_entry.model_name = obj.__class__.__name__
            log_entry.object_id = str(obj.pk)
            log_entry.object_repr = str(obj)[:255]
            log_entry.content_object = obj

        log_entry.save()
        return log_entry
