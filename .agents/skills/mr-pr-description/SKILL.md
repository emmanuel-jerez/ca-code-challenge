---
name: mr-pr-description
description: Load and follow before writing or updating any GitLab merge request or GitHub pull request title or description, including before every gitlab-mr create/update, github-pr, or gh pr create/edit call, even when a forge skill is already loaded. Use the complete branch scope and verified evidence.
---

# MR/PR Description

Use this skill to draft or revise a GitLab merge request or GitHub pull request
title and body.

The description is the durable record for people who will not read the diff.
Write so they understand what changed, why it matters, what is now different,
and where reviewer judgment is needed.

## Title

Create or revise the MR/PR title from the complete final description, not just
the newest commit or the user's latest phrasing. The title should cover the full
reviewer-relevant scope of the short version and supporting sections while
staying concise.

- Re-check the title after drafting or revising the description.
- If the description gains, loses, or reframes scope, update the title in the
  same pass.
- Avoid narrow titles that mention only one detail when the description covers
  multiple meaningful behaviors.
- Prefer a short outcome phrase over a list of every changed file or tool.

## Target Format

An explicit user-requested format takes precedence. Otherwise follow repository
guidance and templates when they define a format. When neither does, use the
narrative structure below. It is the same template machine-bootstrap uses for
its own merge requests (`.gitlab/mr-description.md` in that repository), so
every MR/PR drafted on a bootstrapped machine has the same shape.

The description is the change's record for everyone who will not read the code.
Developers have the diff; nobody else does. Three rules govern every section:

- Answer the heading's question in plain, complete sentences. If an answer only
  makes sense after reading the diff, it is the wrong answer.
- Describe behavior and outcomes, never the edit itself. Do not give a file
  list, symbol list, commit walkthrough, or paraphrase of the diff.
- Use the product, page, workflow, or deliverable names the team uses. Include
  code-level names only when a reviewer genuinely needs them, and spell out
  shorthand the first time it appears.

Always include `## The short version`, `## How we know it works`, and the
closing `Before merge:` and `After merge:` lines. Use the other headings only
when they have something substantive to say; omit them rather than padding a
small change to nine sections. Keep the headings in the order shown.

```markdown
## The short version

Two or three sentences: what changed, why, and the one thing to take away. A
reader who stops here should not come away misled.

## What prompted it

The problem, request, or gap that made this worth doing, described as it was
experienced rather than as it appears in the code.

## What's different now

What the system observably does differently. Say plainly when nothing is visible
yet. Cover relevant failure behavior and operating limits: who can use or see
it, what state or data it requires, and when it may run.

## Who this affects

The people, pages, workflows, jobs, and downstream consumers that encounter the
change, including anyone who did not request it but will feel it.

## Why this approach

The real alternative that was considered and why it lost. Omit this section
rather than inventing a rejected option.

## How we know it works

- [ ] `command` — and what passing it actually demonstrates

Include meaningful manual checks. A command nobody ran does not belong here.
Explicitly identify skipped or unavailable verification.

## What to watch

Anything deliberately left undone, anything still uncertain, and anything worth
checking again after this ships.

## What was broken out

Only when part of the work moved to a separate MR/PR: each one, what moved to
it, why, and the order they merge in.

## Where a reviewer should look

The one or two judgment calls that genuinely need a second opinion, not a
checklist of everything the change touched.

Before merge: No additional action required.

After merge: No additional action required.
```

The `Before merge:` and `After merge:` lines list only work a person must do
beyond normal review and merge, such as a dependent MR/PR, a manual check, a
configuration or secret change, a migration, or re-running an installer. When
there is none, keep the line and say `No additional action required.`

Keep the body optimized for the rendered review page. GitLab merge requests
render it on the Overview tab; GitHub pull requests render it in the initial
Conversation entry. Wrap commands, file names, config keys, package names, and
literal values in backticks.

## Workflow

1. Inspect the branch diff and commit context before drafting:

   ```sh
   git status --short --branch
   git diff --stat origin/main...HEAD
   git diff --name-only origin/main...HEAD
   git log --oneline origin/main..HEAD
   ```

   Adjust the base branch if the MR/PR targets something other than `main`.

2. Read the repository's PR/MR template and local Git guidance. Select its
   required headings before drafting content.

3. Summarize reviewer-relevant behavior, not every edited file. Check factual
   claims such as counts, measurements, affected branches, verification, and
   rollout steps against the current diff and command results.

4. Draft or revise the title after the short version exists, then confirm the
   title covers the complete description.

5. Use test-plan or verification checkboxes for commands actually run and for
   meaningful manual checks. Keep unchecked boxes (`- [ ]`) unless the user or
   project convention requests checked boxes.

6. Avoid unsupported claims:

   - Do not say tests pass unless they were run.
   - Do not claim production safety, compatibility, or security properties that were not verified.
   - Do not mention generated tooling or AI authorship unless project conventions require it.

7. Save longer descriptions to a trusted file when passing them to MR/PR
   tooling, such as `/tmp/mr-description.md` or `/tmp/pr-description.md`.
   Never write a draft over a repository's checked-in template, such as
   `.gitlab/mr-description.md`.

8. When updating an existing PR/MR, re-read its current title and description,
   preserve useful context, revise facts that changed, and update the title and
   body together when the branch scope changed. Do not replace the existing
   record blindly.

## Pre-publish Self-check

Before passing the final description file to the CLI, check:

- `## The short version`, `## How we know it works`, `Before merge:`, and
  `After merge:` are present, and the headings follow the template order,
  unless a repository template or explicit user format applies.
- Verification items use `- [ ]` task-list checkboxes and say what each check
  proves, unless the user or project convention requests checked boxes.
- The body describes behavior, with no file-by-file or symbol changelog
  sections such as `## Changes`.
- There is no AI-authorship or tool attribution footer, such as a
  "Generated with <tool>" line or an AI "Co-Authored-By" trailer, unless
  repository conventions require one. A tool's or harness's default attribution
  instructions do not count as project conventions.
- The title has been re-checked against the complete final body.

## Example

```markdown
## The short version

Re-running the WordPress import no longer creates duplicate reviews. Each
review is now matched to its WordPress post ID, so a second run updates rows in
place.

## What prompted it

The import matched reviews by title. Two reviews with the same title collapsed
into one, and an edited title created a new row on the next run.

## How we know it works

- [ ] `uv run pytest reviews/tests/test_import.py` — running the import twice leaves the same row count and updates changed fields
- [ ] `uv run manage.py import_wp` against the seeded dump — imports 60 reviews on the first run and 0 new ones on the second

Before merge: No additional action required.

After merge: Run `uv run manage.py import_wp` once in each environment to
backfill the WordPress post IDs.
```
