# NOTICE: the XS-Monthly entitlement is now wired end to end, under Hermes Agent's claim

STATUS: NOTICE (additive; no other record is edited)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-14
FOR: `20260903-hermes-xs-monthly-screen-new.md` (STATUS `ACTIVE`), which owns
  `src/quant_system/research_xs_monthly/**`, `scripts/run_xs_monthly_paper_watch.py` and
  `logs/xs_monthly_new/`
AUTHORIZATION: founder instruction, 2026-09-14, in answer to an explicit question naming this repair
  and naming this claim as the one it crosses. Item 1 of the repair order in
  `reports/loss_diagnosis_20260913/DIAGNOSIS.md`.
SUPERSEDES IN PART: `20260910-NOTICE-xs-monthly-heg-entitlement-unpriced.md`, which implemented the
  capability and left wiring the caller to this record's owner. The founder has now made that call.

## What was left undone, and is now done

That earlier notice added `unpriced_entitlements` to `settle_positions` and pinned it with six tests.
**Nothing called it.** Four further places would have lost the value even if it had:

| Place | Was | Now |
|---|---|---|
| `run_xs_monthly_paper_watch.py:80`, `:102` | `settle_positions(...)` with no map | map built from `data/authorities/nse-demerger-entitlements.json` and passed at both call sites |
| `run_xs_monthly_paper_watch.py:119` | `sum(leg.get("market_value", "0"))` | `paper.book_value(...)`, which reads `leg["market_value"]` and routes a leg that has none to a named exclusion list |
| `_render` | `f"... gross {leg['gross_mark']}"` | `KeyError` on an unpriced leg; now renders `**UNPRICED**` with the reason, and a separate unresolved section |
| `live_dashboard.py:1130` and the KPI block | `parseFloat(leg.gross_mark) \|\| 0` | unpriced legs are counted separately, their entry cost disclosed in a banner, every numeric cell refused rather than zeroed |
| `paper.py` closed branch | matured legs closed through `forward_net`/`_book_closed` | a flagged leg goes to `unresolved` instead: no proceeds into cash, capital reported as committed and unvaluable |

**The maturity branch was the dangerous half.** HEG entered 2026-09-02 with a 21-session hold. Today
the fabricated INR 6,124.30 is *unrealized* and still correctable. On maturity the old code would
have converted it to realized cash, after which correcting it would mean rewriting history — which
the earlier notice rightly refuses.

An unpriced leg still leaves `open`. The runner gates new positions on `if not state["open"]`, so a
leg held open forever would have stopped the book rebalancing, silently and indefinitely.

## Nothing under `logs/` was touched

`git status --short logs/` is empty and the saved HEG leg still reads `market_value: "3300.7"`,
`unrealized: "-6124.3"`. `settle_positions` recomputes every open mark from `entry_open`, `shares`
and the latest bar on each run, so **the correction takes effect on the next scheduled run with no
state edit at all.** The paper history stays intact.

## Verified on the real book, in a scratch copy

The real state was copied to a scratchpad directory and the runner driven against it with
`--state-dir`:

```text
capital 1000000 cash 137184.02 open_mv 853574.90 equity 990758.92
open 99 closed 0 runs 11
UNPRICED 1 holding(s), entry cost 9425, EXCLUDED from equity above:
  HEG entry_value 9425 -- ENTITLEMENT_UNPRICED: held across HEG ex-date 2026-09-07,
  entitled to 1 x HEGGRAPHITE, which has no price in this repository.
```

**What the founder will see change on the next real run.** Displayed equity falls from
`994,059.62` to `990,758.92` — the 3,300.70 the book was crediting HEG's parent shares with — and a
disclosure appears saying 9,425 of entry cost is committed to a holding that cannot be valued. That
is not a new loss. It is the book declining to state a number it never had evidence for: the true
figure lies somewhere between the two, and which end depends on what HEGGRAPHITE is worth.

## Authority handling

The map is built from the issuer-filed authority, never from price. `load_unpriced_entitlements`
**raises** on a missing or wrong-schema authority rather than returning an empty map — an empty map
is indistinguishable from "no corporate actions occurred", and silently returning one is the exact
failure that froze the corporate-action authority for weeks (`CURRENT.md`, repair `ee1b0cb3`).

Two reasons are distinguished, because they are different facts: `ENTITLEMENT_UNPRICED` (the
resulting company has no price here) and `ENTITLEMENT_NOT_REPRESENTABLE` (it is priced, but a leg in
this book carries one symbol and one share count). The second is a stated limitation of the book, not
a gap in the data.

## Verification

- `tests/test_xs_monthly_entitlement_wiring.py`, 12 new tests covering map construction, the
  fail-closed authority, exclusion-not-zeroing, and the maturity path.
- All 6 pre-existing entitlement tests and all 26 other XS-Monthly tests still pass, unchanged.
- Full suite **1,519 passed**. Ruff and strict mypy clean.

## What is still not solved

The entitlement still cannot be **valued**. This makes the book honest about that, it does not price
HEGGRAPHITE. The ratio in the authority is from a reproduced filing, not the issuer's own site
(HTTP 403), and the authority file says so.
