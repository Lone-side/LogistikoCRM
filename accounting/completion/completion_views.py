"""
Obligation Completion Views
Author: LogistikoCRM
Version: 1.0
Description: Views για διαχείριση ολοκλήρωσης υποχρεώσεων με file upload και email.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.db.models import Q, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
from django.core.files.storage import default_storage

import os
import json
import logging
from datetime import datetime

from django.core.exceptions import ValidationError

from ..models import (
    MonthlyObligation, ClientProfile, ObligationType,
    EmailTemplate, EmailLog, ClientDocument, ArchiveConfiguration
)
from ..services import filing
from ..services.access import (
    accessible_clients, accessible_documents, accessible_obligations,
    check_model_perms,
)

PERM_DENIED_JSON = {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'}
from ..services.email_service import EmailService

logger = logging.getLogger(__name__)


# =============================================================================
# OBLIGATION LIST VIEW
# =============================================================================

@staff_member_required
@login_required
def obligation_list_view(request):
    """
    Κύρια οθόνη διαχείρισης υποχρεώσεων με φίλτρα και DataTables.
    """
    now = timezone.now()
    current_month = now.month
    current_year = now.year

    # Φίλτρα από GET parameters
    filters = {
        'month': request.GET.get('month', str(current_month)),
        'year': request.GET.get('year', str(current_year)),
        'status': request.GET.get('status', ''),
        'client_id': request.GET.get('client', ''),
        'type_id': request.GET.get('type', ''),
        'search': request.GET.get('search', ''),
    }

    # Δημιουργία queryset
    queryset = accessible_obligations(request.user).select_related(
        'client', 'obligation_type', 'completed_by'
    ).order_by('deadline', 'client__eponimia')

    # Εφαρμογή φίλτρων
    if filters['month']:
        queryset = queryset.filter(month=int(filters['month']))
    if filters['year']:
        queryset = queryset.filter(year=int(filters['year']))
    if filters['status']:
        queryset = queryset.filter(status=filters['status'])
    if filters['client_id']:
        queryset = queryset.filter(client_id=int(filters['client_id']))
    if filters['type_id']:
        queryset = queryset.filter(obligation_type_id=int(filters['type_id']))
    if filters['search']:
        queryset = queryset.filter(
            Q(client__eponimia__icontains=filters['search']) |
            Q(client__afm__icontains=filters['search']) |
            Q(obligation_type__name__icontains=filters['search'])
        )

    # Στατιστικά
    stats = {
        'total': queryset.count(),
        'pending': queryset.filter(status='pending').count(),
        'completed': queryset.filter(status='completed').count(),
        'overdue': queryset.filter(status='overdue').count(),
    }

    # Data για dropdown φίλτρα
    clients = accessible_clients(request.user).filter(is_active=True).order_by('eponimia')
    obligation_types = ObligationType.objects.filter(is_active=True).order_by('name')

    # Έτη διαθέσιμα
    years = list(range(current_year - 2, current_year + 2))

    # Μήνες
    months = [
        (1, 'Ιανουάριος'), (2, 'Φεβρουάριος'), (3, 'Μάρτιος'),
        (4, 'Απρίλιος'), (5, 'Μάιος'), (6, 'Ιούνιος'),
        (7, 'Ιούλιος'), (8, 'Αύγουστος'), (9, 'Σεπτέμβριος'),
        (10, 'Οκτώβριος'), (11, 'Νοέμβριος'), (12, 'Δεκέμβριος'),
    ]

    context = {
        'obligations': queryset,
        'filters': filters,
        'stats': stats,
        'clients': clients,
        'obligation_types': obligation_types,
        'years': years,
        'months': months,
        'current_month': current_month,
        'current_year': current_year,
    }

    return render(request, 'accounting/obligation_list.html', context)


# =============================================================================
# OBLIGATION DATA API (για DataTables server-side)
# =============================================================================

@staff_member_required
@require_GET
def obligation_list_api(request):
    """
    API endpoint για DataTables server-side processing.
    Επιστρέφει JSON με υποχρεώσεις.
    """
    # DataTables parameters
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))
    search_value = request.GET.get('search[value]', '')

    # Φίλτρα
    month = request.GET.get('month', '')
    year = request.GET.get('year', '')
    status = request.GET.get('status', '')
    client_id = request.GET.get('client', '')
    type_id = request.GET.get('type', '')

    # Base queryset
    queryset = accessible_obligations(request.user).select_related(
        'client', 'obligation_type', 'completed_by'
    )

    # Εφαρμογή φίλτρων
    if month:
        queryset = queryset.filter(month=int(month))
    if year:
        queryset = queryset.filter(year=int(year))
    if status:
        queryset = queryset.filter(status=status)
    if client_id:
        queryset = queryset.filter(client_id=int(client_id))
    if type_id:
        queryset = queryset.filter(obligation_type_id=int(type_id))

    # Search
    if search_value:
        queryset = queryset.filter(
            Q(client__eponimia__icontains=search_value) |
            Q(client__afm__icontains=search_value) |
            Q(obligation_type__name__icontains=search_value)
        )

    # Ordering
    order_column = int(request.GET.get('order[0][column]', 0))
    order_dir = request.GET.get('order[0][dir]', 'asc')

    order_columns = ['id', 'client__eponimia', 'obligation_type__name', 'deadline', 'status']
    if order_column < len(order_columns):
        order_field = order_columns[order_column]
        if order_dir == 'desc':
            order_field = '-' + order_field
        queryset = queryset.order_by(order_field)

    # Counts
    total_count = accessible_obligations(request.user).count()
    filtered_count = queryset.count()

    # Pagination
    obligations = queryset[start:start + length]

    # Build response data
    data = []
    for ob in obligations:
        # Status badge HTML
        status_badges = {
            'pending': '<span class="badge badge-pending">Εκκρεμεί</span>',
            'completed': '<span class="badge badge-completed">Ολοκληρώθηκε</span>',
            'overdue': '<span class="badge badge-overdue">Καθυστερεί</span>',
        }

        # Attachment info
        attachment_html = ''
        if ob.attachment:
            filename = os.path.basename(ob.attachment.name)
            attachment_html = f'''
                <a href="{ob.attachment.url}" target="_blank" class="attachment-preview">
                    <i class="bi bi-file-pdf text-danger"></i> {filename[:20]}...
                </a>
            '''

        # Days until deadline
        days = ob.days_until_deadline
        deadline_class = ''
        if ob.status != 'completed':
            if days < 0:
                deadline_class = 'text-danger fw-bold'
            elif days <= 3:
                deadline_class = 'text-warning fw-bold'

        data.append({
            'id': ob.id,
            'DT_RowId': f'row_{ob.id}',
            'client': ob.client.eponimia,
            'client_afm': ob.client.afm,
            'client_id': ob.client.id,
            'obligation_type': ob.obligation_type.name if ob.obligation_type else '-',
            'period': f'{ob.month:02d}/{ob.year}',
            'deadline': ob.deadline.strftime('%d/%m/%Y') if ob.deadline else '-',
            'deadline_class': deadline_class,
            'days_until': days,
            'status': ob.status,
            'status_badge': status_badges.get(ob.status, ob.status),
            'attachment': attachment_html,
            'has_attachment': bool(ob.attachment),
            'notes': ob.notes[:50] + '...' if ob.notes and len(ob.notes) > 50 else ob.notes or '',
            'completed_by': ob.completed_by.get_full_name() if ob.completed_by else '',
            'completed_date': ob.completed_date.strftime('%d/%m/%Y') if ob.completed_date else '',
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_count,
        'recordsFiltered': filtered_count,
        'data': data,
    })


# =============================================================================
# SINGLE OBLIGATION COMPLETE
# =============================================================================

@staff_member_required
@require_POST
def obligation_complete_single(request, obligation_id):
    """
    Ολοκλήρωση μίας υποχρέωσης με προαιρετικό file upload.
    """
    if not check_model_perms(request, 'accounting.change_monthlyobligation'):
        return JsonResponse(PERM_DENIED_JSON, status=403)
    if request.FILES and not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα δημιουργίας εγγράφων.'},
            status=403,
        )
    obligation = get_object_or_404(accessible_obligations(request.user), id=obligation_id)

    try:
        # File upload
        if 'file' in request.FILES:
            try:
                document = filing.create_client_document(
                    client=obligation.client,
                    uploaded_file=request.FILES['file'],
                    obligation=obligation,
                    user=request.user,
                )
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'error': '; '.join(e.messages)
                }, status=400)
            logger.info(f"Archived file for obligation {obligation_id}: {document.file.name}")

        # Update obligation
        old_status = obligation.status
        obligation.status = 'completed'
        obligation.completed_date = timezone.now().date()
        obligation.completed_by = request.user

        # Notes
        notes = request.POST.get('notes', '').strip()
        if notes:
            timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
            new_note = f"[{timestamp}] {notes}"
            if obligation.notes:
                obligation.notes += f"\n{new_note}"
            else:
                obligation.notes = new_note

        # Time spent
        time_spent = request.POST.get('time_spent', '')
        if time_spent:
            try:
                obligation.time_spent = float(time_spent)
            except ValueError:
                pass

        obligation.save()

        logger.info(f"Obligation {obligation_id} completed by {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': f'Η υποχρέωση "{obligation}" ολοκληρώθηκε επιτυχώς',
            'obligation_id': obligation_id,
            'old_status': old_status,
            'new_status': 'completed',
        })

    except Exception as e:
        logger.error(f"Error completing obligation {obligation_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# BULK COMPLETE
# =============================================================================

@staff_member_required
@require_POST
def obligation_complete_bulk(request):
    """
    Μαζική ολοκλήρωση υποχρεώσεων με per-obligation files.
    """
    if not check_model_perms(request, 'accounting.change_monthlyobligation'):
        return JsonResponse(PERM_DENIED_JSON, status=403)
    if request.FILES and not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα δημιουργίας εγγράφων.'},
            status=403,
        )
    try:
        # Parse obligation IDs
        obligation_ids = request.POST.getlist('obligation_ids[]')
        if not obligation_ids:
            # Try JSON format
            data = json.loads(request.body) if request.content_type == 'application/json' else {}
            obligation_ids = data.get('obligation_ids', [])

        if not obligation_ids:
            return JsonResponse({
                'success': False,
                'error': 'Δεν επιλέχθηκαν υποχρεώσεις'
            }, status=400)

        completed = []
        failed = []
        skipped = []

        for ob_id in obligation_ids:
            try:
                obligation = accessible_obligations(request.user).select_related(
                    'client', 'obligation_type'
                ).get(id=int(ob_id))

                # Skip already completed
                if obligation.status == 'completed':
                    skipped.append({
                        'id': ob_id,
                        'reason': 'Ήδη ολοκληρωμένη'
                    })
                    continue

                # Check for file
                file_key = f'file_{ob_id}'
                if file_key in request.FILES:
                    try:
                        filing.create_client_document(
                            client=obligation.client,
                            uploaded_file=request.FILES[file_key],
                            obligation=obligation,
                            user=request.user,
                        )
                    except ValidationError as e:
                        logger.warning(
                            f"Invalid file for obligation {ob_id}: {'; '.join(e.messages)}"
                        )

                # Complete
                obligation.status = 'completed'
                obligation.completed_date = timezone.now().date()
                obligation.completed_by = request.user
                obligation.save()

                completed.append({
                    'id': ob_id,
                    'client': obligation.client.eponimia,
                    'type': obligation.obligation_type.name if obligation.obligation_type else '',
                })

            except MonthlyObligation.DoesNotExist:
                failed.append({'id': ob_id, 'error': 'Δεν βρέθηκε'})
            except Exception as e:
                failed.append({'id': ob_id, 'error': str(e)})

        return JsonResponse({
            'success': True,
            'completed': len(completed),
            'failed': len(failed),
            'skipped': len(skipped),
            'details': {
                'completed': completed,
                'failed': failed,
                'skipped': skipped,
            }
        })

    except Exception as e:
        logger.error(f"Bulk complete error: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# FILE UPLOAD ONLY (χωρίς ολοκλήρωση)
# =============================================================================

@staff_member_required
@require_POST
def obligation_upload_file(request, obligation_id):
    """
    Upload αρχείου σε υποχρέωση χωρίς να την ολοκληρώσει.
    """
    if not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(PERM_DENIED_JSON, status=403)
    obligation = get_object_or_404(accessible_obligations(request.user), id=obligation_id)

    if 'file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'Δεν επιλέχθηκε αρχείο'
        }, status=400)

    try:
        document = filing.create_client_document(
            client=obligation.client,
            uploaded_file=request.FILES['file'],
            obligation=obligation,
            user=request.user,
        )

        return JsonResponse({
            'success': True,
            'message': 'Το αρχείο αποθηκεύτηκε επιτυχώς',
            'path': document.file.name,
            'filename': document.filename,
            'url': document.file.url if document.file else '',
            'document_id': document.id,
            'version': document.version,
        })

    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': '; '.join(e.messages)
        }, status=400)
    except Exception as e:
        logger.error(f"File upload error for obligation {obligation_id}: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# EMAIL COMPOSITION VIEW
# =============================================================================

@staff_member_required
def email_compose_view(request):
    """
    Οθόνη σύνταξης email με επιλογή υποχρεώσεων και attachments.
    """
    # Λήψη επιλεγμένων υποχρεώσεων
    obligation_ids = request.GET.getlist('ids')
    if not obligation_ids and request.method == 'POST':
        obligation_ids = request.POST.getlist('obligation_ids')

    obligations = []
    if obligation_ids:
        obligations = accessible_obligations(request.user).filter(
            id__in=obligation_ids
        ).select_related('client', 'obligation_type')

    # Group by client
    clients_obligations = {}
    for ob in obligations:
        client_id = ob.client.id
        if client_id not in clients_obligations:
            clients_obligations[client_id] = {
                'client': ob.client,
                'obligations': [],
                'attachments': [],
            }
        clients_obligations[client_id]['obligations'].append(ob)
        if ob.attachment:
            clients_obligations[client_id]['attachments'].append({
                'obligation_id': ob.id,
                'filename': os.path.basename(ob.attachment.name),
                'url': ob.attachment.url,
                'size': ob.attachment.size if hasattr(ob.attachment, 'size') else 0,
            })

    # Email templates
    templates = EmailTemplate.objects.filter(is_active=True).order_by('name')

    context = {
        'obligations': obligations,
        'clients_obligations': clients_obligations,
        'templates': templates,
        'obligation_ids': ','.join(map(str, obligation_ids)),
    }

    return render(request, 'accounting/email_compose.html', context)


# =============================================================================
# SEND EMAIL
# =============================================================================

@staff_member_required
@require_POST
def email_send_view(request):
    """
    Αποστολή email με attachments.
    """
    if not check_model_perms(request, 'accounting.send_client_email'):
        return JsonResponse(PERM_DENIED_JSON, status=403)
    try:
        # Parse data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = {
                'client_id': request.POST.get('client_id'),
                'obligation_ids': request.POST.getlist('obligation_ids'),
                'template_id': request.POST.get('template_id'),
                'subject': request.POST.get('subject'),
                'body': request.POST.get('body'),
                'include_attachments': request.POST.get('include_attachments') == 'true',
                'attachment_ids': request.POST.getlist('attachment_ids'),
            }

        client_id = data.get('client_id')
        obligation_ids = data.get('obligation_ids', [])

        if not client_id:
            return JsonResponse({
                'success': False,
                'error': 'Δεν καθορίστηκε πελάτης'
            }, status=400)

        client = get_object_or_404(accessible_clients(request.user), id=client_id)

        if not client.email:
            return JsonResponse({
                'success': False,
                'error': f'Ο πελάτης {client.eponimia} δεν έχει email'
            }, status=400)

        # Get template
        template_id = data.get('template_id')
        template = None
        if template_id:
            template = EmailTemplate.objects.filter(id=template_id).first()

        # Get obligations
        obligations = accessible_obligations(request.user).filter(
            id__in=obligation_ids
        ).select_related('client', 'obligation_type')

        # Build subject and body
        subject = data.get('subject', '')
        body = data.get('body', '')

        # If template, render it
        if template and obligations.exists():
            rendered_subject, rendered_body = EmailService.render_template(
                template,
                obligation=obligations.first(),
                user=request.user
            )
            if not subject:
                subject = rendered_subject
            if not body:
                body = rendered_body

        # Collect attachments
        attachments = []
        if data.get('include_attachments', True):
            attachment_ids = data.get('attachment_ids', [])
            for ob in obligations:
                if ob.attachment:
                    # If specific attachments selected, check if this one is included
                    if attachment_ids and str(ob.id) not in attachment_ids:
                        continue
                    attachments.append(ob.attachment.path)

        # Send email
        success, result = EmailService.send_email(
            recipient_email=client.email,
            subject=subject,
            body=body,
            client=client,
            obligation=obligations.first() if obligations.count() == 1 else None,
            template=template,
            user=request.user,
            attachments=attachments,
            html_body=body,
        )

        if success:
            return JsonResponse({
                'success': True,
                'message': f'Το email στάλθηκε επιτυχώς στο {client.email}',
                'email_log_id': result.id if hasattr(result, 'id') else None,
            })
        else:
            return JsonResponse({
                'success': False,
                'error': str(result)
            }, status=500)

    except Exception as e:
        logger.error(f"Email send error: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# BULK EMAIL SEND
# =============================================================================

@staff_member_required
@require_POST
def email_send_bulk_view(request):
    """
    Μαζική αποστολή email - 1 email ανά πελάτη με όλα τα attachments του.
    """
    if not check_model_perms(request, 'accounting.send_client_email'):
        return JsonResponse(PERM_DENIED_JSON, status=403)
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = {
                'obligation_ids': request.POST.getlist('obligation_ids'),
                'template_id': request.POST.get('template_id'),
                'include_attachments': request.POST.get('include_attachments') == 'true',
            }

        obligation_ids = data.get('obligation_ids', [])
        template_id = data.get('template_id')
        include_attachments = data.get('include_attachments', True)

        # Get template
        template = None
        if template_id:
            template = EmailTemplate.objects.filter(id=template_id).first()

        # Get obligations and group by client
        obligations = accessible_obligations(request.user).filter(
            id__in=obligation_ids
        ).select_related('client', 'obligation_type')

        clients_data = {}
        for ob in obligations:
            client_id = ob.client.id
            if client_id not in clients_data:
                clients_data[client_id] = {
                    'client': ob.client,
                    'obligations': [],
                    'attachments': [],
                }
            clients_data[client_id]['obligations'].append(ob)
            if ob.attachment and include_attachments:
                clients_data[client_id]['attachments'].append(ob.attachment.path)

        results = {
            'sent': [],
            'failed': [],
            'skipped': [],
        }

        for client_id, client_data in clients_data.items():
            client = client_data['client']

            if not client.email:
                results['skipped'].append({
                    'client': client.eponimia,
                    'reason': 'Δεν έχει email'
                })
                continue

            try:
                # Render template for first obligation
                first_ob = client_data['obligations'][0]
                if template:
                    subject, body = EmailService.render_template(
                        template,
                        obligation=first_ob,
                        user=request.user
                    )
                else:
                    subject = f"Ολοκλήρωση υποχρεώσεων - {first_ob.month:02d}/{first_ob.year}"
                    body = f"Αγαπητέ/ή {client.eponimia},\n\nΟλοκληρώθηκαν οι παρακάτω υποχρεώσεις:\n"
                    for ob in client_data['obligations']:
                        body += f"- {ob.obligation_type.name} ({ob.month:02d}/{ob.year})\n"

                success, result = EmailService.send_email(
                    recipient_email=client.email,
                    subject=subject,
                    body=body,
                    client=client,
                    template=template,
                    user=request.user,
                    attachments=client_data['attachments'],
                    html_body=body,
                )

                if success:
                    results['sent'].append({
                        'client': client.eponimia,
                        'email': client.email,
                        'obligations_count': len(client_data['obligations']),
                        'attachments_count': len(client_data['attachments']),
                    })
                else:
                    results['failed'].append({
                        'client': client.eponimia,
                        'error': str(result)
                    })

            except Exception as e:
                results['failed'].append({
                    'client': client.eponimia,
                    'error': str(e)
                })

        return JsonResponse({
            'success': True,
            'sent': len(results['sent']),
            'failed': len(results['failed']),
            'skipped': len(results['skipped']),
            'details': results,
        })

    except Exception as e:
        logger.error(f"Bulk email error: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# CLIENT FILES VIEW
# =============================================================================

@staff_member_required
def client_files_view(request, client_id):
    """
    Προβολή αρχείων πελάτη με δενδρική δομή.
    """
    client = get_object_or_404(accessible_clients(request.user), id=client_id)

    # Βάση αρχειοθέτησης (από FilingSystemSettings)
    archive_root = filing.get_archive_root()
    client_path = filing.get_client_folder_path(client)

    # Δημιουργία δομής αρχείων
    files_tree = {}

    if os.path.exists(client_path):
        for root, dirs, files in os.walk(client_path):
            rel_path = os.path.relpath(root, client_path)

            for filename in files:
                file_path = os.path.join(root, filename)
                file_stat = os.stat(file_path)

                # Parse path components
                parts = rel_path.split(os.sep) if rel_path != '.' else []

                # Create nested structure
                current = files_tree
                for part in parts:
                    if part not in current:
                        current[part] = {'_files': [], '_folders': {}}
                    current = current[part]['_folders'] if '_folders' in current[part] else current[part]

                # Add file
                if '_files' not in current:
                    current['_files'] = []

                # Media URL
                rel_file_path = os.path.relpath(file_path, archive_root)
                media_url = os.path.join(settings.MEDIA_URL, rel_file_path)

                current['_files'].append({
                    'name': filename,
                    'path': file_path,
                    'rel_path': rel_file_path,
                    'url': media_url,
                    'size': file_stat.st_size,
                    'modified': datetime.fromtimestamp(file_stat.st_mtime),
                })

    # Υποχρεώσεις πελάτη με attachments
    obligations = MonthlyObligation.objects.filter(
        client=client
    ).exclude(
        attachment=''
    ).select_related('obligation_type').order_by('-year', '-month')

    # Documents
    documents = ClientDocument.objects.filter(client=client).order_by('-uploaded_at')

    context = {
        'client': client,
        'files_tree': files_tree,
        'client_path': client_path,
        'obligations': obligations,
        'documents': documents,
        'archive_root': archive_root,
    }

    return render(request, 'accounting/client_files.html', context)


# =============================================================================
# FILE DOWNLOAD / DELETE
# =============================================================================

@staff_member_required
def file_download(request, client_id, file_path):
    """
    Download αρχείου πελάτη.
    """
    client = get_object_or_404(accessible_clients(request.user), id=client_id)

    archive_root = filing.get_archive_root()
    full_path = os.path.realpath(os.path.join(archive_root, file_path))

    # Security check: το αρχείο πρέπει να είναι μέσα στον φάκελο του πελάτη
    client_root = os.path.realpath(filing.get_client_folder_path(client))
    if not full_path.startswith(client_root + os.sep):
        return HttpResponse('Access denied', status=403)

    if not os.path.exists(full_path):
        return HttpResponse('File not found', status=404)

    return FileResponse(
        open(full_path, 'rb'),
        as_attachment=True,
        filename=os.path.basename(full_path)
    )


@staff_member_required
@require_POST
def file_delete(request, client_id, file_path):
    """
    Διαγραφή αρχείου πελάτη.
    """
    if not check_model_perms(request, 'accounting.delete_clientdocument'):
        return JsonResponse(PERM_DENIED_JSON, status=403)
    client = get_object_or_404(accessible_clients(request.user), id=client_id)

    archive_root = filing.get_archive_root()
    full_path = os.path.realpath(os.path.join(archive_root, file_path))

    # Security check: το αρχείο πρέπει να είναι μέσα στον φάκελο του πελάτη
    client_root = os.path.realpath(filing.get_client_folder_path(client))
    if not full_path.startswith(client_root + os.sep):
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

    if not os.path.exists(full_path):
        return JsonResponse({'success': False, 'error': 'File not found'}, status=404)

    try:
        os.remove(full_path)
        logger.info(f"File deleted: {full_path} by {request.user.username}")

        return JsonResponse({
            'success': True,
            'message': 'Το αρχείο διαγράφηκε επιτυχώς'
        })

    except Exception as e:
        logger.error(f"File delete error: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# =============================================================================
# OPEN FOLDER VIEW
# =============================================================================

@staff_member_required
def open_document_folder(request, document_id):
    """
    Επιστρέφει σελίδα με το path του φακέλου για τοπικό άνοιγμα.

    Στα Windows, ο χρήστης μπορεί να κάνει copy το path και να το
    επικολλήσει στον Explorer. Σε μελλοντική έκδοση μπορεί να
    χρησιμοποιηθεί JavaScript με file:// protocol (με περιορισμούς
    ασφαλείας του browser).
    """
    document = get_object_or_404(accessible_documents(request.user), id=document_id)

    folder_path = document.folder_path
    full_file_path = document.full_path

    # Windows path conversion (αν χρειάζεται)
    windows_path = None
    if folder_path:
        windows_path = folder_path.replace('/', '\\')

    context = {
        'document': document,
        'folder_path': folder_path,
        'full_file_path': full_file_path,
        'windows_path': windows_path,
        'client': document.client,
    }

    # Αν ζητηθεί JSON response
    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({
            'folder_path': folder_path,
            'full_file_path': full_file_path,
            'windows_path': windows_path,
            'client_name': document.client.eponimia if document.client else None,
        })

    return render(request, 'accounting/open_folder.html', context)


@staff_member_required
def open_client_folder(request, client_id):
    """
    Άνοιγμα φακέλου πελάτη.
    """
    client = get_object_or_404(accessible_clients(request.user), id=client_id)

    folder_path = filing.get_client_folder_path(client)

    # Windows path conversion
    windows_path = folder_path.replace('/', '\\')

    context = {
        'client': client,
        'folder_path': folder_path,
        'windows_path': windows_path,
    }

    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({
            'folder_path': folder_path,
            'windows_path': windows_path,
            'client_name': client.eponimia,
        })

    return render(request, 'accounting/open_folder.html', context)


# =============================================================================
# ARCHIVE SETTINGS VIEW
# =============================================================================

@staff_member_required
def archive_settings_view(request):
    """
    Προβολή και επεξεργασία ρυθμίσεων αρχειοθέτησης.
    """
    # Current settings
    archive_root = getattr(settings, 'ARCHIVE_ROOT', settings.MEDIA_ROOT)
    media_root = settings.MEDIA_ROOT

    # Archive configurations per obligation type
    configs = ArchiveConfiguration.objects.select_related(
        'obligation_type'
    ).order_by('obligation_type__name')

    # Obligation types without config
    configured_types = configs.values_list('obligation_type_id', flat=True)
    unconfigured_types = ObligationType.objects.filter(
        is_active=True
    ).exclude(id__in=configured_types)

    if request.method == 'POST':
        # Update configuration
        config_id = request.POST.get('config_id')
        if config_id:
            config = get_object_or_404(ArchiveConfiguration, id=config_id)
            config.folder_pattern = request.POST.get('folder_pattern', config.folder_pattern)
            config.filename_pattern = request.POST.get('filename_pattern', config.filename_pattern)
            config.save()
            messages.success(request, f'Οι ρυθμίσεις για "{config.obligation_type.name}" ενημερώθηκαν')

        return redirect('accounting:archive_settings')

    # Pattern variables help
    pattern_variables = {
        'folder': [
            ('{client_afm}', 'ΑΦΜ πελάτη'),
            ('{client_name}', 'Επωνυμία πελάτη'),
            ('{year}', 'Έτος'),
            ('{month}', 'Μήνας (01-12)'),
            ('{type_code}', 'Κωδικός υποχρέωσης'),
        ],
        'filename': [
            ('{type_code}', 'Κωδικός υποχρέωσης'),
            ('{month}', 'Μήνας'),
            ('{year}', 'Έτος'),
            ('{original_name}', 'Αρχικό όνομα αρχείου'),
        ],
    }

    context = {
        'archive_root': archive_root,
        'media_root': media_root,
        'configs': configs,
        'unconfigured_types': unconfigured_types,
        'pattern_variables': pattern_variables,
    }

    return render(request, 'accounting/archive_settings.html', context)


@staff_member_required
@require_POST
def archive_config_create(request):
    """
    Δημιουργία νέας ρύθμισης αρχειοθέτησης.
    """
    obligation_type_id = request.POST.get('obligation_type_id')
    if not obligation_type_id:
        return JsonResponse({'success': False, 'error': 'Δεν επιλέχθηκε τύπος'}, status=400)

    obligation_type = get_object_or_404(ObligationType, id=obligation_type_id)

    # Check if already exists
    if ArchiveConfiguration.objects.filter(obligation_type=obligation_type).exists():
        return JsonResponse({'success': False, 'error': 'Υπάρχει ήδη ρύθμιση'}, status=400)

    config = ArchiveConfiguration.objects.create(
        obligation_type=obligation_type,
        folder_pattern='clients/{client_afm}_{client_name}/{year}/{month}/{type_code}/',
        filename_pattern='{type_code}_{month}_{year}.pdf',
    )

    messages.success(request, f'Δημιουργήθηκε ρύθμιση για "{obligation_type.name}"')

    return JsonResponse({
        'success': True,
        'config_id': config.id,
    })
