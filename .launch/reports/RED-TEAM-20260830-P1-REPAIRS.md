# Red Team report — the repairs to the live paper-trading path (2026-08-30)

STATUS: COMPLETE
VERDICT: **NOT READY.** 2 P1 Critical, 15 P2 Major, 7 P3 Minor.
BRIEF: `.launch/RED-TEAM-BRIEF-20260830-P1-REPAIRS.md`
PRIOR REPORT: `.launch/reports/RED-TEAM-20260829-LIVE-PAPER-PATH.md` (8 P1, 11 P2, 2 P3, NOT READY)
ADJUDICATOR: Claude Code, Red Team. Authored none of the commits in scope.
REPO REVISION UNDER TEST: `c45ee6f8` (branch `main`)
RUN_UTC: 2026-08-30

This file is written incrementally, one claim at a time, by design. A previous attempt at this class
of task died mid-run and produced nothing because it batched the write to the end.

## Commits in scope

| Commit | Claims |
|---|---|
| `2d5f6d31` | P1-1: `RESEARCH_PAPER` surface + `ResearchPaperExemptionV1` + gated loader |
| `bb62bc58` | P1-2..P1-8 and P2-3, P2-6, P2-9, 5.2, 5.4 |
| `c45ee6f8` | P2-1(recorded), P2-2, P2-5, P2-8, P3-1, P3-2 |

## Verdict summary

| # | Claim | Verdict |
|---|---|---|
| 1 | Carry-forward P&L repair (`entry_fee` carried, replay charges it, funding covers it) | **PROVEN for the money.** The funding change breaks reconciliation — new **P1** |
| 2 | Cumulative realized P&L = `previous.realized_pnl + session_realized_pnl` | **PROVEN** — no double count. Residual: no re-run idempotency (P2) |
| 3 | The hold length is exactly 10 sessions | **PROVEN** — 10, fresh and resumed-from-disk |
| 4 | Score-floor removal is faithful to the screen; empty-selection guard | **PROVEN** — floor gone, guard unbypassable. P2-6 only half repaired (P3) |
| 5 | Sizing from `ledger_funding()` does not double-count carried holdings | **PARTLY DISPROVEN** — cost basis is not equity; a no-op under unrealized loss (P2) |
| 6 | The trading-day authority and its guards fail closed | **Mostly PROVEN** — right segment, bound refuses 0 legitimate 2026 sessions. Partial corruption fails **open** (P2) |
| 7 | Exits before entries — nothing broke in the swap | **Nothing broke. Nothing changed** — measurable no-op, false justification (P2) |
| 8 | `peak_equity` monotonic and persisted; the 12% switch can trip | **PROVEN — demonstrated tripping.** But the kill state is not persisted — new **P1** |
| 9 | The RESEARCH_PAPER exemption is genuinely narrow | **PROVEN for the gate.** The chokepoint claim is not — detector and server bypasses (P2) |
| 10 | The rank-sort repair and its retraction | **Retraction CORRECT.** The fidelity test cannot detect a revert (P2) |
| 11 | The 264 restored evidence files | **PROVEN** — 0 of 16,677 differ from their blobs. The new guard is category-only (P2) |
| 12 | Anything overstated, missed, or broken while repairing | **CONFIRMED** — 2 new **P1**, 3 false commit claims, and no test reaches a carried `end_session` |

## Verdict

**NOT READY. 2 P1 Critical, 15 P2 Major, 7 P3 Minor.**

The repairs are substantially real. Seven of the prior report's eight P1s are closed and I could not
reopen them: the cross-session P&L is exact to the paisa, the hold is exactly ten sessions, the
score floor is gone and the liquidation path is doubly gated, the holiday guard asks the right
question, `--skip-refresh` is deleted, and the drawdown switch demonstrably trips. The eighth
(P1-5, sizing) is genuinely reduced but not closed.

Two new P1s. Both were **created or exposed by the repairs themselves**, which is the specific risk
this pass exists to catch:

1. Funding the ledger for the carry replay and then making a failed reconciliation exit non-zero
   means **every session that holds a position exits 7** — nine sessions in ten, by design — while
   the portfolio state advances underneath it.
2. Making the total-drawdown switch trippable revealed that **the kill state is not persisted**, so a
   12% breach halts one session, refuses the exits that would reduce the book, resets the hold clock,
   and is forgotten the next morning.

Neither is visible to ruff, mypy or the 1157-test suite, for a structural reason: **no test in the
repository reaches `PaperPilotEngine.end_session` with a carried position.**

## Findings ranked by severity

### P1 Critical

| # | Finding | Claim |
|---|---|---|
| P1-A | Every session that carries a position fails reconciliation (`POSITION_MISMATCH`) and now exits 7; state still advances | 1 |
| P1-B | The total-drawdown kill switch is not persisted; a breach halts one session, retains the losing book, and is forgotten | 8 |

### P2 Major

| # | Finding | Claim |
|---|---|---|
| P2-A | `save_portfolio` runs before any reconciliation gate, contradicting its own comment | 1 |
| P2-B | No session idempotency; re-running one calendar day shortens the hold | 2 |
| P2-C | `rebalanced` records intent, not outcome; a crashed session still resets the hold clock | 3 |
| P2-D | `ledger_funding()` values holdings at cost, so sizing is a no-op under an unrealized loss | 5 |
| P2-E | A calendar keeping `covers_years` but losing `holidays` runs a session on a real NSE holiday | 6 |
| P2-F | The exits-before-entries swap is a no-op and its stated justification is false | 7 |
| P2-G | A partially filled exit is re-proposed at full size while the first order is open | 7 |
| P2-H | `peak_equity` records cost basis, so unrealized gains never enter the high-water mark | 8 |
| P2-I | The drawdown switch is evaluated only when an order is proposed | 8 |
| P2-J | The AST detector is defeated five ways; it scans 1 of 33 scripts and nothing under `src/` | 9 |
| P2-K | `POST /api/models/mizan/upload` swaps the global model, verdict unchecked and unauthenticated | 9 |
| P2-L | `test_mizan_store_fidelity.py` cannot detect a revert of the repair it accompanies | 10 |
| P2-M | The evidence guard compares line-ending categories, not bytes; 46% of files cannot trip it | 11 |
| P2-N | One symbol lagging by a session aborts the whole cross-section, bypassing the 90% tolerance | 12 |
| P2-O | No test reaches `end_session` with a carried position; the `peak_equity` test asserts a round trip | 12 |

### P3 Minor

| # | Finding | Claim |
|---|---|---|
| P3-A | The carry collapses FIFO lots; a partial close after a carry reports different P&L | 1 |
| P3-B | The selection count takes the ceiling where the screen truncates; 79% of population sizes differ | 4 |
| P3-C | The sizing base includes `carried_entry_fees`, money already paid to the exchange | 5 |
| P3-D | A malformed calendar refuses by unhandled `JSONDecodeError`, not the documented typed refusal | 6 |
| P3-E | Two repair comments describe behaviour the code does not have | 12 |
| P3-F | `per_name_alloc` does not budget the entry fee; a full deployment lands at 4.883% against a 5% buffer | 12 |
| P3-G | `return_pct` uses the CLI nominal while the same table prints `ledger_funding()` as "Initial Capital" | 12 |

## What survived attack

- **The carry-forward money is exact.** 300 randomised portfolios, long-tail costs and fees: worst
  cash drift **0**. A position held seven sessions carries its entry fee once, never seven times.
  The cross-session round trip reports 9538.00, identical to the same-session one.
- **Cumulative realized P&L is right**, and reconciles to the cash movement to the paisa across nine
  sessions and two round trips, one winner and one loser.
- **The hold is exactly 10 sessions**, fresh and resumed-from-disk on every session.
- **The empty-selection guard cannot be bypassed.** Three independent barriers.
- **The 4-day staleness bound refuses zero legitimate 2026 sessions** — verified against every
  trading day derived from the committed calendar.
- **The drawdown switch trips.** Demonstrated at session 10 of a simulated decline.
- **The verdict matrix holds.** `REJECT` executes on no surface; the exemption is refused everywhere
  else; a promotable model is refused on `RESEARCH_PAPER`.
- **The evidence restore is complete**: 0 of 16,677 tracked files differ from their committed blob,
  verified by blob SHA-1 independently of the repository's own test.
- **The rank-sort retraction is correct**, proven by float hex on the real store.
- **The feature-kernel refactor is value-preserving**: 48 rows across three symbols still reproduce
  the published store text-identically, including across the 400-bar cap.
- Ruff clean; mypy clean on 141 files; **1157 tests passing in 75.07s**.

---

## Claim 1 — the carry-forward P&L repair

**VERDICT: the money repair is PROVEN — realized P&L now nets both legs and cash stays exact. But
the funding change it required breaks the session's reconciliation, and the P2-9 repair in the same
commit turns that into a hard exit 7. The live paper path can no longer complete a green session
once it holds anything.**

### What holds

`scratchpad/probe_c1.py`, real `DecimalLedger` and real `PaperPortfolioState`, no mocks:

```
A. same-session vs cross-session round trip, clean numbers
SAME-session   realized=9538.00  cash=1009538.00
CROSS-session  realized=9538.00  cash=1009538.00
  realized delta = 0.00   cash delta = 0.00

D. multi-session carry: does entry_fee drift or double-count over N holds?
  hold session 1: cash=899780.00 entry_fee=220.00 basis=100000.00 funding=1000000.00 realized=0.00
  ...
  hold session 7: cash=899780.00 entry_fee=220.00 basis=100000.00 funding=1000000.00 realized=0.00
  after sell on session 9: cumulative realized=9538.00 cash=1009538.00
  TRUTH (same-session equivalent) = 9538.00, cash = 1009538.00

E. fuzz: 300 random portfolios, cash exactness + funding exactness under fees
  worst cash drift over 300 random portfolios = 0  case=None
  every carried entry_fee reproduced exactly in the fresh ledger's lots: OK
```

Prior finding P1-2 (`9758.00` against a true `9538.00`) is closed. The mechanism does not
double-count: `state_from_ledger` re-reads `entry_fee` from `DecimalLedger.lots` every session
(`scripts/run_paper_pilot_session.py:1193-1196`), so a position held seven sessions carries `220.00`
seven times, never `1540.00`. Cash exactness survives because `ledger_funding()`
(`src/quant_system/execution/paper_portfolio.py:151`) adds `carried_entry_fees` and the replay fill
debits `gross + fee` (`src/quant_system/core/domain.py:206-209`) — the same quantity, cancelling by
construction. 300 randomised portfolios up to 40 holdings, long-tail average costs and fees: worst
drift **0**, every carried `entry_fee` reproduced exactly in the fresh ledger's lots.

### But the funding change breaks reconciliation, and the P2-9 repair makes it fatal

`PaperPilotEngine.end_session` check (b) (`src/quant_system/execution/paper_pilot.py:791-801`)
reconciles `self.ledger.positions` against `self._fills`. The carry replay goes through
`engine.ledger.process_fill(carry_fill)` (`scripts/run_paper_pilot_session.py:809-811`), which never
touches `_fills` — that list is appended only at `paper_pilot.py:622`, inside the order-fill path.

`scratchpad/probe_c1b.py`, real `PaperPilotEngine`, two carried holdings, flat prices, no trades:

```
carried cash          = 50000.00
holdings at cost      = 950000.00
carried entry fees    = 2120.00
ledger_funding()      = 1002120.00
TRUE starting equity  = 1000000.00  (cash + basis)

after replay: ledger cash = 50000.00  (carried cash was 50000.00) -> exact: True
engine.fills after replay = 0  (carry fills bypass the engine fill log)

reconciled            = False
reconciliation_errors = [POSITION_MISMATCH for ACME: Ledger 100 != Net Fills 0,
                         POSITION_MISMATCH for BETA: Ledger 500 != Net Fills 0]
discrepancy_paisa     = 0.00
```

Cash reconciles (`discrepancy_paisa = 0.00`) because carry fills do create ledger transactions.
Positions do not, because they create no engine fills.

Before `bb62bc58` this was invisible — which is precisely prior finding P2-9, "SUCCESS banner and
exit 0 on a failed reconciliation". `bb62bc58` repaired P2-9 at
`scripts/run_paper_pilot_session.py:1481-1487`, returning 7 when `reconciled` is false. The honest
exit code now fires on a condition that is true on **every session ending with a position it did not
buy today**: every hold session (nine of every ten, by design) and every rebalance session that
retains a name. `scripts/run_scheduled_paper_session.py:260-262` returns the child code verbatim, so
the unattended weekday task reports failure daily.

The state still advances. `save_portfolio` is called at `scripts/run_paper_pilot_session.py:1208`,
unconditionally, before `main()` ever inspects `reconciled`. The comment at `:1185-1186` — "Written
after reconciliation so a session that fails to reconcile does not advance the portfolio" —
describes a protection that does not exist: `end_session` *computes* the reconciliation, it does not
gate anything. This is the same false comment the prior report flagged at 5.5, still present.

The reconciliation break is **loud** (exit 7, printed errors) and will be noticed on the first hold
session. The state advance underneath it is **silent**.

### Two smaller divergences the repair does not cover

**Multi-lot entry.** `Position.average_price` is quantized to the paisa
(`src/quant_system/core/ledger.py:498`) and the carry writes that quantized average as the holding
basis, so a symbol filled by two partial fills at different prices reports a slightly different
realized P&L across a session boundary:

```
B. multi-lot entry (two partial fills at different prices) -> average_price quantizes
  1@100.00 + 2@100.01: same=5677.98 cross=5677.97 dPNL=-0.01 dCASH=0.00   <-- DIVERGES
  60@1000.00 + 40@1000.05: same=99976.00 cross=99976.00 dPNL=0.00 dCASH=0.00
  7@333.33 + 6@333.37: same=21644.47 cross=21644.45 dPNL=-0.02 dCASH=0.00   <-- DIVERGES
  1@10.00 + 2@10.01: same=5947.98 cross=5947.97 dPNL=-0.01 dCASH=0.00   <-- DIVERGES
```

Reachable: `paper_pilot.py:606` increments `fill_index` per order, so one order can produce several
fills at different vwap prices. Cash is unaffected; magnitude is one or two paisa per position.

**FIFO is collapsed by the carry.** The replay emits one fill per symbol at the aggregate average
cost, so multiple entry lots become a single average lot and a *partial* close loses FIFO
attribution:

```
C. partial sell after a carry (FIFO collapsed to one average lot)
  SAME-session, sell first 50 (FIFO @1000): realized=24725.00
  CROSS-session, sell 50 (avg @1100):       realized=19714.00
  divergence = -5011.00
```

That construction is deliberately extreme (two lots 20% apart); in practice the lots differ only by
intra-session slippage, so the real magnitude is small. The structural point stands and is
undocumented: `paper_portfolio.py:156-169` says "Nothing is invented: the replay states the position
was acquired at that basis and cost that fee, both of which are true" — true of the aggregate, false
of the lot structure the ledger own FIFO accounting depends on.

FINDING   Every session that carries a position fails reconciliation with POSITION_MISMATCH; the P2-9 repair now makes that exit 7
FAMILY    Assumption archaeology / failure injection / operability
REPRO     `python scratchpad/probe_c1b.py` — two carried holdings, no trades, `reconciled=False`, POSITION_MISMATCH for both
OBSERVED  `end_session` check (b) compares `ledger.positions` to `engine._fills`; the carry replay at `run_paper_pilot_session.py:811` bypasses `_fills`. `main()` returns 7 (`:1487`); `run_scheduled_paper_session.py:262` propagates it
EXPECTED  A carried position reconciles, or the reconciliation is told about the carry-forward baseline
BLAST     Every hold session (9 of 10 by design) and every rebalance session that retains a name. The unattended weekday task reports failure daily while the portfolio silently advances underneath it
SEVERITY  **P1 Critical** — the critical path is broken, and the state file advances on a session the runner itself declares failed

FINDING   `save_portfolio` runs before any reconciliation gate, contradicting its own comment
FAMILY    State machine / failure injection
REPRO     Read `scripts/run_paper_pilot_session.py:1183-1208` against `:1477-1487`
OBSERVED  State is persisted unconditionally at `:1208`; `reconciled` is not consulted until `main()`, after the write
EXPECTED  Either the write is gated on `reconciliation.reconciled`, or the comment is removed
BLAST     Every failed-reconciliation session still advances `sessions_completed`, `sessions_held` and the rebalance clock
SEVERITY  P2 Major

FINDING   The carry collapses FIFO lots into one average lot; a partial close after a carry reports different P&L than the same trade without the boundary
FAMILY    Money and counting
REPRO     `python scratchpad/probe_c1.py` sections B and C
OBSERVED  1-2 paisa from `average_price` quantization; construction-dependent divergence from FIFO collapse on a partial close
EXPECTED  The divergence documented, or lot structure carried
BLAST     Any position filled by more than one fill, i.e. any partially filled order. Cash unaffected
SEVERITY  P3 Minor

---

## Claim 2 — cumulative realized P&L

**VERDICT: PROVEN. `previous.realized_pnl + session_realized_pnl` does not double-count a carried
position's gain, and the cumulative figure reconciles to the cash movement exactly. Prior finding
P2-3 is closed. One residual: nothing makes a session idempotent, so re-running one calendar day
advances the counters twice.**

### The arithmetic: no double count

The carried gain cannot be counted twice because the carry replay is a **BUY**, which produces no
realized P&L in a fresh ledger, and `session_realized_pnl` is `engine.ledger.realized_pnl` from a
ledger constructed that session (`scripts/run_paper_pilot_session.py:1197-1207`). The entry fee is
attributed by `DecimalLedger` when the lot closes (`src/quant_system/core/ledger.py:406-408`), i.e.
exactly once, in the session that closes it.

`scratchpad/probe_c2.py`, nine sessions, two full round trips, one winner and one loser:

```
  s0 buy   session_realized=      0.00  cumulative=      0.00  cash=   899780.00  fees=  220.00  held=1
  s1 hold  session_realized=      0.00  cumulative=      0.00  cash=   899780.00  fees=  220.00  held=2
  s2 hold  session_realized=      0.00  cumulative=      0.00  cash=   899780.00  fees=  220.00  held=3
  s3 sell  session_realized=   9538.00  cumulative=   9538.00  cash=  1009538.00  fees=  462.00  held=1
  s4 buy   session_realized=      0.00  cumulative=   9538.00  cash=   909318.00  fees=  682.00  held=1
  s5 hold  session_realized=      0.00  cumulative=   9538.00  cash=   909318.00  fees=  682.00  held=2
  s6 sell  session_realized=  -5429.00  cumulative=   4109.00  cash=  1004109.00  fees=  891.00  held=1
  s7 hold  session_realized=      0.00  cumulative=   4109.00  cash=  1004109.00  fees=  891.00  held=2
  s8 hold  session_realized=      0.00  cumulative=   4109.00  cash=  1004109.00  fees=  891.00  held=3
  TRUE cumulative realized = 4109.00
  persisted cumulative     = 4109.00
  cash check: 1000000 + cumulative = 1004109.00 vs actual 1004109.00
```

The independent check is the last line: with the book flat, cash must equal opening capital plus
cumulative realized P&L. It does, to the paisa. The winner is counted once at s3 and the loser once
at s6; the three idle sessions between them change nothing, which is the exact failure P2-3
described (one idle session used to zero a real P&L).

### Residual: no session is idempotent

`last_rebalance_on` is written (`paper_portfolio.py:352`) and read back on load (`:297`) but is
**never consulted by any decision** — `grep -rn "last_rebalance_on" --include=*.py .` returns only
the dataclass field, the serializer, the loader, `state_from_ledger`, and one test assertion. There
is no same-day guard anywhere in `scripts/run_paper_pilot_session.py`.

```
=== B. running the SAME session twice (double-click / retry after success) ===
  after the sell : realized=9538.00 cash=1009538.00 sessions=2 held=1
  re-run same day: realized=9538.00 cash=1009538.00 sessions=3 held=1
  -> sessions_completed advanced twice for one calendar day: 3
```

Money is safe under a re-run (the second run has nothing left to trade, so `realized_pnl` and `cash`
are unchanged). The **clock** is not: a re-run of a *hold* session increments `sessions_held` a
second time, so the position exits one session early. Two re-runs exit two sessions early. This is
the retry-after-success case in a script whose whole design is an unattended weekday schedule, and
whose reconciliation now exits 7 on every hold session (Claim 1) — an operator who sees exit 7 and
re-runs the session shortens the hold silently.

FINDING   No session is idempotent; re-running one calendar day advances `sessions_held` and shortens the hold
FAMILY    Concurrency and ordering / the human path
REPRO     `python scratchpad/probe_c2.py` section B — `sessions_completed` 2 -> 3 for one calendar day
OBSERVED  `last_rebalance_on` is persisted but never read; no guard compares `session_date` to the state
EXPECTED  A same-session-date re-run is refused, or is a no-op against the persisted state
BLAST     The hold length, silently. Most likely to be hit precisely because Claim 1 makes every hold session exit 7 and invite a retry
SEVERITY  P2 Major (escalated from Minor: silent, and it corrupts the one quantity Claim 3 exists to pin)

---

## Claim 3 — the hold length

**VERDICT: PROVEN. The executed hold is exactly 10 sessions, matching
`screen_mizan_out_of_sample.py:HOLD_SESSIONS = 10`. Both off-by-ones in prior finding P1-3 are
closed, and the fix survives a resume from disk on every session.**

### Simulated independently, real functions, real model card

`scratchpad/probe_c3.py` drives the real `rebalance_due` and the real `state_from_ledger` with the
real `MizanModel.default_model().config`:

```
model card label_horizon_sessions = 11  -> rebalance_due converts to a held length of 10

session sessions_held rebalance_due holdings
      0             0          True        0
      1             1         False        1
      ...
      9             9         False        1
     10            10          True        1

entry session index = 0
next rebalance      = 10
EXECUTED hold       = 10 sessions   (screen measured 10)

resumed-from-disk every session: entry=0 exit=10 hold=10 sessions
```

The second line is the brief's specific question: the same simulation with
`save_portfolio` -> `load_portfolio` between **every** session gives the identical answer, so the
`sessions_held` convention round-trips through the persisted schema without drift.

Boundary behaviour and the degenerate-horizon guard both hold:

```
  sessions_held=  9 -> rebalance_due(11) = False
  sessions_held= 10 -> rebalance_due(11) = True
  sessions_held= 11 -> rebalance_due(11) = True
  horizon=0: raises PaperPortfolioError: a label horizon of 0 holds for no sessions at all; ...
  horizon=1: raises PaperPortfolioError: ...
  horizon=2: True
  horizon=-5: raises PaperPortfolioError: ...
```

`>=` rather than `==` means a state that somehow overshoots still rebalances rather than holding
forever — the safe direction. The conversion lives in `rebalance_due`
(`src/quant_system/execution/paper_portfolio.py:200-207`), not at the call site, so the caller
cannot pick the wrong convention; and the runner log line at
`scripts/run_paper_pilot_session.py:660-666` prints `horizon - 1`, consistent with what actually
executes.

### The rebalance-with-no-trades case: behaviour is correct, but it is intent, not outcome

```
=== rebalance session that produced NO trades: does the clock still reset? ===
  before: sessions_held=10 rebalance_due=True
  after : sessions_held=1  opened_on=2026-01-01 (unchanged)
```

Resetting the clock on a rebalance that retained every name is **faithful to the screen** — the
screen re-ranks at the horizon and re-selects, and a name that stays in the top 20% is held another
ten. So this is not a defect on its own.

It becomes one in combination with the swallowed exception. `rebalanced=rebalancing` is the session's
*intent*, computed at `scripts/run_paper_pilot_session.py:658`, not a fact about what happened. The
bare `except Exception` at `:1170-1171` logs and falls through to `end_session` and
`save_portfolio`, so a session that raised before placing a single order still writes
`sessions_held = 1` and pushes the next rebalance a full horizon away. That is prior finding 5.5,
unrepaired, and Claim 1 has now made an abnormal session exit far more likely.

FINDING   `rebalanced` records the session's intent, not its outcome; a crashed session still resets the hold clock
FAMILY    State machine / failure injection
REPRO     Read `scripts/run_paper_pilot_session.py:658` (`rebalancing = portfolio.rebalance_due(horizon)`), `:1170-1171` (bare except), `:1204` (`rebalanced=rebalancing`), `:1208` (unconditional save)
OBSERVED  An exception anywhere in the trading loop is logged and swallowed; the portfolio is still persisted with `sessions_held = 1`
EXPECTED  The clock advances only if the rebalance actually completed
BLAST     Any exception in the ~25-step loop delays the next rebalance by a full 10 sessions, silently
SEVERITY  P2 Major (carried forward from the prior report's 5.5, still open)

---

## Claim 4 — the score floor removal

**VERDICT: PROVEN that the screen has no threshold and that the floor is gone from the executing
path. The empty-selection guard is genuinely unreachable-by-accident and correctly belt-and-braces.
But the same commit claims to repair P2-6, and P2-6 had two halves: the threshold half is closed and
the count-rounding half is not — the live count differs from the screen on **79% of population
sizes**.**

### The screen really has no threshold

`grep -ci "threshold" scripts/screen_mizan_out_of_sample.py` -> `0`. The entire selection is
`:200-202`:

```python
scores.sort(key=lambda item: -item[0])
take = max(1, int(len(scores) * SELECTION_FRACTION))
selected.append(statistics.fmean([target for _, target in scores[:take]]))
```

No score filter anywhere in the file. The prior report's 5.1/7.2 reading is correct, and the removal
is faithful.

`select_top_fraction` (`src/quant_system/execution/mizan_live_features.py:165-194`) now has
`score_threshold: float | None = None`, and the runner calls it with two positional arguments only
(`scripts/run_paper_pilot_session.py:738`). The parameter is retained for other callers; on this
path it is unreachable.

### The empty-selection guard cannot be bypassed

Three independent facts close it:

1. `select_top_fraction` returns `()` **only** when `scores` is empty —
   `take = min(population, max(1, ...))` guarantees at least one name otherwise. Verified:

```
  n=1 fraction=0.001 -> 1 name(s)
  n=2 fraction=0.001 -> 1 name(s)
  n=3 fraction=0.001 -> 1 name(s)
  all-negative scores, n=10, f=0.2 -> ('S0', 'S1')
  empty scores -> ()
```

2. `mizan_scores` can only be empty if the post-refusal cross-section is empty, and the coverage gate
   at `run_paper_pilot_session.py:716-721` now runs **after** `refuse_extreme_rows` and after
   `with_extreme_refusals`, so an empty cross-section gives `fraction = 0.0 < 0.90` and raises. That
   raise sits outside the loop's `try`, so it propagates to `main()` and exits 2 — fail-closed.

3. Even if `top_picks` were empty, both loops are gated:
   `if rebalancing and top_picks else []` (`:975`) and `for sym in top_picks if rebalancing else []`
   (`:1006`), with an explicit `logger.error` at `:969-974`.

Prior P1-4 (the whole book liquidated when no name clears the floor) is closed twice over.

One residual in the guard's aftermath: when the selection is empty the session still writes
`rebalanced=True` (`:1204`), so `sessions_held` resets to 1 and the next rebalance is a full ten
sessions away even though nothing was re-ranked. Same intent-versus-outcome defect recorded under
Claim 3.

### P2-6's other half is still open

`bb62bc58` lists P2-6 as repaired. P2-6 was "Live selection adds an unmeasured score threshold **and
rounds the count the other way**". The screen truncates (`int`); the live path takes the ceiling
(`mizan_live_features.py:190`). `scratchpad/probe_c4.py`:

```
    n  screen int()  live ceil()  differ
   47             9           10  DIFFER
   99            19           20  DIFFER
  423            84           85  DIFFER
  499            99          100  DIFFER
  501           100          101  DIFFER

population sizes 2..500 where the live count differs from the screen: 396 of 499 (79%)
```

The docstring at `:171-175` justifies the ceiling on its own terms — "so a non-empty cross-section
always yields at least one name rather than silently abstaining" — but `max(1, ...)` already
guarantees that, so the ceiling buys nothing the code does not already have and costs fidelity to
the measured rule on four population sizes out of five. The NIFTY500 universe after coverage
filtering is exactly the regime where `0.2 * n` is not an integer.

FINDING   The live selection count takes the ceiling where the screen truncates; 79% of population sizes disagree
FAMILY    Assumption archaeology
REPRO     `python scratchpad/probe_c4.py` — 396 of 499 population sizes in 2..500 differ; n=423 gives 85 against the screen's 84
OBSERVED  `mizan_live_features.py:190` uses `math.ceil`; `screen_mizan_out_of_sample.py:201` uses `int`. `bb62bc58` records P2-6 as repaired
EXPECTED  Match the measured rule, or record that only the threshold half of P2-6 was repaired
BLAST     One extra name per rebalance, roughly 1.2% of the book misallocated relative to the screened construction. Small, systematic, and it makes live-versus-screen comparison inexact
SEVERITY  P3 Minor (the defect); the overstatement in the commit message is what raises it above cosmetic

---

## Claim 5 — sizing from `ledger_funding()`

**VERDICT: PARTLY DISPROVEN. It does not double-count in the way the brief asks — but
`ledger_funding()` values the book at **cost**, not at market, so on a book carrying an unrealized
loss the sizing base is exactly the old `initial_cash` constant and the repair is a no-op. The
concentration defect the commit says is "precisely" removed is reachable on every rebalance, at the
size of that cycle's unrealized move. It also sizes against `carried_entry_fees`, which is money
already paid to the exchange.**

### The double-count question, answered

`ledger_funding()` (`src/quant_system/execution/paper_portfolio.py:142-153`) is
`cash + holdings_value_at_cost + carried_entry_fees`. Retained names are neither sold (the exit loop
at `scripts/run_paper_pilot_session.py:975-976` skips `sym in top_picks`) nor re-bought (the entry
loop at `:1007-1008` skips `current_held != 0`), so no name consumes cash twice. There is no
double-count of deployed capital in the arithmetic.

But `carried_entry_fees` **is** money already deployed and unrecoverable: it was paid to the exchange
on entry and no sale returns it. Including it in the sizing base inflates every allocation by about
0.11% of the deployed book. Small, and it is exactly the thing the brief asked about — the book is
sized against equity it has already spent.

### The real defect: cost basis is not equity

`holdings_value_at_cost` sums `average_cost * quantity` (`paper_portfolio.py:97-98,131-134`). It does
not move when prices do. So the sizing base equals the *original nominal* for as long as the loss is
unrealized — and the rebalance sizing is computed at
`scripts/run_paper_pilot_session.py:757-765`, **before** any exit has filled and therefore before
any of that loss is realized.

`scratchpad/probe_c5.py`, a fully invested 50-name equal-weight book, full turnover at the
rebalance, real 0.11% statutory legs:

```
 unreal       funding   true equity    over by      alloc    realizable  names funded   of  unfunded
    +0%    1000000.00     998955.00    1045.00   19000.00     997910.00            52   50         0
    -2%    1000000.00     979955.00   20045.00   19000.00     978930.90            51   50         0
    -5%    1000000.00     951455.00   48545.00   19000.00     950462.25            49   50         1
   -10%    1000000.00     903955.00   96045.00   19000.00     903014.50            47   50         3
   -20%    1000000.00     808955.00  191045.00   19000.00     808119.00            42   50         8
   -30%    1000000.00     713955.00  286045.00   19000.00     713223.50            37   50        13
   +10%    1000000.00    1093955.00  -93955.00   19000.00    1092805.50            57   50         0
   +30%    1000000.00    1283955.00 -283955.00   19000.00    1282596.50            67   50         0

=== the prior defect, for comparison: sizing from the initial_cash constant ===
  unreal    +0%: OLD alloc=19000.00 funded=52 of 50
  unreal   -30%: OLD alloc=19000.00 funded=37 of 50
```

The last two lines are the point. At -30% unrealized the repaired code and the code it replaced
produce the **identical** allocation and the **identical** 37-of-50 outcome, because
`ledger_funding()` at cost is `1000000.00`, which is what `initial_cash` was. The repair changes
nothing until a loss has been *realized* by a completed rebalance — i.e. it corrects the position it
is already leaving, not the one it is entering.

Because `select_top_fraction` returns names strongest-first
(`src/quant_system/execution/mizan_live_features.py:145`), the names that go unfunded are the tail of
the ranking. That is verbatim the sentence the docstring uses to describe the defect being repaired:
"only the first ~N in rank order filled, the rest unexpressed — a concentrated bet on the head of a
ranking, which nobody validated".

For the default NIFTY500 top-20% selection the same mechanism scales with the count:

```
  unreal    -5%: alloc=9500.00 realizable=950462.25 funded=99 of 100 -> 1 names unfunded (1%)
  unreal   -10%: alloc=9500.00 realizable=903014.50 funded=94 of 100 -> 6 names unfunded (6%)
  unreal   -20%: alloc=9500.00 realizable=808119.00 funded=84 of 100 -> 16 names unfunded (16%)
```

The error is asymmetric and adverse in both directions: **over-committed exactly when the cycle lost
money**, and **under-invested exactly when it made money** — at +30% unrealized the book redeploys
950,000 of a realizable 1,282,596 and leaves 26% in cash against a declared 5% buffer, silently
scaling down the strategy after it works.

A -5% to -10% move over a ten-session hold is ordinary, not extreme, so the everyday magnitude is a
few names at the tail rather than thirteen. The defect is the class, the silence, and the claim that
it was removed.

FINDING   `ledger_funding()` values holdings at cost, so on an unrealized loss the sizing base is identical to the `initial_cash` constant it replaced
FAMILY    Money and counting / assumption archaeology
REPRO     `python scratchpad/probe_c5.py` — at -30% unrealized, new alloc 19000.00 funding 37 of 50; old alloc 19000.00 funding 37 of 50
OBSERVED  The head of the ranking is funded and the tail is unexpressed, in proportion to the cycle's unrealized loss; the reverse leaves up to 26% idle after a gain
EXPECTED  Size from realizable equity (cash + market value), or state that the base is cost basis and what that implies
BLAST     Every rebalance. Silent — the log prints one `per_name_alloc` and nothing reports how many picks went unfunded
SEVERITY  P2 Major (the prior P1-5 is genuinely reduced from cumulative drawdown to per-cycle unrealized move, but not closed, and the commit message says it is)

FINDING   The sizing base includes `carried_entry_fees`, money already paid to the exchange
FAMILY    Money and counting
REPRO     `src/quant_system/execution/paper_portfolio.py:151` — `cash + holdings_value_at_cost + carried_entry_fees`; used as `deployable` at `scripts/run_paper_pilot_session.py:763`
OBSERVED  Every allocation is inflated by roughly 0.11% of the deployed book
EXPECTED  `ledger_funding()` is the ledger seeding figure; the deployable figure is a different quantity
BLAST     Every rebalance, small magnitude, systematic and one-directional
SEVERITY  P3 Minor

---

## Claim 6 — the trading-day authority

**VERDICT: mostly PROVEN. The segment is right, the calendar is complete enough that the 4-day
staleness bound refuses zero legitimate 2026 sessions, and the guard fails closed on an absent
calendar and an uncovered year. Two real gaps: a partially-corrupt calendar fails **open**, and the
`sha256_of_payload` the file publishes is verified by nothing in the repository.**

### The right segment, and the staleness bound is right

`data/authorities/nse-trading-holidays.json` declares
`"authority": "NSE trading holidays, Capital Market (CM) segment"`, `"source_segment": "CM"`,
`"source_url": "https://www.nseindia.com/api/holiday-master?type=trading"`, 20 holidays, all 2026.
CM is the correct segment for NSE cash equities.

`scratchpad/probe_c6.py`:

```
=== 1. how many listed holidays are weekends anyway? ===
  4 of 20 listed holidays fall on a weekend: [('2026-02-15', 'Sun', 'Mahashivratri'),
  ('2026-03-21', 'Sat', 'Id-Ul-Fitr (Ramadan Eid)'), ('2026-08-15', 'Sat', 'Independence Day'),
  ('2026-11-08', 'Sun', 'Diwali Laxmi Pujan*')]
  effective weekday holidays in 2026: 16

=== 2. gap to the previous trading day, against MAX_BAR_STALENESS_DAYS = 4 ===
  trading days in 2026 whose previous session is more than 4 calendar days back: 0
```

Every 2026 trading day, derived from this calendar plus weekends, has its previous session within
four calendar days. **The bound refuses no legitimate session in the covered year**, and the
docstring's stated worst case ("a Friday session read on the Tuesday after a Monday holiday", gap 4)
is the actual maximum. The bound is correct, not merely plausible.

### Fail-closed, path by path

```
=== 4. fail-closed behaviour of require_trading_day on every path ===
  weekend                        -> refused: 2026-08-29 Saturday: NSE does not trade at weekends
  listed holiday 2026-08-15      -> refused: 2026-08-15 Saturday: NSE does not trade at weekends
  ordinary weekday 2026-08-31    -> RUNS
  year not covered 2027-01-04    -> refused: the trading-holiday authority covers ['2026'] and not 2027; ...
  year not covered 2025-08-28    -> refused: ... and not 2025; ...
```

Prior P1-6 (the inverted guard that ran a full session **on** the first holiday after a trading day
and refused the trading day after it) is closed: the question asked is now "does today trade", and
`tests/test_scheduled_paper_session.py:69` pins the day-after case. Prior P1-7 is closed by deletion
— `--skip-refresh` is gone (`grep -n "skip-refresh" scripts/*.py` returns nothing but the comment
recording its removal at `run_scheduled_paper_session.py:215-219`).

### But a partially-corrupt calendar fails OPEN

```
=== 5. corrupt-authority paths ===
  missing file                               2026-12-25 -> refused (NotATradingDay)
  not JSON                                   2026-12-25 -> JSONDecodeError: Expecting property name enclosed ...
  holidays key deleted, covers_years kept    2026-12-25 -> RUNS
  holidays emptied                           2026-12-25 -> RUNS
  one holiday silently removed               2026-12-25 -> RUNS
```

`document.get("holidays", [])` (`scripts/run_scheduled_paper_session.py:86`) defaults to the empty
list, so a file that keeps `covers_years` and loses or truncates `holidays` declares every weekday a
trading day. The module docstring says "An absent calendar, a malformed one, or a year it does not
cover all refuse" — the first and third are true, the second is only true for JSON that will not
parse at all, and it refuses by unhandled `JSONDecodeError` rather than by the typed refusal.

This is not academic. **No refresh script for this authority is committed** —
`grep -rln "holiday-master" --include=*.py --include=*.ps1 .` finds only the consumer. The file's own
error message tells a human to "refresh it from
https://www.nseindia.com/api/holiday-master?type=trading". That endpoint returns segments keyed by
name (`CM`, `FO`, ...), not a flat `holidays` array, so the most likely refresh — paste the API
response — produces a document with `covers_years` absent and `holidays` absent. The first case
refuses (good); a hand-edit that keeps `covers_years` and gets the holiday shape wrong runs a full
session on Diwali.

### The hash the file publishes is dead

```
=== 3. is the published sha256_of_payload verified anywhere? ===
  grep -rn sha256_of_payload over .py/.ps1: (no hits)
```

`sha256_of_payload` sits in the authority file and no code computes or compares it. The one field
that would catch every case in section 5 is inert — the same shape as the `skipped_extreme` field
this very commit repaired for being declared and never populated.

### Two smaller items

`covers_years` holds only `["2026"]`, so from 2027-01-01 the scheduled task refuses every day with
exit 2. That is the right direction, but there is no alarm for the absence of sessions: the task
simply stops producing output, and prior finding P2-10's "no alarm for absence of signal" is
unrepaired.

`newest_cached_bar_date()` (`:105-110`) is still a global `max` across every dataset in the store, so
a refresh in which 499 of 500 symbols failed still passes the staleness gate on the one that
succeeded. Prior P2-10's first half is also unrepaired.

FINDING   A calendar that keeps `covers_years` but loses or truncates `holidays` runs a full session on a real NSE holiday
FAMILY    Failure injection / security surface (integrity)
REPRO     `python scratchpad/probe_c6.py` section 5 — `holidays` key deleted, `require_trading_day(date(2026,12,25))` returns without raising
OBSERVED  `document.get("holidays", [])` defaults to empty; no shape validation; the published `sha256_of_payload` is verified by nothing
EXPECTED  A calendar that does not validate is refused, exactly as an absent one is
BLAST     A session traded on a closed market against stale quotes, advancing the portfolio and the rebalance clock. Silent — the log says "scheduled paper session for <date>" and proceeds
SEVERITY  P2 Major (escalated from Minor because the integrity field that exists to prevent it is never checked, and no committed script produces the file in the shape the guard expects)

FINDING   A malformed calendar refuses by unhandled `JSONDecodeError`, not by the documented typed refusal
FAMILY    Operability
REPRO     `python scratchpad/probe_c6.py` section 5, row "not JSON"
OBSERVED  `json.loads` at `:79` is outside any handler; `main()` catches only `NotATradingDay`
EXPECTED  A typed refusal with the same "refresh it from ..." guidance the other paths give
BLAST     An unattended operator sees a traceback instead of the reason. Fails closed, so no wrong trade
SEVERITY  P3 Minor

---

## Claim 7 — exits before entries

**VERDICT: nothing broke — and nothing changed. The swap is a measurable no-op, and the reason given
for it is false: submitting an exit does not release cash, because exits are *submitted*, not filled,
and fills happen in the next step's `process_quote`. The buys are still sized against pre-exit cash.
No harm results, but only because the risk governor's cash-buffer check refuses the premature buy —
a protection the comment does not mention and does not depend on.**

### The stated mechanism is false

`scripts/run_paper_pilot_session.py:998-1001`:

> "On a rebalance, enter the selection. Exits above run first, in the same step, so the proceeds are
> available to fund these buys"

`engine.submit_proposal` (`src/quant_system/execution/paper_pilot.py:290-...`) creates a PENDING
order and runs the pre-trade risk check. It does not fill. Fills happen in `process_quote`, which the
runner calls at `:920` — at the **top** of the step, before both loops. So an exit submitted in step
N first fills in step N+1.

`scratchpad/probe_c7.py`, real engine, one carried holding worth 950,000 and one new pick:

```
cash after carry            = 50000.00
step1 after process_quote   = 50000.00
step1 after EXIT submitted  = 50000.00   <-- the comment claims proceeds are now available
step1 entry sizing          : avail_cash=50000.00 target_alloc=47500.0000 qty=47
```

Cash is byte-identical before and after the exit submission. `avail_cash = engine.cash` at `:1009`
is still the pre-exit buffer, which is the exact condition the swap was supposed to remove.

### The swap changes no outcome — 20 configurations, identical

`scratchpad/probe_c7c.py` runs the runner's full per-step loop (process_quote for every symbol, then
one block, then the other) for 12 steps with the real `PaperPilotEngine`, `PreTradeRiskGovernor`,
`OrderBookSimConfig` and the real 5% `min_cash_buffer_pct`, over five book shapes x two universe
iteration orders x both block orderings:

```
  20 held -> 20 picks, exits early           exits-first   target=  47  at target  20/20  sizes={47: 20}  idle_cash=55832.20
  20 held -> 20 picks, exits early           ENTRIES-first target=  47  at target  20/20  sizes={47: 20}  idle_cash=55832.20
  20 held -> 10 picks, exits early           exits-first   target=  95  at target  10/10  sizes={95: 10}  idle_cash=45814.70
  20 held -> 10 picks, exits early           ENTRIES-first target=  95  at target  10/10  sizes={95: 10}  idle_cash=45814.70
  50 held -> 10 picks, exits early           exits-first   target=  95  at target  10/10  sizes={95: 10}  idle_cash=45787.50
  50 held -> 10 picks, exits early           ENTRIES-first target=  95  at target  10/10  sizes={95: 10}  idle_cash=45787.50
  20 held -> 5 picks, exits early            exits-first   target= 190  at target   5/5  sizes={190: 5}  idle_cash=45814.75
  20 held -> 5 picks, exits early            ENTRIES-first target= 190  at target   5/5  sizes={190: 5}  idle_cash=45814.75
  100 held -> 100 picks, exits early         exits-first   target=   9  at target 100/100  sizes={9: 100}  idle_cash=96009.00
  100 held -> 100 picks, exits early         ENTRIES-first target=   9  at target 100/100  sizes={9: 100}  idle_cash=96009.00
```

(the same ten lines again with the picks early in universe order — identical). **Every configuration
reaches the target size under both orderings**, and every number matches to the paisa.

The reason nothing goes wrong is not the one given. `target_alloc = min(per_name_alloc,
avail_cash * 0.95)` (`:1010`) sizes the premature buy at 95% of the buffer, which would leave cash
below the governor's `min_cash_buffer_pct = 0.05` — so `PreTradeRiskGovernor` refuses it, and the
entry loop re-proposes at full size on a later step once the exits have filled. Set the buffer to
zero and the undersized buy fills instead, after which `current_held == 0` is false and the position
is never topped up: `probe_c7.py` ends with `TARGET was 950 shares of NEW; ACTUAL is 47`, and
951,904.39 idle. The correct behaviour therefore rests entirely on a governor limit that no comment
connects to it.

### The 25-times-per-session loop: still non-idempotent, still self-recovering

The exit guard is `pos.quantity > 0` (`:976`) and the proposal id embeds `step` (`:977`), so a
partially filled SELL is re-proposed at full remaining size while the first order is still open.
`scratchpad/probe_c7d.py`, 1,000 shares against a thin book:

```
step 1: held= 1000 open_orders_before=0 proposed=[('OLD', 1000, True, 'SUBMITTED')] open_orders_after=1 open_sell_qty=1000
step 2: held=  640 open_orders_before=1 proposed=[('OLD', 640, True, 'SUBMITTED')] open_orders_after=2 open_sell_qty=1280   <-- OVERSELL COMMITTED
step 3: held=  280 open_orders_before=1 proposed=[('OLD', 280, True, 'SUBMITTED')] open_orders_after=2 open_sell_qty=560   <-- OVERSELL COMMITTED
step 4: held=    0 open_orders_before=0 proposed=[] open_orders_after=0 open_sell_qty=0
final OLD position = 0
total fills = 3, rejected orders = 0, cancelled = 2
```

Open sell quantity reaches 1,280 against a 640-share holding — twice. The engine cancels the excess,
so no short is created and the position closes correctly; the residue is two spurious cancelled
orders in the audit trail per partially filled exit. This is prior finding 5.3, unrepaired.

### Cross-block variables and ordering assumptions: clean

The exit block reads `engine.positions`, `top_picks`, `rebalancing`, `step`, `loop_now`,
`session_id`, `model`; the entry block reads `per_name_alloc`, `base_market`, `engine.cash`,
`engine.positions`. No name is defined in one and consumed by the other, and `engine.positions` is
unchanged by submitting proposals, so the swap cannot alter what either block sees. Ruff, mypy and
1157 tests are green.

FINDING   The exits-before-entries swap is a no-op and its stated justification is false
FAMILY    Assumption archaeology
REPRO     `python scratchpad/probe_c7.py` (cash unchanged after the exit is submitted); `python scratchpad/probe_c7c.py` (20 configurations, both orderings, identical results)
OBSERVED  `submit_proposal` does not fill; the comment at `:998-1001` asserts proceeds are available in the same step
EXPECTED  The comment describes what the code does, or the entry loop is deferred until the exits have filled
BLAST     A future reader relies on an ordering guarantee that does not exist; correctness actually depends on the governor's cash-buffer refusal, which is documented nowhere
SEVERITY  P2 Major (the repair does not do what it claims, and the real protection is undocumented and easy to remove)

FINDING   A partially filled exit is re-proposed at full remaining size while the first order is still open
FAMILY    Concurrency and ordering
REPRO     `python scratchpad/probe_c7d.py` — open sell quantity 1280 against a 640-share holding
OBSERVED  Committed sell quantity exceeds the position twice; the engine cancels the excess
EXPECTED  The guard consults open orders, not only filled quantity
BLAST     Two spurious cancelled orders per partially filled exit, in a loop that fires ~25 times a session. No short is created
SEVERITY  P2 Major (carried forward from the prior report's 5.3, unrepaired)

---

## Claim 8 — `peak_equity`

**VERDICT: PROVEN with a demonstration — the switch now trips. `peak_equity` is monotonic, persisted,
and a multi-session decline does reach 12% and fire. Three residuals, and one of them is serious: the
kill state itself is not persisted, so a tripped switch is forgotten by the next session.**

### It trips. Here it is tripping.

`scratchpad/probe_c8.py` runs the runner's real per-session sequence for twelve sessions —
`ledger_funding()` -> carry fills -> `start_session` -> `process_quote` -> exits/entries on a
rebalance -> `end_session` -> `state_from_ledger` — with the real `PreTradeRiskGovernor`, real
`PaperPilotEngine`, and the real 12% `max_total_drawdown_pct`. A steady 15%-over-ten-sessions
decline, with the session-10 rebalance rotating the name so an order is actually evaluated:

```
--- A2. same decline, but the rebalance ROTATES the name so orders are evaluated ---
  s     price   reb      funding      peak_in       equity dd_vs_peak  killed     peak_out
  0   1000.00  True   1000000.00   1000000.00    998820.14     0.12%   False   1000000.00
  ...
  9    865.00 False   1000000.00   1000000.00    870570.14    12.94%   False   1000000.00
 10    850.00  True   1000000.00   1000000.00    856320.14    14.37%    True   1000000.00
 11    850.00 False   1000000.00   1000000.00    856320.14    14.37%   False   1000000.00
```

`killed = True` at session 10. Prior finding P1-8 ("the switch resets every session, so a
multi-session decline cannot trip it") is closed: the peak held at 1,000,000 across nine hold
sessions instead of collapsing onto each session's own opening equity, and the eleventh session's
first order evaluation saw the full 14.37%.

### Residual 1 (P1) — the kill state is not persisted, so the halt lasts one session

Look at row 11 of the same table: `killed = False`. `PreTradeRiskGovernor.__init__`
(`src/quant_system/risk/governor.py:25`) sets `_is_killed = False`, and nothing restores it:
`PaperPortfolioState` has no kill field (`grep -n "kill" src/quant_system/execution/paper_portfolio.py`
returns one comment and no state), and the runner constructs a fresh governor every session
(`scripts/run_paper_pilot_session.py:782-785`). The governor's own `to_state`/`from_state`
serializer (`governor.py:100-160`) exists and carries `is_killed` — it is simply never called by this
path.

So a 14.37% total-drawdown breach halts trading for the remainder of **one** session and is silently
forgotten the next morning. Worse, in that same session the exits were refused (the kill fires on the
first order, and the first order is a SELL), so the book is not reduced — and `rebalanced=True` still
resets `sessions_held` to 1, so the losing book is locked in for another ten sessions with the
breach erased. The status file reports `kill_switch_active` from a governor that starts every day at
False.

### Residual 2 (P2) — the peak never records an unrealized gain

`update_peaks` is reachable only from `evaluate_order` (`governor.py:170`, called at
`paper_pilot.py:387` and `:544`). No order is proposed on a hold session, so nine sessions in ten
never touch the peak; the only thing that moves it is
`max(previous.peak_equity, ledger_funding())`, and `ledger_funding()` is a **cost** figure.

```
--- B. +25% during the hold, then -20% from that high ---
  s     price   reb      funding      peak_in       equity dd_vs_peak  killed     peak_out
  ...
 10      1250  True   1000000.00   1000000.00   1236320.14   -23.63%   False   1000000.00
 11   1000.00 False   1000000.00   1000000.00    998820.14     0.12%   False   1000000.00
```

True high-water mark 1,236,320.14; recorded peak 1,000,000.00. The book then gives back 19.2% from
its real high and the trailing-drawdown check reads **0.12%**. A "trailing max drawdown" measured
from cost basis is not a trailing max drawdown. The docstring at `paper_portfolio.py:112-119` says
the peak is "the highest total equity this portfolio has ever reached" — it is the highest *funded
cost* it has ever reached.

### Residual 3 (P2) — the switch is only evaluated when an order is proposed

Run A of the same probe is the same decline with the rebalance **retaining** the name, so no exit and
no entry is proposed:

```
 10    850.00  True   1000000.00   1000000.00    856320.14    14.37%   False   1000000.00
```

14.37% drawdown, rebalance session, `killed = False`. The drawdown is checked inside
`evaluate_order`, so a session that proposes nothing evaluates nothing. Nine sessions in ten propose
nothing by design, and a rebalance whose selection fully overlaps the book proposes nothing either.

FINDING   The kill switch is not persisted; a total-drawdown breach halts one session and is forgotten the next morning
FAMILY    State machine / failure injection
REPRO     `python scratchpad/probe_c8.py` run A2 — session 10 `killed=True`, session 11 `killed=False`, same 14.37% drawdown
OBSERVED  `PreTradeRiskGovernor.__init__` sets `_is_killed = False`; `PaperPortfolioState` carries no kill field; `governor.to_state`/`from_state` exist and are never called by this path. The breach also refuses the exits, so the losing book is retained, and `sessions_held` still resets to 1
EXPECTED  A tripped total-drawdown switch survives the session boundary, as `peak_equity` now does
BLAST     Every drawdown breach. The control that exists to stop a losing book stops it for a few hours and then resumes, silently
SEVERITY  **P1 Critical** — a risk control that does not hold; escalated because the reset is silent and the same session locks the book in for another ten sessions

FINDING   `peak_equity` records cost basis, not equity, so unrealized gains never enter the high-water mark
FAMILY    Money and counting / assumption archaeology
REPRO     `python scratchpad/probe_c8.py` run B — true peak 1,236,320.14, recorded peak 1,000,000.00, a 19.2% real drawdown reported as 0.12%
OBSERVED  `update_peaks` is reachable only from `evaluate_order`; hold sessions propose no orders; the fallback seed is `ledger_funding()`, a cost figure
EXPECTED  The peak tracks marked equity on every session
BLAST     Every profitable holding period. The trailing-drawdown control is systematically too permissive, in exactly the state where a drawdown matters most
SEVERITY  P2 Major (escalated: silent, and it defeats the repair's stated purpose in the one direction the repair does not test)

FINDING   The drawdown switch is evaluated only when an order is proposed
FAMILY    State machine
REPRO     `python scratchpad/probe_c8.py` run A — session 10, rebalance, 14.37% drawdown, `killed=False` because the selection retained the book
EXPECTED  The drawdown is evaluated at least once per session against the closing mark
BLAST     Nine sessions in ten by design, plus any rebalance whose selection overlaps the book
SEVERITY  P2 Major

---

## Claim 9 — the RESEARCH_PAPER exemption

**VERDICT: the exemption itself is genuinely narrow — I could not execute a `REJECT` model on any
surface, and I could not use the exemption as a skeleton key. The *chokepoint* claim is weaker than
stated: the AST detector is defeated by five one-line rewrites, it scans 1 of 33 scripts and nothing
under `src/`, and the server serves Mizan inference from a model that never passes
`require_surface_admits` and can be replaced over HTTP with a `REJECT` one.**

### The gate holds

`scratchpad/probe_c9.py`:

```
=== 1. the verdict matrix ===
  SHADOW          admits ['PAPER', 'PAPER_PILOT', 'SHADOW']
  PAPER_PILOT     admits ['PAPER', 'PAPER_PILOT']
  PAPER           admits ['PAPER']
  RESEARCH_PAPER  admits ['RESEARCH_ONLY']
  verdicts admitted nowhere : ['REJECT']

=== 2. can a REJECT model execute anywhere? ===
  SHADOW: refused ...   PAPER_PILOT: refused ...   PAPER: refused ...   RESEARCH_PAPER: refused ...

=== 4. an unrecognised verdict string ===
  PromotionState('TOTALLY_MADE_UP') -> ValueError: 'TOTALLY_MADE_UP' is not a valid PromotionState
```

`REJECT` is admitted by no surface, including under the exemption; an unknown verdict raises rather
than defaulting; the exemption is refused on the three promotion surfaces and required on
`RESEARCH_PAPER`; a *promotable* model is refused on `RESEARCH_PAPER` too. The design is
self-consistent and I could not break it from the inside.

The exemption is a **declaration, not a credential** — anyone can construct
`ResearchPaperExemptionV1(RESEARCH_PAPER_DECISION_RECORD, "x", "y")` and it is accepted. That is
explicitly the intent, so it is not a finding, but the guarantee is auditability, not authorisation.

### The AST detector: defeated five ways, one line each

`tests/test_research_paper_exemption.py:191-219` skips any file lacking `save_portfolio` or
`PaperPilotEngine`, then collects `ast.Call` nodes whose `func` is an `ast.Attribute` named
`default_model` or `sprint_50k_model`. Replicating that logic exactly against synthetic sources:

```
=== 5. defeating the AST detector (exact logic from tests/test_research_paper_exemption.py) ===
  the defect it was written to catch     -> CAUGHT ['default_model']
  bound to a local name first            -> NOT CAUGHT
  via getattr                            -> NOT CAUGHT
  imported as a free function            -> NOT CAUGHT
  from_pretrained (not in the set)       -> NOT CAUGHT
  from_dict (not in the set)             -> NOT CAUGHT
  no save_portfolio/PaperPilotEngine     -> NOT CAUGHT
```

`f = MizanModel.default_model` then `f()` suffices: the call func is a `Name`, not an `Attribute`.
`MizanModel.from_pretrained(...)` and `MizanModel.from_dict(...)`
(`src/quant_system/modeling/mizan_model.py:431,494`) are public constructors returning a model with
whatever verdict the artifact carries, and are not in the watched set at all.

```
=== 6. scope of the detector ===
  scripts/*.py total 33, scanned by the detector: 1 -> ['run_paper_pilot_session.py']
  src/**/*.py calling default_model(): [execution/mizan_execution.py, modeling/mizan_cli.py,
    server/app.py, strategies/mizan_strategy.py]
```

The detector inspects **one file**. The test docstring says it is "a detector for the known surface,
not for the class", which is honest — but the commit message's "narrowed by a test that parses every
script which persists portfolio state" reads broader than one script and one call shape.
`strategies/mizan_strategy.py:72` calls `default_model()` and is protected by a different mechanism
entirely: `research_only = True` at `:47`, the `85ff535` declaration guard.

### The server reaches a Mizan surface without the verdict check, and accepts a REJECT model

`src/quant_system/server/app.py:588` binds a process-global
`_ACTIVE_MIZAN_MODEL = MizanModel.default_model()` outside the chokepoint, and `:648-665` hot-swaps
it from an arbitrary JSON body with no verdict check, no signature and no auth dependency
(`grep -n "Depends(|require_auth|api_key|Authorization" src/quant_system/server/app.py` returns
nothing). `scratchpad/probe_c9b.py`, real FastAPI app through `TestClient`:

```
csrf token obtained with an unauthenticated GET: G09H6ev302aepNmA...
BEFORE: {'model_id': 'mizan-v1', 'verdict': 'RESEARCH_ONLY', 'weights_hash': '7598699d...'}
UPLOAD: 200 {"status": "SUCCESS", "model_id": "attacker-model-001", "version": "1.0.0"}
AFTER : {'model_id': 'attacker-model-001', 'verdict': 'REJECT', 'weights_hash': '096fbee0...'}
PREDICT from the REJECT model: 200 {"model_id": "attacker-model-001",
  "candidate_id": "cand_mizan_v1", "score": 1.0217703989950435}
```

A `REJECT`-verdict model with every coefficient sign-flipped now answers
`/api/models/mizan/predict` for every subsequent caller in that process. The CSRF check is satisfied
by an unauthenticated GET to `/api/v1/csrf-token`, so it stops cross-site posting and nothing else.

This is advisory output, not order routing, so no order is placed — but it is a surface reached
without `require_surface_admits`, and "REJECT remains executable nowhere" is true of execution and
false of the inference endpoint that the same commit's docstring calls a legitimate ungated reader.
It is also process-global mutable state: one caller's upload changes every other caller's answer.

FINDING   The AST detector is defeated by binding the constructor to a name, by `getattr`, and by `from_pretrained`/`from_dict`; it scans 1 of 33 scripts and nothing under `src/`
FAMILY    Assumption archaeology / security surface
REPRO     `python scratchpad/probe_c9.py` sections 5 and 6 — six of seven variants NOT CAUGHT
OBSERVED  Only `ast.Attribute` calls named `default_model`/`sprint_50k_model`, only in `scripts/*.py`, only in files mentioning `save_portfolio` or `PaperPilotEngine`
EXPECTED  The stated residual scoped to what the detector actually covers, or a detector that follows the constructor rather than its spelling
BLAST     Any future execution path. The residual is disclosed; its size is not
SEVERITY  P2 Major

FINDING   `POST /api/models/mizan/upload` replaces the process-global active model with an arbitrary one, verdict unchecked and unauthenticated; `/predict` then serves it
FAMILY    Identity and authorization / security surface
REPRO     `python scratchpad/probe_c9b.py` — CSRF token from an unauthenticated GET, upload a REJECT card with inverted coefficients, `/predict` answers 200 from it
OBSERVED  `app.py:588` acquires the model outside `load_mizan_for_execution`; `:652-655` hot-swaps it with no verdict check, no signature, no auth
EXPECTED  Server-side model acquisition passes the same chokepoint, or the endpoint is scoped and authenticated
BLAST     Every consumer of the server's Mizan inference in that process, until restart. Advisory only — no order is placed
SEVERITY  P2 Major (pre-existing, not introduced by these commits; it contradicts the chokepoint claim at `execution/mizan_execution.py:9-11`)

---

## Claim 10 — the rank-sort repair and its self-correction

**VERDICT: the retraction is CORRECT — I confirmed the 244 rows are unrecoverable from the store,
by float hex. But `tests/test_mizan_store_fidelity.py` cannot detect a revert of the repair it
accompanies: the current kernel, the current kernel with `raw_values` withheld, and the verbatim
pre-repair implementation from `c5593cae` all pass it identically. The comment claiming otherwise is
false.**

### The retraction is correct

`scratchpad/probe_c10.py`, against the real committed store:

```
  BAJAJHIND return_5 text = '-0.0365853659'
  NIFTYBEES return_5 text = '-0.0365853659'
  texts equal  = True
  floats equal = True
  float.hex    = -0x1.2bb512c1afaa8p-5 vs -0x1.2bb512c1afaa8p-5
  published ranks differ: ['-0.0576923077', '-0.0600961538']
```

Bit-identical IEEE-754 doubles, two different published ranks. No ranking rule that reads only the
store can order these two names, because the ordering was decided by pre-quantisation floats that
were never published. **There is no way to recover the builder's order**, and the author's
withdrawal of the "244 rows are now reproducible" claim is right.

The full sweep confirms the count is unchanged by the repair — the fix improves the live path, not
the store:

```
dates=2427  rows=1,015,831  elapsed=9s
cs_rank_momentum_5   mismatching rows: 244 (0.0240%) on 115 dates
cs_rank_volume_surprise mismatching rows: 0 (0.0000%) on 0 dates
```

### The test cannot fail on the defect it names

`tests/test_mizan_store_fidelity.py:38-40` states: "Two of these are dates the Red Team sweep
reported as carrying mismatches under the old sort, **so a revert fails here**."

It does not. The test builds `raw_values` from the store's own text
(`raw_values = {... float(row[name]) ...}`, `:105`), so `raw_values[s][source]` is *by construction*
identical to the `float(cross_section[s][source])` the pre-repair code sorted on. The two code paths
are the same computation on the same numbers.

Running the test's exact body three ways:

```
=== can tests/test_mizan_store_fidelity.py detect a revert of the fix? ===
  current kernel WITH raw_values (what the test calls) unexplained=  0 tied_divergences= 14  -> TEST PASSES
  current kernel WITHOUT raw_values                    unexplained=  0 tied_divergences= 14  -> TEST PASSES
  PRE-REPAIR implementation (c5593cae)                 unexplained=  0 tied_divergences= 14  -> TEST PASSES
```

Identical on all three counters. Deleting the `raw_values` parameter and restoring
`c5593cae:mizan_features.py:203-223` verbatim leaves the suite green. The test is a regression guard
for the *rule*, not for the repair.

### What it does catch

```
=== what mutations DOES the fidelity test catch? ===
  sort reversed          unexplained=5801 tied=  31 -> TEST FAILS (caught)
  rank offset by one     unexplained=5813 tied=  24 -> TEST FAILS (caught)
  tie-break reversed     unexplained=   0 tied=  19 -> TEST PASSES (missed)
```

So it is a real test — it is not vacuous, and it fails loudly on a drifted ranking rule. It is blind
to the whole tie-breaking dimension, which is precisely the dimension the repair changed.

The test's own module docstring is otherwise scrupulous: it states the divergence is permanent,
states what it does not prove (the thirteen instrument-level features, the libm exposure), and the
`tied_divergences > 0` assertion protects against the sampled dates silently losing the case. One
sentence out of that whole file is wrong, and it is the sentence claiming the repair is protected.

FINDING   `test_mizan_store_fidelity.py` cannot detect a revert of the rank-sort repair, contrary to its own comment
FAMILY    Assumption archaeology / operability
REPRO     `python scratchpad/probe_c10.py` — the current kernel, the kernel without `raw_values`, and the verbatim pre-repair implementation all give `unexplained=0 tied=14`
OBSERVED  The test constructs `raw_values` from the store's own text, so the new sort key equals the old one by construction
EXPECTED  The comment removed, or a test that supplies raw floats which differ from the published text (which requires the original bars, not the store)
BLAST     A future revert of the raw-float sort ships silently; the live path quietly returns to the builder-divergent ordering
SEVERITY  P2 Major (escalated from Minor: the test is cited as the protection for the repair, and it is not)

---

## Claim 11 — the 264 restored evidence files

**VERDICT: the restore is PROVEN complete and byte-exact — 0 of 16,677 tracked evidence files differ
from their committed blob, verified independently by blob SHA-1 rather than by the repository's own
test. Nothing was lost. But the new guard is defeated by any corruption that preserves the
line-ending category, and its assertion message claims byte equality it does not measure.**

### Verified independently: 0 of 16,677 differ

`scratchpad/probe_c11.py` hashes every tracked working-tree file with `git hash-object
--stdin-paths` and compares against the index's blob oid — the committed content, unfiltered by any
attribute:

```
tracked files under data/evidence: 16,677
index entries: 16,677   elapsed 0s
hashed 16,677 working-tree files in 3s

files whose working-tree bytes differ from the committed blob: 0

tracked evidence files containing CRLF on disk: 1289
```

The 1,289 CRLF hits are `\r\n` occurring naturally inside gzip payloads — every one of them matches
its blob exactly, so they are compressed bytes and not corruption.

The five macro inputs the live feature path reads all parse and carry the expected candle counts:

```
macro-regimes-20160822-20260821/macro_INDIAVIX.json    bytes=  289,052 CRLF=0 candles=2478
macro-regimes-20160822-20260821/macro_NIFTY50.json     bytes=  314,017 CRLF=0 candles=2479
macro-regimes-20160822-20260821/macro_NIFTYBANK.json   bytes=  315,193 CRLF=0 candles=2479
macro-regimes-20160822-20260821/macro_NIFTYIT.json     bytes=  315,047 CRLF=0 candles=2479
macro-refresh-20230828-20260827/macro_INDIAVIX.json    bytes=   87,077 CRLF=0 candles=745
```

Prior P2-8 is closed. The whole check runs in four seconds, which matters below.

### The new guard detects line endings, not bytes

`tests/test_committed_evidence_integrity.py:78-121` runs `git ls-files --eol data/evidence/` and
compares the `i/` and `w/` **categories**. Its failure message says "N tracked evidence file(s) hold
different bytes on disk than the repository committed". It does not measure bytes.

Sandbox with the repository's own configuration (`core.autocrlf=true`,
`data/evidence/** -text`), in `scratchpad/eolsbx/`, never touching the real store:

```
--- ATTACK 1: change payload content, keep LF ---
  i/lf    w/lf    attr/-text            data/evidence/store/payload.jsonl
  blob sha: 0c2aa38e0600e0d2df09c2f84664d8a14f899879  disk sha: ce605adb69811dd5089601e2bdbec1f5f389e34a

--- ATTACK 2: change a no-newline file (i/none w/none) ---
  i/none  w/none  attr/-text            data/evidence/store/nonewline.txt
  blob sha: 248b2753a3dcf6b573b8ebe0703e14a37b5951d3  disk sha: 18d500ecdc81551626754dc4aec43c46e3d950e4

--- ATTACK 3: truncate a binary blob ---
  i/-text w/-text attr/-text            data/evidence/store/blob.bin
  blob sha: 4064f73de3cb2e33d2348094d79df77eb94731f4  disk sha: cd925438fa6db609ab6b4ff39d984040ceabbdd8

--- ATTACK 4: delete a tracked evidence file entirely ---
  i/lf    w/      attr/-text            data/evidence/store/COMMITTED

--- what the repaired test would report (i/ vs w/ mismatch count) ---
  mismatched: 1
```

Three of four tampering modes are invisible. Only the deletion is caught, and only because a missing
file makes `w/` empty. On the real repository 3,409 evidence files sit at `i/none w/none` and 4,335
at `i/-text w/-text` — **7,744 of 16,677 (46%) are in categories where no content change of any kind
can produce a mismatch.**

```
$ git ls-files --eol data/evidence/ | awk '{print $1, $2, $3}' | sort | uniq -c | sort -rn
   8933 i/lf w/lf attr/-text
   4335 i/-text w/-text attr/-text
   3409 i/none w/none attr/-text
```

The guard does cover the threat it was written for — an autocrlf checkout always changes the
category — so this is a scope overstatement rather than a hole in the specific defence. But it is
*the same overstatement being corrected*: the previous version of this file claimed "repository-wide
coverage" for a marker-only check, and the replacement claims byte equality for a category-only
check. And the correct check is not expensive: the four-second blob comparison above is a whole test
suite's budget for the strongest possible statement.

FINDING   The evidence guard compares line-ending categories, not bytes, while asserting "different bytes on disk"; 46% of tracked evidence files are in categories where no content change can trip it
FAMILY    Data integrity / assumption archaeology
REPRO     `scratchpad/eolsbx` sandbox — three content tamperings give `i/lf w/lf` with differing blob SHAs; `git ls-files --eol data/evidence/ | sort | uniq -c` gives 7,744 of 16,677 in `none`/`-text` categories
OBSERVED  The assertion text and docstring claim byte-level committed-blob equality; the implementation compares `i/` and `w/` labels
EXPECTED  Compare `git hash-object` against the index oid, which takes 4 seconds for all 16,677 files, or scope the claim to line endings
BLAST     Every future silent corruption of the evidence store that is not a line-ending change. `daily_auto_sync.ps1` runs `git add -A`, so such a change is committed on the next sync
SEVERITY  P2 Major (escalated: silent, it is the only committed protection for 16,677 evidence artifacts, and it repeats the exact overstatement it was written to correct)

---

## Claim 12 — anything overstated, missed, or broken while repairing

**VERDICT: CONFIRMED, and this is the largest section. Two new P1s were introduced or exposed by the
repairs, three claims in the commit messages are false, and the reason none of it is caught is
structural: no test in the suite reaches `PaperPilotEngine.end_session` with a carried position.**

The two new P1s are written up under the claims they belong to and are only indexed here:

- **Every carried session fails reconciliation and now exits 7** (Claim 1). Introduced by the
  interaction of `b3e626b5`'s carry replay with `bb62bc58`'s honest exit code.
- **The total-drawdown kill switch is not persisted** (Claim 8). Exposed by making the switch
  trippable for the first time: the halt now happens, and is forgotten the next morning.

### 12.1 Three commit-message claims that are false

| Claim | Where | Status |
|---|---|---|
| "Exits are proposed before entries in the same step, so proceeds fund the entries" | `bb62bc58`, work record row 5.4, `run_paper_pilot_session.py:998-1001` | **False.** Submitting an exit does not move cash; 20 configurations give identical results under both orderings (Claim 7) |
| "P2-6 ... repaired" | `bb62bc58` | **Half.** The threshold is gone; the count still takes the ceiling where the screen truncates, on 79% of population sizes (Claim 4) |
| "Sizing ... comes from `portfolio.ledger_funding()`" fixes the concentration defect | `bb62bc58`, `run_paper_pilot_session.py:757-765` | **A no-op under an unrealized loss.** Cost basis equals the old `initial_cash` constant until the loss is realized (Claim 5) |

### 12.2 Comments that were true before the repair and are false after it

`scripts/run_paper_pilot_session.py:1186-1187`:

> "Fees counted are today's real fills only - the carry-forward replay is **zero-fee** and must not
> be added again."

The replay is no longer zero-fee — that is the whole of the P1-2 repair, made in the same commit.
The filter the comment justifies (`if not f.fill_id.startswith("carry_")`) is also a dead no-op:
carry fills go through `engine.ledger.process_fill` and never enter `engine.fills`, which
`scratchpad/probe_c1b.py` shows directly (`engine.fills after replay = 0`). The resulting
`total_fees` figure is correct; the guard protecting it guards nothing and its stated reason is now
untrue.

`scripts/run_paper_pilot_session.py:684-687`:

> "The coverage gate runs *after* the extreme-row refusals below, not before. Checking first measured
> a cross-section the session was not going to use: refusals shrink it further, and a rank divides by
> the number of names present, so the gate would have **passed on a population that no longer existed
> by the time anything was ranked**."

Nothing is ranked after the refusal. `load_mizan_cross_section` (`:404`) ->
`build_live_cross_section` -> `compute_mizan_cross_section` -> `apply_cross_sectional_ranks` fills
both rank features **before** `refuse_extreme_rows` runs at `:688`. Moving the coverage gate is a
real improvement to the *fraction*, and the reason given for it describes an ordering the code does
not have. The consequence the comment worries about is real and unaddressed in the other direction:
the surviving rows keep ranks computed over the pre-refusal population while `select_top_fraction`
takes 20% of the post-refusal population — a mixed basis that nothing reconciles.

### 12.3 One lagging symbol aborts the whole session, bypassing the coverage tolerance

`MIN_CROSS_SECTION_COVERAGE = 0.90` exists to tolerate up to 10% of the universe being unavailable.
`_require_one_decision_date` (`src/quant_system/execution/mizan_live_features.py:197-214`) runs
first and tolerates zero. `scratchpad/probe_c12b.py`, real `build_live_cross_section`:

```
all 50 symbols current: scored=50 coverage=100.0%
one lagging symbol of 50 -> MizanLiveFeatureError: cross-section spans 2 decision dates;
  1 symbol(s) do not end at 2026-08-28 (e.g. S007 at 2026-08-27). ...
  -> the whole session aborts; nothing scores, nothing trades, the portfolio does not advance
```

This composes badly with prior P2-10, which is still open: `newest_cached_bar_date()`
(`scripts/run_scheduled_paper_session.py:105-110`) is a **global max** across every dataset, so a
refresh in which 499 of 500 symbols failed still passes the staleness gate on the one that
succeeded. The scheduled run then clears every guard and the session dies at `:683` with exit 2. It
fails closed, and on a 500-name universe a single stale name is an ordinary event, so a rebalance can
be deferred repeatedly with no signal that the cause is one symbol.

### 12.4 The structural reason none of this is caught

Every one of the 29 tests in `tests/test_paper_portfolio.py` drives `DecimalLedger` directly.
`grep -rn "carry_forward_fills" tests/` returns ten hits, all in that file, none of them
constructing a `PaperPilotEngine`. **No test in the 1157 ever calls `end_session` with a carried
position**, which is exactly the state every session after the first will be in, and exactly where
the reconciliation P1 lives.

The same shape shows in the test that backs the `peak_equity` repair.
`test_the_peak_round_trips_so_a_multi_session_decline_can_trip_the_switch`
(`tests/test_paper_portfolio.py:449-454`) is three lines: save, load, assert the value survived. It
constructs no `PreTradeRiskGovernor` and no decline; its name asserts a behaviour it does not
exercise. The switch does in fact trip (Claim 8) — but that had to be demonstrated here, not by the
suite, and the suite would be equally green if it did not.

Gates run at `c45ee6f8`:

```
$ .venv/Scripts/python.exe -m pytest -q      -> 1157 passed, 1 warning in 75.07s
$ .venv/Scripts/python.exe -m ruff check .   -> All checks passed!
$ .venv/Scripts/python.exe -m mypy src       -> Success: no issues found in 141 source files
```

Both new P1s in this report are invisible to all three, as were all eight in the previous report.

### 12.5 Smaller items

**The cash buffer is breached on a full deployment.** `per_name_alloc` is `0.95 * funding / N` and
does not budget the ~0.11% entry fee, so the fee comes out of the 5% buffer.
`scratchpad/probe_c12.py`, first rebalance from a fresh 1,000,000 portfolio:

```
  100 picks @  475.00 (alloc/price EXACT: 20 sh) alloc=9500.00 target_qty=  20 at_target= 100/100 unfunded=  0 risk_refusals=   0 idle_cash=48767.00
```

48,767.00 against an equity of 998,767.00 is **4.883%**, under the declared 5.0% minimum. The
proposals all pass the governor because they are submitted before any of them fills, so each is
checked against the full pre-fill cash.

**Two different "initial capital" figures in one report.** `run_paper_pilot_session.py:1217` computes
`return_pct = total_net_pnl / initial_cash`, where `initial_cash` is the CLI nominal
(default 1,000,000) and never the portfolio. The markdown two lines later prints
`| Initial Capital | Rs {reconciliation.initial_cash} |` — which is `ledger_funding()`, i.e. cash
plus cost basis plus carried entry fees. Neither is the portfolio's marked equity, and the percentage
is computed against one while the table displays the other.

**A liquidation refusal logs 25 times.** The empty-selection guard's `logger.error` sits inside the
trading loop (`:969-974`), which runs once per 15-minute step, so a single refusal produces roughly
25 identical ERROR lines per session.

FINDING   Comments justifying two repairs describe behaviour the code does not have (zero-fee replay; ranking after refusal)
FAMILY    Assumption archaeology / operability
REPRO     `scripts/run_paper_pilot_session.py:1186-1187` against `:809-811`; `:684-687` against `:404-470` and `modeling/mizan_features.py:302`
OBSERVED  The replay charges fees as of this same commit; ranks are filled before `refuse_extreme_rows` runs
EXPECTED  The comment matches the code, or the code matches the comment
BLAST     Every future reader. The `total_fees` filter is a dead no-op; the mixed rank/selection basis is undocumented
SEVERITY  P3 Minor

FINDING   One symbol whose bars end a session early aborts the entire cross-section, bypassing the 90% coverage tolerance
FAMILY    Failure injection / scale
REPRO     `python scratchpad/probe_c12b.py` — 49 current symbols plus one a day behind raises `MizanLiveFeatureError`
OBSERVED  `_require_one_decision_date` runs before coverage is computed and tolerates zero stale names; the scheduled run's staleness guard is a global max and does not catch the cause
EXPECTED  A stale symbol is dropped and counted against coverage, like a symbol with no bars
BLAST     A 500-name universe. The rebalance is deferred with no signal identifying the one responsible symbol. Fails closed
SEVERITY  P2 Major

FINDING   No test reaches `end_session` with a carried position, and the `peak_equity` test asserts a value round-trip under a name claiming the switch can trip
FAMILY    Assumption archaeology / operability
REPRO     `grep -rn "carry_forward_fills" tests/` — ten hits, all `DecimalLedger`, none `PaperPilotEngine`. Read `tests/test_paper_portfolio.py:449-454`
OBSERVED  1157 tests, ruff and mypy all green with both new P1s present
EXPECTED  One end-to-end session test that carries a position through `PaperPilotEngine` and asserts the reconciliation
BLAST     The whole live paper path. This is why eight P1s survived the last gate run and two survive this one
SEVERITY  P2 Major

FINDING   `per_name_alloc` does not budget the entry fee, so a full deployment lands under the declared 5% cash buffer
FAMILY    Money and counting
REPRO     `python scratchpad/probe_c12.py` — 100 picks at 475.00 leaves 48,767.00 against 998,767.00 equity, 4.883%
OBSERVED  All proposals pass the governor because they are evaluated before any of them fills
EXPECTED  The allocation budgets the round-trip entry cost, or the buffer is checked against committed orders
BLAST     Every full deployment. Magnitude ~12 basis points of a declared risk limit
SEVERITY  P3 Minor

FINDING   `return_pct` is computed against the CLI nominal while the same report prints `ledger_funding()` as "Initial Capital"
FAMILY    Operability / money and counting
REPRO     `scripts/run_paper_pilot_session.py:1217` against `:1338`
OBSERVED  Two different bases in one table; neither is the portfolio's marked equity
EXPECTED  One base, named, and it is the portfolio's equity at session open
BLAST     Every session report, increasingly wrong as the persisted portfolio diverges from 1,000,000
SEVERITY  P3 Minor

---

## Coverage

**Twelve failure families walked**, all twelve claims reached, none left `NOT TESTED`.

| Family | Where it produced a finding |
|---|---|
| 1 Input boundaries | `rebalance_due` horizons 0/1/2/-5; `select_top_fraction` n=1..501, fraction 0.001; empty scores |
| 2 Identity, authorization, tenancy | The unauthenticated model upload swapping process-global state for every caller (Claim 9) |
| 3 Concurrency and ordering | Same-day re-run shortens the hold (2); partially filled exit re-proposed (7); submission order vs fill order (7) |
| 4 Failure injection | Missing / malformed / truncated holiday authority (6); tampered and deleted evidence files (11) |
| 5 State machine | Kill state lost at the session boundary (8); `rebalanced` as intent not outcome (3); state saved before the reconciliation gate (1) |
| 6 Scale | 16,677 evidence files hashed; 1,015,831 published rows swept; a 500-name universe against one lagging symbol (12) |
| 7 Money and counting | Cross-session P&L, FIFO collapse, quantization, cumulative accumulation, sizing base, cash buffer |
| 8 Data integrity | Blob-level byte equality; the category-only guard; `sha256_of_payload` verified by nothing |
| 9 Security surface | REJECT model uploaded and served; CSRF obtainable unauthenticated; AST detector evasion |
| 10 The human path | Retry after an exit-7 session shortens the hold (2) |
| 11 Operability | Exit 7 daily on a healthy session (1); 25 duplicate ERROR lines; two "initial capital" figures |
| 12 Assumption archaeology | Three false commit claims; two comments describing behaviour the code lacks; a test that cannot fail |

**Probes written and executed** (all under the session scratchpad, none in the repository):
`probe_c1.py`, `probe_c1b.py`, `probe_c2.py`, `probe_c3.py`, `probe_c4.py`, `probe_c5.py`,
`probe_c6.py`, `probe_c7.py`, `probe_c7b.py`, `probe_c7c.py`, `probe_c7d.py`, `probe_c8.py`,
`probe_c9.py`, `probe_c9b.py`, `probe_c10.py`, `probe_c11.py`, `probe_c12.py`, `probe_c12b.py`,
`probe_nan.py`, plus the `eolsbx/` throwaway git repository and re-runs of the prior pass's
`probe_claim2.py` and `probe_claim2_ranks_full.py`.

**Real components driven, not mocked**: `DecimalLedger`, `PaperPilotEngine`, `PreTradeRiskGovernor`,
`OrderBookSnapshot`, `PaperPortfolioState`/`state_from_ledger`/`save_portfolio`/`load_portfolio`,
`MizanModel.default_model()`, `load_mizan_for_execution`, `require_surface_admits`,
`build_live_cross_section`, `refuse_extreme_rows`, `select_top_fraction`,
`apply_cross_sectional_ranks`, `require_trading_day`, and the FastAPI app through `TestClient`.

**Real data touched**: 1,015,831 published Mizan rows swept twice; three real acquisitions and the
real macro series from the committed caches; the real model card, weights and preprocessor;
`data/authorities/nse-trading-holidays.json`; 16,677 tracked evidence files hashed against their
committed blobs. Nothing under `data/evidence/` was modified — verified after the run
(`git status --short` clean apart from this report and the work record).

**Gates run at `c45ee6f8`**: `pytest -q` 1157 passed in 75.07s; `ruff check .` clean;
`mypy src` clean on 141 files.

**Targets read**: `execution/paper_portfolio.py`, `execution/paper_pilot.py`,
`execution/mizan_live_features.py`, `execution/mizan_execution.py`,
`execution/governed_strategy.py`, `modeling/mizan_features.py`, `modeling/mizan_model.py`,
`core/ledger.py`, `core/domain.py`, `risk/governor.py`, `server/app.py`,
`strategies/mizan_strategy.py`, `scripts/run_paper_pilot_session.py`,
`scripts/run_scheduled_paper_session.py`, `scripts/screen_mizan_out_of_sample.py`,
`tests/test_paper_portfolio.py`, `tests/test_scheduled_paper_session.py`,
`tests/test_research_paper_exemption.py`, `tests/test_mizan_store_fidelity.py`,
`tests/test_committed_evidence_integrity.py`, `.gitattributes`, and the three commit messages and
work records in scope.

## NOT PROBED

The most important section. Everything below is an unknown that this pass converted into a known
unknown rather than closed.

**1. No session was ever run end to end.** `run_paper_session()` was never executed. There is no
Upstox token in this environment, the market is closed, and the brief forbids re-enabling the
schedule. Every finding about the runner comes from driving its real components in the runner's own
order, or from reading the control flow. Consequences:

- The P1 reconciliation failure is proven at the `PaperPilotEngine` level and traced to `:811` and
  `:791-801`, but **no one has watched `run_paper_pilot_session.py` print
  `[PAPER PILOT RECONCILIATION FAILED]` and return 7**. The inference is short and I believe it, but
  it is an inference.
- The 15-minute loop was replayed with synthetic order books at flat prices. Real slippage, real
  depth, partial fills at realistic sizes, and the real `fetch_upstox_live_quotes` path are untested
  here.
- `logs/paper_runs/portfolio_state.json` does not exist, so no real persisted state was read. The
  claim that no v1 file was ever produced is consistent with the filesystem but rests on that.

**2. The holiday calendar's completeness was checked structurally, not against the source.** I
verified the segment label, the year coverage, weekday/weekend composition, and that no 2026 trading
day derived from it has a previous session more than four calendar days back. I did **not** fetch
`https://www.nseindia.com/api/holiday-master?type=trading` and diff the twenty entries against it —
there is no network access here. A holiday genuinely missing from the file would show as an ordinary
weekday to both the guard and my probe. The `sha256_of_payload` field is verified by nothing, so
there is no offline check either.

**3. Multi-instance and true concurrency.** I demonstrated that a sequential re-run of one calendar
day double-advances the clock. I did **not** run two sessions simultaneously. `save_portfolio` uses
a `.staging` file plus `replace`, which is atomic per write but has no lock: two concurrent sessions
would each read the same prior state and the last writer would win, losing one session's trades
entirely. Untested, and it is the natural failure mode of a scheduled task that overruns.

**4. Cross-architecture float reproducibility.** The prior report flagged `math.log`/`math.sqrt` as
libm calls. Everything here ran on the same Windows ARM64 machine as the published store. CI runs on
x86-64. A 1-ULP difference at a 10-decimal rounding boundary would move a rank and is not measurable
from this machine.

**5. `preprocessing_input_hash` (prior P2-1) was not re-probed.** It is recorded as deliberately left
open in `c45ee6f8`, and I accepted that scoping rather than re-deriving the prior pass's result.

**6. The prior report's Claims 1, 2 and 6 were re-verified only in part.** I re-ran the kernel
fidelity probe (48 rows, three symbols) to confirm the `compute_mizan_feature_floats` refactor is
value-preserving, and the full 1,015,831-row rank sweep. I did **not** re-derive the 400-bar window
arithmetic, the `MAX_STANDARDIZED_DEVIATION` percentile figures, or the 511/411 counts now written
into `mizan_live_features.py:217-237`; those docstring corrections are taken from the prior report
rather than independently re-measured.

**7. NaN and non-finite feature values.** `refuse_extreme_rows` is not NaN-safe —
`max(0.0, float('nan'))` returns `0.0`, so a NaN feature passes the guard, produces a NaN score, and
enters a sort whose comparator is then not a total order (`scratchpad/probe_nan.py` demonstrates all
three). I could **not** construct a real bar sequence that produces a NaN: the kernel guards every
division and takes `math.log` only of a strictly positive ratio. **Reported here rather than as a
finding, because I have no reproduction from real input.**

**8. The `_BAR_CACHES` early-exit at `run_paper_pilot_session.py:424`.** It stops consulting further
caches once 90% coverage is reached, so up to 10% of the universe can be dropped while the fallback
store holds those names — and a cross-sectional rank divides by the number of names present. I read
the mechanism but did not measure how many names it actually drops, because that needs the refresh
cache populated by a live ingest.

**9. Windows Task Scheduler state.** The commit messages say the weekday task "is disabled and must
stay disabled". I did not query `schtasks` to confirm, because doing so is outside a read-only
adjudication of the named commits and the assertion is the founder's to verify.

**10. Restore-from-backup and disk-full.** `save_portfolio` writes a `.staging` file then replaces.
I did not simulate a full disk, a SIGKILL between write and replace, or a clock jump across a session
boundary.

**11. The 264 files individually.** I proved 0 of 16,677 tracked evidence files differ from their
committed blobs, which is strictly stronger than checking the 264 — but it means I never identified
*which* 264 they were, so I cannot confirm the prior report's list, only that no file differs now.
