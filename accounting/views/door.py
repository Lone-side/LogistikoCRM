"""
Door Control Views (Tasmota IoT Integration)
Author: ddiplas
Description: Views for controlling office door via Tasmota device
"""

import requests
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.conf import settings

from accounting.door_security import begin_door_mutation, finish_door_mutation

logger = logging.getLogger(__name__)

# SECURITY: Load IP from settings instead of hardcoding
TASMOTA_IP = getattr(settings, 'TASMOTA_IP', '192.168.1.100')
TASMOTA_PORT = getattr(settings, 'TASMOTA_PORT', 80)
TIMEOUT = 2  # 2 seconds


@staff_member_required
@require_http_methods(["GET"])
def door_status(request):
    """Check door status - ON or OFF"""
    try:
        url = f"http://{TASMOTA_IP}:{TASMOTA_PORT}/cm?cmnd=Power"

        logger.info(f"Checking status at {TASMOTA_IP}")
        response = requests.get(url, timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            power = data.get("POWER", "OFF")

            logger.info(f"Status: {power}")

            return JsonResponse({
                "success": True,
                "status": "open" if power == "ON" else "closed",
                "raw_power": power
            })
        else:
            logger.error(f"HTTP {response.status_code}")
            return JsonResponse({
                "success": False,
                "error": f"HTTP {response.status_code}"
            }, status=500)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout connecting to {TASMOTA_IP}")
        return JsonResponse({
            "success": False,
            "error": "Timeout"
        }, status=504)

    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to {TASMOTA_IP}")
        return JsonResponse({
            "success": False,
            "error": f"Cannot connect to {TASMOTA_IP}"
        }, status=503)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return JsonResponse({
            "success": False,
            "error": "Σφάλμα επικοινωνίας με τη συσκευή"
        }, status=500)


@login_required
@require_http_methods(["POST"])
def open_door(request):
    """
    Toggle door - ON <-> OFF
    SECURITY: Authentication and CSRF protection enabled to prevent unauthorized door control
    """
    audit, rejection = begin_door_mutation(request, "toggle")
    if rejection:
        status, message = rejection
        return JsonResponse({"success": False, "error": message}, status=status)

    try:
        # TOGGLE command
        url = f"http://{TASMOTA_IP}:{TASMOTA_PORT}/cm?cmnd=Power%20TOGGLE"

        logger.info(f"Toggling door at {TASMOTA_IP}")
        response = requests.get(url, timeout=TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            new_state = data.get("POWER", "UNKNOWN")

            logger.info(f"New state: {new_state}")

            response_data = {
                "success": True,
                "new_state": new_state,
                "message": f"Πόρτα τώρα: {new_state}"
            }
            finish_door_mutation(audit, "success", response_data)
            return JsonResponse(response_data)
        else:
            logger.error(f"HTTP {response.status_code}")
            response_data = {
                "success": False,
                "error": f"HTTP {response.status_code}"
            }
            finish_door_mutation(audit, "failed", response_data)
            return JsonResponse(response_data, status=500)

    except requests.exceptions.Timeout:
        logger.error(f"Timeout toggling door at {TASMOTA_IP}")
        finish_door_mutation(audit, "timeout", {"success": False})
        return JsonResponse({
            "success": False,
            "error": "Timeout"
        }, status=504)

    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to {TASMOTA_IP}")
        finish_door_mutation(audit, "offline", {"success": False})
        return JsonResponse({
            "success": False,
            "error": f"Cannot connect to {TASMOTA_IP}"
        }, status=503)

    except Exception:
        logger.error("Unexpected legacy door toggle error")
        finish_door_mutation(audit, "failed", {"success": False})
        return JsonResponse({
            "success": False,
            "error": "Σφάλμα επικοινωνίας με τη συσκευή"
        }, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def door_control(request):
    """Unified door control endpoint - requires authentication"""
    if request.method == "POST":
        return open_door(request)
    else:
        return door_status(request)
