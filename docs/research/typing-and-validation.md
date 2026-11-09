# Typing and Validation: Python/Django Equivalents of Zod, Effect and "Fully Typed"

Research notes, 2026-11-09. Scope: the main Django app, the auth service, the shared library and the React `<BrandList />`. The choice between DRF and Django Ninja, the JWT library, CSP and the HTML sanitizer are covered in `docs/research/stack-decisions.md`. Where an answer here depends on DRF vs Ninja, both answers are given.

> **Cooldown.** Today is 2026-11-09, so with uv `exclude-newer = "7 days"` and pnpm's release-age delay, a version must have been uploaded **before 2026-11-02**. Every "pin" below meets that. Release dates come from the PyPI JSON API (`pypi.org/pypi/<name>/json`, earliest file upload) and `npm view <pkg> time`. Write ranges in `pyproject.toml`/`package.json` and let the lockfile resolve to the version listed here. Claims marked *(secondary)* come from non-primary sources.

---

## 1. The Zod equivalent: one schema for runtime validation and static types

| Package | Cooldown-safe version (date) | Py3.14 / Django 5.2 | Maintenance | Pros | Cons |
|---|---|---|---|---|---|
| **Pydantic v2** (`pydantic`) | 2.14.2 (2026-10-29); pins `pydantic-core==2.50.2` (2026-10-29) | 3.14 classifier. Python 3.14 support since 2.12 ([HISTORY](https://github.com/pydantic/pydantic/blob/main/HISTORY.md)). Not Django-specific | Company-backed, 12 listed maintainers, releases monthly ([PyPI](https://pypi.org/pypi/pydantic/json)) | The closest thing to Zod: one class gives validation, static types (`dataclass_transform`, so pyright/ty need no plugin) and JSON Schema. Django Ninja is built on it | Brings 4 packages (`pydantic-core` Rust extension, `annotated-types`, `typing-inspection`, `typing-extensions`) ([requires_dist](https://pypi.org/pypi/pydantic/2.14.2/json)). Pydantic V1 does not work on 3.14 |
| **msgspec** | 0.22.0 (2026-09-29) | 3.14 incl. free-threaded since 0.20.0 ([changelog](https://github.com/msgspec/msgspec/blob/main/docs/changelog.md)) | Moved from `jcrist/` to the `msgspec` GitHub org. Still "4 - Beta" | Zero runtime deps, the fastest option ([vendor benchmarks](https://msgspec.dev/benchmarks) *(vendor claim)*). `Struct` types check well statically | Fewer validators (no custom field validators like Pydantic's). No Django or OpenAPI integration. Its 3.14 forward-reference bug was fixed only in 0.22 (issue 1165) |
| **attrs + cattrs** | attrs 26.1.0 (2026-03-19), cattrs 26.2.1 (2026-09-26) | 3.14 classifiers on both | Hynek Schlawack / Tin Tvrtković, mature | Clean split between data classes (attrs) and (un)structuring (cattrs). Good typing | Two packages for what Pydantic does in one. Error messages are less direct. No Django or OpenAPI tie-in |
| **stdlib `dataclasses` + hand-written parsing** | stdlib | Yes | n/a | **Zero dependencies.** `@dataclass(frozen=True, slots=True)`, `Literal`, `TypeIs` (3.13+) and `match` are enough for small, fixed shapes | You write the checks yourself, with no JSON Schema and no automatic error collection |
| **DRF serializers** | `djangorestframework` 3.18.3 (2026-10-06) | Classifiers list Django 5.2 and Python 3.14 | Encode, mature | Already present if DRF is picked. Model-aware, gives 400 errors, works with drf-spectacular | **No static types.** `validated_data` and `data` are typed `Any` in the stubs ([serializers.pyi L126-132](https://github.com/typeddjango/djangorestframework-stubs/blob/master/rest_framework-stubs/serializers.pyi)). Slow compared with the others. Tied to Django |

**Python 3.14 deferred annotations (PEP 649/749).** Annotations are now evaluated lazily, so forward references work without quotes or `from __future__ import annotations`. Pydantic's docs show 3.14 models with unquoted references to names defined later ([Pydantic forward annotations](https://pydantic.dev/docs/validation/latest/concepts/forward_annotations/)). PEP 749 says the `__future__` import will start emitting `DeprecationWarning` once 3.13 reaches end of life, and will be removed at least two releases after that ([PEP 749](https://peps.python.org/pep-0749/)). **Do not add `from __future__ import annotations` to new 3.14 code.** The trap is that Pydantic, Ninja, msgspec and cattrs **evaluate annotations at runtime**. If Ruff's `TC` rules move an import that one of those libraries needs into an `if TYPE_CHECKING:` block, you get a `NameError` at class creation or the first request. Configure `runtime-evaluated-base-classes = ["pydantic.BaseModel", "ninja.Schema"]` and the matching decorators ([Ruff option source](https://github.com/astral-sh/ruff/blob/main/crates/ruff_workspace/src/options.rs)). Ruff's own docs use `pydantic.BaseModel` as the example.

### Where each layer validates

| Boundary | If DRF | If Ninja | Why |
|---|---|---|---|
| `GET /api/brands/` query params (`industry`, `ordering`, `page`) | A `Serializer` with `ChoiceField(choices=ALLOWED_SORTS)`, mapped to a dict of ORM expressions | A `Schema` with `ordering: Literal["rating", "-rating", "reviews", "-reviews"]` via `Query(...)` | Never pass input to `order_by()` (the Feb 2026 ORM CVEs, see `best-practices-2026.md`). Either way, the allow-list is a closed type |
| `PATCH /api/brands/<slug>/` body | `Serializer` with `max_length`, `partial=True` | `Schema` with `Field(max_length=...)` | DRF gives runtime safety only. Ninja also gives a typed object in the view |
| WP rows during the import | stdlib frozen dataclasses with `parse_brand(row) -> Brand` functions (no new dependency), then `full_clean()` before upsert | Pydantic models (already installed through Ninja) | WP data is untrusted. Failures should be collected per row, not raised on the first error |
| JWT claims in the **shared lib** | stdlib dataclass + explicit checks | same | **Do not add Pydantic to the shared lib.** Both services would inherit its version constraint, and the library's whole job is "token verification + permission check". The JWT library already validates `exp`/`iss`/`aud`. Mapping a dict to `Claims(sub: str, roles: frozenset[Role])` with `Role = Literal["reader", "editor"]` takes about 20 lines and can be tested without a framework |
| Settings and env vars | `os.environ` + explicit parsing in `settings.py` | same | `pydantic-settings` (2.16.2) would be one more dependency for about 10 env vars |

**Recommendation.** Use **no dedicated validation library for DRF**: serializers at the HTTP boundary and stdlib dataclasses elsewhere. For **Ninja, use Pydantic** (it is a transitive dependency anyway, `django-ninja 1.7.3` requires `pydantic>=2,<3` ([PyPI](https://pypi.org/pypi/django-ninja/1.7.3/json))). Use it for the API and the import, but not in the shared lib. If Pydantic is added explicitly: `pydantic>=2.14.2,<2.15`. Skip msgspec and attrs/cattrs. Nothing here needs their speed or their split design, and each is another package.

---

## 2. The Effect equivalent: typed errors, DI, composable effects and resources

| Package | Cooldown-safe version (date) | Py3.14 | Maintenance | Pros | Cons |
|---|---|---|---|---|---|
| **`returns`** (dry-python) | 0.30.0 (2026-10-27) | 3.14 classifier. 0.30 adds mypy `<2.5` support ([CHANGELOG](https://github.com/dry-python/returns/blob/master/CHANGELOG.md)) | Active (pushed today). Still 0.x and "4 - Beta" | The most complete Python version of the idea: `Result`, `Maybe`, `IO`, `RequiresContext` (a Reader for DI), `FutureResult` | **Needs its mypy plugin** for full typing ([README](https://github.com/dry-python/returns#readme)), so pyright/ty/pyrefly users lose features. Non-idiomatic for Django, where views, ORM and middleware all signal errors with exceptions |
| **`result`** (rustedpy) | 0.17.0 (2024-06-02) | No 3.14 classifier | **Archived 2026-06-25.** README: "THIS PROJECT IS NO LONGER MAINTAINED" ([issue #201](https://github.com/rustedpy/result/issues/201)) | — | Dead. A co-maintainer wrote: "this style of programming simply does not lend itself well to the python ecosystem, both for technical and cultural reasons" ([comment](https://github.com/rustedpy/result/issues/201)). No official successor; the `montasaurus/result` fork is unpublished |
| `option` | 2.1.0 (2022-04-18) | No | Stale since 2022 | — | Do not use |
| **`expression`** | 5.8.0 (2026-10-29) | 3.14 classifier | Active, single lead (repo moved to `dbrattli/Expression`) | F#-style `Result`/`Option`/pipelines, typed without a plugin | Same cultural mismatch as `returns`. Another vocabulary for reviewers to learn |
| `pyeffect` | 0.1.0 (2026-09-02), the only release | Requires 3.14 | One author, no project URLs on PyPI | Explicitly an Effect clone | Two months old, one release, unvetted. **Reject** (slopsquatting-shaped risk) |
| `effectpy` | 0.2.0 (2025-09-09) | No classifier | No author metadata, inactive for 14 months | "Effect/ZIO-inspired structured async" | **Reject** |
| **`anyio`** | 4.16.0 (2026-11-01) | 3.14 | Alex Grönholm, mature | Structured concurrency and cancel scopes | The app is sync Django with a sync import. Nothing needs it |
| `asyncio.TaskGroup` / `ExceptionGroup` | stdlib (3.11+) | Yes | — | Structured concurrency built in | Same: no concurrent I/O in scope |
| **`svcs`** | 26.2.0 (2026-08-24) | 3.14 | Hynek Schlawack | A small service locator with health checks | Official integrations are AIOHTTP, FastAPI, Flask and Starlette; **no Django integration** ([README](https://github.com/hynek/svcs#readme)) |
| `dependency-injector` | 4.49.1 (2026-06-18) | 3.14 | One lead, Cython build | Has a Django example | A full container and wiring framework. Heavy for two services and one verifier |

**Stdlib patterns that give most of Effect's value (Python 3.14, no dependencies):**
- **Typed errors** as a small exception hierarchy in the shared lib (`TokenError` → `TokenExpired`, `TokenInvalid`, `RoleMissing`), mapped to 401/403 in **one** place (a DRF `exception_handler` or a Ninja `@api.exception_handler`). Document the errors that can be raised in docstrings, since Python has no checked exceptions.
- **Errors as values where it helps:** the importer returns `Brand | RowError` per row, and `match` collects failures without aborting. A union type gives this without a `Result` library.
- **Exhaustiveness:** `match` on a `Literal`/`Enum` with `case _: assert_never(x)`, plus mypy's opt-in `exhaustive-match` error code ([mypy docs](https://github.com/python/mypy/blob/master/docs/source/error_code_list2.rst)). Use `Never` for functions that always raise, and `TypeIs` (3.13+) for narrowing helpers such as `is_editor(claims)`.
- **Generics:** PEP 695 `class Page[T]: ...` / `type Role = Literal[...]`. No `TypeVar` boilerplate.
- **DI:** constructor injection plus `typing.Protocol`. Example: `TokenVerifier(keys: KeyProvider, issuer: str, audience: str)`, built once in each service's `AppConfig.ready()` or a `functools.cache` factory. Tests pass a fake `KeyProvider`.
- **Resources:** `with` / `contextlib.ExitStack` and `transaction.atomic()` for the import.

**Assessment.** An Effect-style library is **not idiomatic or worth it** here. Django's request/response cycle, ORM and test client are built on exceptions. Wrapping them in `Result` adds an adapter at every edge. The best-known Result library died partly for that reason (above). The challenge also says the team will probe for code you can't defend. Plain exceptions, unions, `match`/`assert_never` and Protocol-based DI are easy to defend and fully checked by mypy/pyright.

**React side.** Use **plain TS + Zod, not Effect.** `effect` 4.0.0 was released on 2026-10-01 ([npm time](https://www.npmjs.com/package/effect?activeTab=versions)), so the major is five weeks old. The cooldown-safe version is 4.1.1 (2026-10-30), with a 56 MB unpacked package. The beta post said v3 was still recommended for production at the time ([Effect v4 beta](https://effect.website/blog/releases/effect/40-beta)). One fetch with loading, empty and error states is a discriminated union (`{status: "loading"} | {status: "error", error} | {status: "ok", data}`) plus `AbortController`. Effect's typed-error and retry machinery would be most of the component's code.

---

## 3. Fully typed code

### Python type checkers

| Checker | Cooldown-safe version (date) | Py3.14 | Maturity | Django support |
|---|---|---|---|---|
| **mypy** | 2.4.1 (2026-10-28); 2.3.1 (2026-08-15) | Yes. 2.4 adds 3.15 and makes the native parser the default ([CHANGELOG](https://github.com/python/mypy/blob/master/CHANGELOG.md)) | Reference checker. 2.0 (2026-05) turned on `local-partial-types` and `strict-bytes` by default | **Best.** django-stubs plus its mypy plugin: "full and complete support" (managers, querysets, reverse relations, `settings`), and the same for the DRF plugin ([django-stubs README](https://github.com/typeddjango/django-stubs#readme)) |
| pyright | npm 1.1.414 (2026-09-09) | Yes | Mature and fast. The PyPI `pyright` package is a third-party wrapper that downloads Node through `nodeenv` | django-stubs: "basic support, checked in CI". No plugins, so reverse relations and many queryset/manager types fall back to `Any` |
| basedpyright | 1.40.2 (2026-10-04) | Yes | Pyright fork with stricter rules and bundled Node (`nodejs-wheel-binaries`) | Same as pyright |
| **ty** (Astral) | 0.0.95 (2026-10-29) | Yes | **Beta**, "breaking changes … may occur between any two versions" ([README](https://github.com/astral-sh/ty#version-policy)). Releases almost daily | Built-in Django inference since 0.0.92 (fields, `pk`/`id`, `<fk>_id`, `get_FOO_display`), but **requires `django-types`, not django-stubs**. No reverse relations and no checks on query field names ([ty Django docs](https://docs.astral.sh/ty/features/third-party/django/)) |
| pyrefly (Meta) | 1.4.0 (2026-10-15) | Not verified explicitly | 1.0 shipped 2026-05-12, "5 - Production/Stable" | Built-in support for a subset with django-stubs: fields, FK, M2M forward managers, choices. Reverse relations "Not yet supported", querysets only basic `.all()` ([pyrefly Django docs](https://pyrefly.org/en/docs/django/)) |

**Stubs version matrix (important).** `django-stubs` 6.1.2 (2026-10-05) targets Django 6.1, with **"partial" support for 5.2** and mypy 1.13–2.4 on Python 3.11–3.14. `django-stubs` 5.2.9 targets 5.2 but lists only Python 3.10–3.13 ([compat table](https://github.com/typeddjango/django-stubs#version-compatibility)). "Partial" means APIs removed in newer Django stay in the stubs, but **APIs added in 6.x are also present**, so the checker will not flag a 6.x-only API such as `django.tasks` ([maintainer explanation](https://github.com/typeddjango/django-stubs/discussions/2101#discussioncomment-9276632)). The `django-lts` skill's "not in the 5.2 docs" rule and the tests still have to catch those. `djangorestframework-stubs` 3.18.1 (2026-08-25) needs `django-stubs>=6.1.0` and **`mypy<2.4`**. 3.18.2 widens that to `<2.5`, but it was uploaded 2026-11-02 23:46 UTC and clears the cooldown on **2026-11-10**.

**Recommendation: mypy + django-stubs as the CI gate**, because it is the only checker that understands Django's ORM fully, and the ORM is most of this codebase. Basedpyright or ty can serve as the editor LSP if you like, but the gate is mypy. Pins:
- Ninja: `mypy>=2.4.1,<2.5`, `django-stubs[compatible-mypy]>=6.1.2,<6.2` (brings `django-stubs-ext`), plus Pydantic's mypy plugin (`pydantic.mypy`).
- DRF, today: `mypy>=2.3.1,<2.4`, `django-stubs>=6.1.2,<6.2`, `djangorestframework-stubs>=3.18.1,<3.19`. From 2026-11-10, move to 3.18.2 and mypy 2.4.1.
- The shared lib needs only `mypy` (no Django stubs). Run `--strict` there.

```toml
[tool.mypy]
python_version = "3.14"
strict = true
warn_unreachable = true
enable_error_code = ["ignore-without-code", "redundant-expr", "truthy-bool",
  "possibly-undefined", "explicit-override", "exhaustive-match", "deprecated"]
plugins = ["mypy_django_plugin.main"]   # + "mypy_drf_plugin.main" or "pydantic.mypy"
[[tool.mypy.overrides]]
module = ["*.migrations.*"]
ignore_errors = true
[tool.django-stubs]
django_settings_module = "config.settings"
```
`strict = true` means you cannot disable `disallow_any_generics` without good reason. Third-party packages without types (for example a MariaDB driver) get a targeted `ignore_missing_imports` override, not a global one.

### Ruff (`ruff>=0.17.3,<0.18`, 0.17.3 = 2026-10-27)

`select = ["E","F","W","I","UP","B","ANN","S","TC","DJ","PGH","RUF","BLE","PT","PYI","FA"]`. Reasons:
- `ANN`: annotations everywhere, with `ANN401` banning bare `Any`.
- `S`: bandit-style security checks (`S608` SQL string formatting, `S105` hardcoded secrets, `S308` `mark_safe`, `S113` requests without a timeout). Ignore `S101` in tests.
- `TC`: move typing-only imports into `TYPE_CHECKING` blocks. It **must** be set up with `runtime-evaluated-base-classes` / `-decorators` for Pydantic/Ninja (see §1).
- `DJ`: flake8-django (`null=True` on CharField, model `__str__`, `fields = "__all__"` on ModelForm).
- `PGH003`: no blanket `# type: ignore`.
- `RUF100`: remove unused `noqa`.
- `UP`: 3.14 syntax (PEP 695, `X | Y`). `UP037` removes quoted annotations.

### TypeScript (frontend)

TypeScript 7.0 (the Go port, released 2026-07-08) **turns `strict` on by default and ships no programmatic API**. Tools that need the compiler API should stay on 6.0 through the `@typescript/typescript6` alias ([TS 7.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7.0/)). This matters for codegen (§4) and typescript-eslint, so **use `typescript@6.0.3` (2026-04-16)** unless the frontend researcher has a reason to move. Flags beyond `strict`: `noUncheckedIndexedAccess` (array and record access returns `T | undefined`), `exactOptionalPropertyTypes`, `noImplicitOverride`, `noImplicitReturns`, `noFallthroughCasesInSwitch`, `noPropertyAccessFromIndexSignature`, `verbatimModuleSyntax`, `erasableSyntaxOnly` (no enums or namespaces, which fits Vite/esbuild transpilation), `noUncheckedSideEffectImports`, and `isolatedModules` ([tsconfig reference](https://www.typescriptlang.org/tsconfig/)).

---

## 4. End-to-end type safety across the API boundary

| Tool | Cooldown-safe version (date) | Role | Maintenance | Pros | Cons |
|---|---|---|---|---|---|
| **Ninja built-in OpenAPI** | django-ninja 1.7.3 (2026-10-29) | Schema from Pydantic types | Single lead (vitalik), active | OpenAPI **3.1.0** from the same types the views use ([schema.py](https://github.com/vitalik/django-ninja/blob/master/ninja/openapi/schema.py)). `manage.py export_openapi_schema` is built in | Ninja-only |
| **drf-spectacular** | 0.30.0 (2026-07-06) | Schema from DRF serializers | Single lead (tfranzel), active | OAS 3.0.3/3.1/3.2. `manage.py spectacular --file schema.yml --validate` ([README](https://github.com/tfranzel/drf-spectacular#readme)) | +5 runtime deps (`uritemplate`, `PyYAML`, `jsonschema`→`attrs`/`referencing`/`rpds-py`/`jsonschema-specifications`, `inflection`). CI tests `py314-django5.2-drf3.16` but **not DRF 3.18** ([tox.ini](https://github.com/tfranzel/drf-spectacular/blob/master/tox.ini)). Function views need `@extend_schema` |
| **openapi-typescript** | 7.13.0 (2026-02-11) | Types only (`paths`, `components`) | 2 maintainers. **No release in 9 months**; recent commits are Renovate bumps only | Output is pure types, so **zero runtime bytes**. 6 deps, dev-only | Peer `typescript ^5.x`. It imports the TS compiler API (`ts.factory`, [source](https://github.com/openapi-ts/openapi-typescript/blob/main/packages/openapi-typescript/src/lib/ts.ts)), so it **breaks on TS 7**. A PR to widen the peer to TS 6 was closed unmerged (#2773). It runs on 6.0 with a peer warning *(not tested here)* |
| openapi-fetch | 0.17.0 (2026-02-11) | Typed fetch wrapper | Same team | Tiny, 1 dep | Not needed for one GET and one PATCH |
| @hey-api/openapi-ts | 0.99.0 (2026-06-22) | Types + client + optional Zod schemas | **One npm maintainer**, pre-1.0 | Can generate Zod validators too | Several `@hey-api/*` packages plus `c12`. Breaking changes between 0.x releases |
| orval | 8.46.0 (2026-10-30) | Clients + Zod + mocks | 2 maintainers | Feature-rich | Depends on ~20 `@orval/*` packages (angular, hono, swr, mcp …). Heavy supply-chain surface |
| Zod `z.fromJSONSchema()` | zod 4.6.7 | JSON Schema → Zod at runtime | — | — | "**Experimental** … not considered part of Zod's stable API" ([docs](https://github.com/colinhacks/zod/blob/main/packages/docs/content/json-schema.mdx)). Runtime only, no static types |

**Recommended minimal path (2 frontend dependencies: `zod` at runtime, `openapi-typescript` for dev):**
1. Backend: commit the generated schema (`openapi.json`) to the repo. In CI, regenerate it and `git diff --exit-code`, so an API change without a schema update fails. Ninja needs no extra dependency for this. DRF needs `drf-spectacular>=0.30.0,<0.31`, or hand-written types with no generator if you want zero extra dependencies (only 2 endpoints).
2. Frontend: `pnpm exec openapi-typescript ../openapi.json -o src/api/schema.gen.ts` (dev dependency `openapi-typescript@7.13.0`, on TS 6.0.3).
3. Write **one** Zod schema by hand for the brand-list response (`zod@^4.6.7`, 2026-10-12, zero deps, one npm maintainer: `colinhacks`). Tie it to the generated type at compile time so they cannot drift: `type _Check = Expect<Equal<z.infer<typeof BrandPage>, components["schemas"]["BrandPage"]>>` (or `satisfies z.ZodType<…>`).
4. `fetch` → `BrandPage.safeParse(json)` → on failure, show the error state and log the issue path.

**Should React still validate at runtime with Zod? Yes, at this one boundary.** Generated types prove what the API was meant to return when the schema was generated. They prove nothing about what the separately deployed service returns at runtime (version skew during a rolling deploy, a proxy error page, a field that is `null`). `safeParse` turns those cases into the error state the challenge grades, instead of `undefined` showing up in the UI. The cost is one small dependency (`zod/mini` is available if bundle size matters). Generating Zod from OpenAPI (hey-api, orval) would remove the hand-written schema, but adds a pre-1.0 or very large tool for a single endpoint.

---

## Unverified / open items
- Pyrefly's Python 3.14 support was not confirmed in its docs (no 3.14 classifier on PyPI).
- openapi-typescript 7.13.0 on TypeScript 6.0 was not run (it peers `^5.x`). If it fails, run it with a pinned TS 5 through `pnpm dlx`, or hand-write the types.
- drf-spectacular with DRF 3.18 is not in its CI matrix. Ask the stack-decisions researcher to confirm, or run its test suite.
- Effect 4.0 stable release notes were not read directly. Benchmark and bundle claims are vendor or *(secondary)*. The release date comes from npm.
- The msgspec vs Pydantic performance figures are vendor benchmarks. They don't matter at this data size (hundreds of rows).
