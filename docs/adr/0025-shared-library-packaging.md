# 0025. Shared library packaging, name and upgrade path

- Status: Accepted
- Date: 2026-11-09

## Context
CHALLENGE.md Pillar 6: the shared library is its own versioned package, with its own
`pyproject.toml`, installed into both services, and question 8 asks how they pin and
upgrade it. AGENTS.md already says it installs by local path. The research
(`docs/research/pillar-6-shared-library.md` §5–6, verified with uv 0.13.6) found:

- **What a directory path source records.** `uv.lock` stores only its version, with no
  content hash.
  - A version bump makes each service's `uv lock --check` fail until it re-locks.
  - A code-only change passes silently.
  - Non-editable installs keep stale code unless `tool.uv.cache-keys` covers the source.
- **Build backends.** `uv_build` downloads nothing at build time. `hatchling` fetches 6
  packages that aren't in any lockfile.
- **The name.** With `--no-sources`, or under pip, the package name is looked up on
  PyPI. `shared` is a real PyPI project. `brandreviews-authz` returned 404 on
  2026-11-09.

## Options considered
**Install mode:**
- **Hashed wheel paths.** Each service could pin its own version. Rejected: committed
  binary artifacts and an extra release step.
- **A git tag.** Rejected: network and credentials at build time.
- **A uv workspace.** Rejected: one lockfile would couple both services' third-party
  upgrades.
- **A directory path plus a required version bump.** Chosen.

**Build backend:**
- **hatchling.** Rejected: build-time downloads outside the lockfile.
- **setuptools.** Rejected: two major versions in 2026.
- **`uv_build`.** Chosen.

**Name:**
- **`shared`** or another generic name. Rejected: a dependency-confusion risk.
- **A project-prefixed name.** Chosen.

## Decision
- **Package:** `brandreviews-authz` (import `brandreviews_authz`), in `shared-lib/`, with
  a `src/` layout and `py.typed`.
- **Build:** `uv_build>=0.13.6,<0.14`, bumped together with the uv binary in the images.
- **Versioning:** a static `version` in `pyproject.toml`, following SemVer, plus a
  `CHANGELOG.md`.
- **Install:** each service declares it as a uv path source.
  - It's editable for local development and installed `--no-editable` in images.
  - Images get it from a Compose `additional_contexts` entry, so no repo-root context is
    needed.
  - `tool.uv.cache-keys` covers `pyproject.toml` and `src/**/*.py`.
- **Upgrades:** every change under `shared-lib/src` bumps `version`, and a check fails
  when it doesn't. The check runs in CI once CI exists. Each service then re-locks and
  runs its tests in the same change.
- **Dependency ranges:** wide in the library, exact in each service's lockfile.

## Consequences
- Both services always run the library at the same commit. Rolling out a breaking change
  still follows expand → migrate → contract (AGENTS.md).
- Anyone can still register the name on PyPI. Never run `uv lock --no-sources` or pip
  against the services.

## Revisit when
The services need different library versions at the same time (switch to hashed wheel
paths), the library moves to its own repository, or uv changes how path sources lock.

## Sources
`docs/research/pillar-6-shared-library.md` §5–7; [uv docs: dependency sources](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-sources); [PyPI JSON API](https://pypi.org/pypi/brandreviews-authz/json) (404 on 2026-11-09).
