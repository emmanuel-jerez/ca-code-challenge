"""The server-rendered pages, through their URLs (WordPress's permalinks)."""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from catalog.models import Brand, Review, Reviewer, Status

if TYPE_CHECKING:
    from django.test import Client
    from pytest_django import DjangoAssertNumQueries

type MakeBrand = Callable[..., Brand]
type MakeReview = Callable[..., Review]


def day(n: int) -> datetime:
    return datetime(2026, 1, n, tzinfo=UTC)


@pytest.mark.django_db
def test_home_features_top_rated_brands_with_unrated_last(
    client: Client, make_brand: MakeBrand, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    make_brand(name="Unrated Co")
    make_brand(name="Middling Co", average_rating=Decimal("3.10"))
    make_brand(name="Great Co", average_rating=Decimal("4.50"))
    make_brand(name="Hidden Co", average_rating=Decimal("5.00"), status=Status.DRAFT)

    with django_assert_num_queries(2):
        response = client.get("/")

    names = [brand.name for brand in response.context["featured_brands"]]
    assert names == ["Great Co", "Middling Co", "Unrated Co"]


@pytest.mark.django_db
def test_home_lists_the_newest_published_reviews(
    client: Client, make_review: MakeReview, make_brand: MakeBrand
) -> None:
    make_review(title="Older", published_at=day(1))
    make_review(title="Newer", published_at=day(2))
    make_review(title="Draft", published_at=day(3), status=Status.DRAFT)
    make_review(
        title="On a hidden brand", published_at=day(4), brand=make_brand(status=Status.REMOVED)
    )

    response = client.get("/")

    assert [r.title for r in response.context["recent_reviews"]] == ["Newer", "Older"]


@pytest.mark.django_db
def test_brand_page_shows_the_brand_and_its_reviews_newest_first(
    client: Client,
    make_brand: MakeBrand,
    make_review: MakeReview,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    brand = make_brand(
        slug="acme-insurance",
        name="Acme Insurance Co.",
        content_html="<p>Founded in <strong>1985</strong>.</p>",
        website_url="https://acme.example.com/about",
        review_count=2,
        average_rating=Decimal("3.92"),
    )
    make_review(brand=brand, title="First", published_at=day(1))
    make_review(brand=brand, title="Second", published_at=day(2))
    make_review(brand=brand, title="Unpublished", status=Status.PENDING)

    with django_assert_num_queries(2):
        response = client.get("/brand/acme-insurance/")

    html = response.content.decode()
    assert response.status_code == 200
    assert "<p>Founded in <strong>1985</strong>.</p>" in html
    assert ">acme.example.com</a>" in html
    assert 'aria-label="Rated 3.9 out of 5"' in html
    assert [r.title for r in response.context["reviews"]] == ["Second", "First"]


@pytest.mark.django_db
def test_review_page_shows_the_review_with_its_brand_and_author(
    client: Client,
    make_review: MakeReview,
    make_brand: MakeBrand,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    make_review(
        slug="fast-claim",
        title="Fast claim",
        rating=5,
        brand=make_brand(slug="acme-insurance", name="Acme Insurance Co."),
        reviewer=Reviewer.objects.create(display_name="Sarah K."),
        reviewer_name="Sarah K.",
        reviewer_location="Denver, CO",
    )

    with django_assert_num_queries(1):
        response = client.get("/review/fast-claim/")

    html = response.content.decode()
    assert response.status_code == 200
    assert 'href="/brand/acme-insurance/"' in html
    assert "Sarah K., Denver, CO" in html
    assert "Posted by Sarah K." in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/brand/draft-brand/",
        "/review/draft-review/",
        "/review/on-draft-brand/",
        "/brand/no-such-brand/",
    ],
)
def test_unpublished_or_unknown_content_is_not_found(
    client: Client, make_brand: MakeBrand, make_review: MakeReview, path: str
) -> None:
    make_brand(slug="draft-brand", status=Status.DRAFT)
    make_review(slug="draft-review", status=Status.DRAFT)
    make_review(slug="on-draft-brand", brand=make_brand(status=Status.DRAFT))

    assert client.get(path).status_code == 404


@pytest.mark.django_db
def test_permalink_without_trailing_slash_redirects_like_wordpress(
    client: Client, make_brand: MakeBrand
) -> None:
    make_brand(slug="acme-insurance")

    response = client.get("/brand/acme-insurance")

    assert (response.status_code, response["Location"]) == (301, "/brand/acme-insurance/")


def test_templates_never_bypass_autoescaping() -> None:
    """Only nh3-cleaned HTML may skip escaping, through one model property.

    Ruff's S308 catches mark_safe() in Python but not |safe in templates.
    """
    templates = Path(__file__).resolve().parents[1] / "templates"
    offenders = [
        path.name
        for path in templates.rglob("*.html")
        if "|safe" in path.read_text() or "autoescape off" in path.read_text()
    ]
    assert offenders == []
