# Pillar 4: SCSS architecture

Researched 2026-11-09.

**Scope.** This note covers the SCSS source tree under `frontend/scss/` that compiles to CSS equivalent to `reference/theme.css`. It goes into implementation detail on six things:
- an inventory of `theme.css`
- the tree shape and how it maps to `@layer`
- the Sass module system and tokens
- the state of Dart Sass in late 2026
- naming, compiling, verifying and linting
- extensibility, and how the tree fits the CSP

It builds on `best-practices-2026.md` §7 and `stack-validation.md` §3.5, corrects them where needed, and doesn't repeat them. Pillar 3 (`<BrandList />`) is covered elsewhere. This note only says what the tree offers the component.

> **How claims were checked.**
> - **Docs:** Context7 first (Sass, Vite 8.3.5, stylelint, stylelint-scss, pnpm), then sass-lang.com, GitHub, MDN, W3C and OSV.
> - **Sass behaviour:** a throwaway prototype in the session scratchpad, compiled with the accepted `sass@1.107.1` through `pnpm dlx` [14]. Nothing was written to or installed into the repo.
> - **Dependency counts:** lockfile-only resolutions with pnpm 12.16.1 and `minimumReleaseAge: 10080`. This step fetches metadata only: no tarballs, no scripts [18].
> - **Secondary sources:** claims marked *(secondary)* come from them. Nothing here relies on one.

---

## Key findings

1. **`theme.css` is small, flat and not BEM** [1]:
   - 62 rules, 195 declarations, 15 custom properties, one breakpoint, no `!important`, no IDs.
   - 34 of 63 selectors use a descendant combinator, and 19 of those end in a bare element (`.card h3 a`).
   - It's identical to the WP theme's `style.css` below the header comment, so no build step ever existed.
2. **Tokens exist but leak.** 16 distinct hex values appear 28 times: 10 in `:root` and 18 raw in rules, 9 of them `#ffffff`. 14 of the 16 are Tailwind CSS v3 palette values (teal, amber, gray, emerald) [1][28]. `--color-accent` is defined and never used [1].
3. **Descendant naming already causes bugs.** In WP, `.review-byline` on the single-review page and `.meta` outside `.card` end up unstyled, because their rules only match inside `.review-item` and `.card` [1]. BEM's one-class-per-element rule removes this kind of bug.
4. **The WP templates carry 7 inline `style=""` attributes in 5 files.** A CSP without `'unsafe-inline'` blocks them [1][25]. The tree must ship modifier classes that replace them.
5. **Dart Sass 2.0 is targeted for December 2026** [4]:
   - `sass` 1.107.1 (2026-10-30) is the newest version past the cooldown. 1.108.x waits [3].
   - `--fatal-deprecation=1.107.0` makes every active deprecation an error, `@import` and global built-ins included. Verified [14].
   - The new `dart-sass-2` value (1.107.0) does **not** cover `@import`, global built-ins or legacy `if()`. Verified [2][14].
   - The blog's `--fatal-deprecations` (plural) spelling is rejected by the CLI [4][14].
6. **Deprecation list correction:**
   - `mixed-decls` has been obsolete since 1.92.0 (2025-09-02), not active [2][7].
   - Sass ships "potentially breaking" changes in minor releases: five in the last 12 months, plus a rollback in 1.108.0 [2].
   - So pin `sass` exactly and read the changelog on every upgrade.
7. **`sass` resolves to 11 packages, plus one platform binary for its optional watcher** [18]:
   - Its declared ranges still admit versions of `immutable` (5.1.5–5.1.7) and `source-map-js` (≤1.2.1) that have High advisories from 2026 [15][16].
   - A fresh lockfile resolves to fixed versions (5.1.9, 1.2.2) [18].
   - Real exposure is low, because Sass only compiles our own trusted files.
8. **Stylelint is the riskiest piece of tooling on offer:**
   - stylelint 17 + `stylelint-config-standard-scss` comes to **126 packages**.
   - 12 of them are from the keyv/cacheable family, whose maintainer account was compromised on 2026-08-04. Trojanized `file-entry-cache` 11.1.6, `flat-cache` 6.1.24 and others were published [17][18].
   - stylelint 18 (2026-11-03, still in cooldown) drops `file-entry-cache` and comes to 30 packages [19][18]. But `stylelint-scss` 7.4.0 only supports stylelint `^16.8.2 || ^17` [3].
9. **Layer order has a trap** [14][22]:
   - `@use` must come before every other rule, and a module's CSS is emitted where it's `@use`d.
   - So a `@layer a, b, c;` statement written after the `@use` lines lands *after* component CSS and silently reorders the layers.
   - Fix: put the statement in `_layers.scss` and `@use` it first in every entry point.
   - `meta.load-css()` emits CSS every time it's included, and wrapping it in a layer can nest layers.
10. **Pure token modules make multiple entry points safe.**
    - `tokens/` and `tools/` emit no CSS, so `theme.scss` and a component stylesheet can both `@use` them without duplicating anything. Verified [14].
    - A token getter that `@error`s on unknown names turns `var(--typo)` (which fails silently) into a build failure [14].
11. **Interpolation drops quotes.** Emitting the font stack with `#{$value}` turns `"Segoe UI"` into `Segoe UI`. `meta.inspect($value)` keeps the quotes [14].
12. **CSP fit is easy for the stylesheet itself** [1][21]:
    - `theme.css` has no `url()`, no `@font-face` and no `@import`, so `style-src 'self'` is enough. `font-src` and `img-src` are unaffected.
    - Vite's dev server injects `<style>` tags, while production builds emit `.css` files.
    - The Sass CLI writes an "error CSS" file on failure by default. Use `--no-error-css` [8][14].

---

## 1. Inventory of `theme.css`

All counts come from a stdlib Python pass over `reference/theme.css` [1].

### 1.1 Shape

| Metric | Value |
|---|---|
| Rules / declarations | 62 / 195 (15 of them custom properties) |
| Selectors | 63. 34 use a descendant combinator; 19 end in a bare element |
| Max specificity | (0,3,0) `.pagination .page-numbers.current` |
| Other hot spots | (0,2,1) `.site-nav a:hover`, `.brand-hero .brand-meta strong`; (0,1,2) `.card h3 a`, `.review-item h3 a` |
| `!important` / IDs | 0 / 0 |
| `url()`, data URIs, `@font-face`, `@import` | none |
| Media queries | 1: `@media (max-width: 640px)` with 4 rules (desktop-first) |
| Naming | Flat classes plus element descendants. WP's `paginate_links()` classes (`.page-numbers`, `.current`) |

### 1.2 Colours

"var" means the colour is used through its custom property. "raw" means a hard-coded hex in a rule. The Tailwind names are matches against the v3.4.17 palette [28].

| Hex | Tailwind v3 | Defined as | Uses | Where | Proposed semantic token |
|---|---|---|---|---|---|
| `#ffffff` | white | `--color-card` | 1 var, **9 raw** | 7 surfaces (header, brand/review hero, `.content`, review item, page body, pagination), 2 text-on-primary | `--color-surface`, `--color-text-inverse` |
| `#1a1a1a` | — (custom) | `--color-text` | 8 var | body, titles, links in titles | `--color-text` |
| `#e5e7eb` | gray-200 | `--color-border` | 8 var | 5 `border`, 3 `border-bottom` | `--color-border` |
| `#0f766e` | teal-700 | `--color-primary` | 5 var, 1 raw | links, nav hover, current page, hero gradient start | `--color-primary` |
| `#6b7280` | gray-500 | `--color-muted` | 3 var | meta, byline, brand meta | `--color-text-muted` |
| `#f7f7f5` | — (custom) | `--color-bg` | 1 var | page background | `--color-bg` |
| `#115e59` | teal-800 | `--color-primary-dark` | 1 var | badge text | `--color-primary-strong` |
| `#f59e0b` | amber-500 | `--color-accent` **and** `--color-star` | 1 var (star); accent unused | stars | `--color-accent`; star becomes a component token |
| `#d1d5db` | gray-300 | `--color-star-empty` | 1 var, 1 raw | empty star; footer text | split: `--color-icon-muted`, `--color-text-on-dark` |
| `#134e4a` | teal-900 | — | 1 raw | hero gradient end | `--color-primary-deep` |
| `#374151` | gray-700 | — | 1 raw | card excerpt | `--color-text-subtle` |
| `#1f2937` | gray-800 | — | 1 raw | review body | near-duplicate of `--color-text` |
| `#111827` | gray-900 | — | 1 raw | footer background | `--color-surface-inverse` |
| `#9ca3af` | gray-400 | — | 1 raw | footer link | `--color-link-on-dark` |
| `#ecfdf5` | emerald-50 | — | 1 raw | badge background | `--color-primary-subtle` |
| `#d1fae5` | emerald-100 | — | 1 raw | badge border | `--color-primary-subtle-border` |
| `rgba(0,0,0,.04)` / `.06` | — | `--shadow-sm` / `--shadow` | 1 / 1 | card rest / hover | `--shadow-sm` / `--shadow-md` |

**Near-duplicate groups:**
- **Three body-text greys:** `#1a1a1a`, `#1f2937`, `#374151`.
- **Two amber tokens with the same value:** `--color-accent` and `--color-star`.
- **A badge tint from a different family:** emerald-50/100, while the brand colour is teal. Tailwind's teal-50 is `#f0fdfa` [28].

### 1.3 Typography

| Property | Values (count) |
|---|---|
| `font-family` | 1 system stack, via `--font-sans`. No web fonts |
| `font-size` (15 distinct) | 0.95rem ×4, 0.9rem ×4, 1.75rem ×3, 1.1rem ×2, 0.85rem ×2, and once each: 16px (root), 0.78, 0.92, 1.02, 1.05, 1.25, 1.4, 1.5, 2, 2.25rem |
| Near-duplicate sizes | 0.9 / 0.92 / 0.95rem; 1.02 / 1.05 / 1.1rem; 1.4 / 1.5rem |
| `font-weight` | 600 ×5, 700 ×2, 500 ×1 |
| `line-height` | 1.55 ×1 |
| `letter-spacing` | −0.01em ×3, −0.02em ×2, 0.01em, 0.04em, 1px |
| `text-transform` | uppercase ×1 |

### 1.4 Spacing (padding, margin, gap)

The theme uses 19 distinct px values, 47 times in total [1].

| px | 2 | 3 | 4 | 6 | 8 | 10 | 12 | 14 | 16 | 18 | 20 | 22 | 24 | 28 | 32 | 40 | 48 | 56 | 64 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| uses | 1 | 1 | 1 | 1 | 4 | 2 | 6 | 2 | 1 | 3 | 1 | 3 | 7 | 1 | 4 | 2 | 3 | 1 | 3 |

- **On a 4px grid:** 34 uses (12 values).
- **Off the grid:** 13 uses of 2, 3, 6, 10, 14, 18 and 22px. Examples: card padding 22px, header padding 18px, badge padding 3px 10px.

### 1.5 Everything else

| Kind | Values |
|---|---|
| Radii | `--radius` 10px ×4, 999px (pill) ×1, 6px (pagination) ×1 |
| Borders | `1px solid var(--color-border)` ×8; `1px solid #d1fae5` ×1 |
| Shadows | 2 tokens, 1 use each |
| Motion | `transition: box-shadow .15s, transform .15s` ×1; `translateY(-1px)` on hover |
| Opacity | 0.92 ×1 (hero lead) |
| z-index | none |
| Layout | container `--max-width` 1100px plus a 24px gutter; grid `minmax(280px, 1fr)` with gap 20px; hero lead `max-width: 640px` (a measure, unrelated to the breakpoint) |
| Breakpoints | one: `max-width: 640px` |
| Theming / dark mode | none (no `prefers-color-scheme`) |

### 1.6 Components and layout pieces

- **Base:** `*` box-sizing, `html, body`, `a`, `a:hover`, `img`.
- **Layout:** `.container`, `.grid`, `.section`, `.section-header`, `.brand-body`, `.reviews-section`.
- **Components:** site header, title and nav; hero; card; stars; badge; brand hero with meta; content box; review item; review hero; site footer; page body; pagination.

### 1.7 Dead, duplicated and fragile rules

- **Dead or redundant:**
  - `--color-accent` is never read.
  - `.review-hero .brand-link { color }` is overridden for the link inside it by `a { color }`, which has the same value.
  - `html, body` sets the background, colour and font on both.
- **Repeated patterns:**
  - A "panel" (white background, border, radius, padding) appears 4× (`.card`, `.brand-body .content`, `.review-item`, `.page-body`).
  - A "white band with a bottom border" appears 3× (`.site-header`, `.brand-hero`, `.review-hero`).
  - A "title link in text colour" appears 3×.
- **Source-order fights:**
  - `.section-header h2 { margin: 0 }` beats `.section h2 { margin: 0 0 24px }` only because it comes later. Both are (0,1,1).
  - The mobile `.hero h1` override depends on the media query being last.
- **Leaks** (template markup vs. CSS scope):
  - `.review-byline` in `single-review.php` sits outside `.review-item`.
  - `.meta` appears outside `.card` in `single-brand.php` and in the "No reviews yet" message.
  - `.content` is reused on review pages through `.brand-body`.
- **Inline styles in templates** (7 in total; replacement classes are in §10):
  - `front-page.php`: 1
  - `archive-brand.php`: 2
  - `archive-review.php`: 2
  - `single-brand.php`: 1
  - `single-review.php`: 1
- **WP content HTML** (`db/dump.sql`):
  - The main tags are `<p>`, `<h2>`, `<strong>` and `<blockquote>`.
  - A few `wp-block-*` classes come from the default privacy page.
  - There are no `style=` attributes and no `var(--…)` references, so renaming custom properties breaks nothing in the content.

**Accessibility notes for deliberate deviations.** Contrast is computed with the WCAG 2.2 formula [31].
- **`font-size: 16px` on `html`** overrides the user's default font size.
- **No focus styles.** `a:hover` underlines, but focus doesn't.
- **Links vs. body text is 3.18:1.** That's enough only if a non-colour cue (an underline) also appears on focus.
- **Muted text on the page background is 4.51:1.** That's right at the AA limit of 4.5:1, so `--color-text-muted` must never sit on anything darker than `--color-bg`.
- **Stars:** full amber on white is 2.15:1 and empty is 1.47:1. The glyph shapes differ (★/☆) and WP adds an `aria-label`, but the numeric value should stay visible.
- **The card hover lift** has no `prefers-reduced-motion` guard.

---

## 2. Tree structure

| Option | What it is | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|---|
| **7-1** [26] | `abstracts/ base/ components/ layout/ pages/ themes/ vendors/` + `main.scss` | None (no tooling) | Well known. But the canonical guide still shows `@import` and never mentions `@use` [26] | Low | Three empty folders here (no vendor CSS, no themes). `pages/` invites one-off CSS. Header and footer counted as "layout" blurs skin vs. layout |
| **ITCSS** [27] | Settings → Tools → Generic → Elements → Objects → Components → Utilities, ordered by reach and specificity | None | Stable idea. The reference framework (inuitcss) uses `@import` and was last pushed 2023-03-01 [27] | Medium | Seven layers for 62 rules. "Objects" vs. "components" needs explaining. Native `@layer` now does the ordering job ITCSS did by file order |
| **Slim layered tree** | `tokens/ tools/ base/ layout/ components/ utilities/`, mapped 1:1 to `@layer reset, tokens, base, layout, components, utilities` | None | Uses only stable Sass (`@use`/`@forward`) and `@layer` (Baseline widely available since 2024-09-14) [23] | Low | It's a house convention, so it needs a short README section |

**Recommendation.** The slim layered tree. Each folder maps to exactly one cascade layer, declared once in `_layers.scss`, so the file system and the cascade tell the same story.
- **Skip `pages/`.** Page differences become modifiers.
- **Skip `vendors/` and `themes/`.** Nothing would go in them.

**Defend it.** "Six folders, six layers, same order. Folder position tells you where a file sits in the cascade, and `@layer` enforces it, so a new component can't out-specify a utility. I dropped 7-1's empty folders and ITCSS's extra tiers because 62 rules don't need them."

---

## 3. Module system

### What the rules are (verified on `sass` 1.107.1)

- **`@use` comes first.** It must come before every rule except `@forward` and variable declarations. A `@layer` statement before it is an error [14].
- **CSS is emitted where the module is `@use`d.** That's what causes the layer-order trap in Key finding 9 [14].
- **A module is evaluated once per compilation, and its CSS is emitted once,** however often it's `@use`d through the graph. Verified: a partial `@use`d twice appeared once [9][14].
- **`with (...)` configures a module only on its first load.** A second configured `@use` fails with "This module was already loaded, so it can't be configured using `with`" [9][14].
- **Only top-level `!default` variables can be configured** [13].
- **Configuring private variables (`$-x`) is deprecated** (`with-private`, 1.92.0) and becomes an error in 2.0 [2][4][14].
- **`@forward` re-exports a module's members:**
  - `show`/`hide` limit what's exported. `as prefix-*` renames.
  - `@forward ... with (... !default)` lets an index change defaults while still allowing downstream overrides.
  - Write `@forward` before `@use` when a file has both [10].
- **`meta.load-css()` emits the module's CSS every time it's included.** A module loaded twice appeared twice. Inside `@layer components {}` it nests any layer the partial declares (`components.components`) [11][14].
- **`meta.load()` and `meta.css()`** (first-class modules) arrived in 1.105.0 on 2026-09-22 [2]. They're too new for an LTS codebase. Avoid them.

### Avoid emitting the same CSS twice

- **Every compilation is separate.** `theme.scss` (Sass CLI) and a component's stylesheet (Vite) each include all CSS reachable through their own `@use` graph.
- **Rule:** `tokens/` and `tools/` hold only variables, maps, functions and mixins. They emit nothing. Exactly one partial (`tokens/_custom-properties.scss`) emits `:root`, and only `theme.scss` uses it. Verified: a second entry that `@use`s `tools` compiles to its own rules plus the layer statement, with no `:root` copy [14].
- **Don't inject tokens through Vite's `additionalData`.** Vite's docs warn that real styles injected there are duplicated in every file [21]. Implicit injection also hides each file's dependencies. Write `@use "tools" as t;` explicitly.

### `!default` for a second theme without forking

Configuring a map replaces it whole. Expose an overrides map instead:

```scss
// tokens/_color.scss
@use "sass:map";
$-palette: ("teal-700": #0f766e, "gray-500": #6b7280, /* … */);   // private primitives
$overrides: () !default;                                            // public hook
$color: map.merge((
  "primary":    map.get($-palette, "teal-700"),
  "text-muted": map.get($-palette, "gray-500"),
), $overrides);
```

### Built-in modules you'll actually use

| Module | Use here | Notes |
|---|---|---|
| `sass:map` | `map.get($m, $k, $nested...)`, `map.has-key`, `map.merge`, `map.deep-merge`, `map.keys` [12] | Replaces the deprecated global `map-get` |
| `sass:meta` | `meta.inspect()` to keep quotes when emitting font stacks [14]; `meta.load-css` only if you accept per-call emission | Global `feature-exists` is deprecated [7] |
| `sass:math` | `math.div()` for any division | `/` becomes a list separator in Dart Sass 2 [4] |
| `sass:color` | `color.adjust`, `color.scale`, `color.change` only if you derive shades | Global `darken()` etc. are deprecated. Keep literal hex values so the output stays diffable |
| `sass:list`, `sass:string` | Rarely: `list.nth`, `string.unquote` | — |

**Load paths.**
- **Inside the tree:** use relative `@use "../tools" as t;`. It needs no configuration and works the same in the CLI and in Vite.
- **For a component stylesheet outside the tree:** pass a load path (`--load-path` [8], or Vite's `loadPaths` from Sass `StringOptions` [21]).
- **Never rely on the current working directory.** That's the deprecated `fs-importer-cwd` behaviour [7].

**Recommendation.**
- Namespaced `@use` everywhere, with no `as *`.
- `_index.scss` files that `@forward` for `tokens/` and `tools/`, and `@use` for CSS-only folders.
- Pure `tokens/` and `tools/`.
- An overrides map for configuration.

**Defend it.** "Tokens and tools are pure modules: they emit nothing, so any entry point can use them without duplicating CSS. One partial emits `:root`, and only the theme entry loads it. Everything is namespaced, so a reviewer can see where every value comes from."

---

## 4. Tokens

### Tiers

| Tier | Lives in | Emitted? | Example |
|---|---|---|---|
| Primitive | private `$-palette` in `tokens/_color.scss` | No | `teal-700: #0f766e` (Tailwind-style names, because the values are Tailwind v3 [28]) |
| Semantic | public maps in `tokens/` | **Yes**, as `--{category}-{role}[-{variant}]` | `--color-text-muted`, `--color-surface`, `--space-6`, `--font-size-sm`, `--radius-md`, `--shadow-md`, `--duration-fast`, `--container-max` |
| Component | the component partial, on its block | Only where theme.css already had one | `.c-stars { --stars-full: var(--color-accent); }` |

Primitives stay Sass-only. That keeps `:root` short and forces components to use roles, not raw colours.

### Emitting custom properties

```scss
// tokens/_custom-properties.scss — the only CSS-emitting file under tokens/
@use "sass:meta";
@use "index" as tok;
@layer tokens {
  :root {
    @each $name, $value in tok.$color  { --color-#{$name}: #{$value}; }
    @each $name, $value in tok.$font   { --font-#{$name}: #{meta.inspect($value)}; } // keeps "Segoe UI" quoted
  }
}
```

### Reading tokens: functions that fail the build

```scss
// tools/_functions.scss
@function color($name) {
  @if not map.has-key(tok.$color, $name) {
    @error "Unknown color token `#{$name}`. Known: #{map.keys(tok.$color)}";
  }
  @return var(--color-#{$name});
}
```

`t.color("txet-muted")` stops the build and lists the valid names. A raw `var(--color-txet-muted)` would silently fall back to the inherited value [14].

### Breakpoints stay Sass

- **`var()` doesn't work in media queries.** It's allowed only in property values, "not … property names, selectors, or anything else besides property values" [24].
- **`@custom-media` isn't usable.** It has no browser support in web-features data [23].
- **Range syntax (`width <= 640px`) is fine.** It's been Baseline widely available since 2025-09-27 [23], and Sass passes it through with a variable inside [14].

```scss
// tools/_mixins.scss
@mixin below($name) {
  $px: map.get(tok.$breakpoints, $name);
  @if not $px { @error "Unknown breakpoint `#{$name}`"; }
  @media (width <= $px) { @content; }
}
```

**Direction.** theme.css is desktop-first (`max-width: 640px`). For equivalence, keep `below("sm")` as the default. A `from("sm")` (`width > 640px`) mixin can come later. The range syntax avoids the classic 640/641px off-by-one.

### Exact values or a scale?

There are 19 spacing values and 15 font sizes (§1.3–1.4).

- **(a) One token per value.** A lookup table, not a system.
- **(b) Normalize to a 4px scale.** Clean, but output changes by a few px in 13 places.
- **(c) Hybrid.** A scale for the recurring on-grid values (4, 8, 12, 16, 20, 24, 32, 40, 48, 56, 64 as `space(1…16)`, where step = px/4). The 7 off-grid values stay literal in their one component, with a `// WP value, off-scale` comment, so the verify step can report zero differences.

### Dark mode and token files

- **Dark mode:** theme.css gives no hint of it, so it's out of scope. The semantic tier makes it one extra `:root` block later. `light-dark()` is only "newly available" (since 2024-05-13), not yet widely available [23].
- **DTCG token files:** the DTCG Format Module 2025.10 is a stable Final Community Group Report [29]. A JSON source of truth would need a generator, which is another dependency. "With more time", not now.

**Recommendation.**
- Three tiers, with semantic tokens emitted from Sass maps.
- Getter functions with `@error`.
- Breakpoints in a Sass map behind a mixin.
- Option (c) for values.

**Defend it.** "Tokens are the API. Components ask for a role, like `t.color(text-muted)`, and get a custom property back. A typo fails the build instead of silently falling back. Breakpoints stay in Sass because the spec doesn't allow `var()` in media queries. I tokenised the values that repeat and left the one-off WP values local and labelled, so the output stays provably equivalent."

---

## 5. Dart Sass status, late 2026

### Versions and cadence

| Item | Value |
|---|---|
| Latest | 1.108.1 (2026-11-07). 1.108.0 is 2026-11-06. Both are in cooldown [3] |
| Newest past the cooldown | **1.107.1** (2026-10-30), with npm provenance (SLSA v1) [3] |
| Cadence | 34 releases across 15 minor lines between 2025-11-09 and 2026-11-09 [3] |
| Maintainers (npm) | nex3, hcatlin [3] |
| Node | `>=20.19.0` [3] |
| Dart Sass 2.0 | "We're hoping to release Dart Sass 2 in December 2026." Most deprecations become errors; `/` becomes a separator [4] |
| Dart Sass 3.0 | Removes `@import` and global built-ins. "No sooner than two years after Dart Sass 1.80.0", that is, not before 2026-10-17 [6] |
| Breaking changes in minors | "Potentially breaking" fixes in 1.94.0, 1.101.0, 1.103.0, 1.104.0 and 1.106.0. 1.108.0 undid "unintentional breaking changes" from 1.106.0 [2]. Policy: CSS-compatibility breaks may ship in minors after ≥3 months of warnings [5] |

### Deprecations that affect new code

| ID | Since | Becomes an error in | What to write instead |
|---|---|---|---|
| `import` | 1.80.0 | 3.0 | `@use`/`@forward` [6][7] |
| `global-builtin` | 1.80.0 | 3.0 | `map.get`, `math.div`, … |
| `color-module-compat` | 1.23.0 | 3.0 | — [4] |
| `if-function` | 1.95.0 | 3.0 | `if(sass($c): a; else: b)` [2][4] |
| `slash-div` | 1.33.0 | 2.0 | `math.div()` or `calc()` [14] |
| `color-functions`, `color-4-api` | 1.79.0 | 2.0 | `color.adjust/scale/change` [7] |
| `with-private` | 1.92.0 | 2.0 | Configure only public variables [2][14] |
| `misplaced-rest`, `function-name`, `adjacent-compounds` | 1.91 / 1.98 / 1.100 | 2.0 (listed in the blog's flag set) [4] | — |
| `strict-unary`, `function-units`, `duplicate-var-flags`, `new-global`, `feature-exists`, `fs-importer-cwd`, `elseif` | various | 2.0 | — [7] |
| `legacy-js-api` | 1.79.0 | 2.0 | Affects tools that call Sass. Vite 8's docs point to the modern `StringOptions` [21] |
| `deprecation-version` | 1.107.0 | not in 2.0 (after 1.105.0) [4] | Don't pass a future version to `fatalDeprecations` |
| `mixed-decls` | 1.77.7 | **obsolete since 1.92.0** [2][7] | — |
| `css-function-mixin`, `type-function` | 1.76 / 1.86 | obsolete (1.94 / 1.92) [7] | — |

### Turning warnings into errors

All of these were verified with `sass@1.107.1` [14].

| Flag | Effect |
|---|---|
| `--fatal-deprecation=1.107.0` | Every deprecation active in 1.107.0 becomes an error, including `import`, `global-builtin` and `if-function`. **Recommended** |
| `--fatal-deprecation=dart-sass-2` | Only what becomes an error in 2.0. `@import`, `map-get()` and legacy `if()` still pass as warnings |
| `--fatal-deprecation=1.107.0,-import` | The same, minus `import` (exclusion syntax added in 1.107.0) [2] |
| `--fatal-deprecation=1.200.0` | Rejected: "requires a version less than or equal to the current Dart Sass version" |
| `--fatal-deprecations=…` (blog spelling [4]) | Rejected: "Could not find an option named --fatal-deprecations" |
| `--future-deprecation=<id>` | Opts in early to future deprecations. The CLI docs say none exist at the moment [8] |
| `--silence-deprecation` | Don't use it. It hides exactly what we want to see |

### Transitive dependencies and advisories (2026-11-09)

| Package (resolved) | Maintainers | Provenance | Advisories in range | Status |
|---|---|---|---|---|
| `sass@1.107.1` | 2 | yes | none [15] | ✅ |
| `chokidar@5.0.0` → `readdirp@5.1.1` | 1 / 2 | yes / yes | none | ✅ |
| `immutable@5.1.9` (range `^5.1.5`) | 2 | yes | CVE-2026-29063 (fixed 5.1.5), CVE-2026-59879 and -59880 (fixed **5.1.8**), all High [15] | ✅ resolved past the fix. 5.1.10 came out today and waits in cooldown |
| `source-map-js@1.2.2` (range `>=0.6.2 <2`) | 1 | no | CVE-2026-93749, High, fixed 1.2.2 [16] | ✅ resolved past the fix |
| `@parcel/watcher@2.6.0` (optional) + `detect-libc`, `is-glob`, `is-extglob`, `node-addon-api`, `picomatch@4.0.7` + 1 of 12 platform binaries | 1 | no | picomatch CVE-2026-33671/-33672, fixed 4.0.4 [16] | ✅. It has an `install` script (build from source) |

- **Who is exposed.** Every advisory above needs attacker-controlled input: huge lists, crafted map keys, crafted source maps. Sass only compiles our own files, so exposure is low. Scanners will still flag an old lockfile.
- **Check:** after `pnpm install`, confirm the lockfile resolves `immutable>=5.1.8` and `source-map-js>=1.2.2`.
- **`@parcel/watcher` is used only by `--watch`** [2]. Deny its build script rather than approve it. The prebuilt platform package already covers it:

  ```yaml
  # frontend/pnpm-workspace.yaml
  allowBuilds:
    "@parcel/watcher": false
  ```

  The same can be done with `pnpm approve-builds '!@parcel/watcher'` [30].

**Recommendation.**
- Pin `"sass": "1.107.1"` exactly, with no caret, because minors can break.
- Build with `--fatal-deprecation=1.107.0`. The blog says clean builds under such flags won't break on 2.0 [4].
- Take 2.0.0 only after the cooldown and a changelog read.

**Defend it.** "Sass 2 lands next month. I already build with every deprecation fatal, so it can't break me. I pin the exact version, because Sass ships CSS-compatibility breaks in minor releases, and I deliberately didn't use the narrower `dart-sass-2` preset, because it lets `@import` through."

---

## 6. Naming

| Option | Security | Stability | Effort | Why it might lose |
|---|---|---|---|---|
| **Keep WP class names** | — | Zero churn. Diffing against theme.css is trivial | Lowest | Keeps the descendant selectors and the leaks in §1.7. "Equivalent structure" is graded, and this has none |
| **Plain BEM** (`.card__title--featured`) | — | Mature convention since the 2010s | Medium | Can't tell layout from component from utility. Global names can collide with a third-party widget |
| **Prefixed BEM** (`l-`, `c-`, `u-`) | — | Same, plus the prefix states the layer | Medium | Slightly longer names. Needs a one-paragraph README rule |
| **Utility-heavy** (`.p-6 .flex`) | — | Fine, but generating utilities needs loops or a framework | High for this size | Moves design into templates. Duplicates what Tailwind does, which ADR 0011 rejected |

### WP → proposed mapping

| WP | Proposed | Layer |
|---|---|---|
| `.container` | `.l-container` | layout |
| `.grid` | `.l-grid` | layout |
| `.section`, `.section h2`, `.section-header *` | `.l-section`, `__title`, `__header`, `__more`; **`.l-section--alt`** (replaces the inline style on the home page) | layout |
| `.brand-body`, `.reviews-section` | `.l-section--article`, `.l-section--reviews` | layout |
| `.site-header` (+ `.container`, `.site-title`, `a`) | `.c-site-header`, `__inner`, `__title`, `__home-link` | components |
| `.site-nav a` | `.c-site-nav__link`, current page styled via `[aria-current="page"]` | components |
| `.hero h1/p` | `.c-hero__title`, `__lead`; **`.c-hero--compact`** (replaces the inline `padding:48px 0`) | components |
| `.card h3 a`, `.meta`, `.excerpt` | `.c-card__title`, `__link`, `__meta`, `__excerpt` | components |
| `.stars .star-full/.star-empty/.rating-value` | `.c-stars__star`, `__star--empty`, `__value`, **`__count`** (replaces the inline margin) | components |
| `.badge` | `.c-badge` | components |
| `.brand-hero`, `.review-hero` | `.c-page-header--brand`, `--review`; `__title`, `__meta`, `__eyebrow` | components |
| `.brand-body .content` | `.c-prose` (sanitised WP HTML) | components |
| `.review-item *` | `.c-review`, `__head`, `__title`, `__link`, `__body`, **`__brand`** (replaces the archive inline style); `.c-byline` as its own block so the review page can reuse it | components |
| `.page-body` | `.c-panel` | components |
| `.pagination .page-numbers.current` | `.c-pagination__link`, current via `[aria-current="page"]` | components |
| `.site-footer a` | `.c-site-footer__link` | components |
| `.meta` outside cards | `.u-text-muted` | utilities |

- **The one exception to BEM: `.c-prose`.** Sanitised CMS HTML can't carry classes, so `.c-prose` styles elements beneath it. Use `:where()` to keep specificity at one class: `.c-prose :where(h2, blockquote)` is (0,1,0). `:where()` has been widely available since 2023-07-21 [23].
- **State lives in ARIA attributes where one exists** (`aria-current`, `aria-busy`). That ties styling to accessibility.
- **Native `@scope` isn't ready.** It could replace BEM's scoping, but it's only newly available since 2026-03-24 [23]. Wait.

**Recommendation.** Prefixed BEM. Keep a WP→BEM mapping table in the README; the verify step uses the same table.

**Defend it.** "BEM with a layer prefix. `c-card__title` tells you the layer, the block and the element, with one class of specificity. WP's descendant selectors were already leaking: two elements render unstyled. Django templates are new markup, so keeping WP names bought nothing."

---

## 7. Compile and verify

### Which compiler

| Option | For | Against |
|---|---|---|
| **Sass CLI for `theme.scss`** | No Vite config. Works without the React build. Easy to explain in the README. Output is a plain file that whitenoise's manifest storage hashes (ADR 0008) | A second pipeline next to Vite |
| **Vite builds both** | One tool | Hashed file names need manifest lookup in Django (another package or hand-written glue). Theme styles would depend on the React build |
| **Both** (CLI for the theme, Vite for the component) | Each tool does what it's good at. Same `sass` version, same `tools/` | Two commands, so two flag lists to keep in sync |

**README command:**

```bash
cd frontend
pnpm exec sass --no-source-map --no-error-css --style=compressed \
  --fatal-deprecation=1.107.0 scss/theme.scss <django-static>/css/theme.css
# dev: same, with --watch and without --no-source-map / --style=compressed
```

- **Source maps are on by default when writing files** [8]. In production they add nothing; in dev they help. The `.map` file is written next to the CSS, with a `sourceMappingURL` comment [14].
- **`--error-css` is on by default when writing files** [8]. On a compile error the CLI exits 65 but still writes a CSS file. That file shows the error and source path in a `body::before` rule [14]. Never ship it, so builds pass `--no-error-css`.
- **Compressed vs. expanded:** expanded output is easier to diff. Compressed saves bytes, though whitenoise also compresses on the wire. Use compressed for builds and expanded for the equivalence report.
- **In Vite:** pass the same deprecation policy through `css.preprocessorOptions.scss`, for example `fatalDeprecations` and `loadPaths` [21]. The exact config wasn't run here (see Not verified).

### Proving "equivalent"

| Approach | New packages | Convincing? | Why it might lose |
|---|---|---|---|
| Normalised text diff (`sed` + `diff`) | 0 | Weak | Renames, `var()` substitution and `@layer` wrapping make every line differ |
| **postcss script**: parse both, flatten `@layer`, resolve `var()` from each `:root`, map selectors through the WP→BEM table, compare declaration sets per selector and media query | **0**. `postcss@8.5.32` (4 packages) is already in Vite 8's tree [18]. Declare it as a devDependency, because pnpm doesn't expose transitive packages | Strong. A report like "195 declarations: N identical, M intended changes (listed), 0 missing" | You maintain the rename table (but it doubles as docs) |
| Lightning CSS (minify both, compare) | 0 (in Vite's tree) | Weak | Has the same rename and `var()` problem; native binary |
| Visual: manual side by side (WP `:8080` vs. Django) at 375px and 1280px | 0 | Good for humans | Not automated |
| Visual: Playwright screenshots | Heavy (browser downloads) | Strong | Far too much supply chain for one stylesheet |

**Recommendation.**
- One Vitest file (Vitest is already accepted) that compiles `theme.scss` with `sass.compile()` and the same fatal deprecations, parses the result with postcss, then does two things:
  - (1) asserts the architecture invariants (§8);
  - (2) prints the equivalence report against `reference/theme.css`, with intended deviations allow-listed.
- Plus one manual side-by-side check, noted in the README.

**Defend it.** "Equivalence is checked by a test: it resolves custom properties, maps old selectors to new ones and compares every declaration. Intended changes are listed, like focus styles and reduced motion. It reuses PostCSS, which Vite already ships, so it adds no new packages."

---

## 8. Linting

### Cost of stylelint today

| Setup | Packages | Notes |
|---|---|---|
| stylelint 17.16.0 + `stylelint-config-standard-scss` 17.0.0 | **126** [18] | Includes 12 keyv/cacheable-family packages. Their maintainer account was hijacked on 2026-08-04. Trojanized `file-entry-cache@11.1.6`, `flat-cache@6.1.24`, `cacheable@2.5.1` and `keyv@6.0.0` were published with valid provenance and delivered through an install script [17]. Our resolution lands on the versions just before them (11.1.5, 6.1.23, 2.5.0) |
| stylelint 18.0.0 alone | **30** [18] | 18.0.0 "replac[ed] `file-entry-cache`" [19]. In cooldown until 2026-11-10. **`stylelint-scss` 7.4.0 peers only `^16.8.2 \|\| ^17`**, and `stylelint-config-standard` 41 needs 18 [3] |

- **Maintenance health is fine:** stylelint has 4 maintainers and ships monthly; stylelint-scss has 3 maintainers [3].
- **The cost is the tree.** And the SCSS plugin lags the major version that removes the risky part.

### What enforces the architecture

| Rule | stylelint rule [20] | Without stylelint |
|---|---|---|
| No `@import` | `at-rule-disallowed-list: ["import"]` | `--fatal-deprecation=1.107.0` (error) [14] |
| No global functions (`map-get`, `darken`) | `scss/no-global-function-names` | The same flag (`global-builtin`) [14] |
| No unknown tokens | — | Getter functions `@error` [14] |
| BEM with a prefix | `selector-class-pattern` | Test: every class in the compiled CSS matches `^[clu]-[a-z0-9-]+(__[a-z0-9-]+)?(--[a-z0-9-]+)?$` (plus the `c-prose` element exception) |
| No raw hex outside tokens | `color-no-hex` with `overrides` for `tokens/**` | Test: hex appears only in `:root` custom property declarations of the output |
| Max nesting | `max-nesting-depth` | Test: max specificity ≤ (0,2,0) in the output (`selector-max-specificity` in stylelint) |
| Every rule inside a layer | — (no rule) | Test: no rule outside `@layer` in the output. This catches the worst mistake (§9) |
| No `!important` | `declaration-no-important` | Test |
| Namespaced `@use` | `scss/at-use-no-unnamespaced` | Review |

**Lint the output, not just the source.** Layer membership, specificity and class names are properties of the compiled CSS. A postcss walk over the output catches them more reliably than regexes over SCSS, and it shares the parse with the equivalence test.

**Recommendation.**
- No stylelint for now. Use Sass's fatal deprecations, the getter `@error`s, and the output-invariants test.
- Revisit when `stylelint-scss` supports stylelint 18 and both are past the cooldown, at about 30 packages plus the plugin.

**Defend it.** "Stylelint's SCSS setup is 126 packages today, and 12 of them come from a maintainer whose account was hijacked in August. Sass already turns `@import` and global functions into errors. A small test checks the rest on the compiled CSS, which is what actually ships. I'll add stylelint once the SCSS plugin supports version 18, which dropped that dependency chain."

---

## 9. Extensibility

### How a second engineer adds a component

1. **Create `components/_rating-summary.scss`** (file name = block name). Start it with `@use "../tools" as t;`.
2. **Wrap everything in `@layer components { .c-rating-summary { … } }`.** One block per file.
3. **Get values from `t.color()`, `t.space()`, `t.font-size()`, `t.radius()`, `t.shadow()`.** A typo fails the build and lists the valid names.
4. **Use elements (`&__x`), modifiers (`&--y`) and states (`&:hover`, `&[aria-busy="true"]`).** Go one level deep, no more.
5. **For responsive rules, use `@include t.below("sm") { … }`.** Never write a raw px media query.
6. **Need a new value? Add it to the semantic map in `tokens/`.** It's emitted automatically and the getter accepts it.
7. **Add `@use "rating-summary";` to `components/_index.scss`.** Order within a layer only matters between blocks that style the same element, and BEM blocks don't.
8. **Run `pnpm build:css` and `pnpm test`.** That covers fatal deprecations, the invariants and the equivalence report.

| Mistake | What stops it |
|---|---|
| Out-specifying someone else's component | Layers order the cascade before specificity. Invariant: specificity ≤ (0,2,0) |
| Forgetting the `@layer` wrapper (unlayered rules beat **all** layers [22]) | Invariant: no unlayered rules |
| Class collision | Prefix plus block = file name; class-pattern invariant |
| Magic numbers or colours | Getter functions; hex-only-in-`:root` invariant |
| Duplicated CSS from a new entry point | Pure `tokens/` and `tools/` |
| Silent visual regressions in existing blocks | Equivalence report diff |
| `!important` | Invariant (and it *reverses* layer order [22]) |

### Layer assignment: inside each partial, or in the index?

- **(a) Each partial wraps itself in `@layer`.** Explicit and greppable. It behaves the same when a component stylesheet `@use`s it. The risk is forgetting the wrapper, which the invariant catches.
- **(b) The index wraps `meta.load-css()` calls.** Partials stay plain. But `load-css` emits on every call, and it nests layers if a partial also declares one [14].

Recommendation: (a).

### What the tree offers `<BrandList />` (for Pillar 3)

- **Modules that are safe to `@use` from anywhere:** `tools` (getters, `below()`) and `tokens`. They emit no CSS.
- **Runtime custom properties on `:root`:** the semantic tier, readable from any CSS.
- **Global blocks it can use directly:** `.l-grid`, `.c-card`, `.c-badge`, `.c-stars`, `.u-visually-hidden`, plus a reserved `components/_brand-list.scss` for the toolbar, status and empty or error states.
- **`_layers.scss`,** to `@use` first in any extra entry, so its CSS starts with the same order statement. Repeating the statement is harmless: re-declaring a layer doesn't change its order [22].

| Option (SCSS side) | For | Against |
|---|---|---|
| **Global BEM partial in this tree** | One stylesheet and layer order. Server-rendered home-page cards and React cards share `.c-card`. No Vite CSS config. The theme `<link>` in `<head>` avoids a flash of unstyled content | The component isn't self-contained: it depends on theme.css. Global namespace (mitigated by prefix and invariant) |
| **Co-located `BrandList.module.scss`** that `@use`s `tools` | Co-location and scoped names. Delete the component and its CSS goes too. Vite supports `.module.scss` natively [21] | Hashed names can't be reused by Django templates. Card styles get duplicated or need `:global()`. Its CSS must start with `@use "layers"` or it may set layer order first |
| **Hybrid** (shared blocks global, toolbar in a module) | Shares the card; scopes the one-off bits | Two styling mechanisms to explain |

**Recommendation.** A global BEM partial. Pillar 3 owns the call. The pure modules keep the CSS Module route open without refactoring.

**Defend it.** "A new component is one file, one block, one layer, and one line in the index. The test fails if you skip the layer, use a raw colour or invent a token. `<BrandList />` reuses the same card block as the server-rendered pages, so there's one source of truth for what a brand card looks like."

---

## 10. CSP fit (ADR 0005)

- **The stylesheet needs only `style-src 'self'`.** There's no `url()`, no data URI, no `@font-face` (system font stack) and no `@import` [1]. `font-src` and `img-src` are unaffected. If web fonts are ever added, self-host them through whitenoise rather than allowing a font CDN.
- **Inline styles are blocked** without `'unsafe-inline'` or hashes [25][32]. The 7 WP inline styles map to classes:

| Template | Inline style | Replacement |
|---|---|---|
| `front-page.php` | white background + top and bottom border on a section | `.l-section--alt` |
| `archive-brand.php`, `archive-review.php` | `padding:48px 0` on `.hero` | `.c-hero--compact` |
| `archive-review.php` | brand eyebrow (uppercase, 0.78rem, primary colour) | `.c-review__brand` |
| `single-brand.php`, `archive-brand.php` | `margin-left:8px` / `6px` on the review count | `.c-stars__count` |
| `single-review.php` | `margin-top:8px` on the byline | `.c-byline` (spacing in the block) |

- **Styles set through JavaScript:** setting a property on `element.style` is allowed. `setAttribute("style", …)` and `style.cssText` are blocked [25].
- **Vite:** the dev server injects imported CSS as `<style>` tags [21], which `style-src 'self'` would block. ADR 0005 starts in Report-Only, and dev can relax it. Production builds emit `.css` files loaded with `<link>` [21].
- **Builds use `--no-error-css`,** so a failed compile can't ship a stylesheet that prints source paths [8][14].

**Defend it.** "The compiled CSS has no external fetches, so `style-src 'self'` covers it. The WP templates used seven inline styles. Each became a modifier class, so we never need `'unsafe-inline'`."

---

## 11. Proposed file tree

```
frontend/scss/
├── theme.scss                     # entry: @use layers first, then custom-properties, base, layout, components, utilities
├── _layers.scss                   # the single `@layer reset, tokens, base, layout, components, utilities;` statement
├── tokens/                        # pure: maps only, no CSS (except _custom-properties)
│   ├── _index.scss                # @forward of every token file (hides private primitives)
│   ├── _color.scss                # private Tailwind-v3 primitives + public semantic $color map + $overrides
│   ├── _typography.scss           # font stack, font-size steps, weights, line-height, letter-spacing
│   ├── _space.scss                # 4px-based scale: space(1…16)
│   ├── _radius.scss               # md (10px), sm (6px), pill (999px)
│   ├── _shadow.scss               # sm, md
│   ├── _motion.scss               # duration-fast (150ms)
│   ├── _layout.scss               # container-max (1100px), gutter (24px), card min width (280px)
│   ├── _breakpoints.scss          # sm: 640px. Sass-only, never emitted
│   └── _custom-properties.scss    # the only CSS-emitting token file: :root in @layer tokens (theme.scss only)
├── tools/                         # pure: functions and mixins, no CSS
│   ├── _index.scss                # @forward functions, mixins
│   ├── _functions.scss            # color(), space(), font-size(), radius(), shadow(): var() + @error on unknown keys
│   └── _mixins.scss               # below($bp), panel($padding), focus-ring, reduced-motion guard
├── base/                          # @layer reset / base
│   ├── _index.scss
│   ├── _reset.scss                # box-sizing, body margin, img (layer reset)
│   └── _elements.scss             # html/body typography, a, a:hover, a:focus-visible (layer base)
├── layout/                        # @layer layout: content-agnostic structure
│   ├── _index.scss
│   ├── _container.scss            # .l-container
│   ├── _grid.scss                 # .l-grid (+ one column below sm)
│   └── _section.scss              # .l-section, __header, __title, __more, --alt, --article, --reviews
├── components/                    # @layer components: one BEM block per file
│   ├── _index.scss                # @use of every component (alphabetical)
│   ├── _site-header.scss          # .c-site-header (+ column layout below sm)
│   ├── _site-nav.scss             # .c-site-nav, [aria-current]
│   ├── _site-footer.scss          # .c-site-footer
│   ├── _hero.scss                 # .c-hero, --compact
│   ├── _page-header.scss          # .c-page-header --brand / --review (brand-hero, review-hero)
│   ├── _card.scss                 # .c-card (panel mixin, hover lift, reduced-motion guard)
│   ├── _badge.scss                # .c-badge
│   ├── _stars.scss                # .c-stars + component tokens for star colours
│   ├── _byline.scss               # .c-byline (reused on review list and review page)
│   ├── _review.scss               # .c-review
│   ├── _prose.scss                # .c-prose: sanitised WP HTML via :where()
│   ├── _panel.scss                # .c-panel (about/contact/404 body)
│   ├── _pagination.scss           # .c-pagination, [aria-current="page"]
│   └── _brand-list.scss           # reserved for <BrandList /> toolbar/status/empty/error (Pillar 3)
└── utilities/                     # @layer utilities: last word, single purpose
    ├── _index.scss
    ├── _visually-hidden.scss      # .u-visually-hidden (labels, live region)
    └── _text.scss                 # .u-text-muted
```

---

## Open decisions for the user

| # | Question | Options | Recommendation |
|---|---|---|---|
| 1 | Tree shape? | Slim layered · ITCSS · 7-1 | **Slim layered**, 1:1 with `@layer` |
| 2 | Naming? | Prefixed BEM · plain BEM · keep WP names | **Prefixed BEM** plus a WP→BEM table |
| 3 | Token values? | One token per value · normalize to a 4px scale · hybrid | **Hybrid**: scale for recurring values, off-scale WP values local and labelled, so the diff is zero |
| 4 | Custom property names? | Keep the 15 WP names · role-based names (`--color-text-muted`, `--color-surface`, `--radius-md`) | **Role-based.** WP content doesn't reference them (checked in the dump) |
| 5 | Breakpoint direction? | Desktop-first `below()` · mobile-first `from()` | **Desktop-first** for equivalence, with range syntax |
| 6 | Where does each partial's layer come from? | `@layer` inside each partial · `meta.load-css` in the index | **Inside each partial**, plus a test that every rule is layered |
| 7 | Linting? | None now + output invariants · stylelint 17 + standard-scss now (126 packages) · wait for 18 support | **None now**, revisit when `stylelint-scss` supports 18 |
| 8 | `<BrandList />` styles? (with Pillar 3) | Global BEM partial · CSS Module · hybrid | **Global partial**; the tree keeps CSS Modules possible |
| 9 | Build and delivery? | Sass CLI for the theme + Vite for the component · Vite for both. Compile in a Docker build stage (Node only in that stage, pinned by digest) · commit compiled CSS with a drift test | **CLI + Vite**, compiled in a **Docker build stage** so `docker compose up` stays the only setup step and the runtime image has no Node. Coordinate with whoever owns the Dockerfiles |
| 10 | Accept a11y deviations from theme.css? | Strict equivalence · add `:focus-visible`, reduced-motion guard, `font-size: 100%`, underlined links in `.c-prose` | **Accept them**, list them in the equivalence report and the README's "AI defaults" section if the AI proposed them |
| 11 | How to pin `sass`? | Exact `1.107.1` · caret `^1.107.1` | **Exact.** Minors ship breaking fixes, and 2.0 is weeks away |

---

## Conflicts with accepted decisions

None found. Notes:
- **ADR 0005 gap.** ADR 0005 states only `script-src 'self'`. For this tree to matter, the policy should also state `style-src 'self'` with no `'unsafe-inline'`, and Django templates must not copy WP's inline styles (§10). That extends ADR 0005; it doesn't contradict it.
- **Corrections to earlier research notes (not ADRs):**
  - `best-practices-2026.md` §7 suggests linting with `stylelint-config-standard-scss`. Today that brings in 126 packages, including the hijacked keyv/cacheable chain, and the plugin doesn't support stylelint 18 (§8).
  - `stack-validation.md` §3.5's command (`pnpm exec sass frontend/scss/main.scss static/css/main.css`) writes a source map and, on failure, an error stylesheet, and makes no deprecation fatal. Use the §7 command.
  - The brief listed `mixed-decls` as active. It has been obsolete since 1.92.0.

---

## Not verified

- **Vite 8 with CSS Modules and `@layer`.** Whether `.module.scss` keeps layer names global (unhashed). Also whether `composes:` works through Sass. Nothing was installed.
- **The exact Vite config.** `css.preprocessorOptions.scss.fatalDeprecations` with a version value (for example `Version.parse("1.107.0")`) wasn't run.
- **Lightning CSS minification** in Vite's build: whether it rewrites `(width <= 640px)` to `max-width` for the `baseline-widely-available` target. Harmless either way.
- **How React DOM applies the `style` prop** (CSSOM property vs. attribute). MDN says property assignment isn't blocked [25].
- **Support for Dart Sass 1.x after 2.0 ships.** The blog doesn't say [4].
- **Whether stylelint backports fixes to 17.x** after 18.0.0.
- **Visual equivalence.** The WP site wasn't started (no Docker in this task).
- **ITCSS layer names** come from Harry Roberts' inuitcss manifest [27], not from a canonical ITCSS document. The 7-1 page is undated [26].
- **Contrast ratios** were computed locally with the WCAG relative-luminance formula, using the 0.04045 sRGB threshold. The WCAG glossary entry wasn't read in full [31].

---

## Sources

1. Local files, read 2026-11-09: `reference/theme.css`, `wp-content/themes/consumer-reviews/*.php` and `style.css`, `db/dump.sql`. Counts come from a stdlib Python script in the session scratchpad.
2. Dart Sass CHANGELOG, `main`, entries 1.88.0–1.108.1, read 2026-11-09. https://github.com/sass/dart-sass/blob/main/CHANGELOG.md
3. npm registry metadata via `npm view`, 2026-11-09: `sass`, `chokidar`, `readdirp`, `immutable`, `source-map-js`, `@parcel/watcher`, `stylelint`, `stylelint-scss`, `stylelint-config-standard(-scss)`, `stylelint-config-recommended-scss`, `postcss`, `file-entry-cache`, `flat-cache`, `cacheable`, `keyv`. Covers versions, times, dependencies, peers, maintainers and provenance.
4. N. Weizenbaum, "The Road to Dart Sass 2", Sass blog, 2026-09-22. https://sass-lang.com/blog/the-road-to-dart-sass-2/
5. Sass, Breaking Changes index (lists items up to 1.107.0). https://sass-lang.com/documentation/breaking-changes/
6. Sass, "Breaking Change: `@import` and global built-in functions". https://sass-lang.com/documentation/breaking-changes/import/
7. Sass JS API, `Deprecations` interface (31 IDs with active and obsolete versions). https://sass-lang.com/documentation/js-api/interfaces/deprecations/
8. Sass, Dart Sass command-line interface. https://sass-lang.com/documentation/cli/dart-sass/
9. Sass, `@use` (via Context7 `/websites/sass-lang`). https://sass-lang.com/documentation/at-rules/use/
10. Sass, `@forward` (Context7). https://sass-lang.com/documentation/at-rules/forward/
11. Sass, `sass:meta` (Context7). https://sass-lang.com/documentation/modules/meta/
12. Sass, `sass:map` (Context7). https://sass-lang.com/documentation/modules/map/
13. Sass, Variables: default values and configuring modules (Context7). https://sass-lang.com/documentation/variables/
14. Prototype compiled with `sass@1.107.1` (`pnpm dlx`, Node 24.22.2) in the session scratchpad, 2026-11-09. It covers: layer order, CSS emitted once, `load-css` duplication, `with` errors, fatal-deprecation flag sets, `--error-css` and source-map defaults, quote stripping, and the token `@error`.
15. OSV / GitHub Advisory Database, `immutable`: GHSA-wf6x-7x77-mvgw (CVE-2026-29063), GHSA-v56q-mh7h-f735 (CVE-2026-59879), GHSA-xvcm-6775-5m9r (CVE-2026-59880). https://osv.dev/vulnerability/GHSA-v56q-mh7h-f735
16. OSV, `source-map-js` GHSA-68fv-2mgg-jv7q (CVE-2026-93749). `picomatch` GHSA-3v7f-55p6-f55p and GHSA-c2c7-rcm5-vvqj. https://osv.dev/vulnerability/GHSA-68fv-2mgg-jv7q
17. OSV malicious-package records, 2026-08-04: MAL-2026-11970 (`file-entry-cache` 11.1.6), MAL-2026-11971 (`flat-cache` 6.1.24), MAL-2026-11963 (`cacheable` 2.5.1), MAL-2026-11524 (`keyv` 6.0.0), MAL-2026-12007, MAL-2026-11558, MAL-2026-11561. Also GHSA-qp89-2g43-jg8j. https://osv.dev/vulnerability/MAL-2026-11970
18. Lockfile-only resolutions with pnpm 12.16.1 and `minimumReleaseAge: 10080`, plus an OSV batch query of all 180 resolved versions (0 hits), 2026-11-09. Results:
    - `sass` alone: 23 entries (11 packages + 12 platform binaries).
    - stylelint 17 + standard-scss: 126.
    - stylelint 18 alone: 30, resolved without the cooldown just to count.
    - `postcss`: 4.
    - `vite@8.3.5` + `sass`: 60, including `postcss` and `lightningcss`.
19. Stylelint CHANGELOG, 18.0.0 (2026-11-03). https://github.com/stylelint/stylelint/blob/main/CHANGELOG.md
20. Stylelint rule docs at tag 17.16.0 and stylelint-scss at v7.4.0 (Context7 `/stylelint/stylelint`, `/stylelint-scss/stylelint-scss`; README files confirmed at those tags). https://github.com/stylelint/stylelint/tree/17.16.0/lib/rules
21. Vite 8.3.5 docs: `guide/features.md`, `config/shared-options.md` and `config/build-options.md` (Context7 `/vitejs/vite/v8.3.5` and raw GitHub at tag `v8.3.5`). https://github.com/vitejs/vite/tree/v8.3.5/docs
22. MDN, `@layer` (Baseline widely available; unlayered beats layered; `!important` reverses; re-declaring keeps order). https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@layer
23. web-features 3.45.0 (published 2026-11-03), Baseline statuses for cascade-layers, media-query-range-syntax, nesting, container-queries, `:where()`, `@scope`, `light-dark()`, custom-media-queries and color-mix. https://www.npmjs.com/package/web-features
24. W3C, CSS Custom Properties for Cascading Variables Level 1, CR Snapshot 2022-06-16. https://www.w3.org/TR/css-variables-1/
25. MDN, CSP `style-src` (inline attributes blocked; CSSOM property assignment allowed). https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/style-src
26. K. Giraudel, Sass Guidelines, "The 7-1 pattern" (undated; examples use `@import`). https://sass-guidelin.es/#the-7-1-pattern
27. H. Roberts, inuitcss `example.main.scss` (ITCSS layers); repository last pushed 2023-03-01 (GitHub API). https://github.com/inuitcss/inuitcss/blob/develop/example.main.scss
28. Tailwind CSS v3.4.17 default palette. https://github.com/tailwindlabs/tailwindcss/blob/v3.4.17/src/public/colors.js
29. W3C Design Tokens CG, Design Tokens Format Module 2025.10, Final CG Report, 2025-10-28. https://www.w3.org/community/reports/design-tokens/CG-FINAL-format-20251028/
30. pnpm docs, `allowBuilds` and `approve-builds` (Context7 `/pnpm/pnpm.io`). https://pnpm.io/settings#allowbuilds
31. W3C, WCAG 2.2 Recommendation, 2024-12-12 (1.4.3, 1.4.11, contrast ratio). https://www.w3.org/TR/WCAG22/
32. W3C, Content Security Policy Level 3, Working Draft 2026-10-27 (style attributes may match hashes). https://www.w3.org/TR/CSP3/
