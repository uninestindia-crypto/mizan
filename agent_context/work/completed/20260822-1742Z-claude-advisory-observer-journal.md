# Active work: non-authoritative advisory journal (LLM observer mode)

STATUS: COMPLETED  
OWNER: Claude Code (founder-directed)  
TOOL: Claude Code  
STARTED_UTC: 2026-08-22T17:42:53Z  
STARTING_REVISION: 1cdeff41221bc18028a9f64a41b2b86f3cc8152c  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; owned paths are new and disjoint)

## Objective

Build the missing substrate that lets an LLM advisory panel be **recorded without being obeyed**.

Today `MultiAgentConsensusEngine` (`src/quant_system/alpha/ai_advisor.py:331`) can veto a trade and
scale position weight (`src/quant_system/strategies/ai_enhanced_ml.py:116`), yet `AIOpinion` is
never persisted anywhere — it reaches no store, no ledger, no evidence resource. The layer has
authority and leaves no audit trail, which is exactly backwards.

Deliver an append-only, tamper-evident advisory journal that captures what a model said, which
model said it, what it was shown, and whether it was anchored on the quant answer — and that is
**structurally incapable** of influencing a governed decision.

## Owned paths

- `src/quant_system/advisory/**` (new package; did not exist at STARTING_REVISION)
- `tests/test_advisory_records.py` (new)
- `tests/test_advisory_journal.py` (new)
- `tests/test_advisory_isolation.py` (new)
- `agent_context/work/active/20260822-1742Z-claude-advisory-observer-journal.md`

## Non-goals

- `src/quant_system/evidence/**` and `src/quant_system/modeling/**`. Both are claimed by
  `20260821-1048Z-claude-slice4-redteam-repair.md`, which is `STATUS: HANDOFF_REQUIRED` and has not
  been adopted. PROTOCOL.md section 5 keeps that claim live. Advisory records therefore do **not**
  go into `EvidenceStore`, and this is a design virtue rather than a workaround: see rationale.
- Editing `src/quant_system/alpha/ai_advisor.py`. The dependency runs one way only — `advisory/`
  imports `alpha/`, never the reverse — so the panel needs no change to be recorded.
- Giving the advisory layer a vote, a gate, or a promotion path. Observer mode only.
- Any live-money routing (T4 remains unauthorized).
- Repairing the consensus/anchoring defects catalogued below. They are recorded as findings here,
  not fixed, because they sit in files this record does not own.

## Plan

1. COMPLETE - startup sequence, claim check, create this record.
2. COMPLETE - `errors.py`: typed fail-closed advisory failure codes.
3. COMPLETE - `records.py`: sealed record types with mandatory provenance.
4. COMPLETE - `journal.py`: append-only hash-chained JSONL journal.
5. COMPLETE - `capture.py`: `AIOpinion` -> record adapter, secret-stripping.
6. COMPLETE - tests for records, journal, and the isolation invariant.
7. COMPLETE - ruff, ruff format, strict mypy, targeted tests, both audits.

## Current step

Complete. Substrate built and verified. Integration at a call site is deliberately not done — it is
a declared non-goal here and needs a record claiming `strategies/**`. See the linked handoff.

## Decision rationale

**Why a separate package instead of an evidence resource type.** Two reasons converge. The
protocol one: `evidence/**` is claimed. The design one, which would hold anyway — the evidence store
is the substrate for *governed, reproducible* artifacts, and an LLM opinion is neither. Model
versions drift silently, providers deprecate endpoints, and identical prompts return different text.
Admitting non-reproducible content into a store whose entire value proposition is content-addressed
re-verifiability would weaken the store's guarantee to the level of its weakest member. A separate
journal with its own weaker, honestly-labelled guarantee is the correct shape. `AUTHORITY` is a
literal field on every record and its only legal value is `NON_AUTHORITATIVE`.

**Why the isolation test exists.** Observer mode enforced by discipline decays the first time
someone is in a hurry. `tests/test_advisory_isolation.py` walks the AST of every module under
`src/quant_system/modeling/`, `evidence/`, `risk/`, and `execution/` and fails if any of them
imports `quant_system.advisory`. The boundary is asserted by the build, not by a comment.

**Why `execution_mode` is a first-class required field.** `BaseAIAdvisor._fallback_heuristic`
(`src/quant_system/alpha/ai_advisor.py:60`) returns a rule-based RSI verdict at confidence 0.85 when
no CLI is on PATH and no API key works. It tags `mode: HEURISTIC_FALLBACK` inside a free-form
metadata mapping that nothing reads and nothing persisted. A four-model panel that has silently
degraded to one RSI rule is indistinguishable from a working one. Promoting it to a required
enum field means a record cannot be written without answering the question.

**Why `anchored_on_quant_signal` is required.** Every advisor is handed `quant_side` and
`quant_strength` before being asked its opinion. An opinion produced after being shown the answer is
a different measurement from one produced cold, and averaging the two kinds together is not
meaningful. Recording the flag now is what makes a future analysis honest; recovering it
retrospectively would be impossible.

**Why hindsight is computed, not asserted.** An LLM's pretraining cutoff is later than any backtest
window, so asking it about a 2024 bar leaks 2025-2026 knowledge. That contamination cannot be
prompted away. It can, however, be *measured*: the record carries the last observation date it was
shown and the model's declared cutoff, and derives `HindsightStatus`. `CONTAMINATED` is the expected
value for backtests and is not an error — recording it as unknown would be the error.

**Why hypotheses carry `trial_ordinal`.** The founder's clarified intent is to use LLMs as strategy
and pattern reasoners rather than live-data forecasters. That is a materially better use because
hypotheses are countable, and `analytics/multiplicity.py` already deflates against attempt counts.
The risk is a suggested strategy quietly becoming a backtest without spending an ordinal, which is
undeclared multiplicity — the precise failure `CURRENT.md` warns about after the 51-trial campaign.
`StrategyHypothesisRecord.trial_ordinal` is `None` until registered, and
`assert_registered_for_backtest()` raises `HYPOTHESIS_NOT_REGISTERED` when it is not.

**Rejected alternative: reuse `EvidenceStore` with a new `EvidenceResourceType`.** Rejected on the
reproducibility argument above, and it would have required editing a claimed path.

**Rejected alternative: log to `logging` and grep later.** Log lines are not tamper-evident, rotate
away, and have no schema. The learning loop the founder wants needs a queryable, ordered, complete
record or the resulting dataset silently under-reports.

**Rejected alternative: fix the `opinions[0].action_bias` consensus defect here.** Real defect
(`ai_advisor.py:410` takes the first advisor's direction and calls it consensus), but repairing the
panel is a behavioural change to a decision-making path, and this record deliberately owns only the
observing path. Logged under findings.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch` | PASS | Shared checkout; no other agent holds `advisory/` or the three new test files |
| `git worktree list` / `git branch --list` | PASS | Single worktree `D:/quant_system`, single branch `main`; no hidden claims |
| `uv run ruff check src/quant_system/advisory tests/test_advisory_*.py` | PASS | `All checks passed!` |
| `uv run ruff format --check src/quant_system/advisory tests/test_advisory_*.py` | PASS | `8 files already formatted` |
| `uv run mypy --strict src/quant_system/advisory` | PASS | `Success: no issues found in 5 source files` |
| `uv run mypy --strict src` | PASS | `Success: no issues found in 115 source files` |
| `uv run pytest tests/test_advisory_{records,journal,isolation}.py` | PASS | **119 passed**, 0 failed |
| `uv run pytest -q` (full suite) | **NOT A STABLE MEASUREMENT** | See below. Not claimed as evidence. |
| `scripts/audit-agent-claims.ps1` | PASS | `every workspace has a visible claim and every claim resolves`, exit 0 |
| `scripts/audit-disk-layout.ps1` | PASS | `no stray QuantOS directories`, exit 0 |

### Why no full-suite number is claimed here

Three identical `uv run pytest -q` invocations minutes apart returned **626 passed / 0 failed**,
then **624 passed / 6 failed**, then **647 passed / 1 failed**, with collection growing 630 -> 648.
The tree is being edited by other agents while the suite runs. Confirmed directly: `git status`
gained `src/quant_system/execution/governed_strategy.py`, `tests/test_governed_strategy.py`, and
three new active records during this session, and `find -newermt "-20 minutes"` showed live edits to
`modeling/holdout.py`, `modeling/preprocessing.py`, `modeling/features.py`, and `core/ledger.py`.

Every failure observed sits in a file owned by another live record —
`20260822-claude-h2-l2-repair` (`modeling/holdout.py`, `tests/test_modeling_holdout.py`,
`tests/test_modeling_promotion.py`, `core/ledger.py`) or `20260822-claude-governed-execution-adapter`
(`execution/governed_strategy.py`, `tests/test_governed_strategy.py`). None is in a path this record
owns, and none is reachable from `advisory/`, which imports only `data/market_data_evidence`.

Recording a full-suite pass/fail count from this tree would be citing another agent's in-flight
repair as though it were a gate measurement. The attributable evidence is the 119 targeted tests,
strict mypy across all 115 source files, and the isolation guard.

**My test count moved 118 -> 119 without any edit of mine**, because
`test_no_governed_module_imports_the_advisory_layer` is parametrized over every governed source
file and automatically picked up `execution/governed_strategy.py` the moment it appeared. The guard
extends itself to new governed modules rather than needing maintenance — which is the point of
asserting the boundary from the build.

## Files changed

- `src/quant_system/advisory/__init__.py`: public surface
- `src/quant_system/advisory/errors.py`: `AdvisoryFailureCode`, `AdvisoryError`
- `src/quant_system/advisory/records.py`: `AdvisoryOpinionRecord`, `StrategyHypothesisRecord`, enums, sealing
- `src/quant_system/advisory/journal.py`: `AdvisoryJournal` append-only hash-chained JSONL
- `src/quant_system/advisory/capture.py`: `AIOpinion` -> record adapter with secret stripping
- `tests/test_advisory_records.py`, `tests/test_advisory_journal.py`, `tests/test_advisory_isolation.py`

## Findings raised, not repaired (all outside owned paths)

1. **`ai_advisor.py:410` — "consensus" is the first advisor's opinion.** `action_bias` is taken as
   `opinions[0].action_bias`; only the multiplier is aggregated. A panel that appears to vote does
   not. Severity: Major. Owner: whoever next claims `alpha/**`.
2. **`ai_advisor.py:60-95` — advisory layer fails open, and the marker is mostly absent.**
   Missing CLI or exhausted key pool yields a confident heuristic verdict. Worse than a plain
   fail-open: of the three return branches in `_fallback_heuristic`, **only the third tags
   `metadata["mode"] = "HEURISTIC_FALLBACK"`.** The VETO branch (`weight_multiplier=0.0`,
   confidence 0.85, cancels the trade outright) and the NEUTRAL branch (`weight_multiplier=0.5`,
   halves the position) both return with empty metadata and are byte-for-byte indistinguishable
   from a live model response. The two most consequential outcomes carry the least provenance.
   Reproduced in `tests/test_advisory_records.py::test_veto_fallback_carries_no_mode_marker_so_inference_returns_none`.
   This is why `capture_opinion` requires `execution_mode` explicitly instead of inferring it.
   Severity: Major.
3. **`ai_advisor.py` — `masked_key` is written into opinion metadata.** Not a secret leak today
   (it is masked), but it puts key material shape on a path headed for persistence. `capture.py`
   strips `masked_key`, `key_id`, and any key-like field defensively. Severity: Minor.
4. **`ai_enhanced_ml.py:121` — LLM output multiplies position size.** `weight_multiplier` from an
   unrecorded, non-reproducible source scales real position weight. This is the authority-without-
   audit-trail problem in one line. Severity: Major.

## Blockers and conflicts

None. Owned paths were newly created and collided with no active record. `evidence/**` and
`modeling/**` were deliberately avoided; the claim in `20260821-1048Z-claude-slice4-redteam-repair.md`
is untouched, and no number that record pins as evidence is altered by this work.

## Stop point

All seven plan steps complete. The working tree carries one new package
(`src/quant_system/advisory/`, 5 modules) and three new test files, all untracked and uncommitted.
**No pre-existing file was edited.** `git status` shows the new paths as `??` only. Both audits exit
0. Nothing is staged; committing is left to the founder or the coordinator because the shared
checkout currently holds three other agents' in-flight repairs and a broad commit would sweep them
in — `PROTOCOL.md` section 4 forbids `git add -A` here.

Handoff for the remaining integration:
`agent_context/handoffs/20260822-claude-advisory-observer-journal-handoff.md`.

## Next safe action

Wire capture at one call site, under a new record claiming `strategies/**`. Recommended:
`strategies/ai_enhanced_ml.py:107`, recording the opinion immediately after `evaluate()` returns and
**before** the veto branch at :116, so vetoed opinions are captured rather than discarded — vetoes
are the most interesting rows in the dataset and the current control flow drops them.

Do not give the advisory layer a vote as part of that wiring. The point of observer mode is that
months of prospective records accumulate while the layer changes nothing; only then is there
evidence to argue it should influence anything.
