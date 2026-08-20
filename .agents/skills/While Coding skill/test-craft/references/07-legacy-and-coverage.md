# 07 — Testing untested code, and what coverage means

Two problems that arrive together: a codebase with no tests, and a metric that claims to measure
whether you fixed it.

---

## 1. Coverage is a floor, never a target (Law 10)

**What coverage tells you:** which lines did not execute. That is genuinely useful — uncovered code
is definitely untested.

**What it does not tell you:** whether anything was verified. This test gives 100% coverage of the
function and asserts nothing:

```js
it('processes an order', () => {
  processOrder(anOrder());   // every line ran. nothing was checked.
});
```

**Goodhart's law applies immediately.** The moment coverage becomes a target, people write tests
that execute code without asserting on it — and now you have the maintenance cost of a suite plus
the false confidence of a number.

### Using it well

- **Look at what is uncovered**, not at the percentage. The uncovered list is a to-do list; the
  number is a distraction.
- **Enforce "no decrease" rather than an absolute target.** New code comes with tests; the legacy
  backlog is a separate, scheduled effort.
- **Weight by risk.** 100% on the money module matters; 40% on a rarely-used admin screen is a
  reasonable trade you made deliberately.
- **Branch coverage over line coverage.** `if (a && b)` is one line and four paths.
- **Mutation testing is the real measure**, where the tooling exists: it changes your code and
  checks that a test fails. A surviving mutant is a hole no coverage number will show you. It is
  slow — run it on the critical modules, not the whole repo.

**A single mutation-tested module is worth more than a year of line-coverage reports** — because it
answers the only question that matters: would this suite notice?

## 2. Approaching code with no tests

The trap: you cannot safely refactor without tests, and the code is hard to test without
refactoring. The way out is to buy safety before you change anything.

### Step 1 — Characterization tests

Do not try to write *correct* tests. Write tests that pin down **what it currently does**, bugs
included:

```js
// Not "this is right" — "this is what it does today".
it('currently returns 0 for a null customer', () => {
  expect(calculateDiscount(null)).toBe(0);
});
```

Run the code, observe the output, assert exactly that. You now have a net: any change in behavior
becomes a red test. That is what makes refactoring safe.

**Where behavior looks wrong, write the test for the current behavior anyway** and add a comment
noting the suspected bug. Fixing it is a separate, visible change — not something smuggled inside a
refactor.

### Step 2 — Find a seam

A seam is a place you can change behavior without editing the code around it. Usually created by
injecting a dependency:

```
BEFORE  function chargeCustomer(id) {
          const stripe = new StripeClient(process.env.KEY);   // hard-wired
          ...
        }

AFTER   function chargeCustomer(id, payments = defaultPayments()) {
          ...
        }
```

The default keeps every existing caller working — a strictly additive change — and the parameter
gives tests a way in. This is the smallest possible step toward testability.

### Step 3 — Sprout and wrap

**Sprout:** put new behavior in a new, fully tested function and call it from the old code. The new
code is clean even though its neighborhood is not.

**Wrap:** rename the old function, create a new one with the original name that does the new work
and delegates. Callers are untouched; the new layer is testable.

Both let you add tested code today without a rewrite you cannot finish.

### Step 4 — Test at the widest seam you can reach

If the unit is untestable, go up a level. An integration test through the HTTP endpoint is far
better than nothing, and it does not require touching the code at all. Tighten later.

## 3. Priority order for a legacy codebase

You will not test all of it. Spend the effort where it pays:

1. **Code you are about to change.** Test first, then change. Always.
2. **Where bugs keep happening.** Check the history — defects cluster, and past frequency predicts
   future frequency better than any intuition.
3. **Money, identity, permissions, data loss.**
4. **The two to five critical journeys**, at least at a smoke level.
5. Everything else, opportunistically.

**Do not start with a "add tests everywhere" project.** It has no visible payoff, it stalls, and it
produces exactly the low-value assertion-free tests that give coverage a bad name.

## 4. The regression test rule

**Every bug fix begins with a failing test that reproduces the bug.**

1. Write the test. Watch it fail — it now proves the bug exists.
2. Fix the code. Watch it pass — it now proves the fix works.
3. Keep it. It now proves the bug never comes back.

This is the only category of test guaranteed to have caught a real defect, and it is the cheapest
test you will ever write, because the reproduction is already in your hands.

**Skipping this step is how the same bug ships three times.** If the fix cannot be expressed as a
failing test, you probably do not yet understand the bug.

## 5. When you inherit a suite

- **Run it.** How long does it take, and does it pass twice in a row in random order?
- **Measure the flake rate** before anything else. Fix or delete every flake; a suite with known
  flakes is not a baseline, it is noise.
- **Find the assertion-free tests** — the checker flags them — and either strengthen or delete them.
- **Find the committed `.only`.** It is astonishingly common and means most of a file has not run in
  months.
- **Check the skips.** Each one is a claim that something is tested when it is not.
- **Then, and only then,** trust it enough to use as a baseline for a refactor.

`founder-mode`'s bootstrap records this as the project's baseline, so that later gates can say "your
change added no new failures" rather than arguing about whether a failure is yours.
