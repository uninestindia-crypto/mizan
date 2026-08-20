# 01 — What to test, and at what level

`founder-mode/references/04-test-matrix.md` decides **how much** testing each kind of code gets.
This file decides **what is worth asserting** once you are writing one.

---

## 1. The one question

> **If this behavior broke, would this test go red — and for the right reason?**

Everything else follows. A test that would stay green while the feature is broken is worse than no
test, because it produces confidence. A test that goes red when nothing broke is worse than no test,
because it trains people to ignore red.

## 2. Test behavior, not implementation (Law 2)

**Behavior** is what a caller can observe: the return value, the raised error, the state change they
can query, the message they receive. **Implementation** is how you got there.

| Assert this | Not this |
|---|---|
| The order comes back `paid` | `markPaid()` was called |
| A second charge with the same key returns the first result | The cache was hit |
| An invalid email is rejected with `VALIDATION_FAILED` | `validateEmail()` returned false |
| The email was queued | `EmailService.send` was called with 3 arguments |

**The test for whether you are testing implementation:** could a refactor that keeps behavior
identical break this test? If yes, you have coupled to the how — and you have made the codebase
harder to improve, which is the opposite of what tests are for.

This is why over-mocking is so damaging (see `03-doubles.md`): a mock asserts *how* by construction.

## 3. What deserves a test

In descending order of value:

1. **Anything with money, identity, permissions, or data loss.** Always. No exceptions.
2. **Business rules with branches** — eligibility, pricing, state transitions, tax, limits.
3. **Every bug you fix.** Write the failing test first; it is the only test guaranteed to have
   caught a real defect.
4. **Boundaries** — empty, one, many, maximum, over-maximum, zero, negative, null.
5. **Failure paths** — the ones never exercised in development and always exercised in production.
6. **Contracts other people depend on** (see `api-craft`).
7. **Anything you had to think hard about.** Difficulty is a proxy for defect probability.
8. **Concurrency and ordering**, where the code assumes either.

## 4. What does not deserve a test

- **Getters, setters, and pass-throughs.** You are testing the language.
- **The framework.** Its maintainers already did, and their tests are better than yours.
- **Third-party libraries.** Test *your integration* with them, not them.
- **Private methods directly.** Test them through the public surface; if that is impossible, the
  private method wants to be its own unit with its own public surface.
- **Generated code.**
- **Exact log strings.** Logs are not an interface, and asserting on them freezes wording.
- **Trivially obvious constants.**

Adding tests here does not raise quality; it raises the cost of every future change.

## 5. Choosing the level

| Level | Scope | Speed | Use it for |
|---|---|---|---|
| **Unit** | One unit, dependencies faked | ms | Logic, branches, calculations, edge cases |
| **Integration** | Several real components, real DB | 100ms–s | Queries, transactions, serialization, wiring |
| **End-to-end** | The whole system as a user | s–min | A handful of critical journeys, only |

**Push tests down to the cheapest level that can still catch the bug.** A pricing rule tested
through the browser is slow, flaky, and tells you almost nothing about which branch is wrong.

**But do not push a bug down to a level that cannot see it.** The most common blind spot is
mocking the database in a test whose entire purpose is the query — the query is never executed, so
the SQL bug ships. That test proves your mock returns what you told it to.

### The distribution

Many unit tests, fewer integration tests, very few end-to-end. Not because of a diagram, but
because of arithmetic: E2E tests are slow, and slow suites stop being run.

The most common real-world failure is not the wrong shape — it is a suite with plenty of unit tests
that all mock the database, and no integration test anywhere. Every unit passes and the system does
not work.

## 6. One behavior per test (Law 3)

```
BAD   it('handles orders', () => {
        expect(create().status).toBe('pending')
        expect(pay().status).toBe('paid')
        expect(refund().status).toBe('refunded')
      })
```

Three behaviors. When it goes red, you know only "orders are broken", and the second and third
assertions never ran — so you cannot see whether they also broke.

```
GOOD  it('starts a new order as pending', ...)
      it('marks an order paid once payment succeeds', ...)
      it('marks a refunded order as refunded', ...)
```

**Several assertions about one behavior are fine** — asserting three fields of one returned object
is one behavior. The test is whether they would fail for the same reason.

## 7. Boundaries and the cases people forget

For any input, test: **zero, one, many, maximum, over-maximum, and malformed**.

The ones consistently missed:

- **Empty collections.** The most common production `NullPointerException` in existence.
- **Exactly at the limit**, and one past it.
- **Duplicate submissions** — the retry case (`api-craft` Law 5).
- **Concurrent access** to the same row.
- **Unicode, emoji, and RTL text** in anything that measures or truncates a string.
- **Time zones and DST** in anything that does date arithmetic.
- **Very large inputs** — the 90-character name, the 10MB payload.
- **The second call.** An enormous number of bugs only appear on the second invocation, because the
  first one initialized something.

## 8. Property-based testing, where it fits

For pure functions with algebraic properties — parsers, serializers, sorters, money arithmetic — a
property test generates hundreds of cases and finds the boundary you did not think of:

```
for any order o:  parse(serialize(o)) == o
for any a, b:     add(a, b) == add(b, a)
for any list l:   sort(l).length == l.length
```

It complements example-based tests; it does not replace them. Examples document intent
concretely — properties find the case nobody imagined. Use both where the shape fits, and neither
where it does not.
