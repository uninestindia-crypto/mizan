# Handoff: wire advisory capture at a call site

STATUS: ADOPTED AND DISCHARGED — 2026-08-22T18:30Z  
ADOPTED_BY: `agent_context/work/completed/20260822-1830Z-claude-advisory-capture-wiring.md`

> The wiring described below is **done**: `AIEnhancedMLEquityStrategy` now seals every panel verdict
> before the veto branch, 149 advisory tests pass, and the 11 pre-existing strategy/panel tests pass
> unmodified. What remains is the follow-on named in that record's *Next safe action* — per-advisor
> capture inside `MultiAgentConsensusEngine`, which needs a record claiming `alpha/**` and would
> replace every `ExecutionMode.UNDETERMINED` with a real mode.
>
> One finding from the wiring changes the picture: `evaluate()` discards **all** per-advisor
> metadata, keeping only rationales. The aggregate carries no provenance whatsoever, so
> `UNDETERMINED` is not a shortcut — it is the only honest value available downstream of the engine.

Original handoff follows, retained as the record of what was requested.

STATUS_AT_CREATION: READY_FOR_ADOPTION  
FROM: Claude Code (founder-directed)  
TO: unassigned — requires a record claiming `src/quant_system/strategies/**`  
DATE_UTC: 2026-08-22T17:42:53Z  
ACTIVE_RECORD: `agent_context/work/completed/20260822-1742Z-claude-advisory-observer-journal.md`

## Objective and acceptance criteria

The advisory journal substrate exists and is verified. It is not yet invoked anywhere. Complete the
observer loop so that every opinion the panel produces is sealed into a journal, while changing
nothing about what the system decides.

Done when:

- every call to `MultiAgentConsensusEngine.evaluate()` results in exactly one journal entry,
  including calls whose outcome is `VETO`;
- `AdvisoryJournal.verify_chain()` passes over the resulting file;
- no decision, weight, gate, or order changes as a result of the wiring — provable by the
  pre-existing strategy tests passing unmodified;
- `tests/test_advisory_isolation.py` still passes, which it will only do if `strategies/**` is not
  added to `GOVERNED_PACKAGES` to make it pass. Do not weaken the guard to fit the wiring.

## Completed

- `src/quant_system/advisory/` — 5 modules: `errors`, `records`, `journal`, `capture`, `__init__`.
- Record types: `AdvisoryOpinionRecord`, `StrategyHypothesisRecord`, both sealed and hashed.
- `AdvisoryJournal` — append-only, hash-chained JSONL, fsynced, tamper-evident.
- `capture_opinion` / `capture_hypothesis` — adapters that never import the panel (structural
  `SupportsAIOpinion` protocol), strip credential-shaped metadata, and require `execution_mode`.
- 119 tests across three files, all passing; strict mypy clean; ruff and ruff format clean.
- Both audits (`audit-agent-claims.ps1`, `audit-disk-layout.ps1`) exit 0.

## In progress

Nothing. The substrate is complete and self-contained. The integration below was a declared
non-goal of the originating record, not partial work.

## Files and ownership

- `src/quant_system/advisory/**`: untracked, complete, uncommitted. Owned by the completed record.
- `tests/test_advisory_records.py`, `tests/test_advisory_journal.py`,
  `tests/test_advisory_isolation.py`: untracked, complete, uncommitted.
- No pre-existing file was edited. Nothing is staged.

## Verification

| Command | Result | Notes |
|---|---|---|
| `uv run ruff check src/quant_system/advisory tests/test_advisory_*.py` | PASS | `All checks passed!` |
| `uv run ruff format --check src/quant_system/advisory tests/test_advisory_*.py` | PASS | 8 files already formatted |
| `uv run mypy --strict src/quant_system/advisory` | PASS | 5 source files |
| `uv run mypy --strict src` | PASS | 115 source files |
| `uv run pytest tests/test_advisory_{records,journal,isolation}.py` | PASS | 119 passed |
| `uv run pytest -q` (full suite) | NOT CLAIMED | Unstable while other agents edit the tree; see the completed record |
| `scripts/audit-agent-claims.ps1` | PASS | exit 0 |
| `scripts/audit-disk-layout.ps1` | PASS | exit 0 |

## Known failures and risks

- **The full suite is not a stable measurement in this checkout right now.** Three identical runs
  gave 626/0, 624/6, and 647/1, with collection growing 630 -> 648, because
  `20260822-claude-h2-l2-repair` and `20260822-claude-governed-execution-adapter` are editing
  `modeling/`, `execution/`, and `core/` live. Every observed failure is in their owned paths. Do
  not attribute those to the advisory work, and do not "fix" them.
- **`capture_opinion` requires `execution_mode` and will not guess.** Whoever wires it must
  determine the mode at the call site. `infer_execution_mode()` returns `None` for the untagged
  fallback branches and that `None` must not be defaulted to `LIVE_MODEL` — that would recreate the
  exact fail-open this work exists to make visible.
- **The journal is single-writer.** Concurrent appenders to one path surface as a broken chain, not
  as interleaved rows. If the wiring runs under the server or a multi-process pilot, give each
  process its own journal path or serialise appends.
- **These records are tamper-evident, not reproducible.** Do not let them into `EvidenceStore` or
  cite them in a gate. Re-running the prompts will not reproduce the text.

## Exact stop point

Last action: `scripts/audit-disk-layout.ps1` returned `RESULT: PASS`, exit 0. Working tree carries
the new package and three test files as untracked additions. Nothing staged, nothing committed.

## Next safe action

Create a record claiming `src/quant_system/strategies/**`, then edit
`strategies/ai_enhanced_ml.py:107` to seal the opinion immediately after `evaluate()` returns and
**before** the veto branch at :116. Vetoed opinions are currently dropped by the control flow and
they are the rows most worth having.

## Do not do

- Do not give the advisory layer a vote, a gate, or a promotion path as part of the wiring.
- Do not add `strategies` to `GOVERNED_PACKAGES` in `tests/test_advisory_isolation.py` to make a
  failing import assertion pass. If that guard fails, the wiring is in the wrong place.
- Do not write advisory records into `EvidenceStore`, and do not edit `evidence/**` or `modeling/**`
  — both are claimed by other live records.
- Do not repair the four `alpha/**` findings listed in the completed record from this handoff
  without first claiming `alpha/**`; they are real, but they are behavioural changes to a
  decision path.
- Do not commit with `git add -A`. The shared checkout holds three other agents' in-flight repairs.
