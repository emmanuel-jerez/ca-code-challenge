# 0026. Pillar 1: industry link, removals, sanitizing, writes and views

- Status: Accepted
- Date: 2026-11-09

## Context
ADRs 0019–0021 settled ratings, reviewer identity and postmeta. The Pillar 1
research (`docs/research/pillar-1-django-backend.md`, "Open decisions") left
more choices open, which had to be made before the import and pages could be
written. Facts from the dump: every brand has exactly one industry, every
brand and review is `publish`, and every body is attribute-free `<p>` HTML.
Editors will change `Brand.short_description` through Pillar 5's `PATCH`.

The user chose items 1–4 on this date. Items 5–10 are implementation defaults
the agent took from the research while building, flagged for review in the
Pillar 1 pull request.

## Options considered
1. **Brand → industry.** Many-to-many matches WordPress's taxonomy. Rejected:
   filters need `distinct()`, cards must pick one industry, and the theme only
   ever shows the first. A foreign key was chosen.
2. **Rows unpublished or deleted in WordPress.**
   - Hard delete. Rejected: irreversible, and `PROTECT` blocks deleting a brand
     that has reviews.
   - Report only. Rejected: deleted content would stay public.
   - Store the status, and mark vanished rows `removed`. Chosen.
3. **Where HTML is sanitized.**
   - At render. Rejected: one template that forgets the filter is stored XSS.
   - At import, cleaned only. Rejected: a stricter allow-list would need a
     re-import from WordPress.
   - At import, keeping the raw source too. Chosen.
4. **Test tooling.** Django's runner alone was rejected: the shared library
   can't use it. Chosen: pytest 9.2, pytest-django 4.14, and typeshed's
   `types-PyMySQL` so mypy strict accepts PyMySQL.
5. **Skipping unchanged rows.** The research proposed a per-row SHA-256
   column. Rejected in favor of comparing the incoming values with the stored
   row: no extra column, and it also catches a changed sanitizer allow-list,
   which a hash of the raw row would miss. The cost: existing rows are loaded
   into memory, fine at 100x (about 7,000 posts).
6. **Who owns `short_description`.** Overwriting it on every import was
   rejected: it would erase editors' changes.
7. **Bad rows.** Skipping and reporting them was rejected: a half-imported
   site looks correct while missing content.
8. **Views.** Class-based views were rejected: their behavior lives in
   inherited methods that are harder to explain line by line.
9. **Header links to `/brand/`, `/review/` and `/about/`.** Not built: they
   aren't required, and `/brand/` belongs to Pillar 3. The nav shows only Home
   until those pages exist, so it never links to a 404.
10. **`django.contrib.auth` and the admin in the main app.** Left out: the auth
    service owns users, and the admin is out of scope and carries its own
    advisories (CVE-2026-15920).

## Decision
- `Brand.industry` is a `ForeignKey(PROTECT)`. The import stops if a brand has
  zero or more than one industry.
- Brands and reviews store WordPress's status. Pages show only `publish`
  (and hide reviews of hidden brands). Rows WordPress no longer has become
  `removed`, are counted in the report, and are never deleted.
- `content_source` keeps the raw HTML and is never rendered. `content_html` is
  cleaned at import with nh3 and the allow-list in `wp_import/content.py`.
  Templates reach it only through one `body_html` property; a test fails on
  `|safe` in templates.
- Writes use `update_or_create` on the WordPress id, inside one transaction
  behind a Postgres advisory lock. Rows whose stored values already match are
  not written, so a re-run writes nothing and says so.
- `short_description` is set (excerpt, else the body's first 22 words) only
  when a brand is created.
- Every check runs before the first write, and any bad row stops the run. The
  known-and-ignored postmeta list (ADR 0021) also includes `_edit_lock` and
  `_edit_last`, which wp-admin adds whenever someone opens a post.
- Function views, each 1–2 queries, pinned by `assertNumQueries`-style tests.

## Consequences
- Fixing a bad row means fixing it in WordPress and re-running; nothing is
  half-written in the meantime.
- Saving a brand in wp-admin with Yoast enabled adds more `_yoast_wpseo_*`
  keys, which stop the import until they're triaged. That's intended (ADR
  0021), but it surprises anyone who edits in wp-admin.
- `removed` rows accumulate. A `--prune` flag can delete them later.
- Changing the sanitizer allow-list needs only a re-run: every row's cleaned
  HTML differs, so every row updates.

## Revisit when
A brand needs a second industry, imports grow past what fits in memory (switch
to per-batch lookups and bulk upserts), content needs tags the allow-list
lacks, or Pillar 3 adds the brand archive page.

## Sources
`docs/research/pillar-1-django-backend.md` §2, §6–8 and "Open decisions";
nh3 0.3.7 `Cleaner` docstring (installed package, checked 2026-11-09).
