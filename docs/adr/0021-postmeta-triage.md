# 0021. Postmeta triage: typed columns, two SEO fields, the rest dropped

- Status: Accepted
- Date: 2026-11-09

## Context
CHALLENGE.md question 2 says brands have "~30 fields" of postmeta, including Yoast, and
asks which became columns, which became JSON and which were dropped. The dump has **10
postmeta rows per brand and 8 per review**
(`docs/research/pillar-1-django-backend.md` §5). The "30" most likely refers to Yoast's
`wp_yoast_indexable` table: 53 columns, 16 of them non-empty for brands, all derived
from postmeta. Of the postmeta rows, half are ACF's `_`-prefixed field-key pointers,
which exist only for ACF's admin screens.

## Options considered
- **SEO as a `JSONField`.** Flexible, but untyped; it needs a parser at the boundary
  (ADR 0013). Rejected for two values that are always present.
- **SEO as two typed columns.** Chosen.
- **A raw postmeta snapshot (`wp_raw` JSON) to keep everything.** Rejected: it
  duplicates storage and personal data for keys we've already triaged.
- **Unknown keys skipped silently.** Rejected: a new key means WordPress's schema
  changed, and a person should see that. Unknown keys fail the import instead.

## Decision
| WP source | Becomes | Why |
|---|---|---|
| `website_url` | `Brand.website_url` (`URLField`, http/https only) | Rendered as a link |
| `founded_year` | `Brand.founded_year` (small int, checked 1800–2100) | Rendered |
| `headquarters` | `Brand.headquarters` (`CharField`) | Rendered |
| `average_rating` | `Brand.legacy_average_rating` | Audit only (ADR 0019) |
| `_yoast_wpseo_title` | `Brand.seo_title` | `<title>` |
| `_yoast_wpseo_metadesc` | `Brand.seo_description` | Meta description |
| review `brand` | `Review.brand` foreign key | The relationship |
| review `rating` | `Review.rating` (small int, check 1–5) | Averaged, sorted, shown |
| `reviewer_name`, `reviewer_location` | Snapshots on `Review` (ADR 0020) | What was displayed |
| `_`-prefixed ACF keys, `_wp_page_template` | Dropped | ACF admin pointers; pages aren't imported |
| `wp_yoast_indexable` table | Dropped | Derived cache; duplicates the two SEO keys |
| `wp_usermeta` | Not read by the main app | Roles belong to the auth service |

The importer keeps an explicit list of known-and-ignored keys. Any other key fails the
run.

## Consequences
- More Yoast keys (Open Graph, robots) would each need a migration.
- Yoast descriptions hard-code review counts ("Read 12 independent customer
  reviews…"), so they go stale when reviews change. They're imported as written.

## Revisit when
SEO output beyond title and description is wanted, or WordPress gains fields we need.

## Sources
`docs/research/pillar-1-django-backend.md` §5.
