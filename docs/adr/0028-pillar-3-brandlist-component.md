# 0028. Pillar 3: how `<BrandList />` fetches, keeps state and renders

- Status: Accepted
- Date: 2026-11-09

## Context
`<BrandList />` consumes `GET /api/brands/` (ADRs 0022, 0027) and must handle
an industry filter, sorting, loading, empty and error states, keyboard use,
and mobile and desktop widths (CHALLENGE.md, Pillar 3). ADR 0011 fixed the
toolchain and ADR 0023 the styling approach. The options are in
`docs/research/pillar-3-brandlist-component.md`. Facts that shaped them:

- The SCSS tree (Pillar 4) didn't exist yet, so the component had nothing to
  be styled by.
- ADR 0027 left open where the filter gets its list of industries.
- The API already takes repeated `industry` keys, so multi-select costs
  nothing on the server.
- TanStack's npm org was compromised on 2026-05-11. SWR passes no
  `AbortSignal` to its fetcher. MSW would add 45 dev packages, five of which
  had malicious versions published on 2025-09-08.

The user chose items 1–5 on this date, taking the recommendation each time
except item 3. Items 6–14 are implementation defaults the
agent took while building, flagged for review in the Pillar 3 pull request.

## Options considered
1. **Where the industry list comes from.**
   - A new `GET /api/industries/` endpoint. Rejected: one more request per
     page, and backend scope for a frontend pillar.
   - A constant in the frontend. Rejected: it drifts silently when an
     industry is added.
   - A prop, which Django fills from `json_script`. Chosen: no request, no
     backend change, and the mount code validates it with Zod like any
     input.
2. **Fetching, URL state, controls, history, pagination and test mocking**,
   taken together on the research note's recommendations:
   - TanStack Query or SWR rather than a custom hook. Rejected: a cache
     library for one endpoint, TanStack's 68 releases this year against the
     cooldown, and SWR can't cancel.
   - nuqs or React Router for URL state. Rejected: a single-maintainer
     package, or a router with 20 advisories in 2025–26, to own one query
     string on a page Django routes.
   - A single `<select>` or `<select multiple>` for industries. Rejected:
     single choice only, or non-standard multi-select keyboard behavior.
   - Pushing every sort change to history. Rejected: arrow keys on a select
     can create one entry per keypress.
   - Buttons for pagination. Rejected: links keep open-in-new-tab and
     copy-link.
   - MSW in tests. Rejected: 45 packages (see Context).
3. **Styles while the SCSS tree doesn't exist.**
   - Markup now, CSS with Pillar 4. Recommended, but the component would look
     unstyled until then.
   - Pillar 4 first. Rejected: it reorders the pillars.
   - A minimal tree now, holding only what the component needs. Chosen. It
     makes some of Pillar 4's choices early; ADR 0030 records them.
4. **Mounting into a Django page.** Doing it here was rejected: a template
   tag, a view, a template and a Node build stage in the Dockerfile, in a PR
   that is already about the component. Pillar 4 needs the same build stage
   and the theme `<link>`, so mounting moves there.
5. **pnpm hardening.** Recorded separately in ADR 0029.

Implementation defaults:

6. **Page size.** The component sends `page_size=12` itself, rather than
   relying on the server's default, because it computes the page count from
   `count`.
7. **Pagination names.** Links carry `aria-label="Page 2"`, `"Next page"`.
   Visually hidden text was rejected: Testing Library's name calculation drops
   the space in `<span>Page </span>2` while browsers keep it, so tests and
   screen readers would disagree. The visible text is part of each name
   (WCAG 2.5.3).
8. **Announcements.** One visually hidden `role="status"` region, mounted
   from the first render, silent until the first user change. Reading the
   count on page load was rejected as chatter. `aria-busy` was rejected:
   NVDA and VoiceOver mishandle it in live regions.
9. **A page past the end** (DRF's 404) replaces the URL with page 1 and shows
   the loading state until page 1 arrives, so the error alert doesn't flash
   and get announced.
10. **Errors.** A 10-second timeout. One message per error kind (network,
    timeout, HTTP, contract), chosen in an exhaustive `switch`. Schema
    details go to the console, never the UI.
11. **Ratings** are drawn as on the server-rendered cards: full stars rounded
    down, the value rounded half up to one decimal. `toFixed()` was rejected:
    it shows 4.05 as "4.0".
12. **The card** has one link, the brand title, stretched over the card with
    `::after`, so it's one tab stop. The top review is a quote with the
    reviewer and title, without its own link, which would add a second tab
    stop per card. The brand path `/brand/<slug>/` is written in the
    component, matching Django's route. Django's `_brand_card.html` gains the
    same `c-card__link` class.
13. **Entry point.** `build.rolldownOptions.input`, not the top-level `input`
    the research preferred: the top-level option also applies to the dev
    server, whose entry is the dev page. `base` is `/static/frontend/` for
    builds only.
14. **Zod, not `zod/mini`.** The build is 96 kB gzipped, mostly React DOM and
    Zod. `zod/mini` would shrink Zod, but it brings a second API style for
    one schema.

## Decision
- **Props:** `apiUrl` and `industries`. `mount.tsx` reads them from
  `data-api-url` and a `json_script` block, validates the industries with
  Zod, and fails loudly on a misconfigured page.
- **State:** the URL is the source of truth (`industry`, `ordering`, `page`,
  the API's names). It's read with `useSyncExternalStore` over
  `location.search` and parsed by pure functions in `urlQuery.ts`: unknown
  values are dropped, defaults omitted, the order is fixed, and parameters
  the component doesn't own (`utm_*`) are kept. A bad URL is corrected with
  `replaceState`.
- **History:** filter, clear and page changes push an entry. Repeated sort
  changes share one, tagged in `history.state`. Corrections replace.
- **Fetching:** `useBrands` refetches when the request URL changes, aborts
  the request it replaces, and derives "loading" from whether the settled
  result answers the current request. `fetchBrands` never throws; it returns
  a typed result, and the response is `safeParse`d.
- **Rendering:** checkboxes in a `<fieldset>` inside `<search>`, a native
  `<select>` for sort, pagination as links with `aria-current="page"`.
  Skeleton cards on first load, the previous results dimmed on later loads,
  an empty state with Clear filters, and an error alert with Retry. Focus
  moves to the results heading only when the focused control goes away
  (Clear filters, Retry, a page link).
- **Tests:** the contract fixture, the pure URL functions, the component
  through roles with `fetch` stubbed, axe in each state, a Tab-order pass,
  and the mount code.

## Consequences
- The component depends on `theme.css` being on the page (ADR 0023). The dev
  page imports it; a Django page will link it.
- Until Pillar 4 mounts it, the component runs only on Vite's dev page.
- The brand path is in two places: Django's URLconf and `BrandCard.tsx`.
- Colour contrast, target size and screen-reader announcements need a real
  browser: jsdom can't check them, so axe runs with those rules off.

## Revisit when
A second data-driven component appears (TanStack Query with `retry` tuned,
and CSS Modules per ADR 0023), the Navigation API becomes widely available
(projected 2028), or a mobile client needs infinite scroll (ADR 0022).

## Sources
`docs/research/pillar-3-brandlist-component.md` §2–13 and "Open decisions";
Vite 8.3.5 `index.d.ts` (`build.rolldownOptions`, shared `input`), Sass
1.107.1 `types/deprecations.d.ts`, checked in `node_modules` 2026-11-09.
