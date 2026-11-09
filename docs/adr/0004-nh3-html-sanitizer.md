# 0004. nh3 for sanitizing WordPress HTML

- Status: Accepted
- Date: 2026-11-09

## Context
`post_content` for reviews is user-submitted HTML. Rendering it with `|safe` is stored
XSS. The `django-lts` skill treats choosing a sanitizer as a dependency decision.

## Options considered
- **nh3** (bindings to the Rust `ammonia` sanitizer). Allow-list API, Python 3.14
  wheels. Chosen.
- **bleach.** Rejected: its maintainers announced no more releases, including security
  fixes.
- **lxml-html-clean.** Rejected: its own README says it isn't suitable for security.
- **justhtml.** Credible newcomer, but under a year old with no security record.

## Decision
`nh3>=0.3.7,<0.4`, with an explicit allow-list that never includes `style`, `svg`,
`math` or `animate*`. Sanitize before output; tests include known XSS payloads.

## Consequences
nh3 0.3.7 bundles ammonia 4.1.4, which has three open medium advisories (October
2026). All require SVG animation tags or `style` to be allowed, which our allow-list
forbids. The fix is merged upstream but unreleased.

## Revisit when
nh3 releases the ammonia fix, or the allow-list needs any of the forbidden tags.

## Sources
`docs/research/stack-decisions.md` §3.
