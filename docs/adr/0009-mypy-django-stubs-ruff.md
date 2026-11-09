# 0009. mypy strict with django-stubs, plus Ruff

- Status: Accepted
- Date: 2026-11-09

## Context
The code should be fully typed, and the type checker must understand Django models,
managers and querysets. Django is pinned to 5.2 (ADR 0001).

## Options considered
- **mypy + django-stubs plugin.** The only checker that fully understands the ORM.
  Chosen.
- **pyright / basedpyright.** Fast, good editor support. Rejected as the gate: partial
  Django ORM understanding.
- **ty (Astral).** Needs `django-types` rather than django-stubs; young. Rejected.
- **pyrefly (Meta).** Python 3.14 support unverified. Rejected.

## Decision
- mypy in strict mode with `django-stubs[compatible-mypy]` and
  `djangorestframework-stubs[compatible-mypy]`.
- Ruff with ANN (annotations), S (security), TC (type-checking imports), DJ (Django),
  PGH, and TID251 banning Django 6.x-only imports.

## Consequences
- djangorestframework-stubs 3.18.1 caps mypy below 2.4, so mypy is 2.3.1 until stubs
  3.18.2 clears the cooldown (2026-11-09 23:46 UTC), then mypy `>=2.4.1,<2.5`.
- The DRF stubs require django-stubs 6.1+, which describes Django 6.x and can't be
  restricted to 5.2. mypy won't flag 6.x-only APIs; TID251 and tests on 5.2 catch them.
- Ruff's TC rules must be configured so Pydantic-style runtime annotations aren't moved
  under `TYPE_CHECKING` (relevant if any runtime-annotation library is added).

## Revisit when
django-stubs or the DRF stubs change their mypy caps, or another checker gains full
Django support.

## Sources
`docs/research/typing-and-validation.md` §3; `docs/research/stack-validation.md` §2.3–2.4.
