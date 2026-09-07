# Red Team Round 7 — QuantOS live paper-trading path

STATUS: COMPLETE (written incrementally; every finding was appended the moment it was confirmed)
STARTED_UTC: 2026-09-01T21:40Z (2026-09-02 ~03:10 IST)
HEAD_UNDER_TEST: `dd280f06`
TIP_AT_START: `41a93f60` (automated sync commit; brief + work record only)
BRIEF: `.launch/RED-TEAM-BRIEF-20260901-ROUND7.md`
PRIOR_ROUND: `.launch/reports/RED-TEAM-20260831-ROUND6.md`
WORK_RECORD: `agent_context/work/active/20260901-redteam-round7.md`

## Independence declaration — READ BEFORE CITING THIS REPORT

**This round is NOT independent.** The author of all eleven repairs under test also wrote the
brief that directs this pass. The strongest verdict this report can support is
**"survived a hostile pass by its author"**. It is never "adjudicated", and it may not be cited
as an independent adjudication in `.launch/STATE.md`, `agent_context/CURRENT.md`, or any gate.

## Working constraints honoured

- No writes to `data/evidence/`, `logs/paper_runs/`, `.env`, or Windows scheduled tasks.
  An unattended session runs at 09:00 IST 2026-09-02 against the real 97-position book.
- No mutants left in the tree. `scripts/daily_auto_sync.ps1` does `git add -A` + push at 23:00 IST.
  All mutants applied to scratchpad copies or applied-and-reverted inside one tool call.
- Probe scripts live outside the repository, in the session scratchpad.
- Adjudication only. No repairs.

## Verdict summary

| # | Claim | Verdict |
|---|---|---|
| C1 | token preference and explicit override | **PARTLY DISPROVEN** — the dashboard's override does not override (R7-04, P2) |
| C2 | `marks_for_open_positions` covers every held name | **PROVEN for the crash, DISPROVEN for the consequence** — the loud failure became a silent total order rejection (R7-01, **P1**) |
| C3 | a bad HTTP 200 is a failed chunk | **HOLDS**; a string-preserving mutant still defeats it (M16, in R7-08) |
| C4 | the drawdown anchor persists across a restart | **PROVEN, driven** — and three mutants disable it with the suite green |
| C5 | a rebalance is judged by coverage | **DISPROVEN** — a session with 0 fills and every order rejected is recorded as executed (R7-02, **P1**) |
| C6 | `save_portfolio` refuses to clobber a concurrent write | **PROVEN, driven** — and the runner's use of it is unguarded (M1) |
| C7 | six decisions extracted, 10 of 10 mutants killed | **DISPROVEN** — 18 mutants, **13 survive**; the functions are guarded and the call sites are not (R7-08, **P1**) |
| C8 | v3 migrates to v4 after the hash check | **HOLDS** (not separately re-derived; the live book is already v4) |
| C9 | the dashboard serves concurrently, no token at import | **HOLDS for the import**; the control endpoints take no credential and check no Origin (R7-06, P2) |
| C10 | an unpriceable quote is skipped, not stamped | **HOLDS for the parse** — and the skipped symbol is what triggers R7-01 |
| C11 | retry, abort does not spend a session, macro cache protected | **PARTLY DISPROVEN** — a *successful* restart still spends one (R7-05, **P1**) |
| — | out of scope of the eleven | `git add -A` nightly (R7-10, P2); state-file loss fails open (R7-09, **P1**); pre-flight vs cross-section date guard (R7-03, P2); dashboard-default P&L (R7-07, P2) |

### The one-paragraph verdict

The eleven repairs do what their commit messages say, and two of them — the persisted drawdown
anchor and the compare-and-swap — were driven under hostile conditions and **held**, closing round
six's R6-10 and R6-17 outright. Round six's own two headline mutants are dead. What the batch did
not do is move the guard to where the defects live: **13 of 18 string-preserving mutants survive,
and every survivor is a call site rather than a function**, so the runner's exit loop, entry loop,
halt refusal, anchor wiring and compare-and-swap wiring can each be disabled entirely with 1,292
tests green. Three of the five new P1s were created by these repairs in the round-six pattern, and
the sharpest is the one the repairs made *quieter*: removing the `LedgerInvariantViolation` crash
left underneath it a governor that refuses **every order in the session** when one held name is
unquoted — so the rebalance that has never run would trade nothing, reconcile cleanly, and exit 0.
**Round five found 5 new P1s, round six found 7, this round finds 5** — and that number was produced
by the author of the work under test, so it is not comparable to the five before it.

## Findings

Five P1, five P2, one P3.

---

### R7-01 — one unquoted holding rejects **every order in the session**, silently, and the run exits 0

**FAMILY** Assumption archaeology / failure injection / operability
**SEVERITY** **P1 Blocker** (escalated: the failure is silent and reconciles clean)
**CLAIM UNDER TEST** C2 — "`marks_for_open_positions` covers every held name ... and can no longer
raise `LedgerInvariantViolation` at `end_session`."

**REPRO** `scratchpad/r7/probeA2_reasons.py`. Real `run_paper_session`, real cached NIFTY bars, real
Mizan model, real `PreTradeRiskGovernor`. Ten-name universe; book holds four names at cost = market
so no drawdown limit interferes; `sessions_held = 10` so the session rebalances; the fake provider
omits exactly one held name (`TCS`) from the response — the 2026-08-31 condition, where 2 of 500
names were unquoted.

**OBSERVED**

```
=========== PROBE A2 ===========
PICKS: ('AXISBANK', 'ITC')  exits: RELIANCE (quoted) TCS (UNQUOTED)
  x12  RELIANCE     SELL  approved=False  PORTFOLIO_VALUATION_UNAVAILABLE: no market price supplied
                                          for held position(s) TCS; leverage cannot be determined
  x12  TCS          SELL  approved=True   RISK_APPROVED_STAGED
orders: {'orders_submitted': 24, 'orders_filled': 0, 'orders_cancelled': 12, 'orders_rejected': 12,
         'total_fills_count': 0, 'open_positions': {'AXISBANK':100,'ITC':100,'RELIANCE':100,'TCS':100}}
PERSISTED holdings: ['AXISBANK','ITC','RELIANCE','TCS']  sessions_held: 1  last_rebalance_on: 2026-09-10
risk: {'kill_switch_active': False, 'halt_reason': '', 'orders_rejected': 12}
Session Concluded & Reconciled: SUCCESS
```

The rejection names `TCS` but it is `RELIANCE`'s order that is refused.
`PreTradeRiskGovernor.evaluate_order` (`src/quant_system/risk/governor.py:366-392`) is handed
`current_prices=self._price_cache` (`src/quant_system/execution/paper_pilot.py:472`), and
`_price_cache` is written only by `process_quote` — which is never called for a name the feed did
not return. **One unvaluable holding refuses every priced order in the book**, exit and entry alike,
for the whole day.

**Why this is a round-seven finding and not a restatement of R6-04.** Before C2 the same missing
name raised `LedgerInvariantViolation` at `:1233`/`:1388` and the session died loudly (round six's
R6-04, the Blocker). C2 removed the crash. The governor refusal underneath it — which predates this
batch (`ecb248ad`, 2026-08-23) — was **masked by that crash and is now the live behaviour**. Round
six predicted exactly this for its P2 R6-11 ("live the moment R6-04 is fixed with a fallback"); it
is now live for the *orders*, not only for the anchor, and nobody has looked at it. **A loud
whole-day failure was converted into a silent one.**

**EXPECTED** Either the governor values the unquotable name the way `_risk_equity` already does one
frame away (at cost, with the warning it already emits), or the runner refuses the rebalance
outright. A rebalance in which 100% of orders are refused for a reason unrelated to any of them must
not report `[PAPER PILOT SUCCESS]` and exit 0.

**BLAST** The 2026-09-10 rebalance, against the real 97-position book. Two of five hundred names
were unquoted on 2026-08-31; 97 of 500 are now held, so the exposure is ~48x. One missing name and
the entire rebalance — every exit of 97 positions and every entry of ~100 picks — is refused. The
run exits 0 with `Session Concluded & Reconciled: SUCCESS`; the operator's only signal is one
`ERROR` line about *marks*, which does not mention orders. It repeats every morning until the
exchange happens to quote that name.

---

### R7-02 — a rebalance in which **zero orders filled and every order was rejected** is recorded as executed

**FAMILY** State machine / assumption archaeology
**SEVERITY** **P1** (silent; resets the ten-session hold clock)
**CLAIM UNDER TEST** C5 — "`rebalance_executed` judges a rebalance by coverage of the selection
(threshold 0.8), not by exits alone."

**REPRO** Same run as R7-01 (`scratchpad/r7/probeA2_reasons.py`), and independently in
`scratchpad/r7/probeA_exit_at_cost.py` with `peak_equity` set high enough to trip the total-drawdown
kill switch (`TOTAL_MAX_DRAWDOWN_BREACHED: 55.00% >= 12.00%`, 24 of 24 orders rejected).

**OBSERVED** In both runs: `orders_filled: 0`, `total_fills_count: 0`, every order rejected, the two
names the model wanted **sold** still held — and

```
PERSISTED  sessions_held: 1   last_rebalance_on: 2026-09-10
```

`rebalance_executed(selected, held)` (`scripts/run_paper_pilot_session.py:213-232`) computes
`len(held & selected) / len(selected)`. It is blind to names held that are **not** in the selection,
and blind to whether anything traded. When the selection is a subset of what was already held,
coverage is 1.0 no matter how completely the session failed.

**This is a regression introduced by C5.** The rule it replaced was
`bool(entry_fills) or holds_the_selection`, with `holds_the_selection` being
`set(engine.positions) == set(mizan_picks)` — set **equality**, which is false here because
`RELIANCE` and `TCS` are still held. Zero entry fills and a book that is not the selection gave
`False` before this batch and gives `True` after it. Verified against the round-six report's own
statement of the prior rule (`RED-TEAM-20260831-ROUND6.md:451-452`).

**EXPECTED** A rebalance in which nothing filled, every order was refused, and the book still holds
names the model instructed it to sell is not an executed rebalance. Coverage is a necessary
condition, not a sufficient one; the *complement* (names held that are not selected) is the half
that was dropped.

**BLAST** The hold clock resets to 1 on a day when nothing happened, so the book is frozen for
another ten sessions in a state the model did not choose — and `last_rebalance_on` is stamped, so
the evidence record says a rebalance occurred. In the halted variant the book is additionally
`risk_halted`, so every later session exits 8 while the state file records a completed rebalance.
Silent: no warning fires, because the `if rebalancing and not executed_rebalance` branch is not
entered.

---

### R7-03 — the pre-flight staleness gate is a **max** and the cross-section guard is an **all-or-nothing**; one lagging name in 500 loses the rebalance day

**FAMILY** State machine / ordering / assumption archaeology
**SEVERITY** **P2** (loud — exit 2, nothing corrupted — but it costs the whole rebalance day and can repeat)
**CLAIM UNDER TEST** C11 / the lead appended to the brief at 2026-09-02 03:05 IST.

**REPRO** `scratchpad/r7/probeB_decision_date.py`. Real `run_paper_session`, real cached bars, real
model, a rebalancing book. One symbol's ingest is made to lag by exactly one session at the bars
boundary — the shape Upstox's rolling overnight publication produces — and everything downstream is
the shipped code.

**OBSERVED**

```
[inject] AXISBANK: dropping its newest bar 2026-08-31 (rest end 2026-08-31)
*** run_paper_session RAISED OUT: MizanLiveFeatureError: cross-section spans 2 decision dates;
    1 symbol(s) do not end at 2026-08-31 (e.g. AXISBANK at 2026-08-28). ...
state file unchanged? True
persisted sessions_completed 10 sessions_held 10
report files written: []
live_paper_status.json written: False
```

`load_mizan_cross_section` is called at `scripts/run_paper_pilot_session.py:1028`, which is
**outside** the `try` that begins at `:1310`, so the error unwinds `run_paper_session` entirely and
`main()` returns 2. Nothing is written: no report, no status file, no state advance.

The two gates disagree by construction. `newest_cached_bar_date()`
(`scripts/run_scheduled_paper_session.py:127-144`) takes the **maximum** `exchange_date` across the
whole store, so `MAX_MISSED_SESSIONS = 0` is satisfied by **one** fresh symbol out of 500.
`_require_one_decision_date` (`src/quant_system/execution/mizan_live_features.py:197-214`) then
requires **every** symbol to end on that same date. The pre-flight measures the best case and the
session requires the worst case.

**Measured, from the live store** (`scratchpad/r7/census.py`, 499 datasets enumerated):

```
symbols: 499
   2026-08-31 499
newest: 2026-08-31 stale count: 0
```

so it is uniform *now*. The brief records the provider mid-rollout at 03:00 IST on 2026-09-02:
18 of a 20-name sample fresh, 2 stale.

**EXPECTED** The pre-flight to measure what the session requires. Either the staleness gate counts
per-symbol (refuse at exit 4, before the session starts, with the lagging names named), or the
cross-section drops a lagging name into `skipped_short_history` and lets the coverage floor decide —
which is what the coverage machinery exists for.

**BLAST** The 2026-09-10 rebalance is the only session between now and then that places orders. One
name out of 500 still un-published at 09:00 and the day is lost, with the only signal being
`paper session exited 2` in an unwatched log. On a **hold** session the cross-section is never built
(confirmed: the 2026-09-01 log has no `Mizan cross-section` line at all), so this is invisible until
the day it matters.

---

### R7-04 — the dashboard's operator-supplied token is silently discarded; the child's own `.env` loader puts the analytics token back

**FAMILY** Assumption archaeology / identity
**SEVERITY** **P2**
**CLAIM UNDER TEST** C9 / `build_pilot_launch` docstring: *"An operator-supplied token still wins ...
the competing analytics variable is removed from the child's environment so it cannot outrank what
the operator just typed."*

**REPRO** `scratchpad/r7/probeD_dashboard_token.py` — drives the real `build_pilot_launch`, then
loads the real runner under the child environment it produced.

**OBSERVED**

```
  .env UPSTOX_ACCESS_TOKEN      exp 2026-09-01 03:30 IST   EXPIRED
  .env UPSTOX_ANALYTICS_TOKEN   exp 2027-08-23 03:30 IST   VALID
  child env has UPSTOX_ANALYTICS_TOKEN : False
  child env has UPSTOX_ACCESS_TOKEN    : True
  the child resolves               : UPSTOX_ANALYTICS_TOKEN
```

`build_pilot_launch` does pop `UPSTOX_ANALYTICS_TOKEN` from `child_env`
(`scripts/serve_live_dashboard.py:216`). The child then runs
`scripts/run_paper_pilot_session.py:34-43`, which reads `.env` at import and re-injects every key
**not already in `os.environ`** — including the analytics token the parent had just removed.
`resolve_upstox_token` prefers it (`:129-132`). The operator's typed token loses.

**EXPECTED** Either the docstring's claim, or the claim withdrawn. The removal is defeated by a
mechanism in the same repository, two files away, that the docstring does not mention.

**BLAST** An operator pasting a fresh token into the dashboard because the pilot is failing on
credentials gets a session that ignores it. Today the two tokens disagree — one is expired and one
is not — so the *accidental* outcome is the working one, which is why nobody has noticed. If the
analytics token is the one that has been revoked, the recovery path does not work and the log will
say the session is using a token the operator did not supply.

**Recorded alongside**, from the same probe: pressing Start with default fields launches
`--capital 50000 --model-profile sprint_50k` against the real ~Rs 9.9 lakh book. `net_pnl` is
`live_equity - initial_cash` (`:1657`) and `total_net_pnl` is
`reconciliation.total_equity - initial_cash` (`:1902`), so the dashboard tile, the session JSON and
the markdown report would all read about **+Rs 9.4 lakh, +1880%**. See R7-07.

---

### R7-05 — every restart on the same trading day spends another of the model's ten held sessions

**FAMILY** State machine / money and counting / assumption archaeology
**SEVERITY** **P1** (silent; shortens the measured hold horizon and pays real statutory cost)
**CLAIM UNDER TEST** C11 — "an aborted session does not spend a held session."

**REPRO** `scratchpad/r7/probeF_book.py` part (b). A **copy** of the real 97-position
`portfolio_state.json` in the scratchpad; three consecutive real `run_paper_session` runs in
`--realtime` mode on the same calendar date, each ending cleanly.

**OBSERVED**

```
book: 97 holdings, cash Rs 145520.31, sessions_held 2, daily_anchor_on 2026-09-01
    first start   (market at 1000): daily_anchor_equity=3802520.31 sessions_held=3
    RESTART -10%  (market at  900): daily_anchor_equity=3802520.31 sessions_held=4
    RESTART -19%  (market at  810): daily_anchor_equity=3802520.31 sessions_held=5
```

Three runs on one date, `sessions_held` 2 -> 5. `state_from_ledger`
(`src/quant_system/execution/paper_portfolio.py:509-511`) is
`previous.sessions_held + (1 if session_completed else 0)` and `sessions_completed` likewise
(`:491`). Neither consults a date. `PaperPortfolioState` carries no `last_session_on` field at all,
so the state file cannot tell "the tenth trading session" from "the tenth time the process ran".

C11 (`df11af59`) closed exactly half of this: a session that *aborts* no longer counts. A session
that *succeeds* still counts, every time, and restarting a completed session is the ordinary
operator action — the dashboard Start button, a manual re-run, or a scheduled run plus a manual one.
Round six recorded three sessions started and abandoned on 2026-08-31 alone
(`logs/paper_runs/scheduled_20260831_*.log`).

**EXPECTED** `sessions_held` counts trading sessions, which is what
`rebalance_due(horizon_sessions)` divides against and what the out-of-sample screen measured
(`HOLD_SESSIONS = 10`). A second run on a date already counted must not advance it.

**BLAST** The executed hold is shorter than the measured one by the number of restarts. Two
restarts across the hold window and the pilot rebalances after eight trading sessions instead of
ten — a different strategy from the one that was validated, paying the NSE statutory round trip
(0.2225%, about Rs 2,200 on this book) earlier and more often than the measurement it claims to
reproduce. `agent_context/CURRENT.md` records that the executed hold was already 12 sessions rather
than 10 once, from two compounding off-by-ones; this is the same class in the other direction and
nothing counts it.

**Note, in the repairs' favour:** the same probe shows **C4 holds**. The persisted drawdown anchor
was reused unchanged across two restarts on a falling market (`daily_anchor_equity=3802520.31`
through a -10% and a further -10% move), which is exactly what round six's R6-10 asked for.

---

### R7-06 — `/api/control/start` and `/api/control/stop` take no credential and check no Origin: any page the operator visits can start or stop a trading session

**FAMILY** Security surface (CSRF), identity
**SEVERITY** **P2** (loopback-bound, paper only — but it is the mechanism that produces the two
concurrent sessions C6 exists to survive)

**REPRO** `scratchpad/r7/probeE_dashboard_http.py`. The real `DashboardHandler` on a real socket;
`subprocess.Popen` and `PID_FILE` stubbed so nothing is launched and nothing under
`logs/paper_runs/` is written. One cross-origin-shaped POST: `Content-Type: text/plain` (a CORS
*simple* request, so a browser sends it with no preflight), `Origin: https://evil.example`, no
cookie, no token, no header the page could not set.

**OBSERVED**

```
dashboard bound at 127.0.0.1:57083 (loopback only -- correct)
HTTP 200 {"status": "STARTED", "pid": 424242, "message": "M\u012bz\u0101n session started. ..."}
sessions the handler launched: 1
   argv: python.exe run_paper_pilot_session.py --realtime --capital 999999 --slippage-bps 5.0
         --end-time-ist 15:30:00 --interval-seconds 10.0 --model-profile sprint_50k --universe-name NIFTY500
   UPSTOX vars handed to the child: ['UPSTOX_ACCESS_TOKEN']
STOP -> 200 {"status": "HALTED", "message": "Trading session halted and reconciled to disk."}
```

`--capital 999999` came from the attacker's body. `do_POST`
(`scripts/serve_live_dashboard.py:87-167`) reads `Origin` never, requires no credential, and sets no
CSRF token. Binding to loopback (`:243-245`, correctly fixed) stops the *network*; it does not stop
the operator's own browser, which is on loopback.

**EXPECTED** A same-origin check on `Origin`/`Sec-Fetch-Site`, or a token the page holds and a
cross-site request cannot read. `http.server` gives neither by default and neither was added.

**BLAST** A visited page can (a) start a second concurrent session against the live book — the exact
overlap C6 documents as still possible and only mitigates the loss from; (b) stop the 09:00
scheduled session mid-day, whose `SIGTERM` handler runs the clean-close path and persists a
part-day book; (c) choose `--capital`, which corrupts every P&L figure in the report (R7-07).

---

### R7-07 — a dashboard-launched session reports a P&L that is wrong by the whole book

**FAMILY** Money and counting
**SEVERITY** **P2** (silent, and it is the number on the operator's screen)

**REPRO** `scratchpad/r7/probeF_book.py` part (a). A **copy** of the real 97-position book, real
`run_paper_session`, `initial_cash=50000` — the dashboard's own default
(`serve_live_dashboard.py:200`) — and `--model-profile sprint_50k`, also its default (`:208`).

**OBSERVED**

```
    total_equity      Rs 3802520.31
    total_net_pnl     Rs 3752520.31
    return_pct            7505.0406 %
    dashboard tile: net_pnl Rs 3752520.31  net_pnl_pct 7505.041 %
```

(The Rs 1000 flat mark in this probe inflates the equity; with real marks the same defect reads
about **+Rs 9.4 lakh, +1880%** on a book whose true cumulative P&L is about **-Rs 8,100**.)

`net_pnl = live_equity - initial_cash` (`scripts/run_paper_pilot_session.py:1657`) and
`total_net_pnl = reconciliation.total_equity - initial_cash` (`:1902`). `initial_cash` is the
**command-line nominal**, not the funding of the book being resumed
(`portfolio.ledger_funding()`, which the engine is actually given at `:1220`). The two agree only
because the scheduled wrapper happens to pass `--capital 1000000.0`, matching the original seed.

**EXPECTED** P&L measured against the book's own carried basis, or the mismatch refused. A resumed
portfolio has a funding figure of its own; a caller-supplied nominal is not it.

**BLAST** Every figure in the session JSON, the markdown evidence report and the live dashboard
tile. It is silent, self-consistent, and the sign is flattering.

---

### R7-08 — 18 string-preserving mutants, **13 survive**. The extracted *functions* are guarded; the *wiring* that calls them is not

**FAMILY** Assumption archaeology
**SEVERITY** **P1** (it is the evidence four of the eleven commits rest on)
**CLAIM UNDER TEST** C7 — "Six decisions are extracted as named functions with behavioural tests,
and 10 of 10 string-preserving mutants are killed."

**REPRO** `scratchpad/r7/mutants.py` and `mutants2.py`, applied to a **mirror of the tree in the
scratchpad** — `src/`, `scripts/`, `tests/`, `data/authorities/` copied out, `PYTHONPATH` pointed at
the copy. The repository tree is never modified, so the 23:00 IST `git add -A` sweep cannot pick a
mutant up. Baseline on the mirror: `188 passed, 1 skipped, 4 deselected` (the 4 deselected read
`data/evidence/`, which is not mirrored).

**OBSERVED**

```
MUTANTS RUN: 18   SURVIVED: 13   KILLED: 5
```

| Mutant | Survives? | What it restores |
|---|---|---|
| M1 `portfolio_hash_at_load = state_hash_on_disk(...)` re-bound one line above the save | **SURVIVES** | **C6's compare-and-swap made vacuous.** R6-17's silent lost update returns |
| M2 `daily_anchor_on=session_date if ... and False else None` | **SURVIVES** | **C4 defeated.** The anchor is never persisted; every restart re-baselines the 4% rule (R6-10) |
| M10b `anchor_to_reuse(portfolio, session_date) and None` | **SURVIVES** | C4 defeated from the read side |
| M17 `if realtime and not daily_peak_anchored and step > 100000:` | **SURVIVES** | the daily baseline is never anchored at all |
| M3 `MIN_REBALANCE_COVERAGE = 0.8` -> `0.26` | **SURVIVES** | **C5's threshold.** A book holding 26% of the selection is an executed rebalance. All five assertions in `test_a_rebalance_counts_only_when_the_book_became_the_selection` still pass |
| M4 exit loop `... and False else []` | **SURVIVES** | the pilot never sells anything on a rebalance |
| M5 entry loop `top_picks if rebalancing and False else []` | **SURVIVES** | the pilot never buys anything on a rebalance |
| M6 `if portfolio.risk_halted and False:` | **SURVIVES** | a tripped kill switch no longer refuses the next session |
| M7 `session_completed=not session_abort_reason or True` | **SURVIVES** | **C11 reverted.** An aborted session spends a held session again (R6-15) |
| M9 `fetch_quotes_with_retry(..., attempts=1)` | **SURVIVES** | **C11 reverted.** One SSL blip at 09:00 loses the day (R6-19) |
| M12 `if len(distinct) > 1 and len(distinct) > 2:` | **SURVIVES** | names ending on two different sessions are ranked against each other |
| M14 `if unpriced and False:` | **SURVIVES** | the operator is no longer told which carried names are unquoted |
| M16 `if (... not a success payload ...) and results:` | **SURVIVES** | **C3 defeated for the first chunk of every poll** |
| M8 `anchor_equity = marked_opening_equity` bound one line above the call | killed | round six's M-F20-1, now caught |
| M15 `if failed_chunks and not results:` | killed | round six's M-F1-1, now caught |
| M11 CAS made vacuous inside `save_portfolio` | killed | the module-level CAS test bites |
| M13 `rebalance_due` always True | killed | |
| M18 `sessions_held` never advances | killed | |

**What this does and does not say.** The five kills are real progress: round six's own two headline
survivors, M-F20-1 and M-F1-1, are both **dead** at HEAD, and `save_portfolio`'s
compare-and-swap is genuinely tested. C7's extraction worked *for the functions*.

It did not work for the **call sites**. M1 and M11 are the same defect at two levels: the CAS
inside `save_portfolio` is guarded and the runner's use of it is not, so a mutant that recomputes
the expected hash one line before the call reinstates round six's Blocker with the whole test suite
green. The same holds for the anchor (M2, M10b, M17), the halt refusal (M6), and both order loops
(M4, M5) — **nothing in the suite drives `run_paper_session` to the point of submitting or refusing
an order**, so the two loops that place every trade in this system can be disabled entirely and
1,292 tests still pass.

M3 is the sharpest single result: the constant `MIN_REBALANCE_COVERAGE` can be moved from 0.8 to
0.26 and every assertion in the test written to pin it still passes, because the test's five cases
are 0.0, 0.25, 0.97, 1.0 and empty — none of which discriminates anywhere in (0.25, 0.97].

**EXPECTED** Mutation evidence that constrains the behaviour the commit messages claim. As measured
it supports "the extracted helpers are guarded", not "the decisions are guarded".

**BLAST** Four of the eleven commits cite mutation testing as their evidence. On this measurement
that evidence covers the helper functions and stops at the boundary where they are called — which
is where round six's Blocker lived and where R7-01 and R7-02 live now.

---

### R7-09 — losing the only copy of the book fails **open**: a fresh Rs 10 lakh portfolio is invented, real fees are paid, and the run reports SUCCESS

**FAMILY** Data integrity / failure injection
**SEVERITY** **P1** (escalated: silent, unrecoverable, and the one file it destroys is not backed up)

**REPRO** `scratchpad/r7/probeG_cas_and_loss.py` part (2). A **copy** of the real 97-position book in
the scratchpad, deleted, then the real `run_paper_session` re-run against it.

**OBSERVED**

```
  (2) state file deleted, session re-run:
      aborted=False  reconciled=True
      new book: 100 holdings, cash 98440.54, sessions_completed 1, sessions_held 1,
                realized_pnl 0.00, total_fees 1091.46
      the 97-position book is gone and the session reports success
```

`load_portfolio` returns `None` when the file is absent and the runner takes
`or PaperPortfolioState(cash=initial_cash)` (`scripts/run_paper_pilot_session.py:1001`).
`rebalance_due` returns `True` for an empty book (`paper_portfolio.py:250-251`), so the session
immediately buys a fresh hundred-name portfolio, pays **Rs 1,091.46** of real statutory cost, and
exits 0 with `[PAPER PILOT SUCCESS]`. The carried `realized_pnl` and `total_fees` reset to zero.

The runner already knows this: `:1188` warns the operator that "deleting it invents a fresh
portfolio and discards the real book". The code says so and then does it anyway, with no guard,
because absence is indistinguishable from a first install.

**And there is no copy of it anywhere.**

```
git check-ignore -v logs/paper_runs/portfolio_state.json
.gitignore:21:logs/    logs/paper_runs/portfolio_state.json
```

The nightly sync commits and pushes 2,292 evidence files and ignores `logs/` entirely. The
authoritative record of the book — hash-protected against *corruption* — has no backup, no restore
path, and no second copy. One SSD event, one `logs/` cleanup, one operator deleting a "log
directory", and the book is gone with the next scheduled session reporting a clean start.

**EXPECTED** Absence of the state file on a machine that has run sessions before is a different
condition from a first install, and it is distinguishable — `sessions_completed`, the session JSON
reports beside it, and the auto-sync history all record that a book existed. Fail closed, or write
the book somewhere the backup reaches.

**BLAST** Total, silent loss of the pilot's entire accounting history, with a green exit code and an
evidence report describing a brand-new portfolio as though it were the running one.

---

### R7-10 — `scripts/daily_auto_sync.ps1` runs `git add -A` and pushes to `origin/main` every night: a standing PROTOCOL §4 violation that endangers every agent's uncommitted work

**FAMILY** Operability / data integrity
**SEVERITY** **P2** (raised in the brief; recorded here as its own finding)

**REPRO** Read `scripts/daily_auto_sync.ps1:48`, and the live task registration:

```
Name   : QuantOS-DailyAutoSync
State  : Ready
Next   : 9/2/2026 11:00:00 PM
Last   : 9/1/2026 11:00:01 PM
Result : 0
Action : powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File
         "D:\quant_system\scripts\daily_auto_sync.ps1"
```

**OBSERVED** The script stages **everything** (`git add -A`), commits as
`sync: daily automated checkpoint [<utc>]`, then `git pull --rebase --autostash origin main` and
`git push origin main`. It already swept this round's brief and work record into `41a93f60` and
pushed them, minutes after they were written — visible in `git log`.

`agent_context/PROTOCOL.md` §4 lists "repository-wide format, lint-fix, dependency sync/update, code
generation, and Git staging" among operations requiring explicit single-owner coordination, and says
plainly: **"Do not use `git add -A` or broad commits in a shared checkout. Stage explicit owned
paths only."** The repository's own contract forbids exactly what runs unattended every night.

**Concrete consequences, not hypothetical:**

- A half-finished edit by any agent at 23:00 is committed and pushed to `main` under a message that
  attributes it to nobody. **This is why every mutant in R7-08 was applied to a scratchpad mirror.**
- `git pull --rebase --autostash` rewrites local history unattended, against a `main` with no branch
  protection (`403 Upgrade to GitHub Pro`, per `agent_context/CURRENT.md`).
- CI has not run since 2026-08-29 for billing, so nothing checks what is pushed.

**Mitigating, and verified:** `.env` and `logs/` are both in `.gitignore`
(`git check-ignore` above; `.gitignore:21,28-29`), so the sweep does **not** publish the Upstox
tokens or the live book to the remote. That is also why R7-09 has no backup.

**EXPECTED** Stage declared paths, or run only when `git status --porcelain` shows nothing owned by
an active work record.

---

## Claims that survived the pass

Stated as explicitly as the failures, because a red-team report that only lists breaks is not a
measurement.

| Claim | Verdict | Evidence |
|---|---|---|
| **C4** — the drawdown anchor persists across a restart on the same session date | **HOLDS, driven** | `probeF_book.py` (b): three consecutive real sessions on one date across a -10% and a further -10% move all reused `daily_anchor_equity=3802520.31`. Round six's R6-10 is closed. *Residual:* mutants M2, M10b and M17 all disable it with the suite green (R7-08) |
| **C6** — `save_portfolio` refuses to write over a file whose hash changed since load | **HOLDS, driven** | `probeG_cas_and_loss.py` (1): a real concurrent write mid-session; session B refused to persist, was marked `aborted=True`, exited 10, and A's book survived (`cash 133174.64, sessions_completed 3`). Round six's R6-17 silent lost update is closed. *Residual:* M1 defeats the runner's use of it with the suite green |
| **C10** — a quote that cannot be priced returns `None` and is skipped | **HOLDS** for the parse itself (`parse_quote_payload`, behavioural tests at `tests/test_paper_pilot_carried_session.py:1121-1201`). *But* the skipped symbol then becomes an unvaluable held position and triggers R7-01 |
| **C7** — round six's own two headline survivors | **KILLED at HEAD.** M-F20-1 (`anchor_equity = marked_opening_equity` one line above the call) and M-F1-1 (`if failed_chunks and not results:`) are both caught now |
| The closing `process_quote` loop cannot fabricate a fill | **HOLDS.** `Quote.bid_size`/`ask_size` default to 0, so `OrderBookSnapshot.from_quote` yields an empty ladder and nothing fills at the close. The hypothesis that C2's cost-basis marks could **sell** an unquoted holding at its own cost was tested and is **false** — the order is cancelled instead (`orders_cancelled: 12`) |
| The 0.8 coverage floor is reachable on the real book | **HOLDS.** `probeC_coverage_feasibility.py`: 55 of 100 picks already held, 45 to buy, only 2 unaffordable at an allocation of Rs 9,481.94 (`POWERINDIA` Rs 33,760, `FORCEMOT` Rs 17,526), so the best achievable coverage on 2026-09-10 is **98/100 = 0.980** against a floor of 0.8. The threshold does not lock the pilot into a daily rebalance |

---

### R7-11 — the comment defending the instrument-key fallback states a consequence the code does not have

**FAMILY** Assumption archaeology
**SEVERITY** **P3**

`scripts/run_paper_pilot_session.py:596-600`:

> *"Both are kept ... but this is recorded so nobody removes the fallback as redundant.
> **Removing it would return an empty book with no error.**"*

**REPRO** `scratchpad/r7/probeI_fallback.py`. The real `fetch_upstox_live_quotes` against the
provider shape measured on 2026-09-01 (request keyed by ISIN, response keyed by symbol), then the
same function with `payload.get(alt_key)` deleted.

```
  shipped code (both lookups): 10 of 10 quotes
  fallback removed: RAISED QuoteFeedError: Upstox returned no quotes for any of 10 symbols.
                    Refusing to trade: a session priced from anything other than ...
```

`if not results: raise QuoteFeedError(...)` (`:649-654`) catches exactly this. The removal is loud,
not silent. The finding stands — the primary lookup really is dead in production and the fallback
really does carry every quote — but the stated consequence is wrong, and it is the sentence a reader
would rely on. Same class as round six's R6-20.

---

## Round six's open items, rechecked

The brief asked for confirmation rather than rediscovery. Verified at `dd280f06`.

| Round six | Status now |
|---|---|
| R6-01 chunk lost to HTTP 200 | **CLOSED** (`:582-586`). *But* mutant M16 makes it vacuous for the first chunk of every poll with the suite green |
| R6-02 `last_price: 0` becomes Rs 0.00 | **CLOSED** by `parse_quote_payload`. *But* the skipped symbol now feeds R7-01 |
| R6-03 the partial-batch test drives a total failure | **CLOSED.** `tests/test_paper_pilot_carried_session.py:700-712` now returns a genuinely good first chunk and asserts `"100 of 150 symbols returned"`. This is why round six's M-F1-1 is dead |
| R6-04 fifth/sixth ledger consumer crashes | **CLOSED** as a crash. Replaced by R7-01 as a silent total rejection |
| R6-05 13/13 mutants survive | **PARTLY CLOSED.** 5 of 18 killed, including both of round six's headline survivors. 13 still survive — R7-08 |
| R6-06 risk equity marks unquoted at cost | **CHANGED, not closed.** `_risk_equity` still substitutes cost and now says so (`paper_pilot.py:203-232`). The *order* path refuses instead — which is R7-01 |
| R6-07 partial-fill rebalance recorded as executed | **CLOSED for that shape** (coverage 0.25 < 0.8). Re-opened in a different shape by R7-02 |
| R6-08 `max_position_weight` drift never trimmed | **STILL OPEN, and inert on this book.** `weight_drift_report` reports it; nothing corrects it. Measured now: heaviest holding **SUZLON 0.98%** of equity against a 30% limit, **0 breaches** across 97 names. *Assessment for the rebalance day:* it does not change severity. The mechanism (`current_held == 0`, `:1539`) means the 55 carried picks keep their old sizes while 43 new ones get the new equal allocation, so the book stays near equal weight rather than concentrating |
| R6-09 flat-book alarm states a loss that did not occur | **CLOSED** (`flat_book_alarm`, three branches, behaviourally tested) |
| R6-10 daily baseline is "since this process started" | **CLOSED, driven.** See the survived-claims table |
| R6-11 unquoted holding contributes zero to the anchor | **CLOSED** (`equity_marked_at` falls back to `position.average_price`) |
| R6-12 all-market summary test cannot catch a code regression | **STILL OPEN.** `tests/test_scheduled_paper_session.py:186` still skips when the file is absent and still never executes `refresh_bars` |
| R6-13 `--corporate-actions-dir` default | **CLOSED** (`build_refresh_command`, `:213-214`) |
| R6-14 the refresh authenticates with the daily token | **CLOSED** (`data/upstox.py` reads both; `.env` analytics token valid to 2027-08-23) |
| R6-15 zero-priced name aborts; aborted session advances the clock | **CLOSED.** Replaced in the other direction by R7-05: a *successful* restart still spends a session |
| R6-16 macro overwrite on an empty 200 | **CLOSED** (`ingest_macro_regimes.py`, `tests/test_macro_cache_guard.py`) |
| R6-17 no lock, no CAS | **CLOSED for the loss, driven.** Overlap is still possible and R7-06 is a fresh way to cause it |
| R6-19 one failed chunk at startup loses the day | **CLOSED** (`fetch_quotes_with_retry`). *But* mutant M9 reverts it with the suite green |
| R6-20 false statement of mechanism above the entry loop | **CLOSED** (`:1520-1532`). Recurs as R7-11 elsewhere |
| R6-21 per-interval log volume | **PARTLY CLOSED.** Coverage logging is now change-triggered (`last_reported_coverage`). `:1542` "selected but no quote this step" is still per-step per-name, and a rebalance day is the day it fires |
| R6-22 token in the log and on the command line | **CLOSED** (`build_pilot_launch`). Reopened differently as R7-04 |

---

## Coverage

- **Claims adjudicated:** 11 of 11, plus the two sections appended to the brief at 03:05 IST.
- **Families worked:** input boundaries; identity/authorization (the dashboard surface); concurrency
  and ordering; failure injection; state machine; money and counting; data integrity; security
  surface; the human path (dashboard defaults); operability; assumption archaeology. **Scale was not
  worked** — see NOT PROBED.
- **Probes attempted:** 11 executable probes in the session scratchpad, all outside the repository.
  **18 string-preserving mutants** written and executed against a scratchpad mirror of `src/`,
  `scripts/`, `tests/` and `data/authorities/`. **9 full end-to-end `run_paper_session` executions**
  against real cached NIFTY 500 bars, the real Mizan model, the real `PreTradeRiskGovernor` and a
  scratch copy of the real 97-position book. One real `ThreadedDashboardServer` bound to a socket
  and driven over HTTP. Two full 500-name cross-section builds (~102s each) and one full
  499-dataset store census.
- **Static gates re-run at `dd280f06`:**

  ```
  1292 passed, 1 warning in 90.77s (0:01:30)
  ```

  which matches the work record's claim exactly.
- **Targets:** `scripts/run_paper_pilot_session.py`, `scripts/run_scheduled_paper_session.py`,
  `scripts/serve_live_dashboard.py`, `scripts/daily_auto_sync.ps1`,
  `src/quant_system/execution/paper_portfolio.py`, `paper_pilot.py`, `mizan_live_features.py`,
  `src/quant_system/risk/governor.py`, `src/quant_system/core/domain.py`,
  `src/quant_system/execution/orderbook_sim.py`, and the nine test modules mirrored for mutation.
- **Live state:** unmodified and verified at the end of the run —
  `logs/paper_runs/portfolio_state.json` still hashes
  `08690772fd957caf34abe0830318d90ef6906def533cb3df9b00cdb18fca9de3`, still 97 holdings,
  `sessions_completed 2`, `sessions_held 2`. No file under `logs/paper_runs/` was written; no file
  under `data/evidence/` changed; `.env` untouched; both scheduled tasks read only
  (`Get-ScheduledTask`, no `Set-`/`Register-`/`Unregister-`). `git status --short` shows this report
  and the brief's own 03:05 IST edit, nothing else. No mutant was ever present in the tree.

---

## The convergence question

> Rounds two through six found **2, 3, 3, 5, 7** new P1s. Has the defect-creation rate converged?

**Round seven finds 5 new P1s.** The sequence is now **2, 3, 3, 5, 7, 5**.

That is a decrease, and it is the first decrease in the sequence. It is also not convergence, and
the honest reading has to carry four qualifications, all of which point the same way:

1. **This round is not independent.** The adjudicator wrote all eleven repairs and wrote the brief
   that directed the search. Rounds two through six were run by an agent that had not. Comparing
   this number to those five is comparing a self-check to five external ones, and a self-check finds
   fewer defects for reasons that have nothing to do with the code. **5 from a hostile self-pass is
   not evidence of the same kind as 7 from an independent one.**

2. **Three of the five are the previous round's repairs, exactly as before.**
   - R7-01 exists *because* C2 removed the crash that was masking it. Round six predicted this in
     R6-11 and the prediction came true one level up.
   - R7-02 exists *because* C5 replaced set-equality with coverage; the shape it now blesses was
     refused before this batch.
   - R7-05 exists *because* C11 fixed the aborted half of the session count and left the successful
     half.
   The pattern "each round's P1s were created by the previous round's repairs" is **intact**, at
   three of five. It has not broken.

3. **Two of the five are older defects that the repairs made reachable or visible rather than
   created.** R7-08's mutation result and R7-09's fail-open loss both predate this batch. Round six
   would have found them with the same probes; it did not run them. A defect-creation *rate* is not
   measurable from a count that mixes creation with discovery, and every round in this sequence has
   mixed them.

4. **The strongest positive signal in this round is not the count.** It is that round six's own two
   headline mutants — M-F20-1 and M-F1-1, the ones whose survival was that round's central finding —
   are both **dead** at HEAD, and that C4 and C6 both held under a driven concurrent attack. The
   repairs did fix what they claimed, at the level they claimed it. What they did not do is move the
   guard to the level where the defects actually live: **13 of 18 mutants still survive, and every
   one of the survivors is a call site rather than a function.**

**The defensible conclusion:** the *severity* of what is found is falling — round six's headline was
a session-killing crash on the next morning's run; round seven's is a silent no-op on a rebalance
that will not happen for another eight sessions — but the *mechanism* that generates new P1s from
repairs is unchanged, and the count is not evidence of convergence because the observer changed
between round six and round seven. **The next round must be run by an agent that did not write the
repairs.** Until one is, this sequence has one data point too few to have a trend.

---

## NOT PROBED

The most important section. Each item is something a later round should take.

1. **No live Upstox call was made.** Deliberate, for the same reason round six gave: not spending
   the operator's rate budget and not handling the credential. Consequence: the **09:00-09:15
   pre-open payload shape is still unmeasured**, which is the single input that decides whether
   R7-01 fires on the rebalance morning. `LIVE-PROVIDER-PROBE-20260901.md` sampled 17:00, after the
   close, and found `last_price` present and non-zero on 10 of 10 — it did **not** sample the
   pre-open. If a pre-open `last_price` of `0` is normal for a name that has not traded, C10 drops
   it, and if that name is held, R7-01 refuses every order in the session. **The cheapest decisive
   probe remains one authenticated `market-quote/quotes` call at 09:02 IST for the 97 held names.**
   That single call decides R7-01's live blast radius.
2. **The 2026-09-02 09:00 run itself.** It is in the future and running it would write the real
   book. Everything here is driven against a scratch copy.
3. **The rebalance on the real 500-name universe, end to end.** All nine full sessions ran on a
   10-name universe or a hold. R7-02 and R7-01 are demonstrated at 4 holdings and 2 picks; the
   arithmetic at 97 holdings and 100 picks is computed (`probeC`, `probeH`) but not executed. In
   particular the **multi-step cash cascade** — exits staged in step N filling in step N+1 and
   funding entries in step N+2, across up to 780 intervals — was never run. That is the mechanism
   the whole rebalance depends on and nothing has ever executed it at scale.
4. **`newest_cached_bar_date()` at 09:00 during a live rollout.** R7-03 is driven by injecting the
   lag; the *frequency* of a lagging name at 09:00 is unmeasured. The brief's 03:00 sample (18 of 20
   fresh) is six hours before the session.
5. **Two genuinely concurrent OS processes.** R7-06's CSRF is driven over a real socket with
   `Popen` stubbed; R7-09's CAS is driven with the concurrent write injected in-process at the right
   moment. Neither is two real `python.exe` processes racing, so the **window between
   `state_hash_on_disk` and `staging.replace`** in `save_portfolio` — a real check-then-act — is
   reasoned about and not measured. C6 prevents the *observed* loss; it does not prevent a loss in
   that window.
6. **Scale.** 500 symbols x ~780 intervals. `engine.fills`, `engine.audit_log`, `_orders` and
   `_open_orders` all grow without bound, and on a rebalance day the exit loop re-submits a fresh
   proposal for every unsold holding **every step** — my 12-step probe produced 24 orders for 2
   names, which extrapolates to roughly **75,000 orders** on a 780-step rebalance day with 97
   holdings. Nothing measures the memory or the time. Round six flagged this and it is still open.
7. **`clear_paper_halt.py`.** Round six's NOT PROBED #12, still not read or exercised. It is the
   operator's only documented recovery from `SystemExit(8)`, and mutant M6 shows the refusal it
   recovers from is itself untested.
8. **The `sprint_50k` profile.** It is the dashboard's default (`serve_live_dashboard.py:208`) and
   nothing in this round or round six exercised its risk limits (50% position, 3% daily, 8% total)
   against a 97-name book.
9. **The evidence store and the ingester.** `ingest_all_market_data.py` and its
   `_clean_stale_locks` were not read this round. Round six's NOT PROBED #8 stands.
10. **Whether `staging.replace(path)` is atomic across processes on this NTFS volume.** Assumed,
    not verified. Round six's #10 stands.
11. **The dashboard HTML.** `quant_system.server.ui.live_dashboard.HTML_DASHBOARD` is served to a
    browser and was not read. Whether it reflects any field from `live_paper_status.json` unescaped
    — a stored-XSS surface fed by symbol names from a CSV authority — is unexamined.
12. **Timezone and clock.** Every timestamp is IST-fixed and nothing tests a DST-free assumption, a
    clock jump, or a session that spans midnight. `session_date` comes from `now_ist().date()` at
    process start and never re-reads it.
13. **Round five's 15 P2 / 9 P3.** Not re-verified. Where this report disagrees with an earlier one
    it says so; silence is not agreement.
14. **The `.launch/` gate documents.** This report was not reconciled against `.launch/STATE.md`;
    per the brief, that is a coordinator action and `STATE.md` is claimed elsewhere.
