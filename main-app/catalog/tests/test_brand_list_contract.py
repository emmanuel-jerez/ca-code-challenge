"""The API half of the brand listing contract (ADR 0010).

Writes real responses from GET /api/brands/ to contracts/brand-list.example.json.
The frontend's Vitest test parses the same file with its Zod schema, so a change
on either side that breaks the other fails a test.

A case per shape the UI must handle: rows with every field set, an unrated
brand with a blank description, text that looks like markup, both page links,
an empty page, and the 400 and 404 error bodies.

When the API changes on purpose, regenerate the file and commit it:
    UPDATE_CONTRACTS=1 uv run pytest catalog/tests/test_brand_list_contract.py
"""

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.test import Client

    from catalog.models import Brand, Industry, Review

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "brand-list.example.json"


@pytest.fixture
def catalog(
    make_industry: Callable[..., Industry],
    make_brand: Callable[..., Brand],
    make_review: Callable[..., Review],
) -> None:
    """Every value the payload shows is set here, so the file is the same on every run."""
    insurance = make_industry(name="Insurance", slug="insurance")
    finance = make_industry(name="Finance", slug="finance")
    make_industry(name="Retail", slug="retail")

    make_brand(
        name="New Brand",
        slug="new-brand",
        industry=insurance,
        average_rating=None,
        review_count=0,
        short_description="",
    )
    primepath = make_brand(
        name="PrimePath Bank",
        slug="primepath-bank",
        industry=finance,
        average_rating=Decimal("4.00"),
        review_count=1,
        short_description="A regional retail bank with 220 branches.",
    )
    make_review(
        brand=primepath,
        title="Better than AT&T's support",
        slug="better-than-atts-support",
        rating=4,
        reviewer_name="Roberto G.",
        content_text="Support beat AT&T's <by far> & the app works.",
        published_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    acme = make_brand(
        name="Acme Insurance Co.",
        slug="acme-insurance",
        industry=insurance,
        average_rating=Decimal("3.50"),
        review_count=2,
        short_description="An agent-led insurer for auto, home and umbrella cover.",
    )
    for n, rating in enumerate((5, 2), start=1):
        make_review(
            brand=acme,
            title=f"Acme review {n}",
            slug=f"acme-review-{n}",
            rating=rating,
            reviewer_name="Sarah K.",
            content_text="Added an umbrella policy in fifteen minutes. " * 5,
            published_at=datetime(2026, 1, n, tzinfo=UTC),
        )


def response_case(client: Client, query: str) -> dict[str, object]:
    response = client.get(f"/api/brands/{query}")
    return {"query": query, "status": response.status_code, "body": response.json()}


@pytest.mark.django_db
@pytest.mark.usefixtures("catalog")
def test_contract_fixture_matches_the_api(client: Client) -> None:
    cases = {
        "first_page": response_case(client, "?ordering=review_count&page_size=2"),
        "last_page": response_case(client, "?ordering=review_count&page_size=2&page=2"),
        "empty_page": response_case(client, "?industry=retail"),
        "invalid_query": response_case(client, "?ordering=name&page_size=0&industry=nope"),
        "page_not_found": response_case(client, "?page=9"),
    }
    generated = json.dumps(cases, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if os.environ.get("UPDATE_CONTRACTS") == "1":
        CONTRACT.parent.mkdir(exist_ok=True)
        CONTRACT.write_text(generated, encoding="utf-8")

    assert CONTRACT.exists(), "Missing contract fixture; run with UPDATE_CONTRACTS=1"
    assert CONTRACT.read_text(encoding="utf-8") == generated, (
        "The API no longer matches the contract fixture. If that's intended, "
        "regenerate it with UPDATE_CONTRACTS=1 and update the frontend's Zod schema."
    )
