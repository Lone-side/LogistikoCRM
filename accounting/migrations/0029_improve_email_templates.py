# Data migration to improve email templates with more professional design

from django.db import migrations


# Professional email template HTML with better styling
IMPROVED_COMPLETION_TEMPLATE = '''<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f5f7fa;">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 32px 24px; text-align: center; border-radius: 12px 12px 0 0;">
        <h1 style="margin: 0; color: white; font-size: 24px; font-weight: 600;">✓ Ολοκλήρωση Υποχρέωσης</h1>
        <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{company_name}</p>
    </div>

    <!-- Body -->
    <div style="background: white; padding: 32px 24px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <p style="font-size: 16px; color: #1f2937; margin: 0 0 16px 0;">
            Αγαπητέ/ή <strong>{client_name}</strong>,
        </p>

        <p style="color: #4b5563; line-height: 1.7; margin: 0 0 24px 0;">
            Σας ενημερώνουμε ότι η υποχρέωση <strong style="color: #4f46e5;">{obligation_type}</strong>
            για την περίοδο <strong>{period_display}</strong> ολοκληρώθηκε επιτυχώς.
        </p>

        <!-- Info Card -->
        <div style="background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border-left: 4px solid #10b981; padding: 20px; margin: 0 0 24px 0; border-radius: 0 8px 8px 0;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 4px 0; color: #065f46; font-size: 14px;">
                        <strong>Τύπος:</strong>
                    </td>
                    <td style="padding: 4px 0; color: #065f46; font-size: 14px; text-align: right;">
                        {obligation_type}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 4px 0; color: #065f46; font-size: 14px;">
                        <strong>Περίοδος:</strong>
                    </td>
                    <td style="padding: 4px 0; color: #065f46; font-size: 14px; text-align: right;">
                        {period_display}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 4px 0; color: #065f46; font-size: 14px;">
                        <strong>Προθεσμία:</strong>
                    </td>
                    <td style="padding: 4px 0; color: #065f46; font-size: 14px; text-align: right;">
                        {deadline}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 4px 0; color: #065f46; font-size: 14px;">
                        <strong>Ημ/νία Ολοκλήρωσης:</strong>
                    </td>
                    <td style="padding: 4px 0; color: #065f46; font-size: 14px; text-align: right;">
                        {completed_date}
                    </td>
                </tr>
            </table>
        </div>

        <p style="color: #6b7280; font-size: 14px; margin: 0 0 24px 0;">
            Παραμένουμε στη διάθεσή σας για οποιαδήποτε διευκρίνιση.
        </p>

        <!-- Signature -->
        <div style="border-top: 1px solid #e5e7eb; padding-top: 24px; margin-top: 24px;">
            <p style="color: #374151; margin: 0 0 4px 0; font-size: 14px;">Με εκτίμηση,</p>
            <p style="color: #4f46e5; margin: 0 0 4px 0; font-weight: 600; font-size: 16px;">{accountant_name}</p>
            <p style="color: #6b7280; margin: 0; font-size: 14px;">{company_name}</p>
            <p style="color: #9ca3af; margin: 4px 0 0 0; font-size: 13px;">{company_phone}</p>
        </div>
    </div>

    <!-- Footer -->
    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p style="margin: 0;">Αυτό το email στάλθηκε αυτόματα από το σύστημα διαχείρισης πελατών.</p>
    </div>
</div>'''


IMPROVED_GENERAL_TEMPLATE = '''<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f5f7fa;">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); padding: 32px 24px; text-align: center; border-radius: 12px 12px 0 0;">
        <h1 style="margin: 0; color: white; font-size: 24px; font-weight: 600;">Ενημέρωση</h1>
        <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{company_name}</p>
    </div>

    <!-- Body -->
    <div style="background: white; padding: 32px 24px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <p style="font-size: 16px; color: #1f2937; margin: 0 0 16px 0;">
            Αγαπητέ/ή <strong>{client_name}</strong>,
        </p>

        <p style="color: #4b5563; line-height: 1.7; margin: 0 0 24px 0;">
            Σας ενημερώνουμε για τα εξής:
        </p>

        <!-- Content Box -->
        <div style="background: #f9fafb; border: 1px solid #e5e7eb; padding: 20px; margin: 0 0 24px 0; border-radius: 8px;">
            <p style="margin: 0; color: #374151; line-height: 1.7;">
                [Εισάγετε το κείμενο της ενημέρωσης εδώ]
            </p>
        </div>

        <p style="color: #6b7280; font-size: 14px; margin: 0 0 24px 0;">
            Για οποιαδήποτε διευκρίνιση ή απορία, μη διστάσετε να επικοινωνήσετε μαζί μας.
        </p>

        <!-- Signature -->
        <div style="border-top: 1px solid #e5e7eb; padding-top: 24px; margin-top: 24px;">
            <p style="color: #374151; margin: 0 0 4px 0; font-size: 14px;">Με εκτίμηση,</p>
            <p style="color: #3b82f6; margin: 0 0 4px 0; font-weight: 600; font-size: 16px;">{accountant_name}</p>
            <p style="color: #6b7280; margin: 0; font-size: 14px;">{company_name}</p>
            <p style="color: #9ca3af; margin: 4px 0 0 0; font-size: 13px;">{company_phone}</p>
        </div>
    </div>

    <!-- Footer -->
    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p style="margin: 0;">Αυτό το email στάλθηκε από το σύστημα διαχείρισης πελατών.</p>
    </div>
</div>'''


IMPROVED_DOCUMENT_REQUEST_TEMPLATE = '''<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f5f7fa;">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 32px 24px; text-align: center; border-radius: 12px 12px 0 0;">
        <h1 style="margin: 0; color: white; font-size: 24px; font-weight: 600;">📋 Υπενθύμιση Εγγράφων</h1>
        <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{company_name}</p>
    </div>

    <!-- Body -->
    <div style="background: white; padding: 32px 24px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <p style="font-size: 16px; color: #1f2937; margin: 0 0 16px 0;">
            Αγαπητέ/ή <strong>{client_name}</strong>,
        </p>

        <p style="color: #4b5563; line-height: 1.7; margin: 0 0 24px 0;">
            Σας υπενθυμίζουμε ότι για την ολοκλήρωση της υποχρέωσης
            <strong style="color: #d97706;">{obligation_type}</strong> περιόδου <strong>{period_display}</strong>,
            χρειαζόμαστε τα παρακάτω έγγραφα:
        </p>

        <!-- Documents List -->
        <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-left: 4px solid #f59e0b; padding: 20px; margin: 0 0 24px 0; border-radius: 0 8px 8px 0;">
            <p style="margin: 0 0 12px 0; color: #92400e; font-weight: 600;">Απαιτούμενα Έγγραφα:</p>
            <ul style="margin: 0; padding-left: 20px; color: #92400e;">
                <li style="margin-bottom: 8px;">[Έγγραφο 1]</li>
                <li style="margin-bottom: 8px;">[Έγγραφο 2]</li>
                <li>[Έγγραφο 3]</li>
            </ul>
        </div>

        <!-- Deadline Box -->
        <div style="background: #fef2f2; border: 2px solid #ef4444; padding: 16px; margin: 0 0 24px 0; border-radius: 8px; text-align: center;">
            <p style="margin: 0; color: #dc2626; font-size: 16px;">
                <strong>⏰ Προθεσμία: {deadline}</strong>
            </p>
        </div>

        <p style="color: #6b7280; font-size: 14px; margin: 0 0 24px 0;">
            Παρακαλούμε να μας αποστείλετε τα παραπάνω το συντομότερο δυνατό.
        </p>

        <!-- Signature -->
        <div style="border-top: 1px solid #e5e7eb; padding-top: 24px; margin-top: 24px;">
            <p style="color: #374151; margin: 0 0 4px 0; font-size: 14px;">Με εκτίμηση,</p>
            <p style="color: #d97706; margin: 0 0 4px 0; font-weight: 600; font-size: 16px;">{accountant_name}</p>
            <p style="color: #6b7280; margin: 0; font-size: 14px;">{company_name}</p>
            <p style="color: #9ca3af; margin: 4px 0 0 0; font-size: 13px;">{company_phone}</p>
        </div>
    </div>

    <!-- Footer -->
    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p style="margin: 0;">Αυτό το email στάλθηκε αυτόματα από το σύστημα διαχείρισης πελατών.</p>
    </div>
</div>'''


IMPROVED_DEADLINE_TEMPLATE = '''<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #f5f7fa;">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 32px 24px; text-align: center; border-radius: 12px 12px 0 0;">
        <h1 style="margin: 0; color: white; font-size: 24px; font-weight: 600;">⚠️ Υπενθύμιση Προθεσμίας</h1>
        <p style="margin: 8px 0 0 0; color: rgba(255,255,255,0.9); font-size: 14px;">{company_name}</p>
    </div>

    <!-- Body -->
    <div style="background: white; padding: 32px 24px; border-radius: 0 0 12px 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <p style="font-size: 16px; color: #1f2937; margin: 0 0 16px 0;">
            Αγαπητέ/ή <strong>{client_name}</strong>,
        </p>

        <p style="color: #4b5563; line-height: 1.7; margin: 0 0 24px 0;">
            Σας υπενθυμίζουμε ότι η προθεσμία για την υποχρέωση
            <strong style="color: #dc2626;">{obligation_type}</strong> περιόδου <strong>{period_display}</strong>
            πλησιάζει.
        </p>

        <!-- Deadline Alert -->
        <div style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border: 2px solid #ef4444; padding: 24px; margin: 0 0 24px 0; border-radius: 12px; text-align: center;">
            <p style="margin: 0 0 8px 0; color: #991b1b; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Προθεσμία</p>
            <p style="margin: 0; color: #dc2626; font-size: 28px; font-weight: 700;">{deadline}</p>
        </div>

        <p style="color: #6b7280; font-size: 14px; margin: 0 0 24px 0;">
            Παρακαλούμε επικοινωνήστε μαζί μας άμεσα για να διασφαλίσουμε την έγκαιρη υποβολή.
        </p>

        <!-- Signature -->
        <div style="border-top: 1px solid #e5e7eb; padding-top: 24px; margin-top: 24px;">
            <p style="color: #374151; margin: 0 0 4px 0; font-size: 14px;">Με εκτίμηση,</p>
            <p style="color: #dc2626; margin: 0 0 4px 0; font-weight: 600; font-size: 16px;">{accountant_name}</p>
            <p style="color: #6b7280; margin: 0; font-size: 14px;">{company_name}</p>
            <p style="color: #9ca3af; margin: 4px 0 0 0; font-size: 13px;">{company_phone}</p>
        </div>
    </div>

    <!-- Footer -->
    <div style="text-align: center; padding: 20px; color: #9ca3af; font-size: 12px;">
        <p style="margin: 0;">Αυτό το email στάλθηκε αυτόματα από το σύστημα διαχείρισης πελατών.</p>
    </div>
</div>'''


def update_email_templates(apps, schema_editor):
    """Update email templates with improved professional design"""
    EmailTemplate = apps.get_model('accounting', 'EmailTemplate')

    # Update Obligation Completion template
    EmailTemplate.objects.filter(name='Ολοκλήρωση Υποχρέωσης').update(
        body_html=IMPROVED_COMPLETION_TEMPLATE
    )

    # Update General Notification template
    EmailTemplate.objects.filter(name='Γενική Ενημέρωση').update(
        body_html=IMPROVED_GENERAL_TEMPLATE
    )

    # Update Document Request template
    EmailTemplate.objects.filter(name='Υπενθύμιση Εγγράφων').update(
        body_html=IMPROVED_DOCUMENT_REQUEST_TEMPLATE
    )

    # Update Deadline Reminder template
    EmailTemplate.objects.filter(name='Υπενθύμιση Προθεσμίας').update(
        body_html=IMPROVED_DEADLINE_TEMPLATE
    )


def reverse_migration(apps, schema_editor):
    """This migration cannot be easily reversed - templates would need to be recreated"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0028_unified_document_system'),
    ]

    operations = [
        migrations.RunPython(update_email_templates, reverse_migration),
    ]
