# Red Team round three — the repairs to the repairs

DATE_UTC: 2026-08-30
COMMIT UNDER TEST: `86d1769c` — "fix(execution): a carried session reconciles, and a halt outlives the morning"
BRIEF: `.launch/RED-TEAM-BRIEF-20260830-ROUND3.md`
ADJUDICATOR: independent third pass. Wrote none of the code under test.
STATUS: COMPLETE

## Verdict

**NOT READY.** Three P1 Critical, five P2 Major, eight P3 Minor.

The pattern the brief predicted held for a third time. Round 1 found 8 P1; round 2 found that the
repairs to those created 2 new P1; round 3 finds that the repairs to *those* created 3 more. Every
one of the three is a consequence of two correct-looking repairs composing:

- `bb62bc58` seeded the governor with the persisted all-time peak, which silently converted the 4%
  *daily* drawdown limit into a 4% *total* one (`_daily_peak_equity` takes the same seed and nothing
  ever resets it).
- `86d1769c` then (a) made the resulting kill permanent and (b) made the peak ratchet on every
  session's marked close, which is what makes hitting a 4% running-maximum drawdown near-certain.

Measured consequence: **median 30 sessions -- about six weeks -- to a terminal, unrecoverable halt**,
99.9% within a trading year, on a limit the profile documents as 12%. The documented recovery does
not work, and the only action that does silently destroys the entire portfolio.

Everything the commit set out to repair, it repaired. Both round-2 P1s are genuinely closed, all four
of round 2's proven money results survive intact, and the carry arithmetic is exact to the paisa over
eleven carried sessions. The failure is not in the repairs; it is again in what they compose with.

## Findings

### P1 Critical

| # | Finding | Claim |
|---|---|---|
| P1-1 | The persisted halt fires on the 4% **daily** limit measured against the all-time peak, not the 12% total limit; `TOTAL_MAX_DRAWDOWN_BREACHED` is unreachable. It is now permanent, the refused exit leaves the losing book held forever, and nothing can sell it | 4, 9 |
| P1-2 | The documented recovery is impossible -- the state file is hash-protected and no clear-halt tool exists. The only route that works, deleting the file, silently discards the book, cumulative P&L, fees and the high-water mark, and the next session reports SUCCESS | 4 |
| P1-3 | Ratcheting `peak_equity` to every session's marked close turns P1-1 from rare into near-certain: 3995/4000 simulated paths halt permanently within a trading year, median session 30 | 5 |

### P2 Major

| # | Finding | Claim |
|---|---|---|
| P2-1 | A refused session writes no report and does not update `live_paper_status.json`, so every dashboard serves the last successful session's `COMPLETED` indefinitely; nothing alarms on the absence of a session | 4 |
| P2-2 | `test_the_peak_records_marked_equity_not_only_cost` passes verbatim against the parent commit; it cannot detect the repair it is named for. Round 2's P2-O repeating | 7 |
| P2-3 | The reconciliation has zero mutation coverage: forcing `reconciled=True` unconditionally leaves all 1166 tests passing | 7 |
| P2-4 | The commit message reasons throughout about the total-drawdown switch and a 14% breach; the switch that actually fires at 14% is the daily one | 9 |
| P2-5 | The sticky halt is erased silently by a lost update between two overlapping sessions; there is no lock, PID file or compare-and-swap anywhere | 4 |

### P3 Minor

| # | Finding | Claim |
|---|---|---|
| P3-1 | `carry_in_positions` writes no audit record, so a carried session's evidence file has two audit events and no trace of the opening book | 2 |
| P3-2 | A re-used engine opens a second session carrying the first one's `_fills` and `_carried_positions`; `start_session` resets neither | 3 |
| P3-3 | The halt refusal is placed after the model decision the same file argues must not be computed when it will not be acted on | 4 |
| P3-4 | The three new schema fields fail three different ways: raw `KeyError`, silent `None`, silent `""` | 6 |
| P3-5 | `bool(payload["risk_halted"])` accepts any type; `null`, `0` and `[]` clear the halt without complaint | 6 |
| P3-6 | The `carry_in_positions` docstring says lot accounting is "reconstructed by the ledger"; the replay collapses every lot into one at the average price | 9 |
| P3-7 | Exit 2 from the scheduled wrapper means either "today is a public holiday" or "the session crashed" | 9 |
| P3-8 | `carry_in_positions` advances `_carried_positions` even when the ledger idempotently ignores the fill, producing a false `POSITION_MISMATCH` | 1 |

## What survived attack

- **The carry arithmetic is exact.** Worst cash drift across eleven carried sessions: **0.00**.
  `Position.average_price` is quantized at `core/ledger.py:497`, so no rounding path exists.
- **Both round-2 P1s are genuinely closed**, and reverting either repair reproduces the original
  defect precisely.
- **All four of round 2's proven money results survive.** Cross-session round trip 9651.20 equals the
  same-session one to the paisa; cumulative realized P&L equals the cash movement exactly; the hold is
  exactly 10 sessions; the entry fee is charged once, not eleven times.
- **The `INITIALIZED` guard has no bypass.** `_session_status` never returns to `INITIALIZED` by any
  route.
- **A v2 state file is refused cleanly** with a typed error naming both versions, and no state file
  has ever been written, so "no migration needed" is correct.
- **`halt_reason` round-trips every adversarial string tested** -- Devanagari, emoji, RTL override,
  zero-width, embedded newline, embedded quotes, 5,000 characters -- through the canonical hash.
- **Scale is a non-issue.** A 500-name carried book: `carry_in_positions` 16.0 ms, `end_session`
  2.8 ms.
- Ruff clean; mypy clean on 141 files; **1166 tests passing in 84.32s**; the scheduled task is
  confirmed `Disabled`.


## Claim status

| # | Claim | Verdict |
|---|---|---|
| 1 | `carry_in_positions` is correct and complete | **PROVEN** — 7 attacks reconcile; one P3 residual |
| 2 | Keeping carried fills out of `_fills` broke no other consumer | **PROVEN** for money/counts; new P3-1 audit gap |
| 3 | The `INITIALIZED` guard is the right boundary | **PROVEN** - no route back to `INITIALIZED` |
| 4 | The persisted halt is sticky and refusing to trade is safe | Sticky **PROVEN**; safe **DISPROVEN** - 2 new P1 |
| 5 | `session_peak_equity` from marked equity is the right quantity | Quantity **PROVEN**; ratcheting it makes P1-1 near-certain |
| 6 | Schema v3 needs no migration; the load path is clean | **PROVEN** — never written; v2 refused cleanly. 2 P3 |
| 7 | The new tests can actually fail | **PARTLY DISPROVEN** — 8 of 9 real, 1 worthless, 3 repairs untested |
| 8 | Regression against round 2's proven money results | **PROVEN** — all four survive; carry drift 0.00 |
| 9 | Anything `86d1769c` introduced, overstated, or broke | **CONFIRMED** — 3 new P1, 1 false commit claim, 1 overstated docstring |

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

### P3-8 — the baseline advances even when the ledger refuses the fill

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
self._daily_peak_equity: Decimal = init_eq  # governor.py:27
self._all_time_peak_equity: Decimal = init_eq  # governor.py:28
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

### P2-5 -- the sticky halt is erased silently by a lost update, and there is no lock of any kind

`save_portfolio` is atomic (`staging.replace(path)`), but the sequence the runner performs is
load -> trade all day -> save, with no lock, no PID file and no compare-and-swap:

```
=== concurrency: is there any lock around load -> trade -> save? ===
   'lock' in paper_portfolio.py: False | in run_paper_pilot_session.py: False
   'flock' ... False | 'msvcrt' ... False | 'fcntl' ... False | 'O_EXCL' ... False | 'pid' ... False
```

`state_from_ledger` makes the halt sticky against `previous.risk_halted` -- but `previous` is
whatever *that process* loaded at 09:10. Two overlapping sessions (the schedule firing while an
operator runs the script by hand is the ordinary way this happens):

```
after session A saves : risk_halted = True | halted_on = 2026-08-31
after session B saves : risk_halted = False | halted_on = None | halt_reason = ''

  -> HALT ERASED by the later writer
  sessions_completed: 21 (A wrote 21, B wrote 21; one session lost)
```

Probe: `scratchpad/probe_race.py`. The whole of session A -- its fills, its cash, its P&L, and the
kill switch it tripped -- is overwritten with no error and no log line. It is P2 rather than P1
because the scheduled task is currently `Disabled`, so two concurrent runs require deliberate action
today; the mechanism is unconditional.

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

**VERDICT: "no migration needed" is PROVEN. The load path is clean for v2, asymmetric for the three
new fields.**

### No state file has ever been written -- verified

```
$ ls logs/paper_runs/
live_paper_status.json
paper_session_2026-08-26_*.json / .md   (8 sessions, all 2026-08-26)
(no portfolio_state.json)

$ git log --oneline --all -- logs/paper_runs/portfolio_state.json
(empty)

$ grep -n logs .gitignore
21:logs/
```

The reason is stronger than the absence of the file. Persistence landed in `b3e626b5`, dated
**2026-08-29 22:16 +0530**; every session artifact on disk is from **2026-08-26**. `save_portfolio`
has therefore never executed outside tests, so there is no v1 or v2 file anywhere to migrate. The
claim is correct.

The corollary belongs in the record: **the entire carried-session path has never run in the real
runner.** `carry_in_positions`, the halt guard, the peak, the whole v2->v3 shape are supported only by
unit tests and by the probes in this report.

### A v2 file is refused cleanly

```
=== A. a genuine v2 file (hash valid, version 2) ===
   refused cleanly: portfolio state at ...\v2.json declares quantos.paper_portfolio v2, expected quantos.paper_portfolio v3
```

Typed `PaperPortfolioError`, both versions named. Correct.

### P3-4 -- the three new fields have three different failure modes

```
=== B. a v3 file MISSING each new field, hash recomputed so it is otherwise valid ===
   risk_halted  missing -> KeyError: 'risk_halted'   <-- untyped
   halted_on    missing -> LOADED, defaults to None   <-- SILENT
   halt_reason  missing -> LOADED, defaults to ''   <-- SILENT
```

`paper_portfolio.py:319-321`: `payload["risk_halted"]` is subscripted (raw `KeyError`, escaping the
module's `PaperPortfolioError` contract and surfacing in the runner as exit 2 with a stack trace,
the same shape as round 2's P3-D), while `halted_on` and `halt_reason` use `payload.get(...)` and
default silently. Those two are the entire human-facing content of the refusal message at `:786-792`,
so losing them costs the operator the date and the reason while the halt itself stays on:

```
=== D. halted set but halted_on absent (what the refusal message then prints) ===
   risk_halted=True halted_on=None halt_reason=''
   runner :786-792 logs: 'the risk kill switch fired on None ... Reason: not recorded'
```

### P3-5 -- `bool(payload["risk_halted"])` accepts anything

```
=== C. risk_halted with a truthy string / wrong type ===
   risk_halted='false'  -> loaded as True
   risk_halted='0'      -> loaded as True
   risk_halted=''       -> loaded as False
   risk_halted=0        -> loaded as False
   risk_halted=1        -> loaded as True
   risk_halted=None     -> loaded as False
   risk_halted=[]       -> loaded as False
   risk_halted='no'     -> loaded as True
```

The string cases fail *safe* (a halt stays on), so this is P3 rather than higher. But `null`, `0` and
`[]` all clear the halt without complaint, and given P1-2 -- where the documented recovery is
impossible and no clear-halt tool exists -- an operator hand-repairing the file and recomputing the
hash is the realistic path. Nothing type-checks the field that decides whether the system trades.

## 7. The new tests can actually fail

**VERDICT: 8 of the 9 are real. 1 is worthless. 3 of the 6 repairs in the commit have no test at
all, and the reconciliation itself has none.**

Method: no source was modified. Each repair was reverted in-process by monkeypatch, or the test was
run verbatim against `git show c45ee6f8:...` -- the parent commit's own module.

### Reverting `carry_in_positions` to the pre-repair bare ledger replay

```
--- BASELINE at 86d1769c (all must pass) ---
   PASS  test_a_carried_sell_is_refused
   PASS  test_a_halt_survives_the_session_boundary
   PASS  test_a_quiet_session_does_not_lift_a_halt
   PASS  test_a_session_starting_flat_still_reconciles
   PASS  test_a_session_that_carries_positions_reconciles
   PASS  test_a_session_that_trades_on_top_of_carried_positions_reconciles
   PASS  test_positions_cannot_be_carried_in_once_the_session_is_open
   PASS  test_the_carried_positions_are_not_counted_as_today_s_trading
   PASS  test_the_peak_records_marked_equity_not_only_cost

--- REV-A: carry_in_positions reverted to a bare ledger replay (no baseline, no guards) ---
   FAIL  test_a_carried_sell_is_refused   (AssertionError: Regex pattern did not match.)
   FAIL  test_a_session_that_carries_positions_reconciles   (POSITION_MISMATCH for ACME: Ledger 100 != Carried 0 + Net Fills 0)
   FAIL  test_a_session_that_trades_on_top_of_carried_positions_reconciles   (POSITION_MISMATCH ...)
   FAIL  test_positions_cannot_be_carried_in_once_the_session_is_open   (Failed: DID NOT RAISE RuntimeError)
   FAIL  test_the_carried_positions_are_not_counted_as_today_s_trading   (AssertionError)

--- REV-B: check (b) reverted to comparing against today's fills alone ---
   FAIL  test_a_session_that_carries_positions_reconciles
   FAIL  test_a_session_that_trades_on_top_of_carried_positions_reconciles
   FAIL  test_the_carried_positions_are_not_counted_as_today_s_trading
```

Real tests. They reproduce the exact P1-A of round 2 when the repair is removed.

### The repairs no test can detect

| Repair | Site | Detected by a test? |
|---|---|---|
| `carry_in_positions` baseline + BUY/status guards | `paper_pilot.py:214-239` | Yes (5 tests) |
| check (b) reconciles `carried + net fills` | `paper_pilot.py:844-849` | Yes (3 tests) |
| the "sold to flat" loop | `paper_pilot.py:851-865` | **No** |
| `risk_halted` refusal + `SystemExit(8)` | `run_paper_pilot_session.py:782-793` | **No** |
| `session_peak_equity = max(gov, reconciliation.total_equity)` | `run_paper_pilot_session.py:1225` | **No** |
| `risk_halted` / `halted_on` / `halt_reason` persisted, sticky | `paper_portfolio.py:133-135, 238-240, 319-321, 383-385` | Yes (2 tests) |

**The "sold to flat" loop.** Whole-suite coverage of `quant_system.execution`, all 1166 tests:

```
Name                                            Stmts   Miss  Cover   Missing
src\quant_system\execution\paper_pilot.py         366     30    92%   ... 829, 846, 856-862, 870
```

Lines **856-862** are the body of the new loop. They never execute. No test in the repository ever
has a carried symbol that the ledger no longer holds, so the second half of the check-(b) repair
could be deleted without a single failure.

**The two runner repairs.** Nothing imports the runner:

```
$ grep -rn run_paper_pilot_session --include=*.py tests/
tests/test_research_paper_exemption.py:3:Red Team finding P1-1: `scripts/run_paper_pilot_session.py` called `MizanModel.default_model()`
```

One docstring mention. `run_paper_session` is never called by a test, so the exit-8 refusal and the
marked-equity peak -- P1-1, P1-2 and P1-3 in this report -- are executed by nothing.

### P2-2 -- `test_the_peak_records_marked_equity_not_only_cost` passes against the code it says is broken

Its docstring names the runner defect: "`update_peaks` is reachable only from `evaluate_order` ... so
the peak moved only via `max(previous, ledger_funding())` -- a cost figure." The repair for that is
`run_paper_pilot_session.py:1225`. The test exercises `state_from_ledger`, which `86d1769c` did not
change in this respect. Run verbatim against the parent commit's module:

```
loaded paper_portfolio.py as of the PARENT commit c45ee6f8

REV-E: test_the_peak_records_marked_equity_not_only_cost, verbatim, against the parent commit
   -> PASSES. The test cannot detect the repair it is named for.

REV-F: the two halt-persistence tests against the parent commit
   test_a_halt_survives_the_session_boundary: fails -> TypeError: state_from_ledger() got an unexpected keyword argument 'risk_halted'
   test_a_quiet_session_does_not_lift_a_halt: fails -> TypeError: PaperPortfolioState.__init__() got an unexpected keyword argument 'risk_halted'
```

The two halt tests are genuine. The peak test asserts that `state_from_ledger` honours a value the
caller passes in -- which it already did. This is round 2's **P2-O repeating verbatim** ("the
`peak_equity` test asserts a round trip"); the response to that finding was a second test with the
same shape.

### P2-3 -- the reconciliation cannot fail in any test, so nothing would notice if it stopped working

The three error branches of `end_session` -- `CASH_MISMATCH` (`:829`), `POSITION_MISMATCH` (`:846`)
and `OPEN_ORDERS_REMAINING` (`:870`) -- are all in the missing-lines list above. No test in the
repository has ever produced `reconciled=False`.

Demonstrated by mutation. A pytest plugin wraps `end_session` and returns the same report with
`reconciled=True, reconciliation_errors=()` -- i.e. the reconciliation is made unconditionally
successful, and nothing else is touched:

```
$ PYTHONPATH=<scratch> .venv/Scripts/python.exe -m pytest -q -p mut_recon
================= 1166 passed, 1 warning in 82.66s (0:01:22) ==================
```

**All 1166 pass.** The penny-exact reconciliation is described at `paper_pilot.py:820` as the
"financial-model-craft non-negotiable invariant", it is what round 2's P1-A was about, and it is what
`bb62bc58`'s honest exit code exists to surface. It has zero mutation coverage: a change that made it
always report success would ship green.

## 8. Regression against round 2's proven money results

**VERDICT: PROVEN. `86d1769c` disturbs none of them, and the carry now runs through the new
`carry_in_positions` path rather than the raw ledger.**

Twelve simulated sessions, real `PaperPilotEngine`, real `DecimalLedger`, real
`PaperPortfolioState.carry_forward_fills` / `ledger_funding` / `state_from_ledger`, real
`IndianMarketCostModel` costs, each session opened by `engine.carry_in_positions(...)`
(`scratchpad/probe_claim8.py`).

### The cross-session round trip still nets both legs

```
=== A. cross-session round trip vs same-session round trip, identical prices ===
  d00 buy 100 @1000          carry-drift   0.00 | recon True  | session realized       0.00 | cum realized       0.00 | cum fees    119.26 | cash    899825.74 | held 1
  d01 sell 100 @1100         carry-drift   0.00 | recon True  | session realized    9651.20 | cum realized    9651.20 | cum fees    233.80 | cash   1009651.20 | held 1
  cross-session realized P&L = 9651.20
  same-session  realized P&L = 9651.20
  DIFFERENCE = 0.00   (IDENTICAL)
```

### Cash exact, hold exactly 10, no double count

```
=== B. twelve sessions, one full hold cycle: cash exact, no double count, hold == 10 ===
  d00 rebalance: enter       carry-drift   0.00 | recon True  | session realized       0.00 | cum realized       0.00 | cum fees    298.14 | cash    749559.36 | held 1
  d01 hold 1                 carry-drift   0.00 | recon True  | session realized       0.00 | cum realized       0.00 | cum fees    298.14 | cash    749559.36 | held 2
  ...
  d09 hold 9                 carry-drift   0.00 | recon True  | session realized       0.00 | cum realized       0.00 | cum fees    298.14 | cash    749559.36 | held 10
      rebalance_due(horizon=11) first True at sessions_held = 10 -> the position was held for 10 sessions
  d11 rebalance: exit        carry-drift   0.00 | recon True  | session realized    5647.28 | cum realized    5647.28 | cum fees    565.22 | cash   1005647.28 | held 1
  worst carry cash drift across 11 sessions = 0.00
  cumulative realized P&L = 5647.28   cumulative fees = 565.22
  final cash = 1005647.28   holdings = {}

  cash_end - 1,000,000 = 5647.28   cum realized = 5647.28
```

Four independent checks, all clean:

- **Carry cash drift is exactly 0.00 on all 11 carried sessions.** `engine.cash` after
  `carry_in_positions` equals `portfolio.cash` to the paisa every time.
- **The hold is exactly 10.** `rebalance_due(11)` first returns True at `sessions_held = 10`.
- **The entry fee is charged once, not eleven times.** `cum fees` sits at 298.14 for the whole hold
  and only moves at the exit.
- **No double count.** Cumulative realized P&L 5,647.28 equals the cash change 1,005,647.28 minus
  1,000,000.00 exactly.
- Every one of the 12 sessions reconciles.

Round 2's claim-1, claim-2 and claim-3 results all survive `86d1769c`.

## 9. Anything `86d1769c` introduced, overstated, or broke

**VERDICT: three P1 (sections 4 and 5), one false commit-message claim, one overstated docstring, and
the static/test claims all check out.**

### The commit message, claim by claim

| Claim | Verdict |
|---|---|
| "Every carried session failed reconciliation" | **True** — REV-B in claim 7 reproduces it exactly |
| "Check (a) was never affected: it reads `ledger.transactions`, which does include the carry fills" | **True** — discrepancy 0.00, no errors |
| "The carried fills stay out of `_fills` on purpose ... inflating `total_fees_paid` and both trade counts" | **True** — claim 2 |
| **"A 14% breach ... the total-drawdown switch"** | **FALSE** — see below |
| "`risk_halted`, `halted_on` and `halt_reason` now persist, sticky, and the runner refuses to trade and exits 8" | **True**, and unsafe — P1-1, P1-2 |
| "Auto-clearing was rejected because a switch that resets itself is not a switch" | True as stated; the alternative it chose cannot be executed — P1-2 |
| "The peak now takes the session's marked equity" | **True at the session close only** — claim 5 |
| "`PORTFOLIO_SCHEMA_VERSION` moves to 3. Still no migration -- no state file has ever been written, and the schedule remains disabled" | **True on both counts** |
| "ruff clean; mypy clean on 141 files; 1166 tests passing (was 1157)" | **True** |

Static gates and suite re-run here:

```
$ .venv/Scripts/python.exe -m ruff check .
All checks passed!
$ .venv/Scripts/python.exe -m mypy src
Success: no issues found in 141 source files
$ .venv/Scripts/python.exe -m pytest -q
================= 1166 passed, 1 warning in 84.32s (0:01:24) ==================
```

Schedule state, checked rather than assumed:

```
$ Get-ScheduledTask | ? { $_.TaskName -match 'quant|paper|QuantOS' }
TaskName                       State
--------                       -----
QuantOS Mizan Paper Session    Disabled
QuantOS-DailyAutoSync          Ready
```

And no state file exists (claim 6).

### P2-4 -- the commit names the wrong switch. `TOTAL_MAX_DRAWDOWN_BREACHED` is unreachable

The message is built on the total-drawdown switch: "Making the **total-drawdown** switch trippable
exposed that nothing persisted it. A **14% breach** halted trading for the rest of one session".
A 14% breach does not reach the total check. `governor.py:186-206` tests the daily limit first and
returns:

```
=== 1. commit message: "A 14% breach ... the total-drawdown switch" ===
   5% below the all-time peak -> DAILY_DRAWDOWN_LIMIT_BREACHED: 5.00% >= 4.00%
   10% below the all-time peak -> DAILY_DRAWDOWN_LIMIT_BREACHED: 10.00% >= 4.00%
   14% below the all-time peak -> DAILY_DRAWDOWN_LIMIT_BREACHED: 14.00% >= 4.00%
   20% below the all-time peak -> DAILY_DRAWDOWN_LIMIT_BREACHED: 20.00% >= 4.00%
   TOTAL_MAX_DRAWDOWN_BREACHED is unreachable: the daily check at governor.py:190 returns first.
```

This is not a wording quibble. The author reasoned about a 12%/8% limit and shipped a mechanism that
fires at 4%/3%, permanently, and wrote the `halt_reason` field that will record the name of a switch
the message never discusses. It is the same class as round 2's section 12.1: a repair justified by a
mechanism the code does not have. P1-1 is the consequence.

### P3-6 -- the `carry_in_positions` docstring overstates what the replay reconstructs

> "The fills are replayed through the ledger's own `process_fill`, so lot accounting, cost basis and
> each lot's `entry_fee` are **reconstructed by the ledger rather than asserted**."

```
=== 3. carry_in_positions docstring: "lot accounting ... reconstructed by the ledger" ===
   two real lots: [(100, '900.50'), (100, '1100.60')]
   after the carry : [(200, '1000.55')]
   -> one synthetic lot at the average, not two reconstructed lots.
```

`carry_forward_fills` emits one fill per *symbol* at the position's average price with the summed
entry fee, so the FIFO structure is destroyed and a later partial close prices against the average
rather than the oldest lot. That defect is round 2's P3-A and is not new; the docstring asserting
the opposite is new.

### Confirmed still false, still uncorrected -- round 2 P2-A

`run_paper_pilot_session.py:1198-1200`:

> "Written after reconciliation so a session that fails to reconcile does not advance the portfolio."

```
   1196: reconciliation = engine.end_session(timestamp=final_now, close_prices=final_prices)
   1200: # Written after reconciliation so a session that fails to reconcile does not advance the
   1204: (f.fee for f in engine.fills if not f.fill_id.startswith("carry_")), Decimal("0.00")
   1225: session_peak_equity=max(governor.all_time_peak_equity, reconciliation.total_equity),
   1228: governor.kill_events[-1].reason if governor.is_killed and governor.kill_events else ""
   1231: save_portfolio(PORTFOLIO_STATE_PATH, portfolio)
   -> no branch on reconciliation.reconciled anywhere between end_session and save_portfolio.
```

`86d1769c` adds two more fields to the write this comment claims is gated, including the one that
decides whether the system ever trades again.

### P3-7 -- exit 8 lands in an exit space that already collides

`run_paper_pilot_session.py` now returns 0, 1 (bad `--date`), 2 (unhandled exception), 7 (failed
reconciliation) and 8 (halted). `run_scheduled_paper_session.py` returns its own 2
(`NotATradingDay`), 3, 4, 5 -- and then propagates the session's return code verbatim at `:262`. So
**exit 2 from the scheduled wrapper means either "today is a public holiday" or "the session crashed
with an unhandled exception"**, which are opposite operational meanings. Exit 8 is distinct today,
which is what makes the collision beside it worth naming rather than repeating.

### Compounding note -- the swallowed loop exception now persists a permanent halt

`:1185-1186` catches every exception from the trading loop, logs it, and continues to `end_session`,
`save_portfolio` and a full report (round 2's P2-C). With `86d1769c`, that path also persists
`risk_halted=governor.is_killed`. A session that tripped the switch and then crashed still writes a
permanent halt, a full green markdown report and an advanced `sessions_held`, in one pass.

## Coverage

| Family | What was attacked |
|---|---|
| 1 Input boundaries | Carry of 0 / 1 / 2 / 500 names; the same symbol twice; oversell 150 of 100; `risk_halted` as `"false"`, `"0"`, `""`, `0`, `1`, `None`, `[]`, `"no"`; `halt_reason` at 5,000 chars |
| 2 Identity, authorization, tenancy | Not applicable to this commit; no multi-tenant or auth surface is touched |
| 3 Concurrency and ordering | Two overlapping sessions racing `portfolio_state.json` (P2-5); double `carry_in_positions` against the ledger's fill-id idempotency (P3-8); carry after `start_session` / `halt_session` / `end_session` |
| 4 Failure injection | Missing close price for a held name; v2 file with a valid hash; v3 file missing each new field; hand-edited `risk_halted` against the content hash; deleted state file |
| 5 State machine | Every route to `INITIALIZED`; re-used engine across two sessions; carried name sold to flat then re-bought; halt -> resume -> carry |
| 6 Scale | 500-name carried book through `carry_in_positions` and `end_session`; 4,000-path equity simulation of the halt trigger |
| 7 Money and counting | Cross-session vs same-session round trip; 12-session cumulative P&L against the cash movement; carry cash drift over 11 sessions; entry fee charged once; hold length exactly 10 |
| 8 Data integrity | Unicode / RTL / zero-width / emoji / newline / 5,000-char `halt_reason` through `canonical_sha256`; FIFO lot collapse across the carry; the audit log for a carried session |
| 9 Security surface | The content-hash refusal path and what it costs the documented recovery (P1-2) |
| 10 The human path | The operator who follows the refusal message's instructions; the operator who then deletes the file; the operator who runs the script by hand while the schedule fires |
| 11 Operability | What a refused session writes; what the dashboard serves afterwards; the wrapper's exit-code space; alarm on absence |
| 12 Assumption archaeology | Every claim in the commit message; every new comment and docstring; `reset_session_peak`'s zero callers; the `carry_` filter that filters nothing; the "written after reconciliation" comment |

Probes: 10 scripts, all under the session scratchpad, none in the repository. Two full-suite runs
(baseline and one mutation), one full-suite coverage run, `ruff check .`, `mypy src`, one scheduled-
task query. Targets: `src/quant_system/execution/paper_pilot.py`,
`src/quant_system/execution/paper_portfolio.py`, `src/quant_system/risk/governor.py`,
`src/quant_system/core/ledger.py`, `scripts/run_paper_pilot_session.py`,
`scripts/run_scheduled_paper_session.py`, `tests/test_paper_pilot_carried_session.py`.

## NOT PROBED

The most important section. Everything below is a known unknown, not a clean bill.

1. **`run_paper_session` was never executed.** It needs a live Upstox feed, the Mizan model store and
   a NIFTY500 cross-section, and no test harness exists. **P1-1, P1-2, P1-3 and P2-1 all live in that
   function.** They are established by reading the code plus component-level reproduction of every
   step (governor construction, `evaluate_order`, `state_from_ledger`, `save_portfolio`,
   `load_portfolio`) driven with the runner's own literal arguments. Nobody has watched the real
   thing exit 8.
2. **The real equity path is unknown.** The 99.9%/median-30 figure comes from a zero-drift lognormal
   walk at 0.8-1.5% session volatility, not from the strategy's realised returns. The paper portfolio
   has never run, so no equity curve exists to test against. The *mechanism* is exact; the *rate* is
   a model.
3. **The scheduled path end-to-end.** `run_scheduled_paper_session.cmd` under Task Scheduler was not
   executed. The task's `Disabled` state was queried; the refresh, the calendar gate and the log
   redirection were not exercised.
4. **Crash-during-write.** No SIGKILL between `staging.write_text` and `staging.replace`, no disk-full
   simulation, no partial-write recovery test. `replace` is atomic on NTFS for a same-volume rename;
   that was assumed, not measured.
5. **The concurrency finding is a simulated interleaving, not a real race.** Two processes were not
   run simultaneously. The absence of any lock is a code fact; the timing window was not measured.
6. **The `end_session` crash when a carried name loses its closing price** (brief known-open item 4).
   The mechanism was confirmed; what a real universe change does to a 500-name book, and whether any
   NIFTY500 name has actually left the universe in the window, was not tested.
7. **The server and dashboard surfaces.** `server/app.py:1235`, `scripts/serve_live_dashboard.py` and
   `scripts/view_live_pnl.py` were identified as readers of the stale status file by grep. None was
   started, and no HTTP request was made.
8. **Timezone and clock.** `halted_on` derives from `now_ist().date()`; behaviour across the IST day
   boundary, a clock jump, or a session started before midnight UTC was not probed.
9. **Mutation coverage is one mutation, not a sweep.** Only "the reconciliation always passes" was
   run. `paper_pilot.py` has 366 statements; no systematic mutation sweep was attempted, so P2-3
   should be read as one proven hole, not as a bound on how many exist.
10. **Round 2's remaining 14 P2 / 7 P3 were not re-adjudicated**, beyond P2-A, P2-O, P3-A and P3-E,
    which this commit touches. They are assumed still open per the brief.
11. **Everything outside this commit's blast radius.** The cross-section builder, the coverage gate,
    the calendar authority, the `RESEARCH_PAPER` exemption, the evidence store and the Mizan feature
    kernel were not re-examined at all.
12. **The `_carried_positions` baseline cannot be independently validated.** It and the ledger's
    carried quantity both derive from the same `carry_forward_fills` output, so check (b) no longer
    cross-checks the carry itself -- only today's fills. Whether the `state_hash` is a sufficient
    substitute for that lost independence was reasoned about, not tested against a tampered-and-
    rehashed file with a plausible attacker model.
