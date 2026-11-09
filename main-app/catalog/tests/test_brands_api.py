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


@pytest.mark.django_db
def test_repeated_industries_match_any_of_them(
    client: Client, make_brand: MakeBrand, make_industry: MakeIndustry
) -> None:
    for slug in ("insurance", "finance", "retail"):
        make_brand(slug=f"{slug}-brand", industry=make_industry(slug=slug))

    body = get_json(client, "?industry=insurance&industry=retail&ordering=review_count")

    assert [row["slug"] for row in body["results"]] == ["insurance-brand", "retail-brand"]


@pytest.mark.django_db
def test_an_industry_without_published_brands_gives_an_empty_page(
    client: Client, make_industry: MakeIndustry
) -> None:
    make_industry(slug="insurance")

    body = get_json(client, "?industry=insurance")

    assert body == {"count": 0, "next": None, "previous": None, "results": []}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "error"),
    [
        # A stale or mistyped link: say so rather than show "no brands".
        ("?industry=nope", 'Unknown industry: "nope".'),
        (
            "?industry=" + "&industry=".join(f"i{n}" for n in range(11)),
            "Ensure this field has no more than 10 elements.",
        ),
    ],
)
def test_bad_industry_filters_are_a_400(
    client: Client, make_industry: MakeIndustry, query: str, error: str
) -> None:
    make_industry(slug="insurance")

    response = client.get(f"/api/brands/{query}")

    assert response.status_code == 400
    assert response.json() == {"industry": [error]}


@pytest.mark.django_db
@pytest.mark.usefixtures("ranked_brands")
def test_pages_follow_page_size_and_link_to_each_other(client: Client) -> None:
    first = get_json(client, "?ordering=review_count&page_size=3")
    second = get_json(client, "?ordering=review_count&page_size=3&page=2")

    assert first["count"] == second["count"] == 4
    assert [row["slug"] for row in first["results"]] == ["c", "a", "d"]
    assert [row["slug"] for row in second["results"]] == ["b"]
    assert first["previous"] is None
    assert first["next"] == (
        "http://testserver/api/brands/?ordering=review_count&page=2&page_size=3"
    )
    assert second["next"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("page_size", ["0", "51", "abc"])
def test_a_page_size_outside_1_to_50_is_a_400(client: Client, page_size: str) -> None:
    response = client.get(f"/api/brands/?page_size={page_size}")

    assert response.status_code == 400
    assert list(response.json()) == ["page_size"]


@pytest.mark.django_db
def test_a_page_past_the_end_is_a_404(client: Client, make_brand: MakeBrand) -> None:
    make_brand()

    response = client.get("/api/brands/?page=2")

    assert response.status_code == 404
    assert response.json() == {"detail": "Invalid page."}
