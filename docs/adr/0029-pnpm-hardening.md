# 0029. pnpm hardening beyond the cooldown

- Status: Accepted
- Date: 2026-11-09

## Context
ADR 0012 set a 7-day release age for npm packages (`minimumReleaseAge:
10080`). The frontend's first install (Pillar 3) was the point to decide the
rest of pnpm's supply-chain settings. From
`docs/research/pillar-3-brandlist-component.md` §11:

- pnpm is on 12. With `minimumReleaseAge` set explicitly, it fails when no
  version is old enough. The built-in non-strict mode installs a too-new
  version instead.
- `trustPolicy` is off by default. `no-downgrade` fails when a release has
  weaker trust evidence (trusted publisher, provenance, none) than an earlier
  one of the same package. It would not have caught the TanStack attack,
  which used the real trusted publisher; the cooldown would have.
- Only two packages in the planned tree have install scripts, both optional:
  `@parcel/watcher` (for `sass --watch`) and `fsevents` (macOS).
- `onlyBuiltDependencies` was removed in pnpm 11 in favor of `allowBuilds`.

The user accepted the research recommendation on this date.

## Options considered
- **The cooldown alone.** Rejected: it leaves trust downgrades, exotic
  transitive sources and install scripts to defaults that may change.
- **Approving the two install scripts.** Rejected: neither is needed to
  compile or test, and prebuilt packages cover `@parcel/watcher`.
- **State every setting explicitly, deny both scripts, pin pnpm.** Chosen.

## Decision
`frontend/pnpm-workspace.yaml` sets, each with a comment saying why:
`minimumReleaseAge: 10080`, `minimumReleaseAgeStrict: true`,
`minimumReleaseAgeIgnoreMissingTime: false`, `trustPolicy: no-downgrade`,
`blockExoticSubdeps: true`, `strictDepBuilds: true`, and `allowBuilds` denying
`@parcel/watcher` and `fsevents`. `package.json` pins
`"packageManager": "pnpm@12.16.1"`. `trustLockfile` stays at its default
(false), so every install re-checks age and trust for each lockfile entry.

## Consequences
- An install can fail when no version in range is old enough or trusted
  enough. That's the point: the fix is waiting or an ADR 0012 exception,
  never loosening a setting.
- `sass --watch` uses its slower fallback watcher.

## Revisit when
pnpm changes these defaults or adds a stronger trust check, or a needed
package requires an install script.

## Sources
`docs/research/pillar-3-brandlist-component.md` §11; pnpm settings docs
(dependency resolution, build), current for pnpm 12.
