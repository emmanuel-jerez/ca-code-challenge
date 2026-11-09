"""Small factories that set only what a test cares about."""

import itertools
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from catalog.models import Brand, Industry, Review

if TYPE_CHECKING:
    from collections.abc import Callable

_ids = itertools.count(1)


@pytest.fixture
def make_industry() -> Callable[..., Industry]:
    def make(**fields: Any) -> Industry:  # noqa: ANN401 - forwards model field values
        n = next(_ids)
        fields.setdefault("name", f"Industry {n}")
        fields.setdefault("slug", f"industry-{n}")
        return Industry.objects.create(**fields)

    return make


@pytest.fixture
def make_brand(make_industry: Callable[..., Industry]) -> Callable[..., Brand]:
    def make(**fields: Any) -> Brand:  # noqa: ANN401 - forwards model field values
        n = next(_ids)
        fields.setdefault("name", f"Brand {n}")
        fields.setdefault("slug", f"brand-{n}")
        if "industry" not in fields:
            fields["industry"] = make_industry()
        return Brand.objects.create(**fields)

    return make


@pytest.fixture
def make_review(make_brand: Callable[..., Brand]) -> Callable[..., Review]:
    def make(**fields: Any) -> Review:  # noqa: ANN401 - forwards model field values
        n = next(_ids)
        fields.setdefault("title", f"Review {n}")
        fields.setdefault("slug", f"review-{n}")
        fields.setdefault("rating", 4)
        fields.setdefault("published_at", datetime(2026, 1, 1, tzinfo=UTC))
        if "brand" not in fields:
            fields["brand"] = make_brand()
        return Review.objects.create(**fields)

    return make
