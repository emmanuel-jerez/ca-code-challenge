# 0023. SCSS: prefixed BEM, a global partial for `<BrandList />`, Sass as the linter

- Status: Accepted
- Date: 2026-11-09

## Context
ADR 0011 chose `sass` and ruled out Tailwind and CSS-in-JS. SCSS was chosen for being
close to CSS, with long history and documentation. Three questions were still open:
- how `<BrandList />` consumes the SCSS tree;
- how classes are named;
- what enforces the architecture.

From `docs/research/pillar-3-brandlist-component.md` §8 and
`docs/research/pillar-4-scss-architecture.md` §5–9:

- The WordPress class names have no structure, and some leak: `.review-byline` and
  `.meta` render unstyled in some templates.
- Server-rendered pages and `<BrandList />` both render brand cards.
- stylelint 17 with `stylelint-config-standard-scss` is 126 packages, 12 of them from the
  keyv/cacheable family. That maintainer's account was hijacked on 2026-08-04. stylelint
  18 drops that chain, but `stylelint-scss` doesn't support 18 yet.
- Five `sass` minor releases in the past year shipped "potentially breaking" changes.
  Dart Sass 2.0 is planned for December 2026.
- `--fatal-deprecation=1.107.0` turns every current deprecation, `@import` included,
  into an error. The `dart-sass-2` preset still lets `@import` through. The spelling in
  the Sass blog (`--fatal-deprecations`) is rejected by the CLI.

## Options considered
**`<BrandList />` styles:**
- **Co-located CSS Modules.** Rejected: hashed names can't be reused by Django
  templates, so card styles would be duplicated.
- **A hybrid of global and module styles.** Rejected: two mechanisms to explain.
- **A global BEM partial in `frontend/scss/`.** Chosen.

**Naming:**
- **Keep the WordPress names.** Rejected: they carry the leaks and show no structure,
  which is what's graded.
- **Plain BEM.** Rejected: it can't tell layout from component from utility.
- **Utility classes.** Rejected: that's Tailwind's approach, which ADR 0011 rejected.
- **BEM with layer prefixes.** Chosen.

**Linting:**
- **stylelint 17 now.** Rejected: its dependency tree.
- **Wait for stylelint 18.** Deferred until `stylelint-scss` supports it.
- **Sass's own errors plus a test on the compiled CSS.** Chosen.

**Pin:**
- **A caret range.** Rejected: minor releases ship breaking fixes.
- **An exact version.** Chosen.

## Decision
- **Naming:** BEM with layer prefixes: `l-` for layout, `c-` for components and `u-` for
  utilities (e.g. `c-card__title--featured`). A WordPress→BEM table goes in the README.
- **`<BrandList />`:** styled by a global partial, `components/_brand-list.scss`, in the
  shared tree. It reuses the same `c-card` block as the server-rendered pages. Token and
  tool modules emit no CSS, so a CSS Module can still `@use` them later.
- **No stylelint for now.** Two things enforce the architecture:
  - Sass compiles with `--fatal-deprecation=1.107.0 --no-error-css`;
  - a test on the compiled CSS checks class names against the prefix pattern, raw
    colors outside tokens, rules outside a layer, `!important`, and specificity.
- **`sass` is pinned exactly to `1.107.1`,** and upgraded deliberately.

## Consequences
- `<BrandList />` depends on the theme stylesheet being on the page; it isn't
  self-contained.
- Moving off `1.107.1` means updating the `--fatal-deprecation` version in the same
  change.
- The compile command in `docs/research/stack-validation.md` §3.5 lacks these flags;
  the Pillar 4 note has the corrected one.

## Revisit when
- A second React component appears (reconsider a hybrid).
- `stylelint-scss` supports stylelint 18 and both are past the cooldown.
- Dart Sass 2.0 ships.

## Sources
`docs/research/pillar-3-brandlist-component.md` §8; `docs/research/pillar-4-scss-architecture.md` §5–9.
