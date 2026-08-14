"""Shared authorization, throttling, and audit controls for door mutations."""

import logging

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.cache import cache
from rest_framework.settings import api_settings
from rest_framework.throttling import BaseThrottle

from .models import DoorAccessLog

logger = logging.getLogger(__name__)

DOOR_MUTATION_RATE = 10
DOOR_MUTATION_WINDOW = 60


def has_explicit_door_permission(user):
    """Require an actual user/group grant; superuser status is not a grant."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    permission = Permission.objects.filter(
        content_type__app_label="accounting", codename="open_office_door"
    )
    return permission.filter(user=user).exists() or permission.filter(
        group__user=user
    ).exists()


def _client_ip(request):
    """Use trusted-proxy configuration without trusting arbitrary XFF."""
    if api_settings.NUM_PROXIES is None:
        return request.META.get("REMOTE_ADDR") or "unknown"
    return BaseThrottle().get_ident(request)


def _increment(key):
    backend = settings.CACHES['default']['BACKEND']
    if 'RedisCache' not in backend and not getattr(settings, 'TESTING', False):
        raise RuntimeError('atomic door throttle backend unavailable')
    if cache.add(key, 1, DOOR_MUTATION_WINDOW):
        return 1
    return cache.incr(key)


def begin_door_mutation(request, action):
    """Return ``(audit_log, rejection)`` and fail closed if audit is unavailable."""
    request._door_client_ip = _client_ip(request)
    request._door_peer_ip = request.META.get("REMOTE_ADDR") or "unknown"
    user = request.user if request.user.is_authenticated else None
    if not has_explicit_door_permission(user):
        DoorAccessLog.log_access(user, action, "denied", request=request)
        return None, (403, "Door permission required")

    keys = (
        f"door-mutation:user:{user.pk}",
        f"door-mutation:ip:{_client_ip(request)}",
    )
    try:
        counts = [_increment(key) for key in keys]
    except Exception:
        logger.exception("Door mutation blocked because atomic throttle is unavailable")
        DoorAccessLog.log_access(
            user,
            action,
            "denied",
            request=request,
            response_data={"reason": "throttle_backend_unavailable"},
        )
        return None, (503, "Door security throttle unavailable")
    if any(count > DOOR_MUTATION_RATE for count in counts):
        DoorAccessLog.log_access(user, action, "rate_limited", request=request)
        return None, (429, "Door action rate limit exceeded")

    try:
        audit = DoorAccessLog.log_access(user, action, "attempted", request=request)
    except Exception:
        logger.exception("Door mutation blocked because audit logging failed")
        return None, (503, "Door audit unavailable")
    return audit, None


def finish_door_mutation(audit, result, response_data=None):
    """Persist only a small, secret-free outcome summary."""
    safe_data = dict(audit.response_data or {})
    if response_data:
        allowed = {"success", "new_state", "new_status", "online"}
        safe_data.update({key: response_data[key] for key in allowed if key in response_data})
    audit.result = result
    audit.response_data = safe_data
    audit.save(update_fields=["result", "response_data"])
