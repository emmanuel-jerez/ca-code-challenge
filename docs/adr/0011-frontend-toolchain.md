# 0011. Frontend: React 19 + Vite 8, client-only, TypeScript 6 strict

- Status: Accepted
- Date: 2026-11-09

## Context
One React component mounted into a Django-rendered page, plus SCSS compiled from
`frontend/scss/`. In December 2025 React Server Components had a critical,
unauthenticated remote-code-execution bug (React2Shell, CVE-2025-55182) with follow-up
CVEs.

## Options considered
- **Next.js / server components.** Rejected: adds a server-side React runtime (the
  React2Shell surface) that one component doesn't need.
- **Vite 7.** Rejected: `@vitejs/plugin-react` 6 requires Vite 8.
- **Test wrappers `vitest-axe` / `jest-axe`.** Rejected as stale; call `axe-core`
  directly.
- **`sass-embedded`.** Rejected in favor of `sass` (pure JS, no native binary).
- **Tailwind / CSS-in-JS.** Rejected: the challenge grades SCSS structure, and reusing
  the SCSS tokens avoids a second styling system.

## Decision
React 19, Vite 8, TypeScript ~6.0 strict (`noUncheckedIndexedAccess`,
`exactOptionalPropertyTypes`), `sass`, Vitest 5 + jsdom + Testing Library +
`axe-core`, Zod (ADR 0010). Node `^24.15.0 || >=26`. pnpm only, with
`minimumReleaseAge: 10080` (ADR 0012).

## Consequences
- If ESLint is added, use ESLint 9: `eslint-plugin-jsx-a11y` doesn't support 10.
- Vite shipped releases on five version lines on 2026-11-09 with no advisory yet; the
  cooldown holds them back.

## Revisit when
A second page or app needs routing/SSR, or TypeScript 7 tooling matures.

## Sources
`docs/research/stack-validation.md` §3.5–3.6; `docs/research/best-practices-2026.md` §6–7.
