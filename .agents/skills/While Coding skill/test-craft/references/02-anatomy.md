# 02 — The anatomy of a test

A test is read far more often than it is written — usually in a CI log, by someone who did not
write it, while something is broken. Optimize for that reader.

---

## 1. The name states the behavior (Law 4)

The name is what appears in CI output. It should make the diff unnecessary.

| Good | Bad |
|---|---|
| `rejects a bid submitted after the auction closes` | `test_bid_2` |
| `returns the cached result on a second identical call` | `works` |
| `refunds only the unused portion of a partial month` | `happy path` |
| `raises ConflictError when the idempotency key is reused with a different body` | `test_error` |

Patterns that work:

- `<does something> when <condition>`
- `<rejects/raises> when <condition>`
- Given/When/Then in the name, where the framework encourages it

Rules:

- **State the behavior, not the method.** `calculateTotal returns 0` is weaker than
  `an empty cart totals zero`.
- **Do not start with "should".** It adds a word to every name and says nothing.
- **Do not number tests.** A number tells the reader to go find the others.
- **Name the specific condition.** `handles errors` covers nine cases badly.

## 2. Arrange, Act, Assert — visibly separated (Law 5)

```js
it('marks an order paid once payment succeeds', async () => {
  // Arrange
  const order = await createOrder({ status: 'pending', totalAmount: 1999 });

  // Act
  const result = await settleOrder(order.id, validCard());

  // Assert
  expect(result.status).toBe('paid');
});
```

Blank lines are enough; the comments are optional once the shape is habitual.

**One act per test.** Two actions means two behaviors, and the second is hiding — when the test
fails you will not know which act broke.

**If Arrange is longer than about ten lines**, the unit has too many dependencies. That is a design
signal from `code-craft` Law 2, not a reason to write a longer setup.

## 3. Assertions

**Assert the specific thing, not the general shape.**

```
WEAK    expect(result).toBeTruthy()
WEAK    expect(result.errors.length).toBeGreaterThan(0)
STRONG  expect(result.status).toBe('paid')
STRONG  expect(result.errors).toEqual([{ field: 'expiryMonth', code: 'OUT_OF_RANGE' }])
```

`toBeTruthy` passes for `1`, `"error"`, `{}`, and `[]`. It is an assertion that something happened,
not that the right thing happened.

**Assert on codes, never on human messages** — messages get reworded, and a test that breaks on
copy edits is a test people delete.

**Assert the absence of the wrong thing** where it matters: that the charge did *not* happen, that
the email was *not* sent, that the deleted record is *gone*. Positive-only suites miss whole
categories of defect.

**Prefer one deep equality to six shallow ones** where the object is the unit of meaning — the
failure output shows the entire diff instead of the first mismatched field.

## 4. Test the test (Law 1)

**This is the step everyone skips, and it is the one that makes the difference.**

1. Write the assertion.
2. Run it. Watch it fail — **for the right reason**. A failure from an import error or a typo has
   demonstrated nothing.
3. Make it pass.
4. **Break the production code deliberately** and confirm it goes red again.
5. Restore.

A test whose failure you have never seen might be passing because it asserts nothing, because it
never runs, because the runner silently skips it, or because the assertion is inside an unreached
branch. All four are common. All four look identical to a green suite.

## 5. Parameterized cases over loops

A loop in a test body reports one result for many inputs, and can run zero times (which is why the
checker flags it):

```
BAD    it('validates emails', () => {
         for (const e of badEmails) expect(isValid(e)).toBe(false)
       })
```

Use the framework's table form, so each case is its own reported result with its own name:

```
GOOD   it.each([
         ['missing @',      'foo.com'],
         ['double dot',     'a@b..com'],
         ['leading space',  ' a@b.com'],
       ])('rejects an email with %s', (_, input) => {
         expect(isValid(input)).toBe(false)
       })
```

Every mainstream framework has this: `it.each`, `@pytest.mark.parametrize`, table-driven subtests in
Go, `@ParameterizedTest` in JUnit, `#[rstest]` in Rust. When one case fails you learn *which* one
from the name alone.

## 6. No logic in tests

No `if`, no `try/catch` around the act, no computing the expected value with the same code under
test.

```
BAD    expect(total).toBe(items.reduce((a, i) => a + i.price, 0))
```

That asserts the implementation equals itself; it passes even when both are wrong.

```
GOOD   expect(total).toBe(4497)   // 1499 + 999 + 1999
```

**Hardcode the expected value.** A literal is verifiable by a human reading it; a computed
expectation is not.

## 7. Setup and teardown

- **`beforeEach` is for the truly universal.** Anything only some tests need belongs in those tests,
  or in a named helper they call explicitly.
- **A long `beforeEach` makes every test depend on state nobody can see.** When a test fails you
  must read the setup to understand it, and the setup is now shared with forty other tests you must
  not break.
- **Prefer an explicit factory call in the test** over implicit shared state:
  `const order = anOrder({ status: 'paid' })` says exactly what this test needs.
- **Teardown must be guaranteed** — the framework's `afterEach`, or a scope guard. A test that
  fails mid-way must still clean up, or it poisons every test after it.

## 8. Size and speed

- A unit test that takes more than a few milliseconds is doing I/O it should not be.
- A test over ~20 lines usually has too much arrangement — a design signal.
- **A suite people will not run locally has stopped being a feedback loop.** If the unit suite takes
  more than a minute or two, that is a defect in the suite, not a fact of life.

## 9. Test code is real code

It is read more than production code and changed as often. `code-craft` applies: clear names, no
duplication that hides intent, no dead helpers, no commented-out cases.

**The one deliberate exception is DRY.** A little duplication in tests is often better than a
helper that hides what a test actually does. When a reader must jump to three helpers to learn what
is being asserted, the abstraction cost more than it saved.
