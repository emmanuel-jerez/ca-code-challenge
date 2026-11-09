# Pillar 2: the brands API (`GET /api/brands/`, `PATCH /api/brands/<slug>/`)

Researched 2026-11-09 for Django 5.2 LTS, DRF `>=3.18.3,<3.19`, Postgres 18 (ADRs 0001, 0002, 0006).

Scope: the design of the public brand listing endpoint (pagination, filter and sort parameters, query
shape, "top review snippet", errors, versioning, hardening, and the contract with `<BrandList />`), plus
the shape of the editor-only `PATCH /api/brands/<slug>/` from Pillar 5. Token minting and verification
are another agent's topic; this document only covers what the endpoint needs from them (401 vs 403, a
scope check). It goes below `best-practices-2026.md` §5 and `stack-decisions.md` §2a to implementation
level, and corrects them where they're wrong.

> **How this was checked.** Library behavior comes from DRF 3.18.3 and Django `stable/5.2.x` source and
> docs, read through Context7 (DRF pagination; Django 5.2 `Prefetch`, `condition`, `distinct`; Vite 8.3.5;
> Zod 4.6.7) and the raw files on GitHub. The Context7 quota was not exhausted. Advisories come from the
> GitHub repository advisories API, OSV and the Django release notes. The key DRF/Django behaviors were
> also **run** in a throwaway script outside the repo: Django 5.2.18, DRF 3.18.3 and nh3 0.3.7, resolved
> with the 7-day cooldown, on Python 3.12 + SQLite [35]. That's not the project's Python 3.14 + Postgres 18;
> see "Not verified". Data facts come from parsing `db/dump.sql` as data [35]. Anything secondary is
> marked *(secondary)*.

---

## Key findings

1. **The real data makes `review_count` sorting a total tie.** There are 5 brands and 60 reviews, and
   *every* brand has exactly 12 reviews. `?ordering=-review_count` is therefore decided entirely by the
   tie-breaker. The ACF `average_rating` disagrees with the mean of the review ratings for 4 of 5 brands,
   and the two give **different sort orders**. No brand has a `post_excerpt`, so `short_description` has
   no WordPress source at all [35].
2. **DRF's `OrderingFilter` throws away your tie-breaker.** With `ordering = ["-average_rating", "id"]`
   on the view, `?ordering=-review_count` becomes `order_by("-review_count")`, with no `id`. Even
   `?ordering=-review_count,id` drops `id` unless `id` is allow-listed. Invalid values are dropped
   silently (no 400), and it can't express `nulls_last` [1][35].
3. **Postgres puts NULLs first in `DESC` order** [22]. A brand with no reviews (NULL average) would top a
   "best rated" sort unless the ordering uses `F(...).desc(nulls_last=True)` [21].
4. **The February 2026 CVEs are narrower than our notes say.** Only CVE-2026-1312 involves `order_by()`.
   It and CVE-2026-1287 both need the *attacker* to control alias names passed as `**kwargs`. CVE-2026-1207
   is a PostGIS raster band index. All are fixed in 5.2.11 [14]. An explicit `ordering_fields` list blocks
   these vectors because DRF matches terms by exact string [1]. The patch level is the real fix.
   CVE-2026-1285, a quadratic `Truncator(html=True)` DoS, is the one that touches *this* endpoint (snippet
   truncation) [14].
5. **Cursor pagination doesn't fit a sort on a live aggregate.** DRF filters on the first ordering field
   only, plus an offset capped at 1,000. The cursor is unsigned base64; a forged position raised an
   uncaught `ValueError` (a 500) in the test run. DRF's docs ask for an unchanging, non-float, non-null,
   indexed key [2][3][35]. This supports ADR 0002's page-number choice.
6. **PATCH needs two things DRF won't do for you.** Serializers silently ignore unknown fields (`name`,
   `slug` were dropped with a 200). And 401 vs 403 depends on the auth class implementing
   `authenticate_header()`: the test got 403 without it and 401 with it [7][35]. The shared library's class
   must implement it.
7. **DRF throttling keys anonymous users on a header the client controls.** With the default
   `NUM_PROXIES = None`, the throttle identity is the raw `X-Forwarded-For` value, so rotating that header
   bypasses it. Set `NUM_PROXIES = 0` (there's no proxy, ADR 0008). DRF itself says its throttles are "not
   a security measure" [5][6].
8. **DRF had 5 advisories in 2026**: 2 medium (fixed in 3.17.2) and 3 high (fixed in 3.18.2). One makes
   the default `JSONParser` amplify 108 bytes into a ~50M-character value [10][11]. The browsable API had
   XSS CVEs in 2020 and 2024 [10]. Ship JSON-only renderers and `JSONParser` only in production.
9. **Django's server-side cache had 7 low-severity data-exposure CVEs** in 5.2.14–5.2.19 (`cache_page`,
   `UpdateCacheMiddleware`, `Vary` handling) [16]. Don't cache the listing server-side. Use
   `ConditionalGetMiddleware` plus `Cache-Control`; that saves bandwidth, not database work [20].
10. **Top review without N+1:** a sliced `Prefetch` (Django ≥ 4.2) costs one extra query using
    `ROW_NUMBER() OVER (PARTITION BY brand_id …)`, whatever the page size [18][35]. `Subquery` costs one
    correlated subquery *per column*. If industry becomes many-to-many, a join-based filter **inflates
    `review_count`** (3 became 6 in the test); `Exists()` doesn't [35].
11. **django-filter 26.2 is healthy but doesn't earn its place here.** It supports Python 3.14 and Django
    5.2, is tested against released DRF, and has one advisory (from 2020) [13][24][25]. But for three
    params it can't express `nulls_last` sorts, and its multi-value filter is join-based. A hand-written
    serializer is about 30 lines.
12. **Contract traps:**
    - `COERCE_DECIMAL_TO_STRING` defaults to `True`, so a `DecimalField` average goes out as `"3.9"` [6].
    - nh3 output is HTML-escaped, so the real review "AT&T" would ship as `AT&amp;T` unless unescaped
      once [35].
    - Zod's `z.object` strips unknown keys by default, so additive API changes don't break the client
      [32].

---

## 1. The data behind the endpoint

From `db/dump.sql` (published posts only) and the mu-plugins [35]:

| Brand (slug) | Industry | ACF `average_rating` | Mean of reviews | Reviews | 5-star reviews |
|---|---|---|---|---|---|
| `acme-insurance` | insurance | 4.2 | 3.92 | 12 | 5 |
| `primepath-bank` | finance | 4.0 | 3.83 | 12 | 5 |
| `homeshield-pro` | home-services | 3.9 | 3.08 | 12 | 3 |
| `swiftstream-internet` | telecom | 3.5 | 3.50 | 12 | 3 |
| `urbanretail-co` | retail | 4.4 | 3.67 | 12 | 3 |

What this means for the API:
- **Average-rating sort depends on the source.**
  - By ACF: urbanretail, acme, primepath, homeshield, swiftstream.
  - By derived mean: acme, primepath, urbanretail, swiftstream, homeshield.

  Pillar 1 decides storage, but the API must say which number it shows *and* sorts by. They must be the
  same number, or the card order will look wrong next to the ratings.
- **Review-count sort is a five-way tie**, so the secondary key decides the whole order. A human-friendly
  secondary key (`name`) before `id` makes the result look intentional.
- **No `short_description` source.** `post_excerpt` is empty for all 5 brands. Candidates: the first
  `<p>` of `post_content` (222–276 characters as plain text), the Yoast meta description (105–140
  characters, SEO-flavored "Read 12 reviews of…"), or blank until an editor fills it in through the PATCH.
  Whatever Pillar 1 picks, a re-run of the importer must not overwrite an editor's PATCH (see §6).
- **Industry:** each brand has exactly one term today. But the taxonomy is non-hierarchical and
  attached to `brand` with no cardinality limit (`register_taxonomy('industry', ['brand'], …)` in
  `cpt.php`), so WordPress allows several. FK vs M2M is Pillar 1's call. The API consequence is
  `industry: {…}` vs `industries: [{…}]`, plus the aggregate-inflation trap in §5.3.
- **Reviews:**
  - All 60 bodies are HTML.
  - Ratings: 19 fives, 13 fours, 14 threes, 13 twos, 1 one.
  - Every brand has 3–5 reviews tied at 5 stars, so "highest rating" alone doesn't pick a top review.
  - Review dates are all distinct but fall within 100 seconds (one seeding burst).
  - The 60 bodies have only 47 distinct lengths.
  - There's no helpfulness signal: the only `wp_comments` row is WordPress's sample comment.
- **Text hazards:** one review body contains a bare `&` ("AT&T"). Brand and review content has no other
  entities.

**Defend it:** "I looked at the data first. Every brand has 12 reviews, so review-count sort is all
tie-breaker. And WP's stored average disagrees with the reviews for four of five brands, so I had to
choose which one the API sorts by."

---

## 2. Pagination shape

ADR 0002 already accepted page-number pagination with a tie-breaker and a capped page size. This section
checks that choice against the source and settles the details.

| | `PageNumberPagination` | `LimitOffsetPagination` | `CursorPagination` |
|---|---|---|---|
| Params | `?page=2&page_size=12` | `?limit=12&offset=12` | `?cursor=<opaque>` |
| Envelope | `count, next, previous, results` [2] | same | `next, previous, results` (no count) [2] |
| Jump to page N / total | Yes / yes | Yes / yes | No / no [3] |
| Security cost | None new. Out-of-range page → 404 [2] | No max offset: `offset` is unbounded and invalid values silently become 0 [2]. Deep offsets make the DB scan and discard rows | Cursor is unsigned base64 (`o`, `r`, `p`); the position goes straight into `filter()`. A forged `p=not-a-number` raised `ValueError` → **500** [2][35]. Offset capped at 1,000 against abuse [2] |
| Stability cost | Core class; no behavior changes in the 3.15–3.18 notes [9] | Same | Built in; requires `ordering` with no `__` lookups [2]. NULL handling was added in 3.15.0 and reverted in 3.15.2 [9], so nullable keys stay unsupported |
| Effort | Lowest | Low | Moderate; needs a validated or signed cursor subclass |
| Why it might lose | `COUNT(*)` per request; rows shift between pages when ratings change mid-browse | The UI doesn't think in offsets; same `COUNT(*)` | Filters only on `ordering[0]` and uses an offset within ties [2]. DRF asks for an unchanging, unique, non-float, non-null, indexed key [3]; a live average is none of those. With the real data's 5-way tie it degrades to pure offset [35] |

Details that matter:
- **`COUNT(*)` cost.** On the annotated queryset, Django 5.2 strips the aggregates from the count but
  keeps the join and `GROUP BY`. The test run showed:

  ```sql
  SELECT COUNT(*) FROM (SELECT brand.id … LEFT OUTER JOIN review … GROUP BY 1) subquery
  ```

  Postgres counts by scanning, because of MVCC [23]. At 100x (500 brands, 6,000 reviews) that's
  trivial. It matters at millions of rows; then use stored columns (a plain filtered count) or drop the
  total (cursor).
- **DRF's page-size handling is silent.**
  - `page_size_query_param` is off by default.
  - `max_page_size` *clamps* without an error.
  - A non-numeric or zero `page_size` silently falls back to the default.
  - `?page=99` and `?page=abc` both return `404 {"detail": "Invalid page."}` [2][35].

  The `django-lts` skill wants a 400 for bad values, so validate `page`/`page_size` in the query
  serializer before paginating (§3.4).
- **`next`/`previous` are absolute URLs** built by `request.build_absolute_uri()` [2]. They depend on
  `ALLOWED_HOSTS`, and behind TLS on `SECURE_PROXY_SSL_HEADER`; without it, a mobile client gets
  `http://` links. The web UI shouldn't follow them anyway: it builds the API URL from its own URL state
  (AGENTS.md: state lives in the URL).
- **What a mobile client would want:**
  - infinite scroll, ideally a keyset cursor;
  - correct absolute links;
  - no page jumps.

  If that arrives, the honest path is stored `average_rating`/`review_count` columns with an index
  `(average_rating DESC NULLS LAST, id)`, plus a small **signed** keyset cursor (`django.core.signing`).
  Signing stops the forged-position 500 above. DRF's cursor works mechanically on an annotation (it
  filters through `HAVING`), but it can't keep its "never see an item twice" promise when the key
  changes between requests.

**Recommendation:** `PageNumberPagination` subclass, `page_size = 12`, `page_size_query_param =
"page_size"`, `max_page_size = 50`, both params validated (400 on bad input) before paginating. Keep DRF's
default envelope unchanged. Keep DRF's 404 for an out-of-range page; the UI resets to page 1 when filters
change.

**Defend it:** "Page numbers because the UI is a grid with page controls and a count, and the data is
tiny. Cursor pagination needs an unchanging sort key, and a live average isn't one. For mobile I'd
denormalize the rating and add a signed keyset cursor."

---

## 3. Filter and sort parameters

### 3.1 Industry filter

| Form | Example | For | Against |
|---|---|---|---|
| Single value | `?industry=retail` | Simplest | The UI can't offer multi-select later without a contract change |
| **Repeated key** | `?industry=retail&industry=telecom` | HTML forms and `URLSearchParams.append/getAll` produce and read it natively. DRF's `ListField` reads `QueryDict.getlist()` [8]. Covers single-select too | Slightly longer URLs |
| Comma-separated | `?industry=retail,telecom` | Short; JSON:API style | Custom parsing. Safe for WP slugs (no commas), but a second syntax to maintain |

Semantics: repeated values mean OR (brands in *any* listed industry). Values are slugs (public, stable,
readable), never database IDs. Validate with `ListField(child=SlugField(max_length=…), max_length=10)`; the
cap bounds the `IN` list [8].

### 3.2 Sort parameter

| Option | For | Against |
|---|---|---|
| DRF `OrderingFilter` (`?ordering=-average_rating`) | DRF/django-filter convention; zero code; browsable-API sort widget | Drops the tie-breaker; silently ignores bad values; accepts comma lists; can't express `nulls_last` (findings 2–3) |
| `sort=` + `order=` | Readable | Two params whose combination needs validating; no ecosystem convention |
| **One param, named values, each mapped to a full ordering** | Exactly one code path per sort; tie-breaker and `nulls_last` can't be forgotten; values come from a closed set | ~10 lines you own |

What `OrderingFilter` actually did (view: `ordering_fields = ["average_rating", "review_count"]`,
`ordering = ["-average_rating", "id"]`) [35]:

| Query | Resulting `order_by()` |
|---|---|
| *(none)* | `-average_rating, id` |
| `-review_count` | `-review_count` (tie-breaker gone) |
| `-review_count,id` | `-review_count` (`id` not allow-listed → dropped) |
| `evil` | `-average_rating, id` (silent fallback, 200) |
| `-average_rating,name` | `-average_rating` |

**Recommendation:** keep the DRF-familiar name `ordering`, but treat it as an enum. Each value maps to a
fixed ORM ordering:

```python
SORTS: Final[dict[str, tuple[OrderBy | str, ...]]] = {
    "-average_rating": (F("average_rating").desc(nulls_last=True), F("review_count").desc(), "id"),
    "average_rating":  (F("average_rating").asc(nulls_last=True), "id"),
    "-review_count":   ("-review_count", "name", "id"),
    "review_count":    ("review_count", "name", "id"),
}  # default: "-average_rating"
```

The request value is only ever a dictionary *key*; what reaches `order_by()` is a developer-written
expression.

### 3.3 The February 2026 SQL injection CVEs

All of these were fixed in **5.2.11** (also 6.0.2 and 4.2.28; affected: main, 6.0, 5.2, 4.2) [14][15]:

| CVE | Severity | API | Precondition | Does an `ordering_fields` allow-list help? |
|---|---|---|---|---|
| CVE-2026-1312 | High | `QuerySet.order_by()` | A column alias *containing periods*, where the same alias was used in a `FilteredRelation` via "a suitably crafted dictionary, with dictionary expansion" [14] | Yes, for this vector. `OrderingFilter.remove_invalid_fields()` keeps a term only if it exactly equals an allow-listed name [1], so the client can't introduce an alias. The real fix is the patch |
| CVE-2026-1287 | High | `FilteredRelation` aliases through `annotate()`, `aggregate()`, `extra()`, `values()`, `values_list()`, `alias()` | Control characters in alias names from a crafted `**kwargs` dict [14] | Not relevant to sorting: never build `annotate()`/`alias()` kwargs from request data |
| CVE-2026-1207 | High | PostGIS raster lookups | Untrusted band index [14] | Not relevant (no GIS) |
| CVE-2026-1285 | Moderate | `Truncator.chars/words(html=True)`, `truncatechars_html`, `truncatewords_html` | Many unmatched end tags → quadratic parse [14] | Not an ORM bug, but **relevant to the snippet**: truncate plain text, not HTML (§5.4) |

The DRF docs add a second reason to allow-list: sorting on a hidden field leaks its relative values,
for example "order against a password hash field" [4]. `ordering_fields = "__all__"` widens the set to every
model field and annotation; leaving it unset widens it to every readable serializer field [1].

### 3.4 Invalid and unknown input

| Input | DRF default | Recommendation | Why |
|---|---|---|---|
| Bad `ordering` value | Ignored, default order, 200 [1] | **400** | The `django-lts` skill rule; a silent fallback hides client bugs |
| Bad `page_size` (0, `abc`, 500) | Default or clamped, 200 [2] | **400** | Same |
| Bad `page` | 404 [2] | Keep 404 | DRF convention; the UI handles it |
| Malformed or unknown industry slug | n/a | **400** (open decision) | Same as django-filter's "Select a valid choice"; catches stale links. Alternative: 200 with an empty page, which shows the UI's empty state |
| Unknown parameter *name* (`?foo=1`) | Ignored | **Ignore** (open decision) | Tolerant reader: a newer client (say, a mobile app) must not break against an older server during a rollout. Rejecting catches typos but breaks forward compatibility |

Shape: a `BrandListQuery` DRF serializer validates `request.query_params`. The view converts
`validated_data` to a frozen dataclass at the boundary (ADR 0013) and builds the queryset from it.

**Defend it:** "`ordering` is a closed enum. Each value maps to an ORM expression I wrote, ending in
`id` with NULLs last, so input never reaches `order_by()`. The February CVEs needed attacker-controlled
alias names; my allow-list removes that path, and Django ≥ 5.2.11 fixes it anyway."

---

## 4. django-filter or not

| | django-filter 26.2 | Hand-written `BrandListQuery` serializer |
|---|---|---|
| Version / date | 26.2, 2026-10-03; ~2 releases a year (25.1 Feb 2025, 25.2 Oct 2025, 26.1 Jul 2026) [13][24] | n/a |
| Support | Classifiers: Django 5.2/6.0/6.1, Python 3.11–3.15. tox runs Django 5.2 against *released* DRF; 26.1 notes DRF 3.18 for Django 6.1 [13][24] | Our code, on our pins |
| Advisories | One ever: GHSA-x7gm-rfgv-w973 (`NumberFilter` DoS, fixed 2.4.0, 2020) [25]. 26.2 added defense-in-depth escaping of `LinkWidget` labels [24] | Our responsibility, ~30 lines plus tests |
| Maintainers | Carlton Gibson's repo; small team *(PyPI metadata names Alex Gaynor as author [13])* | Us |
| Fit | `ModelMultipleChoiceFilter`/`MultipleChoiceFilter` gives repeated keys and 400 on invalid choices (`raise_exception = True`) [24]. But its filter is a join + `.distinct()` [24], which doesn't fix aggregate inflation on M2M (§5.3). Its `OrderingFilter` takes field names, not `nulls_last` expressions | Validation, the sort map and an `Exists()` filter are all explicit |
| Attack surface | One more package in both lockfiles, a new release twice a year to vet | None new |

**Recommendation:** hand-written. Revisit django-filter if the endpoint grows past about five filter
params.

**Defend it:** "django-filter is healthy, but I have three params, and its multi-value filter is
join-based, which would double-count reviews if industry ever became many-to-many. Thirty lines of
serializer don't need a dependency."

---

## 5. Query design

### 5.1 Annotated vs stored aggregates (Pillar 1 decides; API consequences)

| | Annotate per request (`Count`, `Avg`) | Stored columns kept in sync |
|---|---|---|
| Correctness | Always matches the reviews | Drifts unless recomputed on review save and in the importer. `GeneratedField` can't do it: it may only reference fields "in the same database table" [21] |
| Sort and filter | `GROUP BY` over reviews; can't be indexed; filters on it become `HAVING` | Index `(average_rating DESC NULLS LAST, id)`; index scan + `LIMIT` |
| `COUNT(*)` | Join + `GROUP BY` subquery (§2) | Plain filtered count |
| Cursor or keyset later | Unsuitable (mutable, float, nullable) [3] | Feasible (still mutable, but indexable) |
| M2M industry filter | Inflates `Count` unless filtered with `Exists` (§5.3) | No aggregate, no inflation |
| Typing (ADR 0009) | django-stubs records annotation *names*, not types; you supply `WithAnnotations[Brand, TypedDict]` [33] | Typed model fields |
| Precision on the wire | `Avg` → float; round with `Round(…, 1)` [21] | A `DecimalField` serializes as a **string** unless `coerce_to_string=False` [6] |

At this scale either works. For the API, the important part is to pin the wire type in the serializer
(`FloatField` or `DecimalField(coerce_to_string=False)`) so the Zod schema doesn't change when storage
does.

### 5.2 What "top review" means

| Definition | For | Against |
|---|---|---|
| **Highest rating → newest → `id`** | Simple, deterministic, cheap to index `(brand_id, rating DESC, published_at DESC, id DESC)` | Every card quotes a 5-star review, even the 3.1-rated brand (positivity bias) |
| Newest | "Fresh" | Dates in this data are an artifact of seeding (100 s apart) |
| Most helpful | Best UX signal | **No data**: there are no votes or comments |
| Longest | Content-rich | Rewards rambling; 60 reviews have only 47 distinct lengths, so it still needs `id` |
| Most representative (rating closest to the brand average → newest → `id`) | Honest | Needs the brand average inside the subquery; easy with stored columns, awkward with annotations |

Every definition must end in `id`. Ties at 5 stars exist for every brand in the real data.

### 5.3 Fetching it without N+1

| Approach | Queries per page | Notes |
|---|---|---|
| **Sliced `Prefetch(..., to_attr="top_reviews")`** | +1 | Supported since Django 4.2 [18]. On SQLite it emitted `ROW_NUMBER() OVER (PARTITION BY brand_id ORDER BY rating DESC, published_at DESC, id DESC)` filtered to `<= 1` [35]. Returns model instances; database-agnostic. Use `.only("id", "brand_id", "slug", "title", "rating", "reviewer_name", "snippet")` so full HTML bodies aren't loaded (`brand_id` is needed for matching) |
| `Subquery(...)[:1]` per column | +0 | One correlated subquery **per selected column**: the test emitted two for `id` and `body` [35]. `JSONObject` [21] inside one subquery fetches several columns at once, but returns untyped dicts |
| `distinct("brand_id")` (`DISTINCT ON`) | +1 | Postgres only; `order_by()` must start with the distinct fields [17]. Same cost as the prefetch, but you stitch the results yourself |
| Stored `Brand.top_review` FK | +0 via `select_related` | Another denormalized value to keep in sync |

**The many-to-many trap.** With M2M industries, filtering `industries__slug__in=[a, b]` on the annotated
queryset counted a brand that has both industries twice: `review_count` 3 → 6, whether the filter came
before or after `annotate()` [35]. Filtering with
`Exists(Industry.objects.filter(brand=OuterRef("pk"), slug__in=…))` gave the correct 3 [35]. With an FK
industry the join doesn't multiply rows, and `select_related("industry")` costs 0 queries.

### 5.4 Snippet text

nh3 is accepted (ADR 0004). `nh3.clean(body, tags=set())` drops tags *and* `<script>` contents. But its
output is **HTML-escaped**, and it glues paragraphs together: the test produced `"…great serviceSecond…"`
with `&amp;` left in [35]. So the snippet pipeline is:

1. Put whitespace at block boundaries.
2. Clean with `tags=set()`.
3. Collapse whitespace.
4. Run `html.unescape()` once.
5. Run `Truncator(text).chars(160)` on plain text.

Never use `html=True` in step 5: that's CVE-2026-1285's path [14]. Compute the snippet at import or save
time (a stored `Review.snippet`), not per request. The contract says `snippet` is **plain text**: React
renders it as a text node and Django autoescapes it. No consumer may inject it as HTML.

### 5.5 Asserting query counts

Use pytest-django 4.14.0 (classifiers Django 5.2 and Python 3.14 [13]) with
`django_assert_num_queries(n)` or `django_assert_max_num_queries(n)` [30]. With an FK industry and a
prefetched top review, the expected count is 3 (count, page, prefetch). Assert the *same* number for 1
brand and for 20 brands; that's what proves there's no N+1. Assert the empty page separately.

**Defend it:** "The top review is the highest-rated, then newest, then by ID, so it's deterministic. It's
fetched with a sliced `Prefetch`, which Django turns into one window-function query. The test asserts
three queries whether the page has one brand or twenty."

---

## 6. The PATCH endpoint

| Concern | Recommendation | Why / source |
|---|---|---|
| Route | `PATCH /api/brands/<slug:slug>/`, `lookup_field = "slug"`; only `patch` (+ `options`) in `http_method_names` | Slugs are the public key; PUT and DELETE aren't offered |
| Body | `{"short_description": "…"}`, with the field **required** | With `partial=True`, an empty `{}` passes as a no-op. One required field is clearer |
| Unknown fields | Reject with 400, keyed by field: `{"name": ["Unknown or read-only field."]}` | DRF ignores them silently: `name` and `slug` were dropped with a 200 [35]. Compare `set(self.initial_data) - set(self.fields)` in `validate()`. DRF has already rejected a non-object body ("Expected a dictionary") by then |
| Validation | `CharField(max_length=300, allow_blank=…)`. Plain text: no HTML accepted *as markup*, stored verbatim, always escaped on output. Optionally reject newlines and control characters | `CharField` already trims whitespace and rejects NUL and surrogate characters [8]. Accepting HTML would mean sanitizing and rendering it raw, which is new XSS surface |
| Parsers | `parser_classes = [JSONParser]` → anything else is 415 | GHSA-3547-9m27-7rxg (JSON codec amplification, fixed in 3.18.2) [11]; Django CVE-2026-108147 (MultiPartParser memory, 5.2.19) [16] |
| 401 vs 403 | No or invalid token → **401** with `WWW-Authenticate: Bearer realm="api"` (add `error="invalid_token"` when a token was sent). Valid token without the write scope → **403** (`insufficient_scope`) | RFC 9110: a 401 MUST carry `WWW-Authenticate` [27]. RFC 6750 §3.1 codes, and no error code when no credentials were sent [29]. DRF returns 401 only if the first authenticator's `authenticate_header()` returns a value, otherwise 403 [7][35] |
| Order of checks | DRF runs content negotiation → versioning → authentication → permissions → throttles, then the handler parses the body [7] | An unauthenticated attacker's body is never parsed. The `Accept` header *is* parsed before auth: GHSA-33wh-fxxf-88vv [10] |
| Revocation | ADR 0003's per-user token-version check runs on this write and fails closed | ADR 0003 |
| Response | **200 with the full card representation** (the same serializer as a list row, re-read through the annotated queryset) plus `Cache-Control: no-store` | The client can swap the row in place |
| Optimistic concurrency | Open decision. Cheapest sound version: an integer `version` column, `ETag: "<version>"` on GET and PATCH responses, and an atomic compare-and-set `filter(pk=…, version=v).update(…, version=F("version") + 1)`. 0 rows updated → **412**. `If-Match` missing → proceed (or **428** if you require it) | RFC 9110: `If-Match` uses strong comparison and fails with 412 [27]; RFC 6585 defines 428 [28]. Django's `condition()` decorator can return 412 [19], but it sets `ETag` only on GET/HEAD responses [19], and it isn't tested on DRF methods |
| Importer interplay | Record `short_description_edited_at` (and the editor's `sub`). The importer must never overwrite a field edited in Django | Otherwise re-running the migration (Pillar 1) silently reverts editors |
| Throttle | `ScopedRateThrottle` on a `brands_write` scope | `UserRateThrottle` keys on `request.user.pk` [5], so the shared library's principal needs a `pk` (or a custom throttle keyed on `sub`) |

**Defend it:** "The PATCH accepts exactly one field and rejects anything else, because DRF would
silently ignore it. No token gives 401 with a Bearer challenge; a reader's token gives 403. It returns
the updated card, so the UI can replace the row."

---

## 7. Errors and versioning

### 7.1 Error shape

DRF's default handler returns `{"detail": "…"}` for most exceptions, a field map
`{"field": ["…"], "non_field_errors": ["…"]}` for validation errors, plus `WWW-Authenticate` and
`Retry-After` headers [7]. DRF 3.18.3 has **no native RFC 9457 support**: nothing in the source, and no
upstream proposal found [7].

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| **DRF default** | None | Unchanged since forever | Zero | Two body shapes; messages, not stable codes |
| Custom `EXCEPTION_HANDLER` → `application/problem+json` (RFC 9457: `type`, `title`, `status`, `detail`, `instance`, plus extensions such as `errors: [{detail, pointer}]` [26]) | None new; RFC §5 says not to leak internals [26] | Our code (~40 lines + tests) | Low | Unnecessary for one client that only branches on status |
| `drf-standardized-errors` 0.16.0 (2026-04-29) | A dependency; no Django framework classifiers on PyPI [13] | Pre-1.0 | Low | 40 lines don't justify a package |
| `drf-problems` | A dependency; implements RFC 7807 (obsoleted by 9457) [34] | Old | Low | Wrong RFC |

**Recommendation:** DRF default for v1. The frontend shows the error state from the status code and
`safeParse` failures (ADR 0010). Add the RFC 9457 handler, with stable `code` values from DRF's
`get_full_details()`, when a second client arrives. The web client ignores error bodies, so switching
then isn't a break for it.

### 7.2 Versioning

The challenge fixes the path: `GET /api/brands/`.

| Option | For | Against |
|---|---|---|
| **None in v1 + compatibility policy** | Matches the spec. Additive changes are safe because Zod's `z.object` strips unknown keys [32] | A breaking change needs a new path later |
| `/api/v1/brands/` now (`URLPathVersioning` or `NamespaceVersioning`) | Explicit; mobile-friendly | Deviates from the spec's path; versioning one endpoint for one client |
| `Accept: application/json; version=1` (`AcceptHeaderVersioning`) | Clean URLs | Invisible in logs and curl; caches must vary on `Accept` (DRF adds `Vary: Accept` [7]) |

**Recommendation:** no version in v1. Write the policy down: additive changes only. On a breaking change,
add `/api/v2/brands/` and keep `/api/brands/` as v1 until clients migrate. That's the same
expand → migrate → contract as the shared library (AGENTS.md).

**Defend it:** "Errors use DRF's default shape because my only client branches on status. For a mobile
client I'd add RFC 9457 Problem Details with stable codes. That's a 40-line exception handler, not a
dependency. The URL stays unversioned as the challenge specifies; additive changes are safe because the
client strips unknown keys, and a breaking change gets `/api/v2/`."

---

## 8. Hardening

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["<shared_lib>.drf.BearerAuthentication"],  # not Session/Basic
    "DEFAULT_PERMISSION_CLASSES": ["<shared_lib>.drf.RequireDeclaredScope"],      # deny by default
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],        # + Browsable if DEBUG
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/min", "brands_write": "30/min"},
    "NUM_PROXIES": 0,
}
# Listing view: authentication_classes = [], permission_classes = [AllowAny], throttle_classes = [AnonRateThrottle]
```

| Control | Recommendation | Why / source |
|---|---|---|
| Permissions | Deny by default. The listing opts in with `AllowAny` | DRF's default is `AllowAny` [6]. A view that forgets its permissions should fail closed |
| Authentication | Only the shared library's bearer class. **The public listing sets `authentication_classes = []`** | DRF defaults to `SessionAuthentication` + `BasicAuthentication` [6]: cookie auth (CSRF exposure) and password checks in an app with no passwords. If an authenticator *raises* (expired token), DRF re-raises even on `AllowAny` views [7], so a stale token would break the public page |
| Browsable API | Off in production; on under `DEBUG` | It ships vendored jQuery 3.7.1 and Bootstrap 3, uses inline `style=` attributes (blocked by ADR 0005's `style-src 'self'`) [12], and has had XSS CVEs (CVE-2020-25626, CVE-2024-21520) [10]. It also can't send a `Bearer` header, so it doesn't help test the PATCH. The challenge's "token via the browsable API" refers to the auth service's login |
| Throttling | `AnonRateThrottle` on the listing (best-effort); `ScopedRateThrottle` on the PATCH; `NUM_PROXIES = 0` | With `NUM_PROXIES = None`, the identity is the whole client-sent `X-Forwarded-For` [5]. DRF's throttles are cache-based, "non-atomic" and "not … a security measure" [5]. `LocMemCache` is per process, so the real limit is rate × gunicorn workers. A `DatabaseCache` would write to the DB on every anonymous GET; real rate limiting belongs at an edge proxy |
| CORS | None. Same origin in production; Vite `server.proxy` in development [31] | django-cors-headers 4.9.0 (2025-09-18) has no advisories, but no Django 6.1 classifier and no release in 14 months [13]. Native mobile apps don't use CORS at all |
| Caching | `ConditionalGetMiddleware` + `Cache-Control: public, no-cache` on the listing (always revalidate; 304 when unchanged), `no-store` on the PATCH. **No `cache_page`** | The middleware hashes the rendered body after the view runs; GET only; skipped on `no-store` [20]. Seven 2026 CVEs hit `cache_page`/`UpdateCacheMiddleware` (`Vary: *`, case-sensitive `Private`, missing `Vary: Authorization`, empty vs absent `Vary` headers…) [16]. If the listing ever shows editor-only data, `public` must go |
| Versions | DRF ≥ 3.18.3 (covers all five 2026 advisories [10]); Django at the newest cooldown-cleared 5.2.x, never below 5.2.11 | §3.3 |
| JSON | Keep `STRICT_JSON = True` (the default; rejects `NaN`/`Infinity`) [6] | 3.18.1 also rejects non-finite `FloatField` values [9] |

**Defend it:** "Deny by default, JSON in and out, no session or basic auth, and the public listing
doesn't even look at the `Authorization` header. Throttles key on the socket address, because DRF's
default trusts a client-sent `X-Forwarded-For`. No server-side cache, because Django's cache middleware
had seven data-exposure CVEs this year."

---

## 9. Contract with the frontend (ADR 0010)

- **Field naming: snake_case on the wire.**
  - It's DRF's default and needs no dependency.
  - The camelCase package `djangorestframework-camel-case` last released on 2023-02-13 and declares only
    Python 3.10 [13].
  - The Zod schema mirrors the wire exactly. If the UI wants camelCase, the Zod `.transform()` at the
    boundary does it, which is a frontend choice.
- **No database IDs on the wire.** Slugs are the public keys. That keeps the fixture stable across test
  databases and avoids enumeration.
- **Fixture cases.** ADR 0010 names one file; covering these means a few cases (one file with named
  cases, or several files):

  | Case | What it pins |
  |---|---|
  | A full page | `count > page_size`, `next` non-null, `previous` null, rows with every field set |
  | A brand with no reviews | `average_rating: null`, `review_count: 0`, `top_review: null` |
  | A blank description | `short_description: ""` (not null, if the model uses `blank=True` without `null=True`) |
  | Text hazards | A snippet with `&` and `<` as plain text (from the real "AT&T" review) |
  | Empty page | `{"count": 0, "next": null, "previous": null, "results": []}` |
  | Error bodies | 400 field map and 404 `{"detail": …}`, so the error-state parser is tested too |

- **Wire types:**
  - `average_rating`: `number | null`, 0–5, one decimal (pin `FloatField` or
    `DecimalField(coerce_to_string=False)` [6]).
  - `review_count`: integer ≥ 0.
  - `next`/`previous`: `string | null`. Absolute URLs: keep the Zod check loose, because the fixture host
    is `testserver` [2].
- **Determinism:** fixed factories, no timestamps or IDs in the payload, sorted keys when writing the
  file.

**Defend it:** "The fixture is generated from the real serializer and parsed by the real Zod schema.
It includes the null cases (a brand with no reviews), the empty page and the error bodies, which are
where UIs usually break."

---

## 10. Sample request and response (illustrative)

Values use the derived mean and a first-sentence `short_description`. Pillar 1 decides both.

```http
GET /api/brands/?ordering=-average_rating&page_size=2 HTTP/1.1
Accept: application/json
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
Vary: Accept
Cache-Control: public, no-cache
ETag: "6f1c…"
```

```json
{
  "count": 5,
  "next": "http://localhost:8000/api/brands/?ordering=-average_rating&page=2&page_size=2",
  "previous": null,
  "results": [
    {
      "slug": "acme-insurance",
      "name": "Acme Insurance Co.",
      "industry": {"slug": "insurance", "name": "Insurance"},
      "average_rating": 3.9,
      "review_count": 12,
      "short_description": "Acme Insurance is a long-running general-lines insurer offering auto, home, and umbrella coverage across 38 US states.",
      "top_review": {
        "slug": "umbrella-policy-was-easy-to-add",
        "title": "Umbrella policy was easy to add",
        "rating": 5,
        "reviewer_name": "Sarah K.",
        "snippet": "Added a $1M umbrella policy. The process was completely painless — about 15 minutes on a phone call with my agent, paperwork emailed for…"
      }
    },
    {
      "slug": "primepath-bank",
      "name": "PrimePath Bank",
      "industry": {"slug": "finance", "name": "Finance"},
      "average_rating": 3.8,
      "review_count": 12,
      "short_description": "PrimePath Bank is a regional retail bank operating 220 branches across the Northeast United States.",
      "top_review": {
        "slug": "tellers-and-managers-are-well-trained",
        "title": "Tellers and managers are well-trained",
        "rating": 5,
        "reviewer_name": "Roberto G.",
        "snippet": "Walked into a branch on vacation in another state. They handled my issue (replacing a debit card lost in a rental car) in 20 minutes…"
      }
    }
  ]
}
```

A fixture-only row (no brand in the dump has zero reviews):
`{"slug": "new-brand", …, "average_rating": null, "review_count": 0, "top_review": null}`.

```http
GET /api/brands/?ordering=name  →  400 {"ordering": ["\"name\" is not a valid choice."]}
GET /api/brands/?page=9         →  404 {"detail": "Invalid page."}
```

```http
PATCH /api/brands/acme-insurance/ HTTP/1.1
Authorization: Bearer <EdDSA at+jwt>
Content-Type: application/json
If-Match: "7"

{"short_description": "Agent-led insurer for auto, home and umbrella cover in 38 states."}
```

| Outcome | Response |
|---|---|
| Success | `200` + full card + `ETag: "8"` + `Cache-Control: no-store` |
| No token | `401` + `WWW-Authenticate: Bearer realm="api"` |
| Expired token | `401` + `WWW-Authenticate: Bearer realm="api", error="invalid_token"` |
| Reader token | `403 {"detail": "You do not have permission to perform this action."}` |
| `{"name": "x", …}` | `400 {"name": ["Unknown or read-only field."]}` |
| Stale `If-Match` | `412` |
| Form-encoded body | `415` |

---

## Open decisions for the user

| # | Question | Options | Recommendation |
|---|---|---|---|
| 1 | Which average does the API show and sort by? (with Pillar 1) | Derived from reviews / WP's ACF value | Derived. It matches the reviews on the page; keep ACF in the DB for audit only |
| 2 | What is the "top review"? | Highest → newest → id / representative / newest / longest | Highest → newest → `id`; name the positivity bias, mention "representative" as the alternative |
| 3 | Sort param name and values | `ordering` enum / DRF `OrderingFilter` / `sort`+`order` | `ordering` enum: `±average_rating`, `±review_count`; default `-average_rating`; NULLs last; ends in `id` |
| 4 | Secondary sort keys | `id` only / `name, id` / `review_count, id` | `-average_rating` → `-review_count, id`; review count → `name, id` |
| 5 | Industry filter | Single / repeated / comma | Repeated keys, OR, slugs, ≤ 10 values |
| 6 | Unknown industry slug | 400 / empty 200 | 400 (consistent with sort validation); the UI offers "clear filters" |
| 7 | Unknown param *names* | Ignore / 400 | Ignore (tolerant reader); validate known params strictly. Note: the `django-lts` skill's "reject anything else with a 400" can be read either way |
| 8 | Client-controlled page size? | Fixed 12 / `page_size` 1–50 | `page_size` 1–50, default 12. It also lets you demo pagination with 5 brands |
| 9 | Error format | DRF default / RFC 9457 handler | DRF default in v1; RFC 9457 when a second client arrives |
| 10 | Versioning | None / `/api/v1/` / `Accept` header | None in v1, with a written additive-only policy |
| 11 | PATCH concurrency | None / optional `If-Match` / required (428) | Optional `If-Match` with a `version` column (cheap, defensible); revisit "required" if editors multiply |
| 12 | `short_description` rules | Plain text vs HTML; max length; blank allowed? | Plain text, ≤ 300 characters, blank allowed; the importer never overwrites an edited value |
| 13 | django-filter | Adopt / hand-write | Hand-write |
| 14 | Contract fixture coverage | One example file (ADR 0010 wording) / named cases | Named cases (§9). This extends ADR 0010 rather than changing it |

---

## Corrections to earlier research notes

- `best-practices-2026.md` §0.8, §4 and the `django-lts` skill say the three February 2026 SQL injection
  CVEs all came "through `order_by` or aliases". **CVE-2026-1207 is PostGIS raster lookups.** The two
  alias CVEs need attacker-controlled `**kwargs` keys; CVE-2026-1312 is the only `order_by` one [14].
  §4 already lists CVE-2026-1207 correctly. The summary line is what overstates.
- `best-practices-2026.md` §5:
  - "`annotate` plus a `Subquery` gives a single query": page-number pagination always adds a `COUNT`
    query, and each `Subquery` column is a separate correlated subquery [35].
  - "Return 400 on unknown values": DRF's `OrderingFilter` does the opposite, so this needs custom code
    [1].
  - "Cap `page_size`": DRF clamps silently rather than rejecting [2].
  - Its proposed top review, "highest rating, then the longest body, then newest", has length
    collisions in the real data [35].
- `stack-decisions.md` §2a counts "8 releases in 2026" and 3 security fixes. PyPI shows **7** 2026
  releases (3.17.0, 3.17.1, 3.17.2, 3.18.0, 3.18.1, 3.18.2, 3.18.3) and GitHub lists **5** 2026
  advisories (two in 3.17.2, three in 3.18.2) [10][13].

## Conflicts with accepted decisions

None of these change a decision; they correct facts in the records.

- **ADR 0001, Context:** "three ORM SQL-injection CVEs reached through `order_by` and aliases". One of
  the three (CVE-2026-1207) is a PostGIS raster band index [14]. The decision (allow-lists) still holds.
- **ADR 0001, Consequences:** "5.2.19 (a GIS-only security fix)". 5.2.19 fixes five CVEs, and two aren't
  GIS: CVE-2026-108147 (MultiPartParser memory) and CVE-2026-113593 (cache keys for empty vs missing
  `Vary` headers) [16]. Both matter here only if multipart parsing or `cache_page` is on; §6 and §8
  recommend neither.
- **ADR 0001, Decision:** the floor `Django>=5.2.8` admits 5.2.8–5.2.10, which lack the February fixes
  [14]. The lockfile is what actually protects. Consider raising the floor to the locked patch (5.2.18
  today, 5.2.19 once it clears the cooldown on 2026-11-10).
- **ADR 0002, Options:** "8 releases in 2026, 3 security fixes in October". It's 7 releases and 5
  advisories in 2026 [10][13]. The `>=3.18.3` floor covers all of them.

## Not verified

- **Postgres 18 and Python 3.14.** The experiment ran on SQLite and Python 3.12. Not checked: the `Avg`
  return type through psycopg 3, the sliced-`Prefetch` SQL on Postgres (the docs say it's supported
  [18]), and `DISTINCT ON` (Postgres-only, not run).
- **DRF cursor pages after the first** on an annotated `HAVING` filter (only page 1 and the offset path
  ran).
- **Django's `condition()` decorator applied to a DRF `APIView` method.** DRF's `Request` proxies
  attributes to `HttpRequest`; untested.
- **Vite `server.proxy` with `changeOrigin`.** How it rewrites `Host` (and so DRF's absolute `next`
  links) during development; the docs show the option but don't spell out the header [31].
- **Docker published ports.** Whether gunicorn sees each client's address or the bridge gateway for
  every client (which would make per-IP throttles one shared bucket). Not tested: containers were out of
  scope.
- **No upstream DRF issue about RFC 9457** turned up. The search tool doesn't index GitHub search well
  [34].
- **django-filter's maintainer roster** beyond PyPI metadata and the repo owner.
- **Dates and IDs.** CVE IDs for the October DRF advisories are as GitHub lists them; OSV publication
  dates differ by a couple of weeks [10].

## Sources

1. DRF 3.18.3 `rest_framework/filters.py` (`OrderingFilter`): https://github.com/encode/django-rest-framework/blob/3.18.3/rest_framework/filters.py
2. DRF 3.18.3 `rest_framework/pagination.py`: https://github.com/encode/django-rest-framework/blob/3.18.3/rest_framework/pagination.py
3. DRF 3.18.3 pagination guide: https://github.com/encode/django-rest-framework/blob/3.18.3/docs/api-guide/pagination.md (also via Context7 `/encode/django-rest-framework/3.18.3`)
4. DRF 3.18.3 filtering guide: https://github.com/encode/django-rest-framework/blob/3.18.3/docs/api-guide/filtering.md
5. DRF 3.18.3 throttling guide and source: https://github.com/encode/django-rest-framework/blob/3.18.3/docs/api-guide/throttling.md · https://github.com/encode/django-rest-framework/blob/3.18.3/rest_framework/throttling.py
6. DRF 3.18.3 settings guide: https://github.com/encode/django-rest-framework/blob/3.18.3/docs/api-guide/settings.md
7. DRF 3.18.3 `views.py` (`exception_handler`, `initial`, `permission_denied`) and `request.py` (`_authenticate`): https://github.com/encode/django-rest-framework/blob/3.18.3/rest_framework/views.py · https://github.com/encode/django-rest-framework/blob/3.18.3/rest_framework/request.py
8. DRF 3.18.3 `fields.py` (`CharField` validators, `ListField.get_value`): https://github.com/encode/django-rest-framework/blob/3.18.3/rest_framework/fields.py
9. DRF release notes, 3.17.0–3.18.3 (2026-03-18 to 2026-10-06): https://github.com/encode/django-rest-framework/blob/3.18.3/docs/community/release-notes.md
10. DRF security advisories (GitHub repo API, fetched 2026-11-09) and OSV: https://github.com/encode/django-rest-framework/security/advisories · https://osv.dev/list?ecosystem=PyPI&q=djangorestframework
11. GHSA-3547-9m27-7rxg (JSONParser codec, fixed 3.18.2): https://github.com/advisories/GHSA-3547-9m27-7rxg
12. DRF 3.18.3 browsable API template `base.html`: https://github.com/encode/django-rest-framework/blob/3.18.3/rest_framework/templates/rest_framework/base.html
13. PyPI JSON metadata, fetched 2026-11-09: djangorestframework, django-filter, django-cors-headers, pytest-django, drf-standardized-errors, djangorestframework-camel-case (`https://pypi.org/pypi/<name>/json`)
14. Django 5.2.11 release notes (2026-02-03): https://docs.djangoproject.com/en/5.2/releases/5.2.11/
15. Django security releases, 2026-02-03: https://www.djangoproject.com/weblog/2026/feb/03/security-releases/
16. Django 5.2.12–5.2.19 release notes (2026-03-03 to 2026-11-03): https://docs.djangoproject.com/en/5.2/releases/5.2.14/ · …/5.2.15/ · …/5.2.16/ · …/5.2.18/ · …/5.2.19/
17. Django 5.2 QuerySet API (`prefetch_related`, `Prefetch`, `distinct(*fields)`): https://docs.djangoproject.com/en/5.2/ref/models/querysets/ (via Context7 `/websites/djangoproject_en/5.2`)
18. Django 4.2 release notes ("`Prefetch` objects with sliced querysets"): https://docs.djangoproject.com/en/5.2/releases/4.2/
19. Django 5.2 conditional view processing and `views/decorators/http.py`: https://docs.djangoproject.com/en/5.2/topics/conditional-view-processing/ · https://github.com/django/django/blob/stable/5.2.x/django/views/decorators/http.py
20. Django 5.2 `middleware/http.py` (`ConditionalGetMiddleware`): https://github.com/django/django/blob/stable/5.2.x/django/middleware/http.py
21. Django 5.2 expressions (`nulls_last`), database functions (`Round`, `JSONObject`), `GeneratedField`: https://docs.djangoproject.com/en/5.2/ref/models/expressions/ · https://docs.djangoproject.com/en/5.2/ref/models/database-functions/ · https://docs.djangoproject.com/en/5.2/ref/models/fields/#generatedfield
22. PostgreSQL 18, Sorting Rows: https://www.postgresql.org/docs/18/queries-order.html
23. PostgreSQL wiki, Slow Counting: https://wiki.postgresql.org/wiki/Slow_Counting
24. django-filter repo (`CHANGES.rst` to 26.2, `tox.ini`, `django_filters/filters.py`, `rest_framework/backends.py`): https://github.com/carltongibson/django-filter
25. GHSA-x7gm-rfgv-w973 (django-filter, 2020): https://github.com/advisories/GHSA-x7gm-rfgv-w973
26. RFC 9457, Problem Details for HTTP APIs (July 2023): https://www.rfc-editor.org/rfc/rfc9457
27. RFC 9110, HTTP Semantics (§13.1.1, §15.5.2, §15.5.4): https://www.rfc-editor.org/rfc/rfc9110
28. RFC 6585 (§3, 428 Precondition Required): https://www.rfc-editor.org/rfc/rfc6585
29. RFC 6750, Bearer Token Usage (§3, §3.1): https://www.rfc-editor.org/rfc/rfc6750
30. pytest-django 4.14.0 helpers (`django_assert_num_queries`): https://github.com/pytest-dev/pytest-django/blob/v4.14.0/docs/helpers.rst
31. Vite 8.3.5 server options (`server.proxy`): https://github.com/vitejs/vite/blob/v8.3.5/docs/config/server-options.md (via Context7 `/vitejs/vite/v8.3.5`)
32. Zod 4.6.7 API (`z.object` strips unknown keys; `z.strictObject`, `z.looseObject`): https://github.com/colinhacks/zod/blob/v4.6.7/packages/docs/content/api.mdx (via Context7)
33. django-stubs README (`WithAnnotations`): https://github.com/typeddjango/django-stubs#readme
34. drf-problems (RFC 7807), found via web search: https://pypi.org/project/drf-problems/
35. Local verification, 2026-11-09: parsing of `db/dump.sql`; a throwaway script on Django 5.2.18 + DRF 3.18.3 + nh3 0.3.7 (uv, `--exclude-newer 2026-11-02`), Python 3.12, SQLite in memory, run outside the repo. It covered `OrderingFilter` terms, the `COUNT` SQL, invalid pages, `Subquery` vs sliced `Prefetch` SQL, unknown PATCH fields, 401 vs 403, a forged cursor, M2M aggregate inflation, and nh3 text output.
