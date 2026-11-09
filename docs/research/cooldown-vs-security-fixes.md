# Release cooldown vs. fast security fixes

Researched 2026-11-09 for this repo's policy: uv `exclude-newer = "7 days"`, plus a per-package exception that needs the user's approval (`uv-only` skill), and pnpm's release-age delay (`pnpm-only` skill).
Every tool behavior marked **(tested)** was reproduced locally with uv 0.13.6, in a throwaway project in the scratchpad that resolves Django. Nothing was installed.
Claims marked *(secondary)* come only from press or blog coverage, not from the source that owns them.

**Bottom line**
- Keep 7 days as the default.
- Don't give Django a standing shorter cooldown. It does **not** use trusted publishing or attestations.
- Handle each security release as a one-off exception, with an **absolute** per-package cutoff, after verifying the release.
- Biggest surprise: GitHub, OSV and `uv audit` still don't link October's or November's Django CVEs to the PyPI package. Tools that act on advisories (Dependabot, Renovate, `uv audit`) can't see them, so watch `django-announce` instead.

---

## 1. The trade-off, quantified

**Malicious releases are mostly removed within hours. The long tail runs to days.**

| Evidence | Number |
|---|---|
| PyPI 2025: time to handle malware reports | "66% of all reports were handled within 4 hours, climbing to 92% within 24 hours", and the slowest took "a maximum of 4 days" ([PyPI 2025 review](https://blog.pypi.org/posts/2025-12-31-pypi-2025-in-review)). This is measured from the *report*, not the upload. |
| LiteLLM / Telnyx on PyPI (Mar 2026) | Upload to quarantine took **2h32m** for litellm and **3h42m** for telnyx. litellm was still downloaded 119k times in that window ([PyPI incident report](https://blog.pypi.org/posts/2026-04-02-incident-report-litellm-telnyx-supply-chain-attack/)). |
| 10 major attacks (npm, PyPI, Actions) | chalk < 12h, Nx 4h, rspack 1h, web3.js 5h, num2words < 12h, Ultralytics 1–12h, tj-actions 3d, Kong ≈ 10d, xz ≈ 5 weeks. **8 of 10 were under a week.** A 14-day cooldown stops every one except xz ([Woodruff](https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns)). |
| Q1 2026 vendor estimate | About 9h median from publication to takedown on PyPI *(secondary, [Safeguard](https://safeguard.sh/resources/blog/pypi-malicious-package-trends-q1-2026))*. |

**Exploitation after disclosure is fast in general, but no Django CVE has ever been in KEV.**
- Mandiant's average time-to-exploit was 5 days in 2023, down from 32 days in 2021–22. It rises to 47 days if 15 outliers are included *(secondary: [Help Net](https://www.helpnetsecurity.com/2024/10/16/time-to-exploit-vulnerabilities-2023/); [Google blog (ja)](https://cloud.google.com/blog/ja/topics/threat-intelligence/time-to-exploit-trends-2023))*.
  - Google's analysis of 2024 data reports −1 days, meaning exploitation before the patch on average *(secondary, via [Qualys](https://www.qualys.com/the-broken-physics-of-remediation))*.
  - Rapid7 reports a median of 5 days from publication to KEV listing *(secondary, [CSA/Rapid7 summary](https://labs.cloudsecurityalliance.org/research/csa-whitepaper-collapsing-exploit-window-ai-speed-vulnerabil/))*.
- The [CISA KEV feed](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json) (catalog 2026.11.06, 1,769 entries) has **zero Django entries**.
  - Nearby stack entries do appear: Starlette CVE-2026-48710 (added 2026-09-02), Vite CVE-2025-31125, and React Server Components CVE-2025-55182.
- So the generic "5 days to exploit" number fits edge devices and mass-scanned products better than Django patch releases, most of which are rated low or moderate. The tail risk is real, though, when a High lands, as in August 2026 (§2).

**Recommended cooldown lengths**

| Length | Who | Why |
|---|---|---|
| 1 day | pnpm built-in default (`1440` minutes, non-strict) ([pnpm](https://pnpm.io/settings/dependency-resolution)) | Backward-compatible floor |
| 2 days | gem.coop server-side *(secondary, [Nesbitt](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html))* | |
| 3 days | PyPI's own advice (`P3D`, "configured globally") ([PyPI incident report](https://blog.pypi.org/posts/2026-04-02-incident-report-litellm-telnyx-supply-chain-attack/)), Dependabot default since 2026-07-14 ([GitHub changelog](https://github.blog/changelog/2026-07-14-dependabot-version-updates-introduce-default-package-cooldown/)), Renovate npm preset *(secondary, Nesbitt)* | Covers about 92% or more of PyPI takedowns |
| 7 days | Woodruff, Semgrep org-wide ([Semgrep](https://semgrep.dev/blog/2026/rolling-out-dependency-cooldowns-org-wide)), zizmor flags anything lower *(secondary, Nesbitt)* | Covers 8 of 10 historical attacks and PyPI's 4-day maximum |
| 14 days | Woodruff (upper bound) | Every attack in his sample except xz |
| 21 days | Snyk auto-upgrade PRs *(secondary, Nesbitt)* | |

## 2. How Django ships security fixes

Source: [Django security policy](https://docs.djangoproject.com/en/dev/internals/security/), unless noted.

- **Severity levels:**
  - **High:** RCE, SQL injection.
  - **Moderate:** XSS, CSRF, broken authentication.
  - **Low:** DoS, data exposure, session problems, open redirects, "issues requiring an uncommon configuration option".
  - An unauthenticated DoS against default configurations may be raised to Moderate.
- **Pre-notification:** about one week before disclosure, the patches go to a vetted list: OS vendors and distributors, plus selected maintainers and large users, case by case. Being a user "is not sufficient reason", and scanning vendors are excluded.
- **Advance public announcement:** about one week ahead, `django-announce` gets "the date and approximate time of the upcoming security release, as well as the severity of the issues", with no details. Its stated purpose is to let organizations plan staff for the upgrade.
  - 2026 notices: Oct 27 for Nov 3 at about 15:30 UTC; Jul 28 for Aug 4; and so on ([django-announce](https://groups.google.com/g/django-announce)).
  - I couldn't read the full Oct 27 notice text, so I haven't confirmed it listed severities.
- **Cadence:** nine security releases so far in 2026 (Feb 3, Mar 3, Apr 7, May 5, Jun 3, Jul 7, Aug 4, Oct 6, Nov 3), nearly always on the first Tuesday ([django-announce](https://groups.google.com/g/django-announce)). A 7-day cooldown therefore delays an LTS patch by about a week, roughly once a month.
- **What a release contains:**
  - Patches go to the two newest release series plus the LTS.
  - On disclosure day, Django publishes to PyPI, pushes a git tag, posts on the weblog and emails oss-security.
  - The timeline "may be shortened considerably" if exploitation is known.
  - The [5.2.19 notes](https://docs.djangoproject.com/en/5.2/releases/5.2.19/) contain only the five CVEs, so in practice LTS patch releases are security-only. The policy page doesn't promise that.
- **Live example, 5.2.19:**
  - Contents: 1 moderate (CVE-2026-111362, SSRF via a GeoJSON `crs`, GIS only) and 4 low. One low, the `Vary` cache-key fix, changes cache keys ([weblog](https://www.djangoproject.com/weblog/2026/nov/03/security-releases/)).
  - Uploaded to PyPI at **2026-11-03T15:22:03Z** (PyPI JSON), so it clears a 7-day cooldown at **2026-11-10T15:22Z**.
  - The [August release](https://www.djangoproject.com/weblog/2026/aug/04/security-releases/) (5.2.17) carried a **High**: CVE-2026-15307, file writes and SSRF via spatial lookups. That is also GIS.
- **Does the pre-announcement help?** Yes. Seven days ahead you know the date, the time and (per the policy) the severity. That gives time to line up the user's approval and draft the exception before release day, so the exception decision becomes a scheduled event rather than an incident.

## 3. Tooling for exceptions and fast-tracking

**uv**

**Settings** ([settings reference](https://docs.astral.sh/uv/reference/settings/), [resolution docs](https://docs.astral.sh/uv/concepts/resolution/))
- `exclude-newer` accepts an RFC 3339 timestamp, a friendly duration (`"7 days"`, `"1 week"`) or an ISO 8601 duration (`"P7D"`). It compares against each file's *upload time*. Months and years aren't allowed, and `false` disables it.
- `exclude-newer-package = { pkg = "<timestamp|duration|false>" }` overrides the global and per-index values. `false` exempts the package entirely.

**How the lockfile records it (tested)**
- `uv.lock` stores `[options] exclude-newer-span = "P7D"`.
  - A relative per-package value is stored as `django = { timestamp = "0001-01-01T00:00:00Z", span = "P1D" }`.
  - An absolute one is stored as `django = "2026-11-03T16:00:00Z"`.
- The docs say the computed timestamp goes into the lock. In 0.13.6 it records the *span* instead.
- Adding the exception alone doesn't upgrade anything. You need `uv lock --upgrade-package django`.

**What happens when you remove it (tested)**
- If you remove the exception while the release is still inside the window, `uv lock --check` fails and `uv lock` **downgrades** (`Updated django v5.2.19 -> v5.2.18`).
- So the removal date must fall after upload + 7 days.

**An absolute cutoff is tighter than a relative one (tested)**
- `django = "2026-11-03T16:00:00Z"` admits 5.2.19 (uploaded 15:22) but nothing uploaded later.
- `django = "1 day"` keeps sliding, so a rogue 5.2.20 would be admitted after a day.
- Moving the cutoff to 15:00 drops back to 5.2.18.

**No vulnerability-aware override**
- uv has nothing that exempts a version which fixes an advisory. There's nothing in the docs or the [changelog](https://github.com/astral-sh/uv/blob/main/CHANGELOG.md), and critics call this the main gap ([Savio](https://alexsavio.github.io/dependency-cooldown-considered-harmful.html)).
- uv does ship an experimental `uv audit`, which queries OSV and supports `--ignore-until-fixed` (`uv help audit`).

**pip, pnpm, Dependabot, Renovate**
- **pip:**
  - `--uploaded-prior-to` accepts an ISO 8601 datetime or `P<n>D`, and reads env `PIP_UPLOADED_PRIOR_TO` ([pip docs v26.3](https://pip.pypa.io/en/stable/cli/pip_install/)). Relative durations arrived in 26.1 ([Willison](https://simonwillison.net/tags/dependency-cooldowns/)).
  - There is **no per-package override**. This repo doesn't use pip anyway.
- **pnpm** ([dependency-resolution settings](https://pnpm.io/settings/dependency-resolution)):
  - `minimumReleaseAge` is in minutes (default `1440`).
  - `minimumReleaseAgeExclude` takes names, scopes (`@org/*`) or exact versions (`nx@21.6.5`, `webpack@4.47.0 || 5.102.1`).
  - `minimumReleaseAgeStrict` defaults to true only when the age is set explicitly. Otherwise pnpm silently falls back to a younger version.
  - **On this machine `pnpm config get minimumReleaseAge` returns `undefined` (pnpm 12.16.1).** That means the built-in non-strict 1 day applies, not 7.
- **Dependabot** ([options reference](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference)):
  - `cooldown:` takes `default-days` (default 3), `semver-major/minor/patch-days`, and `include`/`exclude` (up to 150 entries each, `exclude` wins).
  - It is "only available for *version* updates, not *security* updates", so security PRs bypass it by default.
  - For pnpm and Yarn, Dependabot passes `minimumReleaseAge=0` on security PRs *(secondary, Nesbitt)*.
  - Its uv updater has no code referencing `exclude-newer` ([dependabot-core](https://github.com/dependabot/dependabot-core/tree/main/uv)). My untested inference is that a security PR's `uv lock` would still be held back by `pyproject.toml`.
  - The uv docs recommend matching Dependabot's cooldown to `exclude-newer` ([uv/Dependabot](https://docs.astral.sh/uv/guides/integration/dependabot/)).
- **Renovate** ([config options](https://docs.renovatebot.com/configuration-options/)):
  - `minimumReleaseAge` can't read uv's setting, so you mirror it by hand ([uv/Renovate](https://docs.astral.sh/uv/guides/integration/renovate/)).
  - The built-in `vulnerabilityAlerts` default sets `minimumReleaseAge: null` and `prCreation: immediate` ([options source](https://github.com/renovatebot/renovate/blob/main/lib/config/options/index.ts)). So security PRs skip the cooldown, but only for GitHub alerts or `osvVulnerabilityAlerts`.

**Detecting a held-back fix: the advisory feeds lag for Django (tested 2026-11-09)**
- The GHSAs for the Nov 3 CVEs (e.g. [GHSA-gmp6-3w93-2w6x](https://github.com/advisories/GHSA-gmp6-3w93-2w6x)) and the Oct 6 CVEs (GHSA-76g2-x83x-73r7, GHSA-x869-hccf-fv7r) are all **`unreviewed`, with an empty `vulnerabilities` list**.
- OSV has bare `CVE-*` records with no PyPI range.
- An OSV query for `django==5.2.17` or `5.2.18` returns `{}`.
- `uv audit` on a lock with 5.2.18 printed "Found no known vulnerabilities". On 5.2.16 it flagged the reviewed August advisories.
- pip-audit queries the same OSV/PyPI data, so I expect the same gap there (inferred, not run).
- Result: Dependabot security updates, Renovate `vulnerabilityAlerts` and audits all miss Django fixes for weeks. **`django-announce` and the weblog feed are the reliable trigger.**

## 4. Community practice

- **Woodruff:**
  - "Cooldowns are a *policy*, and all policies have escape hatches." The obvious exemption is security updates.
  - First-party, data-only and trusted dependencies are "reasonable" exemptions too.
  - Bypasses should be "minimal by default", so pick the *lowest* fixing version ([cooldowns redux](https://blog.yossarian.net/2025/12/13/cooldowns-redux)).
- **Semgrep's org-wide rollout:**
  - Uses `exclude-newer = "1 week"`, with an agent-driven rollout and `uv lock --check` in CI.
  - Internal indexes are exempt. "Allowing devs to manage their own exclusions is fine". There's no formal approval step ([Semgrep](https://semgrep.dev/blog/2026/rolling-out-dependency-cooldowns-org-wide)).
- **PyPI / PSF:**
  - Recommends a global `P3D`, which "should be paired with a vulnerability scanning strategy" so security fixes don't wait.
  - Promotes trusted publishing and attestations so users can spot releases that didn't come from the normal workflow ([incident report](https://blog.pypi.org/posts/2026-04-02-incident-report-litellm-telnyx-supply-chain-attack/)).
  - Adoption: over 20% of uploads came via trusted publishing and 17% carried attestations in 2025 ([2025 review](https://blog.pypi.org/posts/2025-12-31-pypi-2025-in-review)).
  - Seth Larson asked for a global relative setting *(secondary, Nesbitt)*.
- **Simon Willison:** endorses cooldowns, and for urgent patches says to watch advisories and release notes rather than upgrading blindly ([tag page](https://simonwillison.net/tags/dependency-cooldowns/)).
- **Andrew Nesbitt:** surveys exception designs across tools ([Nesbitt](https://nesbitt.io/2026/03/04/package-managers-need-to-cool-down.html)):
  - Hex lifts the cooldown automatically when a locked version has an advisory.
  - Bundler uses `--cooldown 0`.
  - Cargo opts in to a specific version and records it in the lockfile, which is the closest analogue to an absolute uv cutoff.
- **Dissent:**
  - Cooldowns "conflate novelty with risk" and clash with auditors.
  - The proposed alternative is an advisory-aware resolver, a cooldown on additions only, or canary rollouts ([Savio](https://alexsavio.github.io/dependency-cooldown-considered-harmful.html)).
- **Verifying a release: Django doesn't use trusted publishing or attestations.**
  - PyPI's integrity API returns "No provenance available" for both 5.2.19 files, and the Simple API shows `provenance: null` for every 5.2.x and 6.1.x file.
  - Django instead publishes a PGP-signed checksum file from its release manager (key `131403F4D16D8DC7`) ([5.2.19 checksums](https://www.djangoproject.com/m/pgp/Django-5.2.19.checksum.txt)).
  - Its SHA256 values **match** the PyPI JSON digests (tested). It names the tag commit `060cd4ad…`, and the `5.2.19` tag is a signed tag that GitHub reports as `verified: true` pointing at that commit (tested via the GitHub API).
  - I couldn't verify the PGP signature itself, because gpg isn't installed.
- **Mitigations while waiting:**
  - Use the advisory's own workarounds. For 5.2.19: integer SRIDs for untrusted input, GDAL ≥ 3.9, an allow-list on older GDAL. For 5.2.17: validate spatial lookup input.
  - All of these apply only to GeoDjango users.
  - A WAF rule is rarely practical for ORM or GIS bugs.
- I found no Django Forum thread or DSF guidance specific to cooldowns.

## 5. Recommended policy for this project

**Decisions**
- **Keep `exclude-newer = "7 days"`.**
  - PyPI's slowest takedown was 4 days and Kong's window was 10, so 3 days leaves real tail risk.
  - Django's pre-announced, monthly releases make a fast lane cheap to run.
  - No Django CVE has been in KEV.
- **No standing shorter cooldown for Django.** It has no trusted publishing or attestations, and a standing exception would also admit an unannounced rogue release. Make each exception specific to one verified release.
- **Fix pnpm separately:**
  - Set `minimumReleaseAge: 10080` explicitly in `pnpm-workspace.yaml`. That also makes it strict.
  - Exempt only exact versions: `minimumReleaseAgeExclude: ["vite@<x.y.z>"]`.
  - Mirror the setting in any Dependabot or Renovate config.

**Checklist when a security release lands inside the cooldown**

1. **Watch the right feed.**
   - Subscribe to `django-announce` and the weblog. On a "Notice of upcoming…" email, record the date and severity, and tell the user it's coming.
   - For other packages, run `uv audit` (in each project) and check GHSA. Don't count on them for Django (§3).
2. **Triage on release day** by reading the advisory. Take the **fast lane** only if one of these holds:
   - (a) the severity is **High**;
   - (b) it is **Moderate** *and* the affected feature is used and reachable by untrusted input (grep for the module or setting);
   - (c) there is known exploitation (a KEV entry, or Django shortening its timeline).
   - Otherwise **wait** for the cooldown, which is at most 7 days, and apply any workaround from the advisory.
   - Example: 5.2.19 is Moderate and GIS-only. This repo has no GeoDjango, so **wait**. It clears 2026-11-10T15:22Z.
3. **Get approval.** The agent proposes the exception with its triage reasoning. **The user approves it.** The agent never approves its own exception.
4. **Verify the release.**
   - The PyPI upload time matches the announced window (`curl -s https://pypi.org/pypi/django/<ver>/json`).
   - The PyPI SHA256 equals the value in `Django-<ver>.checksum.txt`, and `gpg --verify` passes.
   - The tag is signed and its commit matches the checksum file.
   - No other Django version has been uploaded since.
   - Optionally, diff the extracted sdist against `git archive <tag>`.
5. **Change the config in every affected project** (main service, auth service, shared library). Use an absolute cutoff a few minutes after the verified upload:
   ```toml
   [tool.uv]
   exclude-newer = "7 days"
   # SECURITY EXCEPTION: Django 5.2.19 (CVE-2026-111362 moderate + 4 low), uploaded 2026-11-03T15:22Z.
   # Approved by <user> 2026-11-04. Verified: signed checksums + signed tag 5.2.19 -> 060cd4ad.
   # Admits uploads up to 16:00Z only. REMOVE ON OR AFTER 2026-11-11 (upload + 7 days).
   exclude-newer-package = { django = "2026-11-03T16:00:00Z" }
   ```
6. **Lock and test.**
   - Run `uv lock --upgrade-package django`, and check that the `uv.lock` diff changes only Django and the `[options.exclude-newer-package]` table.
   - Then run `uv sync --locked`, the tests, and `uv run manage.py check --deploy`.
7. **Remove the exception** on or after the removal date.
   - Delete the line, run `uv lock`, and confirm the Django version **didn't change**. A downgrade means the exception was removed too early.
   - Run `uv lock --check`.
8. **Log it** in the commit message or PR body:
   - the CVE IDs and severity, and why the project is or isn't exposed;
   - who approved it;
   - the verification evidence (hashes, tag commit);
   - the cutoff and removal date;
   - a link to the removal commit when it lands.
