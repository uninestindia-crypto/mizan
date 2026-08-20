---
name: code-craft
description: >-
  The craft law for the inside of the code, in any language and any kind of product. Load this
  BEFORE writing or changing any function, class, module, script, query, or handler — and before
  any code review. Triggers on: "write", "implement", "add a function", "refactor", "clean up",
  "code review", "review this", "is this good code", "naming", "rename", "split this", "too long",
  "too complex", "simplify", "abstraction", "DRY", "duplication", "error handling", "exception",
  "try/catch", "null", "edge case", "module", "package", "import", "dependency", "circular",
  "coupling", "cohesion", "mutable", "immutable", "side effect", "pure function", "comment",
  "docstring", "dead code", "TODO", "technical debt", "code smell", ".py", ".go", ".rs", ".java",
  ".ts", ".rb", ".php", ".cs", ".cpp", ".swift", ".kt". Ten language-neutral laws — naming,
  function shape, nesting, illegal states, error handling, dependency direction, earned
  abstraction, mutation, comments, deletion — bound to any language through a one-page language
  profile and tightened per product type (library, service, CLI, data pipeline, embedded, game).
  Ships a metrics checker that works on every language it can read and reports UNKNOWN rather than
  guessing on one it cannot. If you are about to write a fifth level of nesting, an empty catch
  block, a name like `data2`, or an abstraction with one caller, you needed this skill and did not
  load it.
---

# Code Craft — The Law for the Inside of the Code

Code is read far more often than it is written, and almost always by someone with less context than
the author had — including the author, six months later, at 3am, during an incident. **Every rule
here optimizes for that reader.** Cleverness that costs them a minute is a bug with a delayed fuse.

This file is not style preference. Style is what a formatter settles, automatically, and you should
not spend a thought on it. This is about structure, and structure is not automatable, which is why
it needs a law.

## Scope — what this skill owns, and what it does not

| Concern | Owned by |
|---|---|
| How the project *starts* — stack, layout, CI, the config and error scaffolding | `project-zero` (day zero only) |
| **How code is written, every day after** — naming, function shape, boundaries, failure | **this skill** |
| What the user sees | `apple-grade-ui` or the project's design law |
| The process that gates the work | `founder-mode` |

The overlap with `project-zero` is deliberate and narrow: it *creates* the module boundaries and the
error taxonomy once; this skill *governs* every change to them afterwards. Where both speak, the day-zero
file decides the initial shape and this file decides whether a change is allowed to alter it.

---

## Two things to establish before the first edit

### 1. The language profile (once per language, ~2 minutes)

**The ten laws are language-neutral. Their expression is not.** "Name things clearly" is universal;
whether that name is `user_count` or `userCount` is not, and getting it wrong makes correct code
look foreign in its own repo.

Write one short profile per language the project uses, at `docs/code-profile.md`. The template and
a worked example are in `references/08-language-profiles.md`. It records the handful of facts no
general document can know: the naming convention, the formatter and linter that are the automatic
bar, how errors are idiomatically signalled, how modules are bounded, and the project's thresholds.

**Without a profile every session re-guesses the idiom, and the codebase ends up written in four
dialects.** If the language already has a dominant community standard — PEP 8, Effective Go,
`rustfmt`, the Google style guide — the profile is mostly a pointer to it, which takes two minutes
and settles a hundred future arguments.

### 2. The product type (once per project)

The laws all apply everywhere. Which ones *tighten* depends on what you are building:

| Product type | Tightens | Because |
|---|---|---|
| **Library / SDK** | Public API surface, backward compatibility, zero global state | Your mistakes become everyone's migrations |
| **Service / API** | Failure handling, idempotency, timeouts, observability | It fails while people are using it |
| **CLI / script** | Exit codes, stdout vs stderr, no interactive prompts | It runs inside other programs' pipelines |
| **Data / ML pipeline** | Determinism, idempotent reruns, schema evolution | It reruns over history and must agree with itself |
| **Embedded / systems** | Allocation, bounded time, explicit failure | There is no operator and no restart |
| **Game / realtime** | Allocation in the hot loop, frame budget | A pause is a defect the user feels |
| **UI application** | Defer to the design law skill for anything visible | — |

Record it in the profile. `references/07-product-types.md` has the specific rules per type.

---

## The ten laws (non-negotiable)

**Law 1 — Name for the reader who arrives at 3am.**
A name states *intent*, not type, not implementation. `retryableUsers` beats `userArray2`. Booleans
read as assertions (`isExpired`, `hasAccess`). Functions are verb phrases; values are noun phrases.
The only acceptable short names are conventional loop indices and a receiver in a two-line closure.
**If a name needs a comment to explain it, the name is wrong.**

**Law 2 — A function does one thing, at one level of abstraction.**
Mixing levels — HTTP parsing beside business arithmetic beside SQL — is the most common cause of a
function nobody can safely change. If you cannot state what it does in one sentence without "and",
it is two functions.

**Law 3 — Nesting is a budget, and the budget is three.**
Return early. Guard clauses first, happy path last and unindented. Every level of nesting multiplies
the states a reader must hold in their head, and past three, nobody does — they guess.

**Law 4 — Make illegal states unrepresentable.**
Validate once, at the boundary, into a type or structure that cannot hold a bad value; then trust it
everywhere inside. Defensive checks scattered through the interior are evidence the boundary is not
doing its job, and they hide the one place a real check was missing.

**Law 5 — Errors are values you handle, never noise you swallow.**
Every failure is handled, propagated with context, or explicitly and visibly ignored with a stated
reason. **An empty catch block is the single most expensive line in software** — it converts a
loud failure into a silent wrong answer, and silent wrong answers are found by customers.

**Law 6 — Dependencies point one way, and never in a circle.**
Business logic depends on nothing. Delivery mechanisms (HTTP, CLI, queue, UI) depend on business
logic. Nothing depends on a delivery mechanism. A cycle means two modules are one module that has
not admitted it.

**Law 7 — Duplication is cheaper than the wrong abstraction.**
Wait for the third occurrence, and abstract only when the *reason* they are the same is the same.
Two functions that look alike today and change for different reasons tomorrow must stay apart.
Un-abstracting is far more expensive than duplicating, because by then five callers depend on it.

**Law 8 — Mutation is local, or it is a bug waiting for a schedule.**
Prefer values over mutable state; prefer returning new data over editing in place. Where mutation is
necessary, confine it to the smallest possible scope. **Shared mutable state is the substrate of
every concurrency bug** you will ever spend a week on.

**Law 9 — A comment explains *why*; the code explains *what*.**
A comment restating the code is noise that goes stale and then lies. Comment the non-obvious: the
constraint, the trade-off, the reason for the surprising choice, the link to the bug this prevents.

**Law 10 — Delete it.**
Dead code, commented-out code, unused parameters, speculative interfaces with one implementation,
`v2` alongside `v1`. It is all in version control. Code that exists must earn its keep, because
every line is read, searched, maintained, and trusted by someone who assumes it matters.

---

## Step 0 — Install the checker (once per project, ~1 minute)

**The mechanical part of this law ships as a program.** It reads every language it recognizes and
reports `UNKNOWN` for one it does not, rather than guessing.

| Copy this file | To | Purpose |
|---|---|---|
| `scripts/check-code.mjs` | `scripts/check-code.mjs` | Structural metrics: file and function length, nesting depth, parameter count, swallowed errors, stale TODOs, commented-out code |

```bash
node scripts/check-code.mjs src
```

Thresholds are defaults, not dogma, and legitimately differ by language and product type. Override
them in `.code-craft.json`:

```json
{ "maxFileLines": 400, "maxFunctionLines": 50, "maxNesting": 3, "maxParams": 4 }
```

**What it cannot check is most of this document.** Naming quality, whether an abstraction is
earned, whether two similar functions change for the same reason — these need judgment, and the
checker deliberately does not pretend otherwise. It catches the mechanical failures so review can
spend its attention on the ones that matter.

---

## Workflow — every time you write or change code

### Before writing
Read the surrounding code first. **Match the file you are in over the guidance in this file** where
they conflict on style — an internally consistent codebase beats a locally optimal function. If the
surrounding code violates these laws badly, that is a refactoring proposal, not a licence to add a
second dialect.

### While writing
Name first, and rename freely as the thing becomes clear. Write the failure path in the same pass
as the happy path (Law 5) — not after, not "later". Keep functions under the budget as you go;
splitting a 300-line function afterwards is a different and much worse task.

### Before calling it done
```bash
node scripts/check-code.mjs <changed paths>
```
Then the project's own formatter, linter, typechecker, and tests — **those are the bar, and this
skill never overrides them.** Then walk `references/09-review-checklist.md`.

---

## What ships with this skill

| Path | What it is |
|---|---|
| `scripts/check-code.mjs` | The structural checker. Multi-language, configurable thresholds, `UNKNOWN` over guessing |

There are deliberately **no code assets**. A component library can ship as one file because a
design system has one correct answer; craft does not — the same law produces different correct code
in Go and in Haskell. The language profile is the binding mechanism instead.

## References — load what the task needs

| File | Load it when |
|---|---|
| `references/01-naming.md` | Naming anything, or a name feels wrong and you cannot say why |
| `references/02-functions.md` | Function shape, size, parameters, return values, purity |
| `references/03-modules-and-deps.md` | Module boundaries, imports, coupling, cycles, layering |
| `references/04-errors-and-failure.md` | Any failure path, error type, retry, timeout, partial failure |
| `references/05-state-and-data.md` | Mutability, data modeling, invariants, concurrency |
| `references/06-comments-and-deletion.md` | Comments, docs, dead code, TODOs, speculative generality |
| `references/07-product-types.md` | **Once per project** — the rules that tighten for your product type |
| `references/08-language-profiles.md` | **First run in any language** — the profile template and worked examples |
| `references/09-review-checklist.md` | Before reporting any code work complete, and for any code review |

Related skills, where the environment has them: `project-zero` for day-zero setup, `founder-mode`
for the process gates, `apple-grade-ui` for anything visible. A related skill that is not installed
is not a blocker; this file is self-sufficient.

---

## The failure modes that give it away

- **Names that describe the container, not the contents** — `data`, `info`, `result`, `temp`,
  `obj`, `manager`, `helper`, `utils`. Each one is a decision someone declined to make.
- **A function whose name contains "and".** It is two functions and you already know it.
- **Boolean parameters.** `render(true)` is unreadable at the call site. Take an enum, or split.
- **Five levels of nesting.** Invert the conditions and return early; it is nearly always mechanical.
- **`catch (e) {}`** — see Law 5. Also `except: pass`, `rescue nil`, `if err != nil { }`.
- **Comments that repeat the code.** `// increment i` above `i++` is a maintenance liability.
- **An interface with exactly one implementation**, added "for testing" or "for later". Later never
  came, and the indirection is charged to every reader in between.
- **`utils.py` at 2000 lines.** It became the place code goes to avoid a decision.
- **A parameter that is always the same value at every call site.** Delete it.
- **Commented-out code.** Version control exists. Delete it.
- **`// TODO: fix this` with no ticket, no name, and no date.** It will be there in three years.
- **Defensive null checks on a value that cannot be null**, which teach every reader that it can.

---

## Scope discipline

This skill makes code better; it does not make code *bigger*. It never authorizes a rewrite, a
framework migration, or a refactor of code you were not asked to touch. **When you notice something
out of scope, note it — do not fix it in the same change.** A pull request that fixes the bug it
claims to fix is reviewable; one that also reorganizes four modules is not, and it will be approved
without being read, which is worse than not being reviewed at all.
