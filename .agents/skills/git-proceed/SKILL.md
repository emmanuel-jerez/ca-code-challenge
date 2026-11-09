---
name: git-proceed
description: "Use when the user invokes git-proceed, requests complete branch-to-PR/MR delivery, or asks for bounded commit or push steps that still need isolated-worktree, verification, and hook-safety rules without authorizing unrequested publication."
---

# Git Proceed

Run a complete, language-agnostic repository change flow from branch/worktree
setup through PR/MR creation, review, and, for a ready GitLab MR, merge.

## Activation

When the user explicitly says `git-proceed` — in any agent's skill-invocation
syntax or in plain prose — treat that as a request to run this workflow, even if this skill
was not listed in the session's available skills. Start by inspecting repository
state and preparing an isolated task worktree before making implementation edits.

Also use this workflow when the user clearly asks for the complete delivery
path, such as “open the merge request,” “branch and PR it,” or “ship this change
end to end.” When the user asks for only bounded steps such as “commit and push
this,” apply the relevant preparation, verification, commit, and push rules but
stop there. Do not infer permission to create a PR/MR, launch review, or perform
other external actions the user did not request. Within the complete delivery
path, merging a ready GitLab MR is implicitly approved; step 15 covers it.

If `git-proceed` is on `PATH` in `~/.local/bin`, it is only a discovery shim for
this skill. Do not treat it as an autonomous implementation command.

If the user gives no task beyond `git-proceed`, infer the task from the current
branch name, dirty files, and recent conversation when possible. If the task
cannot be inferred safely, ask one concise clarification question after the
repository-state inspection. Do not continue implementation in the primary clone
just because the request was terse.

## Ground Rules

- Follow the repo's `AGENTS.md` and local project instructions first.
- Keep the workflow language- and framework-agnostic; choose verification from
  the project itself.
- Do not use `git commit --no-verify`, `git commit -n`, or any equivalent that
  bypasses hooks.
- Preserve unrelated user changes.
- Do all implementation work in an isolated task worktree unless the current
  checkout is already a suitable task worktree.
- A primary clone with a normal project path, even on a task-named branch, is
  not automatically a suitable task worktree. Prefer creating a sibling worktree
  from the primary clone unless `git worktree list` shows the current checkout
  is already an isolated task worktree.
- After creating or entering a task worktree, make dependencies ready before any
  verification, hook, script, or commit step. Fresh Git worktrees do not include
  generated dependency directories such as `node_modules`, so inspect the
  project manifest and lockfile, then run the project-native frozen/safe install
  command when dependencies are missing or local package executables are
  unavailable.
- Delegate host-specific MR details to the relevant skill or repo docs:
  - GitLab MR creation: use the `gitlab-mr` skill.
  - GitHub PR creation: use the `github-pr` skill.

## Scope Contract

A PR/MR contains the requested outcome and the work that outcome makes
necessary. It is not a container for every worthwhile improvement found along
the way.

- Before adding adjacent work, ask whether removing it would still leave the
  requested outcome complete. If yes, record it as a follow-up instead.
- Add guards or assertions when they are needed to deliver or prove the
  requested behavior, not merely because the branch makes them convenient.
- Write tests as the `tdd` skill describes: only at seams chosen up front, one
  red-green slice at a time. Refactoring belongs to review, not to the
  implementation loop.
- Keep an unrelated repository or tooling repair as small and separate as
  practical when it outlives the requested change.
- Apply the same boundary to reviewer suggestions. A useful idea can be real
  without belonging in the current PR/MR.
- The lesson an audit or review fix records under the shared
  `Lessons from audits and reviews` instructions is part of that fix, not
  adjacent work.

When the task comes from a saved plan, treat unverified implementation details
as leads. Confirm paths, APIs, names, assumptions, and external behavior against
the current repository and authoritative documentation before relying on them.
Correct stale plan facts instead of bending the implementation to match them.

## Parallel Work

Run independent work in parallel by default when it is safe, within the
runner's concurrency limits. Two steps are independent when neither needs the
other's output and neither writes anything the other reads or writes, such as
files, caches, ports, databases, or Git state.

- Safe to run in parallel:
  - read-only inspection after `git fetch` finishes, such as the step 1 queries
    for worktrees, remotes, dirty files, open PRs/MRs, and remote branches
  - reading code, docs, and plans while dependencies install
  - verification commands that write nothing another command uses, such as a
    lint check and a type check run without `--fix`; run commands that share
    caches, build output, ports, or databases in sequence
  - independent reviewers of the same source tip, such as the `code-review`
    skill's Standards and Spec reviews
- Keep in order:
  - edits, formatters, code generators, and anything else that writes to the
    task worktree
  - Git operations that change the index, refs, or a worktree, including refs
    that worktrees of one repository share
  - the publication chain, steps 7 through 16: each review round still waits
    for the previous round's fixes, commit, and push
  - writes to external services
  - any step that needs an earlier step's result
- Implement the change in one sequence. Do not split the implementation across
  parallel agents or worktrees unless the user asks for it.
- When it is unclear whether steps are independent, or the runner cannot run
  steps in parallel, run them in sequence.
- Collect every parallel result before acting on any of them. A failed parallel
  check fails its step exactly as a sequential one would.

## Workflow

1. Inspect repository state:
   - current path, branch, worktree list, remotes, and dirty files
   - default base branch and forge host
   - open PRs/MRs and remote branches that match the requested objective or
     selected plan item, not only the current branch; reuse a matching source
     branch and update its existing PR/MR instead of creating a duplicate
2. Derive the branch name from the task:
   - format: `<type>/<kebab-case-slug>`
   - common types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`
3. Prepare the task worktree from the primary clone:
   - run `git fetch`
   - choose a sibling path outside the primary checkout, for example
     `../<repo-name>-<branch-slug>`
   - new branch: `git worktree add <path> -b <branch-name> <base-ref>`
   - existing branch: `git worktree add <path> <branch-name>`
   - `cd` into the worktree before implementation
   - if the primary checkout has dirty files needed for the task, move them
     intentionally into the task worktree with a safe method such as a patch,
     stash, or file copy, preserving unrelated user changes
4. Make the task worktree dependency-ready:
   - inspect package/project manifests, lockfiles, and repo instructions for the
     required package manager and install command
   - if dependencies are missing, or if local package executables needed by
     scripts/hooks cannot run, install them with the repo's frozen/safe command
     before implementation verification or commits
   - examples: `uv sync --locked` in each Python project (both Django services
     and the shared library), `pnpm install --frozen-lockfile` for the
     frontend, or the project-specific equivalent
   - agents do not run `pip install`; Python projects follow the `uv-only`
     skill
   - agents do not run npm installs or npx; a project with only
     `package-lock.json` follows the `pnpm-only` skill: stop and report rather
     than falling back to `npm ci`
   - do not bypass hooks just because dependencies were missing; fix dependency
     readiness first, then let hooks run normally
5. Implement the requested change using the repo's existing patterns and the
   Scope Contract above. Record useful out-of-scope work instead of growing the
   branch.
6. Verify with the most relevant project-native command available:
   - tests, type checks, lint, format checks, build, or a focused smoke test
   - explain any verification that cannot be run
   - exercise the bounded success and failure behavior implied by the change
     before asking a reviewer to discover missing deterministic cases
7. If the work implements an item from a saved execution plan, update the plan
   after implementation and verification but before publication:
   - record verified facts and mark the delivered item complete
   - identify the next remaining item without starting it
   - keep post-merge or human-owned work as explicit follow-up state
   - follow the repository's convention for updating, archiving, or deleting a
     completed plan; do not invent a lifecycle when the repo defines none
8. Stabilize the intended change before committing:
   - inspect the working diff and existing branch commits for scope, accidental
     files, secrets, generated artifacts, migrations, and user-facing
     documentation
   - finish deterministic validation and capture the commands actually run
   - load and follow `mr-pr-description`, then draft the complete PR/MR
     title and description from the stable diff
   - prepare the smallest coherent publication batch; do not create
     approval-only, review-request, or review-result commits
9. Make logical commits:
   - group related changes into atomic commits
   - stage only the files for each commit
   - use present-tense commit messages
   - let hooks run
10. Re-check the committed publication after hooks and before the first push:
    - confirm the worktree is clean or intentionally account for every remaining
      change
    - inspect the committed diff and ensure the recorded verification still
      applies to the exact source tip being published
11. Push with upstream tracking:
   - `git push -u origin HEAD`
12. Create or update the PR/MR:
   - load and follow `mr-pr-description` before drafting the title or
     description (see PR/MR Record), whichever forge path you use
   - follow the relevant forge skill and repository authentication guidance
   - when credentials come from Bitwarden Secrets Manager, read and follow the
     `bws-env` skill rather than reproducing an incomplete credential command
     here
   - GitHub: use `gh pr create` or `gh pr edit` when available, or the
     `github-pr` skill and CLI
   - GitLab: use the `gitlab-mr` skill and the local `gitlab-mr` CLI
   - derive the title from the complete final description, so it covers the
     full reviewer-relevant scope rather than only the latest change
   - include summary and verification in the description
   - if commits change the scope of an existing PR/MR, sync both the title and
     description
13. Finish any unavoidable post-creation self-link or provenance update in one
    coherent batch. Start independent review only after the source tip and
    PR/MR description are stable.
14. Run the repository's post-PR/MR review loop when it has one:
    - look for a review-loop workflow in the repo's agent guidance, for example
      `.agents/skills/*/workflows/mr-review-loop.md`
    - follow that workflow's reviews, issue fixes, redesigns, narrowings,
      limits, and closing staleness cleanup in full
    - with no such workflow, run a fresh independent review with the
      `code-review` skill, fix only its issues, verify, commit, push, update
      the description when scope changed, and review again as Review
      Boundaries describes
    - record each issue fix's lesson as the shared
      `Lessons from audits and reviews` instructions describe, plus anything
      the repository's workflow adds
    - stop when a review reports no issues, the workflow's limits end the loop,
      or the current runner cannot launch independent reviewers
15. Merge a ready GitLab MR:
    - approval is implicit; do not ask first, and skip the merge only when
      the user, the repository's agent guidance, or the MR explicitly says not
      to merge
    - merge after step 14 has fully finished, including any closing cleanup
      that commits after the last review
    - the `gitlab-mr` skill's Merging checklist decides whether the MR is
      ready; follow it, then run `gitlab-mr merge` with the pushed source
      commit's SHA
    - leave GitHub PRs for the user unless they ask you to merge
16. Clean up the temporary worktree:
    - only after the PR/MR exists, the review loop finished or stopped at one
      of its limits, and any merge from step 15 finished
    - remove it from the primary clone, not from inside the worktree path
    - use `git worktree remove <path>`
    - use `git worktree remove --force <path>` only when intentionally dropping
      uncommitted work in that worktree
    - optionally run `git worktree prune` if anything was removed manually
17. Hand the PR/MR back with explicit `Before merge:` and `After merge:`
    instructions as described below, and say whether it was merged.

## PR/MR Record

The title and description are the durable explanation for reviewers and people
who will not read the diff.

- Let the repository's required template or description skill define the exact
  headings and format. You must load and follow the `mr-pr-description`
  skill before drafting or updating any title or description; this bootstrap
  installs it.
- Make the title cover the complete reviewer-relevant scope, not merely the
  latest commit.
- Describe the requested outcome, why it matters, what is observably different,
  who or what is affected, and the relevant failure behavior or limits.
- Describe behavior and decisions rather than narrating files, symbols, or
  commit history.
- List only verification that actually ran, and say what each result proves.
- Record material risks, migrations, configuration changes, manual rollout
  steps, deferred work, and judgment calls where a reviewer will retain them.
- Name the agent guidance added or changed under the shared
  `Lessons from audits and reviews` instructions.
- Explain material scope decisions and corrections to stale plan assumptions so
  reviewers can tell why adjacent work is deliberately absent.

## Review Boundaries

Independent review uses the `code-review` skill, with the PR/MR base branch as
the fixed point, the spec found by that skill's own lookup order, and the
repository's agent guidance as standards sources. The PR/MR description is the
implementer's account of the change, not the spec. A repository review
workflow can add inputs and safety limits but does not replace that skill's
review.

- Treat only issues as actionable: a bug, a complete contradiction, or a
  failure of a requirement, including a request carried out only partly.
  Apart from stale documentation, handled below, record everything else,
  including baseline smells, as a note in the PR/MR description rather than
  acting on it.
- Defer documentation that still describes pre-change behavior until review
  ends, then clean it up once against the final state. Stale text that breaks
  a check, script, or test is a bug; fix it at once.
- A finding whose fix would undo an earlier fix, or reverse a recorded
  decision, is an unclear requirement: record both readings in the PR/MR
  description and do not change the text again.
- Do not stop for human input. When a finding requires a product,
  architecture, scope, or risk-acceptance decision, make it with the
  repository's conflict policy, preferring least privilege and recoverable
  behavior, and record the decision and why in the PR/MR description.
- Fix the underlying bounded concern class, record its lesson in the same
  commit as the shared `Lessons from audits and reviews` instructions describe,
  verify it, commit, push, update the PR/MR record when needed, and use a
  fresh reviewer for the new source tip.
- Follow repository-specific iteration and convergence limits. If none exist,
  stop rather than repeatedly patching the same mechanism or materially growing
  the PR/MR beyond its objective.

## Existing PR/MR Follow-ups

If the branch already has an open GitHub PR or GitLab MR, treat any additional
requested work on that branch as an update to the existing PR/MR.

After implementing, verifying, committing, and pushing follow-up changes:

- Re-read the existing PR/MR title and description.
- Update the description when the new commits change scope, behavior,
  verification, risks, screenshots, migration notes, or user-facing details.
- Re-check the title against the full revised description and update it when it
  no longer encompasses the complete scope.
- Preserve useful existing description content; revise it instead of replacing it
  blindly.
- Add or update the verification/test plan to include commands run for the
  follow-up changes.
- Do not create a second PR/MR for the same branch unless the user explicitly
  asks for one.
- Mention in the final response whether the existing PR/MR description was
  updated or why no description update was needed.

## Merge Handoff

Whenever this workflow creates or updates a PR/MR, the final response must tell
the user what a person still needs to do. Always include both labels:

- `Before merge:` Actions required in addition to normal review and merge, or
  `No additional action required.` When this workflow merged the MR, write
  `Merged by the agent.` instead.
- `After merge:` Actions required after merge, or
  `No additional action required.`

Derive the handoff from the complete change and repository workflow. Check for
dependent PRs/MRs, approvals, manual validation or pipeline jobs, configuration
or secret changes, migrations, deployment sequencing, monitoring, cleanup, and
follow-up work. Separate required actions from optional suggestions, state who
owns conditional actions, and do not present automatic CI or deployment as
user work. Put material merge-time or post-merge actions in the PR/MR
description too.

## User Updates

Keep the user informed at the decision points: branch/worktree choice,
verification result, commit grouping, push result, PR/MR URL, merge result or
the reason for not merging, and cleanup result. The final update also reports
the review rounds, redesigns, and reviews, reviewer-driven fixes, delegated
follow-ups, decisions made under the conflict policy, the guidance lessons
recorded, unclear requirements, any persistent concern, what the staleness
cleanup changed, and the Merge Handoff.
