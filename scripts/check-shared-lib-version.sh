#!/usr/bin/env bash
# Fails when shared-lib/src changed since the base branch but shared-lib's
# version didn't (ADR 0025). Each service's uv.lock records the library's
# version, not its code: without a bump, `uv lock --check` can't tell a
# service that the code it was tested with changed.
#
# Usage: scripts/check-shared-lib-version.sh [base-ref]   (default: origin/main)
set -euo pipefail

base_ref="${1:-origin/main}"
cd "$(git rev-parse --show-toplevel)"
merge_base=$(git merge-base "$base_ref" HEAD)

version_of() { sed -n 's/^version = "\(.*\)"$/\1/p'; }
new=$(version_of < shared-lib/pyproject.toml)

if ! old_toml=$(git show "$merge_base:shared-lib/pyproject.toml" 2>/dev/null); then
  echo "shared-lib is new on this branch (version $new)."
  exit 0
fi
# Compares the base with the working tree, so uncommitted changes count too.
if git diff --quiet "$merge_base" -- shared-lib/src; then
  echo "shared-lib/src unchanged since $base_ref."
  exit 0
fi
old=$(version_of <<< "$old_toml")
if [[ "$old" == "$new" ]]; then
  echo "shared-lib/src changed since $base_ref, but its version is still $old." >&2
  echo "Run 'uv version --bump <patch|minor|major>' in shared-lib/, add a CHANGELOG entry," >&2
  echo "then 'uv lock' in main-app/ and auth-service/." >&2
  exit 1
fi
echo "shared-lib $old -> $new."
