# 0013. Validation and typing patterns

- Status: Accepted
- Date: 2026-11-09

## Context
The user asked for Python equivalents of TypeScript's Zod (one schema for runtime
validation and types), Effect (typed errors, dependency injection, composable effects)
and a fully typed codebase. The stack is DRF on Django 5.2 / Python 3.14.

## Options considered
- **Zod equivalent:** Pydantic v2 (rejected for DRF services: a second validation
  system; rejected for the shared library: it would force a Pydantic version onto both
  services), msgspec and attrs+cattrs (extra dependencies for little gain), DRF
  serializers at the HTTP boundary plus stdlib dataclasses elsewhere (chosen).
- **Effect equivalent:** `returns` (heavy, unidiomatic in Django), `result` (archived
  2026-06-25; maintainers said the style doesn't fit Python), small Effect ports
  `pyeffect`/`effectpy` (unvetted). All rejected in favor of stdlib typing.
- **On the frontend:** Effect rejected (too much framework for one component); plain
  TypeScript + Zod chosen.

## Decision
- Validate at boundaries: DRF serializers for requests; frozen dataclasses for WP
  import rows and JWT claims; Zod for API responses.
- Narrow unknown values with type guards first (`TypeIs`/`TypeGuard`, TS `x is T`
  predicates, Zod). `Any`/`any` only when a guard can't express it, with a comment.
- Typed exception hierarchies, unions with `match`/`assert_never`, PEP 695 generics,
  Protocols for injection.
- No `from __future__ import annotations` (Python 3.14 defers annotations natively).

## Consequences
`validated_data` from DRF is untyped; convert it to a dataclass at the view boundary
where static types matter.

## Revisit when
The API moves to Ninja/Pydantic, or a typed-effects library becomes mainstream in
Python.

## Sources
`docs/research/typing-and-validation.md` §1–2.
