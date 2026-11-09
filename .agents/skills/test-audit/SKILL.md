---
name: test-audit
description: "Use when auditing, reviewing, or pruning tests for low-value, implementation-coupled, or duplicative cases and the test-only hooks they keep alive. When writing tests, load tdd first and use this as its value check."
---

# Test Audit

Three modes, one value bar. The authoring check adds a value gate to every new
or changed test; the `tdd` skill still owns how tests are written. Audit mode
runs focused sweeps of tests that re-assert source, duplicate stronger proof,
couple behavior to implementation, or keep test-only hooks alive in production
code. Campaign mode prunes the whole test surface of one subsystem. When
authorized to publish, deliver broad audits as separate coherent follow-up
PRs/MRs; optimize for confidence, not deletion count.

Read the repository's `AGENTS.md` and other agent guidance first. Where this
skill and the `tdd` skill cover the same step of writing a test, `tdd` wins.

## Terms

- A **seam** is the place a test observes behavior through, as `tdd` and
  `codebase-design` define it. New tests go only at the seams `tdd` has you
  write down up front.
- A **test-only hook** is an export, flag, wrapper, global, or injection point
  that exists only so a test can reach past a seam; no production caller uses
  it. These are not test-only hooks, even when only tests use them: an injected
  dependency that production callers pass, such as the external client `tdd`'s
  mocking guidance injects; a test adapter at a real port, which
  `codebase-design` counts as the second adapter that makes the seam real; and
  an internal seam a module's own tests use without exposing it through the
  interface.

## Authoring check

Use this alongside `tdd` whenever a test is added or changed. Before adding a
test, answer four questions; a missing answer means do not add it yet:

1. What observable behavior, invariant, or independent contract does it
   protect?
2. What credible regression makes it fail?
3. Why does existing coverage not already catch that failure? Each contract has
   one primary test at the strongest seam; another layer needs its own distinct
   risk, such as a transport or lifecycle failure the primary test cannot
   reach. Prefer adding a case to an existing table-driven test or shared
   fixture over writing a near-duplicate test.
4. Does it need a test-only hook? If yes, test at a seam on `tdd`'s list
   instead.

Then check the test against every [junk pattern](#junk-patterns); a match fails
the check unless the [retention bar](#retention-bar) names the contract it
independently guards and the test still passes `tdd`'s anti-pattern checks. A
test that would break under behavior-preserving refactoring is asserting
implementation, not behavior; write it at a seam on `tdd`'s list instead.

Duplicated test setup you notice while writing is review work, not part of the
red-green loop; record it for the review stage, as `tdd` describes.

Bug regression tests must fail on the pre-fix code for the intended reason and
pass after the fix at the owning seam. A regression test that never
demonstrably failed proves the mock, not the fix. One regression test at the
owning seam covers the bug; do not replay the same scenario at every layer it
crosses. When no correct seam exists, follow `diagnosing-bugs` and record the
missing seam instead of adding a shallow test.

## Junk patterns

The shared checklist for every mode: the authoring check rejects a new test
that matches one, and audits hunt for existing tests that do.

- assertion-free coverage probes;
- self-comparisons and identity copiers;
- copied fixtures, inventories, manifests, or export lists;
- exact source, import, or string greps;
- private predicate or call-shape tests duplicated at real seams;
- duplicate invocations of the same contract;
- per-caller replays of a shared helper's own tests;
- tests whose only purpose is preserving test-only exports, globals, or
  wrappers;
- dead production code whose only callers are tests;
- expected values produced by the helper or renderer under test;
- mocks that implement the asserted behavior, or one identical mock standing in
  for different APIs;
- fixtures that supply the acknowledgement, approval, or callback ordering the
  code under test should produce, or persistence asserted against a store the path
  never writes;
- capability tests that restate declared flags instead of exercising the
  delivery or acknowledgement the flag promises;
- negative controls that pass for an unrelated reason, such as a denial from a
  different guard or a rejection the production path never reaches;
- names or fixtures that promise more than the input exercises, such as a
  "clears the cache" test that never checks the cache was cleared.

## Value bar

Tests justify their maintenance cost by protecting behavior, a credible
regression, or an independently meaningful contract. In an audit, an existing
test that must change for behavior-preserving source reorganization is suspect,
not automatically deletable; the authoring check still rejects new ones.

Before judging a candidate, read the complete test and the production code it
covers, its entry point, callers, callees, sibling implementations, overlapping
tests, CI routing, and relevant history. When the test claims
dependency-backed behavior, inspect the dependency source or types directly.

## Audit mode

Keep discovery read-only and report evidence before editing. For broad scope,
split discovery into parallel lanes by the repository's own layout, for example
core libraries, plugins or extensions, apps and UI, scripts and tooling, plus
one cross-cutting sweep for the [junk patterns](#junk-patterns).

Outside campaign mode, prefer a few high-confidence candidates over a large
speculative inventory.

## Campaign mode

A campaign prunes one whole subsystem: every test file a module, package, or
plugin owns. Inventory those files first, then record
[candidate evidence](#candidate-evidence) for each candidate before editing.
The value bar, retention bar, and evidence requirements stay the same; a
campaign is a wider inventory, not a lower bar. Deliver it as one or more
coherent PRs/MRs, each scoped to part of the subsystem. Record in each
PR/MR description which test files the campaign has checked so far and what
remains; the campaign ends when every inventoried file has been checked.

## Retention bar

Keep a test when it independently enforces a public API, plugin or extension
interface, protocol, config, migration, storage, security, platform, default,
exact prompt text, generated code, package, release, or architecture contract. Also keep:

- call ordering when order is observable behavior;
- regressions with a credible failure mode;
- source inspection when it is the cheapest independent guard: it fails when
  the contract changes (the user-facing key, byte, or path) and survives an
  identifier-only refactor;
- a retained test that fails on the baseline: treat it as a possible product
  bug and reproduce it with `diagnosing-bugs`. Do not delete the test; fix the
  code in a separate PR/MR, or record the bug as a follow-up.

Static or slow is not a deletion reason. A test that resembles implementation
may still be the independent contract; prove otherwise before removing it.

## Candidate evidence

Record every field below before editing. A missing field means the candidate is
not ready for deletion:

- exact test name and location;
- what failure it can actually detect;
- non-test callers of the covered production code or test-only hook;
- stronger remaining proof at the owning seam, or why no proof is needed;
- relevant history and the reason the test or hook exists;
- production or test-support deletion unlocked;
- risk and the focused validation command.

## Edit shape

Choose one coherent batch at one owning seam. Delete obsolete test-only
exports, globals, wrappers, and dead production paths instead of preserving
aliases. Move retained regressions to the test that owns the contract.
Consolidate repeated package or dependency assertions into one generic
contract.

Prefer net-negative production LOC. Do not add replacement tests that restate
the same implementation, and do not convert uncertain candidates into cleanup
to increase deletion counts.

## Validation

Do not edit source or tests while a watch-mode test runner is running in the
checkout. Use the repository's own test and check commands.

1. Run the smallest tests for the changed code and its siblings.
2. For removed source greps or assertions on planned output, run the
   executable script or dry run that owns the real contract.
3. Run the repository's formatter on the changed files, then
   `git diff --check`.
4. Run the changed-file or full check the repository requires.
5. Inspect `git diff --numstat`; report production and tooling separately from
   tests and test support.

## Landing and continuation

Commit, push, or open a PR/MR only when authorized, and then follow
`git-proceed`, which routes review to `code-review` and descriptions to
`mr-pr-description`. Land one coherent PR/MR at a time; after it merges,
refresh from the default branch and rerun read-only discovery for the next
high-confidence batch.

## Handoff

Report:

- root cause and removed low-value categories;
- production code simplifications;
- retained false positives and why they remain valuable;
- focused and full checks actually run;
- production versus test LOC;
- PR/MR and merge state;
- lessons recorded or proposed under the shared
  `Lessons from audits and reviews` instructions;
- named follow-ups.
