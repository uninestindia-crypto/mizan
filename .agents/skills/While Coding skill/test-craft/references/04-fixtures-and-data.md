# 04 — Fixtures, test data, and isolation

Most flakes and most unreadable tests come from the same root: **state shared between tests**.

---

## 1. Every test is independent (Law 6)

The bar: **any test, alone, in any order, in parallel, repeatedly.**

```bash
# Run the suite in a random order. Twice. It must pass both times.
<runner> --shuffle          # or --random-order, -shuffle=on, -p
```

**Randomize order in CI permanently.** Order dependence is invisible until the day someone adds a
test in the middle and twelve unrelated ones fail — usually the week before a release.

If a test only passes when run after another, that is a defect in the first test, not a scheduling
requirement.

## 2. Builders over fixtures

A shared fixture file is a magnet: every test adds one field, and eventually no test can change
anything without breaking others.

```
BAD    const user = fixtures.users.standard   // what makes it "standard"? who else uses it?
```

**Use a builder with sensible defaults, and state only what matters to this test:**

```ts
const anOrder = (overrides = {}) => ({
  id: `ord_${counter++}`,
  status: 'pending',
  totalAmount: 1999,
  currency: 'USD',
  createdAt: new Date('2026-01-01T00:00:00Z'),
  ...overrides,
});

// The test says exactly what it depends on:
const order = anOrder({ status: 'paid' });
```

Why this is better:

- **The test documents its own preconditions.** A reader sees `status: 'paid'` and knows that is the
  relevant fact.
- Adding a field later does not break existing tests.
- No coupling between tests through a shared object.

**Name builders for the domain**: `anOrder`, `aPaidOrder`, `aUserWithoutBilling`. A named builder
for a common case is clearer than four overrides repeated everywhere.

## 3. Only specify what the test depends on

```
BAD    anOrder({ id: 'ord_1', status: 'paid', totalAmount: 1999, currency: 'USD',
                 createdAt: ..., customerId: ..., lineItems: [...] })
```

A reader cannot tell which of those seven fields matters. If the test is about refund eligibility
and only `status` matters, say `anOrder({ status: 'paid' })` and let the builder supply the rest.

**Unspecified means irrelevant.** That is the signal you are sending, so make it true.

## 4. Database state

| Strategy | Isolation | Speed | Use when |
|---|---|---|---|
| **Transaction rollback per test** | Excellent | Fast | Default for most suites |
| **Truncate between tests** | Good | Medium | When the code under test manages transactions |
| **Fresh schema per worker** | Excellent | Slow start | Parallel suites |
| **Shared seeded database** | **None** | Fast | Almost never — this is the flake factory |

**Transaction rollback is the default worth reaching for**: begin before each test, roll back after.
Nothing persists, tests cannot see each other's rows, and it is fast.

It does not work when the code under test commits its own transactions. Then truncate, or give each
parallel worker its own schema.

**Never share a seeded database across tests that write.** It works until two tests touch the same
row, and then it fails once a week for a year.

### Seed data

Keep it minimal — reference data only: currencies, countries, roles. **Business data belongs in the
test that needs it**, created by a builder. A seed file with 200 orders means every test depends on
data it did not ask for and cannot see.

## 5. Parallelism

Assume the suite runs in parallel; it eventually will.

- **No shared mutable module state.** A module-level cache, counter, or singleton is shared across
  every test in the worker.
- **No fixed ports.** Bind to port 0 and read the assigned one.
- **No fixed file paths.** Use a per-test temporary directory and clean it up.
- **Unique keys per test** — `ord_${uuid()}`, not `ord_1`. Two parallel tests inserting the same id
  is a unique-constraint failure that looks random.
- **No shared external accounts.** Two tests hitting the same sandbox account race.

## 6. Snapshots and golden files

Useful for large structured output — rendered markup, generated schemas, formatter results.
Dangerous everywhere else.

**The rules that keep them honest:**

- **Read every snapshot diff before accepting it.** An auto-accepted snapshot is a rubber stamp with
  a file attached, and it will happily record a bug as the new expectation.
- **Never accept snapshots in bulk** (`-u` across the suite) unless you have genuinely reviewed the
  change.
- **Keep them small and focused.** A 500-line snapshot fails on every unrelated change, so nobody
  reads it, so it protects nothing.
- **Never snapshot anything non-deterministic** — timestamps, ids, ordering — without normalizing
  first.
- **Do not snapshot as a substitute for an assertion.** `expect(total).toBe(4497)` states intent;
  a snapshot records whatever happened.

## 7. Determinism

A test must produce the same result on every machine, every run, forever.

| Source of nondeterminism | Fix |
|---|---|
| Wall-clock time | Inject a clock; pin the instant |
| `random()`, UUIDs | Fixed seed, or an injected generator |
| Map/set iteration order | Sort before asserting |
| Concurrency | Await everything; assert on final state, not timing |
| Locale, time zone, encoding | Pin them in the test environment |
| Network | Do not use it in unit or integration tests |
| Filesystem ordering | Sort directory listings |

**Pin `TZ` and `LANG` in the test environment.** A suite that passes in UTC and fails in
`Asia/Kolkata` is a suite that will fail for exactly one person, who will be told "works on my
machine".

## 8. The data that finds bugs

Realistic data finds more defects than `foo`/`bar`:

- Names with apostrophes, hyphens, and non-Latin scripts — `O'Brien`, `李`, `Þórð`
- Emoji in any free-text field, especially one you truncate
- Right-to-left text
- Very long values at the field limit, and one over
- Money at zero, negative, and the maximum
- Dates at DST boundaries, on 29 February, and at year end
- Empty strings versus null versus absent

Put a handful of these in your builders' defaults rather than only in dedicated tests. Then every
test quietly exercises them, and the truncation bug surfaces in the test you already had.
