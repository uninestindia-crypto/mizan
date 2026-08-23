# Active work: strategy-hypothesis registry and session runner

STATUS: ACTIVE  
OWNER: Claude Code (founder-directed)  
TOOL: Claude Code  
STARTED_UTC: 2026-08-23T00:00:00Z  
STARTING_REVISION: fcf5765adf52ae74f7b7829d133e7a0bd0051162  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; owned paths disjoint)

## Objective

Give `StrategyHypothesisRecord` a caller. The type exists, is tested, and refuses to be backtested
unregistered — but nothing produces a hypothesis and nothing spends an ordinal, so the guard has
never fired in anger.

Deliver the countable half of the founder's design: a model proposes a strategy or pattern, the
proposal is recorded with provenance, and it cannot become a backtest until it has spent a trial
ordinal drawn from the durable history of prior attempts.

## Owned paths

- `src/quant_system/advisory/registry.py` (new)
- `src/quant_system/advisory/__init__.py`
- `scripts/run_hypothesis_session.py` (new)
- `tests/test_advisory_registry.py` (new)
- `tests/test_hypothesis_session_runner.py` (new)
- `agent_context/work/active/20260823-claude-hypothesis-registry.md`
- `agent_context/work/active/20260823-NOTICE-advisory-capture-lint-resolved.md`

## Non-goals

- `src/quant_system/analytics/multiplicity.py`. Claimed by `20260820-codex-slice4-ridge-training`.
  The registry therefore **reports** an attempt count; feeding it into a deflated-Sharpe computation
  is a governed-runner change and is not attempted here.
- `modeling/**`, `evidence/**`, `execution/**`, `core/**` — all claimed.
- Calling a model over the network. The runner records a hypothesis the founder already obtained
  from a reasoning model; see rationale.
- Giving hypotheses any authority. Recording one changes nothing until a governed runner chooses
  to act on it, and that runner must call `assert_registered_for_backtest()`.

## Plan

1. IN PROGRESS - claim check, this record, stale-lint notice.
2. PENDING - `HypothesisRegistry` with journal-derived ordinals.
3. PENDING - `scripts/run_hypothesis_session.py`.
4. PENDING - tests for both.
5. PENDING - ruff, format, strict mypy, audits.

## Current step

Creating the record.

## Decision rationale

**The ordinal is derived from the journal, not supplied by the caller.** A trial ordinal that a
human types is a number, not a count. Deriving it from the append-only journal makes the attempt
count a consequence of recorded history, which is the only version that can honestly feed a
deflation. `agent_context/CURRENT.md` documents exactly why this matters: GRASIM's published DSR of
`0.696673` looked near-promotable and fell to `0.397794` once re-deflated against the true attempt
count of 51. An ordinal nobody can inflate away is the mechanism that prevents a repeat.

**`register()` verifies the chain before counting.** This is the load-bearing detail. If a row can
be deleted from the journal, the attempt count drops, the ordinal is too low, and the deflation
becomes too weak — the failure would silently favour the candidate. Counting without verifying
would make the whole registry decorative, so verification is not optional and not deferred.

**The runner does not call a model over the network.** The founder's stated workflow is having a
reasoning conversation with Claude or ChatGPT and wanting the result recorded. A subprocess or API
call would add credentials, latency, and non-determinism to a step whose entire value is the
durable record. The runner therefore takes the model's output as input and requires the model's
identity to be declared, which is also the only way `knowledge_cutoff` can be honest — no API
reports it.

**`--execution-mode` is required, with no default.** Same principle as `capture_opinion`: a default
of `LIVE_MODEL` would let an unattributed paste be recorded as a model response.

**Registration is refused twice for the same hypothesis id.** Re-registering would spend a second
ordinal on one idea, inflating the attempt count and over-deflating — dishonest in the opposite
direction, and just as bad.

**Rejected alternative: store the attempt count in a config file or counter table.** A mutable
counter can be reset; the journal cannot be rewritten without breaking its chain.

**Rejected alternative: have the registry import `analytics.multiplicity` and compute the deflated
Sharpe itself.** The module is claimed, and the advisory layer computing a promotion statistic
would give a non-authoritative component a foothold in a governed calculation.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| (to be filled after execution) | | |

## Blockers and conflicts

None. `advisory/**` was committed at `fcf5765` under my four completed records; `registry.py` and
both test files are new. `scripts/run_hypothesis_session.py` collides with no claimed script —
active records name `run_governed_promotion.py`, `run_governed_ridge_training.py`, and
`run_governed_shadow_session.py` only.

## Stop point

Record created; implementation starting.

## Next safe action

Implement `src/quant_system/advisory/registry.py`.
