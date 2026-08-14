# accounting/api_door.py
"""
REST API endpoints for Tasmota door control.
JWT authenticated for React frontend.

Security features:
- Shared per-user/IP rate limiting
- Mandatory audit logging for all door mutations
- Explicit ``accounting.open_office_door`` permission
"""

import requests
import logging
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework.response import Response
from django.conf import settings

from .door_security import begin_door_mutation, finish_door_mutation

logger = logging.getLogger(__name__)

# Tasmota configuration from settings
TASMOTA_IP = getattr(settings, 'TASMOTA_IP', '192.168.1.100')
TASMOTA_PORT = getattr(settings, 'TASMOTA_PORT', 80)
TASMOTA_DOOR_PULSE_DURATION = getattr(settings, 'TASMOTA_DOOR_PULSE_DURATION', 0.5)
TIMEOUT = 5


class DoorStatusThrottle(UserRateThrottle):
    """
    Rate limit for door status checks.
    More lenient - max 30 status checks per minute.
    """
    rate = '30/minute'
    scope = 'door_status'


def log_door_access(request, action, result, response_data=None):
    """Log door access to audit trail"""
    try:
        mutation_audit = getattr(request, "_door_mutation_audit", None)
        if mutation_audit is not None:
            finish_door_mutation(mutation_audit, result, response_data)
            request._door_mutation_audit = None
            return
        from .models import DoorAccessLog
        DoorAccessLog.log_access(
            user=request.user if request.user.is_authenticated else None,
            action=action,
            result=result,
            request=request,
            response_data=response_data
        )
    except Exception as e:
        logger.error(f"Failed to log door access: {e}")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([DoorStatusThrottle])
def door_status(request):
    """
    Get door relay status.
    GET /api/v1/door/status/

    Returns:
        - success: bool
        - status: "open" | "closed" | "error"
        - raw_power: "ON" | "OFF"
        - online: bool
    """
    try:
        url = f"http://{TASMOTA_IP}:{TASMOTA_PORT}/cm?cmnd=Power"

        logger.info(f"Checking door status at {TASMOTA_IP}")
        response = requests.get(url, timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            power = data.get("POWER", "OFF")

            logger.info(f"Door status: {power}")

            response_data = {
                'success': True,
                'status': 'open' if power == 'ON' else 'closed',
                'raw_power': power,
                'online': True
            }
            log_door_access(request, 'status', 'success', response_data)
            return Response(response_data)
        else:
            response_data = {
                'success': False,
                'status': 'offline',
                'online': False,
                'message': 'Αποτυχία επικοινωνίας με τη συσκευή'
            }
            log_door_access(request, 'status', 'failed', response_data)
            return Response(response_data)

    except requests.exceptions.Timeout:
        logger.debug(f"Door status timeout at {TASMOTA_IP}")
        response_data = {
            'success': False,
            'status': 'offline',
            'online': False,
            'message': 'Timeout - η συσκευή δεν απαντά'
        }
        log_door_access(request, 'status', 'timeout', response_data)
        return Response(response_data)
    except requests.exceptions.ConnectionError:
        logger.debug(f"Door connection error at {TASMOTA_IP}")
        response_data = {
            'success': False,
            'status': 'offline',
            'online': False,
            'message': 'Δεν βρέθηκε η συσκευή'
        }
        log_door_access(request, 'status', 'offline', response_data)
        return Response(response_data)
    except Exception as e:
        logger.error(f"Door status error: {e}")
        response_data = {
            'success': False,
            'status': 'error',
            'online': False,
            'message': str(e)
        }
        log_door_access(request, 'status', 'failed', response_data)
        return Response(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def door_open(request):
    """
    Open/toggle the door via Tasmota relay.
    POST /api/v1/door/open/

    Requires: explicit ``accounting.open_office_door`` permission

    Returns:
        - success: bool
        - message: str (Greek)
        - new_status: "open" | "closed"
    """
    audit, rejection = begin_door_mutation(request, "toggle")
    if rejection:
        status, message = rejection
        return Response({"success": False, "message": message}, status=status)
    request._door_mutation_audit = audit

    try:
        # Toggle the relay
        url = f"http://{TASMOTA_IP}:{TASMOTA_PORT}/cm?cmnd=Power%20Toggle"

        logger.info(f"User {request.user.username} toggling door at {TASMOTA_IP}")
        response = requests.get(url, timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            new_power = data.get("POWER", "OFF")

            logger.info(f"Door toggled by {request.user.username}, new state: {new_power}")

            response_data = {
                'success': True,
                'message': 'Η πόρτα άνοιξε!' if new_power == 'ON' else 'Η πόρτα έκλεισε!',
                'new_status': 'open' if new_power == 'ON' else 'closed'
            }
            log_door_access(request, 'toggle', 'success', response_data)
            return Response(response_data)
        else:
            response_data = {
                'success': False,
                'message': 'Αποτυχία επικοινωνίας με τη συσκευή',
                'online': False
            }
            log_door_access(request, 'toggle', 'failed', response_data)
            return Response(response_data)

    except requests.exceptions.Timeout:
        logger.debug(f"Door toggle timeout for user {request.user.username}")
        response_data = {
            'success': False,
            'message': 'Timeout - η συσκευή δεν απαντά',
            'online': False
        }
        log_door_access(request, 'toggle', 'timeout', response_data)
        return Response(response_data)
    except requests.exceptions.ConnectionError:
        logger.debug(f"Door toggle connection error for user {request.user.username}")
        response_data = {
            'success': False,
            'message': 'Δεν βρέθηκε η συσκευή',
            'online': False
        }
        log_door_access(request, 'toggle', 'offline', response_data)
        return Response(response_data)
    except Exception:
        logger.error("Unexpected door toggle error for user %s", request.user.username)
        response_data = {
            'success': False,
            'message': 'Σφάλμα ελέγχου πόρτας',
            'online': False
        }
        log_door_access(request, 'toggle', 'failed', response_data)
        return Response(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def door_pulse(request):
    """
    Pulse the door relay (momentary on for electric locks).
    POST /api/v1/door/pulse/

    Requires: explicit ``accounting.open_office_door`` permission

    Optional body:
        - duration: float (seconds, default from TASMOTA_DOOR_PULSE_DURATION setting)

    Returns:
        - success: bool
        - message: str (Greek)
    """
    audit, rejection = begin_door_mutation(request, "pulse")
    if rejection:
        status, message = rejection
        return Response({"success": False, "message": message}, status=status)
    request._door_mutation_audit = audit

    try:
        duration = float(request.data.get('duration', TASMOTA_DOOR_PULSE_DURATION))

        # Tasmota uses deciseconds and PulseTime1=0 disables auto-off. Never
        # energize the relay with a value that rounds/truncates to zero.
        if not 0.1 <= duration <= 5:
            log_door_access(request, 'pulse', 'failed', {'success': False})
            return Response({
                'success': False,
                'message': 'Η διάρκεια pulse πρέπει να είναι μεταξύ 0.1 και 5 δευτερολέπτων'
            }, status=400)

        pulse_time = max(1, int(round(duration * 10)))

        # Set pulse time
        set_pulse_url = f"http://{TASMOTA_IP}:{TASMOTA_PORT}/cm?cmnd=PulseTime1%20{pulse_time}"
        configuration = requests.get(set_pulse_url, timeout=TIMEOUT)
        configured_value = None
        if configuration.status_code == 200:
            try:
                pulse_ack = configuration.json().get('PulseTime1')
                configured_value = (
                    pulse_ack.get('Set') if isinstance(pulse_ack, dict) else pulse_ack
                )
                configured_value = int(configured_value)
            except (AttributeError, TypeError, ValueError):
                configured_value = None
        if configured_value != pulse_time:
            response_data = {
                'success': False,
                'message': 'Η ασφαλής διάρκεια pulse δεν επιβεβαιώθηκε',
                'online': configuration.status_code == 200,
            }
            log_door_access(request, 'pulse', 'failed', response_data)
            return Response(response_data, status=502)

        # Trigger pulse
        pulse_url = f"http://{TASMOTA_IP}:{TASMOTA_PORT}/cm?cmnd=Power%20ON"

        logger.info(f"User {request.user.username} pulsing door for {duration}s")
        response = requests.get(pulse_url, timeout=TIMEOUT)

        confirmed_power = None
        if response.status_code == 200:
            try:
                power_ack = response.json()
                confirmed_power = power_ack.get('POWER1', power_ack.get('POWER'))
            except (AttributeError, TypeError, ValueError):
                confirmed_power = None

        if confirmed_power == 'ON':
            logger.info(f"Door pulsed by {request.user.username}")
            response_data = {
                'success': True,
                'message': f'Πόρτα ανοιχτή για {duration} δευτ.'
            }
            log_door_access(request, 'pulse', 'success', response_data)
            return Response(response_data)
        else:
            response_data = {
                'success': False,
                'message': 'Αποτυχία επικοινωνίας με τη συσκευή',
                'online': False
            }
            log_door_access(request, 'pulse', 'failed', response_data)
            return Response(response_data, status=502)

    except (TypeError, ValueError):
        response_data = {
            'success': False,
            'message': 'Μη έγκυρη διάρκεια pulse',
        }
        log_door_access(request, 'pulse', 'failed', response_data)
        return Response(response_data, status=400)
    except requests.exceptions.Timeout:
        response_data = {
            'success': False,
            'message': 'Timeout - η συσκευή δεν απαντά',
            'online': False
        }
        log_door_access(request, 'pulse', 'timeout', response_data)
        return Response(response_data, status=504)
    except requests.exceptions.ConnectionError:
        response_data = {
            'success': False,
            'message': 'Δεν βρέθηκε η συσκευή',
            'online': False
        }
        log_door_access(request, 'pulse', 'offline', response_data)
        return Response(response_data, status=503)
    except Exception:
        logger.error("Unexpected door pulse error")
        response_data = {
            'success': False,
            'message': 'Σφάλμα ελέγχου πόρτας',
            'online': False
        }
        log_door_access(request, 'pulse', 'failed', response_data)
        return Response(response_data, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def door_access_logs(request):
    """
    Get recent door access logs.
    GET /api/v1/door/logs/

    Query params:
        - limit: int (default 50, max 200)
        - user_id: int (filter by user)
        - action: str (filter by action type)

    Returns list of recent door access entries.
    """
    from .models import DoorAccessLog

    try:
        limit = int(request.query_params.get('limit', 50))
    except (ValueError, TypeError):
        limit = 50
    limit = min(max(limit, 1), 200)

    logs = DoorAccessLog.objects.select_related('user').all()

    # Optional filters
    user_id = request.query_params.get('user_id')
    if user_id:
        logs = logs.filter(user_id=user_id)

    action = request.query_params.get('action')
    if action:
        logs = logs.filter(action=action)

    logs = logs[:limit]

    return Response({
        'count': len(logs),
        'logs': [
            {
                'id': log.id,
                'user': log.user.username if log.user else None,
                'action': log.action,
                'action_display': log.get_action_display(),
                'result': log.result,
                'result_display': log.get_result_display(),
                'ip_address': log.ip_address,
                'timestamp': log.timestamp.isoformat(),
            }
            for log in logs
        ]
    })
