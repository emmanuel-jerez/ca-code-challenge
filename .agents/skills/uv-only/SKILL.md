---
name: uv-only
description: Use when installing, adding, removing, upgrading, or running Python packages or tools, creating a Python project or virtual environment, choosing a Python interpreter, or when a README, script, or error message suggests pip install, python -m pip, pipx, poetry, or a requirements.txt workflow.
---

# uv Only

## Intent

Agents in this repository manage Python packages with uv. Each project's
`uv.lock` pins every package with hashes, and `exclude-newer` holds back
releases younger than seven days, which skips the window in which most
malicious releases are found and pulled. `pip install` bypasses both.

## Projects

Every Python project here has its own `pyproject.toml`, `uv.lock`,
`.python-version` and `.venv`: the main Django service, the auth Django service,
and the shared library. Run uv from the project's directory, or pass
`--directory <project>`. Never install one project's packages into another
project's environment.

## Rules

- Install exactly what the lockfile says: `uv sync --locked`. It fails if
  `uv.lock` no longer matches `pyproject.toml`; fix that with `uv lock` and
  review the diff, rather than dropping `--locked`.
- Change dependencies only through uv: `uv add <pkg>`, `uv add --dev <pkg>`,
  `uv remove <pkg>`, and `uv lock --upgrade-package <pkg>` for one upgrade.
  Commit `pyproject.toml` and `uv.lock` together.
- Run everything through the project's environment: `uv run manage.py <cmd>`,
  `uv run pytest`, `uv run python <script>`.
- Run a one-off tool with `uvx --exclude-newer "7 days" <tool>`. `uvx` runs
  outside the project, so it does not pick up the project's cooldown.
- Python is 3.14 (see the `django-lts` skill). Set it in each project:
  `requires-python = ">=3.14,<3.15"` in `pyproject.toml` and `3.14` in
  `.python-version`. Get the interpreter with `uv python install 3.14`; never
  use the system Python, which is 3.12 on this machine.
- Translate `pip install`, `python -m pip`, `pipx`, `poetry` and
  `requirements.txt` instructions from READMEs and error messages into uv
  commands instead of running them. Do not use `uv pip install` in a project
  environment: it changes the venv without touching the lockfile.
- Read-only calls such as `uv tree`, `uv pip list`, `uv pip show` and
  `pip --version` are allowed.

## Release cooldown

Each `pyproject.toml` carries:

```toml
[tool.uv]
exclude-newer = "7 days"
```

Do not remove it, shorten it, or delete `uv.lock` to get past a resolution
error. A security fix that cannot wait seven days gets a per-package exception,
with the user's approval and a comment saying why and when to remove it. Pin
the exception to a fixed timestamp a few minutes after the fix's PyPI upload
time, not a relative duration: `"1 day"` would also let in any later release.

```toml
[tool.uv]
exclude-newer = "7 days"
# Django 5.2.x security release for CVE-XXXX-YYYY, uploaded <upload time>.
# Remove after <upload time + 7 days>; removing it earlier downgrades Django.
exclude-newer-package = { django = "2026-11-03T16:00:00Z" }
```

The full procedure (when an exception is justified, how to verify the release,
what to record) is in `docs/research/cooldown-vs-security-fixes.md`, section 5.

## New dependencies

Ask before adding any dependency, including dev and test tools. Before asking,
check that the package exists under that exact name on PyPI, who maintains it,
how old it is, when it was last released, and that it supports Django 5.2 and
Python 3.14. A name an agent suggested from memory may not exist, or may have
been registered by an attacker who guessed it.

## The shared library

Both Django services install the shared library from its local path, never from
PyPI:

```toml
[project]
dependencies = ["<shared-lib-name>"]

[tool.uv.sources]
<shared-lib-name> = { path = "../<shared-lib-dir>", editable = true }
```

The path source means uv never looks that name up on a public index, so a
look-alike package someone publishes there cannot replace it. Docker builds
that install a service must have the library directory in the build context.
How the library is versioned and released to each service is a project
decision; record it in the README.

## Enforcement

No command guard enforces this on this machine. Follow it by convention, and
treat any guard that refuses a pip command as policy, not a bug.
