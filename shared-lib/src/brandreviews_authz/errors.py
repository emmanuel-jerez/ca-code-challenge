"""The library's errors. Each maps to exactly one HTTP status.

Callers catch these, never PyJWT's: the verifier translates every PyJWT error,
so a PyJWT upgrade can't change which status a client gets.
"""


class AuthzError(Exception):
    """Base class; never raised directly."""


class TokenRejected(AuthzError):
    """The token is missing a piece, malformed, expired, or not ours. 401.

    The message says why, for logs. Clients get a generic answer: the reason
    would help someone forging tokens.
    """


class KeySetUnavailable(AuthzError):
    """No usable signing key could be fetched from the auth service. 503.

    Not 401: the client's token may be valid, and a 401 would make it throw
    the token away (ADR 0016).
    """


class InsufficientScope(AuthzError):
    """A valid token that lacks a scope the action needs. 403."""

    def __init__(self, missing: frozenset[str]) -> None:
        super().__init__(f"missing scopes: {' '.join(sorted(missing))}")
        self.missing = missing
