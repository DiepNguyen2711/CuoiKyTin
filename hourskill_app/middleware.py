import time

from django.contrib.auth import logout
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache


class SingleSessionMiddleware(MiddlewareMixin):
    """Enforce one active session per user (1 account = 1 device).

    Stores the active session key in cache per user. If a different session
    key is seen for the same user, the previous session is effectively
    invalidated by logging out the request immediately.
    """

    cache_prefix = "active-session"
    ttl_seconds = 60 * 60 * 12  # keep record for 12h; refreshed per request

    def process_request(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        # Ensure session key exists
        if not request.session.session_key:
            request.session.save()

        session_key = request.session.session_key
        cache_key = f"{self.cache_prefix}:{user.id}"
        active_key = cache.get(cache_key)

        if active_key is None:
            cache.set(cache_key, session_key, timeout=self.ttl_seconds)
            return None

        if active_key != session_key:
            logout(request)
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Phiên đăng nhập đã bị ngắt do đăng nhập trên thiết bị khác.",
                },
                status=401,
            )

        # Refresh TTL to keep the mapping alive while active
        cache.set(cache_key, session_key, timeout=self.ttl_seconds)
        return None
