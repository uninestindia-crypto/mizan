# 03 — Modules, boundaries, and dependencies

Functions are what a person reads. Modules are what a *team* reads, and what determines whether two
people can work at once without colliding.

`project-zero/references/02-repo-and-config.md` sets the initial layout. This file governs every
change to it afterwards.

---

## 1. A module is a decision you can change alone

The purpose of a boundary is not tidiness. It is that **one decision can change without touching
anything else.** If changing the tax rule requires edits in six directories, the boundary is in the
wrong place, regardless of how neat the tree looks.

**Group by domain, not by layer** (the single most consequential structural choice):

| Do | Don't |
|---|---|
| `billing/{service,repository,tests}` | `services/`, `repositories/`, `models/` |

Layer-grouping looks organized and spreads every feature across four directories, so every change
is a four-directory diff and nothing tells you where a concept begins or ends. Domain-grouping makes
**a feature a folder**: deleting it is deleting a folder, and the blast radius is visible in the tree.

## 2. Dependencies point one way (Law 6)

```
delivery  →  domain  →  (nothing)
(http, cli,     ↓
 queue, ui)   config, errors, logging   ← leaves: imported by anyone, importing nothing
```

Three rules:

1. **Domain code never imports a delivery mechanism.** Business logic that imports an HTTP framework
   cannot be called by a cron job, cannot be tested without a server, and cannot be reused.
2. **Domains do not reach into each other's internals.** Cross-domain access goes through a public
   entry point, or through the composition root that wires them.
3. **No cycles, ever.**

**Enforce this with a lint rule, not a document.** A boundary that is documented but not checked
will be crossed in week three by someone in a hurry, and never restored. Record the enforcement
command in the profile — `import/no-cycle`, `eslint-plugin-boundaries`, `depcruise`, Go's
`internal/`, `import-linter` for Python.

## 3. Cycles

**A cycle means two modules are one module that has not admitted it.** They cannot be understood
separately, tested separately, or deployed separately.

Three ways out, in order of preference:

1. **Merge them.** If they are genuinely one concept, stop pretending.
2. **Extract the shared part** into a third module that both depend on.
3. **Invert one direction** — the lower-level module defines an interface; the higher-level one
   implements it.

Some languages (Go) forbid import cycles outright. Where the language allows them, the linter must.

## 4. Coupling and cohesion, concretely

**High cohesion:** things that change together live together. If two files are always edited in the
same commit, they probably want to be one module.

**Low coupling:** a module depends on as little of another as possible.

| Coupling, worst to best | Example |
|---|---|
| Shared mutable state | Two modules reading and writing the same global |
| Reaching into internals | `other.internal.cache.entries[0]` |
| Structural dependency | Depending on the full shape of a large type |
| Narrow interface | Depending on one function with two parameters |
| Data only | Receiving a value; knowing nothing about who made it |

**Depend on the narrowest thing that works.** A function that needs a user's email should take an
email, not a `User`, and certainly not a `Request`. Narrow dependencies are easier to call, easier
to test, and do not break when the wide type changes.

## 5. Public surface

Everything is private until there is a reason. **What you export, you support** — every exported
name is something someone can depend on, and something you cannot change freely afterwards.

- Use the language's real privacy: unexported names in Go, `_` prefix in Python, `private` in
  Java/C#/Kotlin, `pub` opt-in in Rust, `internal/` packages.
- **One entry point per module.** Callers import the module, not a file three levels inside it. A
  deep import path (`../../billing/internal/tax/rules`) is a boundary violation you can see.
- A module's public surface should fit on a screen. If it does not, it is several modules.

## 6. Abstraction is earned, not anticipated (Law 7)

**Wait for the third occurrence**, and abstract only when the *reason* they are the same is the
same. Two functions that look alike today but change for different reasons tomorrow must stay apart
— merging them creates a shared thing that must satisfy two masters, and every future change fights
the other caller.

> Duplication is far cheaper than the wrong abstraction.

Un-abstracting is much more expensive than duplicating, because by then five callers depend on the
abstraction and the parameters have multiplied to serve all of them. The tell-tale of a wrong
abstraction is a function whose parameter list grew boolean flags over time: each flag is a caller
that did not quite fit.

**An interface with one implementation is not an abstraction; it is indirection.** Adding it "for
testing" or "for later" charges every reader a jump for a benefit that never arrived. Add the
interface when the second implementation exists, or when you genuinely must swap it in a test and
the language gives you no other way.

## 7. Dependencies on other people's code

Every third-party dependency is a liability you carry for years: its bugs, its vulnerabilities, its
release cadence, its maintainer's interest.

- **Read before you add.** Last release, maintainer count, transitive dependency count.
- **Prefer the standard library** for anything you could write in twenty lines.
- **One tool per job.** Two date libraries means every future author guesses.
- **Wrap what you do not control** — where a third-party type would spread through your domain,
  translate at the boundary into your own type. Then replacing the library is a change in one file
  rather than four hundred.

Do not wrap everything reflexively. Wrap what is (a) likely to change and (b) would otherwise leak
widely. A thin wrapper around a stable standard library is pure cost.

## 8. Module-shaped smells

- A file over ~400 lines — it has more than one reason to change.
- `utils/`, `helpers/`, `common/`, `shared/`, `misc/` — where code goes when nobody decided.
  These only grow, become import magnets, and eventually contain the application.
- A module imported by everything — either a genuine leaf (fine: config, errors, logging) or a god
  module (not fine).
- A module that imports everything — it is a composition root (fine, one per app) or it is doing
  too much.
- Changing one feature requires edits in five directories — the boundary is wrong.
- A deep relative import (`../../../`) — you crossed a boundary the layout meant to hold.
- Two modules that are always edited together — they are one module.
