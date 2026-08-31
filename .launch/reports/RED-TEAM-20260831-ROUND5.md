# Red Team round five — everything since the round-four repairs

STATUS: COMPLETE
DATE: 2026-08-31
ADJUDICATOR: Claude Code, independent. **Authored none of the code under test.**
SCOPE: `d6f421e3..a6f3e6f1` (twelve commits)
HEAD AT START: `a6f3e6f1`
BRIEF: `.launch/RED-TEAM-BRIEF-20260831-ROUND5.md`

## Verdict

**NOT READY. Five P1, fifteen P2, nine P3.**

The pattern is five for five. Every P1 below exists because of this batch, and four of the five are
composition defects -- a repair that closed what it aimed at and broke on contact with code it did
not touch:

| P1 | The repair that created it |
|---|---|
| F1 partial feed marks and trades at stale prices, tolerance counter never fires | `cc92dd9a`'s tolerance loop composed with `7d121c63`'s partial-return |
| F4 an exit-only session is recorded as a completed rebalance, and the pilot goes to cash | `44583ba4`'s `executed_rebalance` composed with the `qty == 0` skip |
| F7 the pre-open refresh overwrites the all-market ingestion summary every morning | `cc92dd9a` turned the refresh on; the missing `--summary-file` was harmless while it was a no-op |
| F20 the "daily" drawdown baseline is the boot-time price, so a gap alone halts the pilot | `14ec91da`'s marked-equity repair -- the **third** consecutive round this baseline has been fixed and re-broken |
| F23 two missing quotes out of 500 abort the whole session | `7d121c63` declared a partial feed tolerable; no consumer was changed to tolerate it |

The batch's own headline repairs are real: the bar refresh genuinely fetches, the instrument keys
genuinely resolve, the abort path genuinely reports, the halt genuinely reaches four of five
artefacts, the freshness gate genuinely refuses zero legitimate 2026 mornings, and 1184 tests, ruff
and strict mypy are all green. None of those gates can see any finding in this report.

**One correction to my own work.** F13 was first written as a P1 on the reasoning that the access
token expiring at 03:30 IST tomorrow would break the pre-open refresh. I measured it instead of
trusting the reasoning, found that Upstox serves `v3/historical-candle` with no bearer at all, and
withdrew it. What remains there is a P2 in the opposite direction. The section records both.

## Findings index

| # | Severity | Claim | Summary |
|---|---|---|---|
| F1 | **P1** | 1 | A feed serving part of the universe runs all day; the book is traded and marked at prices that stopped arriving; `consecutive_quote_failures` never increments |
| F4 | **P1** | 5 | Exits fill, every entry is skipped as unaffordable, the pilot goes 100% to cash and persists it as a completed rebalance |
| F7 | **P1** | 3 | The scheduled NIFTY500 refresh overwrites `all-market-ingestion-summary.json` (3,359 targets -> 500) every trading morning |
| F20 | **P1** | 6 | "Equity marked at this session's open" is the last trade price at process start; a 5% overnight gap with zero intraday movement halts the pilot permanently |
| F23 | **P1** | 10 | Two missing quotes out of 500 raise `KeyError` and abort the entire session before any order |
| F2 | P2 | 1 | The 5-poll tolerance is justified against a 30s interval; the default is 10s |
| F5 | P2 | 5 | "Proceeds are available in the same step" is false; exits fill on the next interval |
| F8 | P2 | 3 | Refreshed datasets are bound to a corporate-action authority declaring `effective_to=2026-08-21` |
| F10 | P2 | 4 | The freshness gate counts an uncovered year as "no trading days", so a 7-session-stale cache passes on the first session of a covered year |
| F11 | P2 | 2 | A session interrupted at 09:26 against a 15:30 close reports SUCCESS and exits 0 |
| F12 | P2 | 2 | On Windows the SIGTERM handler never runs; the Stop button leaves the status file at RUNNING forever |
| F13 | P2 | 9 | The refresh refuses when only the *preferred* token is configured, for an endpoint that needs no token |
| F14 | P2 | 9 | The dashboard forces `UPSTOX_ACCESS_TOKEN` as an explicit override, defeating the preference order |
| F15 | P2 | 9 | "A revoked or mis-pasted analytics token is caught" is false; the guard reads `exp` only |
| F17 | P2 | 7 | The dashboard paints HALTED and ABORTED green and COMPLETED red, and never renders the halt reason |
| F18 | P2 | 7 | The Stop button kills whatever owns a stale PID from 2026-08-26 and reports "halted and reconciled to disk" |
| F21 | P2 | 6 | The unpriced-holding cost fallback was justified for the risk baseline and now also drives position sizing |
| F24 | P2 | 11 | `44583ba4` reuses `14ec91da`'s subject and contains no production code |
| F25 | P2 | 11 | Three load-bearing code comments assert guarantees the code does not provide |
| F29 | P2 | 11 | `--capital 0` advances the persisted portfolio and then dies without writing any report |
| F3 | P3 | 1 | The partial-feed warning fires once per poll, ~750 times a session |
| F6 | P3 | 5 | Membership is rebalanced; weights never are |
| F9 | P3 | 3 | The full universe is re-downloaded every Monday and post-holiday; a symbol with no new bars is re-fetched forever |
| F16 | P3 | 9 | The expiry message gives the wrong instruction in the case it was written for |
| F19 | P3 | 7 | The halt fired and the book was liquidated anyway; which ordering happens is accidental |
| F22 | P3 | 6 | `enforce_market_hours=False` plus a 09:00 start permits a full rebalance in the pre-open window |
| F26 | P3 | 11 | Duplicated `halted = False` left by the peer collision |
| F27 | P3 | 11 | `e853376a` narrates a destructive overwrite as a routine refresh, and adds a PDF at the repo root |
| F28 | P3 | 11 | `ALLOWED_SYMBOLS` assigned twice with different values and read nowhere |

## Claims

| # | Claim | Verdict |
|---|---|---|
| 1 | Quote-failure tolerance | **DISPROVEN — P1, P2, P3** |
| 2 | The abort path | **PARTLY PROVEN — P2 x2** |
| 3 | Date-aware cache hit | **PARTLY PROVEN — P1, P2, P3** |
| 4 | `MAX_MISSED_SESSIONS = 0` | **MOSTLY PROVEN — P2** |
| 5 | `executed_rebalance` | **PARTLY DISPROVEN — P1, P2, P3** |
| 6 | Marked equity shared by sizing and risk | **DISPROVEN — P1, P2, P3** |
| 7 | The halt reaches every artifact | **PARTLY PROVEN — P2, P3** |
| 8 | The resolving AST test | **DEFEATED — P2** |
| 9 | The peer session's token work | **PARTLY PROVEN — P2 x3, P3** |
| 10 | The single-source removal | **PARTLY DISPROVEN — P1** |
| 11 | Anything this batch introduced, overstated, or broke | **DISPROVEN IN PART — P2 x3, P3 x3** |

### Claim 1 — The quote-failure tolerance

**DISPROVEN. The tolerance is real for a total outage and blind to a partial one. P1.**

The transient-failure half works: `scripts/run_paper_pilot_session.py:967-989` catches
`QuoteFeedError`, increments `consecutive_quote_failures`, skips the interval and resumes; the
fifth consecutive failure re-raises. Verified against today's real feed at
`logs/paper_runs/scheduled_20260831.log:1717` -- a single SSL handshake timeout on the first chunk
raised.

The masking half does not work. The brief's own question -- "can the tolerance mask a real outage,
a feed returning stale or partial data indefinitely without ever raising?" -- answers **yes**.

#### F1 (P1) -- a partial feed runs all day, trades and marks the book at prices that stopped arriving, and never touches the failure counter

`fetch_upstox_live_quotes` raises only when it has **nothing at all**
(`scripts/run_paper_pilot_session.py:303`, `if not results:`). Two independent paths reach a
partial result without raising:

- `scripts/run_paper_pilot_session.py:299-301` -- `except Exception: logger.warning(...); break`.
  The `break` abandons every *later* chunk. On the 500-name NIFTY500 universe that is 5 chunks of
  100, so a timeout on chunk 3 returns exactly 200 symbols and never attempts 4 or 5.
- `scripts/run_paper_pilot_session.py:264` -- the payload is used only when
  `data.get("status") == "success"`, with no `else` branch. An HTTP-200 error envelope (Upstox
  returns these for rate limits and bad keys) is discarded **with no log line of any kind**, and
  the loop continues to the next chunk.

Both return normally, so `consecutive_quote_failures = 0` at line 989 executes on the very poll
that lost 60% of the feed.

**This already happened live today, twice, on the real feed:**

```
logs/paper_runs/scheduled_20260831.log:1317-1319
2026-08-31 13:29:12 IST [WARNING] quant_system.paper_runner: Upstox batch quote fetch failed (<urlopen error timed out>).
2026-08-31 13:29:12 IST [WARNING] quant_system.paper_runner: Upstox returned no quote for 300 of 500 symbols; they are omitted, not estimated: HDFCLIFE, HEG, HEROMOTOCO, HEXT, HFCL, HINDALCO, HINDCOPPER, HINDPETRO, HINDUNILVR, HINDZINC ...
2026-08-31 13:29:12 IST [INFO] quant_system.paper_runner:   FORCEMOT: skipped, 1 share costs Rs 17550.00 against an allocation of Rs 9500.00
```

No abort, no counter increment, no mention in any artifact. Again at 13:44:57 (log line 1439).

**REPRO A** -- the fetcher alone, deterministic, about 2 seconds. Stubs `urllib.request.urlopen` so
chunks 3-5 raise `TimeoutError`, over the real 500-name NIFTY500 authority:

```
[WARNING] Upstox batch quote fetch failed (timed out).
[WARNING] Upstox returned no quote for 300 of 500 symbols; they are omitted, not estimated: HDFCLIFE, HEG, HEROMOTOCO, HEXT, HFCL, HINDALCO, HINDCOPPER, HINDPETRO, HINDUNILVR, HINDZINC ...
RETURNED WITHOUT RAISING. quotes for 200 of 500 symbols
urlopen calls made: 3 (of 5 batches)
```

The warning text is byte-identical to today's live log, which is how I know the stub reproduces the
real mechanism and not a look-alike.

**REPRO B** -- the whole thing. `run_paper_session()` driven end to end against a feed that returns
half the universe on **every poll after the first**, with a controlled clock and a scratch output
directory. `PORTFOLIO_STATE_PATH` monkeypatched to scratch; nothing under `logs/paper_runs/`,
`data/evidence/` or `.env` was written.

```
Interval 01 .. 09  [WARNING] Upstox returned no quote for 10 of 20 symbols; they are omitted, not estimated: HINDALCO, ICICIBANK, INFY, ITC, JSWSTEEL, LT, MARUTI, NESTLEIND, NTPC, ONGC
Interval 02  [FILL EXECUTED] LT: BUY 600 @ Rs 115.18 (Statutory Fee: Rs 82.37)
Interval 03  [FILL EXECUTED] LT: BUY 600 @ Rs 115.18 (Statutory Fee: Rs 82.37)
Interval 04  [FILL EXECUTED] LT: BUY 600 @ Rs 115.18 (Statutory Fee: Rs 82.37)
Market close reached at 09:32:00 IST. Finalizing session...
Session Concluded and Reconciled: SUCCESS
Total Equity : Rs 1001144.27 (Net P&L: Rs 1144.27, +0.11%)

aborted   : False
halted    : False
fills     : 16
equity    : 1001144.27
```

Nine consecutive polls delivered 50% of the universe. `consecutive_quote_failures` never left 0.
The session **traded one of the unserved names** -- LT, 2065 shares, about Rs 238,000, roughly a
quarter of the book -- filling it four times at a price frozen since the first poll (the served
names moved Rs 0.10 per interval; LT did not move at all), then marked it at that same frozen price
for the closing equity.

OBSERVED: clean exit, status COMPLETED, aborted false, a positive P&L computed in part from prices
that stopped arriving.

EXPECTED: either the absent names count against `MAX_CONSECUTIVE_QUOTE_FAILURES`, or the session
refuses to trade and mark a name it has no current price for, or at minimum the artifacts record
which symbols were priced stale and since when.

**Nothing records it.** The final payload carries no such field:

```
keys: [abort_reason, aborted, audit_events_count, capital, closed_at_ist, fills, market_close_ist, model, order_statistics, performance, reconciliation, risk, session_date, session_id, started_at_ist, timezone, universe]
aborted False | abort_reason (empty)
open positions {BHARTIARTL: 2303, GRASIM: 2217, HDFCBANK: 2176, LT: 2065}
status file: COMPLETED | keys mentioning quote/stale: []
```

**A false claim in the code hides this.** `scripts/run_paper_pilot_session.py:311-313` says the
missing names are safe because "the coverage gate downstream already refuses a shrunk one". There
is no such gate. `MIN_CROSS_SECTION_COVERAGE` (defined `:361`, checked `:705`) gates the
**bar-cache** cross-section built once before the loop by `load_mizan_cross_section`, which never
consults `base_market`. Nothing anywhere examines quote coverage. That comment is the entire
justification for tolerating a partial feed, and it is false.

BLAST: every unattended session. On the real 500-name universe one chunk failure loses 100-400
names at a stroke, and today's log shows it twice in two hours on an ordinary connection. The book
is traded and marked from stale prices, the report states a P&L derived from them, and the process
exits 0.

SEVERITY: **P1** -- silent wrong money written into the evidence artifact, on the critical path,
with a live reproduction from today. This defect exists only because of this batch: the tolerance
loop is new in `cc92dd9a` and the partial-return-without-raise is new in `7d121c63`.

#### F2 (P2) -- the tolerance is counted in polls, and the poll interval is not what the comment assumes

`MAX_CONSECUTIVE_QUOTE_FAILURES = 5` is justified at `:73-77` as "at a 30-second interval this is
about two and a half minutes of silence". The scheduled path does pass `--interval-seconds 30`
(`scripts/run_scheduled_paper_session.py:281-282`), but the argument default is **10.0**
(`scripts/run_paper_pilot_session.py:1610-1613`), so a hand-run session tolerates 50 seconds rather
than 150. The bound is a poll count wearing the clothes of a wall-clock bound.

#### F3 (P3) -- the partial-feed warning fires once per poll, forever

REPRO B logged the identical 10-of-20 warning on all nine intervals. At the scheduled 30-second
interval across a 6h15m session that is roughly 750 identical WARNING lines; today's real log is
246 KB. An operator scanning for trouble cannot distinguish one bad poll from a two-hour outage,
which is the operability half of F1.

### Claim 2 — The abort path

**PARTLY PROVEN. The exception path works. Two non-exception failures still report clean. P2 x2.**

The exception leg is correct and I could not defeat it. `scripts/run_paper_pilot_session.py:1287-1294`
records `session_abort_reason`; `:1462-1463` publishes `aborted`/`abort_reason`; `:1522-1526` writes
the markdown banner; `:1573-1579` writes `ABORTED` to the status file; `:1681-1706` prints
`[PAPER PILOT ABORTED]` and returns 10; `scripts/run_scheduled_paper_session.cmd:13-17` now
propagates the code to Task Scheduler. Today's real log shows the pre-repair behaviour it fixes --
`QuoteFeedError` at 14:21:11 followed by `[PAPER PILOT SUCCESS] ... paper session exited 0`
(`logs/paper_runs/scheduled_20260831.log:1717-1745`).

The brief asked for a failure that still reports clean. There are two, and neither goes through
`except Exception`.

#### F11 (P2) -- a session interrupted at 09:26 against a 15:30 close reports SUCCESS and exits 0

`handle_sigint` (`scripts/run_paper_pilot_session.py:895-900`) sets `shutdown_requested`; the
`while not shutdown_requested` loop exits **normally**, so `session_abort_reason` stays empty and
every downstream branch reads the session as complete.

REPRO (`probe_claim2.py`): identical to a normal run except that `signal.raise_signal(SIGINT)` fires
on the fourth quote poll -- an operator pressing Ctrl-C, or the dashboard Stop button on any POSIX
host.

```
>>> delivering SIGINT
aborted        : False | abort_reason: ''
reconciled     : True
kill switch    : False
closed_at_ist  : 2026-08-31 09:26:00 IST   market_close_ist: 2026-08-31 15:30:00 IST
status file    : COMPLETED
main() banner  : [PAPER PILOT SUCCESS]  exit code 0
```

OBSERVED: a session that ran for six minutes of a six-hour trading day produces a report, a status
file and an exit code byte-identical in kind to one that ran to the bell. The portfolio is advanced
(`sessions_completed + 1`, and `executed_rebalance` if anything filled), so the truncation is
permanent.

EXPECTED: the same treatment the exception path gets. The information is already in the payload --
`closed_at_ist` is 09:26 and `market_close_ist` is 15:30 -- and nothing compares them.

BLAST: every operator-interrupted run, every reboot, every Task Scheduler "End task" on a POSIX
host, and the dashboard Stop button. The commit subject is "say so when you do not"; on this path it
does not say so.

SEVERITY: **P2**, escalated from P3 because it is silent and it advances persistent state.

#### F12 (P2) -- on Windows the SIGTERM handler is unreachable, so the Stop button leaves the dashboard reading RUNNING forever

`scripts/run_paper_pilot_session.py:903` registers `handle_sigint` for `SIGTERM`. On Windows
`os.kill(pid, SIGTERM)` and `Popen.terminate()` both call `TerminateProcess`; no handler runs.
Measured on this machine with a child that installs exactly that handler:

```
parent: os.kill(pid, SIGTERM)  <- exactly what serve_live_dashboard.py:157 does
child stdout: 'child ready\n'      <- "HANDLER RAN" never printed
child returncode: 15
```

So the dashboard Stop path (`scripts/serve_live_dashboard.py:150`, `:157`) hard-kills the pilot:

- `end_session` never runs, so there is no reconciliation and no session JSON or markdown;
- `save_portfolio` never runs, so the day's fills are absent from the persisted portfolio while the
  ledger that held them is gone;
- `live_paper_status.json` is left at its last in-loop write, `"status": "RUNNING"`, with
  `kill_switch_active: false` -- and `/api/status` then serves that indefinitely to every dashboard
  reader, which per F17 renders it as a green LIVE badge.

There is no staleness check anywhere: neither the server (`scripts/serve_live_dashboard.py:56-69`)
nor the page compares `timestamp_ist` to the wall clock. The dashboard cannot distinguish a running
session from one killed four hours ago.

This is the operability family's "alarm for the absence of signal", and it is absent.

### Claim 3 — The date-aware cache hit

**PARTLY PROVEN. The no-op is genuinely fixed. The refresh that now runs destroys a different
evidence artefact every morning, and re-downloads the whole universe every Monday. P1 + P2 + P3.**

The repair itself is correct. `scripts/ingest_all_market_data.py:245-258` compares
`received_end >= self.to_date` and `:277-280` requires it before returning a cache hit. Verified
against the real provider that the *data* the no-op was hiding is genuinely there: the v3
historical endpoint the client actually calls
(`src/quant_system/data/upstox.py:193-198`) returns Friday 2026-08-28 today, while the cache the
pilot read still ends 2026-08-27.

```
URL: https://api.upstox.com/v3/historical-candle/NSE_EQ%7CINE009A01021/days/1/2026-08-31/2026-08-20
UPSTOX_ACCESS_TOKEN:    HTTP 200 candles=7 newest=2026-08-28
UPSTOX_ANALYTICS_TOKEN: HTTP 200 candles=7 newest=2026-08-28
```

#### F7 (P1) -- the scheduled pre-open refresh overwrites the all-market ingestion summary, every trading morning

`scripts/run_scheduled_paper_session.py:176-189` builds the ingester command with
`--universe-csv`, `--cache-root`, `--from-date`, `--to-date` and `--concurrency`. It does **not**
pass `--summary-file` or `--corporate-actions-dir`, and both default to the all-market paths
(`scripts/ingest_all_market_data.py:504-521`):

```
--summary-file          data/evidence/market-analysis/all-market-ingestion-summary.json
--corporate-actions-dir data/evidence/market-cache/all-market-20160822-20260821/corporate-actions
```

So a NIFTY500 refresh writes its own results over the all-market record. This has already happened
and is committed in this batch (`e853376a`, +/- 41,798 lines on that file):

```
BEFORE (46c7bb67): universe_csv = data/authorities/nse-all-listed-equities.csv
                   total_targets 3359  results 3359  bars 4,501,992  updated 2026-08-24T18:12:46Z
AFTER  (HEAD)    : universe_csv = data/evidence/market-cache/scheduled-universe-instruments.csv
                   total_targets  500  results  500  bars   350,857  updated 2026-08-31T06:47:01Z
```

OBSERVED: the evidence summary for the 3,267-symbol / 4.6M-bar all-market cache -- the artefact
`agent_context/CURRENT.md` cites as the basis for the expanded-universe replication -- now describes
a 500-symbol NIFTY500 refresh of a different store. `update_summary()` is called every 25 symbols
and again at the end (`scripts/ingest_all_market_data.py:464`, `:468`), so it is rewritten
unconditionally on every scheduled run.

EXPECTED: a refresh of store A does not write the summary of store B.

BLAST: recurs at 09:00 IST every trading day, unattended, with no log line naming the file it
overwrote. The prior content survives in git at `46c7bb67`, so this is recoverable rather than
permanently lost -- but only because a daily auto-sync happened to commit the old version first.
Nothing in the design preserves it.

SEVERITY: **P1.** Silent corruption of a governed evidence artefact under `data/evidence/`,
recurring daily, created by wiring introduced in this batch.

#### F8 (P2) -- refreshed datasets carry a corporate-action authority that does not cover them

`scripts/ingest_all_market_data.py:160-172` hardcodes the authority window:

```python
publication_date=date(2026, 8, 24),
effective_from=date(2016, 8, 22),
effective_to=date(2026, 8, 21),
```

Every dataset the scheduled refresh now persists covers 2023-08-31..2026-08-30 and is bound to a
corporate-action authority that declares itself effective only to **2026-08-21**. A split, bonus or
dividend after that date is outside the declared window and the adjustment is applied anyway.

`fetch_or_load_corporate_actions` (`:114-119`) returns the on-disk file whenever it exists and never
re-fetches, so the CA record for a symbol is frozen at whatever range the first ingest asked for.
Combined, a corporate action occurring after the original ingest is invisible to every subsequent
refresh, permanently.

This code is pre-existing. What this batch changed is that it is now **reachable**: before the
`_is_current` repair, `process_target` returned at the cache-hit line and never built an authority
or persisted a dataset. Fixing the no-op turned a dormant mis-scoped authority into one written
into new governed evidence every Monday.

#### F9 (P3) -- the whole universe is re-downloaded every Monday and every post-holiday morning

`scripts/run_scheduled_paper_session.py:245` sets `target = today - timedelta(days=1)` and passes it
as `--to-date`. `_is_current` then requires `received_end >= to_date`. On a Monday `to_date` is
Sunday, and no exchange date can satisfy it, so all 500 symbols miss the cache. Same on any day
whose previous calendar day was a weekend or a holiday.

The docstring says "Re-fetching a symbol whose range is already complete costs nothing"
(`scripts/ingest_all_market_data.py:249-250`). It is not free: it is 500 provider round trips plus
500 corporate-action file reads, inside a 15-minute window before the 09:15 open, and it is also
what makes F7 and F8 fire. The brief's question "does it re-download ten years every morning?"
answers: not every morning, but roughly one morning in five, and always on the busiest one.

**A symbol that legitimately has no new bars** -- suspended, delisted mid-window, or simply not
traded -- can never satisfy `_is_current` and is therefore re-fetched on every run forever, each
time returning the same data. Silent, unbounded, and indistinguishable in the logs from a healthy
name (`Empty/Fail: 1` in today's real run, unnamed).

### Claim 4 — `MAX_MISSED_SESSIONS = 0`

**MOSTLY PROVEN. Zero is not too strict on any 2026 morning. It fails open across a year boundary. P2.**

I walked all 365 days of 2026 against the committed holiday authority
(`data/authorities/nse-trading-holidays.json`, `covers_years: ['2026']`, 20 holidays, 245 trading
sessions) and, for every one of the 244 session-to-session transitions, asked whether an ideal cache
-- one holding exactly the previous trading session's bar -- would be refused:

```
authority covers_years: ['2026']
holiday count: 20
2026 trading sessions per the authority: 245
ideal-cache mornings that would REFUSE: 0 []
```

**Zero.** Long weekends, Monday holidays, the Diwali cluster: none of them refuses a legitimate
morning. `trading_sessions_between` is correct on the cases the brief asked about and the new test
asserts (Fri->Mon = 0, Thu->Mon = 1, Wed->Mon = 2). The replacement of the four-calendar-day bound
is sound.

#### F10 (P2) -- the gate silently passes an arbitrarily stale cache on the first trading day of a covered year

`trading_sessions_between` (`scripts/run_scheduled_paper_session.py:100-115`) counts a day as a
session only if `require_trading_day(day)` does not raise. `require_trading_day`
(`:88-92`) raises `NotATradingDay` when the day's **year is not in `covers_years`**. The authority
covers 2026 only. So every day in 2025 is classified "not a trading session", and the loop's
`except NotATradingDay: pass` turns that into "nothing was missed".

REPRO (`probe_cal.py`, using the real authority):

```
  cache ends 2025-12-31 (Wed), run 2026-01-01: missed = 0
  cache ends 2025-12-30 (Tue), run 2026-01-01: missed = 0
  cache ends 2025-12-29 (Mon), run 2026-01-01: missed = 0
  cache ends 2025-12-22 (Mon), run 2026-01-01: missed = 0
```

OBSERVED: a cache ten days and seven trading sessions stale passes `missed > MAX_MISSED_SESSIONS`
with `missed = 0`, and the session proceeds to trade on it.

EXPECTED: an uncovered year is the module's own definition of "fail-closed on every uncertainty"
(`:72-75`). Used as a *predicate* rather than as a *gate on today*, the same fail-closed raise
becomes fail-open.

BLAST: one morning per year per covered range, plus any future rollover. It is exactly the
condition the check exists to catch -- stale data used silently -- and it produces no log line at
all, because `missed` is only reported when it exceeds the limit.

SEVERITY: **P2.** Rare by date, silent, and it defeats the guard on the one morning the calendar
changes underneath it. Escalated from P3 because it is silent.

Two related observations, both fail-closed and therefore not defects:

- The forward direction is safe. `require_trading_day(today)` runs first
  (`scripts/run_scheduled_paper_session.py:232`), so from 2027-01-01 the scheduler refuses outright
  with exit 2 until the authority is refreshed. Confirmed: `trades(2027-01-04)` is `False`.
- `require_trading_day` re-reads and re-parses the holiday JSON on every call, and
  `trading_sessions_between` calls it once per calendar day. Negligible at current ranges; it is
  O(days x holidays) file I/O rather than a cached lookup.

**Tomorrow's real case, measured.** The cache currently ends 2026-08-27; the provider has
2026-08-28. On 2026-09-01 (Tuesday, a trading day):

```
REAL: newest cached bar is 2026-08-27; run on 2026-09-01 -> 2 missed
REAL: newest cached bar 2026-08-28,  run on 2026-09-01 -> 1 missed
```

Either way the gate refuses with exit 4 unless the refresh actually delivers 2026-08-31. It should:
the v3 historical endpoint serves this data without any bearer at all (measured under F13), so the
expiry of `UPSTOX_ACCESS_TOKEN` at 03:30 tomorrow does not block it.

### Claim 5 — `executed_rebalance`

**PARTLY DISPROVEN. The set equality is defensible; the first clause is not. P1 + P2.**

Two sub-questions from the brief answered first, because both are clean:

- **Zero-quantity positions cannot pollute the set.** `DecimalLedger` pops a symbol whose lots net
  to zero (`src/quant_system/core/ledger.py:487`, `:495`), so `engine.positions`
  (`src/quant_system/execution/paper_pilot.py:206`) holds only live positions. Set equality is not
  defeated by closed names.
- **Carry-in fills cannot satisfy clause 1.** `carry_in_positions`
  (`src/quant_system/execution/paper_pilot.py:213-238`) deliberately keeps the replayed fills out
  of `self._fills`, and `total_fills_count` is `len(self._fills)`
  (`src/quant_system/execution/paper_pilot.py:904`). So `total_fills_count > 0` really does mean
  something traded **today**. Side note: the runner's `if not f.fill_id.startswith("carry_")`
  filter at `scripts/run_paper_pilot_session.py:1312` is therefore dead code -- the engine never
  puts a `carry_` fill in that list. Harmless, but the runner and the engine disagree about what
  `engine.fills` contains.

#### F4 (P1) -- a session that sells the whole book and buys nothing is recorded as a completed rebalance

`scripts/run_paper_pilot_session.py:1331-1334` reads, in effect: `rebalancing and
(total_fills_count > 0 or (bool(mizan_picks) and set(engine.positions) == set(mizan_picks)))`.

`total_fills_count > 0` counts **any** fill, including an exit. The stated intent at `:1329-1330`
is "whether the selection was *executed* ... either something traded, or nothing needed to". A
session in which every exit fills and every entry is skipped satisfies clause 1 while executing
none of the selection.

That state is reachable through a guard added in this same batch.
`scripts/run_paper_pilot_session.py:1114-1123` skips a pick when one share costs more than the
equal-weight allocation. Today's real session hit that on 3 of 100 picks (FORCEMOT, APARINDS,
BOSCHLTD, at Rs 9,500 per name). The allocation is `marked_opening_equity * 0.95 / len(picks)`, so
it shrinks with equity and with the number of picks. When it skips all of them, the exits still
fire.

REPRO (`probe_claim5.py`, scratch state file; no repository artifact touched). Carried book of four
names, `sessions_held=10` so a rebalance is due; the four selected names priced above the
allocation:

```
SEED  sessions_held=10 last_rebalance_on=2026-08-14 holdings=[ASIANPAINT, AXISBANK, CIPLA, COALINDIA] cash=40000.00

[EXIT PROPOSAL SUBMITTED] prop_..._1_ASIANPAINT_SELL SELL 2000 ASIANPAINT (Risk: APPROVED)      x4
  BHARTIARTL: skipped, 1 share costs Rs 999999.00 against an allocation of Rs 38000.00
  HDFCBANK:   skipped, 1 share costs Rs 999999.00 against an allocation of Rs 38000.00
  LT:         skipped, 1 share costs Rs 999999.00 against an allocation of Rs 38000.00
  GRASIM:     skipped, 1 share costs Rs 999999.00 against an allocation of Rs 38000.00
[FILL EXECUTED] ASIANPAINT: SELL 2000 @ Rs 99.88 (Statutory Fee: Rs 208.13)                     x4
Session Concluded and Reconciled: SUCCESS
Orders Summary : 4 submitted | 4 filled | 0 cancelled | 0 rejected

fills today          : 4
open positions after : {}
PERSISTED sessions_held      = 1
PERSISTED last_rebalance_on  = 2026-08-31
PERSISTED holdings           = []
PERSISTED cash               = 838207.48
```

OBSERVED: the pilot went 100% to cash, paid Rs 832.52 of statutory exit costs plus Rs 400 slippage,
persisted `last_rebalance_on = 2026-08-31` and `sessions_held = 1`, and exited clean. No warning
fired -- `if rebalancing and not executed_rebalance` at `:1335` was skipped precisely because
`executed_rebalance` was True.

EXPECTED: this is the outcome the batch's own guard at `:1071-1076` exists to forbid -- "Holding
the existing book rather than liquidating: going to cash is not a rule the screen contains." That
guard covers exactly one of the two ways to reach an empty book (`top_picks` empty). It does not
cover the other (every pick unaffordable), and `executed_rebalance` then certifies the result as a
completed rebalance.

`rebalance_due` returns True for an empty book
(`src/quant_system/execution/paper_portfolio.py:212`), so the next session re-enters. That does not
repair it, it doubles the cost: a full exit round trip today plus a full entry round trip tomorrow,
at prices one session later, for a re-ranking the horizon did not call for.

BLAST: any rebalance from a drawn-down book. `per_name_alloc` falls with equity; on the 500-name
universe with 100 picks, Rs 1,000,000 equity gives Rs 9,500 per name and three real NIFTY500 names
already exceed it. At Rs 200,000 equity the allocation is Rs 1,900 and most of the index is
unaffordable.

SEVERITY: **P1.** Unmeasured strategy change (full liquidation), real money in fees, silent, and
the persisted state records the opposite of what happened. A composition defect created by this
batch: the `qty == 0` skip and the `executed_rebalance` test were both introduced here.

#### F5 (P2) -- "the proceeds are available to fund these buys" is false

`scripts/run_paper_pilot_session.py:1100-1103` claims: "Exits above run first, in the same step, so
the proceeds are available to fund these buys: sizing every entry against pre-exit cash meant a
fully invested book could only spend its ~5% buffer." Exits are **submitted** in the same step;
they **fill** on the next interval's `process_quote`. `engine.cash` at `:1111` is still pre-exit.

REPRO (`probe_claim5b.py`), fully invested carried book, Rs 40,000 cash against Rs 840,280 equity:

```
Interval 01  [EXIT PROPOSAL SUBMITTED] ... SELL 2000 ASIANPAINT (Risk: APPROVED)   x4
Interval 01  [PROPOSAL SUBMITTED] ... BUY 380 BHARTIARTL (Risk: REJECTED, Reason: INSUFFICIENT_CASH: Need 38000.00, Available after buffer is -2000.00)   x4
Interval 02  [FILL EXECUTED] ASIANPAINT: SELL 2000 @ Rs 99.90   x4
Interval 02  [PROPOSAL SUBMITTED] ... BUY 1995 BHARTIARTL (Risk: APPROVED)   x4
Orders Summary : 12 submitted | 8 filled | 0 cancelled | 4 rejected
```

Rs 38,000 is exactly 95% of the Rs 40,000 pre-exit cash; the correct allocation is Rs 199,500 and
it only appears at interval 02. The comment describes a behaviour the code does not have.

The outcome here is saved by the governor's cash-buffer check rejecting all four premature buys,
and the retry on the next interval enters at the right size, so the damage is bounded. What it does
cost: four spurious `orders_rejected` -- one of the two numbers the "Rebalance did NOT execute"
diagnostic at `:1336-1342` reports, and also published as `risk.orders_rejected` in the session
payload. A rejection count that includes self-inflicted sequencing artifacts is a worse signal than
one that does not.

#### F6 (P3) -- membership is rebalanced, weights never are

`scripts/run_paper_pilot_session.py:1109-1110`: the entry loop acts only when
`current_held == 0`. A name that survives from one selection to the next is never re-sized, so the
equal weight computed in the sizing block applies to newly-entered names only and the book drifts
from it indefinitely. Confirmed by construction, not separately reproduced. It also makes the
brief's "what about quantities" question moot for the set-equality clause: the runner has no
concept of a target quantity for an already-held name.

### Claim 6 — Marked equity shared by sizing and risk

**DISPROVEN. The two consumers wanted different things, and the shared number is not what its own
name says it is. P1 + P2 + P3.**

The mechanical part is fine: `marked_opening_equity` (`scripts/run_paper_pilot_session.py:755-780`)
depends only on `portfolio` (loaded `:645`) and `base_market` (fetched `:572`), both of which
precede it. Lifting it above the sizing block moved it before nothing it depends on. `git diff
cc92dd9a..44583ba4` confirms the block was relocated intact.

#### F20 (P1) -- "equity marked at this session's open" is the last trade price when the runner booted, which for the 09:00 scheduled run is the previous close; a gap alone trips the daily kill switch

The commit comment at `:736-755` states the defect it fixed:

> a book that drifted 5.6% down over ten sessions -- with exactly zero intraday movement -- halted on
> the first order of the first rebalance. That order is the exit, so the losing book was then held
> with nothing able to sell it. Which is verbatim the failure the previous commit claimed to have
> fixed.

It is still verbatim that failure. `base_market` is fetched once at `:572`, at whatever wall-clock
time the process starts. The scheduled task starts at 09:00 IST and the refresh runs first, so the
quote fetch lands in the pre-open window: `last_price` is the previous close, not the open. The 4%
"daily" limit therefore measures **previous close -> now**, which contains the entire overnight gap.

REPRO (`probe_claim6.py`): carried book of 4 names at Rs 100, Rs 40,000 cash, rebalance due. The
startup quote is the previous close of 100; every subsequent poll returns 95 and **never moves
again** -- a 5% gap down and a perfectly flat session.

```
[EXIT PROPOSAL SUBMITTED] ..._3_COALINDIA_SELL SELL 2000 COALINDIA (Risk: REJECTED)
[PROPOSAL SUBMITTED] ..._3_BHARTIARTL_BUY BUY 400 BHARTIARTL (Risk: REJECTED, Reason: KILL_SWITCH_ACTIVE)
Rebalance did NOT execute: 24 order(s) submitted, 0 filled, 24 rejected. The hold clock is not reset and the book is carried unchanged.
Portfolio saved: cash Rs 40000.00, 4 holding(s), realized Rs 0.00, fees to date Rs 0.00
Orders Summary : 24 submitted | 0 filled | 0 cancelled | 24 rejected

payload risk.halt_reason : 'DAILY_DRAWDOWN_LIMIT_BREACHED: 4.76% >= 4.00%'
persisted risk_halted    : True | halted_on 2026-08-31
main() exit code would be: 9
```

OBSERVED: the kill switch fires on the first order of the rebalance. The first order is the **exit**,
so the losing book is retained with nothing able to sell it. `risk_halted: true` is persisted, and
`scripts/run_paper_pilot_session.py:823-837` then refuses **every subsequent session** with
`SystemExit(8)` until a human runs `clear_paper_halt.py`. There was no intraday drawdown of any
kind; the reason string attributes 4.76% of decline to a session in which the price did not move.

EXPECTED: a *daily* drawdown limit measures from the session open. Nothing in the runner ever reads
an open. The three candidate quantities -- cost basis (rejected in round 3), carried peak (rejected
in round 4), and the price at process-start (this batch) -- are all wrong, and the third is wrong on
a much more common input than the first two: a 4% overnight gap is an ordinary NSE mid-cap event,
whereas a 4% multi-session drift took ten sessions.

BLAST: the unattended pilot, on the first meaningfully gapped morning. The outcome is a permanently
halted pilot requiring manual intervention, with a halt reason that misdescribes why.

SEVERITY: **P1.** Wrong risk behaviour on the critical path, unrecoverable without a human, and it
is the third consecutive round in which this same baseline has been repaired and re-broken.

#### F21 (P2) -- the unpriced-holding fallback was justified for one consumer and is now used by two

`:761-770`:

> Cost basis for these, stated rather than silent. **It is a baseline for a risk limit, not a P&L
> figure**, and refusing the whole session because one carried name is unquoted would be worse than
> a bounded approximation that is logged.

That justification was written when `marked_opening_equity` had one consumer. It now also drives
`per_name_alloc` (`:803-806`). Missing quotes are not rare -- F1 shows 300 of 500 symbols absent
from a single real poll today. A carried name that is down 40% and unquoted contributes its **cost**
to `marked_opening_equity`, inflating `usable`, inflating `per_name_alloc`, and over-allocating to
the head of the ranking so the tail goes unfilled. That is, word for word, the concentration defect
the same comment block says it exists to prevent ("measured at 9.87% cash held against a declared 5%
buffer, with a selected name absent entirely").

The two consumers genuinely want different quantities: sizing wants deployable capital, the governor
wants a mark-to-market baseline. Unifying them was right for the *market-priced* case and silently
wrong for the *unpriced* case, and the comment that authorises the fallback was not revisited.

#### F22 (P3) -- pre-open trading is not prevented

`OrderBookSimConfig(..., enforce_market_hours=False)` (`:854-858`). Combined with a 09:00 start, the
first intervals run in the pre-open window and can submit, match and fill an entire rebalance against
previous-close quotes before the market opens. This is pre-existing configuration, not new in this
batch, but the 09:00 schedule is what makes it reachable and the schedule is part of what this batch
put into production. Not reproduced against a real pre-open window -- the only live run so far
started at 12:17.

### Claim 7 — The halt reaches every artifact

**PROVEN for four of five artefacts. The dashboard leg is broken, and colours the halt green. P2 + P3.**

Driven end to end (`probe_claim7.py`): carried book of 4 names, rebalance due, prices gap down 30%
after the opening quote so the 4% daily limit is genuinely breached inside `evaluate_order`.

```
[PROPOSAL SUBMITTED] ..._9_BHARTIARTL_BUY BUY 2850 BHARTIARTL (Risk: REJECTED, Reason: KILL_SWITCH_ACTIVE)
Orders Summary : 40 submitted | 4 filled | 0 cancelled | 36 rejected

payload risk.kill_switch_active : True
payload risk.halt_reason        : 'DAILY_DRAWDOWN_LIMIT_BREACHED: 28.74% >= 4.00%'
markdown has KILL SWITCH banner : True
status file status              : HALTED
status file kill_switch_active  : True
status file risk_governor block : {'kill_switch_active': True, ...}
persisted risk_halted           : True | halted_on 2026-08-31
persisted halt_reason           : 'DAILY_DRAWDOWN_LIMIT_BREACHED: 28.74% >= 4.00%'
main() exit code would be       : 9
```

The session payload, the markdown report, the live status file, the persisted portfolio and the exit
code all carry the halt. That part of the claim holds, and the next session's `SystemExit(8)` guard
(`scripts/run_paper_pilot_session.py:823-837`) then refuses to trade. Good.

#### F17 (P2) -- the dashboard renders a halted session in green and a clean one in red

`src/quant_system/server/ui/live_dashboard.py:598-604`:

```javascript
statusElem.textContent = data.status || "RUNNING";
if (data.status === "COMPLETED") {
  statusElem.className = "badge-stopped";
} else {
  statusElem.className = "badge-live";
}
```

`badge-stopped` is red (`:81-84`, `var(--loss-red)`); `badge-live` is green (`:70-73`,
`var(--profit-green)`). `COMPLETED` is the only value treated specially, so:

| status written by the runner | badge colour shown |
|---|---|
| RUNNING | green |
| **HALTED** | **green** |
| **ABORTED** | **green** |
| COMPLETED | **red** |

The two states that mean "the pilot stopped itself" are indistinguishable in colour from a healthy
running session, and the only healthy terminal state is the one painted red. `grep -n
"kill_switch\|halt_reason\|abort_reason" src/quant_system/server/ui/live_dashboard.py` returns
**nothing** -- the reason string that the runner takes care to publish in three places is never
rendered. An operator watching the dashboard sees the word HALTED in a green badge and no reason.

This is the "dashboard" leg of the claim, and the dashboard file is in this batch (`416f560c`).

#### F18 (P2) -- the Stop button kills whatever process currently owns PID 39516, then reports "halted and reconciled to disk"

`scripts/serve_live_dashboard.py:153-159` falls back to `logs/paper_runs/runner.pid` when
`ACTIVE_PROCESS` is unset -- which it always is for a session started by the scheduler, and for any
dashboard restarted since the session began. The PID file is written on start (`:122-123`) and
**never removed**. It currently holds a PID from 2026-08-26:

```
$ cat logs/paper_runs/runner.pid
39516
```

`os.kill(39516, SIGTERM)` on Windows is `TerminateProcess`, not a signal. If PID 39516 has been
recycled, an unrelated process is terminated, `halted` is set True, and the endpoint answers:

```json
{"status": "HALTED", "message": "Trading session halted and reconciled to disk."}
```

Nothing was halted and nothing was reconciled. See F12 for the measurement that SIGTERM is not
deliverable on this platform.

#### F19 (P3) -- the halt fired and the book was liquidated anyway

Incidental but worth recording. In the run above the exits were submitted at interval 1 (pre-gap,
approved) and filled at interval 2 at the crashed price, and only then did the buys trip the switch.
Final state: `cash Rs 598617.40, 0 holding(s), realized Rs -241,662.60`, and `executed_rebalance`
True because 4 fills occurred -- so the halted, fully-liquidated session was also persisted as a
completed rebalance (`sessions_held = 1`, `last_rebalance_on = 2026-08-31`). This is F4 firing on a
second, independent path. `paper_portfolio.py:126-133` describes the opposite failure -- the halt
refusing the exits and retaining the losing book -- so both orderings are now reachable and neither
is chosen deliberately; which one happens depends on whether the price moves between the interval
that submits and the interval that fills.

### Claim 8 — The resolving AST test

**DEFEATED. Five ways, one of them an ordinary edit. P2.**

The detector (`tests/test_paper_pilot_carried_session.py:301-340` and the two tests at `:342-377`)
is a real improvement on the string search it replaced, and it does catch the plain regression. It
also fails **open** on every input it cannot resolve, and the number of such inputs is larger than
the mutation set found.

The structural weakness is one line. When resolution fails for any reason, `resolve` falls through
to `ast.unparse(expression)`, which for an unresolved `ast.Name` is **the identifier text itself**.
The third assertion is `"opening_marks" in seed or "marked" in seed`. The variable is called
`marked_opening_equity`. So any failure to resolve produces a string that satisfies the assertion by
containing the *variable's own name* -- precisely the "checking spelling rather than meaning" failure
the helper's docstring says it fixed, reintroduced as the fallback path.

REPRO (`probe_claim8.py`). The resolver logic is copied verbatim from
`tests/test_paper_pilot_carried_session.py:301-340`; only the source string is parameterised. Each
case seeds `initial_equity` from `portfolio.ledger_funding()` -- the exact defect the test exists to
catch -- expressed differently:

```
HONEST (today's code)                          seed='portfolio.cash + opening_marks_total' test PASSES
REGRESSION, plain assign (caught)              seed='portfolio.ledger_funding()'       test FAILS
REGRESSION via type annotation                 seed='marked_opening_equity'            test PASSES
REGRESSION via walrus                          seed='marked_opening_equity'            test PASSES
REGRESSION via tuple unpack                    seed='marked_opening_equity'            test PASSES
REGRESSION via 6-deep alias chain              seed='marked_x'                         test PASSES
REGRESSION via helper function                 seed='_baseline(portfolio)'             test FAILS
REGRESSION via later reassignment              seed='portfolio.ledger_funding()'       test FAILS

cost seed, honest value assigned AFTER         seed='portfolio.cash + opening_marks_total' test PASSES
```

Five defeats, by mechanism:

1. **Type annotation.** `marked_opening_equity: Decimal = portfolio.ledger_funding()` is an
   `ast.AnnAssign`, and `assignments` is built from `ast.Assign` only (`:327-333`). The name never
   resolves and the fallback supplies "marked". **This is the dangerous one**: this repository runs
   `mypy --strict` and the natural instinct of the next agent touching this block is to annotate the
   Decimal. One added `: Decimal` silently blinds the detector to the exact regression it guards.
2. **Walrus.** `(marked_opening_equity := portfolio.ledger_funding())` is an `ast.NamedExpr`, also
   not `ast.Assign`.
3. **Tuple target.** `marked_opening_equity, _spare = portfolio.ledger_funding(), 0` -- `node.targets`
   holds an `ast.Tuple`, and the comprehension's `if isinstance(target, ast.Name)` drops it.
4. **Alias depth.** `depth < 5` (`:336`) stops after five hops. A chain that terminates on any name
   containing "marked" returns that name unresolved and passes.
5. **Flow insensitivity.** `assignments` is a flat map over `ast.walk(enclosing)` with last-write-wins
   and no notion of position. A governor seeded from the cost figure, followed *later in the function*
   by an honest reassignment of the same variable, resolves to the honest one. The final case above
   is exactly that: the code seeds `initial_equity` from `ledger_funding()` and the test reports PASS.

Two further blind spots in the same family, not separately reproduced:

- `next(...)` at `:314-318` takes the **first** `PreTradeRiskGovernor` call in walk order. A second
  construction anywhere in the file is never examined.
- `test_a_risk_halt_is_reported_as_a_halt_not_a_success` (`:379-393`) and
  `test_the_scheduler_wrapper_propagates_the_exit_code` (`:396-410`) are raw `in source` substring
  checks. `'"kill_switch_active": governor.is_killed' in source` is satisfied by that text appearing
  in a comment, a docstring or unreachable code. They assert that a string exists, not that a
  behaviour holds -- and the behaviour is cheap to test directly, as `probe_claim7.py` shows.

SEVERITY: **P2.** No production defect, but a guard that fails open and is disabled by an ordinary
type annotation is worse than a guard known to be absent, because the next round will read a green
suite as evidence.

The brief's framing was right: "a mutation set chosen by the author tests what the author imagined."
Every mutant that was killed changed the *expression*. Every defeat above changes the *statement
form*, which the author did not imagine.

### Claim 9 — The peer session's token work

**PARTLY PROVEN. The preference order is sound and correctly implemented. Three consumers do not honour it, and one claim about the guard is false. P2 x3 + P3.**

*(This section contains a correction to my own first finding: see F13.)*

Preferring a year-long token over a daily one, and validating whichever was selected by the same
`exp` rule, is the right design. The resolution matrix behaves as the peer's record says
(`probe_tok3.py`, real `resolve_upstox_token` / `assert_upstox_usable`, env vars cleared first):

```
valid analytics + expired access                     -> PROCEEDS via UPSTOX_ANALYTICS_TOKEN
no analytics + valid access                          -> PROCEEDS via UPSTOX_ACCESS_TOKEN
empty-string analytics + valid access                -> PROCEEDS via UPSTOX_ACCESS_TOKEN
EXPIRED analytics + VALID access                     -> REFUSES
revoked-but-unexpired analytics (server would 401)   -> PROCEEDS via UPSTOX_ANALYTICS_TOKEN
```

#### F13 (P2) -- the scheduled refresh refuses to run when only the *preferred* token is configured, for an endpoint that needs no token at all

`UPSTOX_ANALYTICS_TOKEN` is read by exactly one file in the repository:

```
grep -rn UPSTOX_ANALYTICS_TOKEN --include=*.py .
  scripts/run_paper_pilot_session.py:103   _TOKEN_ENV_VARS = ("UPSTOX_ANALYTICS_TOKEN", "UPSTOX_ACCESS_TOKEN")
  tests/test_paper_pilot_carried_session.py  (4 sites)
```

Nothing in `src/` reads it. Both steps the scheduled session runs **before** the pilot demand the
daily token by name and refuse without it:

- `src/quant_system/data/upstox.py:96` -- `os.getenv("UPSTOX_ACCESS_TOKEN", "")`, with
  `is_authenticated` being `bool(self.access_token)` (`:101-102`);
  `scripts/ingest_all_market_data.py:383-384` raises
  `RuntimeError("UPSTOX_ACCESS_TOKEN is missing or invalid in environment.")`.
- `scripts/ingest_macro_regimes.py:40-42` -- same variable, same hard refusal.

```
UpstoxClient picks ACCESS  token: True
UpstoxClient picks ANALYTICS token: False
```

**I first reported this as a P1 on the reasoning that the access token expires at 03:30 IST tomorrow
(2026-09-01) and every historical fetch would 401. That reasoning is wrong and I withdraw it.**
`.env.example:31-35` claims the v3 historical endpoint needs no token whatsoever, and the claim is
true. Measured against the live API on the exact URL `UpstoxClient` builds
(`src/quant_system/data/upstox.py:193-198`):

```
NO Authorization header                  -> HTTP 200 candles=7
EXPIRED/bogus bearer (exp 2025-08-12)    -> HTTP 200 candles=7
garbage bearer                           -> HTTP 200 candles=7
UPSTOX_ACCESS_TOKEN (real)               -> HTTP 200 candles=7 newest=2026-08-28
UPSTOX_ANALYTICS_TOKEN (real)            -> HTTP 200 candles=7 newest=2026-08-28
```

Upstox ignores the bearer on this route entirely, so tomorrow's expired access token does **not**
break the refresh. The commit's headline survives on that path.

What remains is a real defect in the other direction. The guard is `bool(token)`, not validity, so
the failure is triggered by the variable being **empty** rather than expired. An operator who
follows this batch's own guidance -- `.env.example:56-58` "Preferred for unattended sessions",
`scripts/run_paper_pilot_session.py:140-142` "UPSTOX_ANALYTICS_TOKEN is preferred" -- and configures
only the analytics token cannot run the scheduled session at all. It dies in `refresh_bars` before
the pilot is ever launched, with a message naming a variable the endpoint does not require.

It also dies badly. `refresh_bars` uses `subprocess.run(command, check=True)`
(`scripts/run_scheduled_paper_session.py:191`) and `main()` has no handler, so the ingester's
`RuntimeError` surfaces as an uncaught `CalledProcessError` traceback; `refresh_macro` runs
in-process and surfaces the `RuntimeError` directly. Neither produces the `log("refusing: ...")`
diagnostic every other refusal in that file produces, and neither returns one of the file's
documented exit codes.

SEVERITY: **P2.** The documented, preferred configuration does not work end to end; the failure is
loud but uninformative, and it names the wrong cause.

RELATED, unverified: `.env.example:52-53` also states that with no token configured "the bundled
server and daily pipeline run on SYNTHETIC bars". The scheduled pipeline does not -- it raises. Not
probed for the bundled server.

#### F14 (P2) -- the dashboard forces the daily token, defeating the preference order

`scripts/serve_live_dashboard.py:85`:

```python
upstox_token = req_data.get("upstox_token") or os.getenv("UPSTOX_ACCESS_TOKEN", "")
...
if upstox_token:
    cmd.extend(["--upstox-token", upstox_token])
```

`resolve_upstox_token` treats an explicit argument as the winner
(`scripts/run_paper_pilot_session.py:115-116`), so a dashboard-launched session uses
`UPSTOX_ACCESS_TOKEN` regardless of the analytics token. `.env` sets both. From 03:30 IST tomorrow,
pressing Start on the dashboard aborts at `assert_upstox_usable` with "explicit --upstox-token
expired", while a token valid until 2027-08-23 sits unused in the same environment.

The dashboard file is in scope for this batch (`416f560c`) and was written by the peer session that
also wrote the token work, so the two halves of the same agent's change contradict each other.

Two smaller consequences of the same line: the bearer token is placed on a child process command
line, where it is readable by any local process (`wmic process get commandline`, Task Manager's
command-line column); and `run_paper_session` then re-exports it via
`os.environ["UPSTOX_ACCESS_TOKEN"] = upstox_token` (`scripts/run_paper_pilot_session.py:533-534`),
which is dead for resolution but mutates the process environment for anything else that reads it.

#### F15 (P2) -- "a revoked or mis-pasted analytics token is caught just as an expired access token is" is false

`scripts/run_paper_pilot_session.py:131-135` claims the guard catches revocation. It reads the `exp`
claim and makes no network call and no signature check
(`scripts/run_paper_pilot_session.py:144-168`). Proven above: a well-formed JWT with a future `exp`
and no server-side validity **PROCEEDS**. Revocation is caught only later, by the feed returning
nothing, which raises `QuoteFeedError` at the startup fetch -- a different mechanism, a different
message, and one that the partial-batch behaviour in F1 can suppress entirely if any chunk succeeds.

#### F16 (P3) -- the expiry message gives the wrong instruction in the case it was written for

With an expired analytics token and a valid access token the runner refuses with:

```
UPSTOX_ANALYTICS_TOKEN expired at 2025-08-12 17:30 IST, 383 days, 23:20:10.563511 ago.
Upstox standard access tokens expire at 03:30 IST the morning after they are issued.
Set UPSTOX_ANALYTICS_TOKEN instead -- it is free, one per user, and lasts about a year.
```

The message tells the operator to set the variable that is already set and just failed, describes
the *other* token class's expiry rule, and reports the age to microsecond precision. Operability
rule 11: it says what happened but not what to do next.

### Claim 10 — The single-source removal

**PROVEN that the fallback is gone. DISPROVEN that the consumers were fixed with it. P1.**

The removal is clean. `grep -rni "yahoo|REAL_NSE_ESTIMATE|query1.finance" scripts/ src/ tests/`
returns only prose in comments and the test that asserts their absence
(`tests/test_paper_pilot_carried_session.py:447-448`). No second quote source remains, no price
table, no Rs 1000.00 constant. `d802fdff` also genuinely fixed the instrument-key resolution:
measured now, **0 of 50 NIFTY50 and 0 of 500 NIFTY500 constituents lack an Upstox instrument key**
in `data/authorities/nse-all-listed-equities.csv`.

#### F23 (P1) -- two missing quotes out of 500 abort the entire session, on the condition the fetcher documents as tolerable

`scripts/run_paper_pilot_session.py:309-319` states the contract for a partial feed:

> Reported, not filled in. A partial cross-section is the caller's problem to judge ... but inventing
> a price for the absent names is how a fabricated quote reaches a decision.

Forty lines later the caller indexes the map unconditionally:

```python
scripts/run_paper_pilot_session.py:1049-1052
for sym in universe:
    quote_state = base_market[sym]
```

Three consumers still assume full coverage -- `:1052` (`returns_map`), `:1113` (the entry loop's
price lookup for a pick), `:1224` and `:1234` (top gainers/losers). `:756` is correctly guarded with
`if symbol in base_market`; the rest are not.

REPRO (`probe_claim10.py`) -- an otherwise ordinary session where the feed omits exactly two of
twenty symbols, which is how Upstox actually behaves:

```
KeyError: 'ITC'
Rebalance did NOT execute: 0 order(s) submitted, 0 filled, 0 rejected.
Orders Summary : 0 submitted | 0 filled | 0 cancelled | 0 rejected
PERSISTED sessions_held      = 11
```

OBSERVED: the session aborts before submitting a single order and trades nothing for the whole day.

**This already happened today.** `logs/paper_runs/scheduled_20260831_keyerror_aborted.log:22-27`:

```
2026-08-31 11:55:55 IST [WARNING] ...: Upstox returned no quote for 495 of 500 symbols; they are omitted, not estimated: 360ONE, 3MINDIA, ...
2026-08-31 11:56:33 IST [ERROR]   ...: Error during paper trading loop: '360ONE'
Traceback (most recent call last):
  File "D:\quant_system\scripts\run_paper_pilot_session.py", line 928, in run_paper_session
    quote_state = base_market[sym]
KeyError: '360ONE'
```

`d802fdff` repaired the *cause* of that particular occurrence (the ten hardcoded keys) and left the
crash in place. It is still at HEAD, five commits later.

EXPECTED: the same treatment the fetcher gives -- omit the name from the derived views, or refuse
the session with a typed error naming the coverage, not a `KeyError` on an arbitrary symbol.

BLAST: any morning the first quote batch loses a chunk. Today's log shows exactly that happening
twice between 13:29 and 14:21 on the real connection (F1); the only reason it was not fatal is that
those drops came *after* a complete startup fetch. A drop on the **first** fetch aborts the day.

It is also reachable with no network fault at all: a NIFTY500 reshuffle adds a name that is not yet
in `nse-all-listed-equities.csv`, `fetch_upstox_live_quotes` logs "No published Upstox instrument key
for 1 symbol(s); not requested", and every session from that morning on aborts at `:1052` until a
human refreshes the authority. Coverage is 500/500 today, which is the only thing standing between
the pilot and a daily abort.

SEVERITY: **P1.** Total loss of the trading session, recurring, triggered by a condition the code
above it explicitly declares acceptable. Loud since `cc92dd9a` (exit 10), so not silent -- but the
pilot simply does not run.

The two guards contradict each other in the same file, which is the signature the brief warned
about: `7d121c63` added the "omitted, not estimated" tolerance and nothing was changed downstream to
tolerate it.

### Claim 11 — Anything this batch introduced, overstated, or broke

**Gates green; four commit-level or comment-level claims are false. P2 x3 + P3 x3.**

Gates confirmed at `a6f3e6f1` with nothing modified:

```
.venv/Scripts/python.exe -m pytest -q      -> 1184 passed, 1 warning in 80.83s
.venv/Scripts/python.exe -m ruff check .   -> All checks passed!
.venv/Scripts/python.exe -m mypy src       -> Success: no issues found in 141 source files
```

Every finding in this report is invisible to all three.

#### F24 (P2) -- `44583ba4` reuses `14ec91da`'s subject verbatim and does none of what it says

The brief asked why the two carry identical subjects. `git diff --stat 14ec91da 44583ba4`:

```
 agent_context/work/completed/20260831-claude-round4-remaining-four.md |  99 +++++
 tests/test_paper_pilot_carried_session.py                             | 120 +++++------
 tests/test_paper_portfolio.py                                         |  50 +++++
 3 files changed, 219 insertions(+), 50 deletions(-)
```

`44583ba4` touches no production code. It is the mutation-hardened test replacement plus the
completed record. Its subject -- "mark equity for sizing, track executed rebalances, and surface risk
halts in status" -- describes `14ec91da`, which is where all three of those landed.

Anyone bisecting on the subject line, or reading `git log --oneline` to establish when the marked-
equity change happened, gets the wrong commit. Rounds two and four both found false commit messages;
this is the third instance of the same habit, and it is the one that makes commit boundaries
unreliable in the way the brief warned about.

#### F25 (P2) -- three code comments assert guarantees the code does not provide

Each is load-bearing: each is the stated justification for accepting a risk.

| Location | Claim | Status |
|---|---|---|
| `scripts/run_paper_pilot_session.py:311-313` | missing quotes are safe because "the coverage gate downstream already refuses a shrunk one" | **False.** No gate examines quote coverage; `MIN_CROSS_SECTION_COVERAGE` gates the bar-cache cross-section. See F1. |
| `scripts/run_paper_pilot_session.py:1100-1103` | "Exits above run first, in the same step, so the proceeds are available to fund these buys" | **False.** Exits are submitted in that step and fill on the next. Measured: Rs 38,000 allocation at interval 01 against Rs 199,500 at interval 02. See F5. |
| `scripts/run_paper_pilot_session.py:131-135` | "a revoked or mis-pasted analytics token is caught just as an expired access token is" | **False.** The guard reads `exp` and makes no network call; a well-formed JWT with a future `exp` and no server-side validity proceeds. See F15. |

A fourth is not false but is now out of date: `:249-250` "Re-fetching a symbol whose range is already
complete costs nothing" -- see F9.

#### F26 (P3) -- the peer collision left a duplicated statement and a comment that describes it

`scripts/serve_live_dashboard.py:147-148`:

```python
            halted = False
            halted = False
```

with the repair comment at `:166-168` explaining that `halted` "was assigned in both branches above
and never read". The repair reads the flag and left the duplicate line behind. Harmless, and ruff
does not flag it -- but it is the visible fingerprint of two agents editing one file, which is
exactly what the brief asked me to look for.

#### F27 (P3) -- `e853376a`'s message does not mention that it replaced the all-market ingestion summary

The commit body reads "Macro cache and ingestion summary refreshed by the scheduled pipeline". The
"ingestion summary" it refreshed belongs to a *different store*: 3,359 targets and 4,501,992 bars
replaced by 500 and 350,857 (F7). "Refreshed" is not a description of that. The auto-sync had no way
to know, which is the point: the sync commits whatever is in the tree and writes a summary from the
diffstat, so a destructive side effect arrives narrated as routine maintenance.

The same commit also added `quantos_ai_opinion.pdf` at the repository root, outside every documented
directory in `agent_context/DISK-LAYOUT.md` and `agent_context/README.md`.

#### F28 (P3) -- accreted duplicate module state in the runner

`scripts/run_paper_pilot_session.py` imports `os` twice (`:19`, `:179`), imports `NIFTY50_SYMBOLS`
twice (`:182`, `:330`), and assigns `ALLOWED_SYMBOLS` twice with different values (`:184` NIFTY50,
`:357` NIFTY500). `ALLOWED_SYMBOLS` has no reader anywhere in the repository:

```
grep -rn "ALLOWED_SYMBOLS" --include=*.py .   ->  only the two assignments in this file
```

Dead, and contradictory while dead. Ruff does not flag module-level rebinding. Noted because a
future reader could reasonably take `ALLOWED_SYMBOLS` for the enforced universe; it enforces nothing.

#### F29 (P2) -- `--capital 0` advances the portfolio and then dies without writing any report

`--capital` is `type=float` with no validation (`scripts/run_paper_pilot_session.py:1602`). Measured:

```
argparse accepts --capital 0    -> 0.0
argparse accepts --capital -5e6 -> -5000000.0
argparse accepts --capital nan  -> nan          (Decimal(str(nan)) -> NaN)
```

With `initial_cash = 0` the session runs, then:

```
    net_pnl_pct = float(net_pnl / initial_cash * Decimal("100.0"))     <- :1217, inside the loop
decimal.InvalidOperation: [<class 'decimal.DivisionUndefined'>]
Rebalance did NOT execute: 0 order(s) submitted, 0 filled, 0 rejected.
Portfolio saved: cash Rs 0.00, 0 holding(s), realized Rs 0.00, fees to date Rs 0.00
    return_pct = float(total_net_pnl / initial_cash * Decimal("100.0"))  <- :1374, OUTSIDE the try
decimal.InvalidOperation: [<class 'decimal.DivisionUndefined'>]
```

The first raise is caught by the loop handler and becomes an abort. The second is **after**
`save_portfolio` and outside every handler, so:

- `logs/paper_runs/portfolio_state.json` **is** written and `sessions_completed` advanced;
- no session JSON, no markdown report and no final status-file update are ever produced;
- `live_paper_status.json` is left at `RUNNING`;
- `main()` catches it at `:1718` and returns 2 -- not the abort code 10, and with no artifact
  naming the session at all.

A persisted state advance with no evidence record is the partial write the abort path exists to
prevent. `NaN` capital reaches the same arithmetic by a different route and is not probed further.

Pre-existing rather than introduced here -- the `total_equity - initial_cash` form predates this
batch -- but it is inside the abort machinery this batch built and no earlier round reports it.

#### Verified true, for the record

- `d802fdff` -- instrument keys resolve from the NSE authority. Measured: **0 of 50 NIFTY50 and 0 of
  500 NIFTY500** constituents lack a key.
- `7d121c63` -- no second quote source remains. `grep -rni "yahoo|REAL_NSE_ESTIMATE|query1.finance"`
  finds only prose and the test that asserts their absence.
- `cc92dd9a` -- the refresh genuinely fetches now (F7/F8/F9 are its consequences, not its failure).
- `run_scheduled_paper_session.cmd` -- `endlocal & exit /b %RC%` does propagate the code.
- The completed record `20260831-claude-round4-remaining-four.md` is honest about what it left open,
  including that a session refused at the exit-8 gate still writes no status file. That is true --
  `SystemExit(8)` at `:837` fires before `status_file` is even bound at `:905` -- and it is correctly
  listed as open rather than claimed closed.

## Coverage

Families run: input boundaries (F29), identity/authorization (F14, F18 -- the dashboard has no auth
of any kind), concurrency/ordering (F5, F19 -- and see NOT PROBED), failure injection (F1, F11, F12,
F13, F23), state machine (F4, F6, F20), scale (F9), money and counting (F1, F4, F20, F29), data
integrity (F7, F8, F10, F21), security surface (F14, F18), the human path (F11, F12, F17, F18),
operability (F3, F16, F17, F27), assumption archaeology (F5, F13, F15, F21, F24, F25, F28).

Probes attempted: 12 executable probes, of which 8 drive `run_paper_session()` end to end against a
stubbed Upstox transport with a controlled clock and a scratch output directory. 5 real HTTPS calls
to `api.upstox.com` (read-only market data, no orders, no writes). Full gate run: pytest, ruff,
mypy.

Targets: `scripts/run_paper_pilot_session.py`, `scripts/run_scheduled_paper_session.py`,
`scripts/run_scheduled_paper_session.cmd`, `scripts/ingest_all_market_data.py`,
`scripts/ingest_macro_regimes.py`, `scripts/serve_live_dashboard.py`,
`src/quant_system/server/ui/live_dashboard.py`, `src/quant_system/data/upstox.py`,
`src/quant_system/execution/paper_pilot.py`, `src/quant_system/execution/paper_portfolio.py`,
`src/quant_system/core/ledger.py`, `tests/test_paper_pilot_carried_session.py`,
`tests/test_paper_portfolio.py`, `tests/test_scheduled_paper_session.py`, `.env.example`, and the
real artifacts in `logs/paper_runs/` including the three preserved aborted attempts.

Nothing in the repository was modified except this report and
`agent_context/work/active/20260831-redteam-round5.md`. No writes to `data/evidence/`,
`logs/paper_runs/` or `.env`; every probe wrote to the session scratchpad and monkeypatched
`PORTFOLIO_STATE_PATH`.

## NOT PROBED

This is the section that matters most. Everything below is a known unknown, not a clean bill.

**Tomorrow's real run.** Every statement about 2026-09-01 09:00 IST is a prediction from
measurement, not an observation. I could not run the scheduled path end to end without writing to
`data/evidence/` and `logs/paper_runs/`. Specifically unobserved: whether `_is_current` produces a
tolerable refresh time for 500 symbols inside the pre-open window, whether Upstox rate-limits
(HTTP 429) a 500-symbol burst at 8 threads, and whether the CA authority mismatch (F8) changes any
persisted adjustment.

**The pre-open window.** F22 is reasoned from `enforce_market_hours=False` plus a 09:00 trigger and
is **not reproduced**. The only live session so far started at 12:17. What a real 09:00-09:15 poll
returns from Upstox -- previous close, pre-open equilibrium, or nothing -- decides both F22 and the
exact magnitude of F20, and I could not observe it.

**The Task Scheduler registration.** I read `run_scheduled_paper_session.cmd` and the brief's
statement that the task fires at 09:00 IST. The task definition itself is Windows configuration
outside the repository; its trigger, its "stop if runs longer than" setting and its
`LastTaskResult` behaviour after the `exit /b %RC%` repair are unverified.

**Concurrency on `portfolio_state.json`.** Not probed, and it is the largest untested hole.
`save_portfolio` (`src/quant_system/execution/paper_portfolio.py:252-263`) is atomic per write
(staging + `replace`) but there is no lock, no lease and no compare-and-swap on the state it read.
Two sessions -- the scheduler plus a dashboard Start, or two dashboard Starts, which
`/api/control/start` permits -- would both `load_portfolio` the same state and the second to finish
would silently discard the first's entire trading day. Nothing in the file format would show it. I
did not build the repro.

**Cross-site request forgery against the dashboard.** `/api/control/start` and
`/api/control/stop` take an unauthenticated POST and parse the body as JSON. A cross-origin
`fetch` with `Content-Type: text/plain` is a CORS "simple request" and is dispatched without a
preflight, so any page the operator visits could plausibly start a session with an
attacker-supplied `upstox_token` or trigger F18. The loopback bind in `416f560c` does not prevent
this. **Reasoned, not demonstrated** -- I did not build the attacker page.

**A real long session.** All eight session probes used a fake clock, zero-second sleeps and 3-9
intervals. Untested: 750 intervals of real wall-clock running, growth of `proposals_submitted` and
`engine.audit_log`, memory, file-handle churn from rewriting the status file every 30 seconds, and
whether the 246 KB log from today grows linearly.

**Statutory cost arithmetic.** `IndianMarketCostModel` and the Decimal rounding of STT, GST, stamp
duty and exchange charges were not examined at all. Every rupee figure in this report was taken from
the engine at face value.

**The Mizan model itself.** Feature computation, the shared kernel, `predict_scores`,
`select_top_fraction`, `refuse_extreme_rows` and the cross-section coverage arithmetic were exercised
only incidentally by running sessions. No adjudication of correctness. The model remains
`RESEARCH_ONLY` and unpromotable, which is out of this brief's scope.

**`clear_paper_halt.py`.** The documented recovery path from F20 was never run. Whether it actually
clears `risk_halted` and whether it can be run while a session holds the file is unverified.

**Evidence-store internals.** Whether `persist_verified_acquisition` creates a new dataset directory
per re-ingest (unbounded growth once F9's Monday refetch starts) or replaces in place, and whether
`_fast_index_catalog`'s last-write-wins over `dataset_dir.iterdir()` can select a stale manifest,
were reasoned about and **not measured**.

**The `NaN` capital path.** `--capital nan` is accepted and `Decimal(str(nan))` is `NaN`; where it
first surfaces was not traced. `--capital -5000000` is also accepted and untested.

**Windows `Popen.terminate()`.** I measured `os.kill(pid, SIGTERM)` directly
(`serve_live_dashboard.py:157`). `ACTIVE_PROCESS.terminate()` at `:150` is the same underlying
`TerminateProcess` per CPython, but I did not run it separately.

**Timezone and clock jumps.** IST is hardcoded as a fixed `UTC+05:30` offset, which is correct for
India, but nothing was tested across a machine clock change, a DST-observing host timezone, or a
session spanning midnight UTC.

**The peer's `agent_context` records.** `20260831-claude-upstox-token-semantics.md` and the two
NOTICE records were read for context. Their claims were not independently adjudicated except where
they overlap claim 9.

**Round four's remaining P2s and P3s, the auto-sync behaviour, `reset_session_peak` having no
caller, and the drawdown being evaluated only inside `evaluate_order`** were excluded by the brief as
known-open and were not re-examined -- except that F20 and F19 both turn out to depend on the last
of those, so its severity is higher than "known-open" suggests.
