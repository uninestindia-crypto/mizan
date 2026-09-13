# Re-evaluating the two paper books: both measured, neither beats cash

Method and its limits: [`METHOD.md`](METHOD.md). Machine-readable:
[`paper-book-decomposition.json`](paper-book-decomposition.json).

```bash
.venv/Scripts/python.exe scripts/reevaluate_paper_books.py
```

## Flagship: RESOLVED — it marginally underperforms its own equal-weight basket

**Earlier this was reported as REFUSED for want of a price source. That was wrong, and the correction
matters more than the number.** The research cache genuinely cannot value this book — it opened
2026-08-31 and the deepest cache ends 2026-08-27 — and the session reports genuinely carry only
aggregate performance. But `logs/paper_runs/live_paper_status.json`, which the dashboard writes,
holds a **per-name** `current_price` and `market_value` for all 97 open positions. It was in the
repository the whole time; the first search simply did not look at it.

Marked at **2026-09-11** on the book's own recorded marks — the same source for the book and
its benchmark, so any staleness in a quote moves both sides identically and cancels in the difference.

| | Amount (INR) |
|---|---:|
| Entry consideration (97 positions) | 853,407.04 |
| Marked value | 840,749.87 |
| **Gross P&L** | **-12,657.17** |
| Paid costs (lifetime fees, already out of cash) | 1,072.65 |
| Prospective exit costs (accrued, unpaid) | 1,883.28 |
| **Net P&L** | **-15,613.10** |
| Matched benchmark, net (equal-weight, 97 names) | -15,155.72 |
| **Excess over benchmark** | **-457.38** |
| Cash alternative | 0.00 |

**The market explanation does not rescue this book, and neither does it condemn it.** Flagship's
selection is essentially indistinguishable from equal-weighting the same 97 names: it trails its own
basket by 457.38 on 853,407
of notional, which is about 0.054%.
That is not evidence of negative skill; it is evidence of *no measurable* skill over this window.

**Cash beat it.** Net -15,613.10 against 0.00.

**What this still does not test.** The benchmark holds Flagship's own 97 names, so it isolates
*weighting* and says nothing about *selection*. A book that picked 97 poor names from the eligible
universe would track its own basket closely and still have chosen badly. Testing selection needs
point-in-time universe membership at each rebalance, which is a separate measurement not made here.

## XS-Monthly: the displayed loss is dominated by one unpriceable position

Marked at **2026-09-10** using the book's own recorded per-leg marks — the only prices in this
repository that cover its holding period, and the same source the book uses for itself, so any error
in them affects the book and its benchmark identically and cancels in the difference.

| | Amount (INR) |
|---|---:|
| Entry consideration (91 priced legs) | 853,390.98 |
| Marked value | 853,574.90 |
| **Gross P&L** | **+183.92** |
| Paid costs | 0.00 |
| Prospective exit costs | 1,912.01 |
| **Net P&L** | **-1,728.09** |
| Matched benchmark, net (equal-weight, same 91 names) | -8,473.73 |
| **Excess over benchmark** | **+6,745.64** |
| Cash alternative | 0.00 |
| **Unpriced: HEG** | **9,425.00 of capital, no defensible value** |

### What that reframes

The book's own display counts HEG at `13 shares x post-demerger quote` — the pre-demerger share count
multiplied by the post-demerger price, which implicitly asserts the entitlement is worth zero. That
single position is the largest item in its headline loss.

Excluding the position that cannot be valued:

- On its 91 priceable legs the book is **-1,728.09 net**, after accruing the exit
  costs it has not yet paid.
- It **beats its own equal-weight basket by 6,745.64**, so its
  weighting within its selection added value over this window.
- **Cash still beat it**: 0.00 against -1,728.09.
- And **9,425.00 of its capital sits in an entitlement nothing here can price.**
  Whether the book is ahead or behind on total wealth depends entirely on what that turns out to be
  worth, which is exactly what cannot be established from this repository.

**Neither invented nor erased.** The entitlement is not priced. The loss is not reversed. HEG is
excluded from *both* entry consideration and marked value — counting its cost while excluding its
value would implicitly mark it at zero, which is a larger error than the one being corrected, and an
earlier version of this script did exactly that before the ordering was fixed.

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

- **Neither book beats cash over its current window.** Flagship -15,613.10,
  XS-Monthly -1,728.09, cash 0.00.
- **Flagship shows no measurable weighting skill** — it trails its own equal-weight basket by
  457.38, about 0.05% of notional.
- **XS-Monthly's headline loss is dominated by one unpriceable corporate action**, not by selection.
- **Both books' displayed numbers are materially incomplete** without the four-way decomposition:
  XS-Monthly in particular carries 1,912.01 of modelled exit cost it
  has not booked, because it charges the round trip only at closing.

**Does not:**

- **These are short windows.** Flagship opened 2026-08-31 and XS-Monthly 2026-09-02, against declared
  holds of 10 and 21 sessions. Neither has completed a full holding period. No excess figure here is
  evidence of edge, in either direction.
- **The benchmark tests weighting, not selection.** It holds each book's own names, so a book that
  chose poorly from the eligible universe would still track its basket closely. Testing selection
  needs point-in-time universe membership at each rebalance — a separate measurement, not made here.
- **Nothing here promotes anything.** No gate was evaluated, and the standing position is unchanged:
  no model in this repository is promotable.

## Note on re-running these numbers

Both books are **live**. Their marks move, so this decomposition is a snapshot, not a constant. The
XS-Monthly gross figure moved from +4,155.67 to +183.92 between two runs a day
apart purely because the book re-marked — nothing in the method changed. Any figure quoted from this
report should carry its mark date, and re-running is the only way to refresh it:

```bash
.venv/Scripts/python.exe scripts/reevaluate_paper_books.py
```
