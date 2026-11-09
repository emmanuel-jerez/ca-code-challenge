#!/usr/bin/env bash
# Link each skill in .agents/skills into .claude/skills so Claude Code can load
# it. .agents/skills is the only source; .claude/skills is generated and ignored.
# Links are per skill because Claude Code writes its own files into
# .claude/skills, which breaks a single directory-level link.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
src="$root/.agents/skills"
dest="$root/.claude/skills"
mkdir -p "$dest"

# Remove links that point at skills that no longer exist.
for link in "$dest"/*; do
  [ -L "$link" ] && [ ! -e "$link" ] && rm "$link" && echo "removed stale $(basename "$link")"
done

for dir in "$src"/*/; do
  name="$(basename "$dir")"
  [ -f "$dir/SKILL.md" ] || continue
  target="../../.agents/skills/$name"
  if [ -e "$dest/$name" ] && [ ! -L "$dest/$name" ]; then
    echo "skipped $name: .claude/skills/$name exists and is not a link" >&2
    continue
  fi
  ln -sfn "$target" "$dest/$name"
done
echo "linked $(find "$dest" -maxdepth 1 -type l | wc -l) skills into .claude/skills"
