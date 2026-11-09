"""The database refuses invalid rows, whatever code path writes them.

Django runs model validators only in full_clean(), which save(),
update_or_create() and bulk writes skip. These checks are the last line.
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from django.db import IntegrityError

if TYPE_CHECKING:
    from collections.abc import Callable

    from catalog.models import Brand, Review


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fields",
    [
        {"website_url": "javascript:alert(1)"},
        {"website_url": "ftp://example.com"},
        {"website_url": "data:text/html,hi"},
        {"founded_year": 1799},
        {"founded_year": 2101},
        {"average_rating": Decimal("0.99")},
        {"legacy_average_rating": Decimal("5.1")},
    ],
)
def test_brand_rejects_invalid_values(
    make_brand: Callable[..., Brand], fields: dict[str, Any]
) -> None:
    with pytest.raises(IntegrityError):
        make_brand(**fields)


@pytest.mark.django_db
@pytest.mark.parametrize("website_url", ["", "http://example.com", "HTTPS://example.com"])
def test_brand_accepts_empty_or_http_urls(
    make_brand: Callable[..., Brand], website_url: str
) -> None:
    assert make_brand(website_url=website_url).pk is not None


@pytest.mark.django_db
@pytest.mark.parametrize("rating", [0, 6])
def test_review_rating_must_be_1_to_5(make_review: Callable[..., Review], rating: int) -> None:
    with pytest.raises(IntegrityError):
        make_review(rating=rating)
