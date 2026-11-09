"""GET /api/brands/: the brand listing behind <BrandList /> (ADRs 0022, 0027)."""

from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from catalog.models import Brand, Industry, Status

if TYPE_CHECKING:
    from django.test import Client

type MakeBrand = Callable[..., Brand]
type MakeIndustry = Callable[..., Industry]


def get_json(client: Client, query: str = "") -> Any:  # noqa: ANN401 - parsed JSON body
    response = client.get(f"/api/brands/{query}")
    assert response.status_code == 200, response.content
    return response.json()


@pytest.mark.django_db
def test_lists_published_brands_as_cards(
    client: Client, make_brand: MakeBrand, make_industry: MakeIndustry
) -> None:
    insurance = make_industry(name="Insurance", slug="insurance")
    make_brand(
        name="Acme Insurance Co.",
        slug="acme-insurance",
        industry=insurance,
        average_rating=Decimal("3.92"),
        review_count=12,
        short_description="Agent-led insurer.",
    )
    make_brand(status=Status.REMOVED)

    body = get_json(client)

    assert body == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "slug": "acme-insurance",
                "name": "Acme Insurance Co.",
                "industry": {"slug": "insurance", "name": "Insurance"},
                "average_rating": 3.92,
                "review_count": 12,
                "short_description": "Agent-led insurer.",
                "top_review": None,
            }
        ],
    }


@pytest.fixture
def ranked_brands(make_brand: MakeBrand) -> None:
    """Ties on purpose, so each ordering's tie-breakers decide something."""
    make_brand(slug="a", name="Delta", average_rating=Decimal("4.50"), review_count=3)
    make_brand(slug="b", name="Charlie", average_rating=Decimal("4.50"), review_count=7)
    make_brand(slug="c", name="Alpha", average_rating=None, review_count=0)
    make_brand(slug="d", name="Bravo", average_rating=Decimal("3.00"), review_count=7)


@pytest.mark.django_db
@pytest.mark.usefixtures("ranked_brands")
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # Default: best rated first, then more reviews; unrated last.
        ("", ["b", "a", "d", "c"]),
        ("?ordering=-average_rating", ["b", "a", "d", "c"]),
        # Unrated stays last in both directions; equal ratings fall back to id.
        ("?ordering=average_rating", ["d", "a", "b", "c"]),
        # Equal counts fall back to name.
        ("?ordering=-review_count", ["d", "b", "a", "c"]),
        ("?ordering=review_count", ["c", "a", "d", "b"]),
    ],
)
def test_orderings(client: Client, query: str, expected: list[str]) -> None:
    body = get_json(client, query)

    assert [row["slug"] for row in body["results"]] == expected


@pytest.mark.django_db
def test_an_unknown_ordering_is_a_400(client: Client) -> None:
    response = client.get("/api/brands/?ordering=name")

    assert response.status_code == 400
    assert response.json() == {"ordering": ['"name" is not a valid choice.']}
