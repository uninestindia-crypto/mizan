# 04 — The Test Matrix

The question this file answers: **for this exact piece of code, what gets tested, how, how many
times, and what counts as passing?**

Nothing here is aspirational. Every row is a minimum, and a minimum is not a target.

**Companion skill.** This file specifies *how much* and *which cases*. The `test-craft` skill
specifies *how to write the test itself* — structure, what to assert, fakes vs mocks, fixtures,
determinism, and flake elimination. Load it before writing tests; a case list executed as bad tests
buys nothing.

## Contents

- [Three-pass rule](#the-3-pass-rule-law-5)
- [Nine test rings](#the-nine-rings)
- [Per-part requirements](#per-part-type-requirements)
- [Per-slice budget](#the-per-slice-test-budget)
- [Test quality and coverage](#test-quality--the-tests-themselves-are-code-that-can-be-wrong)

---

## The 3-pass rule (Law 5)

No unit of T2+ work is done until three independent actors have hit it. T0–T1 may use a recorded
solo exception when crew mode was not requested or approved:

| Pass | Actor | Question they are answering | Output |
|---|---|---|---|
| **1. Build** | Staff Engineer | Does it do what the criteria say? | Tests written, tests green |
| **2. Break** | Red Team | What input makes it wrong? | Reproductions, ranked |
| **3. Prove** | Verifier | Is it still true from a clean state? | Raw output, PASS/BLOCKED |

For T2+, the same actor doing all three counts as **one** pass. For a T0–T1 solo exception, change
stance explicitly: pass 2 must design adversarial inputs, and pass 3 must delete derived state and
rebuild from zero. Record the exception; it cannot clear T2–T4.

---

## The nine rings

| Ring | Name | Trigger | Exit bar | Typical runtime |
|---|---|---|---|---|
| **R0** | Static | Every file write | 0 errors — not 0 *new* errors, 0 errors | seconds |
| **R1** | Unit | Every slice with logic | Every branch of domain logic exercised | seconds |
| **R2** | Contract | Every slice touching a boundary | Every interface shape pinned by a test | seconds |
| **R3** | Integration | Every slice touching >1 module or the DB | Real DB, real migrations, real wiring | minutes |
| **R4** | End-to-end | Every slice on a critical path | The user's whole journey, real runtime | minutes |
| **R5** | Adversarial | Every slice, **and again** in P5 | The 12 attack families (`05-hardening.md`) | manual + tests |
| **R6** | Non-functional | P5 | Perf, a11y, load, soak, bundle, i18n, security | minutes–hours |
| **R7** | Human | P6–P7 | Customer Zero + taste, on real devices | one session |
| **R8** | Production | P8–P9 | Smoke on prod, canary, monitors fired, 72h watch | 72 hours |

### R0 — Static

Whatever the project has: type checking, linting, formatting, dead-code detection, secret scanning,
dependency audit. Discover and record them in `.launch/COMMANDS.md` during an authorized
bootstrap.

**The bar is zero findings, including warnings.** A codebase with 400 tolerated warnings has no
static analysis — it has a wall of noise that hides the one warning that mattered. If the project
starts with pre-existing findings, record the exact baseline count at bootstrap and require that
your change adds none; then fix the baseline as its own slice.

### R1 — Unit

Pure logic in isolation: no network, no DB, no clock, no filesystem, no randomness. If a function
needs those, inject them — untestable code is a design finding, and the correct response is to
change the design, not to skip the test.

**Bar:** every branch of domain logic. Not "80% coverage" — coverage percentages are satisfied by
tests that assert nothing. The bar is *branches of logic that matter*, and for money, time,
permissions, and units it is *every boundary of every input*.

### R2 — Contract

Pin the shape of every boundary so that a change to it is a *deliberate* act that breaks a test,
rather than an accident that breaks a consumer in production.

Test: request/response schemas, DB schema expectations, event payload shapes, error taxonomy,
public module exports, config/env contract, and (critically) **the auth and tenancy rules as
assertions**.

**Bar:** you cannot change a boundary without a test going red.

### R3 — Integration

Real database, real migrations run forward from empty, real module wiring; external services
stubbed at the network boundary (not mocked at the function boundary — mocking your own wrapper
tests your wrapper, not the integration).

**Bar:** the paths that cross module lines work against a real datastore, with real constraints,
real transactions, and real migrations.

### R4 — End-to-end

The user's actual journey, in the actual runtime: browser, CLI, or API client, with a real server.
Identify the project's **money paths** — the two to five journeys that, if broken, mean the product
has no reason to exist — and cover each one completely.

**Bar:** every money path passes end to end from an empty starting state.

### R5 — Adversarial

The full catalog is `05-hardening.md`. Run per slice on that slice's inputs, and again in P5 on the
integrated system with emphasis on the seams.

**Bar:** every finding is fixed with a regression test, or accepted in writing by the founder.

### R6 — Non-functional

Performance against a stated budget at realistic volume; load and soak; accessibility; bundle and
memory; internationalization and time zones; security and dependency scanning.

**Bar:** stated budgets met, with numbers. "Feels fast" is not a measurement, and a budget invented
after the measurement is not a budget.

### R7 — Human

Customer Zero on a real device from an empty account; taste review against the project's design
law; support-readiness (can a support person answer the top five questions from the docs alone?).

**Bar:** a stranger completes the primary job unaided.

### R8 — Production

Post-deploy smoke against production; canary metrics vs. captured baseline; **every monitor fired
on purpose** and confirmed to reach a human; the structured 72-hour watch.

**Bar:** thresholds held for 72 hours, or every incident resolved.

---

## Per-part-type requirements

Find the row for what you are building. If your work spans several rows, apply **all** of them —
requirements union, they do not average.

### Pure function / domain logic
**Rings:** R0 R1 R5
**Minimum cases:**
- Happy path
- Every boundary of every input: empty, zero, one, max, max+1, negative, null/undefined
- Every error branch, asserting the *specific* error, not merely that something threw
- If it does arithmetic: a property test (associativity, idempotency, round-trip, invariants)
- If it parses or formats: round-trip both directions
- If it sorts, dedupes, or groups: empty, single, all-identical, already-sorted, reverse-sorted

### Money, pricing, tax, currency, units
**Rings:** R0 R1 R2 R5 — **and always treat as critical path**
**Minimum cases:** everything above, plus
- Rounding at every boundary, in both directions, including banker's rounding if applicable
- Precision: the smallest unit, and a value with more decimals than the type holds
- Zero, negative, and the maximum representable amount
- Multi-currency: mixed currencies rejected or converted explicitly, never silently added
- **Idempotency**: the same operation applied twice produces one effect
- **Replay**: a duplicated webhook/message does not double-charge
- Partial: partial payment, partial refund, partial delivery, over-payment, over-delivery
- Reconciliation: the sum of the parts equals the whole, asserted as a test
- **Never floating point for money.** If you find float money, that is a Blocker, not a nit.

### Date, time, timezone, scheduling
**Rings:** R0 R1 R5
**Minimum cases:**
- DST spring-forward and fall-back (the hour that doesn't exist, the hour that happens twice)
- Timezones east and west of UTC, including a half-hour and 45-minute offset
- Leap year, Feb 29, Dec 31 → Jan 1, and the end of a month with 30 vs 31 days
- Server timezone ≠ user timezone ≠ database timezone (assert all three explicitly)
- Clock skew and an event timestamped in the future
- Duration across a DST boundary
- Locale-dependent week start and date format

### Auth, permissions, tenancy, data isolation
**Rings:** R0 R1 R2 R3 R5 — **always critical path, no exceptions**
**Minimum cases:**
- Every role × every resource × every action (read/write/delete/list), as a matrix — write the
  matrix down, then implement it as a table-driven test
- Unauthenticated access to every protected route
- **Cross-tenant read AND cross-tenant write**, tested separately (read isolation is commonly
  implemented while write isolation is forgotten)
- ID enumeration: request another tenant's object by its ID directly
- Expired token, revoked token, malformed token, token for a deleted user
- Privilege escalation: can a user grant themselves a role? modify their own permissions? change
  their own tenant?
- The indirect path: can they reach the forbidden data through a *related* object, a search
  result, an export, an error message, or a count?
- Log and error output do not leak other tenants' data

### API route / handler
**Rings:** R0 R1 R2 R3 R5
**Minimum cases:**
- Happy path with a minimal body, and with a maximal body
- Missing required fields; unexpected extra fields; wrong types for each field
- Malformed body (truncated JSON, wrong content type, empty body)
- Oversized payload; deeply nested payload
- Unauthenticated; authenticated but unauthorized; correct auth for the wrong tenant
- Rate limit reached, and behavior after it resets
- Idempotency for anything non-GET that mutates
- Every documented error code actually returned by some test
- The response matches the published contract exactly (R2)

### Database query / schema / migration
**Rings:** R0 R2 R3 R5 R6
**Minimum cases:**
- Empty table; one row; a production-scale row count (timed)
- Null in every nullable column
- Unicode, emoji, RTL text, and 10k-character strings in every text column
- Constraint violations: unique, foreign key, check — each producing a *handled* error
- Transaction rollback leaves no partial state
- Concurrent writes to the same row (test the lock or the version, do not assume)
- N+1 detection on any list endpoint
- **The migration run forward from zero**
- **The rollback executed**, not merely written — this is the one that gets skipped
- Migration timed at production scale, with the lock duration measured
- Backward compatibility: the *old* code running against the *new* schema (this is what actually
  happens during a rolling deploy, for a window of minutes)

### UI component / screen
**Rings:** R0 R1 R5 R7
**Minimum cases:** all nine states (Law 6) — default, loading, empty, error, partial/stale,
disabled, offline, permission-denied, too-much-data — plus:
- Keyboard only: reach every control, activate it, escape from every modal, no trap
- Screen reader: every control has a name and a role
- 320px width, and a very wide viewport
- Dark mode and light mode
- Long content: a 200-character name, a 10,000-row list
- Reduced motion
- Double-click the submit button (does it submit twice?)
- Browser back/forward mid-flow, and refresh mid-flow
- **If the project has a design law skill, its checklist is part of this ring**

### Background job / queue / worker
**Rings:** R0 R1 R3 R5
**Minimum cases:**
- Success; retriable failure; permanent failure
- **Double delivery** — the same message twice (queues are at-least-once; assume it will happen)
- Out-of-order delivery
- Poison message: one that always fails, and does not block the queue forever
- Partial completion then crash: is the state recoverable, or is it wedged?
- Worker killed mid-job (SIGKILL, not graceful) — no half-committed state
- Backlog: 100,000 queued items — does it drain, and at what rate?
- Job takes longer than its visibility timeout and is re-delivered while still running

### Third-party integration
**Rings:** R0 R2 R3 R5 R6
**Minimum cases:**
- Success; 400; 401 (expired credentials); 403; 404; 429 (with and without `Retry-After`); 500;
  502/503
- Timeout, and a slow-but-successful response near the timeout
- Malformed response body; empty body; HTML error page instead of JSON; wrong content type
- **Provider entirely unreachable** — DNS failure, connection refused
- Credentials expired mid-session
- Webhook: replay, out-of-order, forged/invalid signature, duplicate ID
- Their sandbox behaving differently from production (document the differences you find — this is
  a classic launch-day surprise)
- Circuit breaker / degraded mode actually engages, and actually recovers

### File upload / media / documents
**Rings:** R0 R1 R3 R5 R6
**Minimum cases:** empty file; 1-byte file; the maximum size; maximum + 1; wrong extension;
correct extension with wrong magic bytes; a zip bomb; a file with a malicious name (`../../etc/x`,
null bytes, 300-character names); an image with a huge pixel count; upload interrupted at 50%;
duplicate upload; concurrent uploads of the same name; a virus test file (EICAR) if scanning is
claimed.

### Search, list, filter, pagination
**Rings:** R0 R1 R3 R5
**Minimum cases:** no results; exactly one page; exactly one item over a page boundary; last page;
page beyond the end; a filter matching everything; special characters and SQL/regex metacharacters
in the query; sort stability across pages; **an item inserted or deleted between page 1 and page 2**
(the classic pagination bug); very long queries; and results filtered by permission — with the
count matching the visible items.

### Configuration, env vars, secrets, feature flags
**Rings:** R0 R2 R3
**Minimum cases:** every variable missing (does it fail loudly at startup, or silently at 3am?);
present but empty; wrong type; wrong format; a secret accidentally logged (assert it is redacted);
flag on, flag off, and **flag flipped while a user is mid-flow**; a stale cached config after a
change.

### Anything on the critical path
**Rings:** R0 through R8, all of them, no exceptions, at every tier above T0.
The critical path is defined in the charter. If you are unsure whether something is on it, ask:
*if this silently returns the wrong answer for one hour, do we have a serious problem?* If yes, it
is critical path.

---

## The per-slice test budget

For a typical T2 slice, this is what "enough" looks like. Numbers are minimums.

| Ring | Cases | Who | When |
|---|---|---|---|
| R0 | 1 full run, 0 findings | Builder | Every save; again before the gate |
| R1 | 5–20 per unit of logic, per the table above | Builder | During build |
| R2 | 1 per boundary crossed | Builder | During build |
| R3 | 2–5 per cross-module path | Builder | End of build |
| R4 | 1 per money path touched | Builder | End of build |
| R5 | 12 attack families, ~30 probes | **Red Team** | After build |
| — | + 1 regression test per finding | Builder | After red team |
| R0–R4 | **Full re-run from clean state** | **Verifier** | Gate |

**That is three independent passes over the slice and roughly 50–80 distinct assertions for a slice
of real substance.** If your slice has six tests, you have not tested it — you have demonstrated it.

---

## Test quality — the tests themselves are code that can be wrong

A green suite proves nothing if the suite is decorative. Audit against these:

1. **Every test must be able to fail.** Break the implementation deliberately and confirm the test
   goes red. A test that has never failed has never been validated. Do this at least once per slice,
   on the most important test.
2. **Assert on values, not on absence of exceptions.** `expect(result).toEqual(42)`, not
   `expect(() => f()).not.toThrow()`.
3. **No conditional logic in tests.** An `if` in a test means it can silently assert nothing.
4. **One reason to fail per test.** When it goes red, the name should tell you what broke.
5. **No shared mutable state between tests**, and tests must pass in random order — order
   dependence is a bug that appears the day CI parallelizes.
6. **Do not mock what you are testing.** Mocking your own wrapper around the DB tests the wrapper.
   Mock at the network/process boundary only.
7. **Fixed clock, fixed seed, fixed IDs.** Non-deterministic tests get muted, and muted tests are
   how known bugs enter production.
8. **A flaky test is a failing test.** Fix it or delete it. Never re-run until green — "re-run
   until green" is a policy of ignoring your only warning system.
9. **Test names state the behavior**, not the function: `rejects a bid submitted after the RFQ
   closes`, not `test submitBid 3`.
10. **The bug-to-test ratio.** Every bug found anywhere — in review, red team, staging, or
    production — produces a test that fails without the fix. No exceptions. This is what stops a
    codebase from re-breaking the same way forever.

---

## Coverage: what to measure and what to ignore

- **Ignore the global coverage percentage.** It is trivially gamed and tells you nothing about
  whether the important branches are exercised.
- **Do measure coverage on the critical path**, and require it to be complete there. Uncovered
  lines in money, auth, or migration code are gate failures.
- **Mutation testing, if the stack supports it, on domain logic only.** It is the only automated
  measure that answers "would these tests catch a real bug?" Even one run on the money module is
  worth more than a year of line-coverage reports.
- **The real metric is escaped defects**: bugs found in P5+ that R1–R4 should have caught. Track
  them in the postmortem. Every escape names a missing ring for a part type — write it into this
  matrix so the next launch catches it.
