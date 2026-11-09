import re
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from catalog.models import Brand, Review, Reviewer
from wp_import.errors import WpRowError
from wp_import.service import run_import
from wp_import.tests.fakes import FakeWordPress

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def wordpress() -> FakeWordPress:
    wp = FakeWordPress()
    wp.add_industry(2, "Insurance")
    wp.add_user(2, "Sarah K.")
    wp.add_brand(7, industry=2)
    wp.add_review(12, brand=7, rating=5, author=2)
    wp.add_review(13, brand=7, rating=4, author=2)
    wp.add_review(14, brand=7, rating=4, author=2)
    return wp


@pytest.mark.django_db
def test_first_run_creates_every_row(wordpress: FakeWordPress) -> None:
    report = run_import(wordpress)

    assert (report.industries.created, report.reviewers.created) == (1, 1)
    assert (report.brands.created, report.reviews.created) == (1, 3)
    brand = Brand.objects.get(slug="brand-7")
    assert brand.industry.name == "Insurance"
    assert brand.reviews.count() == 3


@pytest.mark.django_db
def test_second_run_changes_nothing(wordpress: FakeWordPress) -> None:
    run_import(wordpress)

    report = run_import(wordpress)

    assert (report.brands.unchanged, report.reviews.unchanged) == (1, 3)
    assert report.brands.created == report.brands.updated == 0
    assert report.reviews.created == report.reviews.updated == 0
    assert Review.objects.count() == 3


@pytest.mark.django_db
def test_an_edit_in_wordpress_updates_only_that_row(wordpress: FakeWordPress) -> None:
    run_import(wordpress)
    wordpress.edit_post(13, title="Slow claim")

    report = run_import(wordpress)

    assert (report.reviews.updated, report.reviews.unchanged) == (1, 2)
    assert Review.objects.get(wp_id=13).title == "Slow claim"


@pytest.mark.django_db
def test_brand_rating_is_computed_from_published_reviews(wordpress: FakeWordPress) -> None:
    wordpress.add_review(15, brand=7, rating=1, status="draft")
    wordpress.add_brand(8, industry=2, meta={"average_rating": "4.4"})

    run_import(wordpress)

    rated = Brand.objects.get(wp_id=7)
    assert (rated.average_rating, rated.review_count) == (Decimal("4.33"), 3)
    unrated = Brand.objects.get(wp_id=8)
    assert (unrated.average_rating, unrated.review_count) == (None, 0)
    assert unrated.legacy_average_rating == Decimal("4.4")


@pytest.mark.django_db
def test_short_description_is_derived_once_then_left_to_editors(
    wordpress: FakeWordPress,
) -> None:
    words = " ".join(f"w{i}" for i in range(30))
    wordpress.edit_post(7, content=f"<p>{words}</p>")
    run_import(wordpress)
    brand = Brand.objects.get(wp_id=7)
    assert brand.short_description == " ".join(f"w{i}" for i in range(22)) + "…"

    Brand.objects.filter(pk=brand.pk).update(short_description="Edited by an editor")
    wordpress.edit_post(7, content="<p>New body from WordPress.</p>")
    run_import(wordpress)

    assert Brand.objects.get(wp_id=7).short_description == "Edited by an editor"


@pytest.mark.django_db
def test_rows_gone_from_wordpress_are_hidden_not_deleted(wordpress: FakeWordPress) -> None:
    run_import(wordpress)
    wordpress.reviews = [r for r in wordpress.reviews if r.id != 14]
    wordpress.edit_post(13, status="trash")

    report = run_import(wordpress)

    assert report.reviews.removed == 1
    statuses = dict(Review.objects.values_list("wp_id", "status"))
    assert statuses == {12: "publish", 13: "trash", 14: "removed"}
    assert Brand.objects.get(wp_id=7).review_count == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda wp: wp.add_review(20, brand=7, rating="6"), "review 20: rating '6'"),
        (lambda wp: wp.add_review(20, brand=7, rating="4.5"), "review 20: rating '4.5'"),
        (lambda wp: wp.add_review(20, brand=99), "review 20: points at brand 99"),
        (
            lambda wp: wp.add_brand(8, industry=2, meta={"website_url": "javascript:alert(1)"}),
            "brand 8: website_url",
        ),
        (lambda wp: wp.add_brand(8, industry=2, slug="café"), "brand 8: slug 'café'"),
        (lambda wp: wp.add_brand(8), "brand 8: has 0 industries"),
        (
            lambda wp: (
                wp.add_industry(3, "Retail"),
                wp.add_brand(8, industry=2),
                wp.links.append(wp.links[-1].__class__(object_id=8, term_id=3)),
            ),
            "brand 8: has 2 industries",
        ),
        (
            lambda wp: wp.add_brand(8, industry=2, meta={"_yoast_wpseo_focuskw": "x"}),
            "brand 8: untriaged postmeta keys ['_yoast_wpseo_focuskw']",
        ),
        (
            # WordPress's post_password field, not a credential.
            lambda wp: wp.add_brand(8, industry=2, password="x"),  # noqa: S106
            "brand 8: is password-protected",
        ),
    ],
)
def test_a_row_that_does_not_fit_stops_the_run_before_any_write(
    wordpress: FakeWordPress, change: Callable[[FakeWordPress], object], message: str
) -> None:
    change(wordpress)

    with pytest.raises(WpRowError, match=re.escape(message)):
        run_import(wordpress)

    assert not Brand.objects.exists()


@pytest.mark.django_db
def test_content_is_sanitized_and_the_raw_source_kept(wordpress: FakeWordPress) -> None:
    body = '<p onclick="x()">AT&T <script>alert(1)</script><a href="javascript:x">l</a></p>'
    wordpress.edit_post(12, content=body)

    run_import(wordpress)

    review = Review.objects.get(wp_id=12)
    assert review.content_html == '<p>AT&amp;T <a rel="nofollow noopener noreferrer ugc">l</a></p>'
    assert review.content_text == "AT&T l"
    assert review.content_source == body


@pytest.mark.django_db
def test_plain_text_keeps_a_space_between_adjacent_paragraphs(wordpress: FakeWordPress) -> None:
    wordpress.edit_post(12, content="<p>Fast claim.</p><p>Fair price.</p>")

    run_import(wordpress)

    assert Review.objects.get(wp_id=12).content_text == "Fast claim. Fair price."


@pytest.mark.django_db
def test_dry_run_reports_without_writing(wordpress: FakeWordPress) -> None:
    report = run_import(wordpress, dry_run=True)

    assert report.reviews.created == 3
    assert not Review.objects.exists()


@pytest.mark.django_db
def test_only_review_authors_become_reviewers(wordpress: FakeWordPress) -> None:
    wordpress.add_user(1, "admin")
    wordpress.add_user(3, "Mike &amp; Co.")
    wordpress.add_review(15, brand=7, author=3)

    run_import(wordpress)

    names = set(Reviewer.objects.values_list("display_name", flat=True))
    assert names == {"Sarah K.", "Mike & Co."}
