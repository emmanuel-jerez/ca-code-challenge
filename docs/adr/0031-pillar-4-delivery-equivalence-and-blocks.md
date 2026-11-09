# 0031. Pillar 4: build and delivery, the equivalence check, the remaining blocks

- Status: Accepted
- Date: 2026-11-09

## Context
ADR 0030 built the SCSS tree for `<BrandList />` and left Pillar 4 three
things: the blocks the server-rendered pages need, a comparison with
`reference/theme.css`, and getting `theme.css` and the component onto Django
pages (open decision 9 in `docs/research/pillar-4-scss-architecture.md`).
ADR 0028, item 4, moved mounting the component here too. Facts that shaped
the options:

- The Django templates already carry prefixed BEM classes from Pillar 1
  (`c-site-header`, `c-hero`, `c-review`, `c-prose`…), but no page links a
  stylesheet, so those classes have no styles yet.
- The main app's image is `python:3.14-slim-trixie` with no Node. The
  challenge's only setup step is `docker compose up`.
- WordPress has a brand archive at `/brand/` (`archive-brand.php`,
  `has_archive` in `cpt.php`). Django has no page there.
- WordPress's markup and CSS disagree in places: `.meta` and
  `.review-byline` are used outside the selectors that style them, so they
  render unstyled, and seven inline styles carry spacing and colors.

The user chose items 1–4 on this date, taking the recommendation each time
except item 4. Items 5–15 are defaults the agent took while building, flagged
for review in the Pillar 4 pull request.

## Options considered
1. **Build and delivery.**
   - Vite builds both `theme.scss` and the component. Rejected: every page's
     CSS would depend on the React build, and Django would need the manifest
     to find the hashed theme file.
   - Commit the compiled CSS and bundle, with a drift test. Rejected:
     generated files in git, and every SCSS change needs a manual rebuild.
   - The Sass CLI for `theme.css` and Vite for the component, both run in a
     Node stage of the main app's Dockerfile, pinned by digest. Chosen: the
     runtime image has no Node, and `docker compose up` stays the only
     setup step. The cost is two build commands that must pass the same Sass
     flags.
2. **Where `<BrandList />` mounts.**
   - The homepage, in place of "Featured Brands". Rejected: `/brand/` would
     stay a 404 where WordPress has a page.
   - A new `/brand/` page. Chosen: it keeps WordPress's archive URL.
3. **Showing the output is equivalent.**
   - A hand-checked table only. Rejected: nothing catches a rule dropped
     later.
   - A Vitest check with postcss, which is already a devDependency. Chosen.
4. **How to ship it.**
   - One PR. Recommended, but the user preferred smaller reviews.
   - Two PRs. Chosen: the SCSS blocks and the equivalence check first, then
     build, delivery and mounting, stacked on the first. Until the second
     merges, no Django page shows the CSS.

## Decision
- `frontend/scss/equivalence.ts` compares two stylesheets declaration by
  declaration. It resolves `var()` on both sides, maps WordPress selectors
  through a table, and treats as equal:
  - physical and logical box sides;
  - `border` shorthands and their sides;
  - `max-width` and range-syntax media queries;
  - `150ms` and `0.15s`;
  - quoted and unquoted attribute values.
- `frontend/scss/wp-mapping.ts` holds that table (`WP_TO_BEM`, also the
  README's rename table) and the list of intended deviations, each with a
  reason. `equivalence.test.ts` fails when a WordPress selector isn't mapped,
  when a declaration differs without a listed deviation, or when a listed
  deviation no longer applies.
- The remaining blocks are in the tree, one partial each: `c-site-header`,
  `c-site-nav`, `c-site-footer`, `c-hero`, `c-brand-hero`, `c-brand-facts`,
  `c-review-hero`, `c-review`, `c-byline`, `c-panel`, `c-prose`, `c-empty`
  and `u-skip-link`. `l-section` gains `__title`, `__header`, `__more` and
  `--alt`, `--article` and `--reviews` modifiers.
- Build and delivery (item 1) and the `/brand/` page (item 2) arrive in the
  second PR.

Defaults the agent took (items 5–15):

5. **Two comparison statuses besides same and different.** These aren't
   deviations to list:
   - `motion-guarded`: the same value, but only under
     `prefers-reduced-motion: no-preference` (ADR 0030, item 6).
   - `initial`: WordPress set a margin or padding side to `0`, and we leave
     it at its initial `0`. That holds only on elements without browser
     margins or padding; the mapped blocks sit on divs, sections, headers
     and footers.
6. **A `surface` mixin, not a shared class,** for the white bordered box
   that WordPress repeated four times. Card, review and panel each include
   it and keep their own padding. A shared `c-surface` class would put two
   blocks on every element and couple their padding.
7. **`c-byline` as its own block.** Review items and the review page both
   show a byline. WordPress styled `.review-byline` only inside
   `.review-item`, so the review page's byline was unstyled.
8. **Long-form content as `c-panel c-panel--article c-prose`.** The panel
   draws the box and `c-prose` styles the sanitized HTML inside it. The
   templates now nest the box inside `l-container`, as WordPress did.
   `c-prose` is the one block that styles bare elements, through `:where()`,
   so it stays at one class of specificity.
9. **`.page-body`'s 48px margin moves to the surrounding `l-section`.** A
   block doesn't place itself. There are no About or Contact pages yet;
   `c-panel` is ready for them.
10. **New tokens:**
    - color roles `text-prose`, `primary-deep`, `inverse-surface`,
      `on-inverse` and `on-inverse-muted`;
    - font size `2xl` (1.75rem, used three times);
    - letter spacing `tight` and `tighter` (used five and two times).

    Other one-off WordPress values stay in their block, marked `WP value,
    off-scale`, as ADR 0030 item 2 set.
11. **Accessibility changes beyond ADR 0030:**
    - underlined links in `c-prose` (3.18:1 against body text);
    - a skip link, visible on focus;
    - review cards get the same stretched title link as brand cards, with
      the brand link raised above it so it stays clickable.
12. **WordPress's leaks fixed, not reproduced.** "No reviews yet" gets
    `c-empty` (muted text) instead of an unstyled `.meta`. The brand facts
    become a `<dl>`: the label is bold in the text color like WordPress's
    `<strong>`, and its colon comes from CSS.
13. **`l-page` and `l-main` stay unstyled hooks.** The templates carry them
    from Pillar 1. WordPress had no styles for its equivalents either.
14. **The architecture test's specificity counter** no longer counts
    `:not()`, `:is()` and `:has()` themselves, only their arguments, as
    Selectors Level 4 specifies. Before, `.u-skip-link:not(:focus)` counted
    as three classes instead of two.
15. **Shared compile options** move to `scss/compileTheme.ts`, so both test
    files compile with the same deprecation policy.

## Consequences
- The equivalence test reports these deviations from `reference/theme.css`:
  - `html`: its rule is folded into `body`;
  - the forced 16px root font size is dropped;
  - the grid column is `min(100%, 17.5rem)` and needs no mobile media query;
  - `.page-body`'s margin moves to the section.

  Everything else matches, motion-guarded or initial.
- Changing a WordPress-derived value now means updating `wp-mapping.ts`
  with a reason. That is the point, but it is one more file to touch.
- The comparison assumes left-to-right text when it maps logical sides to
  physical ones.
- Nothing is checked visually yet. That needs the second PR, which puts the
  CSS on Django pages.

## Revisit when
- A right-to-left language is added (the comparison's logical-side mapping).
- About or Contact pages are built (`c-panel` without the article modifier).
- The second PR changes any part of item 1 or 2 while building it.

## Sources
`docs/research/pillar-4-scss-architecture.md` §1.7, §6, §7, §10 and "Open
decisions"; ADRs 0023, 0028 and 0030; `reference/theme.css`;
`wp-content/themes/consumer-reviews/*.php`.
