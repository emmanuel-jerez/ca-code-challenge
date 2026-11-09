# 0019. Brand rating computed from reviews and stored at import

- Status: Accepted
- Date: 2026-11-09

## Context
CHALLENGE.md question 1: a brand has an ACF `average_rating` field *and* reviews with
their own ratings. Store, derive, or both? The data settled most of it
(`docs/research/pillar-1-django-backend.md` §1, §3; checked again by parsing
`db/dump.sql` on this date):

| Brand | ACF `average_rating` | Mean of its 12 reviews |
|---|---|---|
| UrbanRetail Co. | 4.4 | 3.67 |
| Acme Insurance Co. | 4.2 | 3.92 |
| PrimePath Bank | 4.0 | 3.83 |
| HomeShield Pro | 3.9 | 3.08 |
| SwiftStream Internet | 3.5 | 3.50 |

The stored value is too high for 4 of 5 brands, by up to 0.82. Review submission is out
of scope, so the importer is the only thing that ever writes reviews. The listing API
sorts by rating (Pillar 2), so the value has to be sortable cheaply.

## Options considered
- **Derive at query time** (`annotate(Avg, Count)`). Always right. Rejected: every
  listing request aggregates before `LIMIT`, and the "top review" subquery stacks on top.
- **Signals keep stored columns in sync.** Rejected: `bulk_create`, `update()` and bulk
  upserts skip signals, so the importer's fast path would bypass them.
- **A PostgreSQL trigger, or a materialized view.** Rejected: raw SQL in migrations,
  logic hidden from Python readers, and heavyweight for 5 brands (or 500).
- **`GeneratedField`.** Impossible: it can't reference other rows.
- **Show WP's stored value.** Rejected: it contradicts the reviews on the same page.
- **Stored columns recomputed by one set-based update at the end of each import, with
  WP's value kept for audit.** Chosen.

## Decision
- `Brand.average_rating` (nullable decimal, NULL when a brand has no reviews) and
  `Brand.review_count` hold values computed from the brand's reviews.
- One service function recomputes both for all brands in a single set-based `UPDATE` at
  the end of every import run.
- WP's number is kept as `Brand.legacy_average_rating`. It is never shown by default and
  exists to show the discrepancy.
- Pages and the API show and sort by the computed value. Sorts put NULLs last
  (`nulls_last=True`), because PostgreSQL puts NULLs first in descending order.
- A test compares the stored values with a fresh `annotate()` to catch drift.

## Consequences
- The homepage order changes from WP's. By computed mean it's Acme, PrimePath,
  UrbanRetail, SwiftStream, HomeShield. Acme drops from 4 to 3 full stars, because the
  theme floors the value.
- If a second writer of reviews is ever added, it must call the same recompute function.

## Revisit when
Reviews gain another writer (submission, moderation), or review volume makes the
recompute slow.

## Sources
`docs/research/pillar-1-django-backend.md` §1, §3; `docs/research/pillar-2-brands-api.md` §1, §5.1.
