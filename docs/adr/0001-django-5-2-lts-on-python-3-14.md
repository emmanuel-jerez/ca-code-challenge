# 0001. Django 5.2 LTS on Python 3.14

- Status: Superseded by [0014](0014-raise-the-django-floor.md)
- Date: 2026-11-09

## Context
Both Django services and the shared library need one target. On this date Django's
newest release is 6.1.x; 5.2 is the LTS (security fixes until April 2028); 4.2 went
end of life in April 2026. The `django-lts` skill already pinned 5.2. A February 2026
security release fixed three ORM SQL-injection CVEs reached through `order_by` and
aliases.

## Options considered
- **Django 6.0/6.1.** Built-in CSP (`SECURE_CSP`), template partials, a tasks
  framework. Rejected: not LTS, shorter support.
- **Django 5.2 LTS.** Chosen. Missing 6.x features are replaced by small pieces (CSP:
  ADR 0005; partials: `{% include %}`).
- **Python 3.13.** Wider package support. Rejected: 3.14 is the newest version 5.2.8+
  supports, and every compiled dependency we chose ships 3.14 wheels.

## Decision
`Django>=5.2.8,<5.3`, `requires-python = ">=3.14,<3.15"`. User input never reaches
`order_by()`, `annotate()`/`alias()` names, `values()` or `extra()`; sort and filter
params map through allow-lists.

## Consequences
- Docs lookups must target 5.2, not latest.
- Pure-Python packages without a 3.14 classifier need explicit approval (gunicorn:
  ADR 0008).
- On this date 5.2.19 (a GIS-only security fix, 2026-11-03) is held back by the
  cooldown until 2026-11-10 (ADR 0012).

## Revisit when
Django 6.2 LTS ships (expected April 2027), or a needed package drops 5.2.

## Sources
`.agents/skills/django-lts/SKILL.md`; `docs/research/best-practices-2026.md` §4;
`docs/research/stack-validation.md`.
