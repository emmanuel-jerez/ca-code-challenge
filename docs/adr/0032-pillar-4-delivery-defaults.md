# 0032. Pillar 4: how theme.css and `<BrandList />` reach Django pages

- Status: Accepted
- Date: 2026-11-09

## Context
ADR 0031 decided that the Sass CLI builds `theme.css` and Vite builds the
component, both in a Node stage of the main app's Dockerfile, with whitenoise
serving the result, and that `<BrandList />` mounts on a new `/brand/` page.
This record lists the implementation choices made while building that. None
was put to the user; each is flagged for review in the second Pillar 4 pull
request. Facts that shaped them:

- whitenoise 6.12.0 (2026-02-27) declares Django 5.2 and Python 3.14, and
  ADR 0008 had already accepted it (`>=6.12.0,<7`).
- Node 24.22.1 (2026-10-20) is the latest Node security release. Its
  `trixie-slim` image was built on 2026-10-28. 24.22.2 (2026-10-27) fixed no
  vulnerabilities, and its image was rebuilt on 2026-11-05, inside the
  seven-day cooldown that AGENTS.md applies to packages.
- Docker Compose builds the main app's image for two services, `main-app`
  and `wp-import`.
- django-vite doesn't declare Django 5.2 or Python 3.14
  (`docs/research/pillar-3-brandlist-component.md` §9).

## Options considered
1. **Getting pnpm into the Node stage.** The `curl | sh` installer was
   rejected: it runs a remote script. Installing it with npm was rejected:
   the project bypasses npm (pnpm-only). Corepack, bundled with Node 24, was
   chosen: it fetches the version `package.json` pins and checks its npm
   signature.
2. **Getting the frontend source into the build.** Moving the build context
   to the repo root was rejected: every `COPY` in the Python stages would
   change, and the context would carry the whole repository. A named
   context (`additional_contexts: frontend-src: ./frontend`) was chosen, and
   the stage copies only the files the build reads, never the host's
   `node_modules`.
3. **Which build steps run in the image.** Running `pnpm build`, which
   type-checks first, was rejected: the type check also reads `../contracts`,
   which isn't in the context, and it belongs with the tests. The stage runs
   `pnpm scss` and `vite build`.
4. **Reading the Vite manifest.** Serving it as a static file was rejected:
   it would publish the build's file list. The tag reads
   `frontend/dist/.vite/manifest.json` from disk; `collectstatic` skips the
   dot directory.

## Decision
- **Dockerfile:** a `node:24.22.1-trixie-slim` stage, pinned by digest, runs
  `pnpm install --frozen-lockfile`, `pnpm scss` and `vite build`. The Python
  build stage copies `dist-css/` and `dist/` to `/app/frontend` and runs
  `collectstatic` with a throwaway secret key. The runtime image has no
  Node.
- **Compose:** one `build` definition, shared by `main-app` and `wp-import`
  through a YAML anchor. If a service built the image without the named
  context, `COPY --from=frontend-src` would treat `frontend-src` as an image
  name and pull it from Docker Hub.
- **Settings:**
  - `django.contrib.staticfiles` and `WhiteNoiseMiddleware`, placed right
    after `SecurityMiddleware` as whitenoise documents;
  - `CompressedManifestStaticFilesStorage` with whitenoise's defaults, so
    unhashed originals stay and a Vite chunk that imports another by its
    Vite name still resolves;
  - `DJANGO_FRONTEND_DIR` points at the build: `../frontend` in a checkout,
    `/app/frontend` in the image;
  - no Brotli: it needs the optional `Brotli` package, so the files are
    gzipped only.
- **Template tag `{% vite_entry %}`,** about 40 lines:
  - emits the entry's stylesheets, then its module script, through
    `static()`;
  - reads the manifest once per process;
  - raises `ImproperlyConfigured`, naming `pnpm build`, when the manifest or
    entry is missing.

  It emits no `modulepreload` links: the build has one chunk.
- **The `/brand/` page:**
  - a compact hero ("Brands"), as WordPress's archive has;
  - the mount point with `data-api-url`;
  - all industries sorted by name, passed through `json_script`;
  - a `<noscript>` note that the list needs JavaScript.

  The page runs one query. The nav gains a "Brands" link, marked
  `aria-current` on that page, and the home page's "Featured Brands" gains
  WordPress's "All brands →" link.
- **Zod runs `jitless`.** A browser check of `/brand/` found five
  report-only CSP violations per page view: Zod 4 compiles object parsers
  with `new Function`, after probing with `Function("")`. Under the enforced
  policy it would catch the error and fall back, so nothing would break, but
  every view would log or report violations and bury real ones.
  `z.config({ jitless: true })` runs in `schema.ts` before any schema is
  built. Parsing a dozen brands without the JIT costs nothing noticeable.
  The alternative, allowing `'unsafe-eval'`, was rejected: it would let any
  injected string run as script.
- **Tests** use plain `StaticFilesStorage` and no `STATIC_ROOT`, so they
  need neither `collectstatic` nor a frontend build. The page tests write
  their own manifest.

## Consequences
- `docker compose up` builds and serves the stylesheet and the component.
  There's no new setup step.
- The image build now needs network access to the npm registry, for pnpm
  and the frontend packages, and takes a few seconds longer.
- Every page links `theme.css`. With the manifest storage, a page fails if
  `theme.css` wasn't collected, so running Django outside Docker needs
  `pnpm scss` and `pnpm build` first.
- Without JavaScript, `/brand/` shows only the note. Brand pages still work.
- `collectstatic` also copies DRF's bundled static files, which the
  JSON-only API never uses.
- Industries with no published brands still appear in the filter, and
  choosing one shows the empty state.

## Revisit when
- Vite splits the build into more chunks (add `modulepreload` links).
- Server-rendering the first page of brands becomes worth it for users
  without JavaScript, or for search engines.
- Brotli is wanted (add `Brotli` as a dependency, after the usual vetting).
- Node 24.22.1 has a security successor past the cooldown.

## Sources
ADRs 0008, 0029, 0031; whitenoise 6.12.0 docs (Django setup and settings,
via Context7 `/websites/whitenoise_readthedocs_io`); PyPI metadata for
whitenoise; nodejs.org `dist/index.json`; Docker Hub image metadata for
`node:24.22.x-trixie-slim`.
