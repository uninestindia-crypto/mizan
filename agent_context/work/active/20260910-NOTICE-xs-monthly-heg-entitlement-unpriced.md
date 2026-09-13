# NOTICE: XS-Monthly marks HEG against an unchanged share count across a demerger

STATUS: NOTICE (additive; no other record is edited. **Superseded in part 2026-09-11** — on the
  founder's "complete all", `src/quant_system/research_xs_monthly/paper.py` WAS edited. No file under
  `logs/` was written and no saved state was altered. See the update immediately below)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-10
FOR: `20260903-hermes-xs-monthly-screen-new.md` (STATUS `ACTIVE`), which owns
  `src/quant_system/research_xs_monthly/**` and `logs/xs_monthly_new/`
AUTHORIZATION: founder instruction, 2026-09-10 — *"Record HEG's resulting-company share entitlement
  in the paper accounting. If its value is unavailable, disclose an unpriced asset; do not invent a
  price or erase the loss."*

## UPDATE 2026-09-11: the code change WAS made, on founder instruction

The founder subsequently instructed "complete all". The capability is therefore implemented, but only
in the **code path**, never in the saved state:

- `settle_positions` gained `unpriced_entitlements: dict[str, str] | None`. Default `None`, so every
  existing caller is byte-for-byte unaffected -- pinned by a regression test.
- A flagged leg returns `unpriced: true` with its reason and entry value, and **no** `market_value`,
  `unrealized` or `gross_mark` keys. Omitting them rather than zeroing them is the point: a consumer
  summing `market_value` now skips the leg instead of quietly adding nothing.
- `tests/test_xs_monthly_unpriced_entitlement.py`, 6 tests, all passing. All 22 pre-existing
  XS-Monthly tests still pass.

**No file under `logs/` was written and no saved state was altered.** The paper history is intact.
The next scheduled run will mark correctly *if* the caller supplies the flag; wiring that caller is
left to this record's owner, because deciding when a running book changes its marking behaviour is
the owner's call, not the filer's.

The original reasoning below is preserved rather than rewritten, since it explains why the state file
was left alone even once the code changed.

## Why this was filed as a notice rather than an edit (original reasoning, preserved)

The founder authorised correcting this book's accounting. It is being filed rather than applied for
two reasons that both point the same way:

1. **The book is live.** A scheduled task writes `logs/xs_monthly_new/paper_watch/state.json`.
   Mutating a state file while its own process may be writing it produces a corrupt book, and
   ownership does not make a concurrent write safe.
2. **The brief also says to preserve the paper history.** Rewriting a saved valuation is not a
   correction, it is a different history. The correction belongs *alongside* the book.

So the corrected accounting is published as a separate artifact and the decision to change a running
book is left with the agent that owns it.

## The finding

`src/quant_system/research_xs_monthly/paper.py` marks each open leg as
`shares × latest_open`. HEG's share count has not changed in the saved state, and HEG underwent a
demerger with **ex-date and record date 2026-09-07**, entitling one resulting-company share per HEG
share per the company filing.

The book therefore marks the post-demerger quote against the pre-demerger share count, which
implicitly asserts the entitlement is worth zero:

```text
13 shares x INR 725.00 entry       =  INR  9,425.00
13 shares x INR 257.00 latest open =  INR  3,341.00
displayed HEG price P&L            =  INR -6,084.00
other 98 selected legs combined    =  INR +4,155.67
total displayed gross P&L          =  INR -1,928.33
```

**About 316% of the book's displayed gross loss is this one position**, and its size rests on an
assumption nothing has established.

## What can and cannot be established here

Measured, not asserted: **the entitlement cannot be priced from this repository.**
`scripts/validate_demerger_factors.py` returns `NO_EX_DATE_BAR` for HEG. The market cache's
`received_end` is **2026-08-21** and the ex-date is **2026-09-07**, so the resulting company has no
price anywhere in this repository — it is not merely missing from the universe, it is outside the
cache window entirely.

So all three of these would be wrong:

| Treatment | Why it is wrong |
|---|---|
| Mark HEG at the post-demerger quote on unchanged shares (**current behaviour**) | Asserts the entitlement is worth zero |
| Reverse the INR 6,084 | Asserts the entitlement is worth exactly the quote drop |
| Invent a price for the entitlement | Fabricates evidence |

The only defensible treatment is to carry it as an **unpriced asset**: exclude it from marked value,
state that it exists, and state that it cannot be valued from available data.

## What has been produced instead

`scripts/reevaluate_paper_books.py` (read-only) decomposes both books into gross P&L, paid costs,
prospective exit costs and net P&L, excludes HEG from marked value, and reports it under
`unpriced_assets` with the reason and the filing cited. Output:
`reports/strategy_reevaluation/paper-book-decomposition.json`. Method:
`reports/strategy_reevaluation/METHOD.md`.

## A second, separable observation about this book's cost display

Also read-only, and independent of HEG. `paper.py` charges the modelled 0.224% round trip **at
closing**. With zero closed legs the book has paid nothing, so its display carries no cost at all
while carrying the full liability.

On the saved entry notional of ~INR 862,815.98 that is about **INR 1,932.71** of unbooked exit cost —
larger than the entire displayed gross P&L of −INR 1,928.33. It is an accrual question, not a defect:
the modelled cost is real and unpaid, and a reader comparing this book to anything else needs to see
it. The re-evaluation reports it as `prospective_exit_costs`, separately from paid costs, rather than
folding it into one number.

The entitlement ratio itself is recorded in `data/authorities/nse-demerger-entitlements.json` with
the filing URL and a note that it must be re-verified against the issuer's own disclosure — the
issuer site returned HTTP 403 on direct retrieval, so the cited source is a reproduction.

## Suggested resolution, for the owner to accept or reject

Offered as a lead, not a decision:

- Give a marked leg an explicit **unpriced-entitlement** state, so the marking function can decline
  to value one rather than multiplying a stale share count by a post-event quote.
- Report equity in two parts: priced value, and a named list of unpriced entitlements. A book that
  cannot say "there is an asset here I cannot price" will always misreport a demerger.
- Consider accruing the modelled exit cost on open marks rather than only at close, so the displayed
  number and the liability move together.

**Status of these three as of 2026-09-11:** the first is **implemented** (see the update at the top).
The second and third are **not** — they change what the book reports and when it charges, which is a
decision for this record's owner rather than for the filer.
