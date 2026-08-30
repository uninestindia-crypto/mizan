# Red Team round three — the repairs to the repairs

DATE_UTC: 2026-08-30
COMMIT UNDER TEST: `86d1769c` — "fix(execution): a carried session reconciles, and a halt outlives the morning"
BRIEF: `.launch/RED-TEAM-BRIEF-20260830-ROUND3.md`
ADJUDICATOR: independent third pass. Wrote none of the code under test.
STATUS: IN PROGRESS

## Verdict

NOT YET DETERMINED — adjudication in progress.

## Claim status

| # | Claim | Verdict |
|---|---|---|
| 1 | `carry_in_positions` is correct and complete | **PROVEN** — 7 attacks reconcile; one P3 residual |
| 2 | Keeping carried fills out of `_fills` broke no other consumer | **PROVEN** for money/counts; new P3-1 audit gap |
| 3 | The `INITIALIZED` guard is the right boundary | **PROVEN** - no route back to `INITIALIZED` |
| 4 | The persisted halt is sticky and refusing to trade is safe | Sticky **PROVEN**; safe **DISPROVEN** - 2 new P1 |
| 5 | `session_peak_equity` from marked equity is the right quantity | Quantity **PROVEN**; ratcheting it makes P1-1 near-certain |
| 6 | Schema v3 needs no migration; the load path is clean | NOT TESTED |
| 7 | The new tests can actually fail | NOT TESTED |
| 8 | Regression against round 2's proven money results | NOT TESTED |
| 9 | Anything `86d1769c` introduced, overstated, or broke | NOT TESTED |

## Findings

_None recorded yet._

## 1. `carry_in_positions` is correct and complete

**VERDICT: PROVEN for the reconciliation, with one reachable-only-by-misuse residual (P3).**

`src/quant_system/execution/paper_pilot.py:214-239` (the new method) and `:833-865` (the rewritten
check (b) plus the new "sold to flat" loop).

Seven attacks on the baseline, driven through the real engine, the real `DecimalLedger`, the real
governor and the real `PaperPortfolioState.carry_forward_fills`:

```
A. carry a name and sell ALL of it
  sell-all: reconciled=True errors=() positions={} carried={'ACME': 100} fills=1 fees=105.14 cash=600819.86
B. sell MORE than carried (150 of 100)
   decision: False NAKED_SHORT_FORBIDDEN: Selling 150 but only hold 100
  oversell: reconciled=True errors=() positions={'ACME': 100} carried={'ACME': 100} fills=0 fees=0.00 cash=500000.00
C. carry TWICE before the session opens
   carried after two calls: {'ACME': 200} ledger qty: {'ACME': 100}
  double-carry: reconciled=False errors=('POSITION_MISMATCH for ACME: Ledger 100 != Carried 200 + Net Fills 0',) positions={'ACME': 100} carried={'ACME': 200} fills=0 fees=0.00 cash=1100220.00
D. same symbol in TWO carry fills
   carried: {'ACME': 100} ledger: {'ACME': 100}
  two-fill carry: reconciled=True errors=() positions={'ACME': 100} carried={'ACME': 100} fills=0 fees=0.00 cash=393780.00
E. carry ZERO names
  empty carry: reconciled=True errors=() positions={} carried={} fills=0 fees=0.00 cash=500000.00
F. carried name sold to flat, then RE-BOUGHT the same session
  round trip: reconciled=True errors=() positions={'ACME': 30} carried={'ACME': 100} fills=2 fees=141.28 cash=570460.92
G. carry-in AFTER a halt (status HALTED, never ACTIVE)
   refused: positions must be carried in before the session opens; the reconciliation baseline cannot move once trading has started (status is HALTED)
```

A, D, E and F all reconcile. The "sold to flat" loop at `:851-865` is doing real work in A: the
ledger drops a flat position entirely, so without that loop a carried name sold to zero would have
gone unchecked, and a carried name sold to *the wrong* zero would have gone unnoticed. B shows the
oversell is refused upstream by the governor's `NAKED_SHORT_FORBIDDEN` using the post-carry ledger,
so the carry does not open a route to a short.

### Residual (P3) — the baseline advances even when the ledger refuses the fill

`carry_in_positions` (`paper_pilot.py:238-239`) does:

```python
self.ledger.process_fill(fill)
self._carried_positions[fill.symbol] += fill.quantity
```

`DecimalLedger.process_fill` is idempotent by `fill_id` (`core/ledger.py:262-281`): an identical
replay **returns the cached transaction and mutates nothing**. The `+=` runs anyway. Case C above is
that divergence: the ledger correctly holds 100, the baseline claims 200, and the session cannot
reconcile.

This is not reachable from `run_paper_pilot_session.py`, which calls `carry_in_positions` exactly
once (`:826`), and it fails **loudly**, so it is P3 rather than higher. It is recorded because the
method is now public API on the engine and its docstring makes no idempotency statement.

### Two things worth stating that are *not* defects

- The paisa arithmetic is exact and cannot drift. `Position.average_price` is quantized to paisa at
  `core/ledger.py:497`, so `PortfolioHolding.average_cost` is always 2dp, `cost_basis` and the
  replay's `net_cash_delta` quantize the same already-exact product, and `ledger_funding()` debits
  out to the paisa. This independently confirms round 2's "worst cash drift 0" result.
- The new check (b) is weaker in one specific sense that does not matter today: `_carried_positions`
  and the ledger's carried quantity are both derived from the *same* `carry_forward_fills` output,
  so check (b) can no longer independently validate the carry itself — only today's fills against
  the ledger. The state file's `state_hash` is what is actually guarding the carried quantity.

## 2. Keeping carried fills out of `_fills` did not break something else that reads `_fills`

**VERDICT: PROVEN for every money and count consumer. One new reporting gap (P3-1).**

Complete enumeration of every read of `_fills` / the public `fills` property. There are twelve, and
no other module in the repository constructs a `PaperPilotEngine`:

| Site | Reads | Correct for a carried session? |
|---|---|---|
| `paper_pilot.py:841` | check (b) net fills | **Yes** — repaired, plus the new flat-name loop at `:856` |
| `paper_pilot.py:883` | `total_fees` | **Yes** — the carried entry fee was paid on an earlier session |
| `paper_pilot.py:901,902` | `total_trades_count`, `total_fills_count` | **Yes** — a hold traded nothing |
| `paper_pilot.py:884` (`_fill_slippage`) | `total_slippage_cost` | **Yes** — carry fills never enter `_fill_slippage` |
| `run_paper_pilot_session.py:1106` | status file `recent_fills` | Yes |
| `run_paper_pilot_session.py:1119` | status file `total_fees_paid` | Yes |
| `run_paper_pilot_session.py:1161` | status file `fills_count` | Yes |
| `run_paper_pilot_session.py:1204` | `todays_fees` -> persisted `total_fees` | Yes, but the filter is dead — round 2 P3-E, still uncorrected |
| `run_paper_pilot_session.py:1333` | `feedback_payload["fills"]` | Yes |
| `run_paper_pilot_session.py:1380` | the markdown fill table | Yes |

Measured on a two-name carried hold session (`ACME` 100 @ 1000.00 fee 220.00, `BETA` 500 @ 1700.00
fee 1900.00, cash 50,000.00), real engine, real ledger:

```
portfolio.cash (true carried cash) : 50000.00
ledger_funding()                   : 1002120.00

--- what a HOLD session reports ---
reconciliation.initial_cash        : 1002120.00   <- printed as 'Initial Capital'
reconciliation.final_cash          : 50000.00
reconciliation.total_cash_delta    : -952120.00   <- printed as 'cash_delta'
reconciliation.total_realized_pnl  : 0.00
reconciliation.total_unrealized_pnl: -4000.00
reconciliation.total_fees_paid     : 0.00
reconciliation.total_slippage_cost : 0.00
reconciliation.total_trades_count  : 0
reconciliation.total_fills_count   : 0
reconciliation.total_equity        : 996000.00
engine.fills                       : []
```

Fees, trade counts and slippage are all right: nothing traded, so nothing is reported. The claim
holds for the money.

### P3-1 (new, this commit) — the session's own audit log has no record of the carry

`PaperAuditRecord` is documented at `paper_pilot.py:83` as the "Immutable audit trail entry for
**every** execution event". `carry_in_positions` writes none. The whole audit log for a session that
opened holding Rs 952,120 of stock:

```
--- the audit log for a session that opened holding Rs 950,000 of stock ---
    SESSION_STARTED None 0 {'session_date': '2026-08-31', 'initial_cash': '50000.00'}
    SESSION_CLOSED None 0 {'reconciled': True, 'final_cash': '50000.00', 'total_equity': '996000.00', 'errors': []}
```

Two events. `feedback_payload["audit_events_count"]` (`:1335`) therefore reports `2`, the markdown
fill table is empty, and `Total Fills: 0`, while section 3 of the same report lists two open
positions with market values. Nothing in the emitted evidence says where they came from.

The ledger's own transaction log does hold it —

```
--- the ledger transaction log DOES record the carry ---
    tx_1 BUY 100 ACME @ 1000.00 cash_delta -100220.00
    tx_2 BUY 500 BETA @ 1700.00 cash_delta -851900.00
```

— but nothing in the runner's JSON or markdown output reads `ledger.transactions`. This is not a
regression (the pre-`86d1769c` direct `ledger.process_fill` call logged nothing either), but the
commit's own reasoning — "recording them in `_fills` ... would report positions opened weeks ago as
today's trades" — decided *where* the record goes and then put it nowhere the report can see. An
`OPENING_POSITION_CARRIED` audit event costs nothing and is the obvious place.

### Confirmed still open, not re-litigated

Round 2 P3-E is unchanged and both halves of it are still false at `run_paper_pilot_session.py:1201-1205`:

```
--- the runner's carry_ filter, line 1203-1205 ---
engine.fills                  : 0
after 'not startswith(carry_)': 0  -> filter removes 0
carry fill ids that the filter was written for: ['carry_ACME_2026-08-17', 'carry_BETA_2026-08-17']
...and their fees, which the comment calls zero-fee: ['220.00', '1900.00']
```

## 3. The `INITIALIZED` guard

**VERDICT: PROVEN. The boundary is right and there is no other route to the baseline.**

`paper_pilot.py:227-231`. `_session_status` is written in exactly five places -- `__init__` (`:153`),
`start_session` (`:299`), `halt_session` (`:309`), `resume_session` (`:325`) and `end_session`
(`:818`) -- and **none of them ever returns it to `INITIALIZED`**. Once the session has been opened
the baseline is frozen for the life of the object.

Every route attempted:

```
G. carry-in AFTER a halt (status HALTED, never ACTIVE)
   refused: positions must be carried in before the session opens; the reconciliation baseline cannot move once trading has started (status is HALTED)

=== C. can the baseline move by re-using the engine across sessions? ===
   session 1 status: CLOSED reconciled: True
   carry after CLOSED refused: positions must be carried in before the session opens; the reconciliation baseline cannot move once trading has started (status is CLOSED)
   start_session after CLOSED succeeded, status now: ACTIVE
   _carried_positions carried over into session 2: {'ACME': 100}
   session 2 reconciled: True ()
```

- Second `start_session` while ACTIVE: refused at `:295-296`.
- Halt then resume: `resume_session` sets ACTIVE, never INITIALIZED; carry still refused.
- Re-used engine after `end_session`: carry refused.

### P3-2 (pre-existing, newly load-bearing) -- a re-used engine is a second session with the first one's books

`start_session` (`:293-305`) resets `_session_date`, `_opened_at`, `_session_status` and
`_halt_reason` and nothing else. `_fills`, `_carried_positions`, `_orders`, `_audit_log`,
`_price_cache` and `_fill_slippage` all survive. The probe shows `start_session` succeeding from
`CLOSED` with session 1's `_carried_positions` still in place.

Not reachable from `run_paper_pilot_session.py`, which builds a fresh engine per session (`:808`),
which is why this is P3. Recorded because `carry_in_positions` is the first method to make the
engine's lifecycle load-bearing, and its guard reads "before the session opens" while the object
permits a second open.

## 4. The persisted halt is genuinely sticky, and refusing to trade is safe

**VERDICT: STICKY -- PROVEN. SAFE -- DISPROVEN. This is P1-1 and P1-2.**

Stickiness is real: `state_from_ledger` (`paper_portfolio.py:383-385`) ORs the previous flag in,
`save_portfolio` / `load_portfolio` round-trip it, and the runner refuses at `:782-793`. Confirmed
below (`NEXT SESSION loads risk_halted = True`).

What is not true is that refusing is safe.

### P1-1 (Blocker, created by `86d1769c`) -- the halt that fires is the 4% *daily* one, measured against the all-time peak, and it is now permanent

`PreTradeRiskGovernor.__init__` seeds **both** peaks from `initial_equity`:

```python
init_eq = initial_equity if initial_equity is not None else Decimal("0.00")
self._daily_peak_equity: Decimal = init_eq        # governor.py:27
self._all_time_peak_equity: Decimal = init_eq     # governor.py:28
```

`reset_session_peak` exists (`governor.py:70`) and has **zero callers in the repository**:

```
$ grep -rn "reset_session_peak" --include=*.py .
./src/quant_system/risk/governor.py:70:    def reset_session_peak(self, new_session_equity: Decimal) -> None:
```

Since `bb62bc58` the runner passes `initial_equity=max(portfolio.peak_equity,
portfolio.ledger_funding())` (`run_paper_pilot_session.py:795-798`) -- the **persisted all-time
peak**. So `_daily_peak_equity` is the all-time peak, and the check at `governor.py:186-206` labelled
`DAILY_DRAWDOWN_LIMIT_BREACHED` is in fact a 4% *total* drawdown test. `max_total_drawdown_pct=0.12`
at `:629` can never fire; the 4% test always fires first. On `sprint_50k` it is 3% against a
documented 8%.

Before `86d1769c` this was survivable: the kill was forgotten overnight and the next morning traded.
`86d1769c` persists it. Reproduction, driven exactly as the runner drives it -- real
`PreTradeRiskGovernor`, real `PaperPilotEngine`, real `state_from_ledger`, real `save_portfolio` /
`load_portfolio`:

```
persisted peak_equity        : 1000000.00
ledger_funding()             : 1000000.00
governor initial_equity      : 1000000.00
governor _daily_peak_equity  : 1000000.00   <-- SEEDED WITH THE ALL-TIME PEAK
governor _all_time_peak      : 1000000.00
reset_session_peak callers   : 0 (grep: only the definition)

marked equity this morning   : 954998.50
drawdown from the peak       : 4.5001%
daily limit  (documented)    : 4%   -- meant to be an INTRADAY limit
total limit  (documented)    : 12%  -- the multi-session limit

first order of the session (the EXIT):
   approved : False
   reason   : DAILY_DRAWDOWN_LIMIT_BREACHED: 4.50% >= 4.00%
   governor.is_killed: True
   kill event: DAILY_DRAWDOWN_LIMIT_BREACHED: 4.50% >= 4.00%

session end: reconciled = True | positions still held = {'ACME': 950}

PERSISTED: risk_halted = True | halted_on = 2026-08-31
PERSISTED: halt_reason = DAILY_DRAWDOWN_LIMIT_BREACHED: 4.50% >= 4.00%
PERSISTED: holdings still held = {'ACME': 950}

NEXT SESSION loads risk_halted = True -> runner :782 raises SystemExit(8)
```

Probe: `scratchpad/probe_halt.py`. The session that fired it **opened flat and moved 0% intraday**.
A book 4.5% below its high -- a routine week -- permanently stops the pilot.

The commit message names half of this and repairs the wrong half:

> "because the kill fires on the first order and the first order is a SELL, that same session's
> exits were refused, so the losing book was retained while the breach that should have stopped it
> was erased."

The erasure is fixed. The **retention** is not, and is now permanent: the exit is refused, the book
stays, and every subsequent session exits 8 without ever proposing another exit. There is no route
in the code by which those 950 shares are ever sold.

### P1-2 (Blocker, created by `86d1769c`) -- the documented recovery is impossible, and the only route that works silently destroys the portfolio

`run_paper_pilot_session.py:786-792` tells the operator:

> "Review the book, then clear `risk_halted` in {PORTFOLIO_STATE_PATH} deliberately."

`save_portfolio` writes `state_hash = canonical_sha256(payload)` (`paper_portfolio.py:260`) and
`load_portfolio` refuses any payload that does not match (`:285-288`). Editing the field as
instructed:

```
--- the documented recovery: 'clear risk_halted in <file> deliberately' ---
   REFUSED: portfolio state at ...\portfolio_state.json does not match its own hash; refusing to resume from it
```

There is no clear-halt tool. `save_portfolio` has exactly one non-test caller,
`run_paper_pilot_session.py:1231`, and it is downstream of the exit-8:

```
$ grep -rn "save_portfolio" --include=*.py . | grep -v "def save_portfolio"
./scripts/run_paper_pilot_session.py:329:    save_portfolio,
./scripts/run_paper_pilot_session.py:1231:    save_portfolio(PORTFOLIO_STATE_PATH, portfolio)
(the remaining matches are tests)
```

The one action that does clear it is deleting the file, because `load_portfolio` returns `None` for a
missing path (`:273-274`) and the runner falls back to `PaperPortfolioState(cash=initial_cash)`
(`:656`). That is the exact failure the module's own docstring says it exists to prevent -- "resetting
to a fresh portfolio on a bad read would silently discard a running position and report a clean
session" -- and the protection covers corrupt files but not missing ones:

```
=== A. the only remaining recovery route: delete the state file ===
before: {'cash': 50000.00, 'realized_pnl': -31000.00, 'total_fees': 8400.00, 'peak_equity': 1000000.00, 'risk_halted': True, 'sessions_completed': 42} holdings {'ACME': 950}
after deleting the file, the runner's own fallback gives:
   risk_halted        : False
   holdings           : {}  <- 950 ACME gone
   realized_pnl       : 0.00  <- -31000.00 gone
   total_fees         : 0.00  <- 8400.00 gone
   peak_equity        : 0.00  <- 1000000.00 gone
   sessions_completed : 0  <- 42 gone
   cash               : 1000000.00  <- invented, was 50000.00
   -> the session then runs normally and reports SUCCESS
```

Probe: `scratchpad/probe_halt2.py`. The halt clears, the entire book vanishes, cumulative P&L and
fees reset to zero, the high-water mark resets to zero (re-arming the drawdown switch from scratch),
and the session reports SUCCESS. Silent, unrecoverable, and it is the only action left to an operator
whose instructions do not work.

### P2-1 -- nothing but the exit code records that a session was refused

The `SystemExit(8)` at `:793` fires before `status_file` is even defined (`:852`). On a halted day:

- no `paper_session_<date>_<id>.json` and no markdown report are written;
- `logs/paper_runs/live_paper_status.json` is **not** rewritten, so it keeps serving the last
  successful session's `"status": "COMPLETED"` indefinitely. It is read by `server/app.py:1235`,
  `scripts/serve_live_dashboard.py:28` and `scripts/view_live_pnl.py:20`;
- `scripts/run_scheduled_paper_session.py:260-262` only logs the return code and returns it. No
  distinct handling, and nothing alarms on the *absence* of a session report.

A dashboard showing a green COMPLETED session while the pilot has been dead for a month is the
operability failure this path exists to avoid.

`SystemExit` is a `BaseException`, so `main`'s `except Exception` (`:1513`) does not swallow it and
the process really does exit 8 -- that part is correct.

### P3-3 -- the refusal happens after the decision it says must not be computed

`:782` sits after the cross-section build, the extreme-row refusals, the model scoring and the pick
logging (`:683-745`), and after sizing (`:757-773`). Every halted day fetches live quotes for the
whole universe and logs the Mizan picks. The same file argues at `:675-676` that on a hold session
the ranking is deliberately not computed because "computing a decision that will not be acted on
invites reading it as one". The halt check is on the wrong side of that principle.

## 5. `session_peak_equity = max(governor peak, reconciliation.total_equity)`

**VERDICT: the quantity is right. Ratcheting it is what makes P1-1 near-certain rather than rare.**

### The quantity itself: correct

`reconciliation.total_equity` is `snapshot.total_equity` from `DecimalLedger.get_portfolio_snapshot`
(`core/ledger.py:539-569`), i.e. cash plus every position marked to the supplied close price. It does
include unrealized marks:

```
=== A. does reconciliation.total_equity include unrealized marks? ===
   cost basis 100,000; marked at 1250 -> equity 175000.00 | unrealized 25000.00 -> YES, marks included
```

So the P2-H repair does what it says: a hold session now moves the high-water mark.

### But it is *session-close* equity, not the session's high

The commit message justifies the change with "a book that rose 25% during a hold and then fell 20%
from that high recorded no drawdown at all". The repair does not record that high either, unless the
session happens to close on it. `update_peaks` is still reachable only from `evaluate_order`
(known-open residual 3), and the new input is taken once, at `end_session`:

```
=== C. an intraday high is still not recorded ===
   book touched 1400 intraday and closed at 1000; recorded peak input = 150000.00
   -> session-CLOSE equity only. update_peaks is still reachable only from evaluate_order.
```

The book touched Rs 190,000 of equity and Rs 150,000 was recorded. Real repair, narrower than stated.

### When it cannot be computed, the whole session is discarded

```
=== B. is it computable on every session? ===
   NO -> LedgerInvariantViolation : cannot mark ACME to market: no price supplied for a held position of 100; refusing to substitute its average price
```

The brief lists this crash as known-open. What is worth adding is the *consequence path*:
`engine.end_session` is called at `run_paper_pilot_session.py:1196`, outside every `try`. The
exception unwinds past `save_portfolio` (`:1231`) into `main`'s `except Exception` (`:1513`), which
logs and returns 2. So a session that traded all day loses **every** fill: the ledger was in-process
only, the state file is not advanced, and the next session resumes from yesterday's book as though
today never happened. The only signal is exit 2 and a stack trace.

### P1-3 -- ratcheting the peak on marked equity turns the P1-1 halt from rare into near-certain

Before `86d1769c`, `session_peak_equity` was `governor.all_time_peak_equity`, which on a hold session
never moved (no orders, so no `update_peaks`) and was floored at `ledger_funding()` -- a cost figure
that only rises when the book is re-bought at a higher basis. The peak therefore climbed slowly and
lagged the market.

After `86d1769c` it takes **every session's marked close**, so it ratchets to the running maximum of
the equity curve. The 4% test of P1-1 is then run against that running maximum, on each rebalance
session, and firing it is now permanent.

Zero-drift lognormal equity path, peak ratcheting at every session close, the 4% test applied on
every 10th session (the rebalance cadence) against that morning's marked equity, 4,000 paths, seed
`20260830` (`scratchpad/probe_claim5b.py`):

```
  default profile, 1.0%/session vol, zero drift, 4% limit
     permanently halted within 250 sessions: 3995/4000 = 99.9%   median session: 30
  default profile, 0.8%/session vol, zero drift, 4% limit
     permanently halted within 250 sessions: 3984/4000 = 99.6%   median session: 50
  default profile, 1.0%/session vol, +12%/yr drift, 4% limit
     permanently halted within 250 sessions: 3980/4000 = 99.5%   median session: 40
  sprint_50k, 1.5%/session vol (2-3 names), zero drift, 3% limit
     permanently halted within 250 sessions: 4000/4000 = 100.0%   median session: 20
```

**Median six weeks to a permanent, unrecoverable halt, and it is not sensitive to the assumptions** --
a positive 12%/year drift barely moves it, because a running-maximum drawdown of 4% is an ordinary
event for any equity book at any realistic volatility. The two changes in this one commit compose:
one raises the bar faster, the other makes hitting it terminal.

## 6. Schema v3

NOT TESTED.

## 7. The new tests can actually fail

NOT TESTED.

## 8. Regression against round 2

NOT TESTED.

## 9. Open-ended: what `86d1769c` introduced, overstated, or broke

NOT TESTED.

## NOT PROBED

NOT YET WRITTEN.
