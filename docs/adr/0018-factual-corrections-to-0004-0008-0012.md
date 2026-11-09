# 0018. Factual corrections to 0004, 0008 and 0012

- Status: Accepted
- Date: 2026-11-09
- Corrects: [0004](0004-nh3-html-sanitizer.md), [0008](0008-gunicorn-whitenoise-base-image.md),
  [0012](0012-dependency-cooldown-and-security-exceptions.md)

## Context
The pillar research found statements in three records that were wrong on the day they
were written. None of the errors changes what those records decided. ADR 0000 says
records are never rewritten, so the corrections live here and each record's status
points to this one. Each fact was checked against the primary source on this date.

## Options considered
- **Supersede each record with a full restatement.** Rejected: a superseding record
  implies a changed decision, and these decisions haven't changed.
- **Edit the records in place.** Rejected by ADR 0000.
- **One correction record, linked from each record's status line.** Chosen.

## Decision
The following corrections apply. The decisions in 0004, 0008 and 0012 stand.

**0004 (nh3).** The Consequences say the ammonia fix is "merged upstream but
unreleased". In fact:
- ammonia released the fixes in 4.1.7 (2026-10-11) and 4.1.8 (2026-10-17), and in
  4.2.3 and 4.2.4 on its 4.2 line.
- nh3 0.3.7 still pins ammonia 4.1.4, so the fix hasn't reached nh3.
- The three advisories that affect 4.1.4 are RUSTSEC-2021-0157, RUSTSEC-2021-0158 and
  RUSTSEC-2026-0373. All need `style` or SVG animation tags to be allowed, which our
  allow-list forbids.

The revisit trigger, "nh3 releases the ammonia fix", stays correct.

**0008 (gunicorn + whitenoise).** The Context says both services need something to
serve static files. Only the main app does, for the compiled SCSS and the React bundle.
The auth service serves static files only if it runs the Django admin or the DRF
browsable API. ADR 0015 turns the browsable API off, and whether the auth service has an
admin is still open. So whitenoise goes into the auth service only if it ends up serving
static files.

**0012 (cooldown).** The Consequences call Django 5.2.19 a "GIS-only fix". It fixes
five CVEs on 5.2, and two aren't GIS: CVE-2026-108147 (`MultiPartParser`) and
CVE-2026-113593 (cache keys and `Vary`). Waiting for the cooldown still holds, because
neither is reachable here (ADR 0014). It clears on 2026-11-10 at 15:22 UTC.

## Consequences
Readers of 0004, 0008 and 0012 follow the status line here. ADR 0014 records the same
5.2.19 correction for 0001.

## Revisit when
Another factual error turns up in an accepted record. A correction that changes a
decision gets a superseding record instead.

## Sources
- [crates.io ammonia versions](https://crates.io/crates/ammonia/versions); [OSV query for ammonia 4.1.4](https://osv.dev/list?ecosystem=crates.io&q=ammonia);
  nh3 v0.3.7 [`Cargo.toml`](https://github.com/messense/nh3/blob/v0.3.7/Cargo.toml).
- [Django security releases, 2026-11-03](https://www.djangoproject.com/weblog/2026/nov/03/security-releases/).
- `docs/research/pillar-1-django-backend.md` Conflicts; `docs/research/pillar-5-auth-service.md` §11 and Conflicts.
