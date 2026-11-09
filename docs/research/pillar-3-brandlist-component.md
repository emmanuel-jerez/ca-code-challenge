# Pillar 3: the React `<BrandList />` component

Researched 2026-11-09. This note covers the component itself: data fetching, URL state, React 19, accessible controls and states, responsive layout, how it consumes the SCSS tree, how it mounts into Django, tests, and the frontend supply chain. It builds on `best-practices-2026.md` §6 and `stack-validation.md` §3.5–3.6 and does not repeat them. Where they are wrong or out of date, it says so (see "Conflicts with accepted decisions"). The SCSS tree is Pillar 4 and the endpoint is Pillar 2. They appear here only where the component depends on them.

Two goals frame every recommendation: **security first** (each option is costed in attack surface) and an **LTS mindset** (each option is costed in stability). Styling with SCSS is decided (ADR 0011). Only *how* the component consumes it is open.

> **Method.** Context7 answered the React, Zod, pnpm, Vite and Vitest lookups; the quota was not exhausted. Baseline data comes from the webstatus.dev API [31], advisories from the OSV API, and package metadata from read-only `npm view` [14]. Dependency counts come from a metadata-only `pnpm install --lockfile-only` in a scratch directory outside the repo (pnpm 12.16.1, `minimumReleaseAge: 10080`, `trustPolicy: no-downgrade`) [15]. Nothing was installed into the repo and nothing was built or run. Claims marked *(secondary)* come from non-primary sources.

---

## Key findings

1. **Client-only React stays clear of the whole RSC CVE class.** OSV lists 8 advisories against `react-server-dom-*` between Dec 2025 and Jul 2026, starting with CVE-2025-55182 (critical, unauthenticated RCE) [5]. The 2026-10-14 patch releases (19.3.1, 19.2.9, 19.1.10, 19.0.9) changed only the RSC transport [1]. `react` and `react-dom` have had no advisory since 2018 [6], and the planned lockfile contains no `react-server-dom-*` package [15].
2. **A small custom hook (`fetch` + `AbortController` + Zod) covers everything this component needs, with zero new dependencies.** The libraries' headline features are either unnecessary for one endpoint or need switching off. TanStack Query retries 3 times by default before showing an error [23]. SWR passes no `AbortSignal` to the fetcher [24][25]. `use()` + Suspense needs your own promise cache [8], and with a URL store it shows the fallback on every filter change [7].
3. **The TanStack org was compromised on 2026-05-11.** Attackers published 84 malicious versions of 42 `@tanstack/*` router and start packages. The versions carried valid trusted-publisher provenance and stole credentials at install time [20]. The query packages were not in the advisory, but the incident shows that provenance and pnpm's `trustPolicy` would not have caught it. The 7-day cooldown would have.
4. **URL state needs no router.** Use `useSyncExternalStore` over `location.search`, with `pushState`/`replaceState` and `popstate` [7][28][29]. The History API has been Baseline since 2015. The Navigation API has only been Baseline *newly* available since 2026-01-13, and becomes *widely* available around 2028-07 [30], so it doesn't meet the LTS bar yet.
5. **Zod must be ≥ 4.6.6.** CVE-2023-54404 (High, published 2026-10-01) lets an oversized failing array exhaust memory, and 4.6.6 fixes it [19]. The planned `^4.6.7` is fine. Also cap `results` with `.max()`. `z.object` strips unknown keys by default [17], so the API can add fields without breaking the UI.
6. **Don't rely on `aria-busy` for loading.** The spec says assistive technologies *may* ignore changes while busy [39]. NVDA ignores busy live regions and stays silent when busy is removed, and VoiceOver/Safari missed the removal [45]. Use one always-mounted `role="status"` region instead [39][44]. This corrects `best-practices-2026.md` §6.
7. **Don't move focus on filter or sort changes.** Moving focus is a change of context (WCAG 3.2.2) [37]. *Do* move focus when the focused control disappears: Retry, Clear filters, or a page link that re-renders.
8. **Native controls win.** Use a checkbox group in `<fieldset>`/`<legend>` inside `<search>`. `<search>` has been widely available since 2026-04-13 [31], and the HTML spec names "filtering" as its purpose [47]. `<select multiple>` has non-standard keyboard behaviour and poor discoverability [43]. A custom listbox brings a complex keyboard model [40].
9. **Two contrast traps in the WP tokens.** `--color-border` (#e5e7eb on white) is 1.24:1, so it must not outline custom-styled controls, which need 3:1 under SC 1.4.11 [33]. `--color-muted` on the page background is 4.51:1, which passes 4.5:1 by 0.01. (Ratios computed for this note.) Separately, the WP stars markup puts `aria-label` on a `<span>`, which ARIA 1.2 prohibits [39]. axe flags this as `aria-prohibited-attr` [65].
10. **Vite's production build fits a strict CSP, with two gotchas.** First, `build.assetsInlineLimit` (4 KiB) inlines small assets as `data:` URIs; set it to `0` [48][50]. Second, the dev-mode React Refresh preamble is an inline script [51]. React's `style` prop is safe because React DOM sets styles through CSSOM, which `style-src` doesn't block [13][57].
11. **django-vite fails the vetting rule that ruled out django-csp.** Version 3.2.0 (2026-09-14) declares Django ≤ 4.2 and Python ≤ 3.12, and its CI stops at 3.12 [58]. A ~30-line template tag that reads Vite's manifest is enough.
12. **Use a plain fetch stub, not MSW.** MSW 3.0.3 would add 45 packages to the dev tree [15]. Five of them (`debug`, `ansi-regex`, `ansi-styles`, `strip-ansi`, `wrap-ansi`) had malicious versions published on 2025-09-08 [67]. pnpm is now on 12, not 10/11. Setting `minimumReleaseAge` explicitly makes it fail instead of falling back. `trustPolicy` is off by default. `onlyBuiltDependencies` was removed in v11 in favour of `allowBuilds` [68][69].

---

## 1. React 19: version, support, and the RSC CVEs

**Where things stand.** React 19.3.1 is `latest` (2026-10-14). 19.3.0 shipped on 2026-09-09 [1][2]. React publishes no support window. Its policy promises backported security fixes "for all major versions that are affected" and reserves patches for critical bugs and security issues [3]. In practice, RSC fixes went to 19.0.x, 19.1.x and 19.2.x in parallel [1].

| Advisory | Package | Type |
|---|---|---|
| CVE-2025-55182 (Dec 2025) | `react-server-dom-*` | **Critical** unauthenticated RCE ("React2Shell") |
| CVE-2025-55183 | same | Source code exposure |
| CVE-2025-55184, CVE-2025-67779 | same | DoS |
| CVE-2026-23864 (Jan), -23869 (Apr), -23870 (May), -44907 (Jul) | same | DoS (High) |
| 19.x.y releases of 2026-10-14 | same | "Improve transport protocol", no advisory found |

Sources: [1][5]. The advisory for CVE-2026-44907 says it directly: "If your app's React code does not use a server, your app is not affected" [5].

**Why client-only avoids it.** Every one of these lives in `react-server-dom-webpack/parcel/turbopack`, the server half of RSC. A Vite SPA never installs those packages. The resolved lockfile for the planned set contains none of them [15]. The client packages' last advisory was CVE-2018-6341, an SSR XSS in `react-dom` [6].

**Defend it:** "Every React CVE of the last year is in the server-components runtime. My build doesn't contain that package, which I checked in the lockfile, so the whole class doesn't apply. React backports security fixes to every affected major, so staying on 19.x is safe."

---

## 2. Data fetching

**Requirement.** Fetch `GET /api/brands/?…` whenever URL state changes. Drop stale responses and cancel in-flight requests. Show loading, empty and error states. Survive StrictMode's double effect run. Validate the response (ADR 0010).

| | Plain `fetch` + `AbortController` in a custom hook | TanStack Query 5 | SWR 2 | React 19 `use()` + Suspense |
|---|---|---|---|---|
| **Runtime packages added** | 0 | +2 (`@tanstack/react-query`, `query-core`) [15] | +3 (`swr`, `dequal`, `use-sync-external-store`) [15] | 0 |
| **Out-of-order responses** | Abort the previous request in effect cleanup. Only the current key's result is committed [10] | Keyed by query key. The `AbortSignal` is passed to `queryFn` and aborted when the query goes out of date [22] | Discards stale results, but **gives the fetcher no `AbortSignal`**. PR #2275 to add one was closed unmerged [24][25] | Needs a promise cache keyed by URL [8]. A cached promise can't be cleanly aborted |
| **Caching** | None. A ~10-line `Map` keyed by URL would make Back instant (optional) | Yes. `staleTime` defaults to 0 and `gcTime` to 5 min [23] | Yes. `revalidateOnFocus` defaults to true [24] | Your own cache |
| **StrictMode (dev)** | Two requests; the first is aborted. "In production, there will only be one request" [10] | Handled | Handled | A promise created during render triggers the "uncached promise" warning [8] |
| **Error UX** | You control it | Retries **3 times with exponential backoff** before an error shows [23]; set `retry: false` or 1 | `shouldRetryOnError` defaults to true [24] | Needs an Error Boundary: a class component or another dependency |
| **Security history** | Platform only | No advisories on the query packages. Same org as the May 2026 compromise (router/start, separate repo) [20][21] | No advisories. Vercel-owned | Platform only |
| **Stability** | Platform APIs; Abortable fetch has been Baseline since 2019 [31] | v5 since 2023-10, but **68 releases in 2026** [14] | v2 since 2022-12; 5 releases in 2026 [14] | API is stable. Suspense for client data is framework territory per react.dev [10] |
| **Why it might lose** | You own race, abort and error code and must test it | A cache and devtools for one endpoint and one component; the constant release churn collides with the cooldown | No cancellation | Worst UX here (see §5) and the most novel pattern |

React's own docs don't force a library. They recommend "using or building a client-side cache" or a framework, and accept Effects "if neither of these approaches suit you" [10]. They also suggest extracting the fetch logic into a custom hook so a library can replace it later [9].

**Implementation shape (custom hook).**
- `useBrands(query)` returns a discriminated union: `{status: 'loading', previous?} | {status: 'success', data} | {status: 'error', error, previous?}`.
- The effect depends on the **canonical query string**, not on an object (§4), so it runs only when the request actually changes.
- Pass `signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10_000)])`. Both have been widely available since Sep/Oct 2026 [31], and jsdom implements both [66]. A timeout rejects with `TimeoutError`; a cleanup abort rejects with `AbortError` [32]. Ignore `AbortError`; show `TimeoutError` as an error.
- Model errors as a typed union rendered with an exhaustive `switch` + `assertNever` (ADR 0013):

```ts
type BrandsError =
  | { kind: 'network' } | { kind: 'timeout' }
  | { kind: 'http'; status: number }         // 404 "Invalid page." → reset page (see §13)
  | { kind: 'contract'; summary: string };   // Zod mismatch; summary goes to console, not the UI
```

- A Retry action bumps a `reloadKey` in the effect's dependencies.

**Recommendation:** the custom hook. It needs zero new packages, the abort semantics are explicit, and it's small enough to defend line by line. If a second data-driven component appears, revisit TanStack Query (with `retry` tuned) rather than SWR, because SWR doesn't cancel.

**Defend it:** "One endpoint, one component: I don't need a cache library. The effect aborts the previous request in cleanup, so a slow old response can't overwrite a new one. In dev you'll see two requests because of StrictMode; the first is aborted. TanStack shipped 68 releases this year and its org was compromised in May. That's a lot of surface for features I'd mostly switch off."

---

## 3. Validating the response with Zod

**Version.** Zod 4.6.7 (2026-10-12) is `latest`. v4 has been out since 2025-07-09, and there were 19 releases in 2026. It has one npm maintainer, publishes with provenance, and has no dependencies [14][15]. **Floor: 4.6.6**, because CVE-2023-54404 (High, GHSA published 2026-10-01) covers memory exhaustion from large arrays with many failing elements "through 4.6.5" [19].

**Patterns.**
- `safeParse` the JSON. Never `parse` in the render path. On failure, `z.prettifyError(error)` gives a readable multi-line summary for the console [16]. Users get the generic error state with Retry, never schema text.
- Use `z.object` (the default strips unknown keys [17]) rather than `z.strictObject`. The API can then add fields first (expand) without breaking the UI, which matches the expand → migrate → contract rule in AGENTS.md.
- Cap the array: `results: z.array(Brand).max(MAX_PAGE_SIZE)`. That bounds work even on a pre-4.6.6 parser and mirrors the API's page-size cap.
- The same Zod schema validates the industries list from `json_script` (§9), which is also a boundary.
- URL params can reuse Zod: `z.coerce.number().int().positive().catch(1)` for `page` and `z.enum([...]).catch(DEFAULT_SORT)` for sort [17]. `.catch()` returns the fallback instead of failing.
- `zod/mini` ships in the same package and version, with a function-style API. The docs' example shows a 64% smaller gzip bundle [18]. It's optional and not worth a second API style for one schema.

```ts
// Field names are illustrative; Pillar 2 owns the contract.
const Brand = z.object({ slug: z.string(), name: z.string(), industry: Industry.nullable(),
  averageRating: z.number().min(0).max(5).nullable(), reviewCount: z.number().int().nonnegative(),
  shortDescription: z.string(), topReviewSnippet: z.string().nullable() });
```

**Defend it:** "The response is untrusted input at a boundary, so it's parsed, not cast. A mismatch becomes the same error state as a 500, with Retry. I stay on Zod 4.6.6+ because of this October's memory-exhaustion CVE, and I cap the array anyway."

---

## 4. URL-synced state without a router

**Requirement.** Filter, sort and page live in the URL (AGENTS.md: shareable, back button works). Bad params must be normalized. The page resets on filter change.

| | `useSyncExternalStore` + History API | nuqs 2.10.2 | React Router 8.5.1 |
|---|---|---|---|
| Packages | 0 | +2 (`nuqs`, `@standard-schema/spec`) [15] | +3 (`react-router`, `cookie-es`, `@remix-run/route-pattern`) [15] |
| Maintainers | — | 1 [14] | 2 [14] |
| Security history | — | No advisories | **20 advisories, Apr 2025–Jul 2026**. Most are framework/SSR/RSC mode, but CVE-2025-68470 and its bypass CVE-2026-53669 hit `<Link>`/`useNavigate` [27] |
| Stability | History API widely available since 2015 [28] | v2 since 2024-10; 13 releases in 2026 [14] | Majors in 2021, 2024 and 2026 (8.0.0 on 2026-06-17) [14] |
| Fit | Exactly what's needed | Has a plain-React adapter and a `serverSearch` prop for server-rendered islands (v2.10+) [26] | Wants to own routing. Overkill for a query string on a Django page |
| Why it might lose | ~40 lines you own and test | A single-maintainer dependency for ~40 lines | Weight, churn and advisory history |

**How the store works.**
- The snapshot is `window.location.search`. It's a string, so it's stable under `Object.is`, which `getSnapshot` requires [7]. Parse it in render (memoized). Never return a new object from `getSnapshot`, or React loops [7].
- `subscribe` listens to `popstate`. `pushState` and `replaceState` don't fire `popstate` [28], so the module's own `navigate()` notifies its listeners after calling them.
- Declare `subscribe` outside the component so React doesn't re-subscribe every render [7].
- Caveat: store updates can't be marked as Transitions. React renders them as blocking updates, and suspending on a store value shows the nearest Suspense fallback [7]. That's fine here because rendering 5–20 cards is cheap. It's also why `use()` + Suspense is a poor match (§5).
- `pushState` throws for a cross-origin URL [29]. Only the query string of the current path is ever changed, so the open-redirect class behind the React Router CVEs [27] can't arise.

```ts
// Sketch, not an implementation
const subscribe = (cb: () => void) => { listeners.add(cb); addEventListener('popstate', cb);
  return () => { listeners.delete(cb); removeEventListener('popstate', cb); }; };
const getSnapshot = () => location.search;
```

**Push vs replace.**

| Event | History | Why |
|---|---|---|
| Toggle an industry checkbox | push | A discrete decision; Back undoes it |
| Change sort | push, but **replace** if the current entry also came from a sort change | Coalesces repeated changes from one control (see "Not verified": arrow keys on a closed `<select>`) |
| Pagination link | push | Behaves like a link; Back returns to the previous page |
| Page reset caused by a filter or sort change | Same entry as that change | One user action, one entry |
| Normalizing bad or missing params on load | replace | A correction, not a navigation |
| Typing in a text box (out of scope: no search) | replace, debounced | Avoids one entry per keystroke |

**Normalizing params.**
- `industry`: keep only slugs in the allow-list (from `json_script`), de-duplicate, and sort, so URLs and the effect key are canonical.
- `sort`: an allow-listed enum; otherwise the default. The backend allow-lists too: `order_by` CVEs, per `best-practices-2026.md` §0.
- `page`: a positive integer, otherwise 1. If the API answers 404 `"Invalid page."` (DRF's `PageNumberPagination` raises `NotFound` [60]), replace the URL with page 1 and refetch.
- Omit defaults (`page=1`, the default sort) from the URL.
- **Preserve unknown params** (e.g. `utm_*`) in the address bar, but don't forward them to the API.

**Navigation API.** It has been Baseline *newly* available since 2026-01-13 (Firefox 147, Safari 26.2), with *widely* available projected for 2028-07-13 [30][31]. It would buy a central `navigate` event, but this component needs two calls and one event. **Not worth it yet**; revisit in 2028.

**Recommendation:** the hand-rolled store. Keep the parse/serialize logic in **pure functions** (`parseQuery`, `toSearch`, `toApiParams`) so they're unit-tested without React.

**Defend it:** "The URL is the single source of truth. The component subscribes to it with `useSyncExternalStore`: push for user decisions, replace for corrections. Params are untrusted, so they're parsed against allow-lists and canonicalized. No router, because I only own a query string on a page Django routes."

---

## 5. React 19 features: what helps, what doesn't

| Feature | Verdict | Why |
|---|---|---|
| `useSyncExternalStore` | **Use** | The documented way to read a browser store [7] |
| `useId` | **Use** | Ids for `aria-labelledby` and `aria-describedby` |
| `<StrictMode>` | **Use (dev)** | Exposes missing effect cleanup. Expect the double fetch [10] |
| `useTransition` | Skip | URL store updates can't be Transitions [7]. With `await` inside, "Actions within a Transition do not guarantee execution order" and React points to your own "queuing and abort logic" [11] |
| `useDeferredValue` | Skip | Defers *rendering* and "does not by itself prevent extra network requests" [12]. Rendering isn't the bottleneck here |
| Actions / `useActionState` | Skip | Built for mutations and forms. It queues in order instead of cancelling [11], which is wrong for filters |
| `use()` + Suspense | Skip | Needs a promise cache [8] and an Error Boundary. Paired with a URL store, every filter change swaps results for the fallback [7] |
| `<ViewTransition>` (stable in 19.3) | Skip | Adds motion (gate behind `prefers-reduced-motion`) and novelty. View Transitions have only been Baseline newly since 2025-10-14 [4][31] |
| Trusted Types support (19.3) | Later | React now passes `TrustedHTML` through [4]. Trusted Types have been Baseline newly since 2026-02-24 [31]. That would let ADR 0005's policy add `require-trusted-types-for 'script'` someday |
| React Compiler | Skip | An extra build plugin; nothing here is render-bound |

**Defend it:** "I used the React 19 features that solve problems I have, `useSyncExternalStore` and `useId`. Transitions, Suspense and Actions solve problems I don't have, and the docs say transitions don't order async results anyway."

---

## 6. Accessible controls and states (WCAG 2.2 AA)

### Controls

| Industry filter | For | Against |
|---|---|---|
| **Checkbox group in `<fieldset>` + `<legend>`** | Native multi-select. Tab moves between boxes and Space toggles (APG checkbox pattern [41]). Only 5 industries exist in the WP data | Needs multi-value support in the API (§13) |
| Single `<select>` with "All industries" | Compact; native | Single choice only |
| Radio group | Native single choice | Arrow keys change the selection immediately, so each keypress triggers a fetch |
| `<select multiple>` | Native | Ctrl/Cmd-click to multi-select; keyboard "not standardized"; MDN says to always tell users it's multi-select [43] |
| Custom listbox | Full styling control | A complex keyboard model (Shift+Arrow, Ctrl+A …) [40]; "a role is a promise" and ARIA adds no keyboard behaviour [42] |

- **Sort:** a native `<select>` with a visible `<label>`. Changing it updates content, not context, so 3.2.2 is satisfied without an Apply button [37].
- **Wrapper:** put the controls in a `<search>` element. It has been widely available since 2026-04-13 [31], and the HTML spec defines it for "a way of searching or filtering search results on the current web page" [47]. Inside, use a `<form>` whose submit is prevented (Enter does nothing harmful).
- **Clear filters:** a `<button type="button">`, shown only when filters are active.
- **Pagination:** `<nav aria-label="Pagination">` holding **links** (`<a href="?industry=…&page=2">`) whose click is intercepted with `preventDefault` + push. Links give open-in-new-tab and copy-link for free. Mark the current page `aria-current="page"`; ARIA names pagination as the example use [39]. At the ends, render "Previous"/"Next" as plain text, not a disabled link. Hide the nav when there's only one page.
- **Results:** an `<h2>` heading, then `<ul>` → `<li>` → `<article>`, each with an `<h3><a href="/brand/slug/">` as its single link. To make the whole card clickable, stretch the link with a pseudo-element; that keeps one tab stop.
- **Rating:** visible text ("4.5") plus visually hidden "out of 5, 12 reviews"; stars `aria-hidden="true"`. **Don't copy WP's `<span class="stars" aria-label="…">`.** ARIA 1.2 prohibits naming the `generic` role [39], and axe reports it as a serious `aria-prohibited-attr` failure [65].
- **Top review snippet:** render it as **plain text** (§13). The component never uses `dangerouslySetInnerHTML`.

### Announcing changes

- **One `role="status"` element, always mounted** from first render. `status` implies `aria-live="polite"` and `aria-atomic="true"` [39]. MDN advises establishing a live region in the initial markup before updating it, and adding a redundant `aria-live="polite"` for compatibility [44].
- **Message:** "5 brands. Insurance, Telecom. Sorted by highest rating. Page 1 of 1." Brief result counts are the textbook status message; the list itself is not [36].
- Announce after user-initiated changes and on `popstate`. Skip the initial load to avoid page-load chatter. While loading, the status says "Loading brands…". Optionally delay it ~300 ms so fast responses don't double-announce.
- **No `aria-busy`.** The spec says AT "MAY ignore changes" while busy [39]. NVDA "doesn't fully support aria-busy for live regions" and stays silent afterwards, and VoiceOver/Safari didn't register the removal [45]. Live regions also never announce while hidden [46] *(secondary)*.
- **Errors:** render the message plus Retry in an element with `role="alert"` (4.1.3 situation B, ARIA19) [36].
- *(secondary)* 2026 testing shows polite timing varies across screen reader/browser pairs [46]. Test with NVDA + Firefox and VoiceOver + Safari.

### Focus management

| Trigger | Focus | Why |
|---|---|---|
| Checkbox or sort change | **Stays put** | Moving focus is a change of context (3.2.2) [37] |
| Back/Forward (`popstate`) | Stays put | Announce via status |
| Page link activated | Move to the results `<h2 tabindex="-1">` and scroll it into view | The new content is above. The clicked link may disappear at the last page |
| Retry or Clear filters succeeds | Move to the results heading | The button that had focus is gone; otherwise focus falls to `<body>` |

Ensure that heading isn't hidden under a sticky header. That's SC 2.4.11 (new in 2.2) [38]; use `scroll-padding-top` (technique C43) [38].

### Loading, empty and error states

- **First load:** skeleton cards at final size, `aria-hidden="true"`, while the status region carries the text. Skeletons avoid layout shift. A spinner needs its own accessible text, which the status region already supplies.
- **Refetch:** keep the previous results visible and dimmed. Don't remove them and don't `inert` them; the status region tells AT users.
- **Empty:** "No brands match Insurance." plus a Clear filters button.
- **Error:** a human message ("We couldn't load brands.") plus Retry. Never raw error or schema text.

### WCAG 2.2 criteria that bite here

- **2.5.8 Target Size (Min), new in 2.2:** targets must be ≥ 24×24 CSS px or meet the spacing exception (a 24 px circle centred on each target, not intersecting its neighbours) [35]. Native checkboxes at their default size fall under the user-agent exception [35]. Custom-styled ones don't. Make each label row ≥ 24 px tall anyway; label clicks activate the control on most platforms [47].
- **2.4.11 Focus Not Obscured (Min), new in 2.2:** see above [38].
- **2.5.7 Dragging, new in 2.2:** no dragging is involved. Keep it that way: no slider for the rating filter [34].
- **2.4.7 Focus Visible:** use a `:focus-visible` outline in `--color-primary` (5.47:1 on white) [33]. `:focus-visible` has been widely available since 2024-09-14 [31].
- **1.4.11 Non-text Contrast:** control boundaries need 3:1 unless left to the user agent [33]. `--color-border` is 1.24:1 on white, so use something like `--color-muted` (4.83:1) for custom control borders. The stars (2.15:1) pass only because the numeric text carries the meaning.
- **1.4.3 Contrast:** `--color-muted` on `--color-bg` is 4.51:1 [33]. It passes, but any token tweak breaks it.

**Defend it:** "Native controls first, so the browser gives me keyboard support and semantics for free. One polite status region announces counts. I don't use `aria-busy` because NVDA and VoiceOver handle it badly with live regions. Focus stays where the user is unless the thing they were on disappears."

---

## 7. Responsive layout

- **Grid without breakpoints.** The WP CSS uses `minmax(280px, 1fr)` and needs a `@media (max-width: 640px)` override, because 280 px plus 48 px of padding overflows narrow screens. `repeat(auto-fill, minmax(min(100%, 17.5rem), 1fr))` never overflows. That meets **1.4.10 Reflow** at 320 CSS px [33] without a media query.
- **Container queries** for the card's internal layout and the filter bar. Put `container-type: inline-size` on the component root, so it adapts to wherever Django mounts it (full width or sidebar). Size container queries have been **widely available since 2025-08-14** [31]. Style queries (newly available since 2026-05-19 [31]) are not needed.
- **Breakpoints stay Sass variables** (AGENTS.md: custom properties don't work in media queries). They can be interpolated into `@container (min-width: #{$bp-md})`. A container's width isn't the viewport, though, so give the component its own container breakpoints rather than reusing the viewport ones.
- **Logical properties** (`margin-block`, `padding-inline`, `inset-inline`) have been widely available since 2024-03-20 [31]. They're RTL-ready at no cost.
- **Motion:** wrap the WP card hover (`transform: translateY(-1px)`, transitions) and any skeleton shimmer in `@media (prefers-reduced-motion: no-preference)`. That query has been widely available since 2022 [31].
- **Filter bar:** on mobile, the fieldset stacks vertically. In wider containers, checkboxes wrap inline (`flex-wrap`) and the sort select sits at the end.

**Defend it:** "The grid is intrinsically responsive, so it reflows at 320 px with no breakpoint. Container queries let the card adapt to its slot, not the viewport. Breakpoints remain Sass variables because custom properties can't go in media queries."

---

## 8. Styling integration (open decision)

All three options cost **zero new dependencies**. Vite compiles `.scss` with the already-chosen `sass`, and CSS Modules support is built in: `postcss-modules` is a Vite *devDependency* (bundled into Vite's build) and is absent from the resolved lockfile [14][15]. All three also produce **external `.css` files** in production [50][51], so CSP is equal. The differences are coupling, collisions, conventions and longevity.

### Vite 8 facts that apply to every option
- Only the **modern Sass API** remains; Vite 7 removed the legacy API and its `api` option [53]. Vite uses `sass-embedded` if it's installed, otherwise `sass` [49].
- `css.preprocessorOptions.scss` passes Sass options through [49]. Set `loadPaths` so component files write `@use 'tokens'`, not `../../scss/tokens` [56]. Load paths apply only when no relative file matches [55].
- **`additionalData` duplicates real CSS** in every compiled file [49]. Use it for nothing, or only for CSS-free partials.
- Sass `@use` emits a module's CSS once **per compilation** [55]. Each `.module.scss` (or each separate entry) is its own compilation, so **only `@use` partials with no CSS output** (variables, maps, functions, mixins) from component files. Emit `:root` custom properties once, from the global entry.
- CSS Modules: `*.module.scss` files go through `postcss-modules` and are configured by `css.modules` [48][49]. With the experimental `css.transformer: 'lightningcss'`, `css.modules` is **ignored** and `css.lightningcss.cssModules` applies instead [48][49]. That's a config-path risk if Vite's default ever changes. Lightning CSS is already the default *minifier* [50].
- Vitest doesn't process CSS by default. CSS Modules return a proxy, and class names are only real if `test.css.include` is set [61]. Tests should query by role anyway [64].

| | **A. Global BEM partials in `frontend/scss/`** | **B. Co-located `BrandList.module.scss`** | **C. Hybrid** |
|---|---|---|---|
| Shape | `components/_brand-list.scss` in the shared tree, in `@layer components`. Reuses the global `.card`, `.badge`, `.stars` and `.pagination` blocks the Django templates also use | All component styles scoped by the build. Tokens via `@use` (CSS-free) plus `var(--…)` | Tokens, base and shared blocks (`card`, `badge`, `stars`, `pagination`) stay global. Component-only layout (filter bar, grid, skeleton, status) goes in a module |
| Collisions | Prevented by BEM block names, `@layer` and a Stylelint naming rule. It's discipline, not enforcement | Enforced by the build | Enforced for component-only classes |
| Coupling | Needs the host page to load the global CSS. The dev harness must import it too | Self-contained | Shared blocks need the global CSS |
| Duplication | None. One `.card` serves Django and React | Either duplicates card/badge/stars, or reaches out with `:global(...)` / `composes` | None |
| Conventions to explain | One (BEM + layers), the same answer for Django and React | Two worlds: BEM in templates, Modules in React | Two, with a rule for which goes where |
| Longevity | Plain Sass and CSS: survives a bundler change | CSS Modules is a community spec, not a web standard. Config differs between the PostCSS and Lightning CSS paths [48]. Native `@scope` is only Baseline newly (2026-03-24) [31] | Mixed |
| Testability | Same (query by role) | Same; class names are proxies [61] | Same |
| Why it might lose | "A second engineer could still collide": it relies on conventions | Duplicates the design system the challenge grades | More rules to defend in a 1-hour call |

**Recommendation: A, global BEM partials.** The user picked SCSS for being close to CSS, and A keeps plain CSS semantics with no build-time renaming. Django pages and the React card share one `.card`/`.badge`/`.stars`, and Pillar 4 grades exactly that structure. It also outlives any bundler or Lightning CSS switch. The Django base template links the global CSS on every page. The island entry imports no CSS, and the Vite dev harness imports the theme entry (`theme.scss` in the Pillar 4 note) so the component looks right in isolation. This matches the Pillar 4 note, which also leans to a global BEM partial and leaves the call to Pillar 3. **Revisit** (move to C) once more React components or more teams appear and enforced scoping starts paying for its second convention.

**Defend it:** "The React card *is* the WP card, so it uses the same BEM blocks the Django templates use. One design system, one convention. Collisions are prevented by block names and cascade layers. If more React components arrive, I'd scope the component-only bits with CSS Modules, which Vite supports with no extra dependency."

---

## 9. Mounting into Django, dev proxy and CSP fit

**Production.**
1. Vite config: the top-level `input` option (documented in 8.3.5 and preferred over `build.rolldownOptions.input` because dev uses it too) [49][50], `build.manifest: true` [50], `build.assetsInlineLimit: 0` [48][50], and `base` set to where Django serves the files (e.g. `/static/frontend/`) [49]. If Vite compiles the theme entry too, add it as a second input; a manifest entry can be CSS [51]. The Pillar 4 note compares the Sass CLI with Vite for the theme; either works with this tag, because the island only needs its own JS entry.
2. Set `build.modulePreload: { polyfill: false }`. Vite injects the polyfill only into `index.html` entries. With a custom JS entry you would have to import `vite/modulepreload-polyfill` by hand [50][51]. There's no need: `<link rel="modulepreload">` has been widely available since 2026-03-18 [31], and a single entry has nothing to preload anyway.
3. A Node build stage writes `dist/`. Django collects it as static files and whitenoise serves it (ADR 0008). The runtime image has no Node.
4. A **custom template tag** (~30 lines, estimate) reads `.vite/manifest.json` once. For the entry it emits `<link rel="stylesheet">` for each `css` file, then `<script type="module" src>` for `file`, both through `static()`. That's the order Vite's backend guide prescribes [51]. Fail loudly if the manifest is missing.
5. The template provides `<div id="brand-list" data-api-url="{% url … %}">` plus `{{ industries|json_script:"brand-list-industries" }}` (ADR 0005). `main.tsx` reads both and validates the JSON with Zod.

```ts
// vite.config.ts (fragment)
export default defineConfig({
  base: '/static/frontend/', input: { brandList: 'src/brand-list/main.tsx' },
  build: { manifest: true, assetsInlineLimit: 0, modulePreload: { polyfill: false } },
  css: { preprocessorOptions: { scss: { loadPaths: [fileURLToPath(new URL('./scss', import.meta.url))] } } },
  server: { proxy: { '/api': 'http://localhost:8000' } },
});
```

**django-vite vs the tag.** django-vite 3.2.0 (2026-09-14) declares Django 3.2–4.2 and Python 3.8–3.12. Its tox/CI matrix stops at Python 3.12 and Django 5.1, there was an 18-month gap before 3.2.0, and it has one runtime dependency [58]. That's the same "no declared 3.14 support" gap that rejected django-csp in ADR 0005. Its `vite_react_refresh` tag also emits an **inline** script and takes a nonce [58], which clashes with ADR 0005's no-nonce policy in dev. **The tag wins.**

**Dev setup.**
- **Recommended: the Vite dev server with its own `index.html` harness** and `server.proxy` sending `/api` to Django [52]. HMR works. The page is Vite's, not Django's, so ADR 0005's CSP isn't involved. Same-origin requests through the proxy avoid CORS.
- The alternative is a Django page loading `@vite/client` from `localhost:5173`. That needs the React Refresh preamble as an **inline** `<script type="module">` [51], plus `script-src`/`connect-src` exceptions for the dev origin. It conflicts with `script-src 'self'` and no nonces.
- Check integration and CSP by serving a `vite build --watch` output through Django.
- Security: every Vite advisory since 2025 concerns the **dev server** (`server.fs.deny` bypasses, WebSocket file read, launch-editor), not the built bundle [54]. Keep the default `server.host: 'localhost'` [52]. If it runs in Compose, publish it as `127.0.0.1:5173:5173`. The same goes for Vitest's UI/API servers (CVE-2025-24964, CVE-2026-47429) [72].

**CSP fit (ADR 0005).**
- The built bundle is external JS and CSS, so `script-src 'self'` holds. `json_script` emits a non-executed data block (ADR 0005's premise).
- With assets inlined (the 4 KiB default), `img-src`/`font-src` would need `data:`. Vite's docs say to allow it or set `assetsInlineLimit: 0`, and never `data:` in `script-src` [48].
- React's `style={{…}}` writes through `style.setProperty`/`style[prop]` [13]. CSSOM property writes are not blocked by `style-src`, while `style=""` attributes, `setAttribute('style')` and `cssText` are [57]. So the component is CSP-clean. **The WP templates' inline `style="…"` attributes must not be copied into Django templates** if `style-src` is ever restricted.

**Defend it:** "Django renders the page and a template tag reads Vite's manifest to emit one stylesheet and one module script, so CSP stays `script-src 'self'`. I didn't take django-vite: it doesn't declare our Django or Python, and its dev helper needs an inline script. In dev, the component runs on Vite's own page and proxies `/api` to Django."

---

## 10. Testing

**Stack (accepted, ADR 0011):** Vitest 5 + jsdom + Testing Library + `axe-core` called directly. On 2026-11-09 the cooldown resolves Vitest **5.1.0** (cleared 16:12 UTC today), jsdom 30.1.3 (31.0.0 still waiting), RTL 16.3.3 and user-event 14.6.8 [14][15].

**Mocking fetch.**

| | Plain stub (`vi.stubGlobal('fetch', vi.fn(...))`) | MSW 3.0.3 |
|---|---|---|
| Packages | 0 | **+45** to the dev tree [15] |
| Supply chain | — | One maintainer [14]. The tree includes `debug`, `ansi-regex`, `ansi-styles`, `strip-ansi` and `wrap-ansi`, all of which had **malicious versions published on 2025-09-08** [67]. They come in via its CLI dependencies (`yargs`, `@inquirer/*`) [15] |
| Fidelity | Returns `new Response(JSON.stringify(fixture), {status})` (Node 24 globals) | Intercepts at the network layer |
| Race tests | Easy: return deferred promises and resolve them out of order | Possible, more ceremony |
| Why it might lose | Tests know the fetch call shape | Weight and dependency history |

Use `vi.stubGlobal` with `unstubGlobals: true` (or `vi.unstubAllGlobals()` in `afterEach`) [62]. Better still, keep `fetchBrands(query, signal)` in `api.ts` and assert on the URL it requested. That tests the param mapping too.

**What to test.**
- **Contract (ADR 0010):** `BrandPage.safeParse(contracts/brand-list.example.json)` succeeds.
- **Pure URL functions:** garbage `page`, unknown `industry`, duplicate params, default omission, canonical order, unknown params preserved.
- **States:** loading → success; empty; HTTP 500 → error + Retry → success; Zod mismatch → error; timeout; 404 invalid page → URL reset to page 1.
- **Races:** request A, then B; resolve B, then A. Only B renders. Unmount mid-flight aborts (assert `signal.aborted`).
- **URL:** toggling a checkbox pushes a URL with the page reset. Set the start URL with `history.replaceState` before render. For Back, dispatch `new PopStateEvent('popstate')` after changing the URL (see "Not verified" on `history.back()` in jsdom).
- **axe in each state** (loading, success, empty, error). Disable `color-contrast`, which axe's README says doesn't work in JSDOM [65]. Disable `target-size`, since jsdom returns zeros for layout [66]. Disable `region` for a component rendered alone. Check contrast and target size in a real browser.
- **Keyboard (user-event):** call `userEvent.setup()` before render [63]. Use `user.tab()` for order [63], `user.keyboard('[Space]')` to toggle, `user.selectOptions` for sort, and Enter on a page link. Assert focus lands on the results heading after a page change or Retry.
- Query with `getByRole`/`getByLabelText`, never class names [64].

**Manual keyboard pass (checklist).**
1. Tab reaches every control in visual order: checkboxes → Clear → sort → card links → pagination (2.4.3).
2. Space toggles checkboxes; arrow keys or Space operate the select; Enter follows links.
3. Focus is always visible (2.4.7) and never fully under a sticky header (2.4.11) [38].
4. No traps. Shift+Tab walks back cleanly.
5. Focus never jumps on filter or sort change. It lands on the results heading after a page change, Retry or Clear.
6. The status region is announced (NVDA + Firefox, VoiceOver + Safari) [46].
7. At 400% zoom / 320 px width there's no horizontal scroll (1.4.10) [33].
8. With `prefers-reduced-motion: reduce`, there's no hover lift and no shimmer.
9. Browser back and forward restore filters and results. A copied URL reproduces the view.

**Defend it:** "Tests drive the component through roles and the keyboard like a user would. Fetch is a plain stub, so I can resolve responses out of order and prove the race handling. I skipped MSW: it would add 45 packages, five of which were hijacked in September 2025."

---

## 11. Frontend supply chain (pnpm 12) and dependency budget

**Version.** pnpm is on **12** (`latest` 12.18.0, 2026-11-05). This machine runs 12.16.1 [14]. pnpm itself had ~28 advisories in 2026 (path traversal, integrity bypasses, a lifecycle-script bypass), all fixed in 10.34.5, 11.11.0 and the 12.0 alphas [71]. Pin the version in `package.json` (`"packageManager": "pnpm@12.16.1"`, or 12.17.0; 12.18.0 clears the cooldown on 2026-11-12). `trustPolicy` also checks that pinned version [68].

**Settings, verified against pnpm.io for the current docs [68][69][70]:**

```yaml
# frontend/pnpm-workspace.yaml
minimumReleaseAge: 10080              # ADR 0012. Built-in default is 1440 (non-strict)
minimumReleaseAgeStrict: true         # default once the age is set explicitly; stated for readers
minimumReleaseAgeIgnoreMissingTime: false   # fail if a registry can't date a release
trustPolicy: no-downgrade             # default is off
blockExoticSubdeps: true              # default true; no git/tarball sources for transitive deps
strictDepBuilds: true                 # default true; unreviewed build scripts fail the install
allowBuilds:                          # replaces onlyBuiltDependencies (removed in v11)
  '@parcel/watcher': false            # optional dep of sass; prebuilt per-platform packages cover it
  fsevents: false                     # macOS-only optional native dep
```

- **Strictness.** With `minimumReleaseAge` set explicitly, `minimumReleaseAgeStrict` defaults to true: pnpm **fails** if no version in range is old enough. The non-strict mode (the built-in default) instead installs a version that *doesn't* meet the age [68].
- **trustPolicy.** `no-downgrade` fails if a release has weaker trust evidence (trusted publisher > provenance > none) than an earlier one [68]. The planned set resolves cleanly under it [15]. It would **not** have caught the TanStack attack, which used the legitimate trusted publisher [20]. The cooldown would have.
- **Lockfile.** `trustLockfile` defaults to false, so `pnpm install` re-checks age and trust for every lockfile entry [68]. Keep it that way, because outside contributors could edit the lockfile. Use `pnpm install --frozen-lockfile` in the Docker build stage.
- **Install scripts.** Only 2 packages in the planned tree have them: `@parcel/watcher` and `fsevents` [14][15]. Both stay unapproved.

**Dependency budget (packages, resolved 2026-11-09) [15].**

| Set | Runtime | Notes |
|---|---|---|
| **Recommended** (react, react-dom, zod) | **4** (`react`, `react-dom`, `scheduler`, `zod`) | Dev + runtime tree: 103 packages, excluding per-platform binaries |
| + TanStack Query | 6 | 68 releases in 2026 |
| + SWR | 7 | No fetcher abort |
| + nuqs | 6 | 1 maintainer |
| + React Router | 7 | 20 advisories in 2025–26 |
| + MSW (dev) | — | +45 dev packages |

**Defend it:** "Four runtime packages. A one-week cooldown that fails rather than falls back, a no-downgrade trust policy, no exotic transitive sources, and no install scripts approved. Every addition was costed in packages, maintainers and advisories, and none earned its place."

---

## 12. Proposed component breakdown

```
src/brand-list/
  main.tsx            mount: read #brand-list data-api-url + json_script industries (Zod), createRoot, <StrictMode>
  BrandList.tsx       composition only; wires hooks to children
  urlQuery.ts         pure: parseQuery(search, allowed) / toSearch(query) / toApiParams(query)
  useUrlQuery.ts      useSyncExternalStore over location.search; navigate(query, 'push'|'replace')
  api.ts              fetchBrands(apiUrl, query, signal) → typed result; HTTP + JSON + Zod
  schema.ts           Zod: Brand, BrandPage, Industry; z.infer types
  useBrands.ts        effect keyed on canonical query + reloadKey; AbortController; state union
  components/
    BrandFilters      <search><form> → IndustryFilter (fieldset/legend/checkboxes), SortSelect, ClearFilters
    ResultsStatus     always-mounted role="status"; text derived from query + state
    ResultsRegion     <h2 tabindex=-1> focus target; switches on state:
                        SkeletonGrid (aria-hidden) | BrandGrid → BrandCard (RatingText, badge, snippet)
                        | EmptyState (Clear filters) | ErrorState (role="alert", Retry)
    Pagination        <nav aria-label="Pagination">, links, aria-current="page"
```

**What state lives where.**
- **URL** (source of truth): `industry[]`, `sort`, `page`.
- **`useBrands`** (local): the last result, status, error, `reloadKey`.
- **Static props**: `apiUrl` and `industries` from Django.
- **Refs**: the focus target, and a "user-initiated" flag that gates announcements.
- **No context, no global store.**

---

## 13. What the component needs from Pillar 2

These are the API agent's decisions, listed so the two sides agree:
- **Param names** the page URL can mirror one-to-one. The Pillar 2 note proposes `industry`, `ordering` and `page` (plus a capped `page_size`).
- **Multi-value industry** (`?industry=a&industry=b`, OR semantics) if the checkbox group is chosen. The Pillar 2 note proposes exactly this, and a **400** for an unknown slug. The component allow-lists slugs before calling, so a 400 means a stale industry list: show the error state with Retry, after replacing the URL without the unknown slug.
- **A sort allow-list and default**, with an `id` tie-breaker (AGENTS.md).
- **A page-size cap.** The Zod schema mirrors it with `.max()`.
- **Out-of-range page behaviour.** DRF's default is 404 `"Invalid page."` [60]; the component resets to page 1.
- **The top review snippet as plain text**, tags stripped server-side, so the UI never needs `dangerouslySetInnerHTML`.
- **Industry list source** for the filter: `json_script` (recommended), a facet in the response, or another endpoint.

---

## Open decisions for the user

1. **How does `<BrandList />` consume SCSS?**
   - A: global BEM partials in `frontend/scss/`.
   - B: co-located CSS Modules.
   - C: hybrid.
   - *Recommendation: A* (§8). Revisit with C once more React components appear.
2. **Data fetching: custom hook or TanStack Query?** *Recommendation: custom hook* (§2). If a library is ever needed, prefer TanStack over SWR, because SWR doesn't cancel.
3. **URL state: hand-rolled `useSyncExternalStore` store, nuqs, or React Router?** *Recommendation: hand-rolled* (§4).
4. **Industry filter: multi-select checkboxes or a single `<select>`?** It depends on Pillar 2 supporting multi-value params. *Recommendation: checkboxes in a fieldset* (5 industries) (§6).
5. **History granularity:** push every discrete change, or coalesce consecutive sort changes with replace? *Recommendation: push filters and pages; coalesce sort* (§4).
6. **Pagination: links or buttons?** *Recommendation: links with intercepted clicks* (§6).
7. **Test fetch mocking: plain stub or MSW?** *Recommendation: plain stub* (§10).
8. **Dev workflow:** Vite's own dev page with an `/api` proxy, or a Django page loading the Vite dev server? *Recommendation: Vite page + proxy*, with a `build --watch` check through Django (§9).
9. **Django mounting: a tiny manifest template tag or django-vite?** *Recommendation: the tag* (§9).
10. **pnpm hardening beyond ADR 0012:** add `trustPolicy: no-downgrade`, the explicit strict and missing-time flags, `allowBuilds` denials, and a pinned `packageManager`? *Recommendation: yes* (§11). This touches ADR 0012's domain, so record it as a new ADR or an addendum, not an edit.

---

## Conflicts with accepted decisions

**None found against the ADRs.** Three points touch ADR 0005 without contradicting it:
- Dev mode with the Vite dev server inside a Django page needs an inline preamble, which is incompatible with "no nonces". The recommended dev setup avoids that (§9).
- A full policy beyond `script-src` needs `assetsInlineLimit: 0` or `data:` in `img-src`/`font-src` [48].
- Django templates must not inherit WP's inline `style=""` attributes [57].

**Corrections to earlier research notes (not ADRs):**
- `best-practices-2026.md` §6 recommends "`aria-busy` on the list while loading". Drop it: AT may ignore busy content [39], and NVDA and VoiceOver mishandle it with live regions [45]. Use an always-mounted status region (§6).
- `best-practices-2026.md` §6 lists `jest-axe`/`vitest-axe`. ADR 0011 already replaced them with `axe-core` called directly. The note predates the ADR.
- `best-practices-2026.md` §3 says "pnpm silently falls back to an older version". On pnpm 12, an explicitly set `minimumReleaseAge` is strict by default and **fails**. Non-strict mode falls back to a version that is *too new*, not older [68].
- `stack-validation.md` §3.6 cites "jsdom can't check colour contrast" as *(secondary)*. axe-core's own README now confirms it [65].
- `stack-validation.md`'s matrix (Vitest 5.0.5, plugin-react 6.1.2) has aged by a day: Vitest 5.1.0 and plugin-react 6.2.1 cleared the cooldown on 2026-11-09 [14][15]. The research brief's "pnpm 10/11" should read pnpm 12 [14].

---

## Not verified

- Whether arrow keys on a closed `<select>` fire `change` per keypress on Windows browsers (the reason for coalescing sort pushes). Not tested here.
- Whether jsdom's `history.back()` fires `popstate` in Vitest. The plan dispatches `PopStateEvent` by hand instead.
- Mixing jsdom's `AbortSignal` with Node's real `fetch` (it only matters if real fetch or MSW is used). Not tested.
- How axe's `target-size` rule behaves under jsdom. "Disable it" is inferred from jsdom returning zero layout [66].
- Whether Safari/VoiceOver still drop list semantics for `<ul>` with `list-style: none` in 2026 (the `role="list"` workaround). Not checked.
- Whether `postcss-modules` scopes or leaves `@layer` names inside CSS Modules files.
- SWR cancellation: no merged change was found after PR #2275 closed [25], but the search wasn't exhaustive.
- The TanStack query packages being clean rests on the GHSA package list [20]. TanStack/query's own CI wasn't audited.
- Whitenoise's manifest storage hashing on top of Vite's already-hashed filenames. It looks harmless for one entry chunk, but wasn't run.
- `json_script` data blocks being outside `script-src` enforcement: consistent with ADR 0005's premise, not tested.
- webstatus.dev lists Chrome 143 for `@scope`, which looks odd. Only its Baseline date (2026-03-24) is used here.
- Which of React Router's 20 advisories affect declarative/library mode beyond the two checked [27].
- Nothing was built or run. Dependency counts come from metadata-only lockfile resolution [15].

---

## Sources

Accessed 2026-11-09 unless noted.

1. React releases v19.3.1, v19.2.9, v19.1.10, v19.0.9 (2026-10-14), v19.3.0 (2026-09-09): <https://github.com/react/react/releases> (the repo moved from facebook/react)
2. react.dev Versions (latest 19.3): <https://react.dev/versions>
3. react.dev Versioning policy: <https://react.dev/community/versioning-policy>
4. React 19.3 release post (2026-09-09): <https://react.dev/blog/2026/09/09/react-19-3>
5. OSV advisories for `react-server-dom-webpack` (CVE-2025-55182/55183/55184/67779, CVE-2026-23864/23869/23870/44907): <https://osv.dev/list?ecosystem=npm&q=react-server-dom-webpack> · <https://osv.dev/vulnerability/GHSA-fv66-9v8q-g76r> · <https://osv.dev/vulnerability/GHSA-wx67-qw84-cm4g>
6. OSV advisories for `react` / `react-dom` (latest CVE-2018-6341): <https://osv.dev/list?ecosystem=npm&q=react-dom>
7. react.dev `useSyncExternalStore`: <https://react.dev/reference/react/useSyncExternalStore>
8. react.dev `use`: <https://react.dev/reference/react/use>
9. react.dev You Might Not Need an Effect, "Fetching data": <https://react.dev/learn/you-might-not-need-an-effect#fetching-data>
10. react.dev Synchronizing with Effects, "Fetching data" and the alternatives DeepDive: <https://react.dev/learn/synchronizing-with-effects#fetching-data>
11. react.dev `useTransition` (caveats, out-of-order troubleshooting): <https://react.dev/reference/react/useTransition>
12. react.dev `useDeferredValue`: <https://react.dev/reference/react/useDeferredValue>
13. React DOM `CSSPropertyOperations.js` at v19.3.1: <https://github.com/react/react/blob/v19.3.1/packages/react-dom-bindings/src/client/CSSPropertyOperations.js>
14. npm registry metadata via read-only `npm view` (versions, publish times, dependencies, maintainers, scripts, provenance): <https://www.npmjs.com/>
15. This research: metadata-only `pnpm install --lockfile-only --ignore-scripts` in a scratch directory (pnpm 12.16.1; `minimumReleaseAge: 10080`; `trustPolicy: no-downgrade`), 2026-11-09
16. Zod v4.6.7 docs, Formatting errors: <https://zod.dev/error-formatting> (source: <https://github.com/colinhacks/zod/blob/v4.6.7/packages/docs/content/error-formatting.mdx>)
17. Zod v4.6.7 docs, API (objects strip unknown keys, `.catch()`, `z.coerce`): <https://zod.dev/api>
18. Zod Mini: <https://zod.dev/packages/mini>
19. GHSA-mrhx-c7xc-m3w5 / CVE-2023-54404 (fixed in 4.6.6; published 2026-10-01): <https://osv.dev/vulnerability/GHSA-mrhx-c7xc-m3w5>
20. GHSA-g7cv-rxg3-hmpx, malware in 42 `@tanstack/*` packages (2026-05-11): <https://github.com/advisories/GHSA-g7cv-rxg3-hmpx>
21. OSV MAL-2026-3465 (`@tanstack/react-router`): <https://osv.dev/vulnerability/MAL-2026-3465>
22. TanStack Query, Query Cancellation: <https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation>
23. TanStack Query, Important Defaults: <https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults>
24. SWR API options: <https://swr.vercel.app/docs/api>
25. vercel/swr PR #2275 (fetcher `signal`, closed unmerged 2025-01-24): <https://github.com/vercel/swr/pull/2275>
26. nuqs adapters: <https://nuqs.dev/docs/adapters>
27. OSV advisories for `react-router` (20, Apr 2025–Jul 2026); GHSA-9jcx-v3wj-wh4m, GHSA-wrjc-x8rr-h8h6: <https://osv.dev/list?ecosystem=npm&q=react-router>
28. MDN, Window `popstate` event: <https://developer.mozilla.org/en-US/docs/Web/API/Window/popstate_event>
29. MDN, `History.pushState()`: <https://developer.mozilla.org/en-US/docs/Web/API/History/pushState>
30. Web features explorer, Navigation API: <https://web-platform-dx.github.io/web-features-explorer/features/navigation> · MDN: <https://developer.mozilla.org/en-US/docs/Web/API/Navigation_API>
31. webstatus.dev Baseline data (API `api.webstatus.dev/v1/features/<id>`), queried 2026-11-09: container-queries, container-style-queries, logical-properties, prefers-reduced-motion, focus-visible, abortsignal-any, abortsignal-timeout, abortable-fetch, modulepreload, view-transitions, trusted-types, search, scope, navigation, arianotify: <https://webstatus.dev/>
32. MDN, `AbortSignal.timeout()`: <https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static>
33. W3C WCAG 2.2 Recommendation (SC 1.4.3, 1.4.10, 1.4.11, 2.4.7): <https://www.w3.org/TR/WCAG22/>
34. W3C, What's New in WCAG 2.2: <https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/>
35. Understanding SC 2.5.8 Target Size (Minimum): <https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html>
36. Understanding SC 4.1.3 Status Messages: <https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html>
37. Understanding SC 3.2.2 On Input: <https://www.w3.org/WAI/WCAG22/Understanding/on-input.html>
38. Understanding SC 2.4.11 Focus Not Obscured (Minimum): <https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html>
39. WAI-ARIA 1.2 (`aria-busy`, `aria-live`, `status`, `aria-current`, `generic`): <https://www.w3.org/TR/wai-aria-1.2/>
40. ARIA APG, Listbox pattern: <https://www.w3.org/WAI/ARIA/apg/patterns/listbox/>
41. ARIA APG, Checkbox pattern: <https://www.w3.org/WAI/ARIA/apg/patterns/checkbox/>
42. ARIA APG, Read Me First: <https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/>
43. MDN, `<select>` (`multiple`): <https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/select>
44. MDN, ARIA live regions guide: <https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Guides/Live_regions>
45. Mozilla Bugzilla 1682063, "aria-busy is not working" (NVDA/VoiceOver comments): <https://bugzilla.mozilla.org/show_bug.cgi?id=1682063>
46. Adrian Roselli, "Live Region Support" (2026-01-14) *(secondary)*: <https://adrianroselli.com/2026/01/live-region-support.html>
47. WHATWG HTML, the `search` element and label activation: <https://html.spec.whatwg.org/multipage/grouping-content.html#the-search-element> · <https://html.spec.whatwg.org/multipage/forms.html#the-label-element>
48. Vite v8.3.5, Features guide (CSS, CSS Modules, pre-processors, Lightning CSS, CSP): <https://github.com/vitejs/vite/blob/v8.3.5/docs/guide/features.md>
49. Vite v8.3.5, Shared options (`base`, `input`, `css.modules`, `css.preprocessorOptions`, `additionalData`): <https://github.com/vitejs/vite/blob/v8.3.5/docs/config/shared-options.md>
50. Vite v8.3.5, Build options (`manifest`, `assetsInlineLimit`, `cssCodeSplit`, `modulePreload`, `cssMinify`): <https://github.com/vitejs/vite/blob/v8.3.5/docs/config/build-options.md>
51. Vite v8.3.5, Backend integration: <https://github.com/vitejs/vite/blob/v8.3.5/docs/guide/backend-integration.md>
52. Vite v8.3.5, Server options (`proxy`, `host`, `cors`): <https://github.com/vitejs/vite/blob/v8.3.5/docs/config/server-options.md>
53. Vite v7.0.0 migration guide (Sass legacy API removed): <https://github.com/vitejs/vite/blob/v7.0.0/docs/guide/migration.md>
54. OSV advisories for `vite` (2025–26 dev-server issues): <https://osv.dev/list?ecosystem=npm&q=vite>
55. Sass `@use`: <https://sass-lang.com/documentation/at-rules/use/>
56. Sass JS API Options (`loadPaths`; docs at Dart Sass 1.108.1): <https://sass-lang.com/documentation/js-api/interfaces/options/>
57. MDN, CSP `style-src` (violation cases; CSSOM property writes not blocked): <https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/style-src>
58. django-vite 3.2.0 on PyPI (classifiers, upload dates) and repo (`tox.ini`, `test.yml`, README): <https://pypi.org/project/django-vite/> · <https://github.com/MrBin99/django-vite>
59. WhiteNoise 6.12.0, Django guide: <https://whitenoise.readthedocs.io/en/stable/django.html>
60. DRF 3.18.3 `pagination.py` (`invalid_page_message`, `NotFound`): <https://github.com/encode/django-rest-framework/blob/3.18.3/rest_framework/pagination.py>
61. Vitest v5.0.5, `css` config: <https://github.com/vitest-dev/vitest/blob/v5.0.5/docs/config/css.md>
62. Vitest, `vi.stubGlobal` / `vi.unstubAllGlobals` / `unstubGlobals`: <https://vitest.dev/api/vi#vi-stubglobal> · <https://vitest.dev/config/unstubglobals>
63. Testing Library, user-event intro and convenience APIs: <https://testing-library.com/docs/user-event/intro> · <https://testing-library.com/docs/user-event/convenience>
64. Testing Library, query priority: <https://testing-library.com/docs/queries/about/#priority>
65. axe-core 4.14.0 README (JSDOM support) and rule descriptions (`aria-prohibited-attr`, `target-size`): <https://github.com/dequelabs/axe-core/blob/v4.14.0/README.md> · <https://github.com/dequelabs/axe-core/blob/v4.14.0/doc/rule-descriptions.md>
66. jsdom README (no navigation, zero layout) and `AbortSignal-impl.js` (`any`, `timeout`), main branch: <https://github.com/jsdom/jsdom>
67. OSV malicious-package entries of 2025-09-08: MAL-2025-46974 (`debug` 4.4.2), MAL-2025-46966 (`ansi-regex` 6.2.1), MAL-2025-46967 (`ansi-styles` 6.2.2), MAL-2025-46980 (`strip-ansi` 7.1.1), MAL-2025-46983 (`wrap-ansi` 9.0.1): <https://osv.dev/vulnerability/MAL-2025-46974>
68. pnpm settings, Dependency resolution (`minimumReleaseAge*`, `trustPolicy*`, `trustLockfile`, `blockExoticSubdeps`), current docs (pnpm 12): <https://pnpm.io/settings/dependency-resolution> (source: <https://github.com/pnpm/pnpm.io/blob/main/docs/settings/dependency-resolution.md>)
69. pnpm settings, Build (`allowBuilds`, `strictDepBuilds`; `onlyBuiltDependencies` removed in v11): <https://pnpm.io/settings/build>
70. pnpm, Supply chain security: <https://pnpm.io/supply-chain-security>
71. OSV advisories for `pnpm` (2026), e.g. GHSA-5wx6-mg75-v57r, GHSA-vq4v-j7r6-jq4m: <https://osv.dev/list?ecosystem=npm&q=pnpm>
72. OSV advisories for `vitest` (CVE-2025-24964, CVE-2026-47429, CVE-2026-84373): <https://osv.dev/list?ecosystem=npm&q=vitest>
