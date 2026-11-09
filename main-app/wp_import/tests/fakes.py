"""An in-memory WordPress that satisfies the WpSource Protocol."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypedDict, Unpack

from wp_import.source import PostType, RawPost, RawTerm, RawTermLink, RawUser

if TYPE_CHECKING:
    from collections.abc import Iterator

POSTED = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


class PostFields(TypedDict, total=False):
    """RawPost fields a test may override."""

    slug: str
    title: str
    content: str
    excerpt: str
    status: str
    password: str


@dataclass
class FakeWordPress:
    terms: list[RawTerm] = field(default_factory=list)
    links: list[RawTermLink] = field(default_factory=list)
    people: list[RawUser] = field(default_factory=list)
    brands: list[RawPost] = field(default_factory=list)
    reviews: list[RawPost] = field(default_factory=list)

    def industries(self) -> Iterator[RawTerm]:
        yield from self.terms

    def industry_links(self) -> Iterator[RawTermLink]:
        yield from self.links

    def users(self) -> Iterator[RawUser]:
        yield from self.people

    def posts(self, post_type: PostType) -> Iterator[RawPost]:
        yield from self.brands if post_type == "brand" else self.reviews

    # Builders: valid rows by default, so a test changes only what it checks.

    def add_industry(self, term_id: int, name: str = "Insurance") -> None:
        self.terms.append(RawTerm(term_id=term_id, name=name, slug=name.lower()))

    def add_user(self, user_id: int, display_name: str) -> None:
        self.people.append(RawUser(id=user_id, display_name=display_name))

    def add_brand(
        self,
        post_id: int,
        *,
        industry: int | None = None,
        meta: dict[str, str] | None = None,
        **fields: Unpack[PostFields],
    ) -> None:
        if industry is not None:
            self.links.append(RawTermLink(object_id=post_id, term_id=industry))
        post = _post(
            post_id,
            f"brand-{post_id}",
            f"Brand {post_id}",
            "<p>A brand that sells things to people in many places.</p>",
        )
        all_meta = {
            "website_url": "https://example.com",
            "founded_year": "1990",
            "headquarters": "Hartford, CT",
            "average_rating": "4.2",
            "_website_url": "field_brand_website_url",
            "_yoast_wpseo_title": "Brand reviews",
            "_yoast_wpseo_metadesc": "Read reviews.",
        }
        self.brands.append(replace(post, meta={**all_meta, **(meta or {})}, **fields))

    def add_review(
        self,
        post_id: int,
        *,
        brand: int,
        rating: int | str = 4,
        author: int = 0,
        meta: dict[str, str] | None = None,
        **fields: Unpack[PostFields],
    ) -> None:
        post = _post(
            post_id, f"review-{post_id}", f"Review {post_id}", "<p>Fast claim, friendly staff.</p>"
        )
        all_meta = {
            "brand": str(brand),
            "rating": str(rating),
            "reviewer_name": "Sarah K.",
            "reviewer_location": "Denver, CO",
            "_rating": "field_review_rating",
        }
        self.reviews.append(
            replace(post, author_id=author, meta={**all_meta, **(meta or {})}, **fields)
        )

    def edit_post(self, post_id: int, **fields: Unpack[PostFields]) -> None:
        for posts in (self.brands, self.reviews):
            for i, post in enumerate(posts):
                if post.id == post_id:
                    posts[i] = replace(post, **fields)


def _post(post_id: int, slug: str, title: str, content: str) -> RawPost:
    return RawPost(
        id=post_id,
        slug=slug,
        title=title,
        content=content,
        excerpt="",
        status="publish",
        password="",
        author_id=0,
        date_gmt=POSTED,
        modified_gmt=POSTED,
        meta={},
    )
