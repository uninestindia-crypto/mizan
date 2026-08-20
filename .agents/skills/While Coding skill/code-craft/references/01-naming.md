# 01 — Naming

Naming is the highest-leverage thing you do, and the cheapest to get right. A good name removes the
need for a comment, a doc, and a question in review. A bad one costs every future reader a trip to
the definition — forever.

**The test:** could a competent stranger, reading only this name and its type, predict what it holds
or does? If not, rename it. Do this before you ask whether the code works.

---

## 1. Name for intent, not implementation

| Do | Don't | Why |
|---|---|---|
| `expiredSessions` | `list2`, `filteredData` | States what it *is* |
| `retryAfter` | `num` | States what it *means* |
| `isEligible` | `flag`, `check` | Reads as an assertion |
| `sendInvoice` | `handleInvoice`, `processInvoice` | States what it *does* |
| `usersByEmail` | `userMap` | States the key, which is the useful part |

The container is never the name. `userArray`, `configDict`, `dataList` tell the reader something
the type already said, and become lies the moment the structure changes.

**"Process", "handle", "manage" are placeholders.** They describe that *something* happens. If a
function is genuinely a coordinator, name what it coordinates: `settleInvoices`, not
`processInvoices`.

## 2. Length scales with scope

| Scope | Length | Example |
|---|---|---|
| Two-line closure, loop index | 1–2 chars is fine | `i`, `x`, `e` |
| Inside one short function | One word | `total`, `user` |
| Module-level | Two or three words | `pendingSettlements` |
| Public API / exported | Fully explicit | `calculateSettlementTotal` |

A name's cost is paid by its readers, and a public name has the most. Inversely, `i` in a
three-line loop is *clearer* than `currentIterationIndex`, which is noise.

## 3. The shape of a name by what it is

- **Functions are verb phrases.** `fetchUser`, `isExpired`, `toJSON`, `withRetry`.
- **Values are noun phrases.** `invoice`, `retryCount`, `defaultTimeout`.
- **Booleans are assertions.** `isActive`, `hasPermission`, `canRetry`, `shouldRetry`. Never
  `status`, `flag`, or a negation — `isNotReady` produces `if (!isNotReady)`, which nobody parses
  correctly at speed.
- **Collections are plural.** `users`, not `userList`.
- **Types are nouns.** `Invoice`, `RetryPolicy`. Never `IInvoice`, `InvoiceImpl`, `AbstractInvoice`
  — those name a language artifact, not a concept.

## 4. Say the same thing the same way

Pick one word per concept and never vary it. `fetch`/`get`/`retrieve`/`load` for the same operation
means four searches instead of one, and it makes a reader wonder what the difference is — because a
careful author would have had one.

Record the chosen verbs in the profile. The common pairs worth settling once:

| Concept | Pick one |
|---|---|
| Read something | `get` (local) vs `fetch` (remote) — decide, then keep it |
| Create | `create` vs `new` vs `make` |
| Remove | `delete` vs `remove` |
| Convert | `to<X>` vs `as<X>` vs `parse` |

**Consistency beats correctness here.** A slightly worse word used everywhere is better than the
best word used half the time.

## 5. Use the domain's words

The user calls it an "order". The schema calls it `txn_hdr`. **Put the user's word in the code.**
Where the two must differ, translate at the boundary and only there — never let `txn_hdr` reach the
business logic, and never invent a third word that neither the user nor the database uses.

If the domain has a precise term — *chargeback*, *tare weight*, *ex-dividend* — use exactly it.
Renaming a term of art to something more "readable" destroys information and makes the code
unsearchable against the domain's own documentation.

## 6. Names that are always wrong

| Name | The problem |
|---|---|
| `data`, `info`, `item`, `obj`, `thing`, `value` | A decision declined |
| `temp`, `tmp`, `foo`, `test1` | Survives to production every time |
| `x2`, `userNew`, `handler2`, `utilsFinal` | A version, not a name. What made it new? |
| `Manager`, `Helper`, `Util`, `Service`, `Processor` (alone) | Names a role, not a responsibility |
| `doWork`, `execute`, `run`, `perform` | Every function does work |
| `myList`, `theUser` | The possessive adds nothing |
| Abbreviations you invented — `usrCnt`, `calcAmt` | Saves four characters, costs every reader |

Established abbreviations are fine: `id`, `url`, `http`, `db`, `max`, `ctx`, and whatever the
domain genuinely abbreviates. The test is whether it is standard *outside* your codebase.

## 7. Negative names and double negatives

`disableFoo`, `notReady`, `skipValidation`, `ignoreErrors` all produce `if (!disableFoo)` at some
call site, and that is a bug waiting for a tired reader. Prefer the positive: `enableFoo`,
`isReady`, `validate`, `raiseErrors`.

## 8. When you cannot find a name

**Difficulty naming something is information, not an obstacle.** It almost always means one of:

- The thing does more than one thing → split it, and each part will name itself (Law 2).
- The thing is not a real concept → it is an accident of implementation, and probably should be
  inlined.
- You do not yet understand the domain → go find out. The name is downstream of understanding.

The wrong response is to pick `processData` and move on. That converts a design problem you noticed
into a comprehension cost every future reader pays.

## 9. Rename freely

Names are the cheapest thing to change and the most expensive to leave wrong. Every editor renames
safely across a project. When a name stops fitting — because the code changed, or because you now
understand it better — change it in that moment.

A name that was right when written and is wrong now is worse than one that was always wrong,
because readers trust it.
