# common/api_health.py
"""
Health Check API Endpoints for LogistikoCRM

Provides endpoints for:
- /api/health/ - Basic health check (public)
- /api/health/detailed/ - Detailed system status (admin only)

Used for monitoring, load balancers, and Kubernetes probes.
"""

import logging
import time
from django.conf import settings
from django.db import connection
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Καταστάσεις component που καθιστούν το σύστημα μη λειτουργικό (503).
UNHEALTHY_COMPONENT_STATUSES = frozenset(
    {'unhealthy', 'critical', 'error', 'unavailable'}
)


def check_database():
    """Check database connectivity"""
    try:
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        latency = (time.time() - start) * 1000  # ms
        return {
            'status': 'healthy',
            'latency_ms': round(latency, 2)
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }


def check_cache():
    """Check cache (Redis/database) connectivity"""
    try:
        start = time.time()
        cache.set('health_check', 'ok', 10)
        result = cache.get('health_check')
        cache.delete('health_check')
        latency = (time.time() - start) * 1000  # ms

        if result == 'ok':
            return {
                'status': 'healthy',
                'latency_ms': round(latency, 2),
                'backend': getattr(settings, 'CACHES', {}).get('default', {}).get('BACKEND', 'unknown')
            }
        else:
            return {
                'status': 'degraded',
                'error': 'Cache read/write mismatch'
            }
    except Exception as e:
        logger.warning(f"Cache health check failed: {e}")
        return {
            'status': 'unavailable',
            'error': str(e)
        }


def check_celery():
    """Check Celery worker status"""
    try:
        from celery import current_app

        # Try to get registered tasks (doesn't require active workers)
        registered_tasks = list(current_app.tasks.keys())

        # Try to inspect active workers
        try:
            inspect = current_app.control.inspect(timeout=2)
            active = inspect.active()
            if active:
                worker_count = len(active)
                return {
                    'status': 'healthy',
                    'workers': worker_count,
                    'registered_tasks': len(registered_tasks)
                }
            else:
                return {
                    'status': 'degraded',
                    'workers': 0,
                    'message': 'No active workers found',
                    'registered_tasks': len(registered_tasks)
                }
        except Exception:
            return {
                'status': 'unknown',
                'message': 'Could not connect to workers',
                'registered_tasks': len(registered_tasks)
            }

    except ImportError:
        return {
            'status': 'unavailable',
            'message': 'Celery not installed'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def check_disk_space():
    """Check available disk space"""
    try:
        import shutil
        media_root = getattr(settings, 'MEDIA_ROOT', '/tmp')
        total, used, free = shutil.disk_usage(media_root)

        free_gb = free / (1024 ** 3)
        used_percent = (used / total) * 100

        status = 'healthy'
        if used_percent > 90:
            status = 'critical'
        elif used_percent > 80:
            status = 'warning'

        return {
            'status': status,
            'free_gb': round(free_gb, 2),
            'used_percent': round(used_percent, 1)
        }
    except Exception as e:
        return {
            'status': 'unknown',
            'error': str(e)
        }


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([])
def health_check(request):
    """
    Basic health check endpoint.
    GET /api/health/

    Returns 200 if the application is running.
    Used for load balancers and simple uptime monitoring.

    Response:
        - status: "healthy" | "unhealthy"
        - version: Application version
    """
    # Quick database check
    db_status = check_database()

    overall_status = 'healthy' if db_status['status'] == 'healthy' else 'unhealthy'
    status_code = 200 if overall_status == 'healthy' else 503

    return Response({
        'status': overall_status,
        'version': getattr(settings, 'VERSION', '1.0.0'),
        'database': db_status['status']
    }, status=status_code)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def health_check_detailed(request):
    """
    Detailed health check endpoint.
    GET /api/health/detailed/

    Requires admin authentication.
    Returns detailed status of all system components.

    Response includes:
        - database: Connection and latency
        - cache: Redis/cache status
        - celery: Worker status
        - disk: Available space
        - settings: Key configuration values
    """
    start_time = time.time()

    # Run all health checks
    db_status = check_database()
    cache_status = check_cache()
    celery_status = check_celery()
    disk_status = check_disk_space()

    # Determine overall status — συμμετέχουν ΚΑΙ τα τέσσερα components,
    # ώστε πεσμένοι Celery workers ή critical disk να μην επιστρέφουν
    # ποτέ overall "healthy".
    statuses = [
        db_status.get('status'),
        cache_status.get('status'),
        celery_status.get('status'),
        disk_status.get('status'),
    ]

    if any(status in UNHEALTHY_COMPONENT_STATUSES for status in statuses):
        # unhealthy / critical / error / unavailable σε οποιοδήποτε
        # απαιτούμενο component ⇒ overall unhealthy.
        overall_status = 'unhealthy'
        status_code = 503
    elif any(status != 'healthy' for status in statuses):
        # degraded / warning / unknown (χωρίς critical κατάσταση)
        # ⇒ overall degraded — ποτέ healthy.
        overall_status = 'degraded'
        status_code = 200
    else:
        # healthy μόνο όταν και τα τέσσερα components είναι healthy.
        overall_status = 'healthy'
        status_code = 200

    total_time = (time.time() - start_time) * 1000

    return Response({
        'status': overall_status,
        'version': getattr(settings, 'VERSION', '1.0.0'),
        'debug': settings.DEBUG,
        'check_duration_ms': round(total_time, 2),
        'components': {
            'database': db_status,
            'cache': cache_status,
            'celery': celery_status,
            'disk': disk_status,
        },
        'settings': {
            'timezone': str(settings.TIME_ZONE),
            'language': settings.LANGUAGE_CODE,
            'allowed_hosts': settings.ALLOWED_HOSTS[:3] if settings.ALLOWED_HOSTS else [],
        }
    }, status=status_code)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([])
def health_ready(request):
    """
    Readiness probe for Kubernetes.
    GET /api/health/ready/

    Returns 200 only if the app is ready to receive traffic.
    Checks database connectivity.
    """
    db_status = check_database()

    if db_status['status'] == 'healthy':
        return Response({'ready': True}, status=200)
    else:
        return Response({'ready': False, 'reason': 'database unavailable'}, status=503)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([])
def health_live(request):
    """
    Liveness probe for Kubernetes.
    GET /api/health/live/

    Returns 200 if the application process is alive.
    Does not check external dependencies.
    """
    return Response({'alive': True}, status=200)
