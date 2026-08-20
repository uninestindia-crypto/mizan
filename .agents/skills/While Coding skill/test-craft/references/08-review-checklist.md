# 08 — The test review checklist

Walk this before reporting any test work complete, and use it when reviewing someone else's tests.
Every line passes or you state the exception and why.

Automated first:

```bash
node scripts/check-tests.mjs
```

Then run the suite **in random order, in parallel, twice**. A suite that has not survived that has
not demonstrated Law 6.

---

## The one question

- [ ] **If this behavior broke, would this test go red — for the right reason?**
- [ ] **You watched it fail.** Broke the production code deliberately, saw red, restored it (Law 1)

## Naming and structure

- [ ] The name states the behavior, not the method: `rejects a bid after the auction closes`
- [ ] No `test_1`, `works`, `happy path`, or a name starting with "should"
- [ ] Arrange / Act / Assert are visibly separated
- [ ] **One action per test**; one reason to fail (Laws 3, 5)
- [ ] Under ~20 lines — longer usually means too many dependencies, a design signal
- [ ] No `if`, no `try/catch` around the act, no loops — parameterized cases instead

## Assertions

- [ ] Asserts the specific value, not `toBeTruthy` / `length > 0`
- [ ] Asserts on stable codes, never on human-readable messages
- [ ] The expected value is a literal, not computed by the code under test
- [ ] Asserts the absence of the wrong thing where it matters (no charge, no email, record gone)
- [ ] Every test has at least one assertion

## Behavior, not implementation (Law 2)

- [ ] A pure refactor of the implementation would leave this test green
- [ ] Does not assert on private methods, internal call counts, or log output
- [ ] Verifies resulting **state** rather than which method was called, wherever possible

## Doubles (Law 7)

- [ ] **Does not mock the thing under test**
- [ ] Prefers real → fake → stub → mock, in that order
- [ ] Does not hand-mock a third-party type you do not own — wraps it and fakes the wrapper
- [ ] Mocks used only where the interaction has no observable result
- [ ] Setup is not longer than the assertion
- [ ] Clock, randomness, and id generation are injected, not reached for

## Isolation (Law 6)

- [ ] Passes alone, in random order, in parallel, and twice in a row
- [ ] No shared mutable state between tests; no module-level caches or counters
- [ ] Creates the data it needs; does not rely on a seeded row or another test's leftovers
- [ ] Unique identifiers per test — no fixed `id: 1`
- [ ] No fixed ports or fixed file paths
- [ ] Teardown is guaranteed, including when the test fails

## Data

- [ ] Builders with defaults, not shared fixture objects
- [ ] The test specifies only the fields it actually depends on
- [ ] Database isolation strategy is real (transaction rollback / truncate / per-worker schema)
- [ ] Snapshots were **read** before being accepted, and are small and deterministic

## Flakes (Laws 8, 9)

- [ ] **No sleeps.** Waits for a condition, with a generous timeout
- [ ] Every async action is awaited
- [ ] No real network calls in unit or integration tests
- [ ] `TZ` and locale pinned in the test environment
- [ ] No dependence on map/set iteration order
- [ ] Any known flake has been root-caused and fixed — **not** wrapped in a retry

## Coverage (Law 10)

- [ ] Uncovered lines were **looked at**, not just counted
- [ ] No test exists purely to move the number
- [ ] Money, identity, permissions, and data-loss paths are covered
- [ ] Branch coverage considered, not only line coverage

## Level (see `01-what-to-test.md`)

- [ ] At the cheapest level that can actually catch the bug
- [ ] **The query is exercised by a real database somewhere** — not mocked everywhere
- [ ] E2E limited to the critical journeys, selecting by role or test id, never CSS or copy
- [ ] Failure modes of external dependencies are tested: timeout, 500, 429, malformed body

## For a bug fix

- [ ] A test that reproduces the bug was written **first** and watched failing
- [ ] It is kept, so the bug cannot return

## Before you report done

- [ ] `node scripts/check-tests.mjs` clean, or findings annotated with reasons
- [ ] The suite passes, **with the output seen** — not assumed
- [ ] It passed in random order and in parallel
- [ ] No `.only` and no new skips committed
- [ ] Anything skipped is stated explicitly, with the reason

**An unverified test claim is an unsupported claim.** "The tests pass" without the output is the
sentence that precedes discovering the suite has not run since Tuesday.
