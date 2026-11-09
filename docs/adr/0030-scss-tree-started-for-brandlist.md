# 0030. The SCSS tree, started early for `<BrandList />`

- Status: Accepted
- Date: 2026-11-09

## Context
ADR 0028, item 3: the user chose to build a minimal SCSS tree in Pillar 3, so
the component is styled now instead of waiting for Pillar 4. That tree
settles some of the Pillar 4 note's open decisions
(`docs/research/pillar-4-scss-architecture.md`, "Open decisions" 1, 3–6 and
part of 10). ADR 0023 had already fixed the naming (prefixed BEM), the global
partial for the component, the exact `sass` pin and the enforcement approach.

The user accepted the Pillar 4 note's recommendations for the parts built,
and chose to ship the compiled-CSS test now rather than with Pillar 4. Item 6
below is a default the agent took, flagged for review.

## Options considered
1. **Tree shape.** 7-1 and ITCSS were rejected: empty folders, or seven tiers
   for a few dozen rules. A slim tree with one folder per cascade layer was
   chosen.
2. **Token values.** One token per WordPress value was rejected as a lookup
   table. Normalizing everything to a 4px scale was rejected because it
   changes the output in 13 places. A hybrid was chosen: a scale for
   recurring values, and one-off WordPress values kept in their component
   with a `// WP value, off-scale` comment.
3. **Custom property names.** Keeping the 15 WordPress names was rejected:
   role names (`--color-text-muted`, `--color-surface`, `--radius-md`) say
   what a value is for, and WordPress content doesn't reference the old ones.
4. **Breakpoints.** Mobile-first was rejected for now: the WordPress CSS is
   desktop-first, and equivalence is graded. `below()` uses range syntax.
5. **Where layers are declared.** Wrapping partials with `meta.load-css` in
   each index was rejected: it nests layers and emits CSS on every call.
   Each partial declares its own `@layer`, and a test checks every rule.
6. **Accessibility changes to the WordPress CSS** (open decision 10, not put
   to the user): no root `font-size: 16px`, which overrode the reader's
   browser setting; a `:focus-visible` ring; hover lift and transitions only
   under `prefers-reduced-motion: no-preference`; a 3:1 border on the sort
   select, where the theme's border color is 1.24:1.
7. **When the compiled-CSS test arrives.** Deferring it to Pillar 4 was
   rejected: the first partials would go in unchecked.

## Decision
- `frontend/scss/`: `theme.scss` loads `_layers.scss` first (the one
  `@layer reset, tokens, base, layout, components, utilities;` statement),
  then `tokens/_custom-properties.scss`, `base/`, `layout/`, `components/`
  and `utilities/`.
- `tokens/` and `tools/` emit no CSS. Primitives are private; semantic maps
  are public, with a `$color-overrides` map for a second theme. Only
  `_custom-properties.scss` emits `:root`, in `@layer tokens`.
- Getters (`t.color("text-muted")`, `t.space(4)`, …) return the custom
  property and stop the build on an unknown name.
- Built now: `l-container`, `l-section`, `l-grid` (intrinsic, no media
  query), `c-card`, `c-badge`, `c-stars`, `c-pagination`, `c-brand-list`
  (container queries) and `u-visually-hidden`. Pillar 4 adds the rest.
- `frontend/scss/theme.test.ts` compiles with `--fatal-deprecation=1.107.0`'s
  policy and checks: one layer statement first, every rule in a layer,
  prefixed BEM class names, raw colors only in the tokens layer (including
  named colors in color properties), no `!important`, no ids and at most two
  classes or states per selector, and that a token typo fails the build.

## Consequences
- Pillar 4 extends this tree instead of designing it from scratch. Its
  remaining open decisions (build and delivery, the equivalence report) are
  unchanged.
- Some token names were added beyond WordPress's: `danger` (error border),
  `primary-subtle-border`, `border-strong`, and the font-size steps.
- The output isn't yet compared with `reference/theme.css`; that's Pillar 4's
  equivalence report.

## Revisit when
Pillar 4 compares the output with `reference/theme.css`, Dart Sass 2.0 ships
(ADR 0023), or a second theme is needed.

## Sources
`docs/research/pillar-4-scss-architecture.md` §2–4, §6, §9–11 and "Open
decisions"; ADR 0023.
