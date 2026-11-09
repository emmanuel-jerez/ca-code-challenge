"""AccessClaims: the payload the auth service signs, and scope checks."""

import uuid

import pytest

from brandreviews_authz import AccessClaims, scopes

CLAIMS = AccessClaims(
    subject=uuid.UUID("0b6f3c1e-5d0a-4c55-9d43-3c8c2f2d7a10"),
    client_id="brands-cli",
    scopes=frozenset({scopes.BRANDS_WRITE, scopes.BRANDS_READ}),
    token_id="abc",
    issued_at=1_000,
    expires_at=1_600,
)


def test_the_signed_payload_is_the_rfc_9068_claim_set() -> None:
    # A literal, not rebuilt from the fields: this is the wire contract the
    # main app's deployed verifier reads.
    assert CLAIMS.to_payload(issuer="http://auth-service:8000", audience="brands-api") == {
        "iss": "http://auth-service:8000",
        "aud": "brands-api",
        "sub": "0b6f3c1e-5d0a-4c55-9d43-3c8c2f2d7a10",
        "client_id": "brands-cli",
        "scope": "brands:read brands:write",
        "iat": 1_000,
        "nbf": 1_000,
        "exp": 1_600,
        "jti": "abc",
    }


def test_a_payload_reads_back_into_the_same_claims() -> None:
    payload = CLAIMS.to_payload(issuer="i", audience="a")

    assert AccessClaims.from_payload(payload) == CLAIMS


def test_claims_the_verifier_does_not_know_are_ignored() -> None:
    # A tolerant reader: the issuer can add a claim without a coordinated release.
    payload = CLAIMS.to_payload(issuer="i", audience="a") | {"tv": 3, "new": "x"}

    assert AccessClaims.from_payload(payload) == CLAIMS


@pytest.mark.parametrize(
    ("required", "expected"),
    [
        pytest.param((scopes.BRANDS_WRITE,), True, id="one held"),
        pytest.param((scopes.BRANDS_READ, scopes.BRANDS_WRITE), True, id="all held"),
        pytest.param(("brands:delete",), False, id="one missing"),
        pytest.param((scopes.BRANDS_WRITE, "brands:delete"), False, id="one of two missing"),
        pytest.param((), True, id="nothing required"),
    ],
)
def test_has_scopes_needs_every_required_scope(required: tuple[str, ...], expected: bool) -> None:
    assert CLAIMS.has_scopes(*required) is expected
