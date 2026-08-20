# 02 — Functions

The unit a reader holds in their head. If it does not fit, they stop reading it and start guessing
about it — and guessing about code is where bugs come from.

---

## 1. One thing, at one level of abstraction (Law 2)

The common failure is not length; it is **mixed altitude**. A function that parses HTTP, applies a
business rule, and writes SQL forces the reader to change mental gears twice per screen.

```
BAD — three altitudes in one function
  read the request body
  check the tax rule for the region      ← business
  build the SQL string                   ← storage
  format the currency for display        ← presentation

GOOD — one altitude; each step is a name you can trust
  const order   = parseOrderRequest(req)
  const total   = calculateTotal(order)
  const saved   = orders.save(total)
  return  presentOrder(saved)
```

The test: **can you describe it in one sentence without "and"?** "Validates and saves the order" is
two functions. Note that the *good* version above is still one thing — "handle an order request" —
because every line is at the same altitude.

## 2. Size

The checker's default is 50 lines, and it is a smell threshold, not a law. But:

- **Under ~15 lines** is where most functions should land.
- **Over 50** is nearly always several functions.
- **Over 100** is a module that has not been extracted yet.

Adjust in the profile with a reason. A table-driven test or a big `switch` mapping codes to
messages is legitimately long and perfectly readable — annotate it and move on.

**Extract when a block needs a comment to explain what it does.** That comment is the name of the
function you have not written yet.

## 3. Nesting is a budget of three (Law 3)

Every level multiplies the states a reader tracks. Past three, nobody tracks them — they assume.

**Invert conditions and return early.** This is nearly always mechanical:

```
BAD                              GOOD
if (user) {                      if (!user)     return error("no user")
  if (user.active) {             if (!user.active) return error("inactive")
    if (hasCredit(user)) {       if (!hasCredit(user)) return error("no credit")
      doTheThing()               doTheThing()
    }
  }
}
```

The good version puts **guards first and the happy path last, unindented**. A reader can find what
the function actually does by looking at the bottom, at the leftmost indentation.

Other ways out of nesting: extract the inner block into a named function; replace a nested
conditional chain with a lookup table; use the language's early-exit idiom (`guard`, `?`, `unless`).

**The idiom exception:** in Go, `if err != nil { return err }` after every call is correct and is
not nesting to be flattened. Record exceptions like this in the profile.

## 4. Parameters

| Count | Verdict |
|---|---|
| 0–2 | Good |
| 3–4 | Fine, if they are genuinely independent |
| 5+ | Group them into a named structure |

A long parameter list usually means a missing concept. `createUser(name, email, street, city, zip,
country)` wants `createUser(name, email, address)` — and now `Address` is a thing you can validate
once (Law 4).

**Boolean parameters are the worst case.** `render(user, true)` is unreadable at the call site, and
the reader must open the definition to learn what `true` meant. Worse, a boolean parameter usually
means the function has two behaviors — which is Law 2 again. Split it, or take a named option.

```
BAD   render(user, true)
GOOD  renderCompact(user)          ← split
GOOD  render(user, { compact: true })   ← named
```

**Argument order matters.** Same-typed adjacent parameters (`copy(a, b)`, `transfer(x, y)`) will be
swapped by someone eventually, and the type system will not catch it. Prefer distinct types or a
named structure for anything dangerous.

## 5. Return values

- **Return early, return often.** Multiple returns are clearer than one return and four flags.
- **One return type.** A function returning `User | null | false | string` makes every caller a
  parser. Use the language's option/result idiom, or throw.
- **Never return a magic sentinel** — `-1`, `""`, `0` meaning "not found". The caller will forget to
  check, and it will look like a valid value. This is the mechanism behind an enormous share of
  real bugs.
- **Do not return a mutable reference to internal state** (Law 8). The caller will mutate it, from
  somewhere you will never think to look.

## 6. Side effects

**A function's name must reveal its effects.** `getUser` that also writes an audit row is a trap —
the name promises a read, so callers will call it in a loop, in a retry, in a test.

- Separate **command** (does something, returns nothing) from **query** (returns something, changes
  nothing). Where a function must do both, the name says so: `popNextJob`.
- **Push side effects to the edges.** A core of pure functions surrounded by a thin shell that does
  I/O is testable without mocks and reusable without a framework. This is Law 6 at function scale.
- **No hidden I/O.** A function that reads an env var, the clock, or the network on the way to
  returning a number cannot be tested and cannot be trusted. Pass those in.

Time and randomness are I/O. `now()` inside business logic makes the logic untestable and its
behavior dependent on when the test runs. Pass a clock.

## 7. Guard the boundary, trust the interior (Law 4)

Validate once, where untrusted data arrives, into a shape that cannot be wrong. Then stop checking.

Defensive `if (x == null)` scattered through the interior is a symptom: it means nobody is sure
where validation happened, so everyone re-does it. That noise hides the one place a real check was
missing, and it teaches readers that the value *can* be null — so they add more checks.

## 8. Function-shaped smells

- A name containing "and" — two functions.
- A comment that divides the body into sections — those sections are functions.
- A parameter that is the same value at every call site — delete it.
- A parameter only used to pass through to another call — restructure.
- Deeply chained access (`a.b.c.d.e`) — the function knows too much about a structure it does not own.
- A function only ever called with a literal — consider inlining or specializing.
- More than about seven local variables — it is holding too much at once.
