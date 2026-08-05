# -*- coding: utf-8 -*-
"""
Email Service for LogistikoCRM
Author: ddiplas
Version: 3.0
Description: Complete email service with retry logic, rate limiting,
             connection pooling, and async support via Celery.

Features:
- Retry with exponential backoff (2s, 4s, 8s delays, max 3 retries)
- Rate limiting (2 emails/sec default)
- Connection pooling for bulk sends
- Async email queue via Celery
- Comprehensive logging with EmailLog model
"""

from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
import logging
import time

from accounting.services.access import mask_pii_value
from .email_utils import (
    retry_with_backoff,
    get_rate_limiter,
    get_connection_pool,
    BulkEmailSender,
    EmailError,
    EmailConnectionError,
    EmailPermanentError,
    RETRIABLE_EXCEPTIONS,
    PERMANENT_EXCEPTIONS,
)

logger = logging.getLogger(__name__)


class EmailService:
    """
    Service class for sending templated emails from the CRM.

    Features:
    - Retry with exponential backoff for transient failures
    - Rate limiting to prevent SMTP throttling
    - Connection pooling for bulk sends
    - Async sending via Celery (optional)
    - Email logging with EmailLog model
    - Template rendering with {variable} syntax
    - Preview functionality
    - Attachment support
    - Database-stored settings (EmailSettings model)
    """

    # Default settings (can be overridden in Django settings)
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 2.0
    DEFAULT_RATE_LIMIT = 2.0  # emails per second

    @staticmethod
    def _get_email_settings():
        """
        Get email settings from database (preferred) or Django settings (fallback).
        Returns tuple: (settings_obj_or_none, from_email, from_name, smtp_config)
        """
        from accounting.models import EmailSettings

        try:
            email_settings = EmailSettings.get_settings()

            # Check if settings are configured and active
            if email_settings.is_active and email_settings.smtp_host and email_settings.from_email:
                smtp_config = email_settings.get_smtp_config()
                from_email = email_settings.from_email
                from_name = email_settings.from_name or ''
                return email_settings, from_email, from_name, smtp_config
        except Exception as e:
            logger.warning(f"Could not load EmailSettings from database: {e}")

        # Fallback to Django settings
        return None, getattr(settings, 'DEFAULT_FROM_EMAIL', ''), '', None

    @staticmethod
    def _get_email_connection(smtp_config=None):
        """
        Get an email connection.
        If smtp_config is provided, create custom connection.
        Otherwise use default Django connection.
        """
        if smtp_config:
            return get_connection(
                host=smtp_config['host'],
                port=smtp_config['port'],
                username=smtp_config['username'],
                password=smtp_config['password'],
                use_tls=smtp_config['use_tls'],
                use_ssl=smtp_config['use_ssl'],
            )
        return get_connection()

    @staticmethod
    def get_context_for_obligation(obligation, user=None):
        """
        Build context dictionary for an obligation.

        Args:
            obligation: MonthlyObligation instance
            user: Optional User who is sending the email

        Returns:
            dict with all available template variables
        """
        client = obligation.client
        obl_type = obligation.obligation_type

        # Greek month names
        month_names = {
            1: 'Ιανουάριος', 2: 'Φεβρουάριος', 3: 'Μάρτιος',
            4: 'Απρίλιος', 5: 'Μάιος', 6: 'Ιούνιος',
            7: 'Ιούλιος', 8: 'Αύγουστος', 9: 'Σεπτέμβριος',
            10: 'Οκτώβριος', 11: 'Νοέμβριος', 12: 'Δεκέμβριος'
        }

        context = {
            # Client variables
            'client_name': client.eponimia,
            'client_afm': client.afm,
            'client_email': client.email or '',
            'client_phone': client.kinito_tilefono or client.tilefono_epixeirisis_1 or '',

            # Obligation variables
            'obligation_type': obl_type.name if obl_type else '',
            'obligation_code': obl_type.code if obl_type else '',
            'period_month': f"{obligation.month:02d}",
            'period_month_name': month_names.get(obligation.month, ''),
            'period_year': str(obligation.year),
            'period_display': f"{obligation.month:02d}/{obligation.year}",
            'deadline': obligation.deadline.strftime('%d/%m/%Y') if obligation.deadline else '',
            'completed_date': timezone.now().date().strftime('%d/%m/%Y'),

            # Company/Accountant variables (from settings)
            'accountant_name': getattr(settings, 'ACCOUNTANT_NAME', 'Λογιστικό Γραφείο'),
            'accountant_title': getattr(settings, 'ACCOUNTANT_TITLE', ''),
            'company_name': getattr(settings, 'COMPANY_NAME', 'Λογιστικό Γραφείο'),
            'company_phone': getattr(settings, 'COMPANY_PHONE', ''),
            'company_website': getattr(settings, 'COMPANY_WEBSITE', ''),
            'email_signature': getattr(settings, 'EMAIL_SIGNATURE', ''),

            # User who sent the email
            'sender_name': user.get_full_name() if user else getattr(settings, 'ACCOUNTANT_NAME', ''),
        }

        return context

    @staticmethod
    def render_template(template, obligation=None, client=None, extra_context=None, user=None):
        """
        Render an email template with the given context.

        Args:
            template: EmailTemplate instance
            obligation: Optional MonthlyObligation instance
            client: Optional ClientProfile instance (used if no obligation)
            extra_context: Optional dict with additional context variables
            user: Optional User who is sending

        Returns:
            tuple: (rendered_subject, rendered_body)
        """
        context = {}

        # Build context from obligation
        if obligation:
            context = EmailService.get_context_for_obligation(obligation, user)
        elif client:
            # Build minimal context from client
            context = {
                'client_name': client.eponimia,
                'client_afm': client.afm,
                'client_email': client.email or '',
                'accountant_name': getattr(settings, 'ACCOUNTANT_NAME', 'Λογιστικό Γραφείο'),
                'company_name': getattr(settings, 'COMPANY_NAME', 'Λογιστικό Γραφείο'),
                'completed_date': timezone.now().date().strftime('%d/%m/%Y'),
            }

        # Add any extra context
        if extra_context:
            context.update(extra_context)

        # Render using simple {variable} syntax
        return template.render_simple(context)

    @staticmethod
    def _prepare_email_message(
        recipient_email,
        subject,
        body,
        html_body=None,
        attachments=None,
        from_email=None,
        from_name=None,
        reply_to=None,
        connection=None,
        append_signature=True
    ):
        """
        Prepare an EmailMessage object.

        Args:
            recipient_email: Email address to send to
            subject: Email subject
            body: Email body (HTML or plain text)
            html_body: Optional separate HTML body
            attachments: Optional list of attachments
            from_email: Optional sender email (uses settings if not provided)
            from_name: Optional sender name
            reply_to: Optional reply-to email
            connection: Optional email connection
            append_signature: Whether to append email signature (default True)

        Returns:
            EmailMessage or EmailMultiAlternatives instance
        """
        # Determine from_email
        if not from_email:
            from_email = settings.DEFAULT_FROM_EMAIL

        # Format from_email with name if provided
        if from_name:
            formatted_from = f"{from_name} <{from_email}>"
        else:
            formatted_from = from_email

        # Append email signature if enabled
        if append_signature:
            try:
                from accounting.models import EmailSettings
                email_settings = EmailSettings.get_settings()
                if email_settings and email_settings.email_signature:
                    signature_html = f'<div class="email-signature" style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb;">{email_settings.email_signature}</div>'
                    body = f'{body}{signature_html}'
                    if html_body:
                        html_body = f'{html_body}{signature_html}'
            except Exception as e:
                logger.warning(f"Could not append email signature: {e}")

        if html_body:
            # Send as multipart (plain + HTML)
            email = EmailMultiAlternatives(
                subject=subject,
                body=strip_tags(body),  # Plain text version
                from_email=formatted_from,
                to=[recipient_email],
                connection=connection
            )
            email.attach_alternative(html_body, "text/html")
        else:
            # Send as HTML
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=formatted_from,
                to=[recipient_email],
                connection=connection
            )
            email.content_subtype = 'html'

        # Add reply-to header if provided
        if reply_to:
            email.reply_to = [reply_to]

        # Add attachments
        if attachments:
            for attachment in attachments:
                if isinstance(attachment, str):
                    # File path
                    try:
                        email.attach_file(attachment)
                    except Exception as e:
                        logger.warning(f"Could not attach file {attachment}: {e}")
                elif isinstance(attachment, tuple) and len(attachment) == 3:
                    # (filename, content, mimetype)
                    email.attach(*attachment)
                elif hasattr(attachment, 'path'):
                    # Django FileField
                    try:
                        email.attach_file(attachment.path)
                    except Exception as e:
                        logger.warning(f"Could not attach FileField {attachment}: {e}")

        return email

    @staticmethod
    @retry_with_backoff(
        max_retries=3,
        base_delay=2.0,
        max_delay=30.0,
        retriable_exceptions=RETRIABLE_EXCEPTIONS,
        permanent_exceptions=PERMANENT_EXCEPTIONS
    )
    def _send_with_retry(email_message, use_rate_limit=True):
        """
        Send email with retry logic.
        This method is decorated with @retry_with_backoff.

        Args:
            email_message: Prepared EmailMessage instance
            use_rate_limit: Whether to apply rate limiting

        Returns:
            int: Number of emails sent (0 or 1)

        Raises:
            EmailConnectionError: On retriable failures after max retries
            EmailPermanentError: On permanent failures (auth, invalid recipient)
        """
        if use_rate_limit:
            rate_limiter = get_rate_limiter()
            rate_limiter.wait()

        return email_message.send(fail_silently=False)

    @staticmethod
    def send_email(
        recipient_email,
        subject,
        body,
        client=None,
        obligation=None,
        template=None,
        user=None,
        attachments=None,
        html_body=None,
        use_retry=True,
        use_rate_limit=True,
        async_send=False,
    ):
        """
        Send an email and log it.

        Args:
            recipient_email: Email address to send to
            subject: Email subject
            body: Email body (HTML or plain text)
            client: Optional ClientProfile for logging
            obligation: Optional MonthlyObligation for logging
            template: Optional EmailTemplate used
            user: Optional User who is sending
            attachments: Optional list of file paths or (filename, content, mimetype) tuples
            html_body: Optional separate HTML body (if body is plain text)
            use_retry: Whether to use retry logic (default True)
            use_rate_limit: Whether to apply rate limiting (default True)
            async_send: Whether to send asynchronously via Celery (default False)

        Returns:
            tuple: (success: bool, email_log: EmailLog or error_message: str)
        """
        from accounting.models import EmailLog

        # Create email log entry
        email_log = EmailLog.objects.create(
            recipient_email=recipient_email,
            recipient_name=client.eponimia if client else recipient_email,
            client=client,
            obligation=obligation,
            template_used=template,
            subject=subject,
            body=body,
            status='pending',
            sent_by=user
        )

        # If async, queue for later
        if async_send:
            try:
                from accounting.tasks import send_email_async
                send_email_async.delay(email_log.id)
                email_log.status = 'queued'
                email_log.save()
                logger.info(f"📧 Email queued for async send: {mask_pii_value(recipient_email)}")
                return True, email_log
            except Exception as e:
                logger.warning(f"Could not queue email, sending synchronously: {e}")
                # Fall through to sync send

        try:
            # Get email settings from database (preferred) or Django settings (fallback)
            db_settings, from_email, from_name, smtp_config = EmailService._get_email_settings()

            # Check if using console backend (for testing)
            is_console_backend = getattr(settings, 'EMAIL_BACKEND', '').endswith('console.EmailBackend')
            is_locmem_backend = getattr(settings, 'EMAIL_BACKEND', '').endswith('locmem.EmailBackend')

            # Check email configuration
            if smtp_config:
                # Using database settings
                if not smtp_config['host']:
                    raise ValueError("SMTP Host δεν έχει οριστεί στις ρυθμίσεις")
                if not smtp_config['password'] and not is_console_backend and not is_locmem_backend:
                    logger.warning("SMTP Password δεν έχει οριστεί - email ίσως αποτύχει")
                connection = EmailService._get_email_connection(smtp_config)
                reply_to = db_settings.reply_to if db_settings and db_settings.reply_to else None
            else:
                # Using Django settings as fallback
                if not getattr(settings, 'EMAIL_HOST', None):
                    raise ValueError("EMAIL_HOST δεν έχει οριστεί στις ρυθμίσεις")
                if not is_console_backend and not is_locmem_backend:
                    if not getattr(settings, 'EMAIL_HOST_PASSWORD', ''):
                        logger.warning("EMAIL_HOST_PASSWORD δεν έχει οριστεί - email ίσως αποτύχει")
                connection = None
                reply_to = None

            # Prepare email message
            email = EmailService._prepare_email_message(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                html_body=html_body,
                attachments=attachments,
                from_email=from_email,
                from_name=from_name,
                reply_to=reply_to,
                connection=connection
            )

            # Send with or without retry
            if use_retry and not is_console_backend and not is_locmem_backend:
                sent = EmailService._send_with_retry(email, use_rate_limit=use_rate_limit)
            else:
                if use_rate_limit and not is_console_backend and not is_locmem_backend:
                    rate_limiter = get_rate_limiter()
                    rate_limiter.wait()
                sent = email.send(fail_silently=False)

            # Update log as sent
            email_log.status = 'sent'
            email_log.retry_count = 0  # Success on first try or after retries
            email_log.save()

            logger.info(f"✅ Email sent to {mask_pii_value(recipient_email)}: {subject}")
            return True, email_log

        except EmailPermanentError as e:
            # Permanent failure - don't retry
            email_log.status = 'failed'
            email_log.error_message = f"Permanent error: {str(e)}"
            email_log.save()
            logger.error(f"❌ Permanent email failure to {mask_pii_value(recipient_email)}: {e}")
            return False, str(e)

        except EmailConnectionError as e:
            # Failed after all retries
            email_log.status = 'failed'
            email_log.error_message = f"Connection error after retries: {str(e)}"
            email_log.retry_count = getattr(e, 'attempt', 0)
            email_log.save()
            logger.error(f"❌ Email failed after retries to {mask_pii_value(recipient_email)}: {e}")
            return False, str(e)

        except Exception as e:
            # Update log as failed
            email_log.status = 'failed'
            email_log.error_message = str(e)
            email_log.save()

            logger.error(f"❌ Failed to send email to {mask_pii_value(recipient_email)}: {e}")
            return False, str(e)

    @staticmethod
    def send_email_from_log(email_log_id):
        """
        Send an email from an existing EmailLog entry (for async/retry).

        Args:
            email_log_id: ID of the EmailLog entry

        Returns:
            tuple: (success: bool, error_message or None)
        """
        from accounting.models import EmailLog

        try:
            email_log = EmailLog.objects.get(id=email_log_id)
        except EmailLog.DoesNotExist:
            logger.error(f"EmailLog {email_log_id} not found")
            return False, "Email log not found"

        if email_log.status == 'sent':
            logger.info(f"Email {email_log_id} already sent")
            return True, None

        try:
            # Prepare email
            email = EmailService._prepare_email_message(
                recipient_email=email_log.recipient_email,
                subject=email_log.subject,
                body=email_log.body,
            )

            # Send with retry
            EmailService._send_with_retry(email, use_rate_limit=True)

            # Update log
            email_log.status = 'sent'
            email_log.save()

            logger.info(f"✅ Email {email_log_id} sent successfully")
            return True, None

        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            email_log.retry_count = (email_log.retry_count or 0) + 1
            email_log.save()

            logger.error(f"❌ Failed to send email {email_log_id}: {e}")
            return False, str(e)

    @staticmethod
    def send_obligation_completion_email(obligation, user=None, include_attachment=True, async_send=False):
        """
        Send completion notification for an obligation.

        Args:
            obligation: MonthlyObligation instance
            user: Optional User who completed the obligation
            include_attachment: Whether to include the obligation attachment
            async_send: Whether to send asynchronously

        Returns:
            tuple: (success: bool, email_log or error_message)
        """
        from accounting.models import EmailTemplate

        client = obligation.client

        # Check if client has email
        if not client.email:
            logger.warning(f"Cannot send email for {obligation}: client has no email")
            return False, "Ο πελάτης δεν έχει email"

        # Get appropriate template
        template = EmailTemplate.get_template_for_obligation(obligation)

        if not template:
            logger.warning(f"No email template found for {obligation}")
            return False, "Δεν βρέθηκε πρότυπο email"

        # Render template
        subject, body = EmailService.render_template(
            template=template,
            obligation=obligation,
            user=user
        )

        # Prepare attachments - use new unified document system
        attachments = []
        if include_attachment:
            try:
                # New: Get attachments from ClientDocument via get_email_attachments()
                email_attachments = obligation.get_email_attachments()
                attachments.extend(email_attachments)
            except Exception as e:
                logger.warning(f"Could not add attachments: {e}")

        # Send email
        return EmailService.send_email(
            recipient_email=client.email,
            subject=subject,
            body=body,
            client=client,
            obligation=obligation,
            template=template,
            user=user,
            attachments=attachments,
            async_send=async_send
        )

    @staticmethod
    def preview_email(template, obligation=None, client=None, extra_context=None, user=None):
        """
        Preview email without sending.

        Returns:
            dict with 'subject', 'body', and 'recipient'
        """
        subject, body = EmailService.render_template(
            template=template,
            obligation=obligation,
            client=client,
            extra_context=extra_context,
            user=user
        )

        recipient = ''
        if obligation and obligation.client:
            recipient = obligation.client.email or ''
        elif client:
            recipient = client.email or ''

        return {
            'subject': subject,
            'body': body,
            'recipient': recipient,
            'recipient_name': client.eponimia if client else (obligation.client.eponimia if obligation else ''),
        }

    @staticmethod
    def send_bulk_emails(
        obligations,
        template=None,
        user=None,
        include_attachments=True,
        use_connection_pool=True
    ):
        """
        Send emails for multiple obligations with connection pooling.

        Args:
            obligations: QuerySet or list of MonthlyObligation instances
            template: Optional specific template (otherwise auto-selects)
            user: User who is sending
            include_attachments: Whether to include obligation attachments
            use_connection_pool: Whether to use connection pooling (faster for bulk)

        Returns:
            dict with 'sent', 'failed', 'skipped' counts and 'details' list
        """
        from accounting.models import EmailTemplate, EmailLog

        results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }

        obligations_list = list(obligations)

        if not obligations_list:
            return results

        # Use connection pooling for efficiency
        if use_connection_pool and len(obligations_list) > 1:
            try:
                with BulkEmailSender(use_pool=True, use_rate_limit=True) as sender:
                    for obligation in obligations_list:
                        result = EmailService._send_single_bulk_email(
                            obligation=obligation,
                            template=template,
                            user=user,
                            include_attachments=include_attachments,
                            sender=sender,
                            results=results
                        )
            except Exception as e:
                logger.error(f"Bulk email error: {e}")
                # Fall back to individual sends for remaining
                for obligation in obligations_list[results['sent'] + results['failed'] + results['skipped']:]:
                    EmailService._send_single_bulk_email(
                        obligation=obligation,
                        template=template,
                        user=user,
                        include_attachments=include_attachments,
                        sender=None,
                        results=results
                    )
        else:
            # Single email or pool disabled - send individually
            for obligation in obligations_list:
                EmailService._send_single_bulk_email(
                    obligation=obligation,
                    template=template,
                    user=user,
                    include_attachments=include_attachments,
                    sender=None,
                    results=results
                )

        logger.info(
            f"Bulk email results: sent={results['sent']}, "
            f"failed={results['failed']}, skipped={results['skipped']}"
        )
        return results

    @staticmethod
    def _send_single_bulk_email(obligation, template, user, include_attachments, sender, results):
        """
        Helper to send a single email in a bulk operation.
        """
        from accounting.models import EmailTemplate, EmailLog

        client = obligation.client

        # Skip if no email
        if not client.email:
            results['skipped'] += 1
            results['details'].append({
                'obligation_id': obligation.id,
                'client': client.eponimia,
                'status': 'skipped',
                'message': 'Δεν υπάρχει email'
            })
            return

        # Use specific template or find appropriate one
        email_template = template
        if not email_template:
            email_template = EmailTemplate.get_template_for_obligation(obligation)

        if not email_template:
            results['failed'] += 1
            results['details'].append({
                'obligation_id': obligation.id,
                'client': client.eponimia,
                'status': 'failed',
                'message': 'Δεν βρέθηκε πρότυπο'
            })
            return

        # Render template
        subject, body = EmailService.render_template(
            template=email_template,
            obligation=obligation,
            user=user
        )

        # Prepare attachments - use new unified document system
        attachments = []
        if include_attachments:
            try:
                email_attachments = obligation.get_email_attachments()
                attachments.extend(email_attachments)
            except Exception as e:
                logger.warning(f"Could not add attachments: {e}")

        # Create log entry
        email_log = EmailLog.objects.create(
            recipient_email=client.email,
            recipient_name=client.eponimia,
            client=client,
            obligation=obligation,
            template_used=email_template,
            subject=subject,
            body=body,
            status='pending',
            sent_by=user
        )

        try:
            # Prepare email message
            email = EmailService._prepare_email_message(
                recipient_email=client.email,
                subject=subject,
                body=body,
                attachments=attachments
            )

            # Send using bulk sender or regular method
            if sender:
                sender.send(email)
            else:
                EmailService._send_with_retry(email, use_rate_limit=True)

            # Update log
            email_log.status = 'sent'
            email_log.save()

            results['sent'] += 1
            results['details'].append({
                'obligation_id': obligation.id,
                'client': client.eponimia,
                'status': 'sent',
                'message': f'Στάλθηκε στο {client.email}'
            })

        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            email_log.save()

            results['failed'] += 1
            results['details'].append({
                'obligation_id': obligation.id,
                'client': client.eponimia,
                'status': 'failed',
                'message': str(e)
            })


# ============================================================================
# LEGACY FUNCTIONS (for backwards compatibility with existing code)
# ============================================================================

def create_scheduled_email(obligations, template, recipient_email=None, send_at=None, user=None):
    """
    Create a scheduled email for obligations.
    LEGACY: This function maintains backwards compatibility.
    For new code, use EmailService.send_email directly.
    """
    from accounting.models import ScheduledEmail

    if not obligations:
        return None

    obligations_list = list(obligations)
    client = obligations_list[0].client

    # Build context
    context = EmailService.get_context_for_obligation(obligations_list[0], user)

    # Add obligations list for multi-obligation emails
    context['obligations'] = [
        {
            'name': obl.obligation_type.name,
            'deadline': obl.deadline.strftime('%d/%m/%Y'),
            'status': obl.get_status_display(),
        }
        for obl in obligations_list
    ]

    # Render template using legacy method
    subject, body = template.render({
        'client': {
            'eponimia': client.eponimia,
            'afm': client.afm,
            'email': client.email,
        },
        'obligations': context['obligations'],
        'user': {
            'name': user.get_full_name() if user else context['accountant_name'],
        },
        **context
    })

    # Create scheduled email
    scheduled_email = ScheduledEmail.objects.create(
        recipient_email=recipient_email or client.email,
        recipient_name=client.eponimia,
        client=client,
        template=template,
        subject=subject,
        body_html=body,
        send_at=send_at or timezone.now(),
        created_by=user,
    )

    scheduled_email.obligations.set(obligations_list)

    return scheduled_email


def send_scheduled_email(email_id):
    """
    Send a scheduled email.
    LEGACY: Maintains backwards compatibility.
    Now uses retry logic.
    """
    from accounting.models import ScheduledEmail

    try:
        scheduled_email = ScheduledEmail.objects.get(pk=email_id, status='pending')
    except ScheduledEmail.DoesNotExist:
        logger.error(f"ScheduledEmail {email_id} not found or not pending")
        return False

    try:
        email = EmailMessage(
            subject=scheduled_email.subject,
            body=scheduled_email.body_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[scheduled_email.recipient_email],
        )
        email.content_subtype = 'html'

        # Attach files
        attachments = scheduled_email.get_attachments()
        for attachment in attachments:
            try:
                email.attach_file(attachment.path)
            except Exception as e:
                logger.warning(f"Could not attach file: {e}")

        # Send with retry
        EmailService._send_with_retry(email, use_rate_limit=True)
        scheduled_email.mark_as_sent()

        logger.info(f"✅ Scheduled email sent to {mask_pii_value(scheduled_email.recipient_email)}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send scheduled email {email_id}: {str(e)}")
        scheduled_email.mark_as_failed(str(e))
        return False


def trigger_automation_rules(obligation, trigger_type='on_complete'):
    """
    Trigger automation rules for an obligation.
    LEGACY: For new code, use EmailService.send_obligation_completion_email directly.
    """
    from accounting.models import EmailAutomationRule

    rules = EmailAutomationRule.objects.filter(
        is_active=True,
        trigger=trigger_type
    )

    created_emails = []

    for rule in rules:
        if not rule.matches_obligation(obligation):
            continue

        # For immediate sending, use new EmailService
        if rule.timing == 'immediate':
            success, result = EmailService.send_obligation_completion_email(
                obligation=obligation,
                user=None
            )
            if success:
                logger.info(f"📧 Email sent via rule '{rule.name}' for {obligation}")
        else:
            # For delayed/scheduled, create scheduled email
            if rule.timing == 'delay_1h':
                send_at = timezone.now() + timezone.timedelta(hours=1)
            elif rule.timing == 'delay_24h':
                send_at = timezone.now() + timezone.timedelta(days=1)
            elif rule.timing == 'scheduled' and rule.scheduled_time:
                send_at = timezone.now().replace(
                    hour=rule.scheduled_time.hour,
                    minute=rule.scheduled_time.minute,
                    second=0
                )
                if send_at < timezone.now():
                    send_at += timezone.timedelta(days=1)
            else:
                send_at = timezone.now()

            scheduled_email = create_scheduled_email(
                obligations=[obligation],
                template=rule.template,
                send_at=send_at,
                user=None
            )

            if scheduled_email:
                scheduled_email.automation_rule = rule
                scheduled_email.save()
                created_emails.append(scheduled_email)
                logger.info(f"📧 Scheduled email via rule '{rule.name}' for {obligation}")

    return created_emails
