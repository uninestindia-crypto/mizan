---
name: project-zero
description: >-
  The day-zero doctrine for a repository that does not exist yet. Load this BEFORE the first line of
  code in any new project, service, package, or rewrite — and before choosing a stack, a framework,
  a database, or a directory layout. Triggers on: "new project", "from scratch", "greenfield",
  "start a project", "set up a repo", "scaffold", "bootstrap", "initialize", "init", "new service",
  "new app", "new package", "rewrite", "which stack", "which framework", "which database",
  "project structure", "repo layout", "folder structure", "monorepo", "boilerplate", "starter",
  "set up CI", "set up testing", "set up linting", "environment variables", ".env", "config",
  "error handling strategy", "logging setup", "health check", "walking skeleton", "slice 0",
  "day one". Owns the seven things a greenfield repo must have before its first feature: pinned
  stack, repo layout, a validated configuration contract, an error taxonomy, structured logging,
  CI that runs on every push, and a walking skeleton deployed with a rollback you have executed.
  Ships copy-paste implementations of all of them plus a verifier that turns the day-zero gate into
  an exit code. If you are about to write a feature in a repo that has no test you have watched
  fail, no rollback you have run, or no startup check on its config, you needed this skill and did
  not load it.
---

# Project Zero — The Day-Zero Doctrine

The decisions made in a repository's first day are the ones that cannot be undone cheaply. Every
one of them is reversible on day one, expensive on day thirty, and effectively permanent on day
ninety. This file is not advice about starting projects. It is the specification for the first day.

**Your job on day zero is not to build the product. It is to build the machine that builds the
product safely.**

---

## The founding premise

A greenfield project fails slowly, and it always fails the same way. Nobody notices, because on day
one everything works — there is barely any code, so nothing can break.

1. **The stack was chosen by novelty**, so half the effort goes to fighting tools nobody understands.
2. **The first feature came before the first test**, so there was never a moment where the safety
   net was proven to catch anything.
3. **Config was read from `process.env` inline**, so the first production deploy died on a missing
   variable that nobody could name.
4. **Errors were strings**, so by month two nothing could be handled programmatically and every
   caller string-matched on messages.
5. **CI came later**, so "later" became "after the first incident".
6. **Rollback was theoretical**, so the first bad deploy became an outage instead of an inconvenience.

Everything below exists to make those six impossible on this project — not discouraged, impossible,
because a gate blocks the first feature until each one is real.

---

## The ten laws (non-negotiable)

**Law 1 — Choose boring, and pin it.**
Prefer the technology with the most answered questions, not the most interesting one. Every
dependency is a liability you will carry for years. Pin exact versions — language runtime, package
manager, and every dependency — and commit the lockfile. "Latest" is not a version; it is a
promise to be surprised.

**Law 2 — The walking skeleton comes before the first feature.**
One request path, end to end, deployed: client → server → database → response, with a test and a
deploy and a rollback. It does nothing useful, and that is the point. Build it first, and every
feature afterwards is a change to a working system instead of a step toward a hypothetical one.

**Law 3 — Config is a contract, validated at startup.**
Every environment variable is declared in one schema, parsed once at boot, and the process
**refuses to start** if any are missing or malformed. No `process.env` reads scattered through the
code. A service that boots with a missing config and fails on first request has converted a startup
error into a production incident.

**Law 4 — Errors are a taxonomy, not strings.**
Define the error types on day zero: which are the caller's fault, which are yours, which are
transient and retryable. Every error carries a stable machine-readable code. Never `throw new
Error("something went wrong")`, and never make a caller regex a message to decide what to do.

**Law 5 — Logs are structured events, not prose.**
One line, one JSON object, one event, always with a request/correlation id. `console.log("here")`
is not logging. You cannot grep your way out of an incident at 3am if the logs were written for a
human reading them one at a time.

**Law 6 — CI on day zero, running on every push.**
Typecheck, lint, format, test, build. It runs on the first commit, when it takes four seconds and
passes trivially, so it can never become a project too big to add CI to. Red main is an emergency.

**Law 7 — A rollback you have executed, not one you have written down.**
Both kinds: the deploy rollback and the database migration rollback. Run them, on day zero, and
paste the output. An unrehearsed rollback is a plan to improvise during your worst hour.

**Law 8 — One health endpoint and one metric, from the first deploy.**
`/health` that actually checks dependencies, and one number that tells you the system is alive.
Observability added after the first incident is added too late to explain the first incident.

**Law 9 — The repo layout encodes the architecture.**
Directory structure is a dependency diagram that people can see. Decide the boundaries and the
allowed direction of imports on day zero, and enforce the direction mechanically. Layout drift is
architecture drift wearing a disguise.

**Law 10 — Nothing is "temporary".**
There is no such thing as a temporary hack in a new repo, only the oldest code in the project.
Every "we'll fix it later" written on day zero is still there on day four hundred, load-bearing,
with three things built on top of it.

---

## The day-zero sequence

Run these in order. Each step's output is the next step's input, and **the gate at the end is
mechanical** — a script, not an opinion.

| # | Step | Produces | Reference |
|---|---|---|---|
| 0 | Confirm it is actually greenfield | A decision to proceed or to bootstrap instead | below |
| 1 | Choose and pin the stack | `ADR-0001`, lockfile, version files | `references/01-stack-selection.md` |
| 2 | Lay out the repo | Directory tree, import boundaries | `references/02-repo-and-config.md` |
| 3 | Write the config contract | `config.ts` + `.env.example`, boot-time validation | `references/02-repo-and-config.md` |
| 4 | Define errors and logging | `errors.ts`, `logger.ts` | `references/03-errors-and-logging.md` |
| 5 | Stand up CI | Pipeline running on every push | `references/04-ci-and-deploy.md` |
| 6 | Deploy and roll back | A rehearsed rollback with pasted output | `references/04-ci-and-deploy.md` |
| 7 | Build the walking skeleton | One end-to-end path, tested and live | `references/05-walking-skeleton.md` |
| 8 | Pass the gate | Exit code 0 from the verifier | `references/06-day-zero-gate.md` |

### Step 0 — Confirm it is actually greenfield

If the repository already has code, **stop and use
`founder-mode/references/08-bootstrap.md` instead** — that file discovers an existing project's
truth, which is a different job. This skill *chooses* where bootstrap *discovers*.

A repo with a README and nothing else is greenfield. A repo with a half-finished prototype is not:
inventory what exists first, then apply the laws above to what is missing.

---

## Step 0.5 — Install the day-zero verifier (once, ~1 minute)

**This skill ships its gate as a program.** Copy it in before you start, so the target is visible
from the beginning rather than discovered at the end.

| Copy this file | To | Purpose |
|---|---|---|
| `scripts/verify-day-zero.mjs` | `scripts/verify-day-zero.mjs` | The gate. Checks all seven acceptance criteria and exits non-zero until they are real |
| `assets/config.ts` | `src/config.ts` | The configuration contract with boot-time validation (Law 3) |
| `assets/errors.ts` | `src/errors.ts` | The error taxonomy with stable codes (Law 4) |
| `assets/logger.ts` | `src/logger.ts` | Structured JSON logging with correlation ids (Law 5) |
| `assets/ci.github.yml` | `.github/workflows/ci.yml` | CI running the full static + test set on every push (Law 6) |

Then, at any point, ask the gate where you stand:

```bash
node scripts/verify-day-zero.mjs
```

It reports every criterion as `OK`, `FAIL`, or `MANUAL` and exits non-zero until the automatable
ones pass. Run it on the first commit — a wall of `FAIL` on an empty repo is correct, and it is the
to-do list.

**The three it cannot check for you** are the ones that require a human to have *watched something
happen*: a test you saw fail before it passed, a migration rollback you executed, and a deploy
rollback you executed. The gate marks these `MANUAL` and demands pasted evidence. Do not mark them
done from memory — Law 4 of `founder-mode` applies here: evidence or it did not happen.

---

## Workflow — the first day, in order

### Choose the stack (Step 1)
Take the default from `references/01-stack-selection.md` unless you can state a specific reason not
to, in one sentence, in an ADR. **A weak reason to deviate costs a week.** Record the choice, the
rejected alternative, and what would make you revisit it.

### Lay out the repo and write the config contract (Steps 2–3)
The layout encodes the architecture (Law 9). The config contract is the first real code you write —
before any feature, because every feature will depend on it.

### Errors, logging, CI (Steps 4–5)
Copy `errors.ts` and `logger.ts`, then get CI green on a repo that does almost nothing. This is the
cheapest CI will ever be to set up.

### Deploy the skeleton, then break it on purpose (Steps 6–7)
Deploy something trivial. Roll it back. Migrate the database. Roll that back. **Paste the output of
both.** Only then build the walking skeleton, which is the first thing that resembles the product.

### Pass the gate (Step 8)
```bash
node scripts/verify-day-zero.mjs
```
Then walk `references/06-day-zero-gate.md` for the manual criteria. Slice 1 does not start until
this passes. That is the entire point of the skill.

---

## What ships with this skill

| Path | What it is |
|---|---|
| `scripts/verify-day-zero.mjs` | **The gate as a program.** Detects the stack, checks all seven criteria, prints a to-do list, exits non-zero until they pass |
| `assets/config.ts` | The configuration contract: one schema, parsed once, refuses to boot when wrong |
| `assets/errors.ts` | The error taxonomy: typed, coded, with `isRetryable` and safe client serialization |
| `assets/logger.ts` | Structured JSON logging with correlation ids and automatic secret redaction |
| `assets/ci.github.yml` | A CI pipeline that runs the full static + test set on every push |

The assets are TypeScript because that is the default stack this skill recommends. The *shape* of
each — one schema validated at boot, coded errors, structured events — is the law in every
language; port it rather than skipping it.

## References — load what the step needs

| File | Load it when |
|---|---|
| `references/01-stack-selection.md` | Step 1: choosing anything — language, framework, database, hosting — and pinning it |
| `references/02-repo-and-config.md` | Steps 2–3: directory layout, import boundaries, the configuration contract |
| `references/03-errors-and-logging.md` | Step 4: the error taxonomy, structured logging, health and metrics |
| `references/04-ci-and-deploy.md` | Steps 5–6: the pipeline, the deploy, and both rollbacks |
| `references/05-walking-skeleton.md` | Step 7: what the first end-to-end path must contain |
| `references/06-day-zero-gate.md` | Step 8: the gate, including the criteria the script cannot check |

Related skills, where the environment has them: `founder-mode` owns the process this feeds into —
project-zero is its slice 0, and `founder-mode/references/08-bootstrap.md` defines the acceptance
bar used here. `apple-grade-ui` owns any user-visible surface. A related skill that is not installed is not
a blocker; this file is self-sufficient.

---

## The failure modes that give it away

- **A `src/utils` folder on day one.** It is where code goes when nobody decided where it belongs,
  and it only ever grows. Name modules for what they do.
- **`process.env.FOO` read inside a function.** The config contract exists precisely so that the
  set of required variables is knowable without reading every file.
- **A test suite with no failing test in its history.** If you have never watched it go red, you
  have not tested the tests, and a suite that cannot fail is decoration.
- **`catch (e) { console.log(e) }`.** Swallowing an error is choosing to be blind later.
- **Secrets in `.env` committed "just for now".** Rotate them; they are in the history forever.
- **A README with setup steps nobody has run on a clean machine.** Run them on a clean machine.
- **"We'll add types later."** Later is a rewrite, and it will not be scheduled.
- **A migration with no `down`.** You have built a one-way door and called it a schema change.
- **Deploying by hand the first time "just to see".** The first deploy is the one most worth
  automating, because it is the one you will repeat most while the project is young.

---

## Scope discipline

This skill makes a project *start* correctly; it does not make it *bigger*. Day zero is not the day
to build an auth system, a plugin architecture, an event bus, or a design system you will "need
eventually". Build the smallest thing that exercises the whole path end to end, prove you can ship
it and unship it, and stop. **The walking skeleton should be embarrassing.** If it is impressive,
you built a feature and skipped the machine.
