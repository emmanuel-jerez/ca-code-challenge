# 0017. Content Security Policy for scripts and styles, from a custom middleware

- Status: Accepted
- Date: 2026-11-09
- Supersedes: [0005](0005-custom-csp-middleware.md)

## Context
ADR 0005 chose a small custom middleware (Django 5.2 has no built-in CSP; django-csp
4.x doesn't declare Python 3.14) and named only `script-src 'self'`. The Pillar 3 and
Pillar 4 research found three things that policy doesn't cover:

- **Styles.** The WordPress templates have 7 inline `style="…"` attributes, counted in
  `wp-content/themes/consumer-reviews/`. A policy without `style-src` lets injected
  inline styles through. `docs/research/pillar-4-scss-architecture.md` §10 covers this.
- **Vite inlines small assets as `data:` URIs by default.** A policy without `data:` in
  `img-src`/`font-src` then blocks them (`docs/research/pillar-3-brandlist-component.md`
  §9).
- **Vite's dev server needs an inline preamble script** when loaded inside another
  page. 0005 rules out nonces, so that can't run inside a Django page.

## Options considered
- **Allow `'unsafe-inline'` for styles.** Rejected: it lets injected `style` attributes
  and elements through, and imported WordPress content is untrusted (ADR 0004).
- **Nonces or hashes.** Rejected: 0005 kept the middleware nonce-free on purpose, and
  hashes break whenever a template changes.
- **Allow `data:` for images and fonts.** Rejected: setting the build never to inline
  is one line and keeps the policy tighter.
- **Extend the policy to styles and constrain the build.** Chosen.

## Decision
- Unchanged from 0005: a ~20-line custom middleware sets the header from a settings
  value. It starts as `Content-Security-Policy-Report-Only` and switches to enforcing
  once reports are clean. No nonces.
- The policy names `script-src 'self'` **and** `style-src 'self'`, with no
  `'unsafe-inline'` in either.
- Django templates never use inline `style` attributes. The 7 in the WordPress
  templates become modifier classes in the SCSS tree (ADR 0023).
- The Vite production build sets `build.assetsInlineLimit: 0`, so it emits no `data:`
  URIs.
- The Vite dev server is never loaded inside a Django page. Front-end development runs
  on Vite's own page, which proxies `/api` to Django.

## Consequences
- The middleware's tests cover both directives and the report-only switch.
- A component that needs dynamic styling sets classes or CSS custom properties from
  stylesheets, never inline styles.

## Revisit when
Inline scripts or styles become necessary, django-csp declares Python 3.14, or the
project moves to Django 6.2 LTS (built-in CSP).

## Sources
- `docs/research/pillar-3-brandlist-component.md` §9 and Conflicts;
  `docs/research/pillar-4-scss-architecture.md` §10 and Conflicts.
- `docs/research/stack-decisions.md` §1 (the original options).
