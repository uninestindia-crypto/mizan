# NOTICE: `test_server_api.py::test_create_and_poll_backtest_operation` fails under machine load

STATUS: NOTICE (additive; no other record is edited and none of the named files are touched)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-10
FOR: the owner of `tests/test_server_api.py` — `20260821-claude-check-tests-casebody.md`
       (STATUS `HANDOFF_REQUIRED`)
REVISION_OBSERVED: `5523843c` plus this session's uncommitted changes

## What was observed

A full-suite run during this session produced:

```
1 failed, 1221 passed in 1072.42s (0:17:52)
FAILED tests/test_server_api.py::test_create_and_poll_backtest_operation
```

The failure:

```
Operation failed unexpectedly: {'operation_id': 'op-4cec31df50dd', 'type': 'BACKTEST',
 'status': 'LOST', 'stage': 'LOST',
 'error': {'code': 'HEARTBEAT_TIMEOUT',
           'message': 'Worker process heartbeat timed out after 10.0s (limit: 10.0s).',
           'details': {'elapsed_seconds': 10.012839}}}
```

The suite was running concurrently with two other heavy Python processes (a full evidence-store
scan and a package install), on the 8-core Snapdragon reference machine.

## It is load, not a regression

Rerun immediately afterwards on an otherwise idle machine:

```
.venv/Scripts/python.exe -m pytest tests/test_server_api.py::test_create_and_poll_backtest_operation -q
1 passed in 11.13s
```

Note the margin: the test needs **11.13 seconds** to pass, against a heartbeat limit of **10.0
seconds**, and the failing run missed by **12.8 milliseconds** (`elapsed_seconds: 10.012839`). The
worker is not hanging; it is being descheduled for slightly longer than the limit allows.

## Why this is worth a notice rather than a shrug

`agent_context/CURRENT.md` open Major #2 already names test flakiness as *"a flakiness risk to every
gate measurement, which makes every other number in this file slightly less trustworthy."* This is a
concrete instance in a different file from the eight `sleep-in-test` findings that item tracks.

A heartbeat limit of 10.0 s in a test that legitimately takes 11.1 s wall-clock is a limit
calibrated against an idle machine. Any gate run on a busy one — CI, a parallel agent session, a
verifier clone running alongside a training job — can fail it for no code reason. That is exactly
the failure mode that makes an agent distrust a red gate, which is worse than the flake itself.

## What was *not* done

- `tests/test_server_api.py` was **not edited**. It is claimed by
  `20260821-claude-check-tests-casebody.md`, and PROTOCOL §3 forbids editing another record's paths.
- That record was **not edited**. This notice is the additive route (PROTOCOL §8.4).
- No heartbeat limit, worker configuration, or timeout was changed anywhere.

## Suggested resolution, for the owner to accept or reject

The filer's view, offered as a lead rather than a decision: the fix is not to raise the limit until
it stops failing, which just moves the cliff. It is to make the assertion wait on the *condition*
rather than on wall-clock — or to make the heartbeat interval independent of worker scheduling
pressure, so a descheduled worker is distinguishable from a dead one. A worker that is alive but
slow and a worker that has died should not produce the same status.

## Bearing on this session's own claims

This session's changes touch `src/quant_system/data/**`, `src/quant_system/modeling/labels.py`,
`scripts/**` and new `tests/**`. None of them are on the server, operation or worker path, and the
test passes in isolation at the same revision. The 1221 passing tests stand; this one failure is not
evidence about the changes under it.
