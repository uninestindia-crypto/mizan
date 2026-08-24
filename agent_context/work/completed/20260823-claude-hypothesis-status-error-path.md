# Active work: the hypothesis runner's --status path must refuse legibly, not traceback

STATUS: COMPLETED  
OWNER: Claude Code (founder-directed)  
TOOL: Claude Code  
STARTED_UTC: 2026-08-23T00:00:00Z  
STARTING_REVISION: 1b35da5  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; owned paths disjoint)

## Objective

Repair a defect in my own runner, found by a peer's warning rather than by my tests.

`quant-system-61` reported that its `MaturityPolicyError` escapes the shadow session unhandled and
loses the audit report, and advised checking that my call site has a handler. It does not.
`main()` returns `_print_status(registry)` outside any `try`, so `--status` against a truncated or
tampered journal exits 1 with a raw traceback instead of a legible refusal.

Reproduced before repair:

```
quant_system.advisory.errors.AdvisoryError: JOURNAL_TRUNCATED: truncated.jsonl ends at sequence 0
but its witness records 1; 1 entry was removed
EXIT=1
```

The detection is correct; only the presentation is wrong.

## Owned paths

- `scripts/run_hypothesis_session.py`
- `tests/test_hypothesis_session_runner.py`
- `agent_context/work/active/20260823-claude-hypothesis-status-error-path.md`

## Non-goals

- Catching `AdvisoryError` anywhere that would let execution continue with a substituted count.
  See rationale — that is the opposite of this fix.
- `scripts/run_governed_promotion.py`. Owned by `20260822-claude-h2-l2-repair.md`, which has
  already implemented both findings from
  `agent_context/work/active/20260823-REQUEST-deflation-consumer-wiring.md`.
- `analytics/multiplicity.py`. Still owned by `20260820-codex-slice4-ridge-training.md`
  (OWNER: Codex root agent), unreached. That half of the request stays open, and needs no change
  anyway.
- `tests/test_governed_shadow_wiring.py`, `tests/test_governed_strategy.py`. Reported red on ruff
  I001 by a peer; both are claimed by other live records.

## Plan

1. COMPLETE - reproduce the traceback, create this record.
2. COMPLETE - wrap the status path so it refuses with `EXIT_REFUSED` and a `REFUSED:` line.
3. COMPLETE - regressions proving refusal, exit code, and that no count is substituted.
4. COMPLETE - ruff, format, strict mypy.

## Current step

Complete.

## Decision rationale

**Catching to report and fail is not the same as catching to continue.** `quant-system-bf`
deliberately let `AdvisoryError` propagate out of `run_governed_promotion.py`, and that is right
there: an unverifiable count must abort the promotion rather than deflate against a smaller number.
The danger is a handler that substitutes a value and carries on.

This runner is a different case. It is a human-facing CLI whose entire job is to report the attempt
count, so a stack trace is a presentation failure, not a safety property. The repair prints a
`REFUSED:` line naming the failure code and returns `EXIT_REFUSED` (3). It never prints a count, and
never falls through to the recording path. The distinction is pinned by
`test_status_refuses_a_truncated_journal_without_reporting_a_count`, which asserts both that the
refusal appears and that **no count is printed** — so a future edit that "helpfully" recovers a
partial count fails the test.

**Why `EXIT_REFUSED` rather than a fresh code.** A caller scripting this cares about one thing: the
journal could not be trusted. Reusing the existing refusal code keeps that binary and matches the
duplicate-registration path, which already exits 3.

**Rejected alternative: catch in `HypothesisRegistry` and return `None`.** Would push the decision
into every caller and invite exactly the silent-zero substitution the registry exists to prevent.
The raise stays; only this CLI's presentation changes.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Manual repro before repair | FAIL as expected | `AdvisoryError: JOURNAL_TRUNCATED`, raw traceback, exit 1 |
| Manual repro after repair | PASS | `REFUSED: JOURNAL_TRUNCATED: ...`, exit 3, no count printed |
| `uv run pytest tests/test_hypothesis_session_runner.py` | PASS | 25 passed (21 + 4 new) |
| `uv run pytest tests/test_advisory_*.py tests/test_hypothesis_session_runner.py` | PASS | 241 passed |
| `uv run ruff check scripts tests/test_hypothesis_session_runner.py` | PASS | `All checks passed!` |
| `uv run mypy --strict src` | PASS | no issues, 128 source files |

## Coordination outcome for the deflation request

`agent_context/work/active/20260823-REQUEST-deflation-consumer-wiring.md` is **accepted and
implemented** by the owner of `scripts/run_governed_promotion.py`
(`20260822-claude-h2-l2-repair.md`); their reply is
`agent_context/work/active/20260824-NOTICE-deflation-request-accepted.md`.

They went further than the request asked, and correctly. Rather than making `--multiplicity-count`
required, they made it **derived**: `load_persisted_trial_registry(store).multiplicity_count`
supplies the ridge attempts and the flag became an override that may only *raise* the total, never
lower it. The reasoning is better than mine — a required flag still trusts a typed number, and
someone who can type 51 can type 5.

`quant-system-61` corroborated the finding from the evidence side and generalised it: GRASIM's own
manifest stores `multiplicity_count = 18`, not 51, because it was scored while the campaign was
still open. So a count taken from any single trial's record understates the search that produced it.
`TrialRegistryV1` is the only source that sees the whole store — which is exactly the source the
repair now uses.

## Open, recorded rather than resolved

**Advisory-sourced candidates have no identity manifest.** `quant-system-61` landed `97fcc4b`
(`ModelEvidenceIdentityV1`), binding a promoted bundle to one published manifest across `model_id`,
`candidate_id`, `trial_id`, `fitted_state_hash`, `preprocessing_state_hash`, and `score_threshold`.
There is no advisory-side equivalent: a `StrategyHypothesisRecord` carries a `hypothesis_id` and a
spent ordinal, but nothing binds a promoted model back to the hypothesis that proposed it. The
two-attempt-stream problem therefore has an identity dimension as well as a counting one, and only
the counting half is now closed. That agent owns the bundle file and has offered to extend it.
Not actioned here: it is new design, not a defect repair, and needs the founder's direction.

## Blockers and conflicts

None. Both owned paths are mine and uncontested.

## Stop point

Complete and verified, uncommitted.

## Next safe action

Founder decision on whether to pursue advisory-sourced bundle identity with the owner of
`execution/`-side bundle code. Nothing is broken while it is open — an advisory hypothesis cannot
reach promotion without passing the existing governed gates — but a promoted model cannot currently
be traced back to the hypothesis that proposed it.
