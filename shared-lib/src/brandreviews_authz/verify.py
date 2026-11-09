"""TokenVerifier: an access token in, AccessClaims or a library error out (ADR 0016)."""

from typing import TYPE_CHECKING

import jwt

from brandreviews_authz.claims import AccessClaims
from brandreviews_authz.errors import TokenRejected
from brandreviews_authz.profile import (
    ACCEPTED_TOKEN_TYPES,
    ALGORITHM,
    COMPACT_JWS,
    KID,
    LEEWAY_SECONDS,
    MAX_TOKEN_BYTES,
    REQUIRED_CLAIMS,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from brandreviews_authz.jwks import KeyProvider


class TokenVerifier:
    def __init__(
        self,
        keys: KeyProvider,
        *,
        issuer: str,
        audience: str,
        leeway: float = LEEWAY_SECONDS,
    ) -> None:
        self._keys = keys
        self._issuer = issuer
        self._audience = audience
        self._leeway = leeway

    def verify(self, token: str) -> AccessClaims:
        """Raises TokenRejected (401) or KeySetUnavailable (503), nothing else."""
        # Cheap checks first, so junk never reaches the key provider and
        # can't make it refetch the JWKS.
        if len(token) > MAX_TOKEN_BYTES or not COMPACT_JWS.fullmatch(token):
            raise TokenRejected("not a compact JWS of acceptable size")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise TokenRejected("unreadable header") from None
        _check_header(header)
        # _check_header guarantees a str kid.
        key = self._keys.get(str(header["kid"]))
        try:
            decoded = jwt.decode_complete(
                token,
                key,
                algorithms=[ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                # A fresh literal on every call: PyJWT 2.11–2.13 mutated a
                # caller's options dict, disabling checks on later calls
                # (CVE-2026-103001). strict_aud: aud must be our one string.
                options={"require": list(REQUIRED_CLAIMS), "strict_aud": True},
            )
        except jwt.PyJWTError as error:
            # Catch PyJWT's base class only: anything else escaping is a bug
            # to see as a 500, not to hide as a 401.
            raise TokenRejected(type(error).__name__) from None
        # Again on the verified header: typ is part of the signed input,
        # so only now is it authentic.
        _check_header(decoded["header"])
        return AccessClaims.from_payload(decoded["payload"])


def _check_header(header: Mapping[str, object]) -> None:
    # PyJWT never checks typ (ADR 0016).
    typ = header.get("typ")
    if not isinstance(typ, str) or typ.lower() not in ACCEPTED_TOKEN_TYPES:
        raise TokenRejected("typ is not at+jwt")
    if header.get("alg") != ALGORITHM:
        raise TokenRejected("alg is not EdDSA")
    kid = header.get("kid")
    if not isinstance(kid, str) or not KID.fullmatch(kid):
        raise TokenRejected("kid is missing or malformed")
