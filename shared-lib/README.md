# brandreviews-authz

The token contract the two Brand Reviews services share. The auth service
mints access tokens with it, and the main app verifies them and checks their
scopes with it. Decisions: ADRs 0016, 0025 and 0034 in `docs/adr/`.

## What's in it, and who uses it

| Module | Holds | Auth service | Main app |
|---|---|---|---|
| `profile` | `alg`, `typ`, required claims, size cap, leeway | signs with `ALGORITHM` and `TOKEN_TYPE` | verifies against all of it |
| `scopes` | `BRANDS_READ`, `BRANDS_WRITE` | a test checks its seeded scopes match | requires `BRANDS_WRITE` on the `PATCH` |
| `claims` | `AccessClaims`, `to_payload()`, `from_payload()`, `has_scopes()` | builds and signs `to_payload()` | parses verified tokens |
| `errors` | `TokenRejected` (401), `KeySetUnavailable` (503), `InsufficientScope` (403) | through the verifier in its contract test | maps them to statuses |
| `jwks` | `public_jwk()`, `StaticKeyProvider`, `JwksClientKeyProvider` | publishes `public_jwk()`; its contract test uses `StaticKeyProvider` | fetches keys with `JwksClientKeyProvider` (main app only) |
| `verify` | `TokenVerifier` | its contract test | verifies every bearer token |
| `drf` | `BearerAuthentication`, `require_scopes()`, `Principal` | — | protects the `PATCH` |

Kept out:
- **Signing and private keys.** Only the auth service may mint tokens.
- **The role → scope map.** It's the auth service's data, and roles should change
  without a release.
- **Models, settings and HTTP client libraries.**

The core imports neither Django nor DRF. Only `drf.py` does, and it needs the `[drf]` extra.

## Use it

```python
from brandreviews_authz import JwksClientKeyProvider, TokenVerifier, scopes
from brandreviews_authz.drf import BearerAuthentication, require_scopes

verifier = TokenVerifier(
    JwksClientKeyProvider("http://auth-service:8000/.well-known/jwks.json"),
    issuer="http://auth-service:8000",
    audience="brands-api",
)


class ServiceAuthentication(BearerAuthentication):  # DRF builds it with no arguments
    def get_verifier(self) -> TokenVerifier:
        return verifier


# on a view: permission_classes = [require_scopes(scopes.BRANDS_WRITE)]
```

## Tests

No Django project or database is needed. The DRF adapter's tests configure Django in the test module.

```bash
cd shared-lib
uv run pytest            # or `make test-shared` from the repo root (adds mypy and Ruff)
uv run mypy src tests
uv run ruff check && uv run ruff format --check
```

## Releasing a change

1. Change `src/`, add a `CHANGELOG.md` entry, and run `uv version --bump <patch|minor|major>`.
2. Run `uv lock` in `main-app/` and `auth-service/`, then run both services' tests.
   Commit the library and both lockfiles together.
3. `make check-shared` fails if `src/` changed without a version bump, or if a service
   wasn't re-locked.

A breaking change to the token goes expand → migrate → contract:
1. Verifiers accept the old and the new shape.
2. The auth service switches.
3. One token lifetime (10 minutes) later, a major release drops the old shape.

No step needs both services deployed at the same moment.
