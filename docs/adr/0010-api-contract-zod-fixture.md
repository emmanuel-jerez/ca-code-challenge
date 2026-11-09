# 0010. API contract: a Zod schema checked against a shared JSON fixture

- Status: Accepted
- Date: 2026-11-09

## Context
The React `<BrandList />` consumes one endpoint, `GET /api/brands/`, with about eight
fields per row. API and UI drift should fail CI, and the UI must handle bad responses
(the challenge grades the error state).

## Options considered
- **drf-spectacular → committed OpenAPI file → openapi-typescript → TS types.**
  Rejected: openapi-typescript 7.13.0 requires TypeScript 5 (we use 6), has had no
  release since February 2026 and its fixes are unmerged; drf-spectacular has no CI on
  DRF 3.18, no commits since July, and adds 9 packages.
- **Downgrade to TypeScript 5 to keep the generator.** Rejected: TS 6 is the bridge to
  TS 7, and a stalled generator could hold the project on 5.
- **Hand-written Zod schema + a contract fixture.** Chosen.

## Decision
- A pytest test writes (or compares) `contracts/brand-list.example.json` from the real
  serializer output.
- A Vitest test `safeParse`s that file with the Zod schema; the TS type comes from
  `z.infer`.
- The frontend also `safeParse`s live responses and shows the error state on failure.

## Consequences
Zero extra Python dependencies; doesn't scale to many endpoints.

## Revisit when
A second client (e.g. mobile) or several more endpoints appear: add OpenAPI generation
then, once the tools support the TypeScript version in use.

## Sources
`docs/research/stack-validation.md` §2.1–2.2, §4; `docs/research/typing-and-validation.md` §4.
