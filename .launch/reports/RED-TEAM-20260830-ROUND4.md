# Red Team round four — the risk-governor repairs (2026-08-30/31)

STATUS: COMPLETE — all nine claims adjudicated
COMMITS IN SCOPE: `46c7bb67` "the daily limit measures the day, and a halt can actually be cleared",
then `d6f421e3` "seed the daily limit from marked equity, and stop a halt reporting success", which
the author wrote in response to claims 1-6 of this report while it was still open.
ADJUDICATOR: Claude Code (fourth independent pass). **Wrote none of the work under test.**
BRIEF: `.launch/RED-TEAM-BRIEF-20260830-ROUND4.md`
HEAD AT START: `46c7bb67`  ·  HEAD AT FINISH: `d6f421e3`

**How to read this report.** Claims 1-6 were adjudicated against `46c7bb67` and are left as written:
they are the evidence that produced `d6f421e3`, and rewriting them would erase the record of what
was wrong. Claims 7, 8 and 9 are adjudicated against `d6f421e3` and state explicitly which of the
earlier findings that commit closed. Where a claim-5 Blocker has since been repaired, the claims
table says so.

## Verdict

**NOT READY. One Blocker remains open; the two Blockers this report opened are repaired and
verified.**

**Today's session is safe to run.** The scheduled task fires at 09:00 IST on 2026-08-31 with no
`portfolio_state.json` on disk, so it is a first run. That path was driven end-to-end through the
real runner and it reconciles, persists a valid schema-v3 file, advances the hold clock and sets the
peak. Nothing found here fires on session 1.

The open Blocker and the two new Majors fire at **session 11**, the first rebalance — roughly
2026-09-14 on a weekday schedule. There is time to repair them before they matter, and no reason to
disable tomorrow's run.

| | Count |
|---|---|
| P1 Critical open | **1** (P1-3) |
| P1 Critical opened by this report and repaired at `d6f421e3` | 2 (P1-1, P1-2) |
| P2 Major open | **7** |
| P3 Minor open | **4** |

## Findings

### P1 Critical — open

| # | Finding | Claim |
|---|---|---|
| P1-3 | A rebalance in which **every order was refused** is persisted as a rebalance that happened: `last_rebalance_on` advances and `sessions_held` resets to 1 with zero fills. The hold clock is reset by an event that did not occur, the stale book is held another nine sessions, and the halt-recovery tool hands the operator back a pilot that looks healthy. Confirmed still live at `d6f421e3` (session 21: 228 rejections, 0 fills, `sh=1`) | 3, 8 |

### P1 Critical — opened by this report, repaired at `d6f421e3`, repair verified

| # | Finding | Claim |
|---|---|---|
| P1-1 | The 4% **daily** limit was seeded from `ledger_funding()`, a cost figure, so it measured cumulative unrealized loss since inception. A 5.63% drift over ten sessions with **zero** intraday movement halted the book on the first order of the first rebalance — which is the exit. **Repaired**: the same 13-session run now completes; a deeper decline halts at session 21 with `TOTAL_MAX_DRAWDOWN_BREACHED: 14.20% >= 12.00%` | 5, 8 |
| P1-2 | The session that permanently halted the pilot reconciled cleanly, printed `[PAPER PILOT SUCCESS]` and exited 0; the scheduler wrapper recorded `LastTaskResult: 0` regardless. **Repaired**: exit 9, distinct banner, halt reason and recovery command; `endlocal & exit /b %RC%` | 5, 8 |

### P2 Major — open

| # | Finding | Claim |
|---|---|---|
| P2-1 | An unreachable quote falls back to a hardcoded `Rs 1000.00`, tagged `REAL_NSE_ESTIMATE` and logged as `[REAL NSE FEED]`. Observed once in 500 names on a live fetch tonight; 451 of 500 NIFTY500 names have no real default | 5 |
| P2-2 | `clear_paper_halt.py` reports "Not halted. Nothing to do." for a book that is halting right now, because the halt is persisted only at session end. No lock, no PID check, no in-progress marker | 3 |
| P2-3 | Nothing tests what the runner passes as `initial_equity` — the argument `46c7bb67` changed and got wrong. The detector added for it does not work (P2-7) | 4, 9 |
| P2-4 | The session report's capital table does not balance: `Initial Capital + Net P&L != Total Equity`, off by exactly the carried entry fees, on every session holding a position. Always flattering | 6 |
| P2-5 | **New at `d6f421e3`.** The risk baseline is now marked to market but the position sizing still uses `ledger_funding()`, so a drawn-down book over-allocates and silently drops a selected name (`TMPV`), ending with 9.87% cash against a declared 5% buffer | 8 |
| P2-6 | **New at `d6f421e3`.** The halt reaches the exit code and the console but not the markdown report (`Reconciliation Status: PASS`, zero mentions of halt or kill) or `live_paper_status.json` (`status: COMPLETED`) | 8 |
| P2-7 | **New at `d6f421e3`.** `test_the_governor_is_seeded_from_marked_equity_not_a_cost_figure` **passes** against `46c7bb67`, the commit it names. Four of five mutants survive, including a verbatim reintroduction of P1-1 and a seed of zero | 9 |

### P3 Minor — open

| # | Finding | Claim |
|---|---|---|
| P3-1 | One fixed staging filename per state path; concurrent writers crash rather than corrupt on Windows, but the crash discards the whole session | 3 |
| P3-2 | The comment claiming exit proceeds fund the same step's entries is false; the entries land one interval later | 6 |
| P3-3 | A carried holding with no quote is marked at cost for the **whole session**, not just the risk baseline. Measured: 9.48% true drawdown reported as 8.54% with one name of ten unquoted. The bias is toward blindness, not toward a spurious halt | 8 |
| P3-4 | In realtime mode the daily baseline is anchored to a quote snapshot taken ~2.5 minutes before the first drawdown check, inside the most volatile window of the session. One-sided | 8 |

### One false claim in a commit message

`d6f421e3` states "Three detectors added, all of which fail against this commit's parent." One of the
three passes. Round 2 found three false claims in this author's messages; they remain uncorrected,
and this is a fourth — in the commit that responded to a report about exactly this pattern.

## Claims

| # | Claim | Status |
|---|---|---|
| 1 | The governor change is safe for every other caller | **PROVEN** for other callers; the `max()` floor makes the total switch structurally weaker than the daily one (quantified in claim 2) |
| 2 | The daily limit now measures the day | **PART DISPROVEN at `46c7bb67`** — fired on a multi-session decline with zero intraday move. **Repaired at `d6f421e3`**, verified in claim 8 |
| 3 | `clear_paper_halt.py` cannot lose or corrupt the book | **PROVEN for the tool**; the recovery it belongs to is not — 1 new P1, 1 P2, 1 P3 |
| 4 | The two replaced tests are worth something | **PROVEN** — both kill their mutants; detector is loose; 1 new P2 |
| 5 | Tomorrow's session completes correctly | **Session 1 PROVEN**; session 11 DISPROVEN at `46c7bb67` — 2 P1 (both **repaired at `d6f421e3`**), 1 P2 open |
| 6 | The first-run and second-run boundary | **PROVEN** for peak/halt/clock/fees; 1 new P2, 1 new P3 |
| 7 | Regression against rounds 2 and 3 | **PROVEN** at `d6f421e3` — nothing disturbed, 1176 green |
| 8 | Anything `46c7bb67` / `d6f421e3` introduced, overstated, or broke | **PART DISPROVEN** — both Blockers repaired; 2 new P2, 2 new P3, 1 false message claim, P1-3 still open |
| 9 | The three new detectors fail against `46c7bb67` | **DISPROVEN** — one of the three passes against the commit it names |

### Claim 1 — the governor change is safe for every other caller

**PROVEN for the other callers. The floor is defensible but it is what makes the total switch
structurally weaker than the daily one.**

#### Every construction site, enumerated

```
$ grep -rn "PreTradeRiskGovernor(" --include=*.py src scripts tests
src/quant_system/analytics/optimizer.py:57      PreTradeRiskGovernor()
src/quant_system/backtest/engine.py:50          risk_governor or PreTradeRiskGovernor()
src/quant_system/execution/paper_broker.py:33   risk_governor or PreTradeRiskGovernor()
src/quant_system/execution/paper_pilot.py:143   risk_governor or PreTradeRiskGovernor(limits=...)
src/quant_system/execution/realtime_shadow.py:285   risk_governor or PreTradeRiskGovernor()
src/quant_system/execution/shadow_replay.py:65      risk_governor or PreTradeRiskGovernor()
src/quant_system/server/app.py:838              PreTradeRiskGovernor()
src/quant_system/server/app.py:899              PreTradeRiskGovernor(limits=_CURRENT_RISK_LIMITS)
src/quant_system/server/supervisor.py:175       PreTradeRiskGovernor(limits=RiskLimits())
scripts/daily_pipeline.py:136                   PreTradeRiskGovernor(limits=risk_limits)
scripts/run_paper_pilot_session.py:807          <-- the only caller passing all_time_peak_equity
+ 27 test sites
```

Findings from that enumeration:

1. **Exactly one production caller passes the new parameter.** Every other site passes `limits`
   only, so `all_time_peak_equity is None`, so `_all_time_peak_equity = init_eq` — byte-identical to
   the parent commit. No behaviour change is possible for them.
2. **No caller uses positional arguments beyond the first.** A new third positional parameter could
   have silently captured an existing second positional; none exists. Checked all 38 sites.
3. `restore_state` and `get_state` already carried `all_time_peak_equity` as a separate key
   (`governor.py:127,144`), so the split does not break the persistence shape. Neither has a
   production caller.

#### Is the `max(init_eq, all_time_peak_equity)` floor right?

`governor.py:51-53`. It is applied **twice** — the runner already floors at the call site
(`run_paper_pilot_session.py:810`, `max(portfolio.peak_equity, opening_equity)`), then the
constructor floors again. Harmless, and it removes the only real hazard: on a first run
`portfolio.peak_equity` is `0.00`, and without a floor `_all_time_peak_equity = 0` would make
`if self._all_time_peak_equity > Decimal("0")` skip the trailing check entirely
(`governor.py:235`).

It masks no caller. A "lower trailing peak" is not a thing any caller wants: no reset-high-water-mark
operation exists anywhere in the repository, and `peak_equity` is already monotonic by construction
in `state_from_ledger` (`paper_portfolio.py:379`).

**But the floor has a structural consequence the commit does not state.** Because
`_all_time_peak_equity >= _daily_peak_equity` always, and `1 - E/P` is increasing in `P`, the trailing
drawdown is **always >= the daily drawdown**. The two thresholds are 4% and 12%. So the daily switch
fires first unless the all-time peak exceeds the daily peak by more than `0.12/0.04`-implied margin:

    TOTAL fires before DAILY  <=>  0.88·A > 0.96·F  <=>  A > 1.0909·F

Measured (`scratchpad/probes/p2_which_switch.py`), `F` = funding, `A` = all-time peak:

```
 peak/fund  marked/fund  reason
      1.00         0.96  DAILY_DRAWDOWN_LIMIT_BREACHED
      1.09         0.97  APPROVED
      1.09         0.96  DAILY_DRAWDOWN_LIMIT_BREACHED
      1.20         1.00  TOTAL_MAX_DRAWDOWN_BREACHED
      1.20         0.97  TOTAL_MAX_DRAWDOWN_BREACHED
      1.20         0.96  DAILY_DRAWDOWN_LIMIT_BREACHED
      1.50         0.97  TOTAL_MAX_DRAWDOWN_BREACHED
      1.50         0.96  DAILY_DRAWDOWN_LIMIT_BREACHED
```

Read the `1.50` rows: a book **50% above** its funded capital at its peak, now 4% below funding,
reports `DAILY_DRAWDOWN_LIMIT_BREACHED` for a 36% trailing drawdown. The switch that fires names the
wrong rule whenever the loss is deeper than 4% of funding — which is every interesting case.

#### Regression evidence

```
$ .venv/Scripts/python.exe -m pytest -q
1173 passed, 1 warning in 96.49s
$ .venv/Scripts/python.exe -m ruff check .
All checks passed!
$ .venv/Scripts/python.exe -m mypy src
Success: no issues found in 141 source files
```

Matches the commit message's claim of "1173 tests passing (was 1166)", "ruff clean", "mypy clean on
141 files". All three verified.

### Claim 2 — the daily limit now measures the day

**PART PROVEN, PART DISPROVEN.** Verified independently of the author's simulation, at unit level
and end-to-end through the real runner.

| Sub-claim | Verdict |
|---|---|
| The daily rule fires on a genuine intraday decline | **PROVEN** |
| The daily rule does **not** fire on a multi-session decline | **DISPROVEN** — see claim 5 P1-1 |
| `TOTAL_MAX_DRAWDOWN_BREACHED` is reachable | **PROVEN** — it was unreachable at `86d1769c` |
| ...at the right depth | **PROVEN** at the 12% boundary, but only inside a narrow band |

#### Positive and negative controls, one governor per session (`scratchpad/probes/p3_intraday.py`)

```
--- A  POSITIVE CONTROL: opens at funding, falls 4.1% intraday   funding=1000000.00  peak=1000000.00
    step 0: mark=1000000.00  daily_peak=1000000.00  all_time=1000000.00  -> APPROVED
    step 1: mark= 990000.00  daily_peak=1000000.00  all_time=1000000.00  -> APPROVED
    step 2: mark= 970000.00  daily_peak=1000000.00  all_time=1000000.00  -> APPROVED
    step 3: mark= 959000.00  daily_peak=1000000.00  all_time=1000000.00  -> DAILY_DRAWDOWN_LIMIT_BREACHED: 4.10% >= 4.00%

--- B  opens 5% underwater, price FLAT all day (zero intraday move)
    step 0: mark= 950000.00  daily_peak=1000000.00  all_time=1000000.00  -> DAILY_DRAWDOWN_LIMIT_BREACHED: 5.00% >= 4.00%

--- C  opens 10% up, falls 4.1% from that intraday high   peak=1100000.00
    step 0: mark=1100000.00  daily_peak=1100000.00  -> APPROVED
    step 2: mark=1054900.00  daily_peak=1100000.00  -> DAILY_DRAWDOWN_LIMIT_BREACHED: 4.10% >= 4.00%

--- D  opens 10% up, falls only 2% intraday
    step 2: mark=1078000.00  daily_peak=1100000.00  -> APPROVED
```

A, C and D are correct. **B is the defect**: the daily peak is seeded from `ledger_funding()`, a cost
figure, so a book that opens 5% underwater against its own basis halts on the first order with the
price completely flat. There is no day in the measurement at all. Full end-to-end reproduction in
claim 5, P1-1.

The rule the code actually implements is
`max(4% below funded capital, 4% below today's intraday high)` — the two conflated, with the first
having nothing to do with a day.

#### `TOTAL_MAX_DRAWDOWN_BREACHED` is now reachable, at exactly 12%

Round 3's P2-4 said it was unreachable. At `46c7bb67` it is reachable, and the depth is exact:

```
  mark=1056100.00  total_dd=11.9917%  -> APPROVED
  mark=1056000.00  total_dd=12.0000%  -> TOTAL_MAX_DRAWDOWN_BREACHED: 12.00% >= 12.00%
  mark=1055900.00  total_dd=12.0083%  -> TOTAL_MAX_DRAWDOWN_BREACHED: 12.01% >= 12.00%
```
(funding 1,000,000; carried peak 1,200,000; boundary inclusive, as `>=` implies.)

**But only inside a band.** Because `_all_time_peak_equity >= _daily_peak_equity` by construction
and `1 - E/P` increases in `P`, `total_dd >= daily_dd` always. TOTAL therefore wins only when
`0.88·A > 0.96·F`, i.e. `A > 1.0909·F`, **and** the mark has not yet fallen 4% below funding. Once
it has, the daily switch takes it — see the matrix in claim 1, where a book 50% above funding at its
peak and 36% below that peak still reports `DAILY_DRAWDOWN_LIMIT_BREACHED`.

#### The author's simulation was not reproduced, and should not be trusted as evidence

The commit reports:

```
OLD (both peaks = all-time)  halted 4000/4000 | median session  18 | all DAILY
NEW (daily = session open)   halted 3032/4000 | median session 106 | all TOTAL
```

The label `NEW (daily = session open)` is the premise, asserted rather than measured. The runner does
not pass the session open; it passes `ledger_funding()`. Every row of that table is therefore a
simulation of code that does not exist. The "all TOTAL" column is directly contradicted by the
thirteen-session end-to-end run in claim 5, in which the reason is `DAILY`.

### Claim 3 — `clear_paper_halt.py` cannot lose or corrupt the book

**PROVEN for the tool itself. DISPROVEN for the recovery it is part of** — the state it writes is
one the session accepts, but the pilot it restores is not the pilot that halted.

#### Nine direct attacks, all handled (`scratchpad/probes/p4_clear_halt.py`)

| # | Attack | Result |
|---|---|---|
| T1 | missing file | exit 1, "There is nothing to clear." |
| T2 | `--state-path` is a **directory** | exit 1, same message — misleading but harmless |
| T3 | file is `<html>429 Too Many Requests</html>` | exit 2, "REFUSED: ... is not valid JSON", tells you not to delete it |
| T4 | hand-edited `risk_halted` (what the old message told operators to do) | exit 2, "does not match its own hash" |
| T5 | halted book, no flag | exit 3, prints the whole book, **file byte-identical afterwards** |
| T6 | clear it | exit 0; every field compared below |
| T7 | run twice | exit 0, "Not halted. Nothing to do." — idempotent |
| T8 | not-halted portfolio **with** the confirm flag | exit 0, **file byte-identical** — will not rewrite for nothing |
| T9 | on-disk holding with `quantity = 0`, hash recomputed to match | exit 2, refused by the dataclass invariant |

T6, every field of a two-holding book with realized P&L, fees, a peak and a hold clock:

```
cash                 before=Decimal('62195.95')          after=Decimal('62195.95')
realized_pnl         before=Decimal('-3311.07')          after=Decimal('-3311.07')
total_fees           before=Decimal('1086.41')           after=Decimal('1086.41')
last_rebalance_on    before=date(2026, 9, 14)            after=date(2026, 9, 14)
sessions_completed   before=11                           after=11
sessions_held        before=1                            after=1
peak_equity          before=Decimal('1000000.00')        after=Decimal('1000000.00')
risk_halted          before=True                         after=False
halted_on            before=date(2026, 9, 14)            after=None
halt_reason          before='DAILY_DRAWDOWN_LIMIT...'    after=''
holding INFY  before=PortfolioHolding('INFY', 130, Decimal('1121.37'), date(2026,8,31), Decimal('24.80'))
              after =PortfolioHolding('INFY', 130, Decimal('1121.37'), date(2026,8,31), Decimal('24.80'))
holding TCS   before=PortfolioHolding('TCS',   41, Decimal('2272.55'), date(2026,8,31), Decimal('20.51'))
              after =PortfolioHolding('TCS',   41, Decimal('2272.55'), date(2026,8,31), Decimal('20.51'))
```

Nothing is dropped, nothing is rounded, the hash is valid on reload. **The tool does what it says.**
Round 3's P1-2 is closed as far as the tool's own contract goes.

#### And the state it writes IS accepted by the session — proven end-to-end

Taking the real halted state left by the thirteen-session run in claim 5, clearing it with the real
tool, then running the next session:

```
$ .venv/Scripts/python.exe scripts/clear_paper_halt.py --state-path <scratch>/portfolio_state.json --i-have-reviewed-the-book
Halt cleared. The book above is unchanged and the next session will resume from it.

Portfolio: cash Rs 62195.95, 10 holding(s), session 12, held 1 of 10 sessions -> HOLDING
[after-clear session] reconciled=True fills=0 rejected=0 equity=938447.46
[state] hold=10 sc=12 sh=2 HALTED=False reason=''
```

---

#### P1-3 (Blocker) — a rebalance in which every order was refused is persisted as a rebalance that happened

```
FINDING   run_paper_pilot_session.py:1232 passes rebalanced=rebalancing -- the INTENT -- to
          state_from_ledger, which writes last_rebalance_on = session_date and resets
          sessions_held to 1 (paper_portfolio.py:375, 388). Nothing checks whether an order filled.
FAMILY    State machine / data integrity
REPRO     scratchpad/probes/drive_sessions2.py --sessions 13 --fresh --drift-pct -0.6
          Session 11 is the rebalance. The kill switch fires on its first order:
            [session 11] reconciled=True disc=0.00 fills=0 rejected=240 equity=943735.66
            [state] cash=62195.95 hold=10 sc=11 sh=1 peak=1000000.00 HALTED=True
                    last_rebal=2026-09-14
          Zero fills. 240 rejections. Ten stale holdings. The state says the portfolio rebalanced
          on 2026-09-14 and has held for one session.
OBSERVED  After clearing the halt, the very next session reports
            "Portfolio: cash Rs 62195.95, 10 holding(s), session 12, held 1 of 10 sessions
             -> HOLDING"
          and exits SUCCESS. The rebalance clock was reset by a rebalance that never occurred, so
          the pre-halt book -- the exact positions the model had just decided to exit -- is held
          for another nine sessions, and the selection computed on 2026-09-14 is discarded
          unrecorded.
EXPECTED  rebalanced reflects whether the book actually changed. A refused rebalance leaves
          last_rebalance_on and sessions_held alone, so the next session retries.
BLAST     Every rebalance session whose orders are refused for any reason -- kill switch,
          INSUFFICIENT_CASH, SPREAD_TOO_WIDE, PORTFOLIO_VALUATION_UNAVAILABLE,
          POSITION_WEIGHT_LIMIT_EXCEEDED. The persisted, hash-protected record states something
          that did not happen, and the operator's recovery hands back a pilot that looks healthy
          (green sessions, no halt) while holding a book the strategy has already rejected.
SEVERITY  P1 Critical (Major, escalated one level: silent in both the logs and the reports)
```

This is the composition the brief predicted: `clear_paper_halt.py` is correct, and it hands the
operator back a portfolio whose state machine was already falsified by the session it is recovering
from. Neither commit touched line 1232.

---

#### P2-2 — `clear_paper_halt.py` reports "Not halted. Nothing to do." for a book that is halting right now

```
FINDING   The halt is persisted only at session end (run_paper_pilot_session.py:1244). The tool
          reads the file.
FAMILY    Concurrency and ordering
REPRO     T8 above: a not-halted file with the confirm flag exits 0, "Not halted. Nothing to do.",
          file byte-identical. In the claim-5 run the kill switch fires at the first order of
          session 11 (09:15) and risk_halted=True is not written until 15:30.
OBSERVED  An operator who reads the kill-switch rejections in the live log at 09:20 and runs the
          documented recovery tool is told there is nothing to clear, exit 0. Six hours later the
          session persists the halt anyway and every later session exits 8.
EXPECTED  The tool distinguishes "not halted" from "cannot tell -- a session is running". There is
          no lock, no PID check and no session-in-progress marker anywhere; logs/paper_runs/ holds
          a stale runner.pid from 2026-08-26 that nothing reads.
BLAST     The one human in the loop, at exactly the moment the tool exists for.
SEVERITY  P2 Major
```

---

#### P3-1 — one fixed staging filename per state path; concurrent writers crash rather than corrupt

```
FINDING   save_portfolio (paper_portfolio.py:262-264) stages at a deterministic
          portfolio_state.json.staging shared by every writer, and write_text is not atomic.
FAMILY    Concurrency and ordering
REPRO     scratchpad/probes/p5_staging_race.py -- two writer threads (400-holding and 1-holding
          books) and two readers against one path for 6 seconds.
OBSERVED  staging path used by both writers: race.json.staging
          reads: {'json': 0, 'hash': 0, 'other': 0, 'ok': 2112}
          final file loads OK, holdings = 400
          ... but both writers died with
          PermissionError: [WinError 32] The process cannot access the file because it is being
          used by another process: '...race.json.staging' -> '...race.json'
          PermissionError: [WinError 5] Access is denied
EXPECTED  A per-writer temp name (pid/uuid), or a lock.
BLAST     No corruption on Windows -- NTFS sharing turns the race into a crash and 2112 reads were
          clean. But save_portfolio raises out of run_paper_pilot_session.py:1244, which sits
          OUTSIDE the loop's try/except and BEFORE the report writes at :1352, so a collision
          discards the whole session: no state update, no JSON, no markdown, no COMPLETED status.
          On a POSIX filesystem os.replace would not fail and the publish could be torn.
SEVERITY  P3 Minor on the reference Windows machine; the loss-of-session consequence is the part
          worth fixing.
```

Also noted, not defects: `--state-path` pointing at a directory reports "There is nothing to clear"
(T2) rather than naming the real problem; and the verification at the end of `main()` compares only
`len(holdings)` and `cash` against the object it just wrote, so it could not detect a
`save_portfolio` that dropped `realized_pnl`. T6 shows nothing is in fact dropped.

### Claim 4 — the two replaced tests are worth something

**PROVEN, with a caveat on the detector's precision, and one large hole neither test covers.**

#### `test_reconciliation_can_actually_report_failure` — kills the mutant, and it is the only one that does

Mutation applied through a `sitecustomize.py` on `PYTHONPATH` so no repository file was written:
`src/quant_system/execution/paper_pilot.py:888` `reconciled = len(errors) == 0` becomes
`reconciled = True`.

```
$ QS_MUTATE=recon PYTHONPATH=<scratch>/mut .venv/Scripts/python.exe -m pytest -q
[MUTANT] paper_pilot.end_session always reports reconciled=True
FAILED tests/test_paper_pilot_carried_session.py::test_reconciliation_can_actually_report_failure
============ 1 failed, 1172 passed, 1 warning in 91.91s (0:01:31) =============
```

Round 3's P2-3 said forcing `reconciled=True` left all 1,166 tests passing. It is now caught. It is
caught by **exactly one test out of 1,173** — the verdict has a single point of coverage, which is
worth knowing but is a real improvement over none.

#### `test_the_runner_feeds_the_peak_from_marked_equity_not_the_governor_alone` — kills the revert, and four other mutants survive

The detector reads the runner's source, so mutations were applied to a string copy and the test's
own assertions replayed byte-for-byte (`scratchpad/probes/p6_mutate_tests.py`):

```
  TEST PASSES (mutant survives)  <- unmodified (current HEAD)
  TEST FAILS  (mutant killed)    <- REVERT to the pre-repair form
      rejected 'governor.all_time_peak_equity'
  TEST FAILS  (mutant killed)    <- revert to the cost figure
      rejected 'portfolio.ledger_funding()'
  TEST FAILS  (mutant killed)    <- drop the argument entirely
      no session_peak_equity keyword
  TEST PASSES (mutant survives)  <- MIN instead of MAX (inverts the rule)
  TEST PASSES (mutant survives)  <- drop the governor term
  TEST PASSES (mutant survives)  <- zero, guarded by a dead reference
  TEST PASSES (mutant survives)  <- a same-named local that is a cost figure
```

It kills the exact revert it was written for, and it kills the two obvious reverts. It cannot tell
`max` from `min`, and
`session_peak_equity=(reconciliation.total_equity and Decimal('0.00'))` — which sets the high-water
mark to zero — passes. The assertion is `"total_equity" in ast.unparse(expression)`, a substring
test on rendered source, so it verifies that a name appears, not what is done with it. It also
correctly refuses to go blind: renaming or qualifying the call makes `calls` empty and the first
assertion fires.

Verdict: **worth something, not worth much.** It is a tripwire on one identifier, not a check of the
expression. That is better than the `max()`-asserts-`max()` test it replaces.

---

#### P2-3 — nothing tests what the runner passes as `initial_equity`, which is the argument `46c7bb67` changed and got wrong

```
FINDING   The commit added an AST detector for session_peak_equity and none for initial_equity.
FAMILY    Assumption archaeology
REPRO     grep -rn "initial_equity|opening_equity|ledger_funding" tests/
          Only tests/test_risk_governor_session_peaks.py mentions initial_equity, and every one of
          its six tests CONSTRUCTS the governor itself with a hand-chosen `opening`. Nothing
          imports or exercises run_paper_session, and no source-level detector covers
          run_paper_pilot_session.py:806-811.
OBSERVED  All six new governor tests pass a correct marked opening equity, so they prove the
          governor is right about an argument the caller never supplies. The suite is 1173 green
          while the runner seeds the daily peak from a cost figure -- claim 5, P1-1.
EXPECTED  The same detector pattern applied to the governor construction, or a test that drives
          run_paper_session with a carried, underwater book.
BLAST     This is the mechanism by which the round-3 P1 survived its own repair and a full green
          suite. It will do so again for the next repair unless the caller is covered.
SEVERITY  P2 Major
```

### Claim 5 — tomorrow's session completes correctly

**DISPROVEN as stated.** Session 1 (2026-08-31) does complete and persists a valid v3 file. The
first thing that goes wrong is **session 11**, the first rebalance, and it is round 3's P1-1
reproducing verbatim at `46c7bb67`.

#### Setup verified against the real machine

```
$ powershell Get-ScheduledTaskInfo -TaskName 'QuantOS Mizan Paper Session'
LastRunTime           : 8/29/2026 10:05:39 PM
LastTaskResult        : 0
NextRunTime           : 8/31/2026 9:00:00 AM
NumberOfMissedRuns    : 0

$ powershell (Get-ScheduledTask ...).Triggers / .Actions
Enabled       : True
StartBoundary : 2026-08-29T09:00:00
DaysOfWeek    : 62          # Mon-Fri
Execute       : D:\quant_system\scripts\run_scheduled_paper_session.cmd
```

Preconditions, each checked rather than assumed:

| Gate | Value | Passes |
|---|---|---|
| `require_trading_day(2026-08-31)` | Monday; `covers_years=['2026']`; nearest holidays 2026-08-15, 2026-09-14 | yes |
| `logs/paper_runs/portfolio_state.json` | **does not exist** — first run | `load_portfolio` returns `None` |
| newest cached bar | `2026-08-27`, 499 datasets in `nifty500-refresh-20230828-20260827` | staleness 4 == limit 4; passes even if the refresh fetches nothing |
| live quote feed | reachable; 499/500 real on the first fetch, 500/500 on the second | yes |

#### Session 1 completes. Proven by running it.

Driven through the real `run_paper_session` with `PORTFOLIO_STATE_PATH` and `output_dir` redirected
into the scratchpad. Nothing under `logs/paper_runs/` or `data/evidence/` was written.
Probe: `scratchpad/probes/drive_sessions.py`.

```
### SESSION 1  date=2026-08-31  price multiplier=1.000000
[session 1] reconciled=True discrepancy=0.00 fills=10 equity=998416.95
[state] cash=62195.95 holdings=10 sessions_completed=1 sessions_held=1 peak=1000000.00
        halted=False reason='' realized=0.00 fees=1086.41 last_rebal=2026-08-31
### SESSION 2  date=2026-09-01  price multiplier=1.000000
[session 2] reconciled=True discrepancy=0.00 fills=0 equity=998416.95
[state] cash=62195.95 holdings=10 sessions_completed=2 sessions_held=2 peak=1000000.00
        halted=False reason='' realized=0.00 fees=1086.41 last_rebal=2026-08-31
```

It reconciles, persists a schema-v3 file, advances the hold clock, accumulates fees, sets the peak.
That much of the claim holds.

---

#### P1-1 (Blocker) — the "daily" limit still fires on a pure multi-session decline, on the first order, which is the exit. Round 3's P1-1 is NOT closed.

```
FINDING   `initial_equity` is seeded from `portfolio.ledger_funding()`, a COST figure invariant to
          market price, not "equity at this session's open". The 4% daily limit therefore still
          measures cumulative unrealized loss since inception.
FAMILY    Assumption archaeology / state machine / money
REPRO     scratchpad/probes/drive_sessions2.py --sessions 13 --fresh --drift-pct -0.6
          Thirteen real sessions through the real runner. Prices are CONSTANT within every session
          (sequence mode), so intraday movement is exactly zero on every one of them.
OBSERVED  A 5.63% decline accumulated over ten sessions fires DAILY_DRAWDOWN_LIMIT_BREACHED on the
          first order of session 11. That order is the exit. All ten exits and all ten entries are
          refused, the halt is persisted sticky, every later session exits 8, and the losing book
          is held with nothing able to sell it.
EXPECTED  A multi-session decline is measured by the 12% total limit and reports
          TOTAL_MAX_DRAWDOWN_BREACHED. The 4% daily limit fires only on an intraday decline.
BLAST     The scheduled paper pilot, from its first rebalance onward. Every session after it is
          refused until a human runs clear_paper_halt.py -- and clearing it puts the book straight
          back into the same condition, because the trigger is the unrealized loss, not the day.
SEVERITY  P1 Critical
```

```
### SESSION 10 date=2026-09-11 mult=0.947278
[session 10] reconciled=True disc=0.00 fills=0 rejected=0 equity=949057.94
[state] cash=62195.95 hold=10 sc=10 sh=10 peak=1000000.00 HALTED=False

### SESSION 11 date=2026-09-14 mult=0.941594          <-- first rebalance
[session 11] reconciled=True disc=0.00 fills=0 rejected=240 equity=943735.66
[state] cash=62195.95 hold=10 sc=11 sh=1 peak=1000000.00 HALTED=True
        reason='DAILY_DRAWDOWN_LIMIT_BREACHED: 5.63% >= 4.00%' realized=0.00 fees=1086.41

  [EXIT PROPOSAL SUBMITTED] ..._BHARTIARTL_SELL SELL 57 BHARTIARTL (Risk: REJECTED)
  [EXIT PROPOSAL SUBMITTED] ..._DRREDDY_SELL    SELL 14 DRREDDY    (Risk: REJECTED)
  ... all ten exits rejected ...
  [PROPOSAL SUBMITTED] ..._ONGC_BUY BUY 269 ONGC (Risk: REJECTED, Reason: KILL_SWITCH_ACTIVE)
  ... all ten entries rejected ...

### SESSION 12 date=2026-09-15   [session 12] SystemExit(8)
### SESSION 13 date=2026-09-16   [session 13] SystemExit(8)
```

This is the exact sentence `46c7bb67`'s own commit message uses to describe the defect it claims to
have fixed: "a session that opened 4% below its all-time high and never moved intraday halted the
book on its first order -- which is the exit, so the losing position was then held with nothing able
to sell it."

**Root cause, `scripts/run_paper_pilot_session.py:806-811`:**

```python
opening_equity = portfolio.ledger_funding()
governor = PreTradeRiskGovernor(
    limits=risk_limits,
    initial_equity=opening_equity,
    all_time_peak_equity=max(portfolio.peak_equity, opening_equity),
)
```

`ledger_funding()` (`src/quant_system/execution/paper_portfolio.py:157-168`) is
`cash + holdings_value_at_cost + carried_entry_fees`. It contains **no market price**. Across the
run above it is the constant `1000000.00` on every one of the thirteen sessions while marked equity
falls from `998416.95` to `943735.66`. It equals funded capital plus cumulative realized P&L,
forever.

So `daily_dd = (funding - marked) / funding` is the **total unrealized drawdown from cost**, checked
against `max_daily_drawdown_pct = 0.04`. `src/quant_system/risk/governor.py:29-30` documents
`initial_equity` as "Equity at **this session's open**". The caller does not pass that quantity, and
no such quantity is computed anywhere in the runner.

Unit-level confirmation (`scratchpad/probes/p1_cost_vs_mark.py`), price flat all day:

```
--- B  book 5% underwater vs cost, price FLAT today
    ledger_funding (COST) = 1000000.00   daily peak seeded here
    marked equity  (MKT)  = 952500.00
    move vs cost          = -4.75%
    EXIT order approved   = False   reason=DAILY_DRAWDOWN_LIMIT_BREACHED: 4.75% >= 4.00%
    governor killed       = True
--- C  book 4.3% underwater vs cost, price FLAT today
    move vs cost          = -4.08%
    EXIT order approved   = False   reason=DAILY_DRAWDOWN_LIMIT_BREACHED: 4.08% >= 4.00%
    governor killed       = True
```

**Why the commit's own simulation missed it.** The message reports `NEW (daily = session open)
halted 3032/4000 | median session 106 | all TOTAL`. That simulation *asserted* the premise —
`daily = session open` — rather than measuring what the runner passes. The runner passes
`ledger_funding()`, which is not the session open. The premise is the defect.

---

#### P1-2 (Blocker) — the session that permanently halts the pilot exits 0 and prints `[PAPER PILOT SUCCESS]`

```
FINDING   The halting session reconciles cleanly, so main() returns 0 and the banner says SUCCESS.
FAMILY    Operability / failure injection (silent failure)
REPRO     Session 11 above: reconciled=True disc=0.00 rejected=240 fills=0.
          main() (scripts/run_paper_pilot_session.py:1505-1525) branches only on
          res["reconciliation"]["reconciled"]. governor.is_killed, orders_rejected and risk_halted
          are never consulted in the exit path or the report header.
OBSERVED  Exit code 0. stdout "[PAPER PILOT SUCCESS] Session paper_ses_20260914_091500_IST.
          Reconciliation: PASS (0.00 paisa discrepancy)". The JSON and markdown reports carry
          "reconciled": true and "Reconciliation Status: PASS". Nothing in the exit code, the
          banner or the report headline says the kill switch fired and the pilot is now dead.
EXPECTED  A session that trips the kill switch is not a success. Non-zero exit, and the halt named
          in the report header.
BLAST     Unattended schedule. The operator's only signal is a green exit; the pilot is finished.
          Later weekday runs exit 8 into a log file nobody watches -- and per round 3's P2-1 no
          report and no live_paper_status.json update is written on those, so the dashboard serves
          session 11's COMPLETED indefinitely.
SEVERITY  P1 Critical (Major, escalated one level for silence)
```

Compounding: `scripts/run_scheduled_paper_session.cmd` ends with `echo` then `endlocal` and never
propagates `%ERRORLEVEL%`, so **Task Scheduler records `LastTaskResult: 0` whatever the session
did** — confirmed by the real task info above, whose 8/29 22:05 run fell on a Saturday and must
therefore have returned 2 from `require_trading_day`.

---

#### P2-1 — an unreachable quote falls back to a hardcoded Rs 1000.00 that is labelled and logged as a real exchange price

```
FINDING   fetch_live_nse_quotes substitutes DEFAULT_NIFTY_PRICES.get(s, Decimal("1000.00")) for any
          symbol whose fetch fails, tags it source="REAL_NSE_ESTIMATE", and the runner logs it as
          "[REAL NSE FEED]".
FAMILY    Failure injection / data integrity
REPRO     R.fetch_live_nse_quotes(resolve_universe('NIFTY500')), twice, tonight:
            attempt 1: 500 symbols, 1 fell back to REAL_NSE_ESTIMATE, 1 of those priced at the
                       hardcoded Rs 1000.00, 45.6s   sample fallbacks: ['LENSKART']
            attempt 2: 500 symbols, 0 fell back, 72.6s
          DEFAULT_NIFTY_PRICES covers 49 of the 500 NIFTY500 names
          (run_paper_pilot_session.py:104-155), so 451 names have no entry and get flat Rs 1000.00.
OBSERVED  A real fetch failure occurred on the first attempt tonight. The fabricated price drives
          qty = int(target_alloc / price) (:1040), the fill price, the position mark, and therefore
          the governor's equity. Line :591 prints it as "[REAL NSE FEED] LENSKART : Rs 1000.00".
EXPECTED  A symbol with no quote is excluded from trading, or the session refuses. A fabricated
          constant must never be labelled REAL.
BLAST     One name in ~500 per fetch on tonight's measurement. Entries are placed on the FIRST
          fetch of the session, so a first-fetch failure on a selected name is traded at Rs 1000.00.
          Paper only, but it corrupts the session evidence record silently.
SEVERITY  P2 Major (pre-existing; not introduced by 46c7bb67; not reported by rounds 1-3)
```

### Claim 6 — the first-run and second-run boundary

**PROVEN for the four named quantities. One new defect found in what the boundary makes the session
*report*.**

Twelve consecutive sessions through the real runner, flat market, real rebalance at session 11
(`scratchpad/probes/drive_sessions2.py --sessions 12 --fresh --drift-pct 0`):

```
[session  1] fills=10 rejected= 0 equity=998416.95  state: sh= 1 peak=1000000.00 realized=0.00     fees=1086.41
[session  2] fills= 0 rejected= 0 equity=998416.95  state: sh= 2 peak=1000000.00 realized=0.00     fees=1086.41
...
[session 10] fills= 0 rejected= 0 equity=998416.95  state: sh=10 peak=1000000.00 realized=0.00     fees=1086.41
[session 11] fills=20 rejected=10 equity=995223.48  state: sh= 1 peak=1000000.00 realized=-3128.65 fees=3246.92
[session 12] fills= 0 rejected= 0 equity=995223.48  state: sh= 2 peak=1000000.00 realized=-3128.65 fees=3246.92
```

| Quantity | Across the boundary | Verdict |
|---|---|---|
| **Hold clock** | 1,2,...,10 then rebalance on session 11 — held exactly 10 | correct |
| **Entry fees** | persisted state: `cash 62195.95 + cost basis 936717.64 + entry fees 1086.41 = 1000000.00` exactly | correct, no leak |
| **Peak** | `1000000.00` held across all twelve; ratchets on marked close on a hold session | correct |
| **Halt** | sticky — the declining run's sessions 12 and 13 both `SystemExit(8)` | correct |
| **Realized P&L** | `-3128.65` on the round trip in a **flat** market: gross spread/slippage ≈ -993.62 plus the carried entry fee 1086.41 plus the exit fee. Both legs netted | correct (round 2's finding holds) |

---

#### P2-4 — the session report's capital table does not balance, by exactly the carried entry fees

```
FINDING   Total Equity != Initial Capital + Total Net P&L on any session holding a position. The
          gap is exactly the entry fees attributable to the open lots.
FAMILY    Money and counting / data integrity
REPRO     Session 11's own report, logs .../paper_session_2026-09-14_*.json:
            capital     : initial_cash 1000000.00  final_cash 64057.48  total_equity 995223.48
            performance : realized -3128.65  unrealized -537.41  total_net_pnl -3666.06
            BALANCE CHECK  initial_cash + net_pnl = 996333.94  vs total_equity = 995223.48
                           GAP = 1110.46   (= the ten new positions' entry fees)
          And across the whole declining run, every session's reported net P&L is short by exactly
          the carried entry fee total, 1086.41:
            date          init_cap        equity     net_pnl     ret%
            2026-08-31  1000000.00     998416.95     -496.64  -0.0497     true P&L -1583.05
            2026-09-11  1000000.00     949057.94   -49855.65  -4.9856     true P&L -50942.06
            2026-09-15  1000000.00     938447.19   -60466.40  -6.0466     true P&L -61552.81
OBSERVED  `reconciliation.initial_cash` is `ledger_funding()` = cash + cost basis + entry fees, so
          the fees are counted as capital in; `total_net_pnl` is realized + unrealized, and
          unrealized is market minus cost basis, so the fees are never counted as a cost out. The
          markdown table (:1373-1384) prints all three side by side.
EXPECTED  The three numbers reconcile, or the fee line is shown as the reconciling item.
BLAST     Every session report the pilot has ever written that carried a position. The direction is
          always flattering: the loss is understated. Magnitude is bounded by the open positions'
          entry fees, about 0.11% of capital here, and it is silent -- reconciliation still passes
          with 0.00 paisa discrepancy because the ledger's own identity is intact.
SEVERITY  P2 Major (Minor, escalated one level for silence -- it is a wrong money figure in an
          immutable evidence artifact, with no error and a passing reconciliation beside it)
```

Note also that `return_pct` (`:1253`) divides by the CLI nominal `initial_cash`, not by
`reconciliation.initial_cash`. They coincide only while cumulative realized P&L is zero; after any
realized gain or loss the denominator is the wrong base, and the numerator already mixes **this
session's** realized P&L with **since-entry** unrealized P&L.

---

#### P3-2 — the comment claiming exit proceeds fund the same step's entries is false

```
FINDING   run_paper_pilot_session.py:1026-1029: "Exits above run first, in the same step, so the
          proceeds are available to fund these buys". They are not. submit_proposal only stages an
          order; fills happen in process_quote, which for step N already ran at :948 before the
          exits were proposed at :1003.
FAMILY    Assumption archaeology
REPRO     Session 11 above: proposals_submitted=30, orders_filled=20, orders_rejected=10.
          Ten sells + ten step-1 buys + ten step-2 buys = 30. The step-1 buys are sized against
          engine.cash = 62195.95 (carried cash only) and refused: min_cash_required =
          998416.95 x 0.05 = 49920.85, available_for_trade = 12275.10, order_value ~59086.
          The step-2 buys, after the sales settle, use the full 95000 allocation -- ONGC ends at
          407 shares = int(95000/233), not the 253 the step-1 order asked for.
OBSERVED  The rebalance self-heals one interval later, so the book ends correct. Ten spurious
          rejections are written into the evidence record, and the entries execute one interval
          after the exits at whatever price then prevails, not "in the same step".
EXPECTED  Either the comment is corrected, or the entry loop runs after the exit fills.
BLAST     Every rebalance session. Harmless to the book here; the risk is a rebalance triggered in
          the final interval before 15:30, which would sell without buying.
SEVERITY  P3 Minor
```

### Claim 7 — regression against rounds 2 and 3

**PROVEN at `d6f421e3`.** Everything rounds 2 and 3 established still holds, and the two repairs in
`d6f421e3` did not disturb the money path.

#### Gates at the new HEAD

```
$ .venv/Scripts/python.exe -m ruff check .
All checks passed!
$ .venv/Scripts/python.exe -m mypy src
Success: no issues found in 141 source files
$ .venv/Scripts/python.exe -m pytest -q
1176 passed, 1 warning in 83.95s (0:01:23)
```

1176 = 1173 at `46c7bb67` plus the three new detectors. No test was lost or weakened.

#### The money path, twelve real sessions, flat market, real rebalance at session 11

`scratchpad/probes/drive_sessions3.py --sessions 12 --fresh --drift-pct 0` at `d6f421e3`, against
the identical run at `46c7bb67`:

```
                                 46c7bb67                    d6f421e3
session 10   fills= 0 rejected= 0 equity=998416.95   ==   fills= 0 rejected= 0 equity=998416.95
session 11   fills=20 rejected=10 equity=995223.48   ==   fills=20 rejected=10 equity=995223.48
             state: sh=1 realized=-3128.65 fees=3246.92 cash=64057.48   (identical)
session 12   fills= 0 rejected= 0 equity=995223.48   ==   fills= 0 rejected= 0 equity=995223.48
             state: sh=2 realized=-3128.65 fees=3246.92 cash=64057.48   (identical)
```

Byte-identical on every number. The `d6f421e3` change to the risk baseline is inert when opening
marks equal cost, which is the correct null result.

| Round 2 / 3 finding | Status at `d6f421e3` | Evidence |
|---|---|---|
| **Carry-forward P&L nets both legs** | holds | `realized=-3128.65` on a round trip in a **flat** market: gross spread+slippage ≈ -993.62, plus the carried entry fee 1086.41, plus the exit fee. The entry leg is charged. |
| **Cash exact** | holds | persisted `cash 62195.95 + cost basis 936717.64 + entry fees 1086.41 = 1000000.00` exactly, every session |
| **Hold exactly 10** | holds | `sh` runs 1,2,...,10, rebalance on session 11, then 1,2 |
| **Round-2 P1-A** (carried session fails reconciliation) | closed | all twelve sessions `reconciled=True discrepancy=0.00`, including the two that carry ten positions across the boundary |
| **Round-2 P1-B** (halt not persisted) | closed | `state_from_ledger` stickiness: after a quiet session `risk_halted=True halted_on=2026-08-31 reason='TOTAL_MAX_DRAWDOWN_BREACHED: 14%'` |
| **`INITIALIZED` guard** | holds | `carry_in_positions` after `start_session` raises `RuntimeError: positions must be carried in before the session opens; the reconciliation baseline cannot move once trading has started (status is ACTIVE)` |
| **v2 files refused** | holds | and so is every other declaration: v1, v2, v4 and a foreign `schema_id` all refused with the expected-vs-declared message |
| **Round-3 P1-2** (halt recovery impossible) | closed | claim 3 |
| **Round-3 P1-1** (daily rule on a multi-session decline) | **closed at `d6f421e3`**, was still open at `46c7bb67` | claim 8 |
| Known-open: `reset_session_peak` has no caller | unchanged | `git grep` finds only its own definition and two docstrings |

### Claim 8 — anything `46c7bb67` / `d6f421e3` introduced, overstated, or broke

**The two Blockers are genuinely repaired. Three new defects, one still-open Blocker, and one false
claim in the `d6f421e3` message.**

#### The claim-5 reproduction, re-run against `d6f421e3`. The halt is gone and it moved to the right place.

`scratchpad/probes/drive_sessions2.py --sessions 13 --fresh --drift-pct -0.6`, identical to the run
that halted at session 11 under `46c7bb67`:

```
                        46c7bb67                              d6f421e3
session 11   fills= 0 rejected=240 HALTED=True      fills=19 rejected=20 HALTED=False
             DAILY_DRAWDOWN_LIMIT_BREACHED 5.63%    exits fill, realized -57723.33 booked
session 12   SystemExit(8)                          reconciled=True, holds normally
session 13   SystemExit(8)                          reconciled=True, holds normally
```

Pushed deeper (`--sessions 23 --drift-pct -0.8`) to find where it now lands:

```
session 11  fills=19 rejected=20  equity=923222.32   HALTED=False   <- rebalance proceeds
session 12  ... session 20        equity=864300.24   HALTED=False   <- holds
session 21  fills= 0 rejected=228 equity=858012.97   HALTED=True
            reason='TOTAL_MAX_DRAWDOWN_BREACHED: 14.20% >= 12.00%'
session 22  SystemExit(8)
session 23  SystemExit(8)
```

**The right switch, at the right depth, ten sessions later.** Round 3's P1-1 and my claim-5 P1-1 are
both closed. `TOTAL_MAX_DRAWDOWN_BREACHED` is not merely reachable in theory — it is what a real
multi-session decline now produces end-to-end.

`main()`'s branching, exercised directly (`scratchpad/probes/p11_exit_code.py`):

```
--- clean session                    exit 0   [PAPER PILOT SUCCESS]
--- RISK HALT (reconciles cleanly)   exit 9   [PAPER PILOT HALTED BY RISK KILL SWITCH]
                                             RISK HALT: TOTAL_MAX_DRAWDOWN_BREACHED: 14.20% >= 12.00%
                                             Orders refused this session: 228
                                             Every later session is refused until this is reviewed and cleared:
                                                 python scripts/clear_paper_halt.py --i-have-reviewed-the-book
--- reconciliation failure           exit 7   [PAPER PILOT RECONCILIATION FAILED]
```

Claim-5 P1-2 is closed at the exit code and the console. Not everywhere — see P2-6.

---

#### P1-3 is still open at `d6f421e3`, and the commit message's "still open" list omits it

The deep-decline run's session 21: `fills=0 rejected=228`, book unchanged at nine holdings, and the
state records `sh=1` with `last_rebalance_on` advanced to 2026-09-28. A rebalance in which every
order was refused is still persisted as a rebalance that happened (claim 3, P1-3;
`run_paper_pilot_session.py:1232`).

The `d6f421e3` message lists what remains open as "its P2s stand" and names three P2s. P1-3 is a
Blocker, it was at line 245 of the report the author read, and it is not mentioned.

---

#### P2-5 (new, created by `d6f421e3`) — the risk baseline is marked to market, the position sizing is not, so a drawn-down book silently drops a selected name

```
FINDING   d6f421e3 changed the governor seed from ledger_funding() to marked opening equity but
          left run_paper_pilot_session.py:763 `deployable = portfolio.ledger_funding()`. Risk now
          measures market; sizing still measures cost. Under 46c7bb67 both were cost -- wrong, but
          consistent. They now disagree by the whole unrealized loss.
FAMILY    Assumption archaeology / money and counting
REPRO     scratchpad/probes/drive_sessions2.py --sessions 11 --fresh --drift-pct -0.6
          Session 11, book marked at 943735.66 after a 5.6% drift:
            Sizing: equal-weight, Rs 95000.00 per name across 10 picks (5% cash buffer held back)
            Risk baseline: opening equity Rs 943735.66 (marked), carried peak Rs 1000000.00
          95000 x 10 = 950000 targeted against a 943735.66 book whose 5% buffer leaves ~896548
          spendable. Nine of the ten picks fund; the tenth does not.
OBSERVED  MISSING FROM THE SELECTION: ['TMPV']
          cash 92937.17, cost basis 848328.41 -> 9.87% in cash against a declared 5% buffer.
          Repeated at -0.8% drift: hold=9, cash=78345.64 (8.4%).
          The executed book is not the decided book. The drop is reported only as one more
          INSUFFICIENT_CASH line among the ten expected step-1 rejections, so `orders_rejected: 20`
          is the only trace and it looks like the normal pattern.
EXPECTED  `deployable` is the same marked opening equity the governor is seeded with, so ten
          allocations fit inside the book they are drawn from.
BLAST     Every rebalance on a book that has drawn down -- which is the expected state of this
          strategy. It is the concentration defect the comment at :757-762 says equal-weight sizing
          was introduced to remove, reintroduced by the same cost-versus-mark confusion the commit
          fixed forty lines below.
SEVERITY  P2 Major (Minor, escalated one level: silent, and it changes which positions the pilot
          actually holds)
```

---

#### P2-6 (new, residual of the `d6f421e3` repair) — the halt reaches the exit code but not the two artifacts a human reads

```
FINDING   The `risk` block was added to the JSON payload and the console banner. The markdown
          report and live_paper_status.json were not changed.
FAMILY    Operability
REPRO     The halted session 21 from the deep-decline run:
            $ head -12 .../paper_session_2026-09-28_*.md
            - **Reconciliation Status**: **`PASS (0.00 paisa discrepancy)`**
            $ grep -ci "halt|kill" .../paper_session_2026-09-28_*.md
            0
            $ live_paper_status.json -> {'status': 'COMPLETED', ...}
          while the JSON payload correctly carries
            {"kill_switch_active": true,
             "halt_reason": "TOTAL_MAX_DRAWDOWN_BREACHED: 14.20% >= 12.00%",
             "orders_rejected": 228}
OBSERVED  The markdown evidence file for the session that permanently stopped the pilot says PASS
          and never uses the words halt or kill. The dashboard status field says COMPLETED. The
          truth is present only in the JSON and in a console banner that, on a scheduled run, is
          buried in a log file.
EXPECTED  The markdown header names the halt; the status file says HALTED.
BLAST     Anyone reading the session evidence rather than the exit code -- which is the artifact
          the repository treats as authoritative.
SEVERITY  P2 Major
```

Also noted: `main()` reads `res.get("risk", {})`, so a payload without a `risk` block reports
SUCCESS and exits 0. Verified — the "older shape" case in `p11_exit_code.py` exits 0. The guard is a
lookup with a permissive default, not a contract.

---

#### The unpriced-carried-name fallback: attacked, and the hypothesis is the wrong way round

The concern put to me was that a carried name losing its quote could understate the opening equity
and make the daily rule fire **early**. **It cannot, and the real effect is the opposite.**

`marked_opening_equity` falls back to `holding.average_cost`
(`run_paper_pilot_session.py:833`). The engine's `current_equity` falls back to
`p.average_price` (`paper_pilot.py:412`) — the same number, because the carry replay sets the
ledger's average price to the holding's average cost. `_price_cache` is populated only from
`base_market` symbols, so a name absent from `base_market` is absent from both sides. The error
therefore cancels exactly in the numerator `P - E` and survives only in the denominator.

End-to-end (`scratchpad/probes/p10_unpriced.py`): session 1 buys ten names; session 2 runs with
RELIANCE removed from the feed entirely while the market falls 10%.

```
No opening quote for 1 carried name(s); their cost basis is used in the risk baseline: RELIANCE
Risk baseline: opening equity Rs 914241.25 (marked), carried peak Rs 1000000.00

  carried book at cost      : 936717.64   (RELIANCE 94010.40, others 842707.24)
  TRUE equity at -10%       : 905241.83
  equity the risk rule sees : 914642.87   (RELIANCE marked at cost)
  understated loss          : 9401.04
  true total drawdown vs peak 1000000.00 : 9.48%
  measured total drawdown                : 8.54%
```

An unpriced name that has **fallen** inflates the denominator, so the measured drawdown is
**smaller** than the truth and the rule fires **late**. The bias is toward blindness, not toward a
spurious halt. Reported as P3-3 below rather than as a Blocker.

```
FINDING   A carried holding with no quote is marked at cost for the entire session -- in the risk
          baseline, in every current_equity, in get_portfolio_snapshot, in
          reconciliation.total_equity, and therefore in the persisted peak_equity and in the
          session report. Its loss is invisible to both drawdown rules.
FAMILY    Data integrity
REPRO     as above. The warning says the cost basis is used "in the risk baseline"; it is used for
          the whole session.
OBSERVED  9.48% true drawdown reported as 8.54% with one name of ten unquoted.
EXPECTED  Either the last known price is carried across sessions, or a carried name that cannot be
          valued refuses the session the way PORTFOLIO_VALUATION_UNAVAILABLE already refuses an
          order for exactly this reason (governor.py:379-392).
BLAST     Reachable whenever a held name leaves the resolved universe -- NSE rebalances the NIFTY
          indices on a published schedule, and the runner resolves its universe from the current
          authority CSV every session. Not reachable from a quote-fetch failure, because the
          fallback at :211-224 guarantees every universe symbol has an entry.
SEVERITY  P3 Minor (pre-existing for current_equity; d6f421e3 extends it to the baseline and, to
          its credit, is the first code to log it)
```

---

#### P3-4 (new) — in realtime mode the daily baseline is anchored ~2.5 minutes before the first drawdown check

```
FINDING   marked_opening_equity is computed from the base_market fetched at :549. In realtime mode
          the loop refetches at :915 and process_quote refills _price_cache before the first
          proposal, so the first daily_dd compares two different market snapshots.
FAMILY    Concurrency and ordering
REPRO     Measured on this machine, NIFTY500: fetch_live_nse_quotes(500 names) took 45.6s then
          72.6s; load_mizan_cross_section took 37.1s for 50 names over the same store scan. The
          sequence :549 fetch -> model load -> cross-section -> sizing -> :915 fetch is therefore
          roughly 2-3 minutes of market time, all of it inside 09:00-09:05 IST.
OBSERVED  A fall between the two snapshots is counted against the 4% daily limit as though it had
          happened after the session's own measurement began. A rise self-corrects, because
          update_peaks ratchets the daily peak up at the first order -- so the bias is one-sided.
EXPECTED  The baseline is taken from the same snapshot the first check uses, or the daily peak is
          re-seeded at the first order.
BLAST     Only bites when the book moves >4% in that window, which needs a gap-down open. Bounded
          and rare, but it is the same class of defect as P1-1 one layer along, and its consequence
          is the same: the exits are the first orders, so they are what gets refused.
SEVERITY  P3 Minor
```

---

#### The commit messages, claim by claim

`46c7bb67`:

| Claim | Verdict |
|---|---|
| "The 4% daily limit was measuring multi-session declines" | true of its parent, and **still true of itself** — the repair was incomplete and `d6f421e3` says so |
| "`reset_session_peak` has no caller anywhere in the repository" | **true** — `git grep` finds only its definition and two docstrings |
| "`TOTAL_MAX_DRAWDOWN_BREACHED` became unreachable" | true of its parent; made reachable only in a narrow band by `46c7bb67`, genuinely reachable at `d6f421e3` |
| Simulation "NEW (daily = session open) ... all TOTAL" | **not reproducible as a description of the shipped code** — the runner did not pass the session open. Every row simulated code that did not exist |
| "That also closes the third P1 [the peak ratchet]" | **true** in its own terms: once the ratchet feeds only the trailing rule, it no longer makes the daily halt likelier |
| "clear_paper_halt.py ... reloads to prove the write is readable and the book unchanged" | **true**; the reload checks only holdings count and cash, but claim 3 T6 shows every field is in fact preserved |
| "ruff clean; mypy clean on 141 files; 1173 tests passing" | **all three verified** |
| Residual: "the drawdown is still evaluated only inside `evaluate_order`, so a hold session never tests it" | **true and confirmed** — sessions 2-20 of the deep-decline run propose no orders and cannot halt at any depth |

`d6f421e3`:

| Claim | Verdict |
|---|---|
| "session 1 completes ... the failure it found arrives at session 11" | **true**, and correctly attributed |
| "The daily peak is now equity marked at the session open" | **true** |
| The three-line OLD/NEW table | **reproduced**, and independently confirmed end-to-end rather than in isolation |
| "A carried name with no opening quote falls back to its cost basis and is logged by name" | **true**; the log line understates the scope — the fallback governs the whole session, not just the baseline (P3-3) |
| "The payload now carries a `risk` block, the banner distinguishes a halt, and the exit code is 9" | **true** — exits 0/7/9 verified distinct |
| "Now `endlocal & exit /b %RC%`" | **true** |
| **"Three detectors added, all of which fail against this commit's parent."** | **FALSE.** One of the three passes against `46c7bb67`. See claim 9 |
| "Still open: ... its P2s stand" | **incomplete** — P1-3, a Blocker in the same report, is not listed |
| "ruff clean; mypy clean on 141 files; 1176 tests passing (was 1173)" | **all three verified** |

Round 2 found three false claims in this author's commit messages and they remain uncorrected. The
detector claim is a fourth, in the commit that responded to a report about exactly this pattern.

### Claim 9 — do the three new detectors actually fail against `46c7bb67`?

**DISPROVEN. One of the three passes against the commit it was written to catch.** The
`d6f421e3` message states "Three detectors added, all of which fail against this commit's parent."

Method: the `46c7bb67` sources were extracted with `git show` into the scratchpad and each
detector's assertions replayed byte-for-byte (`scratchpad/probes/p9_detectors.py`). No repository
file was modified.

```
D1 governor seeded from marked equity
   at d6f421e3 (HEAD)  : PASS   accepted initial_equity='marked_opening_equity'
   at 46c7bb67 (parent): PASS   accepted initial_equity='opening_equity'
                                <-- DETECTOR DOES NOT CATCH THE DEFECT IT NAMES

D2 a halt is reported as a halt
   at d6f421e3 (HEAD)  : PASS   all three assertions hold
   at 46c7bb67 (parent): FAIL   failed: banner distinguishes a halt; halting session exits 9

D3 wrapper propagates the exit code
   at d6f421e3 (HEAD)  : PASS   found 'exit /b %RC%'
   at 46c7bb67 (parent): FAIL   wrapper swallows the exit code
```

#### P2-7 — `test_the_governor_is_seeded_from_marked_equity_not_a_cost_figure` passes against `46c7bb67`

```
FINDING   The detector asserts "ledger_funding" not in ast.unparse(initial_equity). At 46c7bb67 the
          defect was written through a local:
              opening_equity = portfolio.ledger_funding()
              governor = PreTradeRiskGovernor(..., initial_equity=opening_equity, ...)
          ast.unparse of that argument is 'opening_equity', which does not contain the substring.
          The detector only sees an inlined call.
FAMILY    Assumption archaeology
REPRO     scratchpad/probes/p9_detectors.py. Mutants applied to the CURRENT source:
            TEST PASSES (mutant survives)  <- unmodified HEAD
            TEST PASSES (mutant survives)  <- reintroduce the exact 46c7bb67 defect via a local
                 (marked_opening_equity = portfolio.ledger_funding())
            TEST FAILS  (mutant killed)    <- inline the cost figure at the call site
            TEST PASSES (mutant survives)  <- seed from zero      (initial_equity=Decimal('0.00'))
            TEST PASSES (mutant survives)  <- seed from the CLI nominal (initial_equity=initial_cash)
OBSERVED  Four of five mutants survive, including a verbatim reintroduction of the Blocker the test
          is named for and a seed of zero, which disables the daily rule entirely
          (governor.py:213 guards on `> Decimal("0")`).
EXPECTED  A detector that fails against the commit it was written for. Round 3 rejected
          test_the_peak_records_marked_equity_not_only_cost for exactly this -- passing verbatim
          against its parent -- and the replacement has the same property one level of indirection
          away.
BLAST     The suite is 1176 green and cannot detect a reintroduction of claim 5's P1-1 written the
          way it was originally written. This is the third worthless-or-near-worthless test from
          this author in two rounds, and the second where the failure mode is a substring check
          standing in for a semantic one.
SEVERITY  P2 Major
```

#### D2 is sound overall, but a third of it is inert

`'"kill_switch_active": governor.is_killed' in source` is **already true at `46c7bb67`** — at line
1182, inside the `rolling_status` dict, which predates this work:

```
where the string lives at 46c7bb67:
   line 1182: "kill_switch_active": governor.is_killed,
```

The docstring says the assertion guards "the session payload". It does not distinguish the payload
from the live-status dict, so deleting the new `risk` block while leaving the dashboard line intact
would not fail it. The detector as a whole still fails at `46c7bb67` on its other two assertions,
so it has real value; one of its three assertions has none.

**D3 is correct.** It fails at the parent for the right reason and its assertion is exact.

## Coverage

Twelve failure families walked. Probes under
`<scratchpad>/probes/`: `p1_cost_vs_mark.py`, `p2_which_switch.py`, `p3_intraday.py`,
`p4_clear_halt.py`, `p5_staging_race.py`, `p6_mutate_tests.py`, `p7_mutate_recon.py`,
`p8_regression.py`, `p9_detectors.py`, `p10_unpriced.py`, `p11_exit_code.py`,
`drive_sessions.py`, `drive_sessions2.py`, `drive_sessions3.py`.

Targets: `scripts/run_paper_pilot_session.py`, `scripts/clear_paper_halt.py`,
`scripts/run_scheduled_paper_session.py`, `scripts/run_scheduled_paper_session.cmd`,
`src/quant_system/risk/governor.py`, `src/quant_system/execution/paper_portfolio.py`,
`src/quant_system/execution/paper_pilot.py`, `tests/test_risk_governor_session_peaks.py`,
`tests/test_paper_pilot_carried_session.py`, the live Windows scheduled task, and the real
bar/macro caches.

Roughly 90 real paper sessions were driven end-to-end through `run_paper_session` across seven
scenarios (first run, flat hold, -0.6% drift, -0.8% drift to 23 sessions, rotating re-rank,
post-halt recovery, unpriced carried name). Two mutation runs of the full 1173/1176-test suite.
Nothing under `logs/paper_runs/` or `data/evidence/` was written at any point; every run redirected
`PORTFOLIO_STATE_PATH` and `output_dir` into the scratchpad, and the two source mutations were
applied to string copies or through a `sitecustomize.py` on `PYTHONPATH`.

## NOT PROBED

This is the most important section: it converts unknown unknowns into known ones.

1. **The real 09:00 IST session itself.** Everything here is a redirected replay. The live run will
   use real Upstox/Yahoo quotes, the real 500-name universe, realtime mode with 30-second intervals
   and ~780 loop iterations. My end-to-end runs used **NIFTY50 in sequence mode with synthetic
   prices**, because a NIFTY500 realtime run cannot be compressed. The differences that matter and
   were not exercised: intraday price movement within a session, the realtime refetch path
   (`:915-917`), and ~250-310 status-file writes.
2. **The refresh stage of `run_scheduled_paper_session.py`.** `refresh_bars` shells out to
   `ingest_all_market_data.py` against the live Upstox API. I did not run it — it would write to
   `data/evidence/market-cache/`. So the `subprocess.run(check=True)` failure path, the
   `MAX_BAR_STALENESS_DAYS` boundary, and the behaviour when the ingester exits 0 having ingested
   nothing are all unverified. I did confirm by arithmetic that a **completely failed refresh on
   2026-08-31 passes the staleness gate at exactly 4 days** (newest cached bar 2026-08-27), which
   means the session would decide on Thursday's bars while Friday's exist. Not demonstrated,
   because demonstrating it requires breaking the token.
3. **The Upstox path in `fetch_upstox_live_quotes`.** `UPSTOX_INSTRUMENT_KEYS` holds 10 of 500
   symbols and the fallback key `NSE_EQ|{symbol}` is not a valid instrument key, so I expect the
   Upstox branch to return almost nothing and fall through to Yahoo. I did not verify this with a
   real token — doing so would have required reading `.env`, which the context-safety rule forbids.
4. **Concurrency between two real sessions.** P3-1 was demonstrated with threads in one process.
   Two OS processes racing on `portfolio_state.json`, and round 3's P2-5 lost update, were not
   reproduced. Doing so needs two live runners.
5. **Whether `TMPV` being dropped (P2-5) changes over a long horizon.** I showed one name dropped at
   two drift levels. I did not measure how the drop-count scales with drawdown depth, nor whether
   the dropped name is always the last by rank.
6. **The 12% total switch at NIFTY500 scale.** All drawdown work used a 10-name NIFTY50 book.
   A 99-name NIFTY500 book has different per-name weights, different rounding, and 99 orders per
   step against the 5% cash buffer. The `INSUFFICIENT_CASH` cascade at :1034-1071 could behave
   differently at that width.
7. **`restore_state` / `get_state` round-tripping the two peaks.** Neither has a production caller,
   so I read them and did not exercise them.
8. **The server and backtest callers of `PreTradeRiskGovernor`.** Verified by inspection that all
   nine use the default `all_time_peak_equity=None` and are therefore unchanged, and by the full
   suite passing. Not exercised individually.
9. **The markdown report's body** beyond the header and the fills table.
10. **Anything about the model.** Selection, features, scores, the `RESEARCH_ONLY` exemption and the
    cross-section coverage gate were all out of scope for this brief and are untested here.
11. **The `%DATE%` parsing in `run_scheduled_paper_session.cmd`.** `logs\paper_runs\scheduled_*.log`
    does not exist despite a recorded task run at 8/29 22:05. I did not determine whether the log
    was written and removed, or never written. Worth one minute from someone who can look at the
    machine.
12. **Round 3's five P2s and eight P3s**, and the three uncorrected false commit-message claims from
    round 2. The brief marked them known-open and I did not re-litigate them.
