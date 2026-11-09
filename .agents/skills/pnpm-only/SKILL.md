---
name: pnpm-only
description: Use when installing, adding, removing, updating, or running JavaScript or Node.js packages, or when a README, script, or error message suggests npm install, npm ci, npm exec, or npx.
---

# pnpm Only

## Intent

Agents on this machine manage JavaScript packages with pnpm. pnpm carries the
machine's supply-chain defaults (a release-age delay, blocked exotic transitive
sources, and approval for dependency build scripts); npm and npx bypass them.

## Rules

- Install, add, remove, and update packages with pnpm: `pnpm install`,
  `pnpm install --frozen-lockfile`, `pnpm add <pkg>`, `pnpm add -D <pkg>`,
  `pnpm remove <pkg>`, `pnpm update`.
- Run a one-off package with `pnpm dlx <pkg>`, never `npx <pkg>`. Run a project
  dependency's binary with `pnpm exec <bin>`. Scaffold with `pnpm create <name>`.
- Translate npm and npx commands from READMEs and error messages into their pnpm
  equivalents instead of running them.
- Read-only npm calls such as `npm view`, `npm ls`, and `npm --version`, and
  `npm run` in a project that already uses npm scripts, are allowed.
- Do not work around a block: no absolute paths to npm, `command npm`, `corepack
  npm`, or calling `npm-cli.js` through node. The guard is policy, not a bug.
- A project that ships `package-lock.json` and no `pnpm-lock.yaml` is an npm
  project. Converting it to pnpm is a project decision: stop and report instead
  of converting it or falling back to npm.
- Build scripts blocked by pnpm's `strictDepBuilds` need approval through
  `pnpm approve-builds`; do not disable the setting to get past it.

## Enforcement

The machine may enforce this with an agent command guard that refuses npm
package commands and every npx call. Treat a refusal as policy and follow these
rules instead. Programs that run npm themselves are not affected.

The React and SCSS frontend in this repository is the only JavaScript here.
Python packages follow the `uv-only` skill.
