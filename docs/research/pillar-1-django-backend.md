# Pillar 1: Django Backend (models, WP import, server-rendered pages)

Date: 2026-11-09

Scope: implementation-level research for Pillar 1 of CHALLENGE.md: the relational model, the re-runnable WordPress import, and the three server-rendered pages. It covers "Decisions you will defend live" questions 1–3. It goes deeper than `best-practices-2026.md` §4 and corrects it where the data disagrees. Every number about the data was measured from `db/dump.sql` with a throwaway stdlib parser (no containers were started). Accepted ADRs are taken as given. Design decisions stay with the user, so each topic ends with a **Recommendation**, not a decision.

> Confidence notes. Sources are official docs, specs, source code, changelogs and advisory databases. Nothing here is marked *(secondary)* because no vendor blog or news source was needed. "Tested" means I ran it in a throwaway environment outside the repo (Python 3.14, Django 5.2.18 or nh3 0.3.7, resolved with uv `--exclude-newer "7 days"`). Context7 answered the Django, PyMySQL, nh3 and DRF API questions. The web answered security advisories, MariaDB, PostgreSQL and WordPress questions, because Context7 doesn't index advisories or those docs at the needed depth.

---

## Key findings

1. **The data is small and clean.** 5 brands, 60 reviews (exactly 12 per brand), 5 industries (exactly 1 per brand), 9 users (1 admin, 8 subscribers who wrote every review). Every brand and review is `publish`. The dump holds no revisions, auto-drafts or trash, and only one draft (a page) [44].
2. **The ACF `average_rating` is wrong for 4 of 5 brands**, always too high, by 0.17 to 0.82. Only SwiftStream matches. Showing the computed value reorders the homepage "Featured Brands" and drops Acme from 4 stars to 3 [44].
3. **Brands have 10 postmeta rows, not ~30.** That's 4 ACF values, 4 ACF field-key pointers and 2 Yoast keys. Reviews have 8. Yoast's 53-column `wp_yoast_indexable` table is Yoast's own derived cache of the same data. Don't import it [44].
4. **`post_excerpt` is empty for every brand.** The theme builds the card text from the first 22 words of the stripped body. That "short description" is also the field the editor's `PATCH` changes (Pillar 5), so a re-import must never overwrite it. Django 5.0+ `create_defaults` does exactly this [1][44].
5. **The HTML is trivially clean.** All 65 bodies are single-line `<p>` paragraphs with no attributes, no Gutenberg comments, no shortcodes and no newlines. `wpautop` is a no-op on this data. nh3 0.3.7 changed 1 body of 65 (`AT&T` became `AT&amp;T`, which renders the same) and is idempotent (tested) [27][44].
6. **Reviewer name maps 1:1 to `post_author`, but location doesn't.** Each user appears with 2–4 different locations, so location belongs to the review, not the person. Keying `Reviewer` on the WP user ID removes any ordering dependency on the auth-service import [44].
7. **All seven Django ORM SQL-injection CVEs of 2025–26 share one trigger:** attacker-controlled dictionary keys expanded into `**kwargs`. In the importer, postmeta keys are that kind of input. ADR 0001's floor `Django>=5.2.8` still admits a release vulnerable to CVE-2025-13372, which is PostgreSQL-specific [17][20].
8. **Django 5.2.19 is not GIS-only** (contrary to ADR 0001's wording). Its `MultiPartParser` memory-exhaustion fix is reachable through DRF's default parsers. A JSON-only parser on the `PATCH` endpoint closes that path for good [19][43].
9. **Django's bulk upsert always rewrites every row,** and WordPress doesn't bump `post_modified` when postmeta changes. A per-row content hash gives true no-op re-runs and honest created/updated/unchanged counts [15][32][38].
10. **"100x" is only ~7,100 posts and ~53,200 meta rows.** One transaction works. For reading, keyset pagination inside one MariaDB consistent snapshot beats PyMySQL's `SSCursor`, which blocks the connection while it streams and risks the server's 60 s `net_write_timeout` [23][28][29].
11. **`URLField` validators don't run on `save()` or `bulk_create()`,** and the default `URLValidator` allows `ftp`. CVE-2026-15920 (admin XSS through a dangerous `URLField` scheme) shows why `website_url` needs an http/https check at import plus a DB check constraint [11][15][18].
12. **Pages are cheap and WP-compatible.** `APPEND_SLASH` gives the same 301 WP gives. Each required page needs 1–2 queries. The WP templates carry 3 inline `style=""` attributes on the required pages; a strict CSP style policy would block them [15][42][44].

---

## 1. Facts from the data

Method: parse each `INSERT` row of `db/dump.sql` (one row per line, from `mariadb-dump --skip-extended-insert`, see the Makefile) into JSON. Then count with stdlib Python. Password hashes were never printed [44].

### Counts and statuses

| What | Measured | Import? |
|---|---|---|
| `wp_posts` rows | 71 | |
| `brand` / `publish` | 5 (IDs 7–11) | Yes |
| `review` / `publish` | 60 (IDs 12–71) | Yes |
| `page` / `publish` | 4 (Sample Page, Home, About, Contact) | No (not in the domain) |
| `page` / `draft` | 1 (Privacy Policy) | No |
| `post` / `publish` | 1 ("Hello world!") | No |
| Revisions (`inherit`), `auto-draft`, `trash`, `future`, `private`, `pending` | **0** | n/a |
| Password-protected posts (`post_password` ≠ '') | 0 | Flag if ever seen |
| Industries (`taxonomy = 'industry'`) | 5: insurance, finance, home-services, telecom, retail | Yes |
| Industries per brand | exactly 1 each | |
| Users | 9: `admin` (administrator) + 8 subscribers | Reviewers only (8) |
| Comments | 1, on "Hello world!" | No (out of scope) |

The import should select `post_type IN ('brand','review')` and decide on status explicitly (section 6). Revisions have `post_type = 'revision'`, so a post-type filter already excludes them. Auto-drafts keep the CPT's `post_type`, so the status filter must exclude them.

### Relationships

- **Review → brand:** postmeta `brand` holds the brand's post ID as a string. All 60 point to an existing brand. ACF declares it `post_object`, `return_format: id`, `required` (`acf-fields.php`) [44].
- **Brand → industry:** `wp_term_relationships.term_taxonomy_id` → `wp_term_taxonomy` → `wp_terms`. Here `term_id` equals `term_taxonomy_id` by coincidence. Join through `term_taxonomy_id` and key on `term_id` [44].
- **Review → user:** `post_author` = 2…9. Brands and pages have `post_author = 0`. The admin wrote nothing [44].
- **Duplicate meta keys:** `wp_postmeta` has no unique `(post_id, meta_key)`, so WP allows duplicates. None exist here. If they appear, take the lowest `meta_id`: WP loads meta `ORDER BY meta_id ASC` and `get_post_meta(…, true)` returns the first [38][44].

### Ratings and the stored average

Review `rating` is stored as a string. Values are integers 1–5, no blanks: 1 ×1, 2 ×13, 3 ×14, 4 ×13, 5 ×19 [44].

| Brand | ACF `average_rating` | Mean of its 12 reviews | Rounded | Gap |
|---|---|---|---|---|
| UrbanRetail Co. | 4.4 | 3.667 | 3.7 | −0.73 |
| Acme Insurance Co. | 4.2 | 3.917 | 3.9 | −0.28 |
| PrimePath Bank | 4.0 | 3.833 | 3.8 | −0.17 |
| HomeShield Pro | 3.9 | 3.083 | 3.1 | −0.82 |
| SwiftStream Internet | 3.5 | 3.500 | 3.5 | 0 |

- Homepage order today (ACF, `meta_value_num DESC`): UrbanRetail, Acme, PrimePath, HomeShield, SwiftStream. With computed means: Acme, PrimePath, UrbanRetail, SwiftStream, HomeShield [44].
- `cr_stars()` floors the value, so Acme shows 4 full stars today and 3 with the computed mean (theme `functions.php`) [44].
- Yoast meta descriptions hard-code counts ("Read 12 independent customer reviews of Acme…"). That text goes stale as soon as a review is added [44].

### Reviewers

| `post_author` | `display_name` | `reviewer_name` (ACF) | Reviews | Distinct locations |
|---|---|---|---|---|
| 2 | Sarah K. | Sarah K. | 10 | 3 |
| 3 | Mike T. | Mike T. | 9 | 2 |
| 4 | Jenny W. | Jenny W. | 8 | 4 |
| 5 | David L. | David L. | 9 | 2 |
| 6 | Anna R. | Anna R. | 7 | 3 |
| 7 | Roberto G. | Roberto G. | 7 | 2 |
| 8 | Maya P. | Maya P. | 5 | 2 |
| 9 | Kenji O. | Kenji O. | 5 | 2 |

Password hashes: all 9 use WordPress 6.8+ bcrypt, prefix `$wp$2y$10$`, length 63. `$wp` marks a SHA-384 pre-hash before bcrypt [39][44]. That matters to Pillar 5, not here. The main app never needs `user_pass`, `user_email` or `user_login` (section 9).

### Permalinks and slugs

- `permalink_structure` = `/%postname%/`. `home` and `siteurl` = `http://localhost:8080`. Front page is a static page (`show_on_front = page`, `page_on_front = 4`) [44].
- CPT rewrite slugs are `brand` and `review`; the taxonomy's is `industry` (`cpt.php`). WP's rewrite rule is `brand/([^/]+)(?:/([0-9]+))?/?$`, so the slash is optional in matching and an extra numeric segment is a page number [44].
- All 65 brand/review slugs match `^[a-z0-9-]+$`. Max length 51 (column is `varchar(200)`). No duplicates even across post types. No unicode or percent-encoded slugs. One slug ends in digits, `online-portal-feels-like-2010`, but that comes from its title, not WP's `-2` de-duplication [44].
- `guid` equals the permalink for every brand and review [44].
- `post_date` equals `post_date_gmt` everywhere (`gmt_offset = 0`). `post_modified` equals `post_date` for every brand and review [44].

### Content shape

| | Brands (5) | Reviews (60) |
|---|---|---|
| Length (chars) | 703–820 | 181–481 |
| Tags used | `<p>` only (15) | `<p>` only (60) |
| Attributes | none | none |
| Gutenberg comments / shortcodes / newlines | 0 / 0 / 0 | 0 / 0 / 0 |
| `<script>`, `on*=`, `javascript:` | 0 | 0 |
| Entities / raw `&` | 0 | 1 raw `&` ("AT&T", review 59) |
| Non-ASCII | em dash ×2 | em dash ×15 |
| `post_excerpt` non-empty | 0 | 0 |

Only the default WP pages and post (IDs 1–3) contain Gutenberg block comments [44].

---

## 2. Relational model

### What the domain needs

Four tables, matching the challenge's nouns: `Industry`, `Brand`, `Review`, `Reviewer`. Each imported row carries its WordPress ID with a unique constraint, as the `django-lts` skill requires. Suggested fields:

**Brand**

| Field | Type | From | Why |
|---|---|---|---|
| `wp_id` | `PositiveBigIntegerField(unique=True, null=True)` | `ID` | Upsert key. NULL for rows born in Django. PostgreSQL unique constraints treat NULLs as distinct by default, so many NULLs are fine [46]. It must be a plain unique, not conditional, to work as an `ON CONFLICT` arbiter [32] |
| `name` | `CharField(200)` | `post_title` | Max measured 51 |
| `slug` | `SlugField(200, unique=True)` | `post_name` | Matches WP's `varchar(200)`; drives the URL |
| `industry` | `ForeignKey(Industry, PROTECT)` | term relationship | See the FK vs M2M choice below |
| `content_source` | `TextField` | `post_content` | Raw WP HTML, kept so content can be re-sanitized when the allow-list changes |
| `content_html` | `TextField` | sanitized `post_content` | What templates render (section 7) |
| `short_description` | `CharField(300, blank=True)` | `post_excerpt`, else derived | Card text. Editor-owned after creation (section 6) |
| `website_url` | `URLField(blank=True)` | `website_url` | http/https only, checked at import and by a DB constraint |
| `founded_year` | `PositiveSmallIntegerField(null=True)` | `founded_year` | Check 1800–2100 (the ACF min/max) |
| `headquarters` | `CharField(200, blank=True)` | `headquarters` | Shown on cards and the detail page |
| `legacy_average_rating` | `DecimalField(2, 1, null=True)` | ACF `average_rating` | Audit only. Check 0–5 |
| `average_rating`, `review_count` | `DecimalField(3, 2, null=True)`, `PositiveIntegerField(default=0)` | computed | Only if you choose to store them (section 3) |
| `seo_title`, `seo_description` | `CharField(blank=True)` | `_yoast_wpseo_*` | Section 5 |
| `status` | `CharField(choices=…)` | `post_status` | Lets a re-run unpublish (section 6) |
| `published_at`, `wp_modified_at` | `DateTimeField` | `post_date_gmt`, `post_modified_gmt` | Use the `_gmt` columns; store aware UTC |
| `wp_source_hash` | `CharField(64)` | computed | Skips unchanged rows on re-runs (section 6) |
| `created_at`, `updated_at` | `DateTimeField(db_default=Now())` | | DB-side default [2] |

**Review**: `wp_id`, `title`, `slug` (unique), `brand` (FK), `reviewer` (FK, `null=True`, `SET_NULL`), `reviewer_name` and `reviewer_location` (`CharField(100)`, the displayed snapshot; max measured 10 and 18), `rating` (`PositiveSmallIntegerField`, check 1–5), `content_source`, `content_html`, `status`, `published_at`, `wp_modified_at`, `wp_source_hash`.

**Industry**: `wp_term_id` (unique), `name` (`CharField(200)`), `slug` (`SlugField(200, unique=True)`).

**Reviewer**: section 4.

### Constraints and indexes

```python
class Meta:
    constraints = [
        models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_5"),
    ]
    indexes = [
        models.Index(fields=["brand", "-published_at", "-id"], name="review_brand_recent"),
        models.Index(fields=["-published_at", "-id"], name="review_recent"),
    ]
```

- **`condition=`, not `check=`.** `check` was deprecated in 5.1 in favor of `condition` [3][4]. The 5.2.18 signature takes both (tested [15]). Using `condition` now keeps the 6.2 LTS upgrade free.
- **Brand check constraints:** `founded_year` in 1800–2100 or NULL. `legacy_average_rating` and `average_rating` in 0–5 or NULL. `website_url = ''` or starts with `http://` or `https://`. A DB check catches every write path, including ones that skip `full_clean()` [11].
- **Indexes Pillar 2 will need:** the FK index on `brand.industry` (`ForeignKey.db_index` defaults to `True`, tested [15]); `(brand, -published_at, -id)` for the brand page and "top review"; and, if you store the aggregates, `(-average_rating, id)` and `(-review_count, id)` for the two sorts. Every sort ends in `id` (AGENTS.md).
- **`on_delete`:** `PROTECT` on `Review.brand` and `Brand.industry` makes deleting a brand with reviews an explicit decision, not a silent cascade. `SET_NULL` on `Review.reviewer`, because the review keeps its name snapshot.

### Django 5.0–5.2 features: use or avoid

| Feature | Verdict | Why |
|---|---|---|
| `db_default` | Use for `created_at` | DB-side defaults also apply to rows written outside the ORM. Can't reference other fields [2] |
| `Meta.constraints` with `condition=` | Use | Real DB integrity. `check=` is deprecated [3][4] |
| `GeneratedField` | Avoid for ratings | It can only reference fields in the same row and table, so it can't aggregate reviews. On PostgreSQL, Django 5.2 supports only stored generated columns [2] |
| `CompositePrimaryKey` | Avoid | `ForeignKey` can't target a composite PK. The workaround, `ForeignObject`, is an internal API outside the deprecation policy, so it's an LTS risk [6] |
| `update_or_create(create_defaults=…)` | Use | Separates create-only values from update values (section 6) [1] |
| `bulk_create(update_conflicts=True, …)` | Optional | Sets PKs on PostgreSQL since 5.0, but skips `save()` and signals [1][5] |
| `DEFAULT_AUTO_FIELD` | Set to `BigAutoField` | 5.2 doesn't default it (`django-lts` skill) |

### Industry: FK or many-to-many?

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| **FK `Brand.industry`** | None | None | Lowest. One join; filtering is `industry__slug=…` | WP's taxonomy allows several terms. A second industry later needs a migration to M2M |
| **M2M `Brand.industries`** | None | None | Higher. Filters need `distinct()`; the card needs "which industry to show"; Pillar 2 needs a prefetch | Solves a problem the data doesn't have. The theme itself shows only the first term (`$terms[0]` in `cr_brand_industry`) [44] |

**Recommendation:** FK. Make the importer fail loudly if a brand ever has 0 or more than 1 industry, rather than picking one silently.

**Defend it:** "Four tables with real FKs and check constraints. Every imported row carries a unique WP ID. Industry is an FK because every brand has exactly one and the theme only ever shows one. The importer fails loudly if that stops being true."

---

## 3. `average_rating`: store, derive, or both

The data: the stored ACF number disagrees with the reviews for 4 brands of 5 (section 1). In this app, reviews change only through the importer, because review submission is out of scope (CHALLENGE.md). That makes the importer the only writer of review data, which simplifies sync a lot.

### Options

| Option | Consistency | Performance at 100x (500 brands, 6,000 reviews) | Security / stability cost | Effort | Why it might lose |
|---|---|---|---|---|---|
| **A. Derive at query time** (`annotate(Avg, Count)`) | Always right | Fine for one brand. For the paginated list, sorting by an aggregate needs the full `GROUP BY` before `LIMIT` | None | Low | Every list request aggregates. The "top review" subquery stacks on top |
| **B. Denormalized columns, recomputed by one set-based `UPDATE` at the end of each import** | Right after every import; reviews have no other writer | Index scan for the sort | None | Low (one service function) | Drifts if a second review writer is ever added without calling the function |
| **C. Same columns kept by `post_save`/`post_delete` signals** | Fragile | Same as B | None | Medium | `bulk_create`, `QuerySet.update()` and bulk upserts skip signals [1][12], so the importer's fast path would bypass them |
| **D. PostgreSQL trigger** (`RunSQL`) | Strong, even for raw SQL | Same as B | Raw SQL in migrations to own and test | Medium | Logic hidden from Python readers; harder to explain line by line |
| **E. `GeneratedField`** | n/a | n/a | n/a | n/a | **Impossible**: it can't reference other rows or tables [2] |
| **F. Materialized view** + `REFRESH … CONCURRENTLY` | Stale until refresh | Good reads | `RunSQL` and an unmanaged model. `CONCURRENTLY` needs a unique column index, and every refresh recomputes everything [34] | High | Heavyweight for 500 rows; gains nothing over B |

**Keep WP's number too**, as `legacy_average_rating`, never shown by default. It's evidence for the call: "WP said 4.4; the reviews say 3.7."

**Two implementation details:**
- **Brands with no reviews:** store NULL, not 0. "Not rated" isn't "zero stars". PostgreSQL sorts NULLs **first** in `DESC` order by default [33], so the sort must use `F("average_rating").desc(nulls_last=True)`.
- **Joins:** `Avg` and `Count` over the same single relation are safe. Adding a second multi-valued join to the same `annotate()` inflates both, which Django's docs warn about [14].

**Recommendation:** B plus the legacy column: computed `average_rating` and `review_count`, refreshed by one service function at the end of each import, with WP's value kept for audit. Add a test (or a `--verify` flag) that compares the stored values with a fresh `annotate()` to catch drift. Whether the UI shows computed or legacy numbers is your product call. Computed changes what users see today (order and stars, section 1).

**Defend it:** "Reviews only change during import, so the importer recomputes the average in one set-based UPDATE at the end. It's always consistent and sorts on an index. I kept WP's stored number as a legacy column, because it was wrong for four of five brands and I wanted to show that, not hide it."

---

## 4. Reviewers when the auth service owns users

The data: 8 WP users wrote all 60 reviews. `reviewer_name` always equals the author's `display_name`, but `reviewer_location` varies per review for the same person. The review page also shows "Posted by <author>" (`the_author()` in `single-review.php`) [44]. AGENTS.md: the main app stores only an external user ID, never passwords or roles.

Nothing in scope needs to match a token to a `Reviewer` at request time. The only protected write is an editor changing a brand's short description. The link matters for display today and for features like "edit my review" later.

### Shape options

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| **A. `Reviewer` model** (external key + cached `display_name`) and an FK on `Review` | Little PII: display names only | Must handle users deleted upstream | Low | One more table |
| **B. Denormalized strings on `Review` only** | Least data | Loses "all reviews by this person" | Lowest | Can't tell two "Sarah K."s apart; no path to user-owned features |
| **C. Both** (A, plus `reviewer_name`/`reviewer_location` snapshots on `Review`) | As A | As A | Low | Duplicates the name. That's fine: ACF stores it per review and it's "what was displayed" |

### Which key links `Reviewer` to the auth service?

| Option | Coupling and import order | Why it might lose |
|---|---|---|
| **1. `wp_user_id` (unique) plus nullable `auth_user_id`**, linked later | None. Both importers read WP independently. The auth service also stores `wp_user_id`, so a later sync, or the first token seen, fills `auth_user_id` | Two IDs per person; the link is eventually consistent |
| **2. Auth service `sub` (random UUID)** | Auth import must run first. The main app then needs a mapping export or an API call, because it has no credentials for the auth DB (ADR 0006) | Ordering dependency and a cross-service data hand-off |
| **3. Deterministic `uuid5(namespace, f"wp-user:{id}")`** that both importers compute | None. Stdlib `uuid.uuid5` [40] | Ties the auth service's ID scheme to WP IDs. That's a Pillar 5/6 contract you'd have to own and explain |

**WP users with no auth account yet** (or ones the auth import skips): with options 1 or 3 the review imports anyway. The page shows the review's name snapshot, and "Posted by" uses the cached `display_name`. If the auth service later deletes the user, `SET_NULL` on `Review.reviewer` keeps the review readable.

**Recommendation:** shape C with key option 1. Create the 8 `Reviewer` rows from `wp_users.ID` and `display_name` only. The admin wrote nothing, so they get no row. This also lets the import grant the main app read access to just those two `wp_users` columns (section 9).

**Defend it:** "The auth service owns identity. The main app keeps a thin Reviewer row with the WP user ID and display name, so the content import never waits on the auth import. Location lives on the review, because the same person reviewed from different cities."

---

## 5. Postmeta triage

Correction to CHALLENGE.md's "~30 fields per brand": the dump has **10 postmeta rows per brand** and **8 per review** [44]. The 30-plus "fields" likely refers to Yoast's `wp_yoast_indexable` table: 53 columns, of which 16 are non-empty for brands, and it's derived from postmeta.

| Key | On | Rows | Example | Decision | Reason |
|---|---|---|---|---|---|
| `website_url` | brand | 5 | `https://acme-insurance.example.com` | **Column** `URLField` | Rendered as a link. Validate http/https (section 7) |
| `founded_year` | brand | 5 | `1985` | **Column** `PositiveSmallIntegerField` | Rendered. Typed and checked 1800–2100 |
| `headquarters` | brand | 5 | `Hartford, CT` | **Column** `CharField` | Rendered on cards and detail |
| `average_rating` | brand | 5 | `4.2` | **Column** `legacy_average_rating` | Audit; wrong for 4/5 (section 3) |
| `_website_url`, `_founded_year`, `_headquarters`, `_average_rating` | brand | 5 each | `field_brand_website_url` | **Drop** | ACF field-key pointers for its admin UI. The schema already lives in `acf-fields.php` |
| `_yoast_wpseo_title` | brand | 5 | `Acme Insurance Reviews - Auto, Home & Umbrella Coverage` | **Column** `seo_title` (or JSON) | Cheap `<title>` win. No `%%var%%` templates in the values (measured) |
| `_yoast_wpseo_metadesc` | brand | 5 | `Read 12 independent customer reviews of…` | **Column** `seo_description` (or JSON) | Meta description. Hard-coded counts go stale |
| `brand` | review | 60 | `7` | **FK** `Review.brand` | The relationship |
| `rating` | review | 60 | `5` | **Column** `PositiveSmallIntegerField` + check | Sorted, averaged, rendered |
| `reviewer_name` | review | 60 | `Sarah K.` | **Column** snapshot | What was displayed |
| `reviewer_location` | review | 60 | `Denver, CO` | **Column** snapshot | Varies per review |
| `_brand`, `_rating`, `_reviewer_name`, `_reviewer_location` | review | 60 each | `field_review_rating` | **Drop** | ACF pointers |
| `_wp_page_template` | page | 2 | `default` | **Drop** | Pages aren't imported |
| `wp_yoast_indexable` (table) | all | 76 | | **Drop** | Yoast's derived cache; title and description duplicate the postmeta |
| `wp_usermeta` (16 keys) | users | 135 | `wp_capabilities` | **Drop in the main app** | Roles belong to the auth service (Pillar 5) |

`wp_posts` columns also need triage. `post_excerpt` seeds `short_description` (empty everywhere, so derive it). `post_password` should make the importer skip and report the row (none today). `comment_status`, `ping_status`, `comment_count`, `menu_order`, `post_parent`, `guid`, `to_ping`, `pinged`, `post_content_filtered` and `post_mime_type` are dropped.

**SEO: columns or JSON?**

| Option | Cost | Why it might lose |
|---|---|---|
| Two `CharField`s | Typed, validated, trivially rendered | Yoast has more keys (OG, Twitter, robots); each needs a migration |
| `seo = JSONField(default=dict)` | Flexible | Untyped; needs a dataclass parser at the edge (ADR 0013) |

**Unknown keys:** with every key triaged, a raw snapshot (`wp_raw` JSON) adds storage and PII duplication for little gain. A cheaper LTS-minded guard: the importer holds an explicit "known and ignored" list, and any other key fails the run (or warns, in `--lenient` mode). A new key means WP's schema changed, which a human should see.

**Recommendation:** columns for the four ACF values, the two Yoast keys and the relationship. Drop the `_`-prefixed ACF pointers and the indexable table. Report unknown keys instead of storing a raw snapshot.

**Defend it:** "Every meta key the dump actually has went into a table: four typed columns, two SEO columns, the FK, and eight ACF pointer keys dropped because they only serve ACF's admin. Unknown keys stop the import, because a new key means WordPress changed and I want to know."

---

## 6. The import command

Accepted (ADR 0007): a `manage.py` command reads MariaDB through PyMySQL with a read-only user and upserts on WP IDs. Open here: how to read, parse, write, delete, lock and test.

### Reading MariaDB safely

- **Connection:** `pymysql.connect(host=…, user=…, password=…, database=…, charset="utf8mb4")`. 1.2.0 deprecated `db`/`passwd` in favor of `database`/`password`. PyMySQL's own changelog calls non-UTF-8 charsets legacy after a 1.2.1 charset-related SQL injection fix [22].
- **TLS:** since 1.2.0, PyMySQL uses TLS whenever the server offers it, and setting any SSL option makes TLS mandatory [22]. On compose's private network this is optional; across hosts, set `ssl_verify_cert` and `ssl_verify_identity`, which 1.2.4 tightened [22].
- **Parameters:** fixed SQL with `%s` placeholders only. **Until 1.2.4 clears the cooldown (2026-11-16 09:37 UTC [21]), pass only scalar parameters:** the 1.2.4 SQL-injection fix concerns `tuple`/`list`/`set` parameters (`WHERE post_id IN %s`) when `NO_BACKSLASH_ESCAPES` is set [22]. Range predicates (`BETWEEN %s AND %s`) avoid the issue entirely.
- **One consistent view:** run all reads inside `START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY` [28]. InnoDB's default isolation is `REPEATABLE-READ` [29], so posts, postmeta and terms come from the same moment even if an editor saves mid-import.

### Batching: keyset pagination or `SSCursor`

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| **Keyset pagination** (`WHERE post_type = %s AND ID > %s ORDER BY ID LIMIT %s`) with the default buffered cursor | None | Uses the PK index; resumable from the last ID | Low | One extra round trip per batch |
| **`SSCursor`** (unbuffered streaming) | None | Forward-only. The connection can't run another statement until the result is drained [23], so postmeta needs a second connection. If the Python side pauses (say, writing to Postgres) longer than the server's `net_write_timeout` (default 60 s [29]), the server aborts the write | Medium | Fragile exactly when the data is big |

Per batch, fetch the posts, then their postmeta with `WHERE post_id BETWEEN %s AND %s ORDER BY meta_id`. That's two queries per batch, scalar parameters only, and deterministic duplicate-key handling.

### Parsing into frozen dataclasses (ADR 0013)

```python
@dataclass(frozen=True, slots=True)
class WpReview:
    wp_id: int
    slug: str
    title: str
    content: str
    status: WpStatus            # Literal["publish", "draft", ...]
    published_at: datetime      # aware UTC from post_date_gmt
    author_wp_id: int | None
    brand_wp_id: int
    rating: int                 # 1..5, parsed from a string
    reviewer_name: str
    reviewer_location: str
```

- Parse functions raise a typed hierarchy (`WpRowError` → `MissingMeta`, `BadRating`, `UnknownBrand`, `BadSlug`, `UnsafeUrl`). The command decides per class whether to skip and report, or abort.
- **Never pass dict keys from WordPress into the ORM.** Write `Brand(name=row.name, …)` from the dataclass, never `Brand(**meta)` or `.filter(**meta)`. Every 2025–26 Django ORM SQL injection needed attacker-chosen keys expanded into `**kwargs` (section 9) [17][20].
- Zero dates (`0000-00-00 00:00:00`, the schema default of every `wp_posts` datetime column in the dump) must become `None`, not a crash.
- Slugs must match `^[a-z0-9-]+$`. Anything else fails the row, because Django's `slug` path converter is ASCII-only (section 8) [15].

### Writing: `update_or_create` or bulk upsert

| | `update_or_create` per row | `bulk_create(update_conflicts=True, unique_fields=["wp_id"], update_fields=[…])` |
|---|---|---|
| Queries | 2–3 per row | 1 per batch [1] |
| Created vs updated | Returns `(obj, created)` [1] | Not reported. You need a pre-read of existing IDs |
| `save()`, signals, `auto_now` | Run | Skipped [1][12] |
| Unchanged rows | Rewritten | Rewritten. Django 5.2's signature has no `WHERE` for `DO UPDATE` (tested [15]) |
| Same `wp_id` twice in one batch | Fine | PostgreSQL cardinality-violation error [32]. De-duplicate first |
| Arbiter | n/a | Needs a plain unique on `wp_id`; partial indexes aren't inferred [32] |
| Create-only fields | `create_defaults={…}` [1] | Leave them out of `update_fields` |

**True no-op re-runs.** WordPress doesn't bump `post_modified` when postmeta changes: `update_post_meta()` writes only the meta table [38]. The seed script sets every ACF value with `wp post meta update` (`scripts/seed.sh`). So `wp_modified_at` can't detect changes. Instead, hash the canonical parsed row (stdlib `hashlib.sha256` over a sorted JSON dump of the dataclass) and store it as `wp_source_hash`. One `values_list("wp_id", "wp_source_hash")` query per batch then sorts rows into created, updated and unchanged. Unchanged rows aren't written at all.

**Editor-owned fields.** `short_description` is set from the excerpt (or the first 22 words of the body, like the theme) **only on create**. With `update_or_create` it goes in `create_defaults`; with a bulk upsert it's left out of `update_fields`. Otherwise every re-import would erase the editor's `PATCH`.

### Transactions, dry-run, locking

- **One `transaction.atomic()` per run.** At this size (and at 100x) all-or-nothing is simplest: a failed run leaves the old data untouched.
- **`--dry-run`:** run the same code, then `transaction.set_rollback(True)` [13]. Constraints and FKs are exercised for real, then discarded. Print created/updated/unchanged/skipped/unpublished counts either way.
- **No concurrent runs:** take `pg_try_advisory_xact_lock(<constant>)` as the first statement inside the atomic block. It returns `false` immediately if another run holds it, and releases at commit or rollback [35]. It's one parameter-free raw SQL statement. Alternatives: an `ImportRun` row locked with `select_for_update(nowait=True)`, which doubles as an audit log; or `MAX_USER_CONNECTIONS 1` on the MariaDB import user [30].
- **Order:** industries → reviewers → brands → reviews → recompute brand stats (section 3) → handle missing rows.

### Rows deleted or unpublished in WP since the last run

After a full scan, `seen_ids` holds every WP ID read for the type. Rows with `wp_id` set but not in `seen_ids` vanished from WP (force-deleted). Rows read with a non-`publish` status were unpublished or trashed.

| Option | Why it might lose |
|---|---|
| **Mark `status` and hide** (views filter on `publish`) | Keeps dead rows. Needs a periodic purge |
| **Hard delete** | `PROTECT` blocks deleting a brand that still has reviews. Irreversible |
| **Report only** | WP-deleted content stays public on the new site, which is wrong |

**Recommendation:** read all statuses except `auto-draft` and store them; views show only `publish`; vanished rows get `status = "removed"` plus a line in the report. Hard delete only behind an explicit `--prune` flag.

### Scale: what 100x actually means

100x this dump is ~7,100 posts and ~53,200 meta rows. That fits in memory, and one transaction is fine. Batching, keyset reads and hash-skipping are about doing it right, not about surviving this number. At 10,000x the things that would change: per-type transactions with a checkpoint table (resume from the last committed `wp_id`), keeping the MariaDB snapshot short (a long consistent read holds undo history), and running the stats recompute once at the end, not per batch. On the Postgres side, a `--verify` pass over many rows can use `QuerySet.iterator(chunk_size=…)`, which streams through server-side cursors on PostgreSQL 14+ (the versions Django 5.2 supports) [10].

### Testing the importer

- **Parsers:** table-driven unit tests: rating `"6"`, `""` and `"4.5"`; missing `brand` meta; `brand` pointing at a non-brand; zero dates; a unicode slug; `javascript:` and `ftp:` in `website_url`; duplicate meta keys.
- **Importer against a fake source:** define a `WpSource` Protocol (ADR 0013) with an in-memory implementation. Then on the test Postgres: run twice and assert identical counts with no new rows; change one title and assert 1 updated, 64 unchanged; drop one row and assert it's marked removed; edit `short_description` and assert it survives a re-import.
- **One integration test** against MariaDB loaded from `dump.sql` (the existing compose `db` service). Assert 5/60/5/8 and the four average mismatches.
- `TestCase.assertNumQueries` for the pages (section 8) is built in, so no new dependency is needed.

**Recommendation:** keyset reads in one consistent snapshot; parse to frozen dataclasses; write with `update_or_create(create_defaults=…)` (65 rows don't justify the bulk path's caveats), skipping rows whose hash is unchanged. One atomic run with an advisory lock, `--dry-run` via `set_rollback`, removals marked and reported. Switch to bulk upsert only when a measured run says it's slow.

**Defend it:** "It's re-runnable because every row upserts on its WP ID, and unchanged rows are skipped by a content hash, so a second run writes nothing and says so. It runs in one transaction behind an advisory lock, and dry-run is the same code rolled back. At 100x it's 7,000 posts, still one transaction. What I'd change at real scale is checkpointing and bulk upserts, not the design."

---

## 7. WordPress HTML into Django pages

### What WordPress does to this content

- `the_content()` (both single templates) runs `do_blocks`, `wptexturize`, `convert_smilies`, `wpautop`, `shortcode_unautop`, `do_shortcode` and `wp_filter_content_tags` [38].
- The brand page renders each review body with `wp_kses_post(wpautop(...))` (`single-brand.php`) [44].
- Cards use `esc_html(wp_trim_words(wp_strip_all_tags(content), N))` with N = 22 (brands) or 24 (reviews). `wp_trim_words` appends `&hellip;` when it cuts [38][44].
- `wpautop` turns blank-line gaps into `<p>` and single newlines into `<br />`, around block tags; it's ~160 lines of PHP regex [37].

On this dump, `do_blocks`, shortcodes and `wpautop` are all no-ops: no block comments, no shortcodes, no newlines, and every body is already wrapped in `<p>` (section 1). `wptexturize` only changes typography (straight quotes to curly), which is out of scope ("not pixel-matching").

### Where to sanitize

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| **At import** (store `content_html`) | Safe by default: templates only ever see cleaned HTML | Allow-list changes need a re-sanitize run | Low | Without the raw source, a stricter allow-list can't be re-applied |
| **At render** | Always the current allow-list | Sanitizer cost per request; a forgotten filter means XSS | Low | One template that skips it is stored XSS |
| **Both stores: `content_source` (raw) + `content_html` (cleaned at import)** | Safe by default and re-cleanable | One extra column | Low | Stores raw, untrusted HTML. Fine, as long as nothing renders it |

### The nh3 allow-list (ADR 0004)

```python
CLEANER = nh3.Cleaner(
    tags={"p", "br", "strong", "em", "b", "i", "ul", "ol", "li", "blockquote", "a", "h2", "h3", "h4", "code", "pre"},
    attributes={"a": {"href", "title"}},
    url_schemes={"http", "https", "mailto"},
    link_rel="nofollow noopener noreferrer ugc",
)
```

`Cleaner` is reusable; `strip_comments` defaults to `True` (it removes Gutenberg comments), and `clean_content_tags` drops a tag *and* its contents [24]. Never add `style`, `svg`, `math` or `animate*` (AGENTS.md). The open ammonia advisories that nh3 0.3.7 still bundles need SVG animation tags or CSS `url()` in `style` [25][26].

Tested on the dump with this allow-list [27]: 64 of 65 bodies come out byte-identical; review 59 turns `AT&T` into `AT&amp;T`. Re-cleaning the output changes nothing. Probes: `<script>` is removed with its content; `<img onerror>` disappears; `javascript:` hrefs are dropped (`rel` stays); `style` attributes are stripped; an SVG `<animate>` payload is removed. **Shortcodes and raw newlines pass through untouched**, so nh3 alone isn't a `wpautop`.

### `wpautop`: port, minimal, or nothing

| Option | Why it might lose |
|---|---|
| **Port `wpautop`** (~160 lines of regex [37]) | Lots of code you must explain line by line, for data that doesn't need it |
| **Minimal stdlib fallback**: if the source has no block-level tag, split on blank lines and wrap each chunk in `<p>`; single newlines become `<br>`; then nh3 | Not identical for mixed HTML and text |
| **Nothing, plus an importer check** that warns when a body contains a newline or `[shortcode]` | Future content would render as one paragraph until someone acts |

**Recommendation:** the minimal fallback behind a test, plus the importer warning for shortcodes. It handles plausible new content at ~10 lines.

### Excerpts and card text

Derive plain text at import: `nh3.clean(html, tags=set())`, then `html.unescape()`. Store plain text and let autoescape handle output. Truncate with `{{ text|truncatewords:22 }}` (plain-text `Truncator.words`, `html=False` [15]). Avoid `truncatewords_html` and `Truncator(..., html=True)` for imported content: those were the target of CVE-2026-1285, a DoS through many unmatched end tags, fixed in 5.2.11 [17].

### Autoescape and `|safe` discipline

- Autoescape stays on. The only HTML that reaches a template is `content_html`, through one model property that returns `SafeString`, with a comment pointing at the sanitizer.
- Ruff's S308 flags `mark_safe()` in Python but **not** `|safe` in templates [45]. Add a tiny test that scans `templates/` for `|safe` and `{% autoescape off %}` outside an allow-list.
- **`website_url` is an XSS vector Django won't catch for you.** Model validators don't run on `save()` [11]; `URLValidator`'s defaults allow `ftp`/`ftps` [15]; and CVE-2026-15920 (fixed 5.2.17) was the admin rendering a stored `URLField` with a dangerous scheme as a link [18]. Validate with `URLValidator(schemes=["http", "https"])` at import, add the DB check from section 2, and keep `rel="nofollow noopener"` on the link as the theme does.

**Recommendation:** store raw and cleaned HTML; sanitize once at import with the allow-list above; minimal `wpautop` fallback; plain-text excerpts; one `SafeString` property; a template-scan test.

**Defend it:** "Content is sanitized once at import with nh3 and an explicit allow-list, and I keep the raw source so I can re-clean if the list changes. Templates never use `|safe`; a test enforces it. URLs are checked for http or https, because Django doesn't validate URLField on save."

---

## 8. Server-rendered pages

### URLs that match WP's permalinks

```python
urlpatterns = [
    path("", views.home, name="home"),
    path("brand/<slug:slug>/", views.brand_detail, name="brand-detail"),
    path("review/<slug:slug>/", views.review_detail, name="review-detail"),
]
```

- **Trailing slash:** WP's permalinks end in `/` (`/%postname%/`) [44]. With `CommonMiddleware` and `APPEND_SLASH = True` (the default), `/brand/acme-insurance` gets a redirect to the slash version [7][8]. The redirect class is `HttpResponsePermanentRedirect`, a 301 (tested on 5.2.18 [15]).
- **Slug converter:** `slug` matches `[-a-zA-Z0-9_]+` (tested [15]), which covers every slug in the dump. A future unicode slug would 404, which is why the importer rejects non-ASCII slugs (section 6).
- **Case:** WP's tables use `utf8mb4_unicode_520_ci`, a case-insensitive collation [44], so WP probably resolves `/brand/Acme-Insurance/`. PostgreSQL slug lookups are case-sensitive and will 404. Matching WP's canonical-redirect behavior is optional (see Not verified).
- **Drafts and removed rows:** a `published()` queryset method plus `get_object_or_404(...)`. The `status` field makes this one filter.
- **Out of scope but routed by WP:** `/brand/<slug>/<n>/` (page number), `feed/`, `embed/`, `trackback/` [44]. Django returns 404 for these.
- **Links in the header** (`header.php`): `/brand/`, `/review/`, `/about/` [44]. These pages aren't required, but a nav that 404s looks broken. `/brand/` is the natural home for `<BrandList />`; `/review/` can be a simple paginated list; `/about/` a static template.

### What each page renders, and its query count

| Page | WordPress source | Django query | Queries |
|---|---|---|---|
| Home: hero | Static text in `front-page.php`. The "Home" page's own content is **not** rendered [44] | none | 0 |
| Home: Featured Brands | 6 brands by ACF `average_rating DESC` | `Brand.objects.published().select_related("industry").order_by(F("average_rating").desc(nulls_last=True), "id")[:6]` | 1 |
| Home: Recent Reviews | 6 newest reviews (`get_posts` defaults: `publish`, `date DESC` [36]) | `Review.objects.published().select_related("brand").order_by("-published_at", "-id")[:6]` | 1 |
| Brand detail | Brand, industry, stars, HQ/founded/website, body, all reviews newest first (capped at 100) | brand + industry; reviews + reviewer | 2 |
| Review detail | Review, brand link, stars, name/location/date, "Posted by" | review + brand + reviewer | 1 |

- WP's brand page fetches at most 100 reviews and shows `count($reviews)` as the total (`cr_get_reviews_for_brand($brand_id, 100)`) [44], so at 100x it would show "100 reviews". Use `review_count` for the total, and paginate the list if a brand passes ~50.
- Lock these counts in with `assertNumQueries` so an N+1 can't creep in (AGENTS.md).

### Class-based or function views

| Option | Why it might lose |
|---|---|
| **Function views** (`get_object_or_404`, `render`) | Slightly more code per view |
| **`DetailView` with `get_queryset()`** | Behavior lives in inherited methods you must explain on the call |

**Recommendation:** function views. Three short views are easy to read top to bottom and to defend line by line, which the live session tests.

### Mounting `<BrandList />` into a Django page

- The template renders a mount point with its configuration as data: `<div id="brand-list" data-endpoint="{% url 'api:brands' %}"></div>`. Any initial data goes through `{{ data|json_script:"brand-list-data" }}`, which escapes `<`, `>` and `&` and works under a strict CSP [9].
- **Asset URLs** (shared with Pillar 3):

| Option | Cost | Why it might lose |
|---|---|---|
| Read Vite's `.vite/manifest.json` with a ~20-line template tag (stdlib `json`) [41] | Own code to test | Must follow `imports` to collect CSS [41] |
| Fixed entry filenames from Vite; let Django's manifest storage add hashes | Least code | Relies on a single, non-split bundle |
| `django-vite` package | New dependency to vet (not evaluated here) | Attack surface for ~20 lines of value |

### CSP fit (ADR 0005)

- The bundle loads as `<script type="module" src="…">` from `'self'`, and `json_script` emits a non-executable data block, so `script-src 'self'` holds [9].
- **Inline styles:** the required templates carry 3 `style=""` attributes (`front-page.php`, `single-brand.php`, `single-review.php`); all templates together carry 7 [44]. If the policy gains `default-src 'self'` or `style-src 'self'`, browsers block them: `style-src-attr` falls back to `style-src`, then `default-src` [42]. Port them to BEM classes in the SCSS tree (Pillar 4), not to `'unsafe-inline'`.
- Vite's dev server with React needs an inline refresh preamble [41]. That's dev-only; keep CSP report-only in development, or exempt the dev origin.

**Defend it:** "URLs are the same paths as WP's permalinks, including the trailing slash: Django's APPEND_SLASH issues the same 301. Drafts 404 through one published() filter. Each page is one or two queries, and tests pin those counts."

---

## 9. Security specifics

### Django ORM SQL injection, 2025–26

| CVE | Fixed in 5.2.x | API | Trigger |
|---|---|---|---|
| CVE-2025-57833 | 5.2.6 | `FilteredRelation` aliases via `annotate()`/`alias()` | Crafted dict, `**kwargs` [20] |
| CVE-2025-59681 | 5.2.7 | `annotate()`/`alias()`/`aggregate()`/`extra()` aliases (MySQL/MariaDB) | Crafted dict, `**kwargs` [20] |
| CVE-2025-64459 (critical) | 5.2.8 | `filter()`/`exclude()`/`get()`/`Q()` via `_connector` | Crafted dict, `**kwargs` [20] |
| CVE-2025-13372 | **5.2.9** | `FilteredRelation` aliases **on PostgreSQL** | Crafted dict, `**kwargs` [20] |
| CVE-2026-1287 | 5.2.11 | `FilteredRelation` aliases, control characters | Crafted dict, `**kwargs` [17] |
| CVE-2026-1312 | 5.2.11 | `order_by()` aliases with periods, with `FilteredRelation` | Crafted dict, `**kwargs` [17] |
| CVE-2026-1207 | 5.2.11 | PostGIS raster lookups | GIS only [17] |

- **The lesson is broader than "allow-list `order_by`".** Never expand a dict with outside-controlled keys into any QuerySet method: not `request.GET` in views, and not postmeta keys in the importer.
- **ADR 0001's floor `>=5.2.8` admits 5.2.8,** which is vulnerable to CVE-2025-13372 (PostgreSQL) and the February 2026 trio. `uv.lock` resolves 5.2.18 today, but the floor is the last line if the lock is ever regenerated carelessly (see Conflicts).

### Django 5.2.19 (2026-11-03): what it means here

5.2.19 patches five CVEs on the 5.2 branch: two GIS SSRFs, GIS log injection, `MultiPartParser` memory exhaustion via base64 uploads, and private-data exposure through `Vary` cache keys [19]. It clears the cooldown on 2026-11-10 at 15:22 UTC [21].

- **`MultiPartParser`:** DRF's default parsers are JSON, Form and MultiPart [43], and DRF's `MultiPartParser` wraps Django's [43]. Set `DEFAULT_PARSER_CLASSES` to `JSONParser` only. The `PATCH` endpoint takes JSON anyway, so this removes the path now and shrinks attack surface after the upgrade.
- **Cache middleware:** seven of 2026's 5.2 advisories involve Django's cache middleware or cached pages (May ×2, June ×3, July, November) [16]. The pages cost 1–2 queries, so skip Django's page cache entirely. That's a security and stability win, not a sacrifice.

### XSS through imported content

Covered in section 7: sanitize at import with nh3; only `content_html` reaches templates; `website_url` is scheme-checked in Python and in the DB; card text is plain text.

### Secrets for the MariaDB credentials

- **Keep the WP database out of `DATABASES`.** The importer opens its own PyMySQL connection (ADR 0007). A second Django database alias would put WP credentials in the web process's settings and make the WP DB reachable from any code path.
- **Import-only credentials.** Run the importer as a separate compose service (`profiles: ["tools"]`, like the existing `wpcli`). Only that service gets `WP_IMPORT_DB_*`; the web container never does. Read the password from a file (Docker secrets under `/run/secrets/…`; the MariaDB image supports `_FILE` variables for its own setup [31]).
- **Least privilege at the database.** Create a dedicated user in an init script (init scripts run on the container's first start, in alphabetical order [31]). Grant table-level `SELECT` on `wp_posts`, `wp_postmeta`, `wp_terms`, `wp_term_taxonomy` and `wp_term_relationships`, and **column-level** `SELECT (ID, display_name) ON wp.wp_users`. With column privileges the user can't read other columns at all [30], so the main app's importer can never see password hashes or emails. Add `MAX_USER_CONNECTIONS 1`, and `REQUIRE SSL` if it crosses a network [30]. Don't reuse the `wp` account WordPress writes with.
- Log counts, never connection parameters. AGENTS.md: never read, print or commit `.env`.

**PyMySQL's record (attack-surface context):** four SQL-injection fixes since 2024: CVE-2024-36039 (<1.1.1), `callproc` names (1.1.3), multibyte-charset `bytes` escaping (1.2.1), and sequence escaping under `NO_BACKSLASH_ESCAPES` (1.2.4) [22]. 1.2.0 changed TLS and reconnect defaults [22]. All of these sit behind fixed, parameterized queries against a read-only user, which is why ADR 0007's wait for 1.2.4 is reasonable.

**Defend it:** "Every 2025–26 ORM injection needed outside keys expanded into kwargs, so nothing from WordPress or the request becomes a keyword name. The importer's DB user can read five tables and two columns of wp_users, so it can't leak a password hash even if it's compromised, and the web container never gets those credentials."

---

## Corrections to `best-practices-2026.md` §4

| §4 says | The data or source says |
|---|---|
| Postmeta "~30 fields per brand" (from CHALLENGE.md) | 10 per brand, 8 per review [44] |
| Drop `_edit_lock`, `_edit_last`, `_wp_*` | None of these exist on brands or reviews; only `_wp_page_template` on 2 pages [44] |
| Import order "industries → users → brands → reviews" | The main app imports no users. It imports `Reviewer` rows (WP ID + display name); users go to the auth service |
| At 100x, "stream in batches (server-side cursors)" | With PyMySQL/MariaDB, keyset pagination is safer: `SSCursor` blocks the connection and risks `net_write_timeout` [23][29] |
| `update_or_create` or `bulk_create(update_conflicts=…)` | Also: the bulk path always rewrites, can't report created vs updated, and fails on duplicate keys in a batch [15][32]. Neither path skips unchanged rows without a hash |
| Review HTML is risky "user content" | True in general (keep sanitizing), but in this dump every body is attribute-free `<p>` text [44] |

---

## Open decisions for the user

1. **Which average does the UI show, and how is it kept?** Options: derive per query; store and recompute at import end (+ legacy column); signals; trigger; materialized view. *Recommendation:* store and recompute at import end, keep `legacy_average_rating`, show the computed value. Note this changes today's homepage order and Acme's stars.
2. **Industry: FK or M2M?** *Recommendation:* FK, with an importer check that fails on anything other than exactly one industry.
3. **How does `Reviewer` link to the auth service?** Options: `wp_user_id` + nullable `auth_user_id`; auth `sub` (auth import first); deterministic UUIDv5. *Recommendation:* `wp_user_id` + nullable `auth_user_id`, plus name and location snapshots on `Review`.
4. **SEO: two columns or a JSON field? Keep a raw postmeta snapshot?** *Recommendation:* two columns; no snapshot; unknown meta keys fail the run.
5. **Write path: `update_or_create` or bulk upsert?** *Recommendation:* `update_or_create(create_defaults=…)` plus hash-skip now; bulk upsert when measured as slow.
6. **Rows deleted or unpublished in WP:** status flag, hard delete, or report only? *Recommendation:* `status` + report; hard delete only with `--prune`.
7. **Sanitize at import or render?** *Recommendation:* at import, storing both raw and cleaned HTML.
8. **Who owns `short_description` after an editor's `PATCH`?** *Recommendation:* Django owns it after creation; the importer sets it only on create.
9. **Function views or CBVs?** *Recommendation:* function views.
10. **Bundle URLs:** manifest-reading tag, fixed filenames, or `django-vite`? *Recommendation:* decide with Pillar 3; avoid the extra dependency.
11. **Build the header's `/brand/`, `/review/`, `/about/` pages?** *Recommendation:* yes, minimal; `/brand/` hosts `<BrandList />`.
12. **Raise the Django floor** (see Conflicts)? *Recommendation:* `>=5.2.18` now, `>=5.2.19` after 2026-11-10 15:22 UTC.

---

## Conflicts with accepted decisions

1. **ADR 0001 calls 5.2.19 "a GIS-only security fix".** It patches five CVEs on 5.2, two of them not GIS: `MultiPartParser` memory exhaustion (CVE-2026-108147) and `Vary` cache-key data exposure (CVE-2026-113593) [19]. The first is reachable through DRF's default parsers [43]. The decision to wait still holds, since it clears on 2026-11-10 at 15:22 UTC [21], but the stated reason is inaccurate. Suggested: a superseding note with the correct contents, and JSON-only DRF parsers in the meantime. (`cooldown-vs-security-fixes.md` calls it "Moderate and GIS-only": accurate for the one moderate, but the lows aren't GIS.)
2. **ADR 0001's floor `Django>=5.2.8,<5.3` admits known-vulnerable releases:** CVE-2025-13372 (PostgreSQL SQL injection, fixed 5.2.9) and CVE-2026-1287/1312 (fixed 5.2.11) [17][20]. 5.2.8 was chosen as the first release supporting Python 3.14, not for security. Suggested: raise the floor to the newest release past the cooldown (5.2.18, then 5.2.19).
3. **ADR 0004 (minor wording):** "The fix is merged upstream but unreleased." ammonia **released** the fixes in 4.1.7 (2026-10-11) and 4.1.8 (2026-10-17) [26]. nh3 0.3.7 and nh3's `main` still pin ammonia 4.1.4 [25], so the fix is unreleased *in nh3*. The revisit trigger ("nh3 releases the ammonia fix") stays correct.

---

## Not verified

- **Live WordPress behavior.** No containers were started, so WP wasn't observed answering `/brand/acme-insurance` (no slash) or a mixed-case slug. The 301-to-canonical claim for WP rests on its rewrite rules and collation, not a request.
- **The order `get_the_terms()` returns** when a brand has several industries. It only matters if you choose M2M.
- **Performance at 100x on PostgreSQL 18.** No database was run; claims are about query shape, not timings.
- **PyMySQL's handling of `0000-00-00` datetimes** (string, `None` or error). Parse defensively either way.
- **Whether the MariaDB image skips init scripts on an existing volume:** its docs imply it ("first start") but don't say so [31]. Adding the read-only user to an existing volume may need `make reset` or a manual `GRANT`.
- **DRF's `MultiPartParser` delegation** was read in the 3.18.0 tag; the pinned 3.18.3 wasn't diffed.
- **TLS defaults of the `mariadb:11` image** combined with PyMySQL 1.2's opportunistic TLS.
- **The "~30 fields" in CHALLENGE.md** may describe a different source site; the dump has 10.
- **Exact Vite or Rollup option names** for fixed output filenames (owned by Pillar 3).
- **PostgreSQL case-sensitivity of an exact `slug=` lookup** under the default collation was not tested here.

---

## Sources

1. Django 5.2 docs, QuerySet API (`bulk_create`, `update_or_create`, `iterator`): https://docs.djangoproject.com/en/5.2/ref/models/querysets/ (via Context7 `/websites/djangoproject_en/5.2`)
2. Django 5.2 docs, Model field reference (`GeneratedField`, `db_default`): https://docs.djangoproject.com/en/5.2/ref/models/fields/
3. Django 5.2 docs, Constraints reference: https://docs.djangoproject.com/en/5.2/ref/models/constraints/
4. Django 5.1 release notes (`CheckConstraint.check` deprecated): https://docs.djangoproject.com/en/5.2/releases/5.1/
5. Django 5.0 release notes (`bulk_create` sets PKs with `update_conflicts`; `db_default`; `GeneratedField`): https://docs.djangoproject.com/en/5.2/releases/5.0/
6. Django 5.2 docs, Composite primary keys: https://docs.djangoproject.com/en/5.2/topics/composite-primary-key/
7. Django 5.2 docs, Settings (`APPEND_SLASH`, `DISABLE_SERVER_SIDE_CURSORS`): https://docs.djangoproject.com/en/5.2/ref/settings/
8. Django 5.2 docs, Middleware (`CommonMiddleware`): https://docs.djangoproject.com/en/5.2/ref/middleware/
9. Django 5.2 docs, Built-in template tags and filters (`json_script`): https://docs.djangoproject.com/en/5.2/ref/templates/builtins/
10. Django 5.2 docs, Databases (PostgreSQL 14+; server-side cursors): https://docs.djangoproject.com/en/5.2/ref/databases/
11. Django 5.2 docs, Model instance reference (`full_clean()` not called by `save()`): https://docs.djangoproject.com/en/5.2/ref/models/instances/
12. Django 5.2 docs, Making queries (`update()` skips `save()`, signals, `auto_now`): https://docs.djangoproject.com/en/5.2/topics/db/queries/
13. Django 5.2 docs, Transactions (`set_rollback`): https://docs.djangoproject.com/en/5.2/topics/db/transactions/
14. Django 5.2 docs, Aggregation (combining multiple aggregations): https://docs.djangoproject.com/en/5.2/topics/db/aggregation/
15. Django 5.2.18 installed source, inspected in a throwaway env on 2026-11-09: `CommonMiddleware.response_redirect_class` (301), `CheckConstraint.__init__`, `QuerySet.bulk_create`/`update_or_create` signatures, `URLValidator.schemes`, `SlugConverter.regex`, `Truncator.words`, `ForeignKey.db_index`
16. Django security archive (read 2026-11-09): https://docs.djangoproject.com/en/dev/releases/security/
17. Django weblog, security releases 6.0.2 / 5.2.11, 2026-02-03: https://www.djangoproject.com/weblog/2026/feb/03/security-releases/
18. Django weblog, security releases incl. 5.2.17, 2026-08-04: https://www.djangoproject.com/weblog/2026/aug/04/security-releases/
19. Django weblog, security releases 6.1.3 / 6.0.10 / 5.2.19, 2026-11-03: https://www.djangoproject.com/weblog/2026/nov/03/security-releases/
20. GitHub Advisory Database, Django advisories 2025–26 (API, 2026-11-09): GHSA-6w2r-r2m5-xq5w (CVE-2025-57833), GHSA-hpr9-3m2g-3j9p (CVE-2025-59681), GHSA-frmv-pr5f-9mcr (CVE-2025-64459), GHSA-rqw2-ghq9-44m7 (CVE-2025-13372): https://github.com/advisories?query=ecosystem%3Apip+django
21. PyPI JSON API, upload times (Django 5.2.19: 2026-11-03T15:22Z; PyMySQL 1.2.4: 2026-11-09T09:37Z; nh3 0.3.7: 2026-08-23): https://pypi.org/pypi/Django/json, https://pypi.org/pypi/PyMySQL/json, https://pypi.org/pypi/nh3/json
22. PyMySQL CHANGELOG, v1.1.3–v1.2.4: https://github.com/PyMySQL/PyMySQL/blob/main/CHANGELOG.md; advisories GHSA-m75w-33c4-7v8q (1.2.4), GHSA-x4f8-9hx9-hpp9 (1.2.1), GHSA-v9hf-5j83-6xpp (CVE-2024-36039)
23. PyMySQL cursors API reference (`SSCursor`): https://github.com/pymysql/pymysql/blob/main/_autodocs/api-reference/cursors.md (via Context7 `/pymysql/pymysql`)
24. nh3 documentation (`Cleaner`, `clean`, `ALLOWED_URL_SCHEMES`): https://nh3.readthedocs.io/en/latest/ (via Context7)
25. nh3 v0.3.7 `Cargo.toml`/`Cargo.lock` (ammonia 4.1.4) and `main` `Cargo.toml` (still 4.1.4), read 2026-11-09: https://github.com/messense/nh3/blob/v0.3.7/Cargo.toml
26. ammonia security advisories (GHSA-f2pc-rwv3-69mv, GHSA-69v2-w9vg-4g83, GHSA-x43w-36pp-96g3) and crates.io versions (4.1.7 2026-10-11, 4.1.8 2026-10-17): https://github.com/rust-ammonia/ammonia/security/advisories, https://crates.io/crates/ammonia
27. nh3 0.3.7 run against all brand and review bodies from the dump plus XSS probes, throwaway env, 2026-11-09
28. MariaDB docs, START TRANSACTION (`WITH CONSISTENT SNAPSHOT`, `READ ONLY`): https://mariadb.com/docs/server/reference/sql-statements/transactions/start-transaction
29. MariaDB docs, Server system variables (`net_write_timeout` 60, `net_read_timeout` 30, `transaction_isolation` REPEATABLE-READ): https://mariadb.com/docs/server/server-management/variables-and-modes/server-system-variables
30. MariaDB docs, GRANT (column privileges, `MAX_USER_CONNECTIONS`, `REQUIRE SSL`): https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant
31. MariaDB Docker image docs (`/docker-entrypoint-initdb.d`, `_FILE` secrets): https://github.com/docker-library/docs/blob/master/mariadb/content.md
32. PostgreSQL 18 docs, INSERT (`ON CONFLICT` cardinality rule, arbiter inference, `RETURNING OLD/NEW`): https://www.postgresql.org/docs/18/sql-insert.html
33. PostgreSQL 18 docs, Sorting rows (`NULLS FIRST` default for `DESC`): https://www.postgresql.org/docs/18/queries-order.html
34. PostgreSQL 18 docs, REFRESH MATERIALIZED VIEW: https://www.postgresql.org/docs/18/sql-refreshmaterializedview.html
35. PostgreSQL 18 docs, Advisory lock functions: https://www.postgresql.org/docs/18/functions-admin.html
36. WordPress developer reference, `get_posts()` defaults: https://developer.wordpress.org/reference/functions/get_posts/
37. WordPress developer reference, `wpautop()`: https://developer.wordpress.org/reference/functions/wpautop/
38. WordPress 6.9 source: `default-filters.php` (`the_content` filters), `formatting.php` (`wp_trim_words`), `post.php` (`update_post_meta`), `meta.php` (meta cache `ORDER BY meta_id ASC`): https://github.com/WordPress/wordpress-develop/tree/6.9/src/wp-includes
39. Make WordPress Core, "WordPress 6.8 will use bcrypt for password hashing" (2025-02-17): https://make.wordpress.org/core/2025/02/17/wordpress-6-8-will-use-bcrypt-for-password-hashing/
40. Python 3.14 docs, `uuid` (`uuid5`; `uuid7` new in 3.14): https://docs.python.org/3.14/library/uuid.html
41. Vite docs, Backend integration (manifest, dev preamble): https://vite.dev/guide/backend-integration
42. MDN, CSP `style-src-attr` (fallback to `style-src`, then `default-src`): https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/style-src-attr
43. DRF settings (`DEFAULT_PARSER_CLASSES` default), via Context7 `/encode/django-rest-framework`: https://www.django-rest-framework.org/api-guide/settings/; DRF 3.18.0 `parsers.py` (wraps Django's `MultiPartParser`): https://github.com/encode/django-rest-framework/blob/3.18.0/rest_framework/parsers.py
44. This repository, measured 2026-11-09: `db/dump.sql` (MariaDB 11.8.6 dump), `wp-content/mu-plugins/cpt.php`, `wp-content/mu-plugins/acf-fields.php`, `wp-content/themes/consumer-reviews/*.php`, `scripts/seed.sh`, `docker-compose.yml`, `Makefile`
45. Ruff rule S308 `suspicious-mark-safe-usage`: https://docs.astral.sh/ruff/rules/suspicious-mark-safe-usage/
46. PostgreSQL 18 docs, Constraints (unique constraints and `NULLS DISTINCT` default): https://www.postgresql.org/docs/18/ddl-constraints.html
