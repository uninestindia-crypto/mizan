# How the two existing strategies are re-evaluated, and what the numbers are allowed to mean

This document fixes the method **before** the numbers, so nothing below can be chosen after seeing a
result. Results go in `paper-book-decomposition.json` and the comparison report; this file is the
contract they are produced under.

## The question the loss diagnosis could not answer

`reports/mizan_loss_diagnosis_20260910.md` established what each book is worth. It explicitly could
not establish whether either book is **underperforming** or merely **exposed to a market that fell**,
and said so: *"A same-date, same-exposure total-return benchmark is needed to separate market
movement from selection skill."*

That is the gap this closes. A long-only book in a falling market loses money while doing exactly
what it was asked to do. Without a matched comparator that is indistinguishable from a bad model, and
reading it as a bad model would be the wrong conclusion drawn from a real number.

## Four components, never one

Every book is reported as:

| Component | Definition |
|---|---|
| **Gross P&L** | Marked value − entry consideration. No costs of any kind |
| **Paid costs** | Charges already deducted from cash |
| **Prospective exit costs** | What closing every open position would cost, accrued not charged |
| **Net P&L** | Gross − paid − prospective |

Collapsing these into one number is what lets a paper book flatter itself, and both books do it in
different directions:

- **Flagship** has paid its entry fees (₹1,072.65 lifetime, already out of cash) but not its exit
  costs. Its displayed session fee of zero is a *session* measure, not a lifetime one.
- **XS-Monthly** charges its 0.224% round trip **only at closing**, so with zero closed legs it has
  paid nothing at all and its display carries no cost. On its ~₹862,816 of entry notional that is
  about **₹1,932.71** of unbooked liability against a gross figure of −₹1,928.33.

Neither is a bug. Both are display conventions that must be undone before the two books, or either
book and a benchmark, can be compared.

## The benchmark: same names, equal weights

The comparator is an **equal-weight basket of the same names the book actually holds**, entered at
the same sessions, on the same total notional, charged the same cost model.

Same names deliberately. A broad index would conflate two questions: whether the *universe* the book
selected from rose or fell, and whether the book's *weighting within it* was good. Holding the names
constant and varying only the weights isolates the second, which is the only part the strategy
controls once its selection is made.

Cash is reported alongside at exactly ₹0. For a book that could have abstained, cash is a live
alternative rather than a rhetorical one.

**What this benchmark does not do:** it does not test the *selection*. A book that picked 97 bad
names from 423 will match its own equal-weight basket closely and still have chosen badly. Testing
selection needs a universe-level comparator, which needs point-in-time universe membership at each
rebalance — that is a separate measurement and it is not claimed here.

## One common valuation date

Both books and both benchmarks are marked at **one date**, the last session every instrument can be
priced at from the research cache (2026-08-21).

This is deliberately **not** a restatement of either book's live valuation. The books mark against
live quotes on later dates, and the loss diagnosis already noted their marks are not synchronised
with each other. A like-for-like comparison needs one date for all four series; a live valuation
needs the live quote. They answer different questions and are reported separately rather than mixed.

## HEG: excluded from marked value, disclosed as unpriced

HEG's demerger has ex-date and record date 2026-09-07, entitling one resulting-company share per HEG
share per the company filing. The resulting company has **no price anywhere in this repository** —
the market cache ends 2026-08-21.

The position is therefore **excluded from marked value and disclosed as an unpriced asset**, not
valued at zero. Valuing it at zero would assert the entitlement is worthless, which no evidence here
supports; marking the remaining HEG quote against the unchanged share count — which is what the book
currently does — asserts the same thing implicitly, and is where about ₹6,084 of the book's displayed
loss comes from.

Per the brief: *"do not invent a price or erase the loss."* Neither is done. The loss is not reversed,
the entitlement is not priced, and both facts are stated.

## What is read and what is written

**Read only**, and structurally so: the re-evaluation opens no file for writing under `logs/`. Both
books, their weights, their portfolio state and their history are inputs.

The XS-Monthly state is under a live Hermes claim (`20260903-hermes-xs-monthly-screen-new.md`) and a
scheduled task writes to it. Correcting the HEG accounting *inside* that book would mean mutating a
live file another agent owns while its own process is running — so the corrected accounting is
produced **alongside** it, with a notice filed for its owner. That preserves the paper history the
brief requires preserving, and leaves the decision to change a running book with the person who owns
it.

## Reproduce

```bash
.venv/Scripts/python.exe scripts/reevaluate_paper_books.py
```

## Verdict ceiling

Nothing in this re-evaluation can promote anything. It measures two existing books against a
benchmark and cash at one date. A book that beats its benchmark here has shown one favourable
comparison over a single short window of a few sessions, on a survivorship-biased universe, which is
far below any promotion gate — and the standing position remains that no model in this repository is
promotable, best deflated Sharpe 0.397794 against a 0.95 requirement.
