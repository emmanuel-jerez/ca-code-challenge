"""The access-token profile both services agree on (ADR 0016).

The auth service signs with these values; the verifier accepts only these.
One definition, so the two sides can't drift apart.
"""

import re
from typing import Final

# Ed25519 only, under the identifier PyJWT supports. RFC 9864 deprecates the
# name; move to "Ed25519" by expand -> migrate -> contract once PyJWT can.
ALGORITHM: Final = "EdDSA"

# What the issuer writes in the `typ` header (RFC 9068 §2.1).
TOKEN_TYPE: Final = "at+jwt"  # noqa: S105 - a media type, not a secret
# What a verifier must accept, compared case-insensitively (RFC 9068 §4,
# RFC 7515 §4.1.9).
ACCEPTED_TOKEN_TYPES: Final = frozenset({"at+jwt", "application/at+jwt"})

# PyJWT checks exp, nbf and iat only when they're present, so every claim the
# verifier relies on is required. client_id and scope are checked by
# AccessClaims.from_payload.
REQUIRED_CLAIMS: Final = ("iss", "sub", "aud", "exp", "iat", "nbf", "jti")

# Real tokens are a few hundred bytes; PyJWT has no limit of its own.
MAX_TOKEN_BYTES: Final = 4096

# Compact JWS only: three base64url segments, no padding, nothing else
# (draft-ietf-oauth-rfc8725bis §3.14). PyJWT 2.15.1 tolerates padding.
COMPACT_JWS: Final = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

# A kid is the key's RFC 7638 thumbprint (jwks.public_jwk): 43 base64url
# characters. Anything else can't be one of ours, so it never reaches the
# JWKS lookup and can't trigger a refetch.
KID: Final = re.compile(r"[A-Za-z0-9_-]{43}")

# Clock skew allowed on exp, nbf and iat (RFC 9068 allows a few minutes).
LEEWAY_SECONDS: Final = 30
