# Best Practices for the Challenge (seen from late 2026)

> **Corrected later (2026-11-09).** Parts of this note were superseded by the pillar research: §0.8, §4–8 (SQL injection CVE summary, `aria-busy`, stylelint, token checks, Argon2): see the "Corrections" sections of the `pillar-*.md` notes. The text below is kept as it was written.

Research notes for the WP → Django challenge. Each section covers the long-standing practice, the case for it, its weak spots, and what changed over the last year as AI-written code became normal and supply chain attacks grew. Each section closes with a **Defend it** line: a short answer you can give on the call.

> Confidence notes. Figures marked *(secondary)* come from vendor blogs or news reports, not primary sources. Check them before you quote them on the call. Everything else comes from official docs, standards drafts or primary write-ups.

---

## 0. Ten things to remember

1. **Attackers now go after publishers, not code bugs.** Most big 2026 incidents (Axios, LiteLLM, Keyv/"ChainDrop", Mastra, durabletask) used stolen maintainer or CI credentials to publish real-looking versions. Hash pinning didn't help, because the hashes were legitimate.
2. **Install-time defenses aren't enough.** The AsyncAPI compromise (July 2026) ran its payload at *import* time, so `--ignore-scripts` didn't stop it, and it shipped with valid signed provenance. LiteLLM's payload ran at Python startup without even being imported.
3. **A cooldown is the cheapest strong defense.** Most malicious versions are pulled within hours. A 3–7 day minimum release age (uv `exclude-newer = "7 days"`, pnpm `minimumReleaseAge`, npm's cooldown setting, pip `--uploaded-prior-to`) skips the window. The cost: urgent security fixes need an exception path.
4. **AI-written code is still insecure about 45% of the time by default.** Veracode's 2026 report: a 56% security pass rate, essentially unchanged from 55% the year before, even as models got better at writing code that works. The model only becomes secure when you brief, review and test it that way.
5. **AI amplifies what's already there** (DORA 2025). Throughput goes up and so does delivery instability. Guardrails (tests, types, linters, small diffs, CI) decide which way it goes.
6. **Treat coding agents as privileged supply chain actors.** In 2026 there were prompt-injection-to-publish chains (Clinejection; the Claude Code Action `[bot]` bypass, CVE-2025-66032), slopsquatting (registering names that models hallucinate) and poisoned agent skills.
7. **For the auth boundary:** asymmetric JWTs (EdDSA or ES256), verified locally against a cached JWKS, with short lifetimes. Pin algorithms and check `iss`/`aud`/`exp`/`typ`. Use PyJWT ≥ 2.15.1 (2.13–2.15 fixed CVE-2026-48526 and 14 more advisories, including a critical key-confusion bypass) and not python-jose (it released 3.4.0 and 3.5.0 in 2025, but has a weak security record and FastAPI dropped it).
8. **Django:** this project uses 5.2 LTS on Python 3.14 (see the `django-lts` skill); 6.x is ruled out. Django 4.2 reached end of life in April 2026. Three ORM SQL injection CVEs were patched in February 2026, all through `order_by` or aliases, so allow-list sort parameters and never pass raw input to `order_by()`.
9. **React:** a plain client-side component (Vite) avoids the React Server Components attack surface (React2Shell, CVE-2025-55182: unauthenticated RCE, exploited in the wild). Every dependency is attack surface, so justify each one.
10. **Sass:** use `@use`/`@forward` only. `@import` has been deprecated since Dart Sass 1.80 and will be removed in 3.0. Emit tokens as CSS custom properties.

---

## 1. The 2025–26 threat landscape (context for the call)

| When | Incident | Lesson |
|---|---|---|
| Mar 2025 | `tj-actions/changed-files` GitHub Action compromised (~23k repos) | Pin Actions to a commit SHA, not a tag |
| Aug 2025 | Nx "s1ngularity": the malware used victims' installed AI CLIs to hunt for secrets | Your AI tools are part of the attack surface |
| Sep–Nov 2025 | Shai-Hulud npm worm (and 2.0) | Worms republish using stolen tokens, so token theft spreads |
| Dec 2025 | npm revokes all classic tokens and pushes OIDC trusted publishing | Registries are moving to short-lived, identity-bound publishing |
| Dec 2025 | React2Shell CVE-2025-55182 (RSC RCE), plus follow-up CVEs | Server-side React adds a new server attack surface |
| Feb 2026 | Clinejection: a prompt injection in a GitHub issue led to a malicious `cline` npm release | Prompt injection now leads to supply chain compromise |
| Mar 2026 | Axios (100M+ weekly downloads) compromised; LiteLLM and Telnyx on PyPI (TeamPCP); Trivy images on Docker Hub | Even security tools and core HTTP clients get hit |
| Apr–Jun 2026 | Mini Shai-Hulud waves; @redhat-cloud-services; Mastra AI (140+ packages, attributed to North Korea) | Scope-wide takeovers |
| Jul 2026 | AsyncAPI: payload runs at import time and carries valid provenance | Provenance proves *where* a package was built, not that the source was safe |
| Jul 2026 | PyPI rejects new files on releases older than 14 days | Closes "add a malicious wheel to an old, pinned release" |
| Aug 2026 | ChainDrop/Keyv worm: ~400–444 packages, billions of monthly installs *(counts differ by source)* | The largest npm event of the year |
| Oct 2026 | LiteLLM compromised again (1.107.0) | Repeat targets: AI infrastructure packages are prized |

**Patterns that matter for this challenge**
- Payloads go after **developer machines and CI**: cloud keys, SSH keys, npm and PyPI tokens, `.env` files. Your laptop is the target, not your production app.
- **Dependency confusion** is still alive. In May 2026 Microsoft reported 33 npm packages probing developer environments. This matters for Pillar 6: if your shared library's name is free on PyPI, someone can register it.
- The OWASP Top 10:2025 added **A03 Software Supply Chain Failures** at #3, widening the old "Vulnerable and Outdated Components" to cover build systems, CI/CD and distribution. Security Misconfiguration rose to #2.

---

## 2. AI-assisted engineering: what the evidence says

| Source | Finding | Caveat |
|---|---|---|
| Veracode GenAI Code Security Report 2026 | About 44–45% of tasks produce a vulnerability; 56% pass rate, flat year over year | Measured with no security instruction in the prompt |
| METR RCT (2025) | Experienced OSS developers were **19% slower** with AI but *believed* they were faster | Small sample on mature codebases |
| METR update (Feb 2026) | Productivity is probably improving, but their study design can't measure it reliably any more | No clean new number |
| DORA 2025 (~5,000 respondents) | ~90% use AI; throughput up, **instability up**; ~30% have little or no trust in AI code | "AI is an amplifier" |
| arXiv 2607.15143 | Agents run `pip install` without inspecting packages; none tested ran `pip-audit` first | Research setting |

**What this means for how you work (and what the interviewers are watching)**
- **Brief, don't just prompt.** Give the agent constraints up front in `CLAUDE.md`/`AGENTS.md`: stack, conventions, "no new dependency without asking", "allow-list every query param", "never use `|safe` on WP content".
- **Ask for a plan first**, then code in small diffs. Reject output you can't explain. The challenge says they'll probe for exactly that.
- **Tests are the contract.** Write the important tests first (or have the agent write them and review them hard): idempotent migration, the permission matrix, token expiry, bad `alg`.
- **Check every dependency the AI suggests:** does it exist, how old is it, who maintains it, how many downloads? This defends against slopsquatting.
- **Run the agent without secrets** in its environment. No production `.env`, no publish tokens.
- **Treat imported data as untrusted input to the AI, too.** WP `post_content` from the dump is HTML that could hold a prompt injection when you paste it into a chat. Same for READMEs of dependencies you ask it to evaluate.
- **The challenge README asks where you accepted AI defaults.** Keep a short running log as you go. It's also your best prep for the "how did you steer it" questions.

---

## 3. Cross-cutting: dependency and build hygiene

| Practice | For | Against / weak spots |
|---|---|---|
| **Lockfiles with hashes** (`uv.lock`, `pnpm-lock.yaml`) | Reproducible installs; blocks tampered artifacts | Doesn't stop a *legitimately published* malicious version (LiteLLM passed hash checks) |
| **Release cooldown** (uv `exclude-newer = "7 days"`, pnpm `minimumReleaseAge` — on by default at 1 day in pnpm 11, npm cooldown since Feb 2026, pip 26.1 `--uploaded-prior-to P7D`) | Skips the hours or days before malware is detected; very cheap | Delays urgent security patches, so you need a documented per-package exception (`exclude-newer-package`, `minimumReleaseAgeExclude`). pnpm silently falls back to an older version |
| **Block install scripts** (pnpm ≥ 10 by default; npm `--ignore-scripts`) | Stops the classic postinstall payload | Doesn't stop import-time payloads (AsyncAPI) |
| **Few dependencies** | Less attack surface and upgrade churn | You rewrite small things yourself and must own them |
| **Pin Docker images by digest**; consider Docker Hardened Images (free since late 2025) | Immutable; DHI are rebuilt hermetically with signed provenance | A digest proves immutability, not safety: pin during an attack window and you lock the malware in. Docker Hub tags are mutable by default (immutable tags still beta) |
| **Pin GitHub Actions by SHA**, read-only `GITHUB_TOKEN`, no `pull_request_target` on untrusted code, run `zizmor`/`actionlint` | Prevents tag-swap attacks | Pins go stale without Dependabot; a SHA can resolve to a commit that exists only in a fork; Wiz notes SHA pinning can bypass some newer GitHub defenses |
| **Trusted publishing (OIDC) + attestations** | No long-lived tokens to steal | AsyncAPI showed that provenance from a legitimate workflow can still wrap malicious source |
| **Never mount the Docker socket** into app containers | A compromised container can't take over the host | Some dev tooling expects it |

**Defend it:** "I pinned through lockfiles with hashes and a 7-day cooldown, kept dependencies minimal, and pinned images by digest. The 2026 incidents were mostly stolen publisher credentials, so I assume any version could be hostile in its first days, and the cooldown handles that cheaply. The trade-off is slower security patches, so there's a documented override."

---

## 4. Pillar 1: Django models and data migration

### Version and platform
- **Django 5.2 LTS** (supported to April 2028) on Python 3.14. This project rules out 6.x (see the `django-lts` skill). 6.0's built-in CSP (`SECURE_CSP`), template partials and tasks framework don't exist in 5.2. CSP comes from a small custom middleware instead (see `stack-decisions.md`). 4.2 is end of life as of April 2026.
- Feb 2026 security release (6.0.2 / 5.2.11): **three SQL injection CVEs**: CVE-2026-1287 (FilteredRelation aliases with control characters), CVE-2026-1312 (`order_by` with FilteredRelation and dotted aliases), CVE-2026-1207 (PostGIS raster). It also fixed a username-enumeration timing bug (CVE-2025-13473). **Lesson:** user input never reaches `order_by()`, `annotate()` aliases or `extra()`. Map an allow-listed sort key to an ORM expression.

### Relational model vs. copying WP's shape
- **For:** a clean model (`Brand`, `Industry`, `Review`, `Reviewer`) gives real constraints, indexes and joins. EAV-style postmeta (`wp_postmeta`) can't be typed, indexed or constrained well.
- **Against:** you have to decide on every meta key, and you lose any you forget, so keep a raw JSON snapshot (see below).

### `average_rating`: store, derive, or both?
| Option | For | Against |
|---|---|---|
| Derive (`annotate(Avg)`) | Always correct; one source of truth | Cost per request grows with reviews; sorting by an aggregate across pages is heavier |
| Store only | Fast sorting and indexing | Drifts from the reviews unless kept in sync |
| **Both:** computed column kept in sync (recomputed on review save or in the importer) **plus** the original ACF value kept as `legacy_average_rating` | Fast sort, auditable; you can show where WP's number and the real number disagree | Sync logic to own; you must say which one the API shows |

Check the data: if the ACF `average_rating` doesn't match the mean of the seeded review ratings, that's a good finding to bring up on the call.

### Reviewers when the auth service owns users
- The main app must not store passwords or roles. Options: (a) a `Reviewer` model in the main app holding `auth_user_id` (external ID, not an FK across databases) plus a display name; (b) just `reviewer_name`/`reviewer_location` strings on each review.
- **Recommended:** both. A `Reviewer` keyed by the auth-service ID, **and** keep `reviewer_name`/`reviewer_location` on `Review` as a *snapshot of what was displayed* (ACF stores them per review, and they may differ from the user profile).
- **Weak spot:** no referential integrity across services. Handle deleted users (soft reference; show "Former reviewer").

### Postmeta triage
- **Columns:** anything you query, filter, sort or render: `website_url`, `founded_year`, `headquarters`, `rating`, `brand`.
- **JSON (`seo` JSONField):** Yoast `_yoast_wpseo_*`. It's rendered but never queried. Promote `title`/`metadesc` to columns only if you use them.
- **Drop:** `_edit_lock`, `_edit_last`, ACF key pointers (`_website_url` → `field_xxx`), anything with a `_wp_` prefix you don't render.
- **Keep a raw import snapshot** (`raw_wp` JSON or a separate table) so a dropped field can be recovered without re-importing. The weak spot is storage and PII duplication.

### Migration approach
| Source | For | Against |
|---|---|---|
| **Query MariaDB directly** (management command, read-only DB user) | Complete (all postmeta and Yoast), fast, set-based | Coupled to WP's internal schema; needs a DB driver (`mysqlclient`/`PyMySQL`) |
| REST API | Stable public contract; ACF already shaped | Pagination; `/users` hides fields without auth; Yoast meta may be missing; slow at 100x |
| Parse `dump.sql` | No running WP needed | Fragile SQL parsing; escaping bugs |

**Re-runnable without duplicates:**
- Store `wp_id` (unique) on every imported row and upsert on it, not on slug (slugs can change).
- Use `update_or_create` for clarity, or `bulk_create(..., update_conflicts=True, unique_fields=["wp_id"], update_fields=[...])` for scale.
- Import in dependency order (industries → users → brands → reviews), inside `transaction.atomic()`. Add `--dry-run` and print created/updated/skipped counts.
- Decide on deletes: rows that vanished from WP get soft-deleted or reported, never silently kept.

**At 100x:** stream in batches (server-side cursors), bulk upserts, defer derived recomputes to one set-based `UPDATE` at the end, and make it resumable by checkpointing on `wp_id`.

### Rendering WP HTML
- `post_content` is HTML. `{{ content|safe }}` is a stored-XSS risk if WP content was ever user-supplied (reviews are!). **Sanitize at import or render time with `nh3`** (`bleach` gets no more releases, including security fixes). Never allow `style`, `svg`, `math` or `animate*`: nh3 0.3.7 bundles an ammonia version with open advisories that need those. Add a CSP header from a custom middleware as defense in depth (5.2 has no built-in CSP).

**Defend it:** "I keyed every row on the WP ID and upsert, so re-runs are no-ops. I read MariaDB directly because it's the only source with all the postmeta. Ratings are derived and synced, and WP's value is kept for audit. Review HTML is sanitized because it's user content."

---

## 5. Pillar 2: `GET /api/brands/`

### DRF vs. Django Ninja vs. plain views
| | For | Against |
|---|---|---|
| **DRF** | Most widely deployed; huge ecosystem (`django-filter`, `drf-spectacular`, SimpleJWT); well known to AI models and reviewers | Heavier and slower; serializer "magic"; development pace has slowed (maintenance-heavy) |
| **Ninja** | Pydantic types, automatic OpenAPI, async, less code | Smaller ecosystem, more bus-factor risk; you build more auth and permission pieces yourself |
| Plain `JsonResponse` | No dependencies | You reinvent pagination, validation and docs |

The shared library must provide "a DRF authentication class and permission class, *or* a decorator", so DRF makes Pillar 6 straightforward.

### Pagination shape
| | For | Against |
|---|---|---|
| **Page number** (`?page=2&page_size=12`, returns `{count, next, previous, results}`) | Simple; jump to page N; total count for the UI | `COUNT(*)` gets costly at scale; rows shift between pages under concurrent writes |
| **Cursor** | Stable under writes; O(1) at depth; good for mobile infinite scroll | No page jumps or total; needs a unique, deterministic order |

**Either way:** always add a unique tie-breaker (`-average_rating, id`). Without one, equal ratings make pages repeat or skip rows (a classic AI-generated bug). Cap `page_size` (e.g. ≤ 50).

**If a mobile client also used it:** cursor pagination, smaller payloads, explicit versioning (`/api/v1/` or a header), stable field names, and ETags/caching.

### Filter and sort names
- `?industry=retail&industry=tech` (repeatable; slugs, not IDs) and `?ordering=-average_rating` / `review_count` (the DRF/django-filter convention). Validate against an **allow-list** and return 400 on unknown values instead of ignoring them silently.

### Performance and correctness
- `annotate(review_count=Count(...), avg=Avg(...))` plus a `Subquery` for the top review gives a single query. Assert this with `django_assert_num_queries` in tests: AI code often produces N+1 queries.
- **"Top review snippet":** define and document it, e.g. highest rating, then the longest body, then newest; truncated server-side.
- Add throttling on the PATCH endpoint and on auth login.

**Defend it:** "Page-number pagination because the UI shows a grid with page controls and the data is small. I'd switch to cursor for mobile or infinite scroll. The sort always has an ID tie-breaker. Params are allow-listed, because the February 2026 Django CVEs came from unvalidated input reaching `order_by`."

---

## 6. Pillar 3: React `<BrandList />`

### Build setup
- **Vite + React 19, client-side only.** Next.js or RSC would add a server-side React runtime, the surface hit by React2Shell (CVE-2025-55182, unauthenticated RCE, exploited at scale) and its follow-ups (55183 source exposure, 55184/67779 DoS). For one component on a Django page you don't need it.
- React Compiler 1.0 (Oct 2025) removes most manual `useMemo`/`useCallback`. Optional.

### State
| Concern | Recommended | For | Against |
|---|---|---|---|
| Filter, sort, page | **URL search params are the source of truth** (`URLSearchParams` plus `history.replaceState`/`pushState`, or a router hook) | Shareable, survives refresh, back button works | Must parse and validate params (untrusted input); risk of loops between URL and state |
| Server data | `fetch` + `AbortController` + `useReducer` (`idle/loading/success/error`) **or** TanStack Query | Plain: zero dependencies (a supply chain argument). TanStack: caching, retries, deduplication | Plain: you handle races and stale responses yourself. TanStack: one more dependency to vet |

Either is defensible. Say why. Cancel in-flight requests when filters change; out-of-order responses are a common bug.

### Loading, empty and error UX
- Skeleton cards at final size (no layout shift); keep previous results visible but dimmed while refetching.
- Empty state names the active filters and offers "Clear filters".
- Error state gives a human message and a **Retry** button. Never show raw error text.

### Accessibility (WCAG 2.2 AA; the European Accessibility Act has applied since June 2025)
- Native controls first: `<select>`, or `<fieldset><legend>` with checkboxes for multi-select, and a `<button>` for every action. "No ARIA is better than bad ARIA", and AI output often misuses ARIA or builds clickable `<div>`s.
- Results as `<ul>` with `<li><article>` cards with a heading; one link per card.
- `aria-live="polite"` region announcing "12 brands, sorted by rating"; `aria-busy` on the list while loading.
- Visible focus (WCAG 2.2 *Focus Not Obscured*), target size ≥ 24px (*2.5.8*), `prefers-reduced-motion`, enough contrast. Ratings get text ("4.5 out of 5"), not only stars.
- Test: Testing Library `getByRole` queries, `jest-axe`/`vitest-axe`, then a manual keyboard-only pass and a screen reader spot check.

### Styling choice
- Plain CSS or the Pillar 4 SCSS, with BEM classes, reusing the tokens. This reuses your SCSS and avoids Tailwind's or CSS-in-JS's dependency and runtime cost. **Weak spot:** global classes can collide, so prefix them (`c-brand-card`) or use CSS Modules.

**Defend it:** "The URL owns filter state, so links are shareable and the back button works. Requests are cancelled on change to avoid races. Native form controls for accessibility. No RSC, because it adds a server attack surface I don't need, and that's where 2025's worst React CVE was."

---

## 7. Pillar 4: SCSS architecture

### Module system
- `@use` / `@forward` only, with namespaces. `@import` and global functions (`map-get`) have been deprecated since Dart Sass 1.80 (Oct 2024) and will be removed in **Dart Sass 3.0**, which isn't released yet. Use `sass:map`, `sass:math`. Compile with the `sass` package (Dart Sass). `node-sass`/LibSass is dead.

### Structure options
| Pattern | For | Against |
|---|---|---|
| **7-1** (abstracts, base, components, layout, pages, themes, vendors) | Widely known; easy to navigate | Folder sprawl for a small theme; "pages" invites one-off CSS |
| **ITCSS** (settings → tools → generic → elements → objects → components → utilities) | Orders by specificity; prevents cascade fights | Less familiar; layer names need explaining |
| **Lean hybrid:** `tokens/`, `tools/` (mixins/functions), `base/`, `layout/`, `components/`, `utilities/`, plus `main.scss` | Right-sized for one theme; maps onto `@layer` | Your own convention, so document it |

Pair it with **native `@layer`** (`@layer reset, base, layout, components, utilities;`). The cascade order is then explicit, and a new component can't accidentally beat utilities.

### Tokens
- Keep source tokens in Sass maps (`$color`, `$space`, `$font`, `$radius`, `$breakpoint`) and **emit them as CSS custom properties** on `:root` (with a dark-mode override if you like). Components use `var(--color-text)`, so theming happens at runtime and React or other code can read the same tokens.
- Keep **breakpoints as Sass variables**, because custom properties don't work inside media queries.
- The W3C Design Tokens Community Group format reached a stable spec in 2025, so a JSON token file could become the single source later. A good "with more time" answer.

### Naming
- BEM (`.brand-card__rating--large`), optionally with ITCSS prefixes (`c-`, `l-`, `u-`). Lint with Stylelint (`stylelint-config-standard-scss`) and enforce `@use` order and the no-`@import` rule.

### Weak spots to acknowledge
- Native CSS now has nesting, custom properties, `@layer`, `color-mix()` and container queries, so Sass matters less. It still earns its place through modules, maps and loops (generating spacing utilities), mixins, and compile-time checks.
- Over-abstraction: a mixin for everything makes the CSS harder to read than the CSS it generates.

**Defend it:** "Tokens are the API: Sass maps emitted as custom properties. Partials follow cascade order and map onto `@layer`, so a new engineer adds `components/_thing.scss`, forwards it, and can't break specificity. Only `@use`, because `@import` is being removed."

---

## 8. Pillar 5: auth service

### Token format
| | For | Against |
|---|---|---|
| **Asymmetric JWT** (EdDSA/Ed25519 or ES256; RS256 is fine), auth service signs, publishes **JWKS**, main app verifies locally | No auth call per request; main app keeps working when the auth service is down; only the auth service holds the private key | **Revocation is hard**; role changes lag until expiry; token size |
| Opaque token + **introspection** (RFC 7662) | Instant revocation and role changes | The auth service is on every request's path: a single point of failure plus latency |
| Session cookie | Simple for one origin | Doesn't fit a separate service or an API-first client |
| HS256 shared secret | Simplest | Every verifier can also *mint* tokens; a secret leak in the main app compromises auth |

**Recommended hybrid:** JWT verified locally for reads and normal writes. **Access tokens live 5–15 minutes**, and a refresh token is held and rotated by the auth service (reuse detection revokes the whole family). For immediate revocation, the auth service exposes a `jti`/user denylist or a per-user `token_version` that the main app checks only for sensitive writes, or fetches as a small cached list.

### Validation checklist (the RFC 8725 JWT BCP, being revised as `draft-ietf-oauth-rfc8725bis`)
- **Pin the algorithm list** (`algorithms=["EdDSA"]`). Never derive it from the token header. Reject `none`.
- Check `iss`, `aud` (the main app's identifier), `exp`, `nbf`, `iat` with a small leeway; require `sub` and `jti`.
- **Explicit typing:** `typ: at+jwt` (RFC 9068) so ID tokens or other JWTs can't be replayed as access tokens.
- JWKS: cache with a TTL (5–60 minutes), select keys by `kid`, refetch once on an unknown `kid` (rate-limited), and overlap old and new keys for at least one token lifetime during rotation.
- **Library:** PyJWT **≥ 2.15.1** (`PyJWT[crypto]`). 2.13 fixed CVE-2026-48526 (a JWK-format public key accepted as an HMAC secret → forged HS256 tokens) and CVE-2026-48523 (allow-list bypass with PyJWK). 2.14.0 and 2.15.0 fixed 14 more advisories, including a critical HS/asymmetric key-confusion bypass. Accepting only `algorithms=["EdDSA"]` removes that whole class of bug. **Don't use python-jose:** it released 3.4.0 and 3.5.0 in 2025 after years without releases, but it has a weak security record and FastAPI dropped it. See `stack-decisions.md`.

### Roles and authorization
- The auth service is the source of truth: `Role` (reader, editor) → permissions. Put **permissions/scopes** in the token (`"scope": "brands:read brands:write"`) rather than only role names, so the main app checks capabilities and roles can change without code changes.
- Weak spot: claims go stale until the token expires. Say so, and point to the short TTL plus `token_version`.

### Migrating `wp_users`
- Options: (a) import users with unusable passwords and force a reset (the simplest; the challenge allows it); (b) **write a custom Django `PasswordHasher` that verifies WP hashes** (phpass `$P$…`, or WP ≥ 6.8's bcrypt `$wp$2y$…`). Django's `check_password` then re-hashes to Argon2 or PBKDF2 on the next successful login. Users keep their passwords and the legacy hashes disappear over time.
- Against (b): it's crypto-adjacent code you must test well. Disable the legacy hasher after a cutoff.
- Map WP roles: administrator → editor, subscriber/author → reader. Document the mapping.

### Login endpoint hardening
- Rate-limit by IP and username; constant-time behaviour for unknown users (Django patched a timing enumeration bug in Feb 2026); Argon2 hasher; never log tokens or passwords.

### When the auth service is down
- Local verification keeps reads and authorized writes working until the cached JWKS expires; serve a stale JWKS rather than failing closed for a bounded time. New logins fail, and that's acceptable. Revocation checks (if used) **fail closed** on the protected write.

**Defend it:** "The auth service owns identities, credentials and roles, and signs short-lived EdDSA JWTs. The main app verifies locally with a cached JWKS, so it doesn't depend on auth being up and adds no per-request latency. The cost is revocation lag, bounded by a 10-minute TTL plus a token-version check on the write path. Algorithms are pinned and `aud`/`typ` checked, because algorithm confusion is still producing CVEs in 2026."

---

## 9. Pillar 6: shared library

### What goes in (and what stays out)
- **In:** token verification (a pure-Python `verify(token, jwks, audience) -> Claims`), the claims schema and dataclass, the JWKS client and cache, the permission check (`has_scope`), and a **thin DRF adapter** (`authentication.py`, `permissions.py`).
- **Out:** models, settings, signing (*only the auth service signs*, so signing code in the shared library would put minting ability in the main app's import path), business logic.
- **Possibly in:** shared test fixtures for minting tokens with a test key, shipped as `[testing]` extras.

### Packaging and pinning
- `pyproject.toml` (hatchling or `uv_build`), SemVer, with `CHANGELOG.md`.
- Options: **uv workspace / local path** (monorepo; simplest; both services always in sync) vs **git URL at a tag** (independent pinning) vs a **private index** (proper releases).
- **Weak spots:**
  - Path dependencies mean both services always run the same version, which hides version skew until it hits production.
  - **Dependency confusion:** if the name isn't registered on PyPI and someone uses a public index, an attacker can register it. Use an organisation-prefixed name, reserve it, or pin the index.
  - If it's published, use trusted publishing plus attestations. PyPI now rejects late file uploads to old releases.

### Tests without Django
- Keep the core pure Python and test it with plain pytest. Test the DRF adapter with a tiny `settings.configure()` fixture, or make Django an optional extra (`pip install shared[drf]`) and skip those tests when it isn't installed.
- Must-have cases: expired token, wrong `aud`, wrong `iss`, `alg=none`, an HS256 token signed with the public key (the algorithm confusion case), unknown `kid`, missing scope.

### Breaking changes without a lockstep deploy (expand → migrate → contract)
1. Release **v2 that accepts both** the old and new token shapes (or a new `kid` or claim) in the verifier.
2. Deploy consumers (the main app) on v2.
3. Switch the issuer (auth service) to the new format.
4. Once old tokens have expired, release v3 that removes the old path.
- Include a `ver` claim or a versioned `typ` so verifiers can branch explicitly.

### The case against a shared library
- Coupling: "a distributed monolith". Every change ripples into both services.
- *Duplication is cheaper than the wrong abstraction.* Keep it tiny and justify every module.

**Defend it:** "Only verification and permission checks are shared, because the main app must never be able to sign. The core is framework-free, so it tests without Django. Breaking changes ship expand-then-contract: verifiers accept both formats before the issuer switches."

---

## 10. docker-compose for the new services

- Separate Postgres (or SQLite) per service; the main app gets **no credentials** for the auth database.
- Run as non-root, mount nothing from the host beyond source in dev, and don't mount the Docker socket.
- Pin base images (`python:3.13-slim@sha256:…` or a Docker Hardened Image).
- Secrets come from `.env` (already gitignored). The private signing key lives only in the auth container; the main app gets the JWKS URL.
- Add healthchecks and `depends_on: condition: service_healthy`, the same as the existing `db` service.

---

## 11. Likely probes: one-line answers

| Probe | Answer |
|---|---|
| Why not just use WP's REST API for migration? | It's incomplete (Yoast, users) and slow at scale; the DB is the source of truth |
| How do you re-run safely? | Upsert on `wp_id` inside a transaction; `--dry-run`; counts printed; deletes reported |
| How does it scale to 100x? | Batches, bulk upserts, set-based recompute, checkpointing |
| Store or derive the average? | Derive, keep a synced column for sorting, keep WP's value for audit |
| Revoke a token right now? | Short TTL, refresh-token revocation, `token_version` check on writes |
| Auth service is down? | Verification is local with cached JWKS; logins fail; writes needing revocation checks fail closed |
| Why this pagination? | Page numbers suit a grid with counts; cursor for mobile; always a tie-breaker |
| How do you trust AI output? | Plan first, small diffs, tests as contract, dependencies vetted, security checklist in the brief |
| What did you keep out of the shared library? | Signing, models, settings |
| A new engineer adds a component? | New partial → `@forward` → it lands in the `components` layer; tokens via `var()` |

---

## Sources

**Supply chain**
- [Unit 42: npm threat landscape](https://unit42.paloaltonetworks.com/monitoring-npm-supply-chain-attacks/) · [Trend Micro: Axios compromise](https://www.trendmicro.com/en_us/research/26/c/axios-npm-package-compromised.html) · [Microsoft: AsyncAPI import-time payload](https://www.microsoft.com/en-us/security/blog/2026/07/15/unpacking-asyncapi-npm-supply-chain-compromise-import-time-payload-delivery/) · [Microsoft: ChainDrop worm](https://www.microsoft.com/en-us/security/blog/2026/08/04/chaindrop-supply-chain-compromise-anatomy-self-propagating-worm/) · [Microsoft: npm dependency confusion](https://www.microsoft.com/en-us/security/blog/2026/05/29/33-malicious-npm-packages-abuse-dependency-confusion-profile-developer-environments/) · [Aikido: Keyv](https://www.aikido.dev/blog/keyv-and-friends-compromised-in-npm-supply-chain-attack) · [CSA Singapore advisory](https://www.csa.gov.sg/alerts-and-advisories/advisories/ad-2026-009/)
- [Datadog: LiteLLM/Telnyx (TeamPCP)](https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-teampcp-supply-chain-campaign/) · [Snyk: poisoned scanner → LiteLLM](https://snyk.io/blog/poisoned-security-scanner-backdooring-litellm/) · [The Hacker News: LiteLLM Oct 2026](https://thehackernews.com/2026/10/litellm-compromised-in-supply-chain.html) · [StepSecurity: durabletask](https://www.stepsecurity.io/blog/microsofts-durabletask-pypi-package-compromised-in-supply-chain-attack)
- [GitHub: npm token changes](https://github.blog/changelog/2025-10-10-strengthening-npm-security-important-changes-to-authentication-and-token-management) · [GitHub: plan for a more secure npm](https://github.blog/2025-12-15-our-plan-for-a-more-secure-npm-supply-chain/) · [Socket: npm minimumReleaseAge](https://socket.dev/blog/npm-introduces-minimumreleaseage-and-bulk-oidc-configuration) · [Nesbitt: package managers need to cool down](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html) · [pydevtools: uv supply chain protection](https://pydevtools.com/handbook/how-to/how-to-protect-against-python-supply-chain-attacks-with-uv/)
- [PyPI 2025 year in review](https://blog.pypi.org/posts/2025-12-31-pypi-2025-in-review) · [PyPI rejects files after 14 days](https://pydevtools.com/blog/pypi-rejects-new-files-after-14-days/)
- [Docker: Trivy compromise](https://www.docker.com/blog/trivy-supply-chain-compromise-what-docker-hub-users-should-know/) · [Docker: 2026 supply chain attacks](https://www.docker.com/blog/trivy-kics-and-the-shape-of-supply-chain-attacks-so-far-in-2026/) · [InfoQ: Docker Hardened Images](https://www.infoq.com/news/2025/12/docker-hardened-images)
- [Wiz: Pwn Request reckoning](https://www.wiz.io/blog/github-actions-security-pwn-request-reckoning) · [OWASP Top 10 2025 changes (GitLab)](https://about.gitlab.com/blog/2025-owasp-top-10-whats-changed-and-why-it-matters/)

**AI engineering**
- [CSA: Claude Code Action / Clinejection](https://labs.cloudsecurityalliance.org/research/csa-research-note-claude-code-github-action-prompt-injection/) · [CSA: AI agents as supply chain nodes](https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-agents-software-supply-chain-risk-20260/) · [arXiv 2607.15143: setup instructions vs agents](https://arxiv.org/pdf/2607.15143)
- [Veracode 2026 GenAI Code Security Report](https://www.veracode.com/blog/2026-genai-code-security-report-ai-risk/) · [METR Feb 2026 update](https://metr.org/blog/2026-02-24-uplift-update/) · [DORA 2025 report (PDF)](https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf)

**Frameworks and standards**
- [Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/) · [Django Feb 2026 security releases](https://djangoproject.com/weblog/2026/feb/03/security-releases)
- [JWT BCP revision draft](https://datatracker.ietf.org/doc/draft-ietf-oauth-rfc8725bis/) · [RFC 8725 / BCP 225](https://rfc-editor.org/info/bcp225) · [PyJWT CVE-2026-48526 (Tenable)](https://www.tenable.com/cve/CVE-2026-48526) · [PyJWT CVE-2026-48523](https://advisories.gitlab.com/pypi/pyjwt/CVE-2026-48523/) · [Debian PyJWT tracker](https://tracker.debian.org/pkg/src:pyjwt) · [FastAPI on python-jose](https://github.com/tiangolo/fastapi/discussions/9587)
- [React2Shell explained (JFrog)](https://research.jfrog.com/post/react2shell/) · [Sass: @import is deprecated](https://sass-lang.com/blog/import-is-deprecated/) · [Sass breaking change: @import](https://sass-lang.com/d/import)
- [DRF vs Ninja (loopwerk)](https://loopwerk.io/articles/2024/drf-vs-ninja)
