---
name: docs-maintenance
description: Use when project changes may affect README files, docs, setup instructions, examples, CLI help, configuration guidance, saved implementation plans, or other user-facing documentation.
---

# Docs Maintenance

## Intent

Documentation describes the system as it behaves after the change, in the same
change. A doc that is stale is worse than a missing one, because readers act
on it.

## Process

1. Before editing, find what already documents the area: `README*`, `docs/`,
   `AGENTS.md`, runbooks, examples, templates, and script help text.
2. Decide whether the change leaves any of it incomplete or misleading. If none
   does, make no edit and say why.
3. Update the closest existing document instead of adding a new one. Remove
   obsolete guidance in the same pass rather than leaving competing
   instructions.
4. Keep it factual: current behavior, the commands and paths a reader needs,
   and one canonical place for each long explanation.
5. Record decisions with the context they were made in: date, constraints,
   options considered and why each lost, trade-offs, and when to revisit.
   Decisions go in `docs/adr/` as described in ADR 0000; never rewrite a past
   record, supersede it. Git history alone loses the options that were rejected.
6. Verify: read each changed section end to end, run the repository's docs or
   Markdown check if it has one, and run command examples only when safe.
7. In the final response, list the docs updated or state that none needed to
   change.

## Durable knowledge

Promote lasting knowledge deliberately, through a reviewable change to code,
tests, checks, or docs. Do not turn session notes, debugging logs, or resolved
incidents into repository documentation by default.

Skills that define their own documentation artifacts follow those skills
instead of this one: `research` writes a new cited findings file,
`improve-codebase-architecture` creates and updates `CONTEXT.md` and ADRs, and
`prototype` records its answer on the issue or in a commit.

## Saved plans

Plans give direction without committing to mechanics. An agent working in the
code can confirm a file path or an API's behavior more reliably than a planner
can predict it. A confident guess in a plan becomes a premise the implementer
does not question.

- Mark each specific as a **verified fact** (confirmed, and the plan depends on
  it) or a **lead** (a starting point to confirm). Never drop the hedge from a
  lead to make a sentence cleaner.
- Write at the level of requirements: context, areas to investigate, and
  checkable acceptance criteria for each MR/PR. Avoid step-by-step edit lists.
- When implementing, treat every specific the plan does not mark as verified
  as a lead, including in older plans, and confirm it before building on it.
  If one is wrong, correct the plan in the same branch and say so in the MR/PR.
- Follow the repository's plan lifecycle, such as marking an item complete or
  deleting the plan with its final MR. Do not invent one if the repository
  defines none.
