---
name: test-craft
description: >-
  The law for tests themselves — how to write one that is worth having, in any language and any
  framework. Load this BEFORE writing or changing any test, fixture, mock, or test helper, and
  before diagnosing a flaky or slow suite. Triggers on: "test", "tests", "unit test", "integration
  test", "e2e", "end to end", "spec", "assert", "assertion", "expect", "mock", "stub", "fake",
  "spy", "double", "fixture", "factory", "seed", "setup", "teardown", "beforeEach", "coverage",
  "flaky", "flake", "intermittent", "fails sometimes", "passes locally", "slow tests", "test
  suite", "TDD", "red green", "snapshot", "golden file", "property test", "fuzz", "regression
  test", "how do I test", "hard to test", "untestable". Owns what to assert, how a test is
  structured, when a double is a fake and when it is a mock, how fixtures stay isolated, how to
  eliminate flakes at the root, and how to test code that was written without tests. Ships a test
  checker that finds committed focused tests, assertion-free tests, sleeps, and conditional logic
  in test bodies, in every language it recognizes. If you are about to write a test you have never
  watched fail, mock the thing you are testing, or add a sleep to fix a race, you needed this skill
  and did not load it.
---

# Test Craft — The Law for Tests

A test suite is not a safety net because it exists. It is a safety net **only to the extent that it
fails when the behavior is wrong**, and passes when the behavior is right. Most suites fail at both
ends: they miss real breakage, and they break on harmless refactors.

**The governing question for every test:** *if this behavior broke, would this test go red — and
for the right reason?* If not, the test is decoration with a maintenance bill.

## Scope — what this skill owns, and what it does not

| Concern | Owned by |
|---|---|
| **How much** testing each kind of code gets — the rings, the minimum counts, the gates | `founder-mode/references/04-test-matrix.md` |
| **How to write a test that is worth having** — structure, assertions, doubles, fixtures, flakes | **this skill** |
| Day-zero test runner setup, and one test watched failing | `project-zero` |
| The code under test — naming, function shape, boundaries | `code-craft` |
| Contract tests against a published API | `api-craft` |

The boundary in one line: **`founder-mode` decides that a payment module needs Ring 1–5 coverage;
this skill decides whether each of those tests is any good.**

---

## The ten laws (non-negotiable)

**Law 1 — A test you have never seen fail is not a test.**
Break the behavior on purpose, watch it go red, restore it. Until then you have not tested the
code — you have tested nothing, and a suite that cannot fail is worse than no suite because it
creates confidence.

**Law 2 — Test behavior, not implementation.**
Assert what the unit does for its caller, never how it does it. A test that breaks when you rename a
private method, reorder two lines, or extract a helper is a test that punishes improvement.

**Law 3 — One reason to fail.**
When a test goes red, its name should tell you what broke before you read the diff. A test
asserting six unrelated things fails for six reasons and tells you none of them.

**Law 4 — The test name states the behavior.**
`rejects a bid submitted after the auction closes`, not `test_bid_2`. The name is what a stranger
reads in CI output at 3am, and it is documentation that cannot go stale.

**Law 5 — Arrange, act, assert — visibly separated.**
One action per test. If there are two acts, there are two tests, and the second is hiding.

**Law 6 — Tests are independent and order-free.**
Any test, alone, in any order, in parallel, repeatedly. Shared mutable state between tests is the
root of most flakes and all of the worst ones.

**Law 7 — Mock what you own and cannot control; fake what you depend on.**
Never mock the thing under test. Prefer a real implementation, then a fake, then a stub, and reach
for a mock only to assert an interaction that has no observable result.

**Law 8 — A flaky test is a defect, not a nuisance.**
Fix it or delete it, the day you find it. A suite with known flakes trains everyone to re-run red
builds, and after that it detects nothing.

**Law 9 — Never sleep. Wait for a condition.**
`sleep(500)` is a race you decided to lose slowly. It is simultaneously too short on a loaded CI box
and wasted time on every other run.

**Law 10 — Coverage is a floor, never a target.**
100% coverage of code with no assertions proves the lines executed. Chasing a number produces tests
that execute everything and verify nothing.

---

## Step 0 — Install the test checker (once per project, ~1 minute)

| Copy this file | To | Purpose |
|---|---|---|
| `scripts/check-tests.mjs` | `scripts/check-tests.mjs` | Finds committed focused tests, assertion-free tests, sleeps, conditionals in test bodies, and empty bodies |

```bash
node scripts/check-tests.mjs
```

**The most valuable rule it has is `focused-test`.** A committed `it.only` or `describe.only`
silently disables the entire rest of the file — CI stays green while testing almost nothing, and
nobody notices for weeks. It is the highest-severity, lowest-visibility defect a suite can carry.

Thresholds and paths come from `.test-craft.json` when present.

**What it cannot check** is most of this document: whether an assertion is meaningful, whether a
double should have been a fake, whether the test would actually catch the bug. Those need judgment.

---

## Workflow — writing a test

### 1. Name the behavior first
Write the test name as a sentence about behavior before writing any code. If you cannot state the
behavior in a sentence, you do not yet know what you are testing.

### 2. Write the assertion first, and watch it fail
Assert the outcome you want, run it, see red for the *right reason* — a wrong value, not an import
error. A test that fails because the file does not compile has not demonstrated anything.

### 3. Make it pass, then break it again
Once green, change the production code to be subtly wrong and confirm the test catches it. **This is
Law 1, and it is the step everyone skips.**

### 4. Check the shape
One action. One reason to fail. No branching. No sleeps. No shared state.

### 5. Verify
```bash
node scripts/check-tests.mjs
```
Then run the suite in a random order and in parallel, twice. Then walk
`references/08-review-checklist.md`.

---

## What ships with this skill

| Path | What it is |
|---|---|
| `scripts/check-tests.mjs` | The test checker: focused tests, assertion-free tests, sleeps, conditionals, empty bodies. Multi-language; `UNKNOWN` over guessing |

No fixture or helper assets: a good fixture is shaped by the project's domain, and a canned one in
one framework would be wrong in every other. The laws and the checker are the portable parts.

## References — load what the task needs

| File | Load it when |
|---|---|
| `references/01-what-to-test.md` | Deciding what deserves a test, at which level, and what does not |
| `references/02-anatomy.md` | Structuring a test: naming, AAA, assertions, parameterized cases |
| `references/03-doubles.md` | Any mock, stub, fake, or spy — and deciding which one you actually need |
| `references/04-fixtures-and-data.md` | Test data, factories, builders, isolation, database state |
| `references/05-flakes.md` | Anything intermittent — the taxonomy of causes and the fix for each |
| `references/06-integration-and-e2e.md` | Tests that cross a process, a network, or a browser |
| `references/07-legacy-and-coverage.md` | Testing code written without tests; what coverage means |
| `references/08-review-checklist.md` | Before reporting any test work complete |

Related skills, where installed: `founder-mode` owns how much testing is required and gates it;
`code-craft` owns the code under test; `api-craft` owns contract tests; `project-zero` sets up the
runner. Not installed is not a blocker.

---

## The failure modes that give it away

- **A test with no assertion.** It proves the code did not throw. Say that out loud and it stops
  sounding like a test.
- **`it.only` committed.** The suite is now one test, and CI is green.
- **A test that mocks the thing it is testing.** It asserts that the mock was configured.
- **`sleep(1000)` to fix a race.** The race is still there; it now takes a second to lose.
- **A test named `test_1`, `works`, or `happy path`.** The name should say what broke.
- **`if` or `for` inside a test body.** The test can now pass without testing anything.
- **A test that fails only in CI, or only on Tuesdays.** Shared state, time, or ordering.
- **A 200-line `beforeEach`.** Every test now depends on state no one can see.
- **Asserting on log output** to check behavior. Logs are not an interface.
- **A snapshot updated without being read.** That is a rubber stamp with a file attached.
- **Mocking the database in a test whose entire purpose is the query.**
- **A test suite nobody runs locally because it takes 20 minutes.** It has stopped being a feedback
  loop and become a deployment ritual.

---

## Scope discipline

More tests are not better tests. This skill never authorizes testing getters, testing the framework,
asserting on private methods, or adding a test for every line to move a coverage number. **A suite
earns its keep by catching real defects at a cost people will keep paying** — every test that
breaks on a harmless refactor is a small tax on every future change, charged forever.
