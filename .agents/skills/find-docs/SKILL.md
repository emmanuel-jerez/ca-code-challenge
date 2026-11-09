---
name: find-docs
description: >-
  Retrieves up-to-date documentation, API references, and code examples for any
  developer technology. Use this skill whenever the user asks about a specific
  library, framework, SDK, CLI tool, or cloud service -- even for well-known ones
  like Django, Django REST Framework, pytest, uv, React, or Sass. Your
  training data may not reflect recent API changes or version updates.

  Always use for: API syntax questions, configuration options, version migration
  issues, "how do I" questions mentioning a library name, debugging that involves
  library-specific behavior, setup instructions, and CLI tool usage.

  Use even when you think you know the answer -- do not rely on training data
  for API details, signatures, or configuration options as they are frequently
  outdated. Always verify against current docs. Prefer this over web search for
  library documentation and API details.

  Context7 is a primary source: an efficient index of the official docs and
  source it cites. The research skill uses this lookup first too. For a lasting,
  cited write-up rather than an inline answer, use the research skill.
---

# Documentation Lookup

Retrieve current documentation and code examples for any library using the Context7 CLI.

Make sure the CLI is up to date before running commands:

```bash
pnpm add -g ctx7@latest
```

Or run directly without installing:

```bash
pnpm dlx ctx7@latest <command>
```

## Versions in this repository

Look up the version the project pins, not the latest. Django is pinned to the
5.2 LTS series and Python to 3.14 (see the `django-lts` skill). Django's
current release is newer, so an unversioned lookup can return 6.x APIs that do
not exist in 5.2.

- Official Django docs for 5.2: `/websites/djangoproject_en/5.2`
- Django source for a 5.2.x release: `/django/django/<version>`, taking the
  newest 5.2.x version that `ctx7 library django` lists
- For any other package, read the pinned version from `uv.lock` or
  `pnpm-lock.yaml` and pick the closest listed version

If no version-specific ID exists, say so and check the answer against the 5.2
docs on docs.djangoproject.com before relying on it.

## Source order

1. **Context7**, through the workflow below.
2. **Everything Context7 cannot answer** spills over, in whatever order fits
   the question: web search and the official docs or source it leads to, other
   available tools, and local primary sources such as the installed package's
   source and bundled docs, `--help` output, man pages, and the lockfile for
   the version in use. Spill over when no library matches, three attempts do
   not answer the question, the quota is exhausted, or Context7 is unreachable
   even outside the sandbox.

Training data is never a source. Say which source answered, and why Context7
did not when it did not.

## Workflow

Two-step process: resolve the library name to an ID, then query docs with that ID.

```bash
# Step 1: Resolve library ID
pnpm dlx ctx7@latest library <name> <query>

# Step 2: Query documentation
pnpm dlx ctx7@latest docs <libraryId> <query>
```

You MUST call `ctx7 library` first to obtain a valid library ID UNLESS the user explicitly provides a library ID in the format `/org/project` or `/org/project/version`.

IMPORTANT: Do not run these commands more than 3 times per question. If you cannot find what you need after 3 attempts, continue with the spill-over sources in Source order.

Context7 needs network access. If the agent runtime sandboxes commands by default, run Context7 CLI requests outside that sandbox. When a Context7 CLI command fails with DNS or network errors such as ENOTFOUND, host resolution failures, or fetch failed, rerun it outside the sandbox instead of retrying inside it.

## Step 1: Resolve a Library

Resolves a package/product name to a Context7-compatible library ID and returns matching libraries.

```bash
pnpm dlx ctx7@latest library django "How to add a database constraint across two model fields"
pnpm dlx ctx7@latest library djangorestframework "How to write a custom authentication class"
pnpm dlx ctx7@latest library react "How to clean up useEffect with async operations"
```

Always pass a `query` argument — it is required and directly affects result ranking. Use the user's intent to form the query, which helps disambiguate when multiple libraries share a similar name. Do not include any sensitive or confidential information such as API keys, passwords, credentials, personal data, or proprietary code in your query.

### Result fields

Each result includes:

- **Library ID** — Context7-compatible identifier (format: `/org/project`)
- **Name** — Library or package name
- **Description** — Short summary
- **Code Snippets** — Number of available code examples
- **Source Reputation** — Authority indicator (High, Medium, Low, or Unknown)
- **Benchmark Score** — Quality indicator (100 is the highest score)
- **Versions** — List of versions if available. Use one of those versions if the user provides a version in their query. The format is `/org/project/version`.

### Selection process

1. Analyze the query to understand what library/package the user is looking for
2. Select the most relevant match based on:
   - Name similarity to the query (exact matches prioritized)
   - Description relevance to the query's intent
   - Documentation coverage (prioritize libraries with higher Code Snippet counts)
   - Source reputation (consider libraries with High or Medium reputation more authoritative)
   - Benchmark score (higher is better, 100 is the maximum)
3. If multiple good matches exist, acknowledge this but proceed with the most relevant one
4. If no good matches exist, clearly state this and continue with the spill-over sources in Source order
5. For ambiguous queries, request clarification before proceeding with a best-guess match

### Version-specific IDs

If the user mentions a specific version, use a version-specific library ID:

```bash
# General (latest indexed): may describe Django 6.x
pnpm dlx ctx7@latest docs /websites/djangoproject_en "How to define a CheckConstraint"

# Version-specific: what this repository needs
pnpm dlx ctx7@latest docs /websites/djangoproject_en/5.2 "How to define a CheckConstraint"
```

The available versions are listed in the `ctx7 library` output. Use the closest match to what the user specified.

## Step 2: Query Documentation

Retrieves up-to-date documentation and code examples for the resolved library.

```bash
pnpm dlx ctx7@latest docs /websites/djangoproject_en/5.2 "How to annotate a queryset with a count and an average of related rows"
pnpm dlx ctx7@latest docs /websites/djangoproject_en/5.2 "How to write a data migration with RunPython"
pnpm dlx ctx7@latest docs /facebook/react "How to clean up useEffect with async operations"
```

### Writing good queries

The query directly affects the quality of results. Be specific and include relevant details. Do not include any sensitive or confidential information such as API keys, passwords, credentials, personal data, or proprietary code in your query.

| Quality | Example |
|---------|---------|
| Good | `"How to paginate a JSON list view in Django 5.2"` |
| Good | `"React useEffect cleanup function with async operations"` |
| Bad | `"auth"` |
| Bad | `"hooks"` |

Use the user's full question as the query when possible, vague one-word queries return generic results.

The output contains two types of content: **code snippets** (titled, with language-tagged blocks) and **info snippets** (prose explanations with breadcrumb context).

## Authentication

Works without authentication. For higher rate limits:

```bash
# Option A: environment variable
export CONTEXT7_API_KEY=your_key

# Option B: OAuth login
pnpm dlx ctx7@latest login
```

## Error Handling

If a command fails with a quota error ("Monthly quota reached" or "quota exceeded"):
1. Continue with the spill-over sources in Source order
2. Note in the answer that the Context7 quota is exhausted and that `pnpm dlx ctx7@latest login` raises the limit
3. Do not substitute potentially stale training knowledge

Never fall back to training data. Always say why Context7 was not used and which source answered instead.

## Common Mistakes

- Library IDs require a `/` prefix — `/websites/djangoproject_en/5.2` not `websites/djangoproject_en/5.2`
- Always run `ctx7 library` first — `pnpm dlx ctx7@latest docs django "models"` will fail without a valid ID
- Drop the version and you may get Django 6.x answers; keep `/5.2` on Django lookups
- Use descriptive queries, not single words — `"React useEffect cleanup function"` not `"hooks"`
- Do not include sensitive information (API keys, passwords, credentials) in queries
