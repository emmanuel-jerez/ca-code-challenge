# Changelog

[SemVer](https://semver.org/). Patch: a fix with no API or claim change. Minor: something
new, or an old API deprecated. Major: something removed, or a claim made stricter.

## 1.0.0 (2026-11-09)

### Added
- `TokenVerifier`: verifies EdDSA access tokens. It checks `typ`, `alg`, `kid`, `iss`,
  `aud`, `exp`, `nbf`, `iat`, `sub`, `jti`, `client_id` and `scope`, and raises only this
  library's errors.
- `AccessClaims` with `to_payload()` (the issuer's claim set) and `from_payload()`.
- `public_jwk()` (RFC 7638 thumbprint as `kid`), `StaticKeyProvider` and
  `JwksClientKeyProvider` (wraps PyJWT's `PyJWKClient` and accepts Ed25519 public keys only).
- `scopes.BRANDS_READ` and `scopes.BRANDS_WRITE`.
- `drf`: `BearerAuthentication`, `require_scopes()`, `Principal` and `KeysUnavailable` (503).
