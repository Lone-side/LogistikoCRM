# accounting/views/obligations.py
"""
Obligation Views - Complete management of monthly obligations

Contains:
- Quick complete single obligation
- Bulk complete multiple obligations
- Advanced bulk complete with grouping
- Obligation detail view
- Wizard API for bulk completion
- Duplicate checking
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.files.base import ContentFile

from ..models import (
    ClientProfile, MonthlyObligation, ObligationType,
    ClientDocument
)

# Ενιαία υπηρεσία αρχειοθέτησης (validation + ClientDocument + φάκελοι)
from ..services import filing
from django.core.exceptions import ValidationError as DjangoValidationError

import logging
import json
from accounting.services.access import (
    accessible_clients, accessible_documents, accessible_obligations,
    mask_pii_value,
)

logger = logging.getLogger(__name__)


# ============================================
# QUICK COMPLETE WITH FILE UPLOAD
# ============================================

@require_POST
@staff_member_required
def quick_complete_obligation(request, obligation_id):
    """
    Quick complete single obligation with optional file attachment
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_monthlyobligation'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )
    if request.FILES and not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα δημιουργίας εγγράφων.'},
            status=403,
        )

    try:
        obligation = accessible_obligations(request.user).get(id=obligation_id)

        # Handle both FormData and JSON requests
        if 'multipart/form-data' in request.META.get('CONTENT_TYPE', ''):
            # Form data with file upload
            time_spent = request.POST.get('time_spent', 0)
            notes = request.POST.get('notes', '')
            attachment = request.FILES.get('attachment')
        else:
            # JSON data (no file)
            data = json.loads(request.body)
            time_spent = data.get('time_spent', 0)
            notes = data.get('notes', '')
            attachment = None

        # Update obligation
        obligation.status = 'completed'
        obligation.completed_date = timezone.now().date()
        obligation.completed_by = request.user

        # Handle time spent
        if time_spent:
            try:
                obligation.time_spent = float(time_spent)
            except (ValueError, TypeError):
                pass

        # Handle notes with timestamp
        if notes:
            timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
            new_note = f"[{timestamp}] {notes}"
            if obligation.notes:
                obligation.notes += f"\n{new_note}"
            else:
                obligation.notes = new_note

        # Handle file attachment (validation μέσω FilingSystemSettings)
        if 'attachment' in request.FILES:
            try:
                document = filing.create_client_document(
                    client=obligation.client,
                    uploaded_file=request.FILES['attachment'],
                    obligation=obligation,
                    user=request.user,
                )
            except DjangoValidationError as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Μη έγκυρο αρχείο: {"; ".join(e.messages)}'
                }, status=400)
            logger.info(f'Αρχειοθετήθηκε: {document.file.name}')
        obligation.save()

        # Success response
        message = f'{obligation.obligation_type.name} oloklirothike!'
        if time_spent:
            message += f' ({time_spent}h)'
        if attachment:
            message += ' (file)'

        return JsonResponse({
            'success': True,
            'message': message
        })

    except MonthlyObligation.DoesNotExist:
        return JsonResponse(
            {'success': False, 'message': 'Ypoxreosi den vrethike'},
            status=404
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {'success': False, 'message': 'Μη έγκυρα δεδομένα JSON'},
            status=400
        )
    except Exception:
        logger.exception("Error in quick_complete")
        return JsonResponse(
            {'success': False, 'message': 'Παρουσιάστηκε σφάλμα'},
            status=500
        )


# ============================================
# BULK COMPLETE (SIMPLE VERSION)
# ============================================

@require_POST
@staff_member_required
def bulk_complete_view(request):
    """
    Simple bulk complete - all obligations get same treatment
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_monthlyobligation'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )
    if request.FILES and not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα δημιουργίας εγγράφων.'},
            status=403,
        )

    try:
        try:
            obligation_ids = json.loads(request.POST.get('obligation_ids', '[]'))
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Μη έγκυρα δεδομένα JSON (obligation_ids)'
            }, status=400)
        time_spent = request.POST.get('time_spent', '0')
        if time_spent:
            try:
                float(time_spent)
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'message': 'Μη έγκυρη τιμή για time_spent'
                }, status=400)
        notes = request.POST.get('notes', '')
        attachments = request.FILES.getlist('attachments')

        # Επικύρωση όλων των αρχείων πριν την επεξεργασία (βάσει ρυθμίσεων)
        for attachment in attachments:
            try:
                filing.validate_upload(attachment)
            except DjangoValidationError as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Μη έγκυρο αρχείο "{attachment.name}": {"; ".join(e.messages)}'
                }, status=400)

        if not obligation_ids:
            return JsonResponse({
                'success': False,
                'message': 'Den epilexthikan ypoxreoseis'
            })

        obligations = accessible_obligations(request.user).filter(id__in=obligation_ids)
        completed_count = 0

        for idx, obl in enumerate(obligations):
            obl.status = 'completed'
            obl.completed_date = timezone.now().date()
            obl.completed_by = request.user

            if time_spent:
                obl.time_spent = float(time_spent)

            if notes:
                timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
                new_note = f"[{timestamp}] [BULK] {notes}"
                if obl.notes:
                    obl.notes += f"\n{new_note}"
                else:
                    obl.notes = new_note

            obl.save()

            # Attach file if available (already validated above)
            if idx < len(attachments):
                filing.create_client_document(
                    client=obl.client,
                    uploaded_file=attachments[idx],
                    obligation=obl,
                    user=request.user,
                )

            completed_count += 1

        return JsonResponse({
            'success': True,
            'completed_count': completed_count,
            'message': f'Oloklirothikan {completed_count} ypoxreoseis!'
        })

    except Exception as e:
        logger.exception("Error in bulk_complete")
        return JsonResponse({
            'success': False,
            'message': 'Παρουσιάστηκε σφάλμα'
        }, status=500)


# ============================================
# ADVANCED BULK COMPLETE WITH GROUPING
# ============================================

@require_POST
@staff_member_required
def advanced_bulk_complete(request):
    """Advanced bulk complete with full debugging"""
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_monthlyobligation'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )
    if request.FILES and not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα δημιουργίας εγγράφων.'},
            status=403,
        )


    logger.info("="*50)
    logger.info("ADVANCED BULK COMPLETE - START")
    logger.info(f"Method: {request.method}")
    try:
        # Get completion data
        completion_data_raw = request.POST.get('completion_data', '[]')
        logger.info(f"completion_data length: {len(completion_data_raw)} chars")

        completion_data = json.loads(completion_data_raw)
        notes = request.POST.get('notes', '')

        logger.info(f"Parsed completion_data: {len(completion_data)} groups")

        if not completion_data:
            logger.warning("No completion data found!")
            return JsonResponse({
                'success': False,
                'message': 'Den yparxoun dedomena oloklirosis',
                'completed_count': 0
            })

        completed_count = 0
        errors = []
        processed_details = []

        # Process each group
        for i, group_data in enumerate(completion_data):
            logger.info(f"\n--- Processing group {i+1}/{len(completion_data)} ---")

            client_afm = group_data.get('client_afm', 'NO_AFM')
            group_num = group_data.get('group', '0')
            obligation_ids = group_data.get('obligations', [])

            logger.info(f"AFM: {mask_pii_value(client_afm)}, Group: {group_num}, Obligations: {obligation_ids}")

            # Get files for this group
            files_key = f"file_{client_afm}_{group_num}"
            files = request.FILES.getlist(files_key)

            logger.info(f"Looking for files with key: {files_key}")
            logger.info(f"Found {len(files)} files")

            if files:
                for f in files:
                    logger.info(f"  - File: {f.name} ({f.size} bytes)")

            # Process obligations
            for j, obl_id in enumerate(obligation_ids):
                try:
                    logger.info(f"  Processing obligation {obl_id}...")

                    obligation = accessible_obligations(request.user).get(id=obl_id)

                    # Update status
                    obligation.status = 'completed'
                    obligation.completed_date = timezone.now().date()
                    obligation.completed_by = request.user

                    # Add notes
                    if notes:
                        timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
                        new_note = f"[{timestamp}] {notes}"
                        if obligation.notes:
                            obligation.notes += f"\n{new_note}"
                        else:
                            obligation.notes = new_note

                    # Handle file
                    obligation.save()
                    if group_num == '0':  # Individual files
                        if j < len(files):
                            logger.info(f"    Archiving individual file {j}: {files[j].name}")
                            document = filing.create_client_document(
                                client=obligation.client,
                                uploaded_file=files[j],
                                obligation=obligation,
                                user=request.user,
                            )
                            processed_details.append(f"{obligation.obligation_type.name}: {document.file.name}")
                            logger.info(f"    Archived to: {document.file.name}")
                        else:
                            processed_details.append(f"{obligation.obligation_type.name} (xoris arxeio)")
                            logger.info(f"    No file for this obligation")
                    else:  # Group file
                        if files:
                            file_to_use = files[0]
                            logger.info(f"    Using group file: {file_to_use.name}")

                            # Create copy for each obligation
                            file_content = file_to_use.read()
                            file_copy = ContentFile(file_content)
                            file_copy.name = file_to_use.name
                            file_to_use.seek(0)  # Reset for next use

                            document = filing.create_client_document(
                                client=obligation.client,
                                uploaded_file=file_copy,
                                obligation=obligation,
                                user=request.user,
                            )
                            processed_details.append(f"{obligation.obligation_type.name} (Group {group_num})")
                            logger.info(f"    Archived to: {document.file.name}")
                        else:
                            processed_details.append(f"{obligation.obligation_type.name} (no file)")

                    completed_count += 1
                    logger.info(f"    Completed successfully")

                except MonthlyObligation.DoesNotExist:
                    error_msg = f"Obligation {obl_id} not found"
                    logger.error(f"    {error_msg}")
                    errors.append(error_msg)
                except Exception:
                    logger.exception(f"    Error completing obligation {obl_id}")
                    errors.append(f"Σφάλμα στην υποχρέωση {obl_id}")

        # Final summary
        logger.info(f"\n=== SUMMARY ===")
        logger.info(f"Completed: {completed_count}")
        logger.info(f"Errors: {len(errors)}")

        if completed_count > 0:
            message = f'Oloklirothikan {completed_count} ypoxreoseis!'
            if errors:
                message += f' ({len(errors)} sfalmata)'
            success = True
        else:
            message = 'Kamia ypoxreosi den oloklirothike'
            success = False

        response_data = {
            'success': success,
            'completed_count': completed_count,
            'message': message,
            'errors': errors[:5],
            'details': processed_details[:10]
        }

        logger.info(f"Bulk complete: {completed_count} completed, "
                    f"{len(errors)} errors")

        return JsonResponse(response_data)

    except json.JSONDecodeError:
        logger.exception("advanced_bulk_complete: invalid JSON payload")
        return JsonResponse({
            'success': False,
            'message': 'Μη έγκυρα δεδομένα',
            'completed_count': 0
        }, status=400)

    except Exception:
        logger.exception("advanced_bulk_complete: critical error")
        return JsonResponse({
            'success': False,
            'message': 'Παρουσιάστηκε σφάλμα',
            'completed_count': 0
        }, status=500)


# ============================================
# CHECK DUPLICATE OBLIGATION
# ============================================

@require_GET
@staff_member_required
def check_obligation_duplicate(request):
    """
    AJAX endpoint for checking duplicate obligations
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.view_monthlyobligation'):
        return JsonResponse(
            {'exists': False, 'error': 'Δεν έχετε δικαίωμα.'}, status=403)

    client_id = request.GET.get('client')
    type_id = request.GET.get('type')
    year = request.GET.get('year')
    month = request.GET.get('month')

    if not all([client_id, type_id, year, month]):
        return JsonResponse({'exists': False})

    try:
        client_id = int(client_id)
        type_id = int(type_id)
        year = int(year)
        month = int(month)
    except (ValueError, TypeError):
        return JsonResponse({
            'exists': False,
            'error': 'Μη έγκυρες παράμετροι'
        }, status=400)

    exists = accessible_obligations(request.user).filter(
        client_id=client_id,
        obligation_type_id=type_id,
        year=year,
        month=month
    ).exists()

    return JsonResponse({'exists': exists})


# ============================================
# COMPLETE WITH FILE
# ============================================

@require_POST
@staff_member_required
def complete_with_file(request, obligation_id):
    """
    Complete obligation WITH file upload
    Handles multipart/form-data for file upload + completion
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_monthlyobligation'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )
    if request.FILES and not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα δημιουργίας εγγράφων.'},
            status=403,
        )

    try:
        obligation = accessible_obligations(request.user).get(id=obligation_id)

        # Validate file
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'Den anevasate arxeio'
            }, status=400)

        # Create ClientDocument (validation βάσει ρυθμίσεων + versioning + φάκελοι)
        try:
            document = filing.create_client_document(
                client=obligation.client,
                uploaded_file=request.FILES['file'],
                category=request.POST.get('category', 'general'),
                obligation=obligation,
                user=request.user,
                description=request.POST.get('description', ''),
            )
        except DjangoValidationError as e:
            return JsonResponse({
                'success': False,
                'error': f'Μη έγκυρο αρχείο: {"; ".join(e.messages)}'
            }, status=400)

        # Update obligation
        old_status = obligation.status
        obligation.status = 'completed'
        obligation.completed_date = timezone.now().date()
        obligation.completed_by = request.user

        # Update time spent if provided
        time_spent = request.POST.get('time_spent')
        if time_spent:
            try:
                obligation.time_spent = float(time_spent)
            except ValueError:
                pass

        obligation.save()

        # Log to audit trail
        try:
            from common.models import AuditLog
            AuditLog.log(
                user=request.user,
                action='update',
                obj=obligation,
                changes={
                    'status': {'old': old_status, 'new': 'completed'},
                    'attachment': {'old': None, 'new': document.filename}
                },
                description=f'Oloklirosi me arxeio: {obligation}',
                severity='medium',
                request=request
            )
        except Exception as audit_error:
            logger.warning(f"Could not create audit log: {audit_error}")

        # Send email notification if requested
        send_email = request.POST.get('send_email') == '1'
        if send_email:
            try:
                from accounting.services.email_service import trigger_automation_rules
                emails_created = trigger_automation_rules(obligation, trigger_type='on_complete')
                logger.info(f'Created {len(emails_created)} email notifications for obligation {obligation_id}')
            except Exception as email_error:
                logger.warning(f"Could not send emails: {email_error}")

        return JsonResponse({
            'success': True,
            'message': 'To arxeio anevike kai i ypoxreosi oloklirothike!' +
                      (' (Email stalthike)' if send_email else ''),
            'document_id': document.id,
            'obligation_id': obligation.id
        })

    except MonthlyObligation.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'I ypoxreosi den vrethike'
        }, status=404)
    except Exception:
        logger.exception(f'Error completing obligation {obligation_id} with file')
        return JsonResponse({
            'success': False,
            'error': 'Παρουσιάστηκε σφάλμα'
        }, status=500)


# ============================================
# BULK COMPLETE OBLIGATIONS
# ============================================

@require_POST
@staff_member_required
def bulk_complete_obligations(request):
    """
    Bulk complete multiple obligations with optional file upload
    Handles mass completion with optional file
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_monthlyobligation'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )
    if request.FILES and not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα δημιουργίας εγγράφων.'},
            status=403,
        )

    try:
        # Get obligation IDs
        obligation_ids_str = request.POST.get('obligation_ids')
        if not obligation_ids_str:
            return JsonResponse({
                'success': False,
                'error': 'Den epilexate ypoxreoseis'
            }, status=400)

        obligation_ids = json.loads(obligation_ids_str)

        if not obligation_ids:
            return JsonResponse({
                'success': False,
                'error': 'Den epilexate ypoxreoseis'
            }, status=400)

        # Get obligations
        obligations = accessible_obligations(request.user).filter(
            id__in=obligation_ids,
            status__in=['pending', 'overdue']
        )

        if not obligations.exists():
            return JsonResponse({
                'success': False,
                'error': 'Den vrethikan egkyres ypoxreoseis pros oloklirosi'
            }, status=404)

        # Get optional parameters
        send_email = request.POST.get('send_email') == '1'
        category = request.POST.get('category', 'general')
        description = request.POST.get('description', '')
        uploaded_file = request.FILES.get('file')

        # Validate file if provided (βάσει ρυθμίσεων)
        if uploaded_file:
            try:
                filing.validate_upload(uploaded_file)
            except DjangoValidationError as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Μη έγκυρο αρχείο: {"; ".join(e.messages)}'
                }, status=400)

        completed_count = 0
        failed_count = 0
        errors = []

        # Complete each obligation
        for obligation in obligations:
            try:
                old_status = obligation.status
                obligation.status = 'completed'
                obligation.completed_date = timezone.now().date()
                obligation.completed_by = request.user

                obligation.save()

                # Attach file if provided — αντίγραφο ανά υποχρέωση
                if uploaded_file:
                    uploaded_file.seek(0)
                    file_copy = ContentFile(uploaded_file.read())
                    file_copy.name = uploaded_file.name
                    filing.create_client_document(
                        client=obligation.client,
                        uploaded_file=file_copy,
                        category=category,
                        obligation=obligation,
                        user=request.user,
                        description=description or f'Μαζική ολοκλήρωση - {timezone.now().date()}',
                    )

                # Audit log
                try:
                    from common.models import AuditLog
                    AuditLog.log(
                        user=request.user,
                        action='update',
                        obj=obligation,
                        changes={
                            'status': {'old': old_status, 'new': 'completed'},
                            'bulk_completion': True
                        },
                        description=f'Maziki oloklirosi: {obligation}',
                        severity='medium',
                        request=request
                    )
                except Exception as audit_error:
                    logger.warning(f"Could not create audit log: {audit_error}")

                # Send email if requested
                if send_email:
                    try:
                        from accounting.services.email_service import trigger_automation_rules
                        trigger_automation_rules(obligation, trigger_type='on_complete')
                    except Exception as email_error:
                        logger.warning(f"Could not send email: {email_error}")

                completed_count += 1

            except Exception:
                failed_count += 1
                errors.append(f'{obligation.client.eponimia} - {obligation.obligation_type.name}: σφάλμα')
                logger.exception(f'Error bulk completing obligation {obligation.id}')

        # Build response message
        message = f'Oloklirothikan {completed_count} ypoxreoseis epityxos'
        if failed_count > 0:
            message += f' ({failed_count} apetyxan)'

        return JsonResponse({
            'success': True,
            'message': message,
            'completed_count': completed_count,
            'failed_count': failed_count,
            'errors': errors if errors else None
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Mh egkyra dedomena ypoxreoseon'
        }, status=400)
    except Exception:
        logger.exception('Error in bulk completion')
        return JsonResponse({
            'success': False,
            'error': 'Παρουσιάστηκε σφάλμα'
        }, status=500)


# ============================================
# OBLIGATION DETAIL VIEW
# ============================================

@staff_member_required
def obligation_detail_view(request, obligation_id):
    """
    Detail view for MonthlyObligation
    Allows viewing and editing all fields + document upload
    """
    try:
        obligation = accessible_obligations(request.user).select_related(
            'client', 'obligation_type', 'completed_by'
        ).prefetch_related(
            'client__documents'
        ).get(id=obligation_id)

        # Get all documents for this obligation
        documents = accessible_documents(request.user).filter(
            Q(obligation=obligation) | Q(client=obligation.client)
        ).order_by('-uploaded_at')

        # Handle POST (edit obligation)
        if request.method == 'POST':
            from accounting.services.access import check_model_perms
            if not check_model_perms(request, 'accounting.change_monthlyobligation'):
                messages.error(request, 'Δεν έχετε δικαίωμα επεξεργασίας υποχρεώσεων.')
                return redirect('accounting:obligation_detail', obligation_id=obligation.id)

            # Update obligation fields
            obligation.notes = request.POST.get('notes', '')

            time_spent = request.POST.get('time_spent')
            if time_spent:
                try:
                    obligation.time_spent = float(time_spent)
                except ValueError:
                    pass

            hourly_rate = request.POST.get('hourly_rate')
            if hourly_rate:
                try:
                    obligation.hourly_rate = float(hourly_rate)
                except ValueError:
                    pass

            obligation.save()

            messages.success(request, 'I ypoxreosi enimeroothike epityxos!')
            return redirect('accounting:obligation_detail', obligation_id=obligation.id)

        context = {
            'obligation': obligation,
            'documents': documents,
            'title': f'Ypoxreosi #{obligation.id} - {obligation.client.eponimia}',
        }

        return render(request, 'accounting/obligation_detail.html', context)

    except MonthlyObligation.DoesNotExist:
        messages.error(request, 'I ypoxreosi den vrethike')
        return redirect('accounting:dashboard')


# ============================================
# WIZARD API - Get Obligation Details for Wizard
# ============================================

@staff_member_required
@require_GET
def api_obligations_wizard(request):
    """
    API endpoint for bulk completion wizard.
    Returns details for selected obligations.
    """
    try:
        ids_param = request.GET.get('ids', '')
        if not ids_param:
            return JsonResponse({
                'success': False,
                'error': 'Den parexontai IDs ypoxreoseon'
            }, status=400)

        # Parse IDs
        try:
            ids = [int(id.strip()) for id in ids_param.split(',') if id.strip()]
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Mh egkyra IDs ypoxreoseon'
            }, status=400)

        if not ids:
            return JsonResponse({
                'success': False,
                'error': 'Den parexontai IDs ypoxreoseon'
            }, status=400)

        # Get obligations with related data
        obligations = accessible_obligations(request.user).filter(
            id__in=ids
        ).select_related(
            'client', 'obligation_type'
        ).order_by('deadline', 'client__eponimia')

        # Format data for wizard
        MONTH_NAMES = {
            1: 'Ianouarios', 2: 'Fevrouarios', 3: 'Martios', 4: 'Aprilios',
            5: 'Maios', 6: 'Iounios', 7: 'Ioulios', 8: 'Avgoustos',
            9: 'Septemvrios', 10: 'Oktovrios', 11: 'Noemvrios', 12: 'Dekemvrios'
        }

        # Ένα batch query για τα έγγραφα όλων των υποχρεώσεων (όχι 1/υποχρέωση)
        docs_by_obligation = {}
        for doc in accessible_documents(request.user).filter(
            obligation_id__in=[ob.id for ob in obligations]
        ).values('id', 'filename', 'uploaded_at', 'obligation_id'):
            docs_by_obligation.setdefault(doc.pop('obligation_id'), []).append(doc)

        obligations_data = []
        for ob in obligations:
            existing_docs = docs_by_obligation.get(ob.id, [])

            obligations_data.append({
                'id': ob.id,
                'client_id': ob.client.id,
                'client_name': ob.client.eponimia,
                'client_afm': ob.client.afm,
                'client_email': ob.client.email or '',
                'obligation_type': ob.obligation_type.name,
                'obligation_code': ob.obligation_type.code,
                'period_month': ob.month,
                'period_year': ob.year,
                'period_display': f"{MONTH_NAMES.get(ob.month, ob.month)} {ob.year}",
                'due_date': ob.deadline.strftime('%d/%m/%Y') if ob.deadline else '',
                'due_date_iso': ob.deadline.isoformat() if ob.deadline else '',
                'status': ob.status,
                'notes': ob.notes or '',
                'has_attachment': bool(ob.attachment),
                'existing_documents': list(existing_docs),
            })

        return JsonResponse({
            'success': True,
            'count': len(obligations_data),
            'obligations': obligations_data
        })

    except Exception:
        logger.exception("Error in api_obligations_wizard")
        return JsonResponse({
            'success': False,
            'error': 'Παρουσιάστηκε σφάλμα'
        }, status=500)


# ============================================
# WIZARD BULK PROCESS - Process Wizard Submissions
# ============================================

@require_POST
@staff_member_required
def wizard_bulk_process(request):
    """
    Process wizard submission for bulk obligation completion.
    Each obligation can have its own file.
    """
    from accounting.services.access import check_model_perms
    if not check_model_perms(request, 'accounting.change_monthlyobligation'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα για αυτή την ενέργεια.'},
            status=403,
        )
    if request.FILES and not check_model_perms(request, 'accounting.add_clientdocument'):
        return JsonResponse(
            {'success': False, 'error': 'Δεν έχετε δικαίωμα δημιουργίας εγγράφων.'},
            status=403,
        )

    try:
        # Parse results JSON
        results_str = request.POST.get('results', '{}')
        try:
            results = json.loads(results_str)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Mh egkyra dedomena apotelesmatwn'
            }, status=400)

        if not results:
            return JsonResponse({
                'success': False,
                'error': 'Den yparxoun ypoxreoseis pros epeksergasia'
            }, status=400)

        global_notes = request.POST.get('notes', '')

        completed_count = 0
        skipped_count = 0
        failed_count = 0
        errors = []
        processed_details = []

        # Process each obligation from results
        for ob_id_str, ob_data in results.items():
            try:
                ob_id = int(ob_id_str)

                # Skip if marked to skip
                if ob_data.get('skip', False):
                    skipped_count += 1
                    continue

                # Skip if not marked as complete
                if not ob_data.get('complete', False):
                    skipped_count += 1
                    continue

                obligation = accessible_obligations(request.user).select_related(
                    'client', 'obligation_type'
                ).get(id=ob_id)

                # Skip if already completed
                if obligation.status == 'completed':
                    skipped_count += 1
                    processed_details.append({
                        'id': ob_id,
                        'status': 'skipped',
                        'message': f'{obligation.client.eponimia} - {obligation.obligation_type.name}: Idi oloklirwmeni'
                    })
                    continue

                old_status = obligation.status

                # Update obligation
                obligation.status = 'completed'
                obligation.completed_date = timezone.now().date()
                obligation.completed_by = request.user

                # Handle time spent if provided
                time_spent = ob_data.get('time_spent')
                if time_spent:
                    try:
                        obligation.time_spent = float(time_spent)
                    except (ValueError, TypeError):
                        pass

                # Handle notes
                notes = ob_data.get('notes', '')
                combined_notes = f"{notes}\n{global_notes}".strip() if notes or global_notes else ''
                if combined_notes:
                    timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
                    new_note = f"[{timestamp}] [WIZARD] {combined_notes}"
                    if obligation.notes:
                        obligation.notes += f"\n{new_note}"
                    else:
                        obligation.notes = new_note

                # Handle file upload for this specific obligation
                file_key = f'file_{ob_id}'
                if file_key in request.FILES:
                    try:
                        document = filing.create_client_document(
                            client=obligation.client,
                            uploaded_file=request.FILES[file_key],
                            obligation=obligation,
                            category=ob_data.get('category', 'general'),
                            user=request.user,
                            description=f"Wizard upload - {timezone.now().strftime('%d/%m/%Y')}",
                        )
                        logger.info(f"Wizard: Archived file for obligation {ob_id}: {document.file.name}")
                    except DjangoValidationError as file_error:
                        logger.warning(
                            f"Invalid file for {ob_id}: {'; '.join(file_error.messages)}"
                        )

                obligation.save()

                # Audit log
                try:
                    from common.models import AuditLog
                    AuditLog.log(
                        user=request.user,
                        action='update',
                        obj=obligation,
                        changes={
                            'status': {'old': old_status, 'new': 'completed'},
                            'wizard_completion': True
                        },
                        description=f'Wizard oloklirosi: {obligation}',
                        severity='medium',
                        request=request
                    )
                except Exception as audit_error:
                    logger.warning(f"Could not create audit log: {audit_error}")

                # Send email if requested for this specific obligation
                should_send_email = ob_data.get('send_email', False)
                email_sent = False
                email_error_msg = None

                if should_send_email and obligation.client.email:
                    try:
                        from accounting.services.email_service import EmailService
                        success, result = EmailService.send_obligation_completion_email(
                            obligation=obligation,
                            user=request.user,
                            include_attachment=True
                        )
                        if success:
                            email_sent = True
                            logger.info(f"Email sent for obligation {ob_id} to client id={obligation.client_id}")
                        else:
                            email_error_msg = 'αποτυχία'
                            logger.warning(f"Could not send email for {ob_id}: {result}")
                    except Exception:
                        email_error_msg = 'αποτυχία'
                        logger.exception(f"Could not send email for {ob_id}")

                completed_count += 1
                message_parts = [f'{obligation.client.eponimia} - {obligation.obligation_type.name}: Oloklirothike']
                if email_sent:
                    message_parts.append('(email)')
                elif should_send_email and not email_sent:
                    message_parts.append(f'(email: {email_error_msg or "apotixia"})')

                processed_details.append({
                    'id': ob_id,
                    'status': 'completed',
                    'email_sent': email_sent,
                    'message': ' '.join(message_parts)
                })

            except MonthlyObligation.DoesNotExist:
                failed_count += 1
                errors.append(f'Ypoxreosi {ob_id_str} den vrethike')
            except Exception:
                failed_count += 1
                errors.append(f'Σφάλμα στην υποχρέωση {ob_id_str}')
                logger.exception(f"Error processing obligation {ob_id_str} in wizard")

        # Build response message
        if completed_count > 0:
            message = f'Oloklirothikan {completed_count} ypoxreoseis epityxos!'
            if skipped_count > 0:
                message += f' ({skipped_count} paraleifthikan)'
            if failed_count > 0:
                message += f' ({failed_count} apetyxan)'
            success = True
        else:
            if skipped_count > 0:
                message = f'{skipped_count} ypoxreoseis paraleifthikan, kamia den oloklirothike'
                success = True
            else:
                message = 'Kamia ypoxreosi den oloklirothike'
                success = False

        logger.info(f"Wizard bulk process by {request.user.username}: "
                   f"completed={completed_count}, skipped={skipped_count}, failed={failed_count}")

        return JsonResponse({
            'success': success,
            'message': message,
            'completed_count': completed_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'errors': errors[:10] if errors else [],
            'details': processed_details[:20] if processed_details else []
        })

    except Exception:
        logger.exception("Critical error in wizard_bulk_process")
        return JsonResponse({
            'success': False,
            'error': 'Παρουσιάστηκε σφάλμα'
        }, status=500)
