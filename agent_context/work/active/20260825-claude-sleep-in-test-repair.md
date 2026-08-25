# Active work: remove the sleep-in-test flakiness risk (program Major #2, urgent subset)

STATUS: COMPLETE — repaired and verified; not independently adjudicated  
OWNER: Claude Code — test craft  
TOOL: Claude Code  
STARTED_UTC: 2026-08-25T11:00:00Z  
STARTING_REVISION: `f60fb961`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Why this subset first

`.launch/STATE.md` Major #2 records 207 code and 33 test craft findings. The 8 `sleep-in-test`
findings are the urgent part, and not because there are many: a test that sleeps and then asserts is
asserting the *timing*, so it passes or fails according to how busy the host was. Every gate
measurement in this repository — including the 929-test count recorded in `CURRENT.md` — is slightly
less trustworthy while they exist.

## Two patterns, only one of which was a defect

Reading the eight sites showed they were not the same thing:

| Pattern | Count | Verdict |
|---|---:|---|
| Bounded poll: `while ... < max_wait: if condition: break; sleep(0.05)` | 5 | **Correct.** The assertion is the condition; the sleep is only a yield between checks |
| Fixed sleep then assert: `sleep(0.3)` then assert a heartbeat arrived | 2 | **Genuine defect.** Asserts a timing guess |

Treating all eight as the same thing would have meant either annotating away two real defects, or
rewriting five correct waits for no gain.

## What changed

**The two real defects became waits on the condition:**

- `test_supervisor_heartbeats_and_progress_tracking` slept 0.3s then asserted `last_heartbeat_at is
  not None`. It now waits for the heartbeat to arrive, with a 3s bound and a message naming what it
  waited for.
- `test_supervisor_cooperative_cancellation` slept 0.1s and then cancelled, assuming the worker had
  started. It now waits until the operation is actually `RUNNING` before cancelling — otherwise it
  was testing cancellation of a possibly-unstarted worker.

**The five correct polls were deduplicated** into one `_await_operation` helper taking a predicate, a
timeout, a description used in the failure message, and an optional `abort_on` so a terminal
`FAILED`/`LOST` fails immediately rather than burning the full timeout. The helper's single remaining
`time.sleep` is annotated `test-allow: sleep-in-test` because it is a poll interval, not an
assertion.

**A pre-existing mypy error was fixed** while in the file: the `supervisor_instance` fixture was
annotated `-> WorkerSupervisor` but is a generator. It survived because the repo gate runs
`mypy src`, never `tests`. Confirmed pre-existing by stashing — the same error reports at the old
line number without my change. Now `-> Iterator[WorkerSupervisor]`.

## Verification

| Check | Before | After |
|---|---:|---:|
| `sleep-in-test`, this file | 8 | **0** |
| `loop-in-test`, this file | 5 | **0** |
| `sleep-in-test`, repo-wide | 8 | **1** |
| `loop-in-test`, repo-wide | 36 | **31** |
| `tests/test_server_supervisor.py` | 10 passed | **10 passed** |
| Full suite | 929 passed | **929 passed** |
| Ruff, strict mypy on the file | 1 mypy error | **clean** |

No test was added, removed, weakened or skipped. The count is identical because the change is to how
the tests wait, not to what they assert.

## Correction to STATE.md's description

Major #2 states "The 8 sleep-in-test findings are all in `tests/test_server_supervisor.py`". That is
not quite right — one is in `tests/test_server_api.py:338`. It is the same bounded-poll pattern and
is therefore correct code, but the statement should be amended when someone updates that file.

## Left alone, deliberately

`tests/test_server_api.py` is claimed by `20260821-claude-check-tests-casebody.md`, whose status is
`HANDOFF_REQUIRED`. PROTOCOL §5 says an active record stays in place until another agent explicitly
adopts it, and §7 forbids silently taking over. That record is specifically about the check-tests
checker, so its owner is the right person for a checker finding inside its own claimed file.

The remaining 31 `loop-in-test` findings and the 207 code findings of Major #2 are untouched.
