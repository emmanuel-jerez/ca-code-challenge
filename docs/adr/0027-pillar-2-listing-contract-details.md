# 0027. Pillar 2: the brand listing's open contract details

- Status: Accepted
- Date: 2026-11-09

## Context
ADR 0022 fixed the listing's parameters (`industry`, `ordering`, `page`,
`page_size`) and left six questions open, with options in
`docs/research/pillar-2-brands-api.md`. They had to be answered before
`GET /api/brands/` could be built. Facts that shaped them:

- Every brand in the dump has several 5-star reviews, so any "top review"
  definition needs a tie-breaker.
- `Review.content_text` already holds each review's plain text, cleaned at
  import (ADR 0026).
- The only client today is `<BrandList />`, which reads status codes and
  `safeParse` results, not error messages (ADR 0010).
- The challenge fixes the path at `/api/brands/`.

The user chose items 1–6 on this date, taking the recommendation each time.
Items 7–9 are implementation defaults the agent took while building, flagged
for review in the Pillar 2 pull request.

## Options considered
1. **What "top review" means.**
   - Newest. Rejected: dates in this data are an artifact of seeding.
   - Most helpful, or longest. Rejected: there are no votes, and length
     rewards rambling.
   - The review closest to the brand's average. Rejected, but it's the
     alternative to mention: more honest, and the same cost with stored
     averages.
   - Highest rating, then newest, then id. Chosen: the plain reading of
     "top", and the same answer on every request.
2. **An unknown industry slug.** A 200 with an empty page was rejected: it
   shows a stale or mistyped link as "no brands". A 400, the same as a bad
   `ordering`, was chosen.
3. **Unknown parameter names** (`?foo=1`). Rejecting them was rejected: a
   newer client, say a mobile app, would break against an older server during
   a rollout. They're ignored. Known parameters stay strict.
4. **Error format and versioning.**
   - RFC 9457 Problem Details now. Rejected: about 40 lines that no current
     client reads.
   - `/api/v1/brands/` or an `Accept`-header version. Rejected: they depart
     from the challenge's path, to version one endpoint for one client.
   - DRF's default error bodies, no version, and a written compatibility
     policy. Chosen.
5. **Snippet text.** A stored `Review.snippet` column was rejected: a
   migration and an import change, to save cutting at most 50 short strings
   per page. The snippet is cut from `content_text` per request.
6. **The contract fixture.** One example response (ADR 0010's wording) was
   rejected: it can't show the null and error shapes where UIs break. Named
   cases were chosen. This extends ADR 0010 rather than changing it.
7. **Who parses `page_size`.** ADR 0022 described a paginator with
   `page_size_query_param` and `max_page_size`. That was rejected while
   building: DRF would then parse the value a second time with its own rules,
   so `page_size=5.0` would pass the query serializer and then silently fall
   back to 12 in the paginator. The query serializer is the only parser, and
   the paginator receives the validated number. The contract ADR 0022 gives
   (1–50, default 12, a 400 otherwise, DRF's envelope) is unchanged; 0022's
   status line links here.
8. **Caching.**
   - `cache_page` or the cache middleware. Rejected: seven data-exposure CVEs
     in 5.2.14–5.2.19.
   - No caching headers. Rejected: browsers re-download unchanged pages.
   - `conditional_page` (an ETag and 304s) plus
     `Cache-Control: public, no-cache`. Chosen, on the listing view only.
9. **Throttling.** DRF's throttles were rejected: they're counted per
   gunicorn process, and DRF itself says they aren't a security measure. Rate
   limiting belongs at a proxy in front of the app.

## Decision
- **Top review:** the brand's highest-rated published review, then the
  newest, then the highest id. It's fetched for the whole page by one sliced
  `Prefetch` (a `ROW_NUMBER()` window query), loading card fields only. A
  brand with no published reviews has `top_review: null`.
- **Snippet:** `content_text` cut with `Truncator.chars(160)`, ending in "…"
  when cut. It's plain text on the wire; clients render it as text. Truncator's
  `html=True` (CVE-2026-1285) is never used.
- **Validation:** an unknown industry slug is a 400 naming it. A malformed
  or empty one is reported the same way, checked exactly as sent (no
  trimming). A known industry with no published brands is a 200 with an
  empty page. An empty `ordering` or `page_size` (`?ordering=`) is a bad
  value, a 400, not a request for the default. A repeated `ordering` or
  `page_size` uses its last value, as Django's `QueryDict` does. Unknown
  parameter names are ignored.
- **`page` stays DRF's** (ADR 0022, research §3.4): empty means page 1,
  `last` means the last page, and any other value that isn't a page number,
  or is past the end, is a 404.
- **Errors:** DRF's default bodies. A 400 is a map from parameter name to a
  list of messages; a 404 is `{"detail": "…"}`.
- **Versioning:** none. Compatibility policy: changes to `/api/brands/` are
  additive only. A breaking change adds `/api/v2/brands/` and keeps
  `/api/brands/` until its clients have moved, the same expand → migrate →
  contract as the shared library (ADR 0025). Additive changes are safe
  because Zod's `z.object` strips unknown keys.
- **Fixture:** `contracts/brand-list.example.json` holds real responses:
  first page, last page, empty page, a 400 and a 404. Together they cover an
  unrated brand with a blank description, a snippet with `&`, `<` and `>`, and
  both page links. `make contracts` regenerates it.
- **HTTP:** the listing sets no authentication classes, so a stale token
  can't break it. It sends `Cache-Control: public, no-cache` and an ETag, and
  doesn't throttle. Wire names are snake_case, and slugs are the public keys
  (no database ids).

## Consequences
- A 3-star brand's card still quotes a 5-star review.
- Snippets can end mid-word ("…the same d…").
- DRF's message wording is now in the contract fixture: a DRF upgrade that
  rewords a message fails the fixture test. That's intended. The frontend
  doesn't show these messages.
- The ETag is computed from the rendered body, so a 304 saves bandwidth but
  not the database queries.
- Ignoring unknown parameters hides typos such as `?odering=`.
- A filtered request costs one more query (checking the slugs). An unfiltered
  page costs three, whatever its size.
- Still open: `<BrandList />` needs the list of industries for its filter
  control, and nothing serves it yet. The options (a second endpoint, or a
  list built into the frontend) belong to Pillar 3. The `PATCH` concurrency
  question belongs to Pillar 5.

## Revisit when
A second client arrives (add RFC 9457 errors with stable codes), the listing
is slow under load (an index on `(brand, -rating, -published_at, -id)` for the
top review, then caching at a proxy), or reviews gain votes (redefine "top").

## Sources
`docs/research/pillar-2-brands-api.md` §3.4, §5.2–5.5, §7–9 and "Open
decisions"; DRF 3.18.3 `pagination.py` (`get_page_size`) and `fields.py`
(`ListField.get_value`), installed package, checked 2026-11-09; Django 5.2
`django.views.decorators.http.conditional_page`.
