# Good and Bad Tests

Examples use pytest and pytest-django, the test stack for every Python project
in this repository. The `client` fixture and the `django_db` mark come from
pytest-django.

## Good Tests

**Integration-style**: Test through real interfaces, not mocks of internal parts.

```python
# GOOD: Tests observable behavior through the HTTP interface
@pytest.mark.django_db
def test_brand_listing_filters_by_industry(client, make_brand):
    make_brand(slug="acme-bank", industry="finance")
    make_brand(slug="fresh-foods", industry="grocery")

    response = client.get("/api/brands/", {"industry": "finance"})

    assert response.status_code == 200
    assert [row["slug"] for row in response.json()["results"]] == ["acme-bank"]
```

Characteristics:

- Tests behavior users/callers care about
- Uses public API only
- Survives internal refactors
- Describes WHAT, not HOW
- One logical assertion per test

## Bad Tests

**Implementation-detail tests**: Coupled to internal structure.

```python
# BAD: Tests implementation details
@pytest.mark.django_db
def test_listing_calls_annotate(client):
    real = BrandQuerySet.with_review_stats
    with mock.patch.object(BrandQuerySet, "with_review_stats", autospec=True,
                           side_effect=real) as spy:
        client.get("/api/brands/")
    spy.assert_called_once()
```

Red flags:

- Mocking internal collaborators
- Testing private methods
- Asserting on call counts/order
- Test breaks when refactoring without behavior change
- Test name describes HOW not WHAT
- Verifying through external means instead of interface

```python
# BAD: Bypasses the interface to verify
@pytest.mark.django_db
def test_patch_saves_description(editor_client, make_brand):
    brand = make_brand(slug="acme-bank")
    editor_client.patch("/api/brands/acme-bank/", {"short_description": "New"},
                        content_type="application/json")
    with connection.cursor() as cursor:
        cursor.execute("SELECT short_description FROM brands_brand WHERE id = %s", [brand.id])
        assert cursor.fetchone()[0] == "New"

# GOOD: Verifies through the interface
@pytest.mark.django_db
def test_editor_can_change_short_description(editor_client, client, make_brand):
    make_brand(slug="acme-bank")
    editor_client.patch("/api/brands/acme-bank/", {"short_description": "New"},
                        content_type="application/json")
    row = client.get("/api/brands/").json()["results"][0]
    assert row["short_description"] == "New"
```

**Tautological tests**: Expected value restates the implementation, so the test passes by construction.

```python
# BAD: Expected value is recomputed the way the code computes it
def test_average_rating():
    ratings = [5, 4, 4]
    assert average_rating(ratings) == Decimal(sum(ratings)) / len(ratings)

# GOOD: Expected value is an independent, known literal
def test_average_rating():
    assert average_rating([5, 4, 4]) == Decimal("4.33")
```

## Django specifics

- Mark only the tests that touch the database with `@pytest.mark.django_db`.
  A pure function in the shared library needs no Django and no database.
- Build data with small factory fixtures in `conftest.py` (`make_brand`,
  `make_review`) that set only what the test cares about. Do not load the
  WordPress dump in unit tests; the import command gets its own tests with a
  small fixture file.
- Test views and endpoints through `client`, not by calling view functions or
  serializers directly. The URL, status code and response body are the
  interface.
- The shared library's tests run with plain `pytest` and no Django settings.
  If one needs Django, the code it covers probably belongs in a service, not
  the library.
