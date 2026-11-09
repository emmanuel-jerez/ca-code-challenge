# When to Mock

Mock at **system boundaries** only:

- External APIs (the auth service as seen from the main app, the WordPress REST API)
- Databases (rarely: pytest-django gives each test a real, rolled-back test database; prefer it)
- Time/randomness
- File system (sometimes)

Don't mock:

- Your own classes/modules
- Internal collaborators, including Django models, managers and querysets
- Anything you control

Use `unittest.mock` from the standard library. Add a mocking or HTTP-stubbing
package only with the user's approval, as the `uv-only` skill requires for any
new dependency.

## Designing for Mockability

At system boundaries, design interfaces that are easy to mock:

**1. Use dependency injection**

Pass external dependencies in rather than creating them internally:

```python
# Easy to mock: the key source is passed in
def authenticate(raw_token: str, keys: KeySource) -> Principal:
    return verify(raw_token, keys.current())

# Hard to mock: the HTTP call is built inside
def authenticate(raw_token: str) -> Principal:
    keys = httpx.get(settings.AUTH_JWKS_URL).json()
    return verify(raw_token, keys)
```

In tests, pass a small fake that satisfies the same interface (for example a
`StaticKeySource` built from a test key pair) instead of patching `httpx`.

**2. Prefer SDK-style interfaces over generic fetchers**

Create specific functions for each external operation instead of one generic function with conditional logic:

```python
# GOOD: Each method is independently replaceable
class WordPressClient:
    def brands(self) -> list[dict]: ...
    def reviews(self) -> list[dict]: ...
    def industries(self) -> list[dict]: ...

# BAD: Faking it requires conditional logic inside the fake
class WordPressClient:
    def get(self, path: str, **params) -> Any: ...
```

The SDK approach means:
- Each fake returns one specific shape
- No conditional logic in test setup
- Easier to see which endpoints a test exercises
- Type safety per endpoint

**3. Control time explicitly**

Token expiry and "recent reviews" depend on the clock. Pass `now` in, or read
it through one function the test can replace. Do not patch `datetime` deep
inside a module.
