# 05 — State, data, and concurrency

Most hard bugs are not wrong logic. They are **two things that disagree about what is true** —
because state was shared, copied, cached, or mutated from somewhere nobody was looking.

---

## 1. Mutation is local, or it is a bug waiting for a schedule (Law 8)

The ladder, best to worst:

| Level | What it looks like |
|---|---|
| **Best** — no mutation | Compute a new value; return it |
| Good — local mutation | A loop building a local accumulator, never escaping the function |
| Tolerable — owned mutation | One object owns its field and controls every write |
| **Worst** — shared mutable state | Two callers hold a reference and both write |

**Shared mutable state is the substrate of every concurrency bug** you will ever spend a week on.
It is also what makes single-threaded code unpredictable, because "who changed this?" has no local
answer — the answer is "anywhere in the program".

Practical rules:

- Prefer returning a new value over editing in place.
- **Never mutate a parameter** unless the name says so (`fillBuffer`, `sortInPlace`). A caller
  passing a value does not expect to get it back changed.
- **Never return a mutable reference to internal state.** The caller will mutate it, from a place
  you will never think to look. Return a copy, or an immutable view.
- Confine unavoidable mutation to the smallest scope that works.

## 2. One source of truth

The same fact stored in two places will disagree. Not might — *will*, and usually on the day it
matters most.

- **Derive, do not duplicate.** If `total` is the sum of the items, compute it; do not store it
  alongside them and try to keep them in sync. Where you must store it (for performance), make one
  side authoritative and the other explicitly a cache, with a stated invalidation rule.
- **A cache with no invalidation strategy is a bug with a timer on it.** Decide the strategy when
  you add the cache, not when it first goes stale in production.
- In UI code this is the single largest source of defects: component state and server state both
  claiming to know the current value.

## 3. Make illegal states unrepresentable (Law 4)

The cheapest bug is the one the type system refuses to let you write.

```
BAD    { status: string, error: string?, data: T? }
       → what does status="success" with error set mean? Someone will produce it.

GOOD   { kind: "loading" }
     | { kind: "success", data: T }
     | { kind: "failure", error: Error }
       → the invalid combinations cannot be constructed
```

Even without a rich type system, the principle holds: **fewer representable states means fewer
states to test and fewer to reason about.**

- Prefer a small enum over a free-form string.
- Prefer a required field over an optional one checked everywhere.
- Prefer a validated wrapper (`Email`, `PositiveInt`, `NonEmptyList`) over a raw primitive that
  every function re-validates.
- Parse, do not validate: turn untrusted input into a trusted *type* at the boundary, so the type
  itself carries the proof.

## 4. Null and absence

Absence is a real state and deserves an explicit representation. What matters is that it is
**handled once, at the boundary**, not defensively re-checked in twenty places.

- Use the language's idiom: `Option`/`Maybe`, nullable types with a checker, or a documented
  convention enforced by a linter.
- **Never use a sentinel** — `-1`, `""`, `0` meaning "missing". The caller will forget to check and
  it will look like a valid value. This mechanism is behind an enormous share of real bugs.
- Distinguish **"absent"** from **"present and empty"** from **"unknown"** when the domain
  distinguishes them. A null balance and a zero balance are not the same fact.

## 5. Data shape

- **Give shape to anything with a fixed structure.** A dict/map passed between functions is an
  undocumented contract that no tool can check and no reader can discover.
- **Keep the domain type free of transport concerns.** The JSON shape, the database row, and the
  domain object are three different things that happen to look similar today. Translate at the
  boundary; otherwise a column rename becomes an API break.
- **Immutable value objects** for things defined by their values (money, dates, coordinates).
  `Money` with a currency prevents adding dollars to euros — a bug that a raw `float` invites.
- **Never represent money as a floating-point number.** Use minor units as integers or a decimal
  type. `0.1 + 0.2 != 0.3` is not a curiosity; it is a reconciliation failure.

## 6. Concurrency

Assume simultaneity for anything a service does. Two requests will touch the same row.

- **Share nothing, or share carefully.** Message passing and immutable data beat locks, because
  they eliminate the class rather than manage it.
- **Where you must lock:** the smallest scope, a consistent acquisition order (this is what prevents
  deadlock), and never hold a lock across I/O.
- **Check-then-act is a race.** `if (!exists(k)) create(k)` is two operations and something happens
  in between. Use the atomic form: a conditional insert, a compare-and-swap, a unique constraint.
- **Let the database do it.** A unique constraint, a transaction, or `SELECT ... FOR UPDATE` is
  more reliable than application-level coordination, because it holds even when two instances of
  your service are running.
- **Optimistic concurrency for user-facing edits:** a version number, and a real "someone else
  changed this" path. Last-write-wins silently destroys work.

## 7. Time

Time is I/O, and treating it as anything else makes code untestable and subtly wrong.

- **Never call `now()` deep inside business logic.** Pass a clock, or pass the timestamp. Otherwise
  the behavior depends on when the test runs, and the tests fail in December.
- **Store UTC. Convert at the edges.** A timestamp with no zone is a defect waiting for a traveler.
- **A date is not a timestamp.** A birthday is a date; it has no time zone and no instant.
- Durations are typed values, not bare numbers. `timeout = 30` — thirty what?
- Never assume monotonicity from wall-clock time; it moves backwards. Use a monotonic clock for
  elapsed time.

## 8. State-shaped smells

- A global that is written after startup.
- A singleton holding request-scoped data.
- The same fact in two fields that must be kept in sync.
- A boolean pair where only three of four combinations are legal.
- A cache with no invalidation and no TTL.
- `if (x == null)` on a value the boundary already guaranteed.
- A function that reads the clock, the environment, or a global — and returns a value.
- Money in a float.
- A "temporary" mutable field used to pass data between two methods of the same object — that is a
  parameter that took the long way round.
