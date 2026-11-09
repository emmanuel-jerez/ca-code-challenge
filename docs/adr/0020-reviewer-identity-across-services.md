# 0020. Reviewer identity across the two services

- Status: Accepted
- Date: 2026-11-09

## Context
CHALLENGE.md question 1 also asks how reviewers are modeled: full Django users, a
Reviewer model, or strings on each review. The auth service owns users. The main app
stores only an external user id (AGENTS.md, ADR 0006). The data
(`docs/research/pillar-1-django-backend.md` §1, §4):
- 8 WordPress subscribers wrote all 60 reviews. The single administrator wrote none.
- `reviewer_name` always equals the author's `display_name`.
- `reviewer_location` varies per review for the same person.

Nothing in scope matches a token to a reviewer at request time. The only protected write
is an editor changing a brand's short description. The link matters for display now
and for user-owned features later.

## Options considered
**Shape:**
- **Strings on each review only.** Rejected: it can't tell two people with the same
  name apart, and leaves no path to user-owned features.
- **A `Reviewer` model only.** Rejected: it loses the name and location as they were
  displayed on each review.
- **Both:** a `Reviewer` row, plus snapshots on each review. Chosen.

**Key linking a reviewer to the auth service:**
- **The auth service's id, so the auth import runs first.** Rejected: it orders the two
  imports and needs a hand-off before content can load.
- **`uuid5` from the WP id, computed by both importers.** Rejected: it ties the auth
  service's id scheme to WordPress ids, and anyone can derive the ids from public WP
  ids.
- **An internal lookup API.** Rejected: it needs service-to-service credentials.
- **WP user id now, auth id filled in later from a file the auth service exports.**
  Chosen.

## Decision
- **Main app:** a `Reviewer` model with a unique `wp_user_id`, `display_name` and a
  nullable `auth_user_id` (the auth service's external id).
  - `Review.reviewer` is a foreign key with `on_delete=SET_NULL`.
  - Each `Review` keeps `reviewer_name` and `reviewer_location` snapshots.
  - Only users who wrote reviews get a row, so the administrator gets none.
- **Main-app import:** reads only `wp_users.ID` and `display_name`, through a MariaDB
  user granted just those columns. It never sees password hashes or emails.
- **Auth service:** a management command exports a `wp_user_id → external_id` map, with
  no emails and no hashes. The main-app import reads it, when present, to fill
  `auth_user_id`. Without it, reviews still import and display.

## Consequences
- The content import never waits on the auth import, and there's no runtime coupling.
- The link is eventually consistent: `auth_user_id` stays empty until the map is
  imported.
- If the auth service deletes a user, the review stays readable through its snapshots.

## Revisit when
A feature needs the logged-in user's reviews ("edit my review"), or reviewers can sign
up outside the WordPress import.

## Sources
`docs/research/pillar-1-django-backend.md` §4, §9; `docs/research/pillar-5-auth-service.md` §2 and open decision 4.
