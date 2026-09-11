# Re-evaluating the two paper books: one refused, one reframed

Method and its limits: [`METHOD.md`](METHOD.md). Machine-readable:
[`paper-book-decomposition.json`](paper-book-decomposition.json).

```bash
.venv/Scripts/python.exe scripts/reevaluate_paper_books.py
```

## Flagship: REFUSED, and the refusal is the finding

```text
REFUSED: mark date 2026-08-21 precedes the earliest entry 2026-08-31.
Marking here would value a position at a price from before it was opened.
No price source in this repository covers this book's holding period.
```

Flagship opened all 97 positions on **2026-08-31**. The deepest research cache ends **2026-08-27**;
the all-market cache ends **2026-08-21**. The book marks against live Upstox quotes that are not
persisted anywhere as research data, and its session reports carry only aggregate performance — no
per-name marks.

**So a matched benchmark for Flagship cannot be computed from anything in this repository.** Not
"is hard to"; cannot. This is a precise external blocker: it needs either a market-cache refresh
covering 2026-08-31 onward, or per-name marks persisted in the session reports.

### The near-miss worth recording

The first version of this script did **not** refuse. It called `_price_on_or_before(2026-08-21)`,
got the last price at or before that date, and reported:

```text
gross P&L              :      +9,229.09
NET P&L                :      +6,224.14
benchmark net P&L      :     +14,493.39
EXCESS over benchmark  :      -8,269.25
```

Every one of those numbers is meaningless — it is the difference between an entry price and a price
from **ten days before the position existed**. Nothing about the output looked wrong: the magnitudes
were plausible, the benchmark comparison was coherent, and the conclusion ("the book underperforms
its own basket") was the kind of thing one expects to find.

The script now raises `MarkDateBeforeEntry` instead. A valuation date before entry is a typed
refusal, not a number.

## XS-Monthly: the displayed loss is dominated by one unpriceable position

Marked at **2026-09-09** using the book's own recorded per-leg marks — the only prices in this
repository that cover its holding period, and the same source the book uses for itself, so any error
in them affects the book and its benchmark identically and cancels in the difference.

| | Amount (INR) |
|---|---:|
| Entry consideration (91 priced legs) | 853,390.98 |
| Marked value | 857,546.65 |
| **Gross P&L** | **+4,155.67** |
| Paid costs | 0.00 |
| Prospective exit costs | 1,920.90 |
| **Net P&L** | **+2,234.77** |
| Matched benchmark, net (equal-weight, same 91 names) | −4,182.41 |
| **Excess over benchmark** | **+6,417.18** |
| Cash alternative | 0.00 |
| **Unpriced: HEG** | **9,425.00 of capital, no defensible value** |

**The +4,155.67 reproduces the loss diagnosis exactly.** That report computed "other 98 selected legs
combined = INR +4,155.67" by a different route; this is an independent reproduction of its
arithmetic, which is the check that says the decomposition is reading the book correctly.

### What that reframes

The book **displays** a gross loss of −1,928.33. That figure is
`(other legs +4,155.67) + (HEG −6,084.00)`, and the HEG component is
`13 shares × post-demerger quote` — the pre-demerger share count multiplied by the post-demerger
price, which implicitly asserts the entitlement is worth zero.

Excluding the position that cannot be valued:

- On its 91 priceable legs the book is **+2,234.77 net**, after accruing the exit costs it has not
  yet paid.
- It **beats its own equal-weight basket by 6,417.18**, so its weighting within its selection added
  value over the window.
- It is still **behind cash** on a total-wealth basis only once the unpriced 9,425.00 is accounted
  for — and whether it is behind cash depends entirely on what that entitlement turns out to be
  worth, which is exactly what nothing here can establish.

**Neither invented nor erased.** The entitlement is not priced. The loss is not reversed. HEG is
excluded from *both* entry consideration and marked value — counting its cost while excluding its
value would have implicitly marked it at zero, which is a larger error than the one being corrected,
and an earlier version of this script did exactly that before the ordering was fixed.

### The unbooked liability, quantified

XS-Monthly charges its 0.224% round trip **at closing**, and has closed nothing. Its display
therefore carries **no cost at all** while carrying the full liability:

```text
prospective exit costs : 1,920.90
```

That is 86% of the book's entire net result. Any comparison of this book against anything — the other
book, a benchmark, or cash — is wrong by that amount until it is accrued.

## What this does and does not establish

**Does:**

- XS-Monthly's headline loss is an accounting artifact of one unpriceable corporate action, not a
  selection failure. Its weighting beat its own basket over this window.
- Flagship cannot be evaluated against a benchmark from repository data at all.
- Both books' displayed numbers are materially incomplete without the four-way decomposition.

**Does not:**

- **This is one window of a few sessions.** XS-Monthly entered on 2026-09-02 and is marked
  2026-09-09 — five sessions of a declared 21-session hold, on 91 names. That is not evidence of
  edge, and the +6,417.18 excess is well inside what noise produces at this sample size.
- **The benchmark tests weighting, not selection.** A book that picked 91 poor names from 423 will
  track its own equal-weight basket closely and still have chosen badly. Testing selection needs
  point-in-time universe membership at each rebalance, which is a separate measurement not made here.
- **Nothing here promotes anything.** No gate was evaluated, and the standing position is unchanged:
  no model in this repository is promotable.
