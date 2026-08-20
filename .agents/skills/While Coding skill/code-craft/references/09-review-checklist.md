# 09 — The review checklist

Walk this before reporting any code work complete, and use it as the agenda for reviewing someone
else's. Every line passes or you state the exception and why. "It looks fine" is not a pass.

Automated first — it settles the mechanical items so review can spend its attention on judgment:

```bash
node scripts/check-code.mjs <changed paths>
```

Then the project's own formatter, linter, typechecker, and tests. **Those are the bar, and this
skill never overrides them.**

---

## Before anything else

- [ ] The change does what was asked, and **only** what was asked
- [ ] Out-of-scope problems were noted, not fixed here
- [ ] It matches the surrounding code's conventions and the language profile
- [ ] The diff is reviewable in one sitting — if not, it should have been several changes

## Naming (Law 1)

- [ ] Every name states intent, not type or implementation
- [ ] No `data`, `info`, `temp`, `obj`, `result`, `handler2`, `utils`
- [ ] Booleans read as assertions and are not negations
- [ ] Functions are verb phrases; values are noun phrases
- [ ] One word per concept, consistent with the rest of the codebase
- [ ] Domain terms are the user's words, not the schema's

## Functions (Laws 2, 3)

- [ ] Each does one thing, describable in a sentence without "and"
- [ ] One level of abstraction per function — no HTTP beside SQL beside arithmetic
- [ ] Nesting within budget; guards first, happy path last and unindented
- [ ] Parameters within budget; no boolean parameters
- [ ] One return type; no magic sentinels (`-1`, `""`) meaning "not found"
- [ ] Side effects are visible in the name
- [ ] No hidden I/O — clock, randomness, env, and network are passed in, not reached for

## Boundaries and dependencies (Laws 6, 7)

- [ ] Dependencies point one way; domain code imports no delivery mechanism
- [ ] No import cycles
- [ ] Nothing reaches into another module's internals; no `../../../` imports
- [ ] The public surface is as small as it can be
- [ ] Any new abstraction has a third real caller, or a stated reason
- [ ] Any new third-party dependency was justified — and is it really needed?

## State and data (Laws 4, 8)

- [ ] Illegal states are unrepresentable, or the reason they cannot be is stated
- [ ] Input validated once at the boundary; the interior trusts it
- [ ] No defensive re-checks of things the boundary guaranteed
- [ ] No shared mutable state; no mutated parameters; no returned internal references
- [ ] One source of truth — nothing derived is also stored without a stated invalidation rule
- [ ] Money is not a float; time is UTC and passed in, not read from a global clock
- [ ] Concurrent access considered: check-then-act replaced with an atomic operation

## Failure (Law 5)

- [ ] **No swallowed failures** — every one is handled, propagated, or ignored with a stated reason
- [ ] Catches are narrow; no bare `except:` / `catch (Exception)` standing in for a specific one
- [ ] Errors carry context added on the way up, preserving the original cause
- [ ] Error types distinguish caller-fault from our-fault, and retryable from terminal
- [ ] Every call leaving the process has a timeout
- [ ] Retries only on transient failures, with backoff and a bound
- [ ] **No blind retry of a non-idempotent operation on timeout**
- [ ] Partial failure has a decided behavior — all-or-nothing, or reported
- [ ] User-facing messages say what happened and what to do; 5xx never leaks internals

## Comments and deletion (Laws 9, 10)

- [ ] Comments explain *why*, never restate *what*
- [ ] No commented-out code, dead code, or unused parameters
- [ ] Every TODO has a ticket or a link
- [ ] Public API documents its parameters, return, and **failure modes**
- [ ] No speculative generality — no one-implementation interfaces, no unused config options

## Tests

- [ ] The failure paths are tested, not just the happy path
- [ ] Tests assert behavior, not implementation — they survive a refactor
- [ ] Test names state the behavior: "rejects a bid after the auction closes"
- [ ] Each test can fail for exactly one reason
- [ ] **You have watched a new test fail** before making it pass
- [ ] No sleeps, no ordering dependencies between tests, no shared mutable fixtures

## Product-type specifics

Apply the row for this product from `references/07-product-types.md`:

- [ ] **Library** — public surface minimal, no global state, no unrequested I/O, no `exit`
- [ ] **Service** — timeouts, idempotency, observability, hostile input, graceful shutdown
- [ ] **CLI** — exit codes distinct, stdout is data and stderr is everything else, no TTY prompts
- [ ] **Pipeline** — deterministic, idempotent rerun, schema asserted, atomic output swap
- [ ] **Embedded** — bounded memory and time, every return checked, safe state on fault
- [ ] **Realtime** — no allocation in the hot loop, frame budget respected
- [ ] **UI** — the design law skill was applied to anything visible

## Security, at the level craft owns

- [ ] Input from outside is validated and size-limited
- [ ] No string-built SQL, shell, or HTML — parameterized or escaped
- [ ] No secrets in code, logs, or error messages
- [ ] Authorization checked at the boundary of every operation, not just the UI
- [ ] Errors do not disclose whether a record exists where that is itself sensitive

Anything deeper belongs to a security review skill or the environment's security tooling.

## Before you report done

- [ ] `node scripts/check-code.mjs` clean, or every finding annotated with a reason
- [ ] The project's formatter, linter, typechecker, and tests all pass — **with the output seen**
- [ ] You read your own diff, top to bottom, as if reviewing someone else
- [ ] Anything skipped is stated explicitly, with the reason

**An unverified claim is an unsupported claim.** If you did not run it, say you did not run it.
