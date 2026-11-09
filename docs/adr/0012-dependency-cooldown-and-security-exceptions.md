# 0012. Seven-day dependency cooldown, with approved security exceptions

- Status: Accepted (facts corrected in [0018](0018-factual-corrections-to-0004-0008-0012.md))
- Date: 2026-11-09

## Context
Most 2025–26 supply chain attacks (Axios, LiteLLM, the Keyv worm, Mastra) published
real-looking versions with stolen maintainer or CI credentials, so lockfile hashes
didn't catch them. PyPI handles 92% of malware reports within 24 hours, but the
slowest took 4 days and one major attack lasted about 10. Against that, security fixes
should land quickly. No Django CVE has been on CISA's known-exploited list; Django
pre-announces security releases about a week ahead.

## Options considered
- **No cooldown.** Fastest fixes. Rejected: takes every malicious release on day one.
- **1–3 days** (pnpm's built-in default was 1 day on this machine). Rejected: misses
  the slow tail of detections.
- **14 days.** Rejected: delays fixes with little extra protection.
- **7 days, with per-release exceptions for security fixes.** Chosen.
- Exception syntax: a relative duration (`"1 day"`) was rejected because it also admits
  any later release; a fixed timestamp was chosen.
- A standing shorter cooldown for Django was rejected: Django doesn't use PyPI trusted
  publishing or attestations.

## Decision
- uv: `[tool.uv] exclude-newer = "7 days"` in every pyproject. pnpm:
  `minimumReleaseAge: 10080` in the frontend's `pnpm-workspace.yaml`.
- Exceptions only for a High-severity fix, a Moderate one in a feature we use, or known
  exploitation. The user approves; an agent never approves its own exception.
- Verify the release (PyPI hashes against Django's signed checksums; the signed git
  tag), then pin the exception to a timestamp just after the upload, e.g.
  `exclude-newer-package = { django = "2026-11-03T16:00:00Z" }`, with a comment giving
  the reason and the removal date.
- Remove it only after upload + 7 days (removing it earlier downgrades the package).
  Record the reason in the commit message.

## Consequences
- Scanners can miss Django CVEs: GitHub's entries for the October/November 2026 CVEs
  were unreviewed, so `uv audit`, Dependabot and Renovate reported 5.2.18 as clean.
  Watch the `django-announce` list.
- On this date: Django 5.2.19 (GIS-only fix, not used) waits until 2026-11-10 15:22
  UTC; PyMySQL 1.2.4 waits too (ADR 0007).

## Revisit when
Registries add vulnerability-aware cooldown overrides, Django adopts trusted
publishing, or detection-time data changes.

## Sources
`docs/research/cooldown-vs-security-fixes.md`; `.agents/skills/uv-only/SKILL.md`.
