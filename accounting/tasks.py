# accounting/tasks.py
"""
VoIP & Ticket Management Tasks
Background tasks for auto-ticket creation, email reminders, and summaries
"""

from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from django.conf import settings
from datetime import timedelta
from .models import VoIPCall, Ticket, VoIPCallLog, MonthlyObligation, EmailTemplate, ScheduledEmail
import logging

logger = logging.getLogger(__name__)


# ============================================
# TASK 1: SMART TICKET FOR MISSED CALL
# ============================================

@shared_task(bind=True, max_retries=3)
def create_or_update_ticket_for_missed_call(self, call_id):
    """
    SMART TICKET CREATION:
    - Αν υπάρχει ανοιχτό ticket από ίδιο αριθμό → UPDATE
    - Αν δεν υπάρχει → CREATE NEW
    - ΔΕΝ στέλνει email σε κάθε κλήση
    """
    try:
        call = VoIPCall.objects.get(id=call_id)
        
        if call.status != 'missed':
            logger.info(f"Call #{call_id} is not missed - skipping")
            return None
        
        # ========== CHECK FOR EXISTING OPEN TICKET ==========
        time_threshold = timezone.now() - timedelta(hours=24)
        
        existing_ticket = Ticket.objects.filter(
            call__phone_number=call.phone_number,
            status__in=['open', 'assigned', 'in_progress'],
            created_at__gte=time_threshold
        ).order_by('-created_at').first()
        
        if existing_ticket:
            # ========== UPDATE EXISTING TICKET ==========
            logger.info(f"Found existing ticket #{existing_ticket.id} for {call.phone_number}")
            
            missed_count = VoIPCall.objects.filter(
                phone_number=call.phone_number,
                status='missed',
                started_at__gte=time_threshold
            ).count()
            
            existing_ticket.title = f"🔴 MISSED CALLS ({missed_count}x) - {call.phone_number}"
            
            timestamp = call.started_at.strftime('%d/%m %H:%M')
            new_note = f"[{timestamp}] Νέα αναπάντητη κλήση (Σύνολο: {missed_count})"
            
            if existing_ticket.notes:
                existing_ticket.notes += f"\n{new_note}"
            else:
                existing_ticket.notes = new_note
            
            if missed_count >= 3 and existing_ticket.priority != 'urgent':
                existing_ticket.priority = 'urgent'
                existing_ticket.notes += "\n⚠️ Αυξήθηκε η προτεραιότητα λόγω πολλαπλών κλήσεων"
            
            existing_ticket.save()
            
            VoIPCallLog.objects.create(
                call=call,
                action='ticket_updated',
                description=f"Updated ticket #{existing_ticket.id} (call #{missed_count})"
            )
            
            call.ticket_created = True
            call.ticket_id = existing_ticket.id
            call.save()
            
            return existing_ticket.id
            
        else:
            # ========== CREATE NEW TICKET ==========
            logger.info(f"Creating new ticket for {call.phone_number}")
            
            ticket = Ticket.objects.create(
                call=call,
                client=call.client,
                title=f"🔴 MISSED CALL - {call.phone_number}",
                description=f"Αναπάντητη κλήση από {call.phone_number}\nΏρα: {call.started_at.strftime('%d/%m/%Y %H:%M')}",
                priority='high',
                status='open',
                assigned_to=None,
            )
            
            call.ticket_created = True
            call.ticket_id = ticket.id
            call.save()
            
            VoIPCallLog.objects.create(
                call=call,
                action='ticket_created',
                description=f"New ticket #{ticket.id} for missed call"
            )
            
            logger.info(f"✅ Ticket #{ticket.id} created for {call.phone_number}")
            return ticket.id
            
    except VoIPCall.DoesNotExist:
        logger.error(f"❌ Call #{call_id} not found")
        return None
    except Exception as exc:
        logger.error(f"❌ Error in ticket creation: {exc}")
        self.retry(exc=exc, countdown=60)


# ============================================
# TASK 2: AUTO-CREATE TICKET FOR ANSWERED CALL
# ============================================

@shared_task(bind=True, max_retries=3)
def create_ticket_for_answered_call(self, call_id, user_id=None):
    """
    Auto-create ticket για ANSWERED/COMPLETED call
    Priority: MEDIUM (needs follow-up)
    Status: OPEN (waiting for notes/resolution)
    Assigned: The user who answered (if provided)
    """
    try:
        call = VoIPCall.objects.get(id=call_id)
        
        # Only for completed/active calls
        if call.status not in ['completed', 'active']:
            logger.info(f"Call #{call_id} status is {call.status} - skipping")
            return None
        
        # Skip if already has ticket
        if Ticket.objects.filter(call=call).exists():
            logger.info(f"Ticket already exists for call #{call_id}")
            return Ticket.objects.get(call=call).id
        
        # Get assigned user if provided
        assigned_user = None
        if user_id:
            try:
                assigned_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.warning(f"User #{user_id} not found - ticket will be unassigned")
        
        # Create ticket with MEDIUM priority
        ticket = Ticket.objects.create(
            call=call,
            client=call.client,
            title=f"📞 FOLLOW-UP - {call.phone_number}",
            description=f"Completed call with {call.phone_number}\nDuration: {call.duration_formatted}\nTime: {call.started_at.strftime('%d/%m/%Y %H:%M:%S')}\n\nAwaiting follow-up or resolution update.",
            priority='medium',
            status='open',
            assigned_to=assigned_user,
        )
        
        # Update call
        call.ticket_created = True
        call.ticket_id = ticket.id
        call.save()
        
        # Log action
        assigned_info = f"assigned to {assigned_user.username}" if assigned_user else "unassigned"
        VoIPCallLog.objects.create(
            call=call,
            action='ticket_created',
            description=f"Auto-ticket #{ticket.id} created for answered call ({assigned_info})"
        )
        
        logger.info(f"✅ Ticket #{ticket.id} created for answered call #{call_id} - {assigned_info}")
        return ticket.id
        
    except VoIPCall.DoesNotExist:
        logger.error(f"❌ Call #{call_id} not found")
        return None
    except Exception as exc:
        logger.error(f"❌ Error creating ticket for answered call: {exc}")
        self.retry(exc=exc, countdown=60)


# ============================================
# TASK 3: SEND OBLIGATION REMINDERS
# ============================================

@shared_task
def send_obligation_reminders():
    """
    Αυτόματα emails αναμνήσεων για υποχρεώσεις
    Στέλνεται: Κάθε weekday 9:00 AM
    Λήπτες: Πελάτες με υποχρεώσεις που λήγουν τις επόμενες 7 ημέρες
    """
    # Δεν ξαναστέλνουμε υπενθύμιση για την ίδια υποχρέωση πριν περάσουν Χ ημέρες
    REMINDER_COOLDOWN_DAYS = 3

    try:
        today = timezone.now().date()
        week_end = today + timedelta(days=7)

        # Υποχρεώσεις που λήγουν αυτή την εβδομάδα (και οι «σε εξέλιξη»)
        pending_obligations = MonthlyObligation.objects.filter(
            deadline__gte=today,
            deadline__lte=week_end,
            status__in=['pending', 'in_progress'],
        ).select_related('client', 'obligation_type')

        if not pending_obligations.exists():
            logger.info("No obligations due this week - skipping reminder")
            return f"No reminders sent (0 obligations due)"

        # Πρότυπο: το seeded «Υπενθύμιση Προθεσμίας» (τα ονόματα είναι ελληνικά —
        # το παλιό icontains='reminder' δεν το έβρισκε ποτέ)
        def get_reminder_template(obligation_type):
            return (
                EmailTemplate.objects.filter(
                    obligation_type=obligation_type, is_active=True,
                    name__icontains='Υπενθύμιση'
                ).first()
                or EmailTemplate.objects.filter(
                    name='Υπενθύμιση Προθεσμίας', is_active=True
                ).first()
                or EmailTemplate.objects.filter(
                    is_active=True, name__icontains='Υπενθύμιση Προθεσμίας'
                ).first()
            )

        sent_count = 0
        skipped_recent = 0
        cooldown_start = timezone.now() - timedelta(days=REMINDER_COOLDOWN_DAYS)

        for obligation in pending_obligations:
            try:
                client = obligation.client

                # Skip if no email
                if not client.email:
                    logger.warning(f"Client {client.afm} has no email - skipping")
                    continue

                template = get_reminder_template(obligation.obligation_type)

                # Anti-spam: αν στάλθηκε πρόσφατα υπενθύμιση για την ίδια
                # υποχρέωση, μην την ξαναστείλεις (το task τρέχει καθημερινά)
                already_sent = ScheduledEmail.objects.filter(
                    obligations=obligation,
                    status='sent',
                    sent_at__gte=cooldown_start,
                    subject__icontains='Υπενθύμιση',
                ).exists()
                if already_sent:
                    skipped_recent += 1
                    continue

                context = {
                    'client_name': client.eponimia,
                    'client_afm': client.afm,
                    'obligation_type': obligation.obligation_type.name,
                    'period_month': obligation.month,
                    'period_year': obligation.year,
                    'period_display': f"{obligation.month:02d}/{obligation.year}",
                    'deadline': obligation.deadline.strftime('%d/%m/%Y'),
                    'days_left': (obligation.deadline - today).days,
                    'accountant_name': '',
                    'company_name': '',
                }

                if not template:
                    logger.warning("No reminder template found - using default message")
                    subject = f"⏰ Υπενθύμιση: Υποχρέωση {obligation.obligation_type.name}"
                    body = (
                        f"Καλημέρα {client.eponimia},\n\n"
                        f"Υπενθύμιση: Η υποχρέωση '{obligation.obligation_type.name}' "
                        f"λήγει στις {obligation.deadline.strftime('%d/%m/%Y')}.\n\nΜε εκτίμηση"
                    )
                else:
                    # render_simple: τα seeded templates έχουν {μεταβλητή} με
                    # μονά άγκιστρα — το render() (Django Template) δεν τα
                    # αντικαθιστούσε ποτέ
                    subject, body = template.render_simple(context)

                # Send email
                send_mail(
                    subject=subject,
                    message=strip_tags(body),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[client.email],
                    html_message=body if template else None,
                    fail_silently=False,
                )

                # Log email (με σύνδεση στην υποχρέωση για το anti-spam check)
                log_entry = ScheduledEmail.objects.create(
                    recipient_email=client.email,
                    recipient_name=client.eponimia,
                    client=client,
                    template=template,
                    subject=subject,
                    body_html=body,
                    send_at=timezone.now(),
                    status='sent',
                    sent_at=timezone.now(),
                )
                log_entry.obligations.add(obligation)

                sent_count += 1
                logger.info(f"✅ Reminder sent to {client.email} for obligation {obligation.obligation_type.name}")

            except Exception as e:
                logger.error(f"❌ Error sending reminder for obligation #{obligation.id}: {e}")
                continue

        logger.info(
            f"✅ Obligation reminders: {sent_count} sent, "
            f"{skipped_recent} skipped (recent), of {pending_obligations.count()} due"
        )
        return f"Sent {sent_count} obligation reminders ({skipped_recent} skipped as recent)"

    except Exception as exc:
        logger.error(f"❌ Error in send_obligation_reminders: {exc}")
        return f"Error: {str(exc)}"


# ============================================
# TASK 4: SEND DAILY SUMMARY
# ============================================

@shared_task
def send_daily_summary():
    """
    Ημερήσια σύνοψη στην ομάδα
    Στέλνεται: Κάθε weekday 17:00 (5 PM)
    Λήπτες: Όλοι οι staff members
    Περιέχει: Pending tickets, overdue obligations, missed calls
    """
    try:
        today = timezone.now().date()
        
        # Get statistics
        pending_tickets = Ticket.objects.filter(
            status__in=['open', 'assigned', 'in_progress']
        ).count()
        
        assigned_to_me = Ticket.objects.filter(
            status__in=['open', 'assigned', 'in_progress'],
        ).values('assigned_to__username').distinct().count()
        
        overdue_obligations = MonthlyObligation.objects.filter(
            status='pending',
            deadline__lt=today
        ).count()
        
        due_this_week = MonthlyObligation.objects.filter(
            status='pending',
            deadline__gte=today,
            deadline__lte=today + timedelta(days=7)
        ).count()
        
        missed_calls_today = VoIPCall.objects.filter(
            status='missed',
            started_at__date=today
        ).count()
        
        answered_calls_today = VoIPCall.objects.filter(
            status='completed',
            started_at__date=today
        ).count()
        
        # Get team emails
        team_users = User.objects.filter(is_staff=True, email__isnull=False).exclude(email='')
        
        if not team_users.exists():
            logger.warning("No staff users with emails found")
            return "No team members to send summary to"
        
        # Build email body
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .stat {{ background: #f9fafb; border-left: 4px solid #667eea; padding: 15px; margin: 10px 0; border-radius: 4px; }}
                .stat-number {{ font-size: 24px; font-weight: bold; color: #667eea; }}
                .stat-label {{ color: #666; font-size: 14px; }}
                .warning {{ background: #fef2f2; border-left-color: #ef4444; }}
                .warning .stat-number {{ color: #ef4444; }}
                .link {{ display: inline-block; margin-top: 20px; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Daily Summary - {today.strftime('%d/%m/%Y')}</h1>
                    <p>Good evening! Here's your daily briefing.</p>
                </div>
                
                <div class="stat">
                    <div class="stat-number">{pending_tickets}</div>
                    <div class="stat-label">🎫 Pending Tickets (Open/Assigned/In Progress)</div>
                </div>
                
                <div class="stat warning" {"" if overdue_obligations == 0 else ""}>
                    <div class="stat-number">{overdue_obligations}</div>
                    <div class="stat-label">⚠️ OVERDUE Obligations</div>
                </div>
                
                <div class="stat">
                    <div class="stat-number">{due_this_week}</div>
                    <div class="stat-label">📅 Obligations Due This Week</div>
                </div>
                
                <div class="stat warning" {"" if missed_calls_today == 0 else ""}>
                    <div class="stat-number">{missed_calls_today}</div>
                    <div class="stat-label">📞 Missed Calls Today</div>
                </div>
                
                <div class="stat">
                    <div class="stat-number">{answered_calls_today}</div>
                    <div class="stat-label">✅ Answered Calls Today</div>
                </div>
                
                <a href="{settings.SITE_URL}/el/456-admin/accounting/ticket/" class="link">
                    View All Tickets →
                </a>
                
                <p style="margin-top: 30px; color: #999; font-size: 12px;">
                    Auto-generated by LogistikoCRM - {timezone.now().strftime('%H:%M:%S')}
                </p>
            </div>
        </body>
        </html>
        """
        
        text_body = f"""
        📊 DAILY SUMMARY - {today.strftime('%d/%m/%Y')}
        
        🎫 Pending Tickets: {pending_tickets}
        ⚠️ OVERDUE Obligations: {overdue_obligations}
        📅 Obligations Due This Week: {due_this_week}
        📞 Missed Calls Today: {missed_calls_today}
        ✅ Answered Calls Today: {answered_calls_today}
        
        View all: {settings.SITE_URL}/el/456-admin/accounting/ticket/
        """
        
        # Send to all team members
        sent_count = 0
        for user in team_users:
            try:
                send_mail(
                    subject=f"📊 Daily Summary - {today.strftime('%d/%m/%Y')}",
                    message=text_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_body,
                    fail_silently=False,
                )
                sent_count += 1
                logger.info(f"✅ Daily summary sent to {user.email}")
            except Exception as e:
                logger.error(f"❌ Error sending summary to {user.email}: {e}")
                continue
        
        logger.info(f"✅ Daily summary sent to {sent_count}/{team_users.count()} team members")
        return f"Sent daily summary to {sent_count} team members"
        
    except Exception as exc:
        logger.error(f"❌ Error in send_daily_summary: {exc}")
        return f"Error: {str(exc)}"


# ============================================
# TASK 5: AUTO-ESCALATE & PROCESS TICKETS
# ============================================

@shared_task
def process_pending_tickets():
    """
    Runs every hour to:
    1. Auto-assign tickets based on rules
    2. Escalate old tickets
    3. Send notifications
    """
    now = timezone.now()
    
    # 1. Auto-escalate tickets older than 4 hours
    old_tickets = Ticket.objects.filter(
        status='open',
        created_at__lte=now - timedelta(hours=4),
        priority__in=['low', 'medium']
    )
    
    escalated_count = 0
    for ticket in old_tickets:
        old_priority = ticket.priority
        if ticket.priority == 'low':
            ticket.priority = 'medium'
        elif ticket.priority == 'medium':
            ticket.priority = 'high'
        
        ticket.notes = (ticket.notes or '') + f"\n[{now.strftime('%d/%m %H:%M')}] Auto-escalated: {old_priority} → {ticket.priority}"
        ticket.save()
        escalated_count += 1
        
        logger.info(f"Escalated ticket #{ticket.id}")
    
    # 2. Find unassigned urgent tickets
    urgent_unassigned = Ticket.objects.filter(
        status='open',
        priority='urgent',
        assigned_to__isnull=True
    ).count()
    
    if urgent_unassigned > 0:
        logger.warning(f"⚠️ {urgent_unassigned} URGENT tickets unassigned!")
    
    return f"Processed: {escalated_count} escalated, {urgent_unassigned} urgent pending"


# ============================================
# HELPER: Trigger answered call ticket
# ============================================

def trigger_answered_call_ticket(call, user=None):
    """
    Helper function to manually trigger ticket creation for answered calls
    Call this from voip_call_update() view when status changes to 'completed'
    """
    user_id = user.id if user else None
    create_ticket_for_answered_call.delay(call.id, user_id)
    logger.info(f"Triggered answered call ticket task for call #{call.id}")


# ============================================
# TASK 6: PROCESS SCHEDULED EMAILS
# ============================================

@shared_task
def process_scheduled_emails():
    """
    Process and send scheduled emails that are due.

    Runs: Every 5 minutes via Celery Beat
    Action: Finds all ScheduledEmail with status='pending' and send_at <= now()
            Sends each email using BCC for multiple recipients and updates status

    Supports:
        - Single recipient: sends directly to recipient
        - Multiple recipients: sends to DEFAULT_FROM_EMAIL with all recipients in BCC

    Returns:
        str: Summary of processed emails
    """
    from django.core.mail import EmailMessage

    now = timezone.now()

    # Find all pending emails that are due
    pending_emails = ScheduledEmail.objects.filter(
        status='pending',
        send_at__lte=now
    ).select_related('client', 'template').prefetch_related('obligations')

    if not pending_emails.exists():
        logger.debug("No scheduled emails to process")
        return "No scheduled emails to process"

    sent_count = 0
    failed_count = 0
    total_recipients = 0

    for scheduled_email in pending_emails:
        try:
            # Get list of recipient emails (supports comma/newline separated)
            recipients = scheduled_email.get_recipients_list()
            recipient_count = len(recipients)

            if not recipients:
                logger.warning(f"Scheduled email #{scheduled_email.id} has no valid recipients")
                scheduled_email.mark_as_failed("Δεν βρέθηκαν έγκυρες διευθύνσεις email")
                failed_count += 1
                continue

            logger.info(f"Processing scheduled email #{scheduled_email.id} to {recipient_count} recipient(s)")

            # Create email message
            # For multiple recipients: send to self with BCC to all recipients
            # For single recipient: send directly
            if recipient_count > 1:
                # BCC mode: send to self, BCC to all recipients
                email = EmailMessage(
                    subject=scheduled_email.subject,
                    body=scheduled_email.body_html,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[settings.DEFAULT_FROM_EMAIL],  # Send to self
                    bcc=recipients,  # All recipients in BCC
                )
            else:
                # Single recipient mode: send directly
                email = EmailMessage(
                    subject=scheduled_email.subject,
                    body=scheduled_email.body_html,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=recipients,
                )

            email.content_subtype = 'html'

            # Attach files from obligations
            attachments = scheduled_email.get_attachments()
            for attachment in attachments:
                try:
                    if hasattr(attachment, 'path'):
                        email.attach_file(attachment.path)
                except Exception as attach_err:
                    logger.warning(f"Could not attach file for email #{scheduled_email.id}: {attach_err}")

            # Send email
            email.send(fail_silently=False)

            # Mark as sent
            scheduled_email.mark_as_sent()
            sent_count += 1
            total_recipients += recipient_count

            if recipient_count > 1:
                logger.info(f"✅ Scheduled email #{scheduled_email.id} sent via BCC to {recipient_count} recipients")
            else:
                logger.info(f"✅ Scheduled email #{scheduled_email.id} sent to {recipients[0]}")

            # Create EmailLog entry for tracking
            from accounting.models import EmailLog
            EmailLog.objects.create(
                recipient_email=scheduled_email.recipient_email,
                recipient_name=scheduled_email.recipient_name,
                client=scheduled_email.client,
                template_used=scheduled_email.template,
                subject=scheduled_email.subject,
                body=scheduled_email.body_html,
                status='sent',
                sent_by=scheduled_email.created_by
            )

        except Exception as e:
            # Mark as failed
            scheduled_email.mark_as_failed(str(e))
            failed_count += 1

            logger.error(f"❌ Failed to send scheduled email #{scheduled_email.id}: {e}")

            # Create EmailLog entry for tracking the failure
            from accounting.models import EmailLog
            EmailLog.objects.create(
                recipient_email=scheduled_email.recipient_email,
                recipient_name=scheduled_email.recipient_name,
                client=scheduled_email.client,
                template_used=scheduled_email.template,
                subject=scheduled_email.subject,
                body=scheduled_email.body_html,
                status='failed',
                error_message=str(e),
                sent_by=scheduled_email.created_by
            )

    result = f"Processed scheduled emails: {sent_count} sent ({total_recipients} recipients), {failed_count} failed"
    logger.info(f"✅ {result}")
    return result


# ============================================
# TASK 7: ASYNC EMAIL SENDING
# ============================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_async(self, email_log_id):
    """
    Async task to send email from EmailLog entry.

    This task is triggered when async_send=True is passed to EmailService.send_email().
    It uses the retry logic built into the EmailService.

    Args:
        email_log_id: ID of the EmailLog entry to send

    Returns:
        dict with success status and message
    """
    from accounting.services.email_service import EmailService
    from accounting.models import EmailLog

    try:
        email_log = EmailLog.objects.get(id=email_log_id)
    except EmailLog.DoesNotExist:
        logger.error(f"EmailLog {email_log_id} not found")
        return {'success': False, 'error': 'Email log not found'}

    # Skip if already sent
    if email_log.status == 'sent':
        logger.info(f"Email {email_log_id} already sent, skipping")
        return {'success': True, 'message': 'Already sent'}

    # Update status to show it's being processed
    email_log.status = 'pending'
    email_log.save()

    try:
        success, error = EmailService.send_email_from_log(email_log_id)

        if success:
            logger.info(f"✅ Async email {email_log_id} sent successfully")
            return {'success': True, 'message': f'Sent to {email_log.recipient_email}'}
        else:
            logger.error(f"❌ Async email {email_log_id} failed: {error}")
            # Retry the task
            raise self.retry(exc=Exception(error), countdown=60 * (self.request.retries + 1))

    except EmailLog.DoesNotExist:
        return {'success': False, 'error': 'Email log not found'}
    except Exception as exc:
        # Update log with retry count
        email_log.retry_count = self.request.retries
        email_log.error_message = str(exc)
        email_log.save()

        # Retry if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.warning(f"Retrying async email {email_log_id} (attempt {self.request.retries + 1})")
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        else:
            # Mark as failed after max retries
            email_log.status = 'failed'
            email_log.save()
            logger.error(f"❌ Async email {email_log_id} failed after {self.max_retries} retries: {exc}")
            return {'success': False, 'error': str(exc)}


@shared_task(bind=True, max_retries=3)
def retry_failed_emails(self):
    """
    Periodic task to retry failed emails.

    Runs: Every 30 minutes via Celery Beat
    Retries: Emails that failed within the last 24 hours and haven't exceeded max retries.
    """
    from accounting.models import EmailLog
    from accounting.services.email_service import EmailService

    # Find failed emails from last 24 hours that haven't been retried too many times
    cutoff = timezone.now() - timedelta(hours=24)
    failed_emails = EmailLog.objects.filter(
        status='failed',
        sent_at__gte=cutoff,
        retry_count__lt=3
    ).order_by('sent_at')[:50]  # Limit to 50 per run

    if not failed_emails.exists():
        logger.debug("No failed emails to retry")
        return "No failed emails to retry"

    retried = 0
    succeeded = 0

    for email_log in failed_emails:
        try:
            # Increment retry count
            email_log.retry_count += 1
            email_log.status = 'pending'
            email_log.save()

            success, error = EmailService.send_email_from_log(email_log.id)

            if success:
                succeeded += 1
                logger.info(f"✅ Retry successful for email {email_log.id}")
            else:
                email_log.status = 'failed'
                email_log.error_message = str(error)
                email_log.save()
                logger.warning(f"Retry failed for email {email_log.id}: {error}")

            retried += 1

        except Exception as e:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            email_log.save()
            logger.error(f"Error retrying email {email_log.id}: {e}")

    result = f"Retried {retried} emails, {succeeded} succeeded"
    logger.info(f"✅ {result}")
    return result

# ============================================
# YEARLY FOLDER ROLLOVER
# ============================================

@shared_task
def ensure_yearly_folders(year=None):
    """
    Δημιουργία δέντρου φακέλων αρχειοθέτησης για όλους τους ενεργούς
    πελάτες για το δεδομένο έτος (default: τρέχον).

    Προγραμματίζεται 1η Ιανουαρίου (Celery beat) ώστε η νέα χρονιά να
    έχει έτοιμους φακέλους — τα uploads τούς δημιουργούν ούτως ή άλλως
    on-demand, αυτό είναι το δίχτυ ασφαλείας για χειροκίνητη αρχειοθέτηση.
    """
    from .models import ClientProfile
    from .services import filing

    year = year or timezone.now().year
    created = 0
    failed = 0
    for client in ClientProfile.objects.filter(is_active=True):
        if filing.ensure_folders(client, year=year):
            created += 1
        else:
            failed += 1

    result = f"Φάκελοι έτους {year}: {created} πελάτες OK, {failed} αποτυχίες"
    logger.info(result)
    return result


# ============================================
# DOCUMENT TEXT EXTRACTION
# ============================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def extract_document_text(self, document_id):
    """
    Εξαγωγή κειμένου από έγγραφο πελάτη (async).
    Ενημερώνει extracted_text/ocr_status/afm_mismatch.
    """
    from .models import ClientDocument
    from .services import text_extraction

    try:
        document = ClientDocument.objects.get(id=document_id)
    except ClientDocument.DoesNotExist:
        logger.info(f"Document {document_id} no longer exists - skipping extraction")
        return None

    status = text_extraction.process_document(document)
    logger.info(f"Text extraction for document {document_id}: {status}")
    return status


# ============================================
# DATABASE BACKUP (Celery beat, καθημερινά 02:00)
# ============================================

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def backup_database_task(self):
    """
    Αυτόματο backup βάσης — τρέχει από το Celery beat ώστε να μη
    χρειάζεται χειροκίνητο crontab setup (το scripts/backup_cron.sh
    παραμένει για deployments χωρίς Celery).
    """
    from io import StringIO
    from django.core.management import call_command

    out = StringIO()
    try:
        call_command('backup_database', stdout=out)
        result = out.getvalue().strip()
        logger.info(f"✅ Scheduled backup: {result}")
        return result
    except Exception as exc:
        logger.error(f"❌ Scheduled backup failed: {exc}")
        raise self.retry(exc=exc)


# ============================================
# STALE SYNC LOG CLEANUP (Celery beat, κάθε 30')
# ============================================

@shared_task
def cleanup_stale_sync_logs(stale_minutes=60):
    """
    Μαρκάρει ως ERROR τα myDATA sync logs που έμειναν PENDING επειδή ο
    worker διακόπηκε στη μέση (π.χ. restart/crash). Χωρίς αυτό τα rows
    μένουν PENDING για πάντα και μπερδεύουν το ιστορικό συγχρονισμών.
    """
    from datetime import timedelta
    from django.utils import timezone
    from inventory.models import MyDataSyncLog
    from mydata.models import VATSyncLog

    cutoff = timezone.now() - timedelta(minutes=stale_minutes)
    message = (
        f'Sync διακόπηκε — επισημάνθηκε ως stale από το cleanup task '
        f'(PENDING > {stale_minutes} λεπτά). Άγνωστο αποτέλεσμα: έλεγξε '
        f'τα δεδομένα στην ΑΑΔΕ πριν ξανατρέξεις.'
    )

    invoice_logs = MyDataSyncLog.objects.filter(
        status='PENDING', started_at__lt=cutoff
    ).update(status='ERROR', completed_at=timezone.now(), error_message=message)

    vat_logs = VATSyncLog.objects.filter(
        status='PENDING', started_at__lt=cutoff
    ).update(status='ERROR', completed_at=timezone.now(), error_message=message)

    if invoice_logs or vat_logs:
        logger.warning(
            f'Stale sync logs: {invoice_logs} MyDataSyncLog, {vat_logs} VATSyncLog'
        )
    return f'Cleaned {invoice_logs + vat_logs} stale sync logs'
