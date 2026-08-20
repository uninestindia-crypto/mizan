# 06 — Comments, documentation, and deletion

Two habits that decide whether a codebase ages into something maintainable or something feared.

---

## 1. Comment *why*; the code says *what* (Law 9)

```
BAD    // increment the counter
       counter++

BAD    // loop over users
       for (const user of users) {

GOOD   // Stripe rounds half-up; we round half-even to match the ledger.
       // A 1-cent divergence here reconciles as a failed settlement (see #4471).
       const amount = roundHalfEven(raw)
```

A comment restating the code is worse than no comment: it is duplicated information that will go
stale, and a stale comment is a **lie with authority**. The next reader believes it over the code
and is misled.

**Comment the things code cannot say:**

- Why this approach and not the obvious one
- A constraint from outside the code — a third-party quirk, a legal requirement, a hardware limit
- A non-obvious performance trade-off, with the measurement
- A link to the bug, ticket, or spec that explains the surprise
- A warning about a sharp edge: "callers must hold the lock", "not safe across forks"

**The best comment is a better name.** Before writing one, ask whether renaming the variable or
extracting a named function would carry the meaning instead. Usually it would (Law 1).

## 2. Public API documentation is different

Comments explain the inside; API docs describe the outside. Anything exported deserves:

- What it does, in one line
- What the parameters mean, where non-obvious (units, ranges, ownership)
- What it returns, including the absence case
- **What it throws or returns as an error**, which is the most-skipped and most-needed part
- A short example, for anything with a non-trivial shape

Use the language's convention — docstring, doc comment, `///` — so tooling can surface it. Follow
the profile.

## 3. Comments that are always wrong

| Comment | Why |
|---|---|
| Restating the code | Stale by the next edit |
| Commented-out code | Version control remembers. Delete it. |
| A changelog in the header | That is what git log is |
| An author tag | That is what git blame is |
| `// TODO` with no ticket, name, or date | It will be there in three years |
| Section dividers inside a function | Those sections are functions (Law 2) |
| A comment explaining a bad name | Fix the name |
| Commented-out tests | A test that does not run is a lie about coverage |

## 4. TODOs

A TODO is a promise. Unowned, it is a promise nobody made.

```
BAD    // TODO: fix this properly
GOOD   // TODO(#4471): replace with the batch endpoint once it supports filters.
       // Current version issues N calls; fine under 100 items, not beyond.
```

Every TODO gets a **ticket or a link**, so it exists somewhere that is actually reviewed. The
checker flags TODO/FIXME/HACK without one, because the alternative is a codebase that accumulates
hundreds of them and reads them as wallpaper.

If it is not worth filing, it is not worth writing. Fix it or delete it.

## 5. Delete it (Law 10)

**It is all in version control.** Nothing is lost, and nothing needs to be kept "just in case".

Delete on sight:

- **Commented-out code.** Always. Every time.
- **Dead code** — unreachable, or reachable only from tests of itself.
- **Unused parameters, fields, imports, exports.**
- **Feature flags whose rollout finished.** A flag that has been 100% for six months is dead code
  plus a branch that nobody tests.
- **`v2` living beside `v1`** after the migration completed.
- **Speculative interfaces with one implementation**, added for a future that did not arrive.
- **Config options nobody sets.**
- **Tests of deleted behavior**, and tests that assert nothing.

**Why this matters more than it looks:** every line is read, searched, maintained, and *trusted*.
Dead code appears in grep results and misleads. It appears in coverage and flatters. It gets
refactored, updated for an API change, and reviewed — costs paid forever for a thing that does
nothing. Worst of all, a reader assumes it matters, because why else would it be there?

**The fear that stops deletion** — "what if we need it?" — is answered by version control, which is
exactly the tool built for that fear.

## 6. Speculative generality

The most expensive dead code is the code written for requirements that never arrived.

- A plugin system with one plugin
- A configuration option with one value
- An abstract base class with one subclass
- A generic parameter always instantiated the same way
- An event bus with one publisher and one subscriber

Each was added to "make it easy later". Each charges every reader between now and later a jump in
comprehension — and later usually never comes, or comes shaped differently enough that the
abstraction has to be redone anyway.

**Build the thing you need now, simply enough that changing it later is cheap.** That is what makes
future change easy — not a guess at what the future needs (Law 7).

## 7. Leave it better, in scope

The boy-scout rule, bounded: improve what you touch, **but do not fix what you are not touching in
the same change.**

A pull request that fixes the bug it claims to fix is reviewable. One that also renames four
modules is not — and it will be approved without being read, which is worse than not being reviewed
at all. It also makes the history useless: a future bisect lands on a commit that did six things.

**Note out-of-scope findings; do not fix them here.** Where the environment supports it, file them.
Otherwise list them in the summary of your change so they are visible rather than lost.
