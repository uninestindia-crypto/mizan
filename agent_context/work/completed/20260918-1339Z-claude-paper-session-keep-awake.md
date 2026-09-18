# Active work: the scheduled paper session is suspended mid-run because the machine idles to sleep

STATUS: COMPLETED (verified locally; **not** verified in production until Monday 2026-09-21)  
OWNER: Claude Code (Opus 5)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-18T13:39:21Z  
STARTING_REVISION: `6457102f`  
WORKTREE_OR_BRANCH: `D:\quant_system`, branch `claude/paper-session-keep-awake` (shared checkout).
Branch is mine; per PROTOCOL §8.3 nobody else should remove it.

## Authorization

Founder instruction, 2026-09-18: "ok then complete it asap", after I named the frozen paper book as
the only open item losing ground daily.

## The defect, measured

The flagship paper book has not rebalanced since **2026-08-31 — 18 days**. It is not halted and not
erroring: it completes sessions and never trades.

| Session | Wrapper started | Trading window reached | Outcome |
|---|---|---|---|
| 2026-09-16 | 09:00:19 | ACTIVE 17:57:10 | 0 fills; rebalance refused at 13/100 |
| 2026-09-17 | 09:00:01 | never — process died | no completion |
| 2026-09-18 | 16:12:47 | ACTIVE 16:56:07 | 0 fills; rebalance refused at 21/100 |

Root cause, from Windows power events rather than inference. On 09-16 and 09-17 the scheduled task
fired at 09:00 (`WakeToRun: True` wakes the machine), the process ran for **exactly 7m13s on both
days**, and then:

```
2026-09-16 09:07:32  Kernel-Power 42  "The system is entering sleep. Sleep Reason: System Idle"
2026-09-16 17:32:22  clock resync — machine resumes
2026-09-17 09:07:14  Kernel-Power 42  "Sleep Reason: System Idle"
2026-09-17 14:37:28  Kernel-Power 507 "exiting Modern Standby  Reason: Lid."
```

The process is **suspended**, not hung. It resumes only when a human opens the lid, at an arbitrary
hour, by which time the 15:30 IST close has passed and the trading window is zero. Zero orders means
coverage stays far below `MIN_REBALANCE_COVERAGE`, so `rebalance_executed` correctly returns False,
the hold clock never resets, and the next session repeats it.

**The guard is right. Everything downstream of the suspension works.** The failure is that the
machine does not stay awake for a job it was woken up to run.

## Objective

The scheduled paper session holds a system power request for its whole duration, so Windows does not
idle the machine out from under a run it started.

## Owned paths

- `scripts/run_scheduled_paper_session.py` — **owned by no active record**; checked by scanning the
  `## Owned paths` section of all 99 active records. The four records that own
  `run_paper_pilot_session.py` (the inner runner) are listed under "Blockers and conflicts"; that
  file is **not** touched.
- `tests/test_scheduled_paper_session_keep_awake.py` (new)
- `agent_context/work/active/20260918-1339Z-claude-paper-session-keep-awake.md` (this file)

## Non-goals

- **No change to `scripts/run_paper_pilot_session.py`.** Four active records own it, and nothing
  about the defect is inside it. The wrapper is where the process lifetime lives.
- **No change to what the book trades, to selection, sizing, the hold clock, `rebalance_executed`,
  `MIN_REBALANCE_COVERAGE`, or any risk limit.** The book's behaviour once it reaches its window is
  out of scope and is not being tuned to force a rebalance.
- **No change to Windows power settings or scheduled tasks.** A process saying "do not idle-sleep
  while I run" is in-repo and reversible; changing the machine's lid or sleep policy is neither, and
  `20260909-claude-lid-fix-and-xs-supervision.md` holds the claim on power settings.
- **No re-running of today's or any past session to "catch up".** R7-05 is unrepaired: each run on
  the same trading day advances `sessions_held` again — driven on a copy of the real book, three
  runs took it 2 -> 3 -> 4 -> 5. One attempt per day stands.
- No repository-wide formatter, generator, or `git add -A`.

## Plan

1. Confirm the wrapper's process outlives the session. — DONE (`subprocess.run` at `:317` blocks)
2. Probe `SetThreadExecutionState` on this machine. — DONE
3. File this record. — DONE
4. Failing-first test for the keep-awake contract. — DONE
5. Implement; verify release on both the success and exception paths. — DONE
6. Full gate. — DONE

## Decision rationale

**Why a power request and not a power setting.** The sleep reason is `System Idle`, not `Lid`, so the
lid action is not what fires — the Modern Standby idle path is. `SetThreadExecutionState` with
`ES_CONTINUOUS | ES_SYSTEM_REQUIRED` is exactly the mechanism for "a background job is running, do
not idle-sleep", it is scoped to the process lifetime, and it disappears the moment the run ends.
Changing the machine's power policy would keep the laptop awake on battery permanently, which is a
worse trade and is another record's claim.

Probed before committing to the approach:

```
SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) -> 0x80000000   (non-zero: granted)
release -> 0x80000001
```

**Why not `ES_AWAYMODE_REQUIRED`.** It is supported here, but away mode is for media playback that
must continue with the display off; it changes how the system reports itself and is not what a
compute job wants. `ES_SYSTEM_REQUIRED` is the narrower correct request.

**Why the wrapper and not the session.** `run_scheduled_paper_session.py` calls
`run_paper_pilot_session.py` through a blocking `subprocess.run`, so the wrapper's lifetime spans the
entire run including the 6.5-hour realtime loop. One request in one place covers it, and it keeps the
change out of a file under four active claims.

**Fail soft, never fail the run.** A session that cannot obtain a power request should still trade.
The helper logs what happened and continues; it never raises. A run that refuses to trade because it
could not ask Windows to stay awake would be a worse defect than the one being fixed.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Ownership scan over all 99 active records | **UNCLAIMED** | No record names `run_scheduled_paper_session.py` in its `## Owned paths` |
| `SetThreadExecutionState` probe | **GRANTED** | returns `0x80000000`; release returns `0x80000001` |
| Windows power event correlation, 09-16 / 09-17 | **CONFIRMED** | 7m13s of runtime on both days, then `Sleep Reason: System Idle`; wake source `Lid` |
| `pytest tests/test_scheduled_paper_session_keep_awake.py` **before** | **6 failed** | Failing-first, all six |
| `pytest tests/test_scheduled_paper_session_keep_awake.py` **after** | **6 passed** | |
| `pytest tests/test_scheduled_paper_session.py` | **12 passed** | The wrapper's existing suite, unaffected by the `main` / `_run` split |
| Real (unmocked) production path | **REQUEST GENUINELY HELD** | Inside the context manager, re-asserting returns previous state `0x80000001` — `ES_CONTINUOUS \| ES_SYSTEM_REQUIRED` — and the release logs and clears it |
| `ruff check .` / `ruff format --check .` | **PASS** | 698 files |
| `mypy src launcher.py scripts` | **PASS** | 210 source files |
| `check-code.mjs` | **BASELINE** | 1,082 / 174 files. The wrapper's two findings are the **same two** as before, shifted by the insertion: `deep-nesting` in `require_trading_day` 79 -> 160, `long-function` 252 -> 350 (the old `main` body, now `_run`). Verified by running the checker against the pre-change file. **Zero added** |
| `check-tests.mjs` | **BASELINE** | 87 / 24 files (121 checked, was 120). The new test file contributes 0 |
| `audit-agent-claims.ps1` / `audit-disk-layout.ps1` | **PASS / PASS** | exit 0 / exit 0 |
| `git diff --stat` | **89 insertions, 0 deletions** | Pure addition |
| `pytest tests/ -q` (full, forward) | **PASS** | **1,611 passed in 685.20s**, exit 0. Baseline at `6457102f` was 1,605; +6 is exactly the new file and no other test changed state |
| `pytest` reverse file order | **NOT RUN** | CI's separate job |

## Files changed

- `scripts/run_scheduled_paper_session.py`: adds `ES_CONTINUOUS` / `ES_SYSTEM_REQUIRED`,
  `_system_execution_state_setter()`, and the `keep_system_awake()` context manager; `main()` now
  parses arguments and wraps the rest of the run, whose body moved unchanged into `_run(args)` so the
  request covers the pre-open checks as well as the session subprocess.
- `tests/test_scheduled_paper_session_keep_awake.py` (new): 6 cases — the request is taken with both
  flags, released on the normal path, released on the exception path, a refused request still runs,
  an unavailable API still runs, and `main()` actually calls it (guarding against the helper existing
  while the defect returns).

## Blockers and conflicts

`scripts/run_paper_pilot_session.py` is owned by four ACTIVE records and is **not touched**:

- `20260826-antigravity-paper-trade-live-market-testing.md`
- `20260829-claude-live-mizan-feature-provider.md`
- `20260914-claude-paper-book-accounting-repairs.md`
- `20260915-0900Z-claude-paper-report-baselines.md`

**This fix cannot be verified in production before Monday 2026-09-21.** Today is Friday; NSE does not
trade at weekends, and `require_trading_day` refuses non-trading days. The unit test proves the
contract; only a real 09:00 run with the lid shut on battery proves the outcome.

**CI can verify nothing** — the gate is red for billing
(`20260918-NOTICE-ci-billing-failure-has-recurred.md`).

## Stop point

Repair applied, the power request verified held on the real unmocked path, every gate green.

**This fix is not verified in production and cannot be before Monday 2026-09-21.** Today is Friday;
NSE does not trade at weekends and `require_trading_day` refuses non-trading days. The unit tests
prove the contract — the request is taken with both flags, released on the normal and the exception
paths, and a refused or unavailable API still lets the session run. Only a real 09:00 run with the
lid shut on battery proves the outcome. Read Monday's `logs/paper_runs/scheduled_20260921.log`: the
line `holding a system power request ...` should appear near the top, and the gap between
`scheduled paper session for ...` and `newest cached bar before refresh: ...` should be about ten
minutes rather than hours.

**What this fix does not do.** It does not make the book rebalance. It removes the reason the
session kept missing its trading window; whether a rebalance then executes depends on coverage
reaching `MIN_REBALANCE_COVERAGE` once orders can actually be submitted, which has never been
observed on this book. The 18-day freeze had a single cause on the evidence available, but only
Monday will show whether it was the only one.

## Next safe action

Watch Monday's session. If the window is reached and the rebalance still refuses, the next thing to
examine is order submission rather than scheduling — the runner reached `REBALANCING` and submitted
**0 orders** on every observed session, and this fix does not touch that path.
