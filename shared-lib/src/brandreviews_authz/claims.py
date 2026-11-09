"""The access token's claims: the contract between issuer and verifier.

The auth service builds AccessClaims and calls to_payload() to get what it
signs; the verifier calls from_payload() on what it verified. A frozen
dataclass rather than Pydantic, so the library forces no version of it on
either service (AGENTS.md).
"""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, TypeIs

from brandreviews_authz.errors import TokenRejected

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessClaims:
    # sub: the auth service's external user id, the main app's only user key.
    subject: uuid.UUID
    # Which client the token was issued to (RFC 9068 §2.2).
    client_id: str
    # From the space-separated `scope` claim (RFC 9068 §2.2.3). Authorization
    # reads these, never role names, so roles can change without code changes.
    scopes: frozenset[str]
    # jti: index any revocation list on this, never on the token string,
    # which has more than one valid spelling in PyJWT 2.15.1.
    token_id: str
    issued_at: int
    expires_at: int

    def has_scopes(self, *required: str) -> bool:
        return self.scopes.issuperset(required)

    def to_payload(self, *, issuer: str, audience: str) -> dict[str, object]:
        """The claims to sign. nbf equals iat: a token is valid once issued."""
        return {
            "iss": issuer,
            "aud": audience,
            "sub": str(self.subject),
            "client_id": self.client_id,
            # Sorted, so the same grants always give the same token claim.
            "scope": " ".join(sorted(self.scopes)),
            "iat": self.issued_at,
            "nbf": self.issued_at,
            "exp": self.expires_at,
            "jti": self.token_id,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> Self:
        """Parse a payload whose signature, iss, aud and times were already checked.

        Unknown claims are ignored (a tolerant reader), so the issuer can add
        one without a coordinated release (ADR 0025's expand step).
        """
        sub = payload.get("sub")
        client_id = payload.get("client_id")
        scope = payload.get("scope")
        jti = payload.get("jti")
        iat = payload.get("iat")
        exp = payload.get("exp")
        if not (_is_nonempty_str(client_id) and _is_nonempty_str(jti)):
            raise TokenRejected("client_id and jti must be non-empty strings")
        if not isinstance(scope, str):
            raise TokenRejected("scope must be a string")
        if not (_is_int(iat) and _is_int(exp)):
            raise TokenRejected("iat and exp must be integers")
        return cls(
            subject=_parse_subject(sub),
            client_id=client_id,
            # split() with no argument drops empty items: "" means no scopes.
            scopes=frozenset(scope.split()),
            token_id=jti,
            issued_at=iat,
            expires_at=exp,
        )


def is_claims(value: object) -> TypeIs[AccessClaims]:
    """Narrows DRF's loosely typed request.auth to AccessClaims."""
    return isinstance(value, AccessClaims)


def _parse_subject(sub: object) -> uuid.UUID:
    if not isinstance(sub, str):
        raise TokenRejected("sub must be a string")
    try:
        return uuid.UUID(sub)
    except ValueError:
        raise TokenRejected("sub must be a UUID") from None


def _is_nonempty_str(value: object) -> TypeIs[str]:
    return isinstance(value, str) and value != ""


def _is_int(value: object) -> TypeIs[int]:
    # bool is an int subclass; true is not a timestamp.
    return isinstance(value, int) and not isinstance(value, bool)
