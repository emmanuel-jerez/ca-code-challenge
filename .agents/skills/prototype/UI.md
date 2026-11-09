# UI Prototype

Generate **several radically different UI variations** on a single route, switchable from a floating bottom bar. Flip between variants in the browser, pick one (or steal bits from each), then throw the rest away.

If the question is about logic/state rather than what something looks like, this is the wrong branch. Use [LOGIC.md](LOGIC.md).

## When this is the right shape

- "What should this page look like?"
- "I want to see a few options for this dashboard before committing."
- "Try a different layout for the settings screen."
- Any time the user would otherwise spend a day picking between three vague mockups in their head.

## Two sub-shapes: strongly prefer sub-shape A

A UI prototype is much easier to judge when it's **butting up against the rest of the app**: real header, real sidebar, real data, real density. A throwaway route on its own is a vacuum: every variant looks fine in isolation. Default to sub-shape A whenever there's a plausible existing page to host the variants. Only reach for sub-shape B if the prototype genuinely has no nearby home.

### Sub-shape A: adjustment to an existing page (preferred)

The route already exists. Variants are rendered **on the same route**, gated by a `?variant=` URL search param. The existing data fetching, params, and auth all stay. Only the rendering swaps. This is the default; pick it unless there's a specific reason not to.

If the prototype is for something that doesn't yet have a page but *would naturally live inside one* (a new section of the dashboard, a new card on the settings screen, a new step in an existing flow), it's still sub-shape A. Mount the variants inside the host page.

### Sub-shape B: a new page (last resort)

Only use this when the thing being prototyped genuinely has no existing page to live inside (e.g. an entirely new top-level surface, or a flow that can't be embedded anywhere sensible).

Create a **throwaway route** following whatever routing convention the project already uses. Don't invent a new top-level structure. Name it so it's obviously a prototype (e.g. include the word `prototype` in the path or filename). Same `?variant=` pattern.

Before committing to sub-shape B, sanity-check: is there really no existing page this could be embedded in? An empty route hides design problems that a populated one would expose.

In both sub-shapes the floating bottom bar is identical.

## Process

### 1. State the question and pick N

Default to **3 variants**. More than 5 stops being radically different and starts being noise, so cap there.

Write down the plan in one line, in the prototype's location or a top-of-file comment:

> "Three variants of the settings page, switchable via `?variant=`, on the existing `/settings` route."

### 2. Generate radically different variants

Draft each variant. Hold each one to:

- The page's purpose and the data it has access to.
- The project's styling system: the SCSS tokens and partials under `frontend/scss/` for both Django templates and the React component.
- A clear name per variant: a template such as `brands/_detail_variant_a.html` for a Django page, or an exported component such as `VariantA` in React.

Variants must be **structurally different**: different layout, different information hierarchy, different primary affordance, not just different colours. Three slightly-tweaked card grids isn't a UI prototype, it's wallpaper. If two drafts come out too similar, redo one with explicit "do not use a card grid" guidance.

### 3. Wire them together

Create a single switcher on the route.

For a Django-rendered page, choose the template in the view and keep the
existing query and context:

```python
# PROTOTYPE: remove the losing variants and this switch before merging to main
VARIANTS = {"A": "brands/_detail_variant_a.html", "B": "...", "C": "..."}

def brand_detail(request, slug):
    brand = get_object_or_404(Brand.objects.with_review_stats(), slug=slug)
    key = request.GET.get("variant", "A") if settings.DEBUG else "A"
    context = {"brand": brand, "variant_template": VARIANTS.get(key, VARIANTS["A"]),
               "variant_keys": list(VARIANTS), "variant": key}
    return render(request, "brands/detail.html", context)
```

`detail.html` then does `{% include variant_template %}` and includes the
switcher partial. Only keys in `VARIANTS` are ever rendered.

For the React component:

```tsx
const variant = new URLSearchParams(window.location.search).get('variant') ?? 'A';
return (
  <>
    {variant === 'A' && <VariantA {...data} />}
    {variant === 'B' && <VariantB {...data} />}
    {variant === 'C' && <VariantC {...data} />}
    <PrototypeSwitcher variants={['A','B','C']} current={variant} />
  </>
);
```

For sub-shape A (existing page): keep all the existing data fetching above the switcher; only the rendered subtree changes per variant.

For sub-shape B (new page): add a throwaway `path("prototype/<name>/", ...)` entry, only in development URL patterns, that mounts the same switcher.

### 4. Build the floating switcher

A small fixed-position bar at the bottom-centre of the screen with three pieces:

- **Left arrow**: cycles to the previous variant (wraps around).
- **Variant label**: shows the current variant key and, if the variant exports a name, that name too. e.g. `B (Sidebar layout)`.
- **Right arrow**: cycles forward (wraps around).

Behaviour:

- Clicking an arrow updates the URL search param so the variant is shareable and reload-stable. On a Django page the arrows are plain links to `?variant=<key>`, kept as real `<a>` elements. In React, update the param with `history.replaceState` (or the router, if the frontend adds one).
- Keyboard: `←` and `→` arrow keys also cycle. Don't intercept arrow keys when an `<input>`, `<textarea>`, or `[contenteditable]` is focused.
- Visually distinct from the page (e.g. high-contrast pill, subtle shadow) so it's obviously not part of the design being evaluated.
- Hidden in production: in Django, render the bar and honor `?variant=` only when `settings.DEBUG` is true; in the Vite-built React code, gate on `import.meta.env.DEV`. A stray prototype merge then can't ship the bar to users.

Put the switcher in one shared template partial (and one shared React component, if the frontend needs it) so both sub-shapes reuse it. Locate it wherever shared templates or UI live in the project.

### 5. Pick the winner

Report the URL (and the `?variant=` keys). Then flip through the variants yourself against the page's purpose and pick the winner. The strongest answer is often a combination, like **"the header from B with the sidebar from C"**; say which parts come from where, and why.

### 6. Capture the answer and clean up

Once a variant has won, capture the answer (which variant and why), then capture the prototype the way the [SKILL](SKILL.md) describes. Fold the winner into the real code and move the rest onto the throwaway branch, not into main:

- **Sub-shape A**: fold the winner into the existing page; drop the losing variants and the switcher from main.
- **Sub-shape B**: promote the winning variant to a real route; drop the throwaway route and the switcher from main.

The full set of variants is the primary source, so it lands on the throwaway branch, not the bin, since variant components and the switcher left in the main branch rot fast and confuse the next reader.

## Anti-patterns

- **Variants that differ only in colour or copy.** That's a tweak, not a prototype. Real variants disagree about structure.
- **Sharing too much code between variants.** A shared `<Header>` is fine; a shared `<Layout>` defeats the point. Each variant should be free to throw out the layout.
- **Wiring variants to real mutations.** Read-only prototypes are fine. If a variant needs to mutate, point it at a stub: the question is "what should this look like", not "does the backend work".
- **Promoting the prototype directly to production.** The variant code was written under prototype constraints (no tests, minimal error handling). Rewrite it properly when you fold it in.
