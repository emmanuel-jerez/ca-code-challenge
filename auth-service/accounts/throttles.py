"""Login rate limits: per client IP and per account (ADR 0033).

DRF says its throttles aren't a complete brute-force control. They slow
guessing; scrypt makes each guess expensive. Counts live in the shared
database cache, so every gunicorn worker sees the same totals.
"""

import hashlib
from typing import TYPE_CHECKING

from rest_framework.throttling import SimpleRateThrottle

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


class LoginIpThrottle(SimpleRateThrottle):
    """Limits one address, whichever accounts it tries."""

    scope = "login_ip"

    def get_cache_key(self, request: Request, view: APIView) -> str:
        # get_ident honours NUM_PROXIES, which is 0: the socket address only.
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginUsernameThrottle(SimpleRateThrottle):
    """Limits guesses at one account, however many addresses they come from.

    The cost: anyone can slow one person's logins for a minute. Accepted, as
    OWASP prefers per-account limits over per-IP ones.
    """

    scope = "login_username"

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        data = request.data
        username = data.get("username") if isinstance(data, dict) else None
        if not isinstance(username, str) or not username.strip():
            # Malformed bodies get a 400 from the serializer; the IP limit
            # still counts them.
            return None
        # Hashed, so the cache never stores what people typed: sometimes a
        # password lands in the username box.
        normalized = username.strip().casefold().encode()
        ident = hashlib.sha256(normalized).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}
