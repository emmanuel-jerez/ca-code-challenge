"""TokenVerifier: what it accepts and what it rejects (ADR 0016).

Each rejection case is tied to RFC 9068, RFC 8725bis or a 2026 PyJWT advisory
(docs/research/pillar-6-shared-library.md §8).
"""

import base64
import hashlib
import hmac
import json
import time
from typing import TYPE_CHECKING

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from brandreviews_authz import AccessClaims, StaticKeyProvider, TokenRejected, TokenVerifier

from conftest import AUDIENCE, ISSUER, SUBJECT, Issuer

if TYPE_CHECKING:
    from jwt import PyJWK


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64(value: object) -> str:
    return _b64url(json.dumps(value).encode())


def _signed(issuer: Issuer, header_overrides: dict[str, object]) -> str:
    """A validly signed token with any header; None drops a field.

    Built by hand because jwt.encode always writes alg and typ.
    """
    header = {"alg": "EdDSA", "typ": "at+jwt", "kid": issuer.kid} | header_overrides
    header = {k: v for k, v in header.items() if v is not None}
    signing_input = f"{_b64(header)}.{_b64(issuer.claims())}"
    return f"{signing_input}.{_b64url(issuer.private_key.sign(signing_input.encode()))}"


# Tokens are minted at collection time relative to this; margins are at
# least 60 s beyond the leeway, so a slow run can't flip a result.
NOW = int(time.time())


def test_a_token_the_auth_service_minted_gives_its_claims(
    issuer: Issuer, verifier: TokenVerifier
) -> None:
    token = issuer.mint(iat=1_000, nbf=1_000, exp=4_000_000_000)

    claims = verifier.verify(token)

    assert claims == AccessClaims(
        subject=SUBJECT,
        client_id="brands-cli",
        scopes=frozenset({"brands:read", "brands:write"}),
        token_id="test-jti",
        issued_at=1_000,
        expires_at=4_000_000_000,
    )


def test_a_token_expired_within_the_leeway_still_passes(
    issuer: Issuer, verifier: TokenVerifier
) -> None:
    now = int(time.time())

    claims = verifier.verify(issuer.mint(iat=now - 620, nbf=now - 620, exp=now - 20))

    assert claims.expires_at == now - 20


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"exp": NOW - 90}, id="expired past the 30 s leeway"),
        pytest.param({"nbf": NOW + 120}, id="not valid yet"),
        pytest.param({"iat": NOW + 120}, id="issued in the future"),
        pytest.param({"aud": "another-api"}, id="another audience"),
        # strict_aud: one string, ours; a list could smuggle in a second audience.
        pytest.param({"aud": ["brands-api", "another-api"]}, id="audience as a list"),
        pytest.param({"iss": "http://evil.example"}, id="another issuer"),
        pytest.param({"sub": "42"}, id="sub not a UUID"),
        pytest.param({"scope": ["brands:write"]}, id="scope not a string"),
        pytest.param({"client_id": ""}, id="empty client_id"),
        *(
            pytest.param({claim: None}, id=f"no {claim}")
            for claim in ("iss", "sub", "aud", "exp", "iat", "nbf", "jti", "client_id", "scope")
        ),
    ],
)
def test_claims_that_fail_a_check_are_rejected(
    issuer: Issuer, verifier: TokenVerifier, overrides: dict[str, object]
) -> None:
    with pytest.raises(TokenRejected):
        verifier.verify(issuer.mint(**overrides))


@pytest.mark.parametrize("typ", ["at+jwt", "application/at+jwt", "AT+JWT"])
def test_both_rfc_9068_token_types_are_accepted_in_any_case(
    issuer: Issuer, verifier: TokenVerifier, typ: str
) -> None:
    assert verifier.verify(issuer.mint_with_headers({"typ": typ})).subject == SUBJECT


@pytest.mark.parametrize(
    "headers",
    [
        # An ID token or any other JWT must not pass as an access token (RFC 9068 §4).
        pytest.param({"typ": "JWT"}, id="typ JWT"),
        pytest.param({"typ": None}, id="no typ"),
        pytest.param({"kid": None}, id="no kid"),
        pytest.param({"kid": "x" * 43}, id="unknown kid"),
        pytest.param({"kid": "not-a-thumbprint"}, id="malformed kid"),
    ],
)
def test_headers_that_fail_a_check_are_rejected(
    issuer: Issuer, verifier: TokenVerifier, headers: dict[str, object]
) -> None:
    with pytest.raises(TokenRejected):
        verifier.verify(_signed(issuer, headers))


def test_a_token_signed_by_another_key_under_our_kid_is_rejected(
    issuer: Issuer, verifier: TokenVerifier
) -> None:
    forger = Issuer(private_key=Ed25519PrivateKey.generate(), kid=issuer.kid)

    with pytest.raises(TokenRejected):
        verifier.verify(forger.mint())


def test_alg_none_is_rejected(issuer: Issuer, verifier: TokenVerifier) -> None:
    header = _b64({"alg": "none", "typ": "at+jwt", "kid": issuer.kid})
    payload = _b64(issuer.claims())

    with pytest.raises(TokenRejected):
        verifier.verify(f"{header}.{payload}.")


def test_hs256_signed_with_the_public_key_is_rejected(
    issuer: Issuer, verifier: TokenVerifier
) -> None:
    # The algorithm-confusion attack (CVE-2026-48526 class): the public key's
    # bytes used as an HMAC secret.
    public = issuer.private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    header = _b64({"alg": "HS256", "typ": "at+jwt", "kid": issuer.kid})
    payload = _b64(issuer.claims())
    signature = hmac.new(public, f"{header}.{payload}".encode(), hashlib.sha256).digest()

    with pytest.raises(TokenRejected):
        verifier.verify(f"{header}.{payload}.{_b64url(signature)}")


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("", id="empty"),
        pytest.param("not a token", id="words"),
        pytest.param("a.b", id="two segments"),
        pytest.param("a.b.c.d.e", id="five segments (JWE)"),
        pytest.param("a" * 5000 + ".b.c", id="over 4 KiB"),
        # Nests past Python's recursion limit while parsing the header
        # (CVE-2026-101918 raised a raw RecursionError).
        pytest.param(_b64url(b"[" * 2500) + ".e30.c2ln", id="deeply nested header"),
        pytest.param("e30.e30.c2ln", id="empty header"),
        pytest.param(_b64url(b"\xff\xfe") + ".e30.c2ln", id="header not UTF-8"),
    ],
)
def test_garbage_is_rejected_never_raised_as_something_else(
    verifier: TokenVerifier, token: str
) -> None:
    with pytest.raises(TokenRejected):
        verifier.verify(token)


def test_extra_characters_after_the_signature_are_rejected(
    issuer: Issuer, verifier: TokenVerifier
) -> None:
    token = issuer.mint()

    # Non-canonical signatures (CVE-2026-102269), and the correct padding
    # PyJWT 2.15.1 tolerates (a 64-byte signature pads with "=="): each
    # token has exactly one accepted spelling.
    for tampered in (token + "!!!!", token + "==", token + "AA"):
        with pytest.raises(TokenRejected):
            verifier.verify(tampered)


def test_an_empty_scope_grants_nothing(issuer: Issuer, verifier: TokenVerifier) -> None:
    # A user with no role logs in and gets scope "" (ADR 0033).
    assert verifier.verify(issuer.mint(scope="")).scopes == frozenset()


class CountingKeys:
    """Counts lookups: each one could cost the main app a JWKS fetch."""

    def __init__(self, issuer: Issuer) -> None:
        self.lookups = 0
        self._keys = StaticKeyProvider([issuer.private_key.public_key()])

    def get(self, kid: str) -> PyJWK:
        self.lookups += 1
        return self._keys.get(kid)


@pytest.mark.parametrize(
    "header_overrides",
    [
        pytest.param({"kid": "not-a-thumbprint"}, id="malformed kid"),
        pytest.param({"kid": 7}, id="kid not a string"),
        pytest.param({"typ": "JWT"}, id="typ JWT"),
    ],
)
def test_a_bad_header_never_reaches_the_key_lookup(
    issuer: Issuer, header_overrides: dict[str, object]
) -> None:
    keys = CountingKeys(issuer)
    verifier = TokenVerifier(keys, issuer=ISSUER, audience=AUDIENCE)

    with pytest.raises(TokenRejected):
        verifier.verify(_signed(issuer, header_overrides))
    assert keys.lookups == 0


def test_an_oversized_token_never_reaches_the_key_lookup(issuer: Issuer) -> None:
    keys = CountingKeys(issuer)
    verifier = TokenVerifier(keys, issuer=ISSUER, audience=AUDIENCE)

    with pytest.raises(TokenRejected):
        verifier.verify(issuer.mint(padding="x" * 4096))
    assert keys.lookups == 0
