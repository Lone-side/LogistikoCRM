# accounting/views/email_views.py
"""
Email Views
Author: ddiplas
Description: Email automation API views for bulk emails, templates, and ticket notifications
"""

import json
import logging
from datetime import datetime

from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from django.core.mail import send_mail
from django.utils.html import strip_tags
from django.conf import settings

from ..models import (
    MonthlyObligation, EmailTemplate, Ticket, ScheduledEmail,
)

from .helpers import (
    _calculate_send_time,
    _create_bulk_emails,
)
from accounting.services.access import (
    accessible_clients, accessible_documents, accessible_obligations,
)

logger = logging.getLogger(__name__)


# ============================================
# EMAIL AUTOMATION API
# ============================================

@require_http_methods(["GET"])
@staff_member_required
def api_email_templates(request):
    """
    API endpoint to get all active email templates
    """
    try:
        templates = EmailTemplate.objects.filter(is_active=True).order_by('name')

        result = [
            {
                'id': template.id,
                'name': template.name,
                'description': template.description or '',
                'subject': template.subject,
            }
            for template in templates
        ]

        logger.info(f"Email templates API: {len(result)} templates returned")
        return JsonResponse(result, safe=False)

    except Exception as e:
        logger.error(f"Error in api_email_templates: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@staff_member_required
def api_send_bulk_email(request):
    """
    Schedule bulk emails for obligations
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.send_client_email'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )

    try:
        data = json.loads(request.body)
        obligation_ids = data.get('obligation_ids', [])
        template_id = data.get('template_id')
        timing = data.get('timing', 'immediate')
        scheduled_time = data.get('scheduled_time')

        # Validate input
        if not obligation_ids or not template_id:
            return JsonResponse({
                'success': False,
                'error': 'Missing obligations or template'
            })

        # Get template
        try:
            template = EmailTemplate.objects.get(id=template_id, is_active=True)
        except EmailTemplate.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Template not found'
            })

        # Get obligations
        obligations = accessible_obligations(request.user).filter(
            id__in=obligation_ids
        ).select_related('client')

        if not obligations.exists():
            return JsonResponse({
                'success': False,
                'error': 'No obligations found'
            })

        # Calculate send time
        send_at = _calculate_send_time(timing, scheduled_time)

        # Group by client and create scheduled emails
        emails_created = _create_bulk_emails(
            obligations, template, send_at, request.user
        )

        return JsonResponse({
            'success': True,
            'emails_created': emails_created,
            'message': f'Προγραμματίστηκαν {emails_created} emails'
        })

    except Exception as e:
        logger.error(f"Error in api_send_bulk_email: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@staff_member_required
def api_email_template_detail(request, template_id):
    """
    API endpoint to get a single email template's full content
    """
    try:
        template = EmailTemplate.objects.get(id=template_id, is_active=True)

        return JsonResponse({
            'success': True,
            'id': template.id,
            'name': template.name,
            'description': template.description or '',
            'subject': template.subject,
            'body': template.body_html,
            'obligation_type': template.obligation_type.name if template.obligation_type else None,
        })

    except EmailTemplate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Template not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error in api_email_template_detail: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
@staff_member_required
def api_send_bulk_email_direct(request):
    """
    Send bulk emails directly (immediately) or schedule for later.
    Supports template variable substitution and optional attachments.

    If send_at is provided and in the future:
        - Creates a single ScheduledEmail with all recipients in BCC
    Otherwise:
        - Sends emails immediately to each recipient
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.send_client_email'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )

    from accounting.services.email_service import EmailService

    try:
        data = json.loads(request.body)
        obligation_ids = data.get('obligation_ids', [])
        subject_template = data.get('subject', '')
        body_template = data.get('body', '')
        template_id = data.get('template_id')
        include_attachments = data.get('include_attachments', True)
        send_at_str = data.get('send_at')  # ISO format datetime string

        # Validate input
        if not obligation_ids:
            return JsonResponse({
                'success': False,
                'error': 'Δεν επιλέχθηκαν υποχρεώσεις'
            })

        if not subject_template or not body_template:
            return JsonResponse({
                'success': False,
                'error': 'Απαιτείται θέμα και κείμενο email'
            })

        # Get obligations
        obligations = accessible_obligations(request.user).filter(
            id__in=obligation_ids
        ).select_related('client', 'obligation_type')

        if not obligations.exists():
            return JsonResponse({
                'success': False,
                'error': 'Δεν βρέθηκαν υποχρεώσεις'
            })

        # Get template if specified (for logging purposes)
        email_template = None
        if template_id:
            try:
                email_template = EmailTemplate.objects.get(id=template_id)
            except EmailTemplate.DoesNotExist:
                pass

        # Check if this is a scheduled email
        send_at = None
        if send_at_str:
            try:
                # Parse ISO format datetime
                send_at = datetime.fromisoformat(send_at_str.replace('Z', '+00:00'))
                # Make timezone aware if naive
                if send_at.tzinfo is None:
                    send_at = timezone.make_aware(send_at)
                # Check if in future
                if send_at <= timezone.now():
                    send_at = None  # Send immediately if not in future
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid send_at format: {send_at_str}, error: {e}")
                send_at = None

        # ============================================================
        # SCHEDULED EMAIL (BCC to all recipients)
        # ============================================================
        if send_at:
            # Collect all valid recipient emails and names
            recipient_emails = []
            recipient_names = []
            skipped_count = 0

            for obligation in obligations:
                client = obligation.client
                if client.email:
                    if client.email not in recipient_emails:  # Deduplicate
                        recipient_emails.append(client.email)
                        recipient_names.append(client.eponimia or client.email)
                else:
                    skipped_count += 1

            if not recipient_emails:
                return JsonResponse({
                    'success': False,
                    'error': 'Κανένας πελάτης δεν έχει email'
                })

            # Create ScheduledEmail record
            scheduled_email = ScheduledEmail.objects.create(
                recipient_email=', '.join(recipient_emails),
                recipient_name=', '.join(recipient_names),
                subject=subject_template,
                body_html=body_template,
                send_at=send_at,
                template=email_template,
                created_by=request.user,
                status='pending'
            )

            # Add obligations to the scheduled email
            scheduled_email.obligations.set(obligations)

            # Format datetime for display
            send_at_display = send_at.strftime('%d/%m/%Y %H:%M')
            recipient_count = len(recipient_emails)

            message = f"Προγραμματίστηκε email για {recipient_count} παραλήπτες στις {send_at_display}"
            if skipped_count > 0:
                message += f" ({skipped_count} παραλείφθηκαν - χωρίς email)"

            logger.info(f"Scheduled bulk email #{scheduled_email.id} for {recipient_count} recipients at {send_at}")

            return JsonResponse({
                'success': True,
                'message': message,
                'scheduled': True,
                'scheduled_email_id': scheduled_email.id,
                'recipient_count': recipient_count,
                'skipped': skipped_count,
                'send_at': send_at.isoformat()
            })

        # ============================================================
        # IMMEDIATE SEND (individual emails)
        # ============================================================
        results = {
            'sent': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }

        for obligation in obligations:
            client = obligation.client

            # Skip if client has no email
            if not client.email:
                results['skipped'] += 1
                results['details'].append({
                    'obligation_id': obligation.id,
                    'client': client.eponimia,
                    'status': 'skipped',
                    'message': 'Ο πελάτης δεν έχει email'
                })
                continue

            # Build context for variable substitution
            context = EmailService.get_context_for_obligation(obligation, request.user)

            # Replace variables in subject and body
            subject = subject_template
            body = body_template

            for key, value in context.items():
                placeholder = '{' + key + '}'
                subject = subject.replace(placeholder, str(value) if value else '')
                body = body.replace(placeholder, str(value) if value else '')

            # Prepare attachments
            attachments = []
            if include_attachments and obligation.attachment:
                try:
                    attachments.append(obligation.attachment)
                except Exception as e:
                    logger.warning(f"Could not add attachment for obligation {obligation.id}: {e}")

            # Send email
            success, result = EmailService.send_email(
                recipient_email=client.email,
                subject=subject,
                body=body,
                client=client,
                obligation=obligation,
                template=email_template,
                user=request.user,
                attachments=attachments
            )

            if success:
                results['sent'] += 1
                results['details'].append({
                    'obligation_id': obligation.id,
                    'client': client.eponimia,
                    'status': 'sent',
                    'message': f'Στάλθηκε στο {client.email}'
                })
            else:
                results['failed'] += 1
                results['details'].append({
                    'obligation_id': obligation.id,
                    'client': client.eponimia,
                    'status': 'failed',
                    'message': str(result)
                })

        # Build response message
        total = results['sent'] + results['failed'] + results['skipped']
        message = f"Στάλθηκαν {results['sent']}/{total} emails"
        if results['failed'] > 0:
            message += f" ({results['failed']} απέτυχαν)"
        if results['skipped'] > 0:
            message += f" ({results['skipped']} παραλείφθηκαν)"

        logger.info(f"Bulk email sent: {results['sent']} sent, {results['failed']} failed, {results['skipped']} skipped")

        return JsonResponse({
            'success': True,
            'message': message,
            'scheduled': False,
            'sent': results['sent'],
            'failed': results['failed'],
            'skipped': results['skipped'],
            'details': results['details']
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in api_send_bulk_email_direct: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@staff_member_required
@require_POST
def send_ticket_email(request):
    """Send email about ticket"""
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.send_client_email'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )

    try:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON'
            }, status=400)

        ticket_id = data.get('ticket_id')
        template_id = data.get('template_id')

        if not ticket_id or not template_id:
            return JsonResponse({
                'success': False,
                'message': 'Missing ticket_id or template_id'
            }, status=400)

        # Get ticket
        from accounting.api_voip import _scope_by_client
        ticket = _scope_by_client(Ticket.objects.all(), request.user).get(id=ticket_id)

        # Get template
        template = EmailTemplate.objects.get(id=template_id, is_active=True)

        # Prepare context
        context = {
            'ticket_id': ticket.id,
            'phone': ticket.call.phone_number,
            'client_name': ticket.client.eponimia if ticket.client else 'Unknown',
            'ticket_title': ticket.title,
            'ticket_priority': ticket.get_priority_display(),
            'ticket_status': ticket.get_status_display(),
            'user_name': request.user.get_full_name() or request.user.username,
            'company_name': settings.COMPANY_NAME,
        }

        # Render template
        subject, body = template.render(context)

        # Get recipient
        recipient = ticket.call.client_email or ticket.client.email if ticket.client else settings.DEFAULT_FROM_EMAIL

        if not recipient:
            return JsonResponse({
                'success': False,
                'message': 'Δεν υπάρχει email για αποστολή'
            }, status=400)

        # Send email
        send_mail(
            subject=subject,
            message=strip_tags(body),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=body,
            fail_silently=False,
        )

        # Log email
        ScheduledEmail.objects.create(
            recipient_email=recipient,
            recipient_name=ticket.client.eponimia if ticket.client else 'Client',
            client=ticket.client,
            template=template,
            subject=subject,
            body_html=body,
            send_at=timezone.now(),
            created_by=request.user,
            status='sent',
            sent_at=timezone.now(),
        )

        # Update ticket
        ticket.email_sent = True
        ticket.save()

        logger.info(f"Email sent for ticket #{ticket_id} to {recipient}")

        return JsonResponse({
            'success': True,
            'message': f'Email στάλθηκε στο {recipient}'
        })

    except Ticket.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Ticket δεν βρέθηκε'
        }, status=404)
    except EmailTemplate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Template δεν βρέθηκε'
        }, status=404)
    except Exception as e:
        logger.error(f"Error sending email: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Σφάλμα: {str(e)}'
        }, status=500)
