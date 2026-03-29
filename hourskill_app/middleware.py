import time

from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.utils import timezone

from .models import UserProfile


class SingleSessionMiddleware(MiddlewareMixin):
    """Enforce one active session per user (1 account = 1 device).

    Stores the active session key in cache per user. If a different session
    key is seen for the same user, the previous session is effectively
    invalidated by logging out the request immediately.
    """

    cache_prefix = "active-session"
    ttl_seconds = 60 * 60 * 12  # keep record for 12h; refreshed per request

    def _expects_json(self, request):
        path = str(getattr(request, "path", "") or "")
        if path.startswith("/api/"):
            return True
        accept = str(request.headers.get("Accept", "") or "").lower()
        return "application/json" in accept

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
            message = "Phiên đăng nhập đã bị ngắt do đăng nhập trên thiết bị khác."

            if self._expects_json(request):
                return JsonResponse(
                    {
                        "status": "error",
                        "message": message,
                    },
                    status=401,
                )

            path = str(getattr(request, "path", "") or "")
            if path.startswith("/admin"):
                return redirect(f"/admin/login/?next={path}")

            return redirect("/login.html")

        # Refresh TTL to keep the mapping alive while active
        cache.set(cache_key, session_key, timeout=self.ttl_seconds)
        return None


class VipAccessMiddleware(MiddlewareMixin):
    """Attach VIP access state to request and expire outdated subscriptions."""

    def process_request(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            request.vip_active = False
            return None

        try:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            expiry = profile.vip_expiry or user.vip_expiry
            flagged = bool(profile.is_vip or user.is_vip)
            active = bool(flagged and expiry and expiry > timezone.now())

            if flagged and expiry and expiry <= timezone.now():
                profile.is_vip = False
                profile.vip_expiry = None
                profile.save(update_fields=['is_vip', 'vip_expiry'])
                user.is_vip = False
                user.vip_expiry = None
                user.save(update_fields=['is_vip', 'vip_expiry'])
                active = False

            request.vip_active = active
        except Exception:
            request.vip_active = False

        return None
