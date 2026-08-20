# 08 — Bootstrap: Binding Founder Mode to Any Codebase

Run this once per repository before the first write-authorized founder-mode build or release task.
For read-only reviews, inspect the repository without creating or updating state files.

**Why it exists.** Every gate in this process demands evidence, and evidence means running *this
project's* real commands. A process that guesses at commands produces fake evidence, which is worse
than none. Bootstrap discovers the truth and writes it down.

**Golden rule: discover, never assume.** `npm test` existing in `package.json` does not mean it
works, does not mean it is the whole suite, and does not mean it does not need a database. Run
everything you record.

## Contents

- [Read project instructions and detect the stack](#step-1--read-what-the-project-already-says)
- [Discover and verify commands](#step-3--discover-and-verify-the-commands)
- [Map critical paths and environments](#step-4--find-the-critical-paths)
- [Apply project law and write authorized state](#step-6--note-the-projects-own-law)
- [Report bootstrap or handle greenfield work](#step-8--report-the-bootstrap)

---

## Step 1 — Read what the project already says

Before running anything, read (whichever exist):

- `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `CONTRIBUTING.md` — **these outrank founder-mode on
  anything they cover.** Note the conflicts explicitly.
- `README.md` — the setup steps, which are usually stale; you will verify them
- `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `azure-pipelines.yml` — **the CI config is
  the most reliable source of truth about what commands actually matter**, because unlike the
  README it is executed on every push
- `package.json` scripts, `Makefile`, `justfile`, `Taskfile`, `pyproject.toml`, `Cargo.toml`,
  `go.mod`, `build.gradle`, `composer.json`
- `docker-compose.yml`, `Dockerfile` — what services the app actually needs
- `.env.example` — the env contract
- Existing docs folders — architecture, decisions, prior launch reports

Also read the last 20 commits (`git log --oneline -20`) and any open issues if accessible. The
recent commits tell you what is actively moving and what the team's real conventions are.

---

## Step 2 — Detect the stack

Determine and record: language(s) and versions, framework, package manager, database, cache,
queue, external services, deployment target, test runner(s), CI system, and how the app is run
locally.

Quick signals:

| File | Tells you |
|---|---|
| `package.json` → `workspaces` | Monorepo; commands may need `--workspace` |
| `next.config.*` / `vite.config.*` / `nest-cli.json` | JS framework and its conventions |
| `prisma/schema.prisma`, `migrations/`, `alembic/` | Migration tooling — critical for G2/G7 |
| `pyproject.toml` → `[tool.poetry]` / `requirements.txt` | Python packaging |
| `go.mod`, `Cargo.toml`, `pom.xml`, `*.csproj`, `Gemfile` | Language and its ecosystem |
| `docker-compose.yml` | The real local dependency set |
| `vercel.json`, `fly.toml`, `k8s/`, `terraform/`, `serverless.yml` | Deploy target and rollback mechanism |
| `playwright.config.*`, `cypress.config.*` | E2E capability already exists — find out if it runs |

---

## Step 3 — Discover and **verify** the commands

Fill in this table by *running each command* and recording what actually happened. A command that
you did not run does not go in the file — put it under "unverified" instead.

| Ring / need | Command | Verified | Duration | Notes / prerequisites |
|---|---|---|---|---|
| Install | | | | |
| Typecheck | | | | |
| Lint | | | | |
| Format check | | | | |
| Dead code / unused | | | | |
| Secret scan | | | | |
| Dependency audit | | | | |
| Unit tests | | | | |
| Integration tests | | | | needs DB? |
| E2E tests | | | | needs a running server? |
| Coverage | | | | |
| Build | | | | |
| Start (dev) | | | | port |
| Start (prod-like) | | | | |
| DB migrate up | | | | |
| **DB migrate down / rollback** | | | | **the one most often missing** |
| DB seed | | | | |
| DB reset from zero | | | | |
| Deploy | | | | |
| **Rollback deploy** | | | | |
| Logs (prod) | | | | |
| Metrics/dashboard | | | | |

**Record the baseline.** Run the full static + test set on a clean checkout **before you change
anything** and record the exact result:

```
BASELINE (clean checkout, <date>, <commit sha>)
typecheck: 0 errors
lint:      14 warnings, 0 errors      ← pre-existing; your change must add none
unit:      238 passed, 2 failed        ← name the 2, they are pre-existing
e2e:       could not run — needs DATABASE_URL   ← this is a finding, log it
```

This baseline is what makes R0's "zero findings" bar enforceable in a repo that does not start at
zero: **your change adds nothing new**, and fixing the pre-existing baseline becomes its own slice
with its own gate. Without a recorded baseline every gate becomes an argument about whether a
failure is yours.

---

## Step 4 — Find the critical paths

Ask the founder, and confirm against the code: **which two to five user journeys, if broken, mean
the product has no reason to exist?**

For each, write down: the actor, the steps, what "success" looks like, and what the worst failure
would be. These become the R4 E2E suite and the production smoke suite, and everything in
`04-test-matrix.md` marked "critical path" refers to these.

If the founder cannot name them, that is a P0 finding worth raising immediately — a team that
cannot name its critical paths cannot prioritize anything.

---

## Step 5 — Map the environments

| Environment | Exists? | How to reach it | Data | Who can deploy | Rollback method |
|---|---|---|---|---|---|
| Local | | | | | |
| CI | | | | | |
| Staging / preview | | | | | |
| Production | | | | | |

**If there is no production-like environment, that is a G7 blocker for T3+ work** and must be
raised in P0, not discovered at T-3 days. "We test in production" is a strategy only if the
rollback is instant and rehearsed.

---

## Step 6 — Note the project's own law

Record explicitly:
- Does this project have a **design law skill** (e.g. `apple-grade-ui`)? → P6 taste defers to it
  entirely; `taste-critic` loads it rather than inventing taste.
- Does it have **review tooling** (review skills, static analyzers, custom checks)? → that is
  the P5 evidence.
- Does it have **hooks** that block certain edits? → work with them; a hook that blocks you is the
  project telling you a rule.
- Does `AGENTS.md`/`CLAUDE.md` mandate a **response format**, forbidden patterns, or domain rules?
  → those outrank this skill.

---

## Step 7 — Write the state files

When project-state writes are authorized, create the launch-state directory. **Resolution order,
first hit wins:** `.launch/` → `.claude/launch/` → `.codex/launch/`. If one of those already exists
in this repo, use it and do not migrate. If none exists, create `.launch/`. Paths below are written
against `.launch/`; substitute whichever directory you resolved to.

```
.launch/
  COMMANDS.md      ← the verified command table + baseline  (the most valuable file)
  CONTEXT.md       ← stack, critical paths, environments, project law
  CHARTER.md       ← per-effort, from 07-templates.md
  PRD.md
  ARCHITECTURE.md
  SLICES.md
  RISKS.md
  STATE.md
  PRELAUNCH.md    <- ordered steps 1-15 from 11-pre-launch-procedure.md
  RUNBOOK.md
  POSTMORTEM.md
```

`COMMANDS.md` and `CONTEXT.md` are written once and maintained. The rest are per-effort — archive
them into `.launch/archive/<name>/` when a launch completes, so the next effort starts clean
but the history survives.

Add `.launch/` to the repo (commit it — it is project knowledge, not scratch) unless the
founder prefers otherwise.

---

## Step 8 — Report the bootstrap

```
[BOOTSTRAP · <repo>]

STACK           <language/framework/db/deploy>
COMMANDS        <n> verified, <n> unverified, <n> missing
BASELINE        <the exact numbers>
CRITICAL PATHS  <the 2-5 journeys>
ENVIRONMENTS    <which exist>
PROJECT LAW     <AGENTS.md rules / design skill / review tooling that outrank or feed this process>

GAPS FOUND      ← the important part; these are findings, not chores
- no rollback command exists for migrations
- e2e suite cannot run locally (needs DATABASE_URL and a seeded DB)
- no staging environment
- 2 pre-existing test failures in <file>
- no monitoring/alerting configured

RECOMMENDED     which gaps to close before the first launch, ranked by what they would cost at G7
```

**The gaps section is the point of the whole exercise.** Every gap is a gate that will block later,
and finding them on day one costs an hour, while finding them at T-3 days moves the launch date.
A repo with no rollback command and no staging is not "ready to add a feature to" — it is a repo
where the first slice should be building those.

---

## Bootstrap for a greenfield project

If the repo is empty, bootstrap runs in reverse — you are *choosing* the commands rather than
discovering them. **Load the `project-zero` skill and execute it.** It owns the full day-zero
sequence: stack selection, version pinning, repo layout, the configuration contract, the error
taxonomy, logging, CI, and the walking skeleton. Do not improvise a project structure when a
specified one exists.

The founder-mode acceptance bar for a greenfield repo — what `project-zero` must leave behind
before slice 1 may start — is that all seven of these exist and have been **verified working, with
raw output**:

1. Typecheck / lint / format — configured, running, zero findings
2. A test runner with **one real test that you have watched fail and then pass**
3. A migration tool with **a rollback that you have executed**
4. CI running all of the above on every push
5. A deploy that works, and a rollback that you have executed
6. `.env.example` complete, and a startup check that fails loudly on a missing variable
7. One health endpoint and one metric

**This is slice 0, before any feature.** It costs half a day at the start and is nearly impossible
to retrofit under launch pressure — which is exactly when you will need it. A greenfield project
that reaches its first launch without a rehearsed rollback has to invent one during the incident.
