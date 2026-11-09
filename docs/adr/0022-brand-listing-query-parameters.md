# 0022. Brand listing query parameters

- Status: Accepted (`page_size` parsing refined in [0027](0027-pillar-2-listing-contract-details.md), item 7)
- Date: 2026-11-09

## Context
`GET /api/brands/` is filterable by industry, sortable by average rating and review
count, and paginated (CHALLENGE.md Pillar 2, question 4). ADR 0002/0015 chose
page-number pagination with a tie-breaker and a capped page size. The research
(`docs/research/pillar-2-brands-api.md` §1–4) added what the data and DRF actually do:

- All 5 brands have exactly 12 reviews, checked in the dump on this date. Sorting by
  review count is therefore decided entirely by the tie-breaker.
- DRF's `OrderingFilter`:
  - drops the `id` tie-breaker whenever a client sorts;
  - silently ignores invalid values;
  - accepts comma lists;
  - can't put NULL ratings last.
- DRF's page-size handling clamps or falls back silently instead of rejecting.

## Options considered
**Industry filter:**
- **A single value.** Rejected: multi-select would later need a contract change.
- **Comma-separated values.** Rejected: a second syntax to parse.
- **Repeated keys** (`?industry=a&industry=b`). Chosen: HTML forms, `URLSearchParams`
  and DRF's `ListField` all handle them natively.

**Sort:**
- **DRF `OrderingFilter`.** Rejected for the four behaviors listed above.
- **`sort=` plus `order=`.** Rejected: two parameters whose combinations need
  validating.
- **One `ordering` parameter with a closed set of values.** Chosen.

**Page size:**
- **Fixed at 12.** Rejected: clients can't ask for fewer, and pagination can't be shown
  with 5 brands.
- **`page_size` from 1 to 50.** Chosen.

**django-filter:** rejected. One validated query serializer covers three parameters
without another dependency.

## Decision
- **`industry`:** repeatable; values are industry slugs, never ids. Several values mean
  OR (any listed industry). At most 10 values.
- **`ordering`:** one of the four values below. The request value is only ever a
  dictionary key; what reaches `order_by()` is an expression written in code. Any other
  value gets 400.

  | Value | Ordering |
  |---|---|
  | `-average_rating` (default) | rating desc, NULLs last, then `-review_count`, then `id` |
  | `average_rating` | rating asc, NULLs last, then `id` |
  | `-review_count` | `-review_count`, `name`, `id` |
  | `review_count` | `review_count`, `name`, `id` |
- **`page` and `page_size`:** a `PageNumberPagination` subclass with `page_size = 12`,
  `page_size_query_param = "page_size"` and `max_page_size = 50`, keeping DRF's envelope
  (`count`, `next`, `previous`, `results`).
  - A `page_size` outside 1–50, or not a number, gets 400.
  - A page past the end keeps DRF's 404.
- A DRF serializer validates the query string before anything touches the queryset. The
  view turns the result into a frozen dataclass (ADR 0013).
- Ratings are the computed values from ADR 0019.

## Consequences
- About ten lines of sort mapping that we own, in place of `OrderingFilter`.
- With today's data, the review-count sort shows brands by name.
- Still open: whether an unknown industry slug gets 400 or an empty page; whether
  unknown parameter names are ignored; what the "top review" snippet is; the error
  format; versioning; and `PATCH` concurrency. The options are in the research note.

## Revisit when
A mobile client needs infinite scroll (then a signed keyset cursor over stored columns),
or the listing needs more filters.

## Sources
`docs/research/pillar-2-brands-api.md` §1–4, §10.
