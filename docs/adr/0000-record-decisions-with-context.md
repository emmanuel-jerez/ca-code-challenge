# 0000. Record decisions with the context they were made in

- Status: Accepted
- Date: 2026-11-09

## Context
Humans and AI agents both work in this repo. A bare decision ("use X") invites
re-litigating it, because the reader can't see what was already considered. Git
history keeps the diff but not the reasoning. The challenge also requires a README
section on modeling decisions and AI defaults.

## Options considered
- **README only.** The challenge requires it, but one long section can't hold the
  alternatives for every decision without burying the summary.
- **Git history only** (the `docs-maintenance` skill's earlier default). Rejected: the
  options that lost never reach a commit.
- **Decision records (ADRs), summarized in the README.** Chosen.

## Decision
Every significant decision gets a record in `docs/adr/NNNN-title.md`: status, date,
context and constraints at the time, options considered and why each lost, the
decision, consequences and trade-offs, what would make us revisit it, and sources.
Records are never rewritten to fit later facts. A changed decision gets a new record
that supersedes the old one, and the old one is marked `Superseded by NNNN`. Agent
files (AGENTS.md, skills) state a reason for every rule. README.md summarizes the
records and links to them.

## Consequences
- More writing per decision; in exchange, the reasoning survives and probes on the
  live call have a written answer.
- The `tdd`, `diagnosing-bugs` and `improve-codebase-architecture` skills already look
  in `docs/adr/`.

## Revisit when
The record count makes the index hard to scan, or the format stops being used.
