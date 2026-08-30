# Red Team round four — the risk-governor repairs (2026-08-30)

STATUS: IN PROGRESS
COMMIT IN SCOPE: `46c7bb67` — "fix(risk): the daily limit measures the day, and a halt can actually be cleared"
ADJUDICATOR: Claude Code (fourth independent pass). **Wrote none of the work under test.**
BRIEF: `.launch/RED-TEAM-BRIEF-20260830-ROUND4.md`
REPO HEAD AT START: `46c7bb67`

## Verdict

PENDING.

## Findings

PENDING.

## Claims

| # | Claim | Status |
|---|---|---|
| 1 | The governor change is safe for every other caller | **PROVEN** for other callers; the floor makes the total switch structurally weaker (see P2-2) |
| 2 | The daily limit now measures the day | **PART DISPROVEN** — fires on a multi-session decline with zero intraday move |
| 3 | `clear_paper_halt.py` cannot lose or corrupt the book | **PROVEN for the tool**; the recovery it belongs to is not — 1 new P1, 1 P2, 1 P3 |
| 4 | The two replaced tests are worth something | **PROVEN** — both kill their mutants; detector is loose; 1 new P2 |
| 5 | Tomorrow's session completes correctly | **DISPROVEN** — 2 new P1, 1 new P2 |
| 6 | The first-run and second-run boundary | **PROVEN** for peak/halt/clock/fees; 1 new P2, 1 new P3 |
| 7 | Regression against rounds 2 and 3 | NOT TESTED |
| 8 | Anything `46c7bb67` introduced, overstated, or broke | NOT TESTED |

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

NOT TESTED.

### Claim 8 — anything `46c7bb67` introduced, overstated, or broke

NOT TESTED.

## NOT PROBED

PENDING.
