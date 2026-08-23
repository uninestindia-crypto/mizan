# Active work: per-advisor provenance in the advisory panel

STATUS: COMPLETED  
OWNER: Claude Code (founder-directed)  
TOOL: Claude Code  
STARTED_UTC: 2026-08-22T19:10:00Z  
STARTING_REVISION: 1cdeff41221bc18028a9f64a41b2b86f3cc8152c  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; owned paths disjoint)

## Objective

Replace `ExecutionMode.UNDETERMINED` with real provenance. `MultiAgentConsensusEngine.evaluate()`
currently destroys per-advisor detail before any caller sees it, so every captured record says
"produced somehow, by something". Preserve that detail and record one row per advisor.

Hard constraint: **the panel's decisions must not change.** `evaluate()` has real authority — it
vetoes trades and scales position weight — so every edit here is additive metadata only. No
`action_bias`, `confidence`, `weight_multiplier`, or `rationale` value changes.

## Owned paths

- `src/quant_system/alpha/ai_advisor.py`
- `src/quant_system/advisory/**`
- `src/quant_system/strategies/ai_enhanced_ml.py`
- `tests/test_advisory_*.py`
- `tests/test_panel_provenance.py` (new)
- `agent_context/work/active/20260822-1910Z-claude-per-advisor-provenance.md`

## Non-goals

- Changing any panel decision. Behaviour preservation is the acceptance criterion, not a nicety.
- **Repairing the two rule-based advisors.** `CodexCLIAdvisor` and `AntigravityCLIAdvisor` never
  invoke a CLI and `AntigravityCLIAdvisor` cannot disagree with the quant signal (finding below).
  Both are real defects. Fixing them changes what the panel decides, which this record forbids
  itself. They are recorded for a separate decision.
- `alpha/key_pool.py`, `alpha/direct_providers.py`. Not needed; `20260822-claude-dotenv-loading`
  touched `key_pool.py` recently.
- `evidence/**`, `modeling/**`, `execution/**`, `core/**`, `strategies/ml_equity.py` — claimed by
  live records.
- Giving the advisory layer a vote.

## Plan

1. COMPLETE - claim check, create this record.
2. COMPLETE - `ExecutionMode.DETERMINISTIC_RULE`; map `CLI_SUBSCRIPTION`.
3. COMPLETE - tagged all 11 `AIOpinion` construction sites with an honest mode.
4. COMPLETE - structured `panel_members` preserved in the aggregate metadata.
5. COMPLETE - `capture_panel_members()` with per-member `ModelIdentity`.
6. COMPLETE - strategy records one row per advisor plus the aggregate row.
7. COMPLETE - tests, including the decision-equivalence proof.
8. COMPLETE - ruff, format, strict mypy, audits.

## Current step

Complete.

## Decision rationale

**Additive metadata is decision-neutral, and that is checkable.** Neither `evaluate()` nor
`AIEnhancedMLEquityStrategy` reads `AIOpinion.metadata` when deciding — both read `action_bias`,
`weight_multiplier`, `confidence`, and `rationale` only. Adding metadata keys therefore cannot move
a decision. The test suite pins this rather than asserting it: `test_panel_provenance.py` compares
every decision field before and after across the whole advisor matrix.

**`ExecutionMode.DETERMINISTIC_RULE` is a new member and a distinct fact.** `HEURISTIC_FALLBACK`
means a model was attempted and failed. Codex and Antigravity never attempt one — a rule is their
only path. Collapsing the two would make "how often did the panel actually reach a model?"
unanswerable, which is the first question any analysis of this dataset must ask.

**Six of eleven `AIOpinion` sites emit no mode at all.** Worse than the fallback gap recorded
earlier: `_fallback_heuristic` VETO and NEUTRAL branches, both `CodexCLIAdvisor` returns, the
`AntigravityCLIAdvisor` return, and the engine's empty-panel return. Every one is tagged here.

**The aggregate keeps `individual_opinions` untouched.** A consumer may depend on it. The new
`panel_members` key is added alongside rather than replacing it.

**Rejected alternative: give `MultiAgentConsensusEngine` a journal and let it write records.**
Would invert the one-way boundary — `alpha/` would import `advisory/` — and put file I/O inside a
decision path where a slow disk could delay a trade. The engine stays ignorant of persistence; it
only stops throwing information away.

**Rejected alternative: leave the two rule advisors mislabelled since only metadata is in scope.**
Recording `DETERMINISTIC_RULE` for them is accurate and is not a behaviour change. Renaming the
classes or making them call a CLI would be, and is excluded.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run ruff check` (owned paths) | PASS | `All checks passed!` |
| `uv run ruff format --check` (owned paths) | PASS | `12 files already formatted` |
| `uv run mypy --strict src` | PASS | `Success: no issues found in 119 source files` |
| `uv run pytest` (9 affected files) | PASS | **189 passed** |
| `scripts/audit-agent-claims.ps1` | PASS | exit 0 |
| `scripts/audit-disk-layout.ps1` | PASS | exit 0 |

Test files: `test_panel_provenance` 20, `test_advisory_records` 49, `test_advisory_journal` 16,
`test_advisory_isolation` 67, `test_advisory_capture_wiring` 22, plus the 11 pre-existing
`test_ai_advisor` / `test_ai_enhanced_ml` / `test_quant_rag` / `test_strategies` cases, all unmodified.

### Decision-neutrality evidence

Three independent lines, because this edit touched a file with authority over money:

1. **The diff.** `git diff src/quant_system/alpha/ai_advisor.py` removes exactly two lines, both
   `metadata={"individual_opinions": [op.rationale for op in opinions]},` one-liners reformatted
   into multi-line dicts that still contain that identical expression. Every added line is a
   `metadata=` keyword argument, a comment, or the new `_panel_member_details` helper. No
   `action_bias`, `confidence`, `weight_multiplier`, or `rationale` expression was touched.
2. **Pre-existing tests pass unmodified.** The 11 panel and strategy cases that existed before this
   work, including `test_ai_enhanced_ml_strategy_signal_generation`'s exact `len(signals) == 1`.
3. **New characterization tests pin the decisions forward.** `test_panel_provenance.py` fixes
   `(action_bias, confidence, weight_multiplier, rationale)` for every branch of every advisor, and
   `test_the_aggregate_decision_ignores_advisor_metadata` shows two panels with identical decisions
   but different metadata produce identical aggregates — the structural reason metadata cannot move
   a decision.

`+47` lines in `ai_advisor.py`, `+119` in `ai_enhanced_ml.py`, 4 deletions across both.

## Findings raised, not repaired

1. **`CodexCLIAdvisor` never invokes a CLI.** It defines `is_available` checking for `codex` on
   PATH and never calls it; `evaluate_opportunity` is two hardcoded thresholds on
   `sma_distance_pct` and `return_5d`. Severity: Major — the class name asserts a capability the
   code does not have.
2. **`AntigravityCLIAdvisor` never invokes a CLI and cannot disagree.** `action_bias` is
   `"BULLISH" if quant_side == Side.BUY else "BEARISH"`, so it always confirms the quant direction;
   `confidence` and `weight_multiplier` are closed-form functions of `quant_strength`. As a panel
   member it is a rubber stamp that adds a vote without adding information, and it dilutes the
   averaged `weight_multiplier` toward 1.0. Severity: Major.
3. **The default panel is one model and two rules.** `MultiAgentConsensusEngine.__init__` builds
   `[ClaudeCLIAdvisor, CodexCLIAdvisor, AntigravityCLIAdvisor]`, and only the first can reach a
   model — and only when `claude` is on PATH. Severity: Major, and the reason per-advisor capture
   is worth having: after this change the records make it self-evident.

## Blockers and conflicts

`src/quant_system/alpha/ai_advisor.py` is named by three active records, all as a **non-goal**, none
as a claim: `20260821-1048Z-claude-slice4-redteam-repair` (excludes `alpha/**`),
`20260822-claude-dotenv-loading` (excludes `alpha/**`), `20260821-0530Z-claude-slice4-certification`
(references a collision note). Its implementing record,
`work/completed/20260821-antigravity-ai-multi-provider-keypool.md`, is `STATUS: COMPLETED`, and the
files are committed at `c5f7874`. No live claim exists.

## Files changed

- `src/quant_system/alpha/ai_advisor.py`: mode markers on all sites; `_panel_member_details`;
  `panel_members` preserved on both aggregate returns
- `src/quant_system/advisory/records.py`: `ExecutionMode.DETERMINISTIC_RULE`
- `src/quant_system/advisory/capture.py`: `_MODE_MARKERS`, `_MARKER_INTERFACES`,
  `capture_panel_members()` with a per-member `ModelIdentity`
- `src/quant_system/advisory/__init__.py`: exports
- `src/quant_system/strategies/ai_enhanced_ml.py`: writes member rows then the aggregate row
- `tests/test_panel_provenance.py`: new, 20 cases
- `tests/test_advisory_records.py`, `tests/test_advisory_capture_wiring.py`: updated to assert the
  repaired behaviour rather than the defects they previously documented

## Correction to an earlier record

`work/completed/20260822-1830Z-claude-advisory-capture-wiring.md` states that
`MultiAgentConsensusEngine.evaluate()` discards per-advisor metadata and that `UNDETERMINED` is the
only honest value available downstream. That was accurate when written and is now **superseded**:
the engine preserves `panel_members`, and member rows carry real modes. The aggregate row still
records `UNDETERMINED`, which remains correct — a panel verdict is not a model call. That record is
not edited; this note is the additive correction required by PROTOCOL.md section 3.

## Stop point

Complete and verified. Working tree carries the changes uncommitted. Two source files modified
(`alpha/ai_advisor.py`, `strategies/ai_enhanced_ml.py`), three advisory modules extended, one new
test file, two test files updated.

## Next safe action

Nothing is required for this record. Two follow-ons are worth a decision, both **behaviour
changes** and therefore out of scope here:

1. Decide what to do about `CodexCLIAdvisor` and `AntigravityCLIAdvisor` (findings 1-3). They are
   named as CLI advisors, never invoke a CLI, and one cannot disagree with the quant signal. The
   options are to make them real, rename them, or remove them from the default panel. All three
   change what the panel decides.
2. `MultiAgentConsensusEngine.evaluate` still takes `action_bias` from `opinions[0]`
   (`ai_advisor.py`), so the panel's direction is the first advisor's opinion rather than a vote.
   Recorded as a Major finding in `work/completed/20260822-1742Z-claude-advisory-observer-journal.md`
   and still unrepaired.
