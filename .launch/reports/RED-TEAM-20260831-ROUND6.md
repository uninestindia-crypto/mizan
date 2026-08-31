# Red Team round six — adjudication of the round-five repairs

STATUS: COMPLETE
DATE: 2026-09-01
ADJUDICATOR: Claude Code (independent; authored none of the work under test)
HEAD UNDER TEST: `d6fde28b`
COMMITS IN SCOPE: `739859a1` .. `d6fde28b`
BRIEF: `.launch/RED-TEAM-BRIEF-20260831-ROUND6.md`

## Verdict summary

| # | Claim | Verdict |
|---|---|---|
| 1 | F7, the summary file | PROVEN (narrow); 3 new findings |
| 2 | F1, the quote-batch failure | **PARTLY DISPROVEN** — 2 P1 |
| 3 | F23, the quote lookups | **DISPROVEN** — P1 Blocker |
| 4 | F4, the rebalance flag | **DISPROVEN** — P1 |
| 5 | F20, the daily peak anchor | **PARTLY DISPROVEN** — P1 |
| 6 | The mutation sets themselves | **DISPROVEN** — 13/13 survive |
| 7 | Concurrency on `portfolio_state.json` | **CONFIRMED** — P1 |
| 8 | Tomorrow's 09:00 hold session | **WALKED** — will not run; P1 |
| 9 | What this batch introduced, overstated, or broke | 1 regression, 4 overstatements |

### The one-paragraph verdict

Four of the five fixes do what their commit messages say at the level of the specific case that was
reported. None of them is guarded: **13 mutants written independently of the author, 13 survivors**,
including the author's own claimed-killed F20 mutant with the value bound to a local one line above
the call. Two of the five are wrong beyond their reported case — F23 left a fifth and sixth consumer
in the ledger that crashes harder than the one it fixed, and F4 catches the 100%-cash corner of a
failure that also occurs at 76%. **Round five found 5 new P1s; this round finds 7.**

Separately, and independent of this batch: the 09:00 scheduled run will not start, because the
pre-open refresh authenticates with the daily token, which expires at 03:30 the same morning.


## Findings

**7 P1, 10 P2, 4 P3.** Round five found 5 new P1s; this round finds 7. The pattern has not converged.

Every probe script referenced below is in the session scratchpad and writes only there. Nothing
under `data/evidence/`, `logs/paper_runs/` or `.env` was modified.

---

### P1

**R6-04 — F23 has a fifth and sixth consumer, in the ledger, and it escapes the abort handler**
`scripts/run_paper_pilot_session.py:1233`, `:1388`; `src/quant_system/core/ledger.py:552-557`;
`src/quant_system/execution/paper_pilot.py:214-237`
REPRO `scratchpad/f23_fifth.py` — a copy of the real 97-holding `portfolio_state.json`, one carried
name omitted from the feed.
OBSERVED `LedgerInvariantViolation: cannot mark AADHARHFC to market`. Raised at `:1233` (caught,
session marked ABORTED) and again at `:1388`, which is **outside** the `try`, so it escapes
`run_paper_session`. `save_portfolio` is never reached, no session JSON or markdown is written
(`report files written: []`), and any fills executed earlier in the step are discarded.
EXPECTED The same treatment F23 gave the other four sites: a carried name with no quote is skipped
or marked to cost, and said so, not indexed.
BLAST Tomorrow's 09:00 session. Two of five hundred names were unquoted on 2026-08-31; 97 of the
500 are now held. Each occurrence loses a whole trading day and repeats every morning until the
exchange happens to quote that name again.

**R6-14 — the 09:00 refresh authenticates with a token that expires at 03:30 that morning**
`src/quant_system/data/upstox.py:96,100-102`; `scripts/ingest_all_market_data.py:384`;
`scripts/ingest_macro_regimes.py:40`; `scripts/run_scheduled_paper_session.py:257,269-276`
REPRO `scratchpad/claim8_token.py`.
OBSERVED The pilot resolves `UPSTOX_ANALYTICS_TOKEN` (valid to 2027-08-23). The refresh resolves
`UPSTOX_ACCESS_TOKEN`, whose expiry claim is **2026-09-01 03:30 IST** — before the 09:00 trigger.
`UpstoxClient.is_authenticated` is `bool(self.access_token)`, presence only. All 500 acquisitions
401, the cache stays at 2026-08-27, `missed = 2 > MAX_MISSED_SESSIONS = 0`, `main()` returns 4 and
no paper session runs.
EXPECTED `88b78b9d` — "the pilot survives a morning you forget to refresh the token" — to cover
the step that gates the pilot. Or, at minimum, an expiry check at the ingester's front door rather
than a 500-way 401 storm.
BLAST Every weekday morning until someone re-pastes the daily token by hand. The schedule is not
unattended.

**R6-17 — no lock and no compare-and-swap on `portfolio_state.json`; the second writer discards the
first's whole trading day**
`src/quant_system/execution/paper_portfolio.py:253-263`;
`scripts/run_paper_pilot_session.py:675,1470`; `scripts/serve_live_dashboard.py:117-124,153-157`
REPRO `scratchpad/c7_setup.py` plus two `scratchpad/c7_worker.py` processes.
OBSERVED Both sessions read `sessions_completed 10`; both executed 8 fills; the final book records
`sessions_completed 11` and `total_fees 2811.90` — one session's worth. Sixteen fills happened,
eight are in the ledger, and both session reports remain on disk. No error, no warning; each
session reconciles internally, so nothing detects it. Two sessions are reachable three ways: the
scheduled run is never in the dashboard's `ACTIVE_PROCESS`; `ACTIVE_PROCESS` dies with the dashboard
while `runner.pid` (currently a **dead** PID) is read only by the stop endpoint; and the runner has
no admission control of its own.
EXPECTED An exclusive claim held for the session, or a compare-and-swap on the loaded state's hash
at save time — the hash already exists and is already computed.
BLAST Silent loss of a full trading day's accounting whenever two sessions overlap.

**R6-07 — a rebalance that fills one entry of four, leaving 76% cash, is recorded as executed**
`scripts/run_paper_pilot_session.py:1425-1449`
REPRO `scratchpad/f4_partial.py`.
OBSERVED `fills: 5  open: {'LT': 237}  cash as a share of equity: 76.3%`, Rs 1,115.75 of statutory
cost paid, `sessions_held` reset to 1, `last_rebalance_on` stamped, `[PAPER PILOT SUCCESS]`. The
book will hold one name and three-quarters cash for ten sessions.
EXPECTED The commit's own standard — "Going to cash is not a rule the screen contains, so it
cannot be an outcome that counts as executing one" — applied to partial cash positions, not only
to 100%.
BLAST Every rebalance where entries are systematically blocked (unaffordable names, cash-buffer
rejections, a mid-rebalance halt). Silent.

**R6-05 — 13 independently written mutants, 13 survivors, across all five fixes**
REPRO `scratchpad/mut_lib.py`, `mut_run.py`, `mut_validate.py`, `mut_f23_runtime.py`.
OBSERVED `MUTANTS RUN: 13   SURVIVED: 13   KILLED: 0`, with the same harness passing on unmutated
HEAD and killing all 12 of the author's own mutants. M-F23-1 was executed and restores the exact
2026-08-31 `KeyError`. M-F20-1 is the author's own claimed-killed "boot-time figure" mutant with the
value bound to a local one line above the call.
EXPECTED Mutation evidence that constrains behaviour. Four of the five tests assert on rendered
source text, so any mutation that preserves the strings passes.
BLAST The stated evidence for F7, F23, F4 and F20 supports "not reverted by deletion", not "guarded".

**R6-01 — a chunk lost to HTTP 200 is not a failed chunk, so the poll succeeds and the retry budget
resets**
`scripts/run_paper_pilot_session.py:266`, `:322-327`, `:1020`
REPRO `scratchpad/f1_live.py`.
OBSERVED With one of two chunks returning HTTP 200 and either an Upstox error envelope or
`{"status":"success","data":{}}`: `RETURNED NORMALLY, 100/150 symbols`. Those symbols keep whatever
`base_market` last held, indefinitely, and `consecutive_quote_failures = 0` runs on the poll that
lost them.
EXPECTED The commit's own rule — "A chunk that errored tells us nothing about its symbols and must
be retried" — applied to a chunk whose response was not usable, not only to one that raised.
BLAST The exact round-five F1 scenario, reachable on the repaired code. Silent.

**R6-10 — the daily drawdown baseline is "since this process started", so a restart resets the 4%
rule**
`scripts/run_paper_pilot_session.py:1036-1049`
REPRO `scratchpad/f20_restart.py`.
OBSERVED Anchors at 1,000,000 / 965,000 / 931,000 / 898,000 across four starts on the same falling
day. A 10.2% intraday decline is measured as three separate sub-4% ones.
EXPECTED A baseline tied to the trading day, not the process. Three sessions were started and
abandoned on 2026-08-31 alone, so this is the observed operating mode.
BLAST The 4% daily kill switch is disarmed by exactly the operator action an abort invites.

---

### P2

**R6-03 — `test_a_partial_quote_batch_failure_fails_the_poll` drives a total failure, not a partial
one.** `tests/test_paper_pilot_carried_session.py:677-681`. Both branches of
`one_good_chunk_then_a_timeout` raise; there is no good chunk. Mutant M-F1-1
(`if failed_chunks and not results:`) passes it and reproduces the defect exactly. The test that
gates F1 cannot see F1's own scenario.

**R6-02 — a quote object with `last_price: 0`, or with no `last_price` at all, becomes a real
exchange price of Rs 0.00.** `scripts/run_paper_pilot_session.py:273` uses
`.get("last_price", 0)`, and the result is stamped `"source": "UPSTOX_LIVE_FEED"`. There is no
validation of any field in the payload. `scratchpad/f1_live.py` shows both variants. Escalates to
P1 if the affected symbol is **held**: the marked equity, the risk baseline and the session report
all silently lose that position's value.

**R6-15 — one zero-priced name anywhere in the 500 aborts the session, and the two-minute session
still advances the hold clock.** `scratchpad/claim8_walk.py` variant C:
`aborted=True ValueError: Depth price must be positive, got -0.02`, then
`persisted: sessions_completed 2 sessions_held 2`. `OrderBookSnapshot.from_levels` correctly refuses
a negative bid; the runner has no guard before it. Ten such mornings consume the model's whole
ten-session hold without the book ever having been marked to a real close.

**R6-06 — the equity the risk governor divides by marks unquoted holdings to cost.**
`src/quant_system/execution/paper_pilot.py:411-413` and `:589-592`:
`self._price_cache.get(p.symbol, p.average_price)`. That is the substitution
`Ledger.get_portfolio_snapshot` explicitly refuses three files away, in the same code base, with a
comment saying why.

**R6-08 — `holds_the_selection` blesses a book 90% in one name as an executed rebalance.**
`scripts/run_paper_pilot_session.py:1430` and `:1187-1188`. `scratchpad/f4_weights.py`:
`BHARTIARTL qty 900 ~90.0% of equity` against a declared `max_position_weight = 0.30`, zero orders
submitted, so `evaluate_order` — the only enforcement point — never runs. The entry loop only acts
when `current_held == 0`, so weights are never trimmed or topped up and drift is permanent. The
strategy that was measured re-equal-weights at every rebalance.

**R6-11 — an unquoted holding contributes zero to the daily anchor.**
`scripts/run_paper_pilot_session.py:1037-1047`. `scratchpad/f20_late.py`:
`anchored at Rs 720000.00` where true marked equity is Rs 960,000. The code 250 lines above
(`:805`) handles the identical condition with `opening_marks.get(symbol, holding.average_cost)`.
Currently masked by R6-04; live the moment R6-04 is fixed with a fallback.

**R6-16 — the macro ingester overwrites a good cache on any HTTP 200, including one with no
candles.** `scripts/ingest_macro_regimes.py:65-84`. The write is unconditional after `urlopen`
returns; a 200 whose `data.candles` is empty replaces `macro_INDIAVIX.json` with an empty candle
list and prints `0 daily bars fetched`. `macro_covers` is then permanently false and the scheduled
run refuses at exit 5 until someone re-ingests. A 401 is safe; a 200 is not.

**R6-19 — one failed chunk at startup now loses the whole day, with no retry.**
`scripts/run_paper_pilot_session.py:602` against `:998-1019`. `scratchpad/c9_startup.py`: chunk 3
of 5 timing out returned 300/500 at `739859a1` and raises at HEAD. The five-poll retry budget
exists in the loop and not at startup, and a handshake timeout is the failure that actually ended
the 2026-08-31 session.

**R6-09 — the flat-book alarm states a financial event that did not occur.**
`scripts/run_paper_pilot_session.py:1444-1449`. On a first session that started flat and could not
enter, `scratchpad/rebal_probe.py` produced "The book is FLAT after a rebalance: every exit filled
and no entry did. A full exit round trip was paid" — no exit filled and nothing was paid. On an
unattended schedule this is the operator's alarm text.

**R6-22 — the dashboard writes the Upstox bearer token to its log and onto a command line.**
`scripts/serve_live_dashboard.py:112-115`:

```python
            if upstox_token:
                cmd.extend(["--upstox-token", upstox_token])

            logger.info("Starting background paper pilot: %s", " ".join(cmd))
```

The token is appended to `cmd` **before** the log statement, so `logging.basicConfig(...)` at `:42`
emits the whole bearer token in plaintext — to stderr, and to a file wherever the dashboard is
launched with redirection. It is also on the child process's command line, readable from the
process table by any local process. The default token here is the long-lived
`UPSTOX_ANALYTICS_TOKEN`-class credential, which is valid for a year. Binding to loopback (`:187`,
`:207-209`) is already handled and is not the issue.

---

### P3

**R6-12 — `test_the_all_market_summary_still_covers_the_whole_market` cannot catch a code
regression.** `tests/test_scheduled_paper_session.py:185-195`. It asserts on a committed data file
and never executes `refresh_bars`. It will pass indefinitely while the code that destroys the file
is reintroduced, and only fail after the damage has been committed.

**R6-13 — `refresh_bars` still lets `--corporate-actions-dir` default into the all-market cache.**
`scripts/run_scheduled_paper_session.py:185-200`; `scripts/ingest_all_market_data.py:515-523`. The
2026-08-31 log records it: `Corporate Actions Dir : ...\all-market-20160822-20260821\corporate-actions`.
Currently harmless — all 500 NIFTY500 CA files exist there and parse as lists (measured:
`non-list / unreadable: 0`), so every fetch is a cache hit. A new index constituent absent from the
3,359-name authority would have its 3-year CA record written into the 10-year store, where
`build_corporate_action_authority` hardcodes `effective_from=2016-08-22, effective_to=2026-08-21`.

**R6-20 — a false statement of mechanism in the comment above the entry loop.**
`scripts/run_paper_pilot_session.py:1179-1181` says the exits above run first in the same step so
their proceeds fund the buys. `submit_proposal` only stages (`paper_pilot.py:500-522`); fills occur
in the next step's `process_quote`. Pre-existing at `739859a1`; self-correcting over later steps.

**R6-21 — two new per-interval log statements.** `:1121` and `:1193`, up to roughly 780 repetitions
each per session at the scheduled 30-second interval. The 2026-08-31 log is already 246 KB.

## Claim 1 — F7, the summary file

**VERDICT: PROVEN in its narrow claim; the guard around it is weaker than stated, and a second
default still points into the all-market cache.**

### What holds

`scripts/run_scheduled_paper_session.py:197-199` does now pass the flag:

```python
("--summary-file",)
(str(BARS_CACHE / "ingestion-summary.json"),)
```

The restored file is **byte-identical** to `e853376a~1`, not merely the right length:

```
orig sha a6c166be2a2285608342bbbe99bb0f45e9efc1d08b369d6fd4f53c311604d0ff
head sha a6c166be2a2285608342bbbe99bb0f45e9efc1d08b369d6fd4f53c311604d0ff
identical bytes: True
identical json: True
```

Content is right too, not just length: `total_targets 3359`, `total_bars_ingested 4501992`,
`results len 3359`, `universe_csv .../nse-all-listed-equities.csv`,
`updated_at 2026-08-24T18:12:46`. That is the all-market ingest, restored.

### F7-M1 — the author's own mutant set misses the obvious one (P2)

See Finding **R6-05**. The shipped test asserts `"BARS_CACHE" in destination` on the *unparsed
source text*. A destination that names `BARS_CACHE` and resolves back onto the destroyed file
passes it.

### F7-M2 — the second test cannot ever catch a code regression (P3)

See Finding **R6-12**.

### The other default that was not fixed (P3, latent)

`refresh_bars` passes `--universe-csv`, `--cache-root` and now `--summary-file`. It does **not**
pass `--corporate-actions-dir`, whose default (`scripts/ingest_all_market_data.py:515-523`) is

```
data/evidence/market-cache/all-market-20160822-20260821/corporate-actions
```

— the same all-market cache F7 was about. See Finding **R6-13**. Not currently exploitable: all
500 NIFTY500 CA files exist there and parse as lists, so today's run is a pure cache hit
(measured: `non-list / unreadable: 0`).

## Claim 2 — F1, the quote-batch failure

**VERDICT: PARTLY DISPROVEN. The transport path is fixed. The HTTP-200 path is not, and it is
the same defect wearing a 200.**

The brief asked directly: *"Can a feed return HTTP 200 with empty or garbage payloads indefinitely
and never trip either path?"* The measured answer is **yes**. Findings **R6-01** and **R6-02**.

`scripts/run_paper_pilot_session.py:266` is the gate:

```python
                if data.get("status") == "success" and "data" in data:
```

Anything that fails that predicate falls out of the `try` with **no exception**, so the chunk is
never appended to `failed_chunks`, the poll returns normally, and
`consecutive_quote_failures = 0` executes at line 1020. The symbols in that chunk keep whatever
`base_market` last held.

Measured against shipped HEAD, one of two chunks poisoned (`scratchpad/f1_live.py`):

```
chunk 1 -> HTTP 200 with an Upstox error envelope
  -> RETURNED NORMALLY, 100/150 symbols. chunk-1 prices sample: chunk 1 absent
chunk 1 -> HTTP 200, status success, empty data map
  -> RETURNED NORMALLY, 100/150 symbols. chunk-1 prices sample: chunk 1 absent
chunk 1 -> HTTP 200, a bare JSON list (garbage of the right MIME type)
  -> RAISED: 1 of 2 quote batches failed; 100 of 150 symbols returned. First error: 'list' ob
chunk 1 -> HTTP 200, quote objects with no last_price at all
  -> RETURNED NORMALLY, 150/150 symbols. chunk-1 prices sample: [('SYM100', '0'), ('SYM101', '0')]
chunk 1 -> HTTP 200, last_price 0 (a pre-open scrip that has not traded)
  -> RETURNED NORMALLY, 150/150 symbols. chunk-1 prices sample: [('SYM100', '0'), ('SYM101', '0')]
```

Two of those five are the exact round-five F1 scenario reproduced on the repaired code: a whole
chunk lost, the poll counted as a success, the retry budget reset, stale prices marking the book.
Two more are worse — a fabricated **Rs 0.00** price labelled `"source": "UPSTOX_LIVE_FEED"`, which
is the fabricated-price class F23 removed, reintroduced through the payload instead of a table.

### The transport half does work

The genuinely-partial transport case behaves as the commit says:

```
  shipped HEAD: raised QuoteFeedError -- 1 of 2 quote batches failed; 100 of 150 symbols returned.
```

and the `continue` is real — the second batch is still attempted.

### The shipped test does not test the thing it is named for (P1 test defect, R6-03)

`tests/test_paper_pilot_carried_session.py:677-681`:

```python
    def one_good_chunk_then_a_timeout(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("_ssl.c:1015: The handshake operation timed out")
        raise TimeoutError("_ssl.c:1015: The handshake operation timed out")
```

Both branches raise. There is no good chunk. The test named
`test_a_partial_quote_batch_failure_fails_the_poll` never drives a partial failure — it drives a
total one, which the pre-fix code also refused. See **R6-03** for the surviving mutant that proves
the consequence.

### Every chunk failing on the very first poll

Tested by reading the two call sites. Startup (`:602`) is outside any handler, so it propagates to
`main()` -> `return 2` before `load_portfolio` at `:675` — nothing is persisted, which is correct.
Inside the loop the first poll failing takes the `continue` at `:1019` **before** the anchor block
at `:1036`, so `daily_peak_anchored` stays `False` and the daily baseline remains the boot-time
figure until the first poll that succeeds. If polls 1-5 all fail the session aborts with the
baseline never anchored. Loud, and the book is still persisted. No finding.

## Claim 3 — F23, the quote lookups

**VERDICT: DISPROVEN. There is a fifth consumer, it is two lines of code, and it crashes harder
than the one that was fixed.** Finding **R6-04**, and it is the Blocker for tomorrow's 09:00 run.

F23 fixed four *runner-local* `base_market` lookups. It did not touch the two places the runner
hands its price map to the **ledger**, which refuses by design to mark a held position it has no
price for (`src/quant_system/core/ledger.py:552-557`):

```python
            price = current_prices.get(sym)
            if price is None:
                raise LedgerInvariantViolation(
                    f"cannot mark {sym} to market: no price supplied for a held position of "
```

`snapshot_prices` and `final_prices` are both built from `base_market`
(`run_paper_pilot_session.py:1232`, `:1382`), so a **carried holding absent from the startup quote
poll** is absent from both. `carry_in_positions` does not seed `_price_cache`
(`paper_pilot.py:214-237`; `_price_cache` is written only at `:553`, `:555`, `:816`), so the
fallback path does not save it either.

### Reproduction — real state file, real code, one name omitted

`scratchpad/f23_fifth.py` copies **today's real `logs/paper_runs/portfolio_state.json`** (97
holdings) to scratch, points `PORTFOLIO_STATE_PATH` and `output_dir` at scratch, and omits exactly
one held name from the feed — the 2026-08-31 `360ONE` condition:

```
carried holdings: 97
omitting exactly one carried name from the feed: AADHARHFC
... Quotes cover 97 of 98 names this step; the rest are omitted from the intraday panels, not priced.
... Session ABORTED during the trading loop: cannot mark AADHARHFC to market: no price supplied for
    a held position of 20; refusing to substitute its average price
  File "D:\quant_system\scripts\run_paper_pilot_session.py", line 1233, in run_paper_session
    snap = engine.get_portfolio_snapshot(timestamp=loop_now, current_prices=snapshot_prices)

*** run_paper_session RAISED OUT: LedgerInvariantViolation: cannot mark AADHARHFC to market ...
  File "D:\quant_system\scripts\run_paper_pilot_session.py", line 1388, in run_paper_session
    reconciliation = engine.end_session(timestamp=final_now, close_prices=final_prices)

state file advanced? 1
report files written: []
```

The second raise is the serious one. `:1388` is **outside** the `try/except` that the abort
handling was built around, so the exception escapes `run_paper_session` entirely:

- `save_portfolio` (`:1470`) is never reached. The book does not advance; `sessions_held` stays 1.
- No session JSON, no markdown report — `report files written: []`.
- Any exits and entries filled earlier in the step are **discarded**. On a rebalance day the pilot
  pays a real exit round trip in the ledger and then throws the ledger away.
- `main()` catches and returns 2. The condition repeats every morning until the exchange happens to
  quote that one name again, and each repeat loses that day.

All four F23 assertions pass throughout — `tests/test_paper_pilot_carried_session.py 22 passed`.
They are assertions about four `base_market` lookups; the fifth consumer never touches
`base_market` by name.

### The author saw this exact condition forty lines earlier and handled only half of it

`run_paper_pilot_session.py:790-800` already knows carried names can be unquoted:

```python
    unpriced = sorted(set(portfolio.holdings) - set(opening_marks))
    if unpriced:
        logger.warning(
            "No opening quote for %d carried name(s); their cost basis is used in the risk "
            "baseline: %s",
```

The risk baseline was given a documented fallback. The snapshot and the reconciliation were not.

### A sixth site, silent rather than loud (P2, R6-06)

`paper_pilot.py:411-413` and `:589-592` compute the equity the **risk governor** divides by using
`self._price_cache.get(p.symbol, p.average_price)` — marking an unquoted holding to **cost**, which
is the substitution `Ledger.get_portfolio_snapshot` refuses three files away. See **R6-06**.

## Claim 4 — F4, the rebalance flag

**VERDICT: DISPROVEN. The fix catches only the 100%-cash corner of the failure it describes. At
76% cash it passes silently.** Findings **R6-07** (P1) and **R6-08** (P2).

```python
    executed_rebalance = (
        rebalancing and bool(engine.positions) and (bool(entry_fills) or holds_the_selection)
    )
```
`scripts/run_paper_pilot_session.py:1431-1433`

### Attack 1 — a partial entry fill (R6-07, P1)

The commit's own description of the defect: *"A rebalance where every exit filled and every entry
was skipped as unaffordable left the pilot 100% in cash, having paid a full exit round trip -- and
recorded it as a completed rebalance."* `bool(entry_fills)` fires on **one** fill.

`scratchpad/f4_partial.py` runs the real `run_paper_session` on a real Mizan ranking, book holding
four names not in the selection, three of the four picks priced above the equal-weight allocation:

```
  BHARTIARTL: skipped, 1 share costs Rs 500000.00 against an allocation of Rs 237500.00
  RELIANCE: skipped, 1 share costs Rs 500000.00 against an allocation of Rs 237500.00
  HDFCBANK: skipped, 1 share costs Rs 500000.00 against an allocation of Rs 237500.00
Portfolio saved: cash Rs 761345.01, 1 holding(s), realized Rs -2209.12, fees to date Rs 2075.75
Orders Summary       : 6 submitted | 5 filled | 0 cancelled | 1 rejected

=========== F4 RESULT ===========
fills: 5 open: {'LT': 237}
equity: 998345.01  final cash: 761345.01
fees paid this session: 1115.75
PERSISTED sessions_held: 1  last_rebalance_on: 2026-09-01  holdings: ['LT']
cash as a share of equity: 76.3%
```

Four exits filled, one entry filled, Rs 1,115.75 of statutory cost paid, and the pilot is left
**one name and 76.3% cash** — a portfolio the screen never models — with `sessions_held` reset to 1
and `last_rebalance_on` stamped. It will hold that for the next ten sessions. No warning fires; the
`if rebalancing and not executed_rebalance` branch is not entered and the run reports
`[PAPER PILOT SUCCESS]`.

### Attack 2 — sets match, weights do not (R6-08, P2)

The brief's own question. `holds_the_selection` is `set(engine.positions) == set(mizan_picks)`,
which is blind to size, and the entry loop only acts when `current_held == 0`
(`:1187-1188`) so it never trims or tops up.

`scratchpad/f4_weights.py`, book holding exactly the selection with 90% in one name:

```
=========== F4 weight-drift RESULT ===========
fills: 0 rejected: 0
open: {'BHARTIARTL': 900, 'HDFCBANK': 20, 'LT': 20, 'RELIANCE': 20}
PERSISTED sessions_held: 1 last_rebalance_on: 2026-09-01
   BHARTIARTL   qty  900  ~ 90.0% of equity
   HDFCBANK     qty   20  ~  2.0% of equity
   LT           qty   20  ~  2.0% of equity
   RELIANCE     qty   20  ~  2.0% of equity
```

A rebalance is recorded as executed on a book holding 90% of equity in one name, against a declared
`max_position_weight = 0.30`. Zero orders are submitted, so `evaluate_order` — the only place the
weight limit is enforced — is never reached. The measured strategy re-equal-weights at every
rebalance; this one re-affirms whatever drift has accumulated and calls it a rebalance.

### Attacks that the fix does hold against

- **A rebalance that legitimately ends flat.** `bool(engine.positions)` is sound: `DecimalLedger`
  pops a position at zero quantity (`core/ledger.py:487,495`), so a fully exited book is genuinely
  falsy. The zero-quantity-position bypass does not exist.
- **A book holding names outside the selection.** Set inequality catches it; exits are submitted
  and `holds_the_selection` stays False until they fill.
- **`top_picks` empty.** Exits are gated on `top_picks` (`:1155`), so nothing is sold and
  `holds_the_selection` is False because `bool(mizan_picks)` is False.

### One more, from the same run (R6-09, P2)

The flat-book alarm states a financial event that did not occur. On a *first* session that started
flat and could not enter, `scratchpad/rebal_probe.py` produced:

```
Rebalance did NOT execute: 0 order(s) submitted, 0 filled (0 of them entries), 0 rejected,
  0 position(s) held at close. The hold clock is not reset.
The book is FLAT after a rebalance: every exit filled and no entry did. A full exit round trip was
  paid to reach a state the screen never models.
```

No exit filled and no round trip was paid — the book was flat when the session opened. See
**R6-09**.

## Claim 5 — F20, the daily peak anchor

**VERDICT: PARTLY DISPROVEN. The anchor is placed correctly and `reset_session_peak` composes
correctly with the carried peak. But the baseline is "since this process started", not "the day" —
so a restart resets the 4% rule, and an unquoted holding silently shrinks the baseline by its whole
value.** Findings **R6-10** (P1) and **R6-11** (P2).

### What holds

- `reset_session_peak` (`src/quant_system/risk/governor.py:95-99`) sets the daily peak outright and
  only ever **raises** the all-time peak. It cannot lower the carried high-water mark. The
  interaction the brief asked about is correct.
- The call at `:1036-1049` genuinely precedes both order loops (`:1155`, `:1186`), so the exit —
  the first order of a rebalance — is governed by the anchored baseline.
- A failed first poll anchors **late**, not never. Measured (`scratchpad/f20_late.py`):
  ```
  no poll failures        : anchored at Rs 960000.00
  first 3 polls fail      : anchored at Rs 960000.00
  ```
  The `continue` at `:1019` precedes the anchor block, `daily_peak_anchored` stays `False`, and the
  first poll that succeeds anchors.

### Attack 1 — a restart moves the baseline down with the market (R6-10, P1)

The anchor is "the first live mark **this process** saw". Three sessions were started and abandoned
on 2026-08-31 alone (`logs/paper_runs/scheduled_20260831_fallback_aborted.log`,
`_keyerror_aborted.log`, `_pre_pnl_fix.log`), so restarts are the observed norm on this path, not a
hypothetical.

`scratchpad/f20_restart.py`, a book of 4 x 250 shares, previous close Rs 1000:

```
Book: 4 names x 250 shares. Yesterday's close Rs 1000.00 -> equity Rs 1,000,000.

09:01 session 1, opens flat        : mark Rs 1000.00  -> daily peak anchored at Rs 1000000.00
09:45 RESTART after a -3.5% morning: mark Rs 965.00   -> daily peak anchored at Rs 965000.00
10:30 RESTART after another -3.5%  : mark Rs 931.00   -> daily peak anchored at Rs 931000.00
11:15 RESTART after another -3.5%  : mark Rs 898.00   -> daily peak anchored at Rs 898000.00

Cumulative move from yesterday's close: -10.2%
```

Each restart re-anchors at the depressed mark, so the 4% window reopens from there. A 10.2%
intraday decline is measured as three separate sub-4% ones. The commit title reads *"an overnight
gap is not a daily drawdown"*; the daily rule now measures **since this process booted**, which on a
restarted day is not the day either. This is the fourth consecutive round in which the daily rule
measures something other than the day.

(Stated precisely: on a *hold* session no order is submitted, so `evaluate_order` — the only caller
of the drawdown check — never runs at all; that is round five's known-open item. What this
reproduction establishes is the **baseline value**, which is what a rebalance day's first order
would be judged against.)

### Attack 2 — an unquoted holding contributes zero to the anchor (R6-11, P2, latent)

`:1037-1047` sums only `if symbol in base_market`, with no fallback:

```python
                            Decimal(position.quantity) * base_market[symbol]["price"]
                            for symbol, position in engine.positions.items()
                            if symbol in base_market
```

Forty lines' worth of code above it (`:801-810`) faces the identical condition and uses
`opening_marks.get(holding.symbol, holding.average_cost)` — a documented cost-basis fallback. The
anchor drops the name entirely:

```
1 of 4 holdings unquoted : anchored at Rs 720000.00 (true marked equity is Rs 960000.00;
                           the unquoted name contributed 0, not its cost)
```

A 25% understatement of the daily baseline, which makes the daily drawdown check strictly weaker.
Currently **masked** by R6-04 — the same missing quote kills the session at `:1233` a few lines
later — so this becomes live the moment R6-04 is repaired by giving the snapshot a fallback.

### Gap up, and starting mid-day

Anchoring above `marked_opening_equity` on a gap up is correct behaviour for a high-water mark and
is not new: `update_peaks` already raised the daily peak on the first order. Starting mid-day is the
same mechanism as Attack 1 and is covered there.

## Claim 6 — The mutation sets themselves

**VERDICT: DISPROVEN, comprehensively. I wrote 13 mutants across the five fixes. All 13 survive.**
Finding **R6-05** (P1).

The same harness passes on unmutated HEAD and kills **all 12 of the author's own claimed-killed
mutants**, so it is not measuring a broken re-implementation of the tests.

### Harness

Four of the five shipped tests (F7, F23, F4, F20) are **pure functions of the source text** —
`ast.parse` of the script, then assertions about names, strings and line numbers. None of them
executes the code under test. `scratchpad/mut_lib.py` re-executes each test body verbatim against a
mutated source string, which is precisely what the real test would compute. F1's test is
behavioural, so its mutants are compiled and executed.

Faithfulness check (`scratchpad/mut_validate.py`):

```
--- 1. the harness on UNMUTATED source (all four must pass) ---
   t_f7: PASS on HEAD (faithful)
   t_f23: PASS on HEAD (faithful)
   t_f4: PASS on HEAD (faithful)
   t_f20: PASS on HEAD (faithful)

--- 2. the AUTHOR's own claimed-killed mutants, through the same harness ---
killed    A-F7-1    F7    [author] remove the --summary-file flag entirely
killed    A-F23-1   F23   [author] revert `priced` to the whole universe
killed    A-F23-2   F23   [author] revert sorted_gainers to the whole universe
killed    A-F23-3   F23   [author] revert the returns loop to the whole universe
killed    A-F23-4   F23   [author] drop the entry-loop membership skip
killed    A-F4-1    F4    [author] revert to the fill count
killed    A-F4-2    F4    [author] drop the non-empty-book requirement
killed    A-F4-3    F4    [author] count carry-forward replays as entries
killed    A-F20-1   F20   [author] remove the anchor call
killed    A-F20-2   F20   [author] anchor from the boot-time figure, literally
killed    A-F20-3   F20   [author] disable it with a false guard
killed    A-F20-4   F20   [author] re-anchor every step

MUTANTS RUN: 12   SURVIVED: 0   KILLED: 12
```

### Result — `scratchpad/mut_run.py`

```
MUTANTS RUN: 13   SURVIVED: 13   KILLED: 0
```

| Mutant | Fix | Mutation | What it restores |
|---|---|---|---|
| M-F7-1 | F7 | `str(BARS_CACHE / ".." / ".." / "market-analysis" / "all-market-ingestion-summary.json")` | writes over the 3,359-entry all-market record — the exact F7 defect |
| M-F7-2 | F7 | `str(BARS_CACHE.parent / "all-market-20160822-20260821" / "ingestion-summary.json")` | writes into a cache the refresh does not own |
| M-F23-1 | F23 | `if sym in base_market or sym in ALLOWED_SYMBOLS` | the 2026-08-31 `KeyError` — **executed and confirmed below** |
| M-F23-2 | F23 | `if sym not in base_market and step < 0:` | `KeyError` at `price = base_market[sym]["price"]` |
| M-F4-1 | F4 | `Side.BUY and not startswith("carry_")` -> `or` | every SELL fill counts as an entry; exits alone satisfy the flag |
| M-F4-2 | F4 | `... or holds_the_selection or bool(engine.fills)` | exits-only rebalance on a non-empty book counts as executed |
| M-F20-1 | F20 | `anchor_equity = marked_opening_equity` on the line above the call | **the author's own A-F20-2, renamed.** The kill worked only because the mutant used the literal identifier |
| M-F20-2 | F20 | `and step > 100000` appended to the guard | the anchor is never reached in a 6.5-hour session |
| M-F20-3 | F20 | `daily_peak_anchored = True` at initialisation | `reset_session_peak` is never called at runtime |
| M-F20-4 | F20 | `+ Decimal('0') * sum(...)` | daily baseline becomes cash only; the 4% rule cannot fire on an invested book |
| M-F1-1 | F1 | `if failed_chunks and not results:` | the poll returns normally on a partial loss — the round-five F1 defect verbatim |
| M-F1-2 | F1 | `if failed_chunks and len(failed_chunks) >= chunk_count:` | same |
| M-F1-3 | F1 | `if failed_chunks and len(results) < len(symbols) // 2:` | same |

The three F1 mutants were **executed**, not analysed:

```
SURVIVED  M-F1-1  F1  raise only when a failed chunk left nothing behind
   -> on a genuinely partial poll it returns normally with 100/150 -- counted as a success
```

And M-F23-1 was executed against a real session (`scratchpad/mut_f23_runtime.py`):

```
HEAD (unmutated)
   -> aborted=False
M-F23-1 priced filters then un-filters
   -> aborted=True  KeyError: 'COALINDIA'
```

### The pattern, stated plainly

Every one of the author's mutants is a **deletion or a literal reversion** — remove the flag, remove
the call, revert the identifier, pass the named variable. Every one of mine is a **preservation**:
keep every string and every name the assertion looks for, and change what the code does. Four of the
five tests assert on rendered source text, so preservation always beats them.

M-F20-1 is the sharpest instance. The commit says *"anchoring from the boot-time figure ... killed"*.
Binding `anchor_equity = marked_opening_equity` one line above the call is the same mutant with a
different spelling, and it survives — the test's `"marked_opening_equity" not in argument` check
inspects only the call's argument expression, never what that expression is bound to.

### Consequence for the record

The commit messages for F7, F23, F4 and F20 each cite mutation testing as the evidence that the fix
is guarded. On this measurement that evidence supports a narrower claim than it is being asked to
carry: it shows the fix is guarded **against reverting it by deletion**, not that it is guarded.

## Claim 7 — Concurrency on `portfolio_state.json`

**VERDICT: CONFIRMED, with a reproduction. Two sessions read the same state, both trade, and the
book records one of them. The other day's fills are gone — while its evidence report stays on disk
claiming they happened.** Finding **R6-17** (P1).

Round five's largest `NOT PROBED` item. It is real.

### There is no lock and no compare-and-swap

```
=== any lock/CAS on portfolio state? ===
(no output above = none)
```
Searched `flock`, `msvcrt`, `LockFile`, `filelock`, `.lock` across
`src/quant_system/execution/paper_portfolio.py`, `scripts/run_paper_pilot_session.py`,
`scripts/run_scheduled_paper_session.py`. `save_portfolio` uses staging + `Path.replace`
(`paper_portfolio.py:253-263`), so a single write is atomic and the hash is consistent — but the
read-modify-write across a whole trading day is completely unguarded. The state hash protects
against a torn or hand-edited file. It does nothing against a lost update: the second writer
computes a perfectly valid hash over a payload derived from a stale read.

### Reproduction — two real processes, one state file

`scratchpad/c7_worker.py`, `c7_setup.py`. S0 is 4 holdings, cash Rs 200,000, `sessions_held 10`
(rebalance due), `sessions_completed 10`. A starts first and holds its read open (a real session
holds it from 09:00 to 15:30); B starts five seconds later and finishes first.

```
S0 written: 4 holdings TCS/INFY/ITC/SBIN, cash 200000.00, sessions_held 10 (rebalance due)
--- A starts first and holds its read for 40s; B starts 5s later and finishes immediately ---
== B has finished and written ==
   state now: ['BHARTIARTL', 'HDFCBANK', 'LT', 'RELIANCE'] cash 49239.14 fees 2811.90 sessions_completed 11
== A has now finished and written ==
[A] loaded state: sessions_held=10 holdings=['INFY', 'ITC', 'SBIN', 'TCS'] cash=200000.00
[A] session done: fills=8 open={'RELIANCE': 237, 'HDFCBANK': 237, 'LT': 237, 'BHARTIARTL': 237} equity=997239.14
[B] loaded state: sessions_held=10 holdings=['INFY', 'ITC', 'SBIN', 'TCS'] cash=200000.00
[B] session done: fills=8 open={'RELIANCE': 237, 'HDFCBANK': 237, 'LT': 237, 'BHARTIARTL': 237} equity=997239.14
   FINAL state: [...] cash 49239.14 fees 2811.90 realized -2209.12 sessions_completed 11 sessions_held 1
```

**Sixteen fills executed across two sessions. The book records eight.**
`sessions_completed` went 10 -> **11**, not 12. `total_fees` went 960.00 -> **2811.90**, which is
960.00 plus **one** session's Rs 1,851.90 — not two. Two full exit-and-entry round trips were paid
for; one of them is not in the ledger, and there is no error, no warning, and no discrepancy: the
reconciliation of each session passes, because each session reconciles internally.

A second run with divergent prices makes the overwrite visible directly:

```
after B wrote : {'INFY': 200, 'ITC': 200, 'SBIN': 200, 'TCS': 200} cash 200000.00 fees 960.00
after A wrote : {'BHARTIARTL': 237, 'HDFCBANK': 237, 'LT': 237, 'RELIANCE': 237} cash 49239.14 fees 2811.90
```

B's session report `paper_session_2026-09-01_paper_ses_20260901_012621_IST.json` remains on disk
describing a book that the state file says never existed.

### And two sessions are reachable, three ways

`scripts/serve_live_dashboard.py:117-121`:

```python
                if ACTIVE_PROCESS and ACTIVE_PROCESS.poll() is None:
                    ACTIVE_PROCESS.terminate()
                ACTIVE_PROCESS = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
```

1. **The scheduled 09:00 session is never in `ACTIVE_PROCESS`.** It is launched by Task Scheduler
   through `run_scheduled_paper_session.cmd`, in a different process tree. Pressing Start on the
   dashboard at any point between 09:00 and 15:30 starts a second session that will overwrite the
   scheduled one's whole day.
2. **`ACTIVE_PROCESS` is a module global that dies with the dashboard.** Restart the dashboard while
   a session it launched is running and the guard sees `None`, so Start launches a second session
   and then overwrites `runner.pid` (`:122-124`) — orphaning the first, which can no longer be
   stopped from the UI. `PID_FILE` is read **only** in `/api/control/stop` (`:153-157`); the start
   path never consults it. The file on disk right now names PID 39516, which is `DEAD - stale pid
   file`, and nothing anywhere notices.
3. **`run_paper_pilot_session.py` itself has no admission control.** Two invocations from a shell
   is all it takes.

All three also collide on `logs/paper_runs/live_paper_status.json`, which both sessions rewrite
every interval, so the dashboard shows an interleaving of two books.

## Claim 8 — Tomorrow's 09:00 hold session

**VERDICT: walked. The first thing that goes wrong is that the session does not run at all** —
the pre-open refresh authenticates with a token that expires at 03:30 that same morning. If that is
fixed by hand, the second thing that goes wrong is R6-04. Findings **R6-14** (P1), **R6-15** (P2),
**R6-16** (P2).

Confirmed schedule (`Get-ScheduledTask 'QuantOS Mizan Paper Session'`):

```
StartBoundary : 2026-08-29T09:00:00      DaysOfWeek : 62 (Mon-Fri)
Execute       : D:\quant_system\scripts\run_scheduled_paper_session.cmd
NextRunTime   : 9/1/2026 9:00:00 AM
```

Preconditions measured now:

```
covers_years ['2026'] | 2026-09-01 a holiday? False | weekday Tuesday
newest cached bar: 2026-08-27
trading sessions missing between it and 2026-09-01: 2
macro covers it: True
carried book: 97 holdings, sessions_completed 1, sessions_held 1, cash 145520.31,
              peak_equity 1000000.00, risk_halted false, last_rebalance_on 2026-08-31
horizon 11 -> holds for 10 -> sessions_held 1 -> HOLDING, not rebalancing
```

### 1st failure, ~09:05 — the refresh uses the daily token, and it is dead by then (R6-14, P1)

`scratchpad/claim8_token.py`:

```
  .env UPSTOX_ANALYTICS_TOKEN   expires 2027-08-23 03:30 IST
  .env UPSTOX_ACCESS_TOKEN      expires 2026-09-01 03:30 IST
  the scheduled task next fires  2026-09-01 09:00 IST

  the PILOT (quotes)  resolves : UPSTOX_ANALYTICS_TOKEN
  the REFRESH (bars)  resolves : UPSTOX_ACCESS_TOKEN   (scripts/ingest_all_market_data.py:384)
  the REFRESH (macro) resolves : UPSTOX_ACCESS_TOKEN   (scripts/ingest_macro_regimes.py:40)

  UpstoxClient(access_token='not.a.jwt').is_authenticated -> True   <- presence only, no expiry check

  If the refresh 401s, `after` stays 2026-08-27 and `missed` = 2 > MAX_MISSED_SESSIONS=0
  -> run_scheduled_paper_session.main() returns 4 and no paper session runs at all.
```

`88b78b9d` is titled *"the pilot survives a morning you forget to refresh the token"*. It made
`resolve_upstox_token` prefer the year-long analytics token — in the **pilot**. The scheduled run
executes the **refresh** first and gates the session on its result, and the refresh reaches Upstox
through `UpstoxClient`, which reads `UPSTOX_ACCESS_TOKEN` only
(`src/quant_system/data/upstox.py:96`). `is_authenticated` is `bool(self.access_token)`
(`:100-102`) — the exact "presence is not validity" defect that `assert_upstox_usable` exists to
fix, still live one directory away.

The cache is currently **two trading sessions stale** (2026-08-28 and 2026-08-31 both absent), so
there is no margin: the refresh has to succeed or the run refuses. Exit 4, log line *"the refresh
did not deliver what it asked for -- check the provider and the token"*, and it repeats every
weekday morning.

Related, same path: `ingest_macro_regimes.py:65-84` writes `macro_INDIAVIX.json` **unconditionally
after any HTTP 200**, including one whose `data.candles` is empty. A 200-with-no-candles overwrites
a good macro cache with `"candles": []`, after which `macro_covers` is permanently false and the run
refuses at exit 5. A 401 is safe (the write is inside the `try` after `urlopen`); a 200 is not.
See **R6-16**.

### 2nd failure — one of the 97 held names is not quoted (R6-04, P1)

`scratchpad/claim8_walk.py` runs the real hold session against the **real 97-holding state file** and
the real 500-name NIFTY500 authority:

```
universe 500 | carried holdings 97 | holdings outside the universe: []

### A. all 500 quoted at yesterday's fill prices (the clean case)
    aborted=False
    equity 998927.35  fills 0  halted=False
    persisted: sessions_completed 2 sessions_held 2 holdings 97 peak 1000000.00

### B. one carried name omitted from the 09:01 poll (2 of 500 were on 2026-08-31)
    *** RAISED OUT OF run_paper_session: LedgerInvariantViolation: cannot mark AADHARHFC to market:
        no price supplied for a held position of 20; refusing to substitute its average price

### C. one non-held universe member returns last_price 0 (pre-open, no trade yet)
    aborted=True ValueError: Depth price must be positive, got -0.02
    equity 998927.35  fills 0  halted=False
    persisted: sessions_completed 2 sessions_held 2 holdings 97 peak 1000000.00
```

**A is the good news**: the carry-forward path, which has never run live with a non-empty book,
works. 97 positions carried, reconciled, 0 fills, book persisted, hold clock advanced.

**B is R6-04**, and it is the one that fires on the same condition that fired on 2026-08-31: two of
five hundred names were not returned. With 97 of the 500 now **held**, the exposure is 48x larger.

### 3rd failure — a pre-open quote priced at zero (R6-15, P2)

Variant C. The quote parser accepts `last_price: 0` (and a payload with no `last_price` at all)
as a real exchange price and stamps it `"source": "UPSTOX_LIVE_FEED"`
(`run_paper_pilot_session.py:273`, default `0`). `OrderBookSnapshot.from_levels` then computes a
bid of `-0.02` and refuses, aborting the session at interval 1 — at roughly 09:06, nine minutes
before the market opens.

The session is honest about aborting (exit 10), but it still **advances the hold clock**:
`sessions_held 1 -> 2` for a session that lived for two minutes and never saw a real close. Ten
such mornings consume the model's whole ten-session hold without the book ever having been marked
to a close, and the eleventh rebalances on that basis. That part is silent.

I could not confirm that Upstox emits `last_price: 0` during the 09:00-09:15 pre-open — see
NOT PROBED. What is confirmed is that the code has no validation on the value at all and that a
zero from any **one** of the 500 aborts the day.

### What does not go wrong

- Trading-day gate: 2026-09-01 is a Tuesday, in `covers_years`, not a listed holiday.
- The halt gate: `risk_halted` is false, so no exit 8.
- The hold/rebalance decision: `sessions_held 1` against a horizon of 11 gives HOLDING, so no
  cross-section is built and none of the F4 paths are exercised.
- The daily anchor: fires on the first successful poll and correctly leaves `peak_equity` at
  1,000,000 (variant A).

## Claim 9 — What this batch introduced, overstated, or broke

**VERDICT: the numeric claims all hold; three behavioural claims are overstated; one regression was
introduced.**

### The numbers check out

```
1191 passed, 1 warning in 89.38s
All checks passed!                      (ruff check .)
Success: no issues found in 141 source files   (mypy src)
```

Matches `d6fde28b`'s "ruff clean; mypy clean on 141 files; 1191 tests passing (was 1188)". The
progression 1184 -> 1186 -> 1187 -> 1188 -> 1191 is consistent with the four diffs. The all-market
summary restore is byte-identical to `e853376a~1` (claim 1). `reset_session_peak` genuinely had **no
production caller** before `d6fde28b`:

```
$ git grep -n "reset_session_peak" d6fde28b~1 -- src scripts
d6fde28b~1:src/quant_system/risk/governor.py:37:  ... `reset_session_peak` --
d6fde28b~1:src/quant_system/risk/governor.py:95:    def reset_session_peak(...)
```

### Regression introduced — one failed chunk at startup now loses the whole day (R6-19, P2)

`eddfa68b` replaced `break` with `continue` plus an unconditional raise. Inside the loop that is
governed by a five-poll retry budget. At **startup** (`:602`) there is no try/except and no budget
at all — `run_paper_session` propagates to `main()`, which returns 2. Measured
(`scratchpad/c9_startup.py`), one of five chunks timing out on the first poll of the day:

```
 chunk 0 of 5 fails:
    before this batch (739859a1): startup poll RAISES -> run_paper_session propagates -> main() returns 2
    at HEAD      (d6fde28b)     : startup poll RAISES -> run_paper_session propagates -> main() returns 2

 chunk 3 of 5 fails:
    before this batch (739859a1): startup poll RETURNS 300/500 -- the session begins
    at HEAD      (d6fde28b)     : startup poll RAISES -> run_paper_session propagates -> main() returns 2
```

Refusing to trade on a shrunk feed is defensible. Refusing **without any retry**, when the identical
condition 400 lines later gets five, is not — and it is exactly the failure that ended the
2026-08-31 session (`<urlopen error _ssl.c:1015: The handshake operation timed out>`), observed
three times in 237 polls. One SSL blip in the first two seconds of the day now costs the whole day,
with no report, no state advance, and exit 2.

### Overstated commit claims

| Commit | Claim | Measured |
|---|---|---|
| `8aafa931` | *"Four sites: the intraday returns map, the gainers/losers panels twice, and the entry loop"* | There is a fifth and a sixth, in the ledger — R6-04. The four listed are the four the author could reach by grepping `base_market` in one file |
| `d6fde28b` | *"A rebalance executes when the book ends up holding the selection, or at least moves toward it: an entry filled"* | "moves toward it" includes one fill of four, leaving 76.3% cash — R6-07 |
| `d6fde28b` | *"F20: ... anchoring from the boot-time figure ... killed"* | Killed only when spelled `marked_opening_equity` inside the call. Bound to a local one line above, it survives — M-F20-1 |
| `a0a66c8d` | *"parsed rather than grepped, so a comment naming the flag cannot satisfy it"* | True of a comment. Not true of a **path** that names `BARS_CACHE` and resolves onto the destroyed file — M-F7-1 |
| `eddfa68b` | *"reverting `continue` to `break` is killed"* | Verified true: `calls["n"] == 2` fails with one call |

### Smaller things

- **R6-20 (P3).** `:1179-1181` still asserts *"Exits above run first, in the same step, so the
  proceeds are available to fund these buys."* They are not. `submit_proposal` only stages
  (`paper_pilot.py:500-522`); fills happen in `process_quote`, which for a step-N order is step
  N+1. Entries in the first rebalance step are sized against pre-exit cash. Pre-existing (present at
  `739859a1`), self-correcting over later steps, but the comment is a false statement of mechanism
  in the one place a reader would check it.
- **R6-21 (P3).** F23 added two per-interval log statements (`:1121` "Quotes cover %d of %d names
  this step", `:1193` a WARNING per selected-but-unquoted name). At 30-second intervals across a
  6.5-hour session that is up to ~780 repetitions each. The 2026-08-31 log is already 246 KB.
- The `739859a1` auto-sync committing whatever is in the tree is known-open and not re-reported.

## Coverage

- **Claims adjudicated:** 9 of 9. None left `NOT TESTED`.
- **Families worked:** input boundaries; concurrency and ordering; failure injection; state machine;
  money and counting; data integrity; security surface; operability; assumption archaeology.
  Identity/tenancy and scale were out of scope for a single-operator local pilot (see below).
- **Targets:** `scripts/run_paper_pilot_session.py`, `scripts/run_scheduled_paper_session.py`,
  `scripts/ingest_all_market_data.py`, `scripts/ingest_macro_regimes.py`,
  `scripts/serve_live_dashboard.py`, `src/quant_system/execution/paper_pilot.py`,
  `src/quant_system/execution/paper_portfolio.py`, `src/quant_system/core/ledger.py`,
  `src/quant_system/risk/governor.py`, `src/quant_system/data/upstox.py`,
  `tests/test_paper_pilot_carried_session.py`, `tests/test_scheduled_paper_session.py`,
  `tests/test_risk_governor_session_peaks.py`.
- **Probes attempted:** 25 executable probes in the session scratchpad. 13 independent mutants
  written and executed, plus 12 reconstructions of the author's mutants as a harness control.
  9 full end-to-end `run_paper_session` executions against real Mizan rankings and real cached bars,
  including two concurrent real processes.
- **Static gates re-run at HEAD:** `1191 passed in 89.38s`; `ruff check .` clean;
  `mypy src` clean on 141 source files.
- **Nothing under `data/evidence/`, `logs/paper_runs/` or `.env` was modified.** Every session probe
  ran against a scratch copy of the state file with `PORTFOLIO_STATE_PATH` and `output_dir`
  redirected. Verified: `git status --short` shows only the report and this round's work record.

## NOT PROBED

This is the section that matters. Each item is something a later round should take.

1. **No live Upstox call was made.** Deliberate: I did not want to spend the operator's rate budget
   or handle the credential. Consequence: **R6-01, R6-02 and R6-15 are proven as code paths and
   unproven as provider behaviour.** I did not establish that Upstox returns `last_price: 0` during
   the 09:00-09:15 pre-open, nor that it ever returns HTTP 200 with `status != "success"` or an
   empty `data` map. If it never does, R6-01 and R6-02 drop to "missing validation" rather than
   "live exposure". **The cheapest possible next probe is one authenticated `market-quote/quotes`
   call for ten instruments at 09:02 IST, logging the raw JSON.** That single call decides three
   findings.
2. **The 09:00 run itself.** I could not execute it — it is in the future, and running it would
   write to `logs/paper_runs/` and advance the real book. Claim 8 is a walk built from the real
   state file, the real universe authority, the real task registration and the real code; it is not
   an observation of the run.
3. **Whether the refresh can actually deliver 2026-08-28 and 2026-08-31 bars.** The cache is two
   trading sessions stale and `_is_current` will now force a 500-symbol re-fetch. I did not test
   that path because it writes into `data/evidence/`. Unknown: how long it takes at concurrency 8,
   whether Upstox rate-limits it, and whether a partial re-fetch could produce a *shorter* series
   with a *later* end date that then wins `load_mizan_cross_section`'s
   `(candidate_end, len(records))` preference over a complete older one. That last one is a
   plausible silent-corruption path I reasoned about and did not measure.
4. **The dashboard as an HTTP server.** I read `serve_live_dashboard.py` and reproduced the
   concurrency consequence with two runner processes directly. I did not start the server and press
   Start twice, so the exact request sequence that produces two sessions is inferred from the
   handler, not observed. R6-22 is likewise read, not executed.
5. **`live_paper_status.json` under two concurrent sessions.** Both write it every interval. I did
   not measure what the dashboard renders while that happens.
6. **The rebalance path on the real 500-name universe.** My rebalance probes used a 20-name universe
   so the cross-section built in seconds. The coverage gate, `refuse_extreme_rows`, and the
   selection of ~100 names from 500 were exercised live on 2026-08-31 but not by me. R6-07's
   arithmetic (one fill of four) is demonstrated at 4 picks, not at 100.
7. **Multi-day behaviour.** Nothing here ran ten sessions to the next rebalance. The interaction
   between R6-07 (a concentrated book blessed as executed), R6-08 (weight drift never trimmed) and
   R6-15 (aborted sessions consuming hold clock) compounds across days and I measured only single
   steps of it.
8. **Two concurrent ingests against one `EvidenceStore`.** `_clean_stale_locks` deletes
   `locks/governed-operation.lock` unconditionally at startup (`ingest_all_market_data.py:198-206`),
   which looks like it defeats whatever that lock is for. I did not follow it.
9. **Scale.** 500 symbols x ~780 intervals: `engine.fills`, `engine.audit_log` and `_orders` grow
   without bound and `step_books` rebuilds 500 `OrderBookSnapshot` objects per interval. Today's
   session ran 237 intervals without trouble. 780 was not measured.
10. **Whether `Path.replace` is atomic across processes on this NTFS volume.** Assumed, not
    verified. R6-17 is a lost update, not a torn write, so this only matters for a worse variant.
11. **Identity, authorization and tenancy.** Single-operator local system with a loopback dashboard;
    there is no multi-tenant surface to attack. Not probed, and I do not think it is worth probing.
12. **`clear_paper_halt.py`.** Referenced by two error paths as the operator's recovery route. I did
    not read or exercise it, so "the halt can be cleared" is untested this round.
13. **The three preserved aborted logs** (`_fallback_aborted`, `_keyerror_aborted`,
    `_pre_pnl_fix`). I sampled them for chunk-failure counts and the 401 pattern. I did not read
    them end to end, and the 84-failures-in-83-intervals pattern in `_fallback_aborted` is
    unexplained.
14. **Prior reports.** I read the round-five report's headline items to avoid rediscovery but did
    not re-verify its 15 P2 / 9 P3. Where this report disagrees with an earlier one it says so
    explicitly; silence is not agreement.
