# Model card — XS-Monthly, frozen cross-sectional momentum rule

## Identity

| | |
|---|---|
| Rule | Trailing 21-session close momentum → top 20% → next-open entry → hold 21 sessions → exit at open |
| Cost model | 0.224% round trip, charged once at close |
| Implementation | `src/quant_system/research_xs_monthly/` |
| Paper book | `logs/xs_monthly_new/paper_watch/state.json` (live, forward paper) |
| Verdict | **`RESEARCH_ONLY`** — below cash on its priceable legs |

## What it is

**Not a trained model.** A frozen rule with fixed constants, preserved exactly as declared — tuning
it is forbidden, and this card exists to record its accounting, not to propose a change. Its
constants are shared with `screen.py` so the paper watch and the screen cannot drift apart.

## Results — four-way decomposition, marked 2026-09-10

Gross P&L, paid costs, prospective exit costs and net P&L are reported **separately**, because this
book charges its round trip only at closing and has closed nothing.

| | Amount (INR) |
|---|---:|
| Entry consideration (91 priced legs) | 853,390.98 |
| Marked value | 853,574.90 |
| **Gross P&L** | **+183.92** |
| Paid costs | 0.00 |
| Prospective exit costs (accrued, unpaid) | 1,912.01 |
| **Net P&L** | **-1,728.09** |
| Matched benchmark, net (equal-weight, same 91 names) | -8,473.73 |
| **Excess over benchmark** | **+6,745.64** |
| Cash alternative | **0.00** |
| **Unpriced: HEG** | **9,425.00 of capital, no defensible value** |

**Cash beat it.** Net -1,728.09 against 0.00. It does beat its own equal-weight basket by 6,745.64,
so its weighting within its selection added value over this window — but the benchmark holds the
book's own names, so it tests *weighting*, not *selection*.

## The unpriceable position — neither invented nor erased

HEG underwent a demerger with ex-date **2026-09-07**, entitling one resulting-company share per HEG
share. The resulting company (named by the issuer's own filing as **HEG Graphite Limited**) has **no
price anywhere in this repository**: the market cache's window closes 2026-08-21.

The book's raw display marked 13 shares at the post-demerger quote, booking about **INR 6,084** of
"loss" — which silently asserts the entitlement is worth zero. Three treatments are all wrong:

| Treatment | Why it is wrong |
|---|---|
| Mark at the post-event quote on unchanged shares | Asserts the entitlement is worthless |
| Reverse the 6,084 | Asserts it is worth exactly the quote drop |
| Invent a price | Fabricates evidence |

The defensible treatment is to carry it as an **unpriced asset**: state it exists, state its entry
cost, state that it cannot be valued. `settle_positions(..., unpriced_entitlements=...)` returns such
a leg with `unpriced: true` and **no** `market_value`, `unrealized` or `gross_mark` key — omitted
rather than zeroed, so a consumer summing values skips the leg instead of quietly adding nothing.

HEG is excluded from **both** entry consideration and marked value. Counting its cost while excluding
its value would implicitly mark it at zero — a larger error than the one being corrected, and one an
earlier version of the script actually made before the ordering was fixed.

## Reproduce

```bash
.venv/Scripts/python.exe scripts/reevaluate_paper_books.py
```

```bash
.venv/Scripts/python.exe -m pytest tests/test_xs_monthly_unpriced_entitlement.py -q
```

## Known failures and limitations

- **Below cash.** -1,728.09 against 0.00.
- **The window is far too short to mean anything.** The book opened 2026-09-02 against a declared
  21-session hold and has not completed one holding period. No excess figure here is evidence of
  edge in either direction.
- **The unbooked liability is 86% of the net result.** 1,912.01 of modelled exit cost is accrued but
  not charged by the book's own display, which shows no cost at all while carrying the full
  liability.
- **The code path is corrected; the saved state is not.** No file under `logs/` was written and no
  saved history was altered — rewriting a saved valuation is a different history, not a correction.
  Wiring the caller is the decision of the record that owns the running book.
- The benchmark tests weighting, not selection.

## Must not be used for

Live-money routing, or any claim of edge from a book that has not completed one holding period.
