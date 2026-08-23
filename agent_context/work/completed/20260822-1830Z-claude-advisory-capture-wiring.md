# Active work: wire advisory capture into the AI-enhanced strategy

STATUS: COMPLETED  
OWNER: Claude Code (founder-directed)  
TOOL: Claude Code  
STARTED_UTC: 2026-08-22T18:30:00Z  
STARTING_REVISION: 1cdeff41221bc18028a9f64a41b2b86f3cc8152c  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; owned paths disjoint)

## Objective

Close the observer loop. `src/quant_system/advisory/` exists and is verified but is invoked nowhere.
Wire it into `AIEnhancedMLEquityStrategy` so every consensus opinion is sealed into a journal —
including the vetoes, which the current control flow discards — while changing nothing about what
the strategy decides.

Adopts the handoff `agent_context/handoffs/20260822-claude-advisory-observer-journal-handoff.md`.

## Owned paths

- `src/quant_system/strategies/ai_enhanced_ml.py`
- `src/quant_system/advisory/**` (carried over from the completed record; still untracked)
- `tests/test_advisory_capture_wiring.py` (new)
- `tests/test_advisory_records.py`, `tests/test_advisory_journal.py`, `tests/test_advisory_isolation.py`
- `agent_context/work/active/20260822-1830Z-claude-advisory-capture-wiring.md`

## Non-goals

- `src/quant_system/strategies/ml_equity.py`. Discussed as future work by
  `20260822-claude-model-execution-adapter-scope.md` (`STATUS: IN_PROGRESS`). Not touched.
- `src/quant_system/alpha/**`. Two live records treat it as hands-off, and per-advisor capture
  inside `MultiAgentConsensusEngine` would be a behavioural change to a decision path. The cost of
  staying out is recorded honestly below as `ExecutionMode.UNDETERMINED`.
- `evidence/**`, `modeling/**`, `execution/**`, `core/**` — all claimed by live records.
- Giving the advisory layer a vote. The veto that already exists is left exactly as it is; this
  work only observes it.
- Changing any signal, weight, score, or ordering.

## Plan

1. COMPLETE - re-check claims (tree moved since the substrate landed), create this record.
2. COMPLETE - fix `reject_secret_material` to recurse into nested lists and mappings.
3. COMPLETE - add `ExecutionMode.UNDETERMINED` and `AdvisorInterface.AGGREGATE`.
4. COMPLETE - add `observation_fingerprint` to `capture.py`.
5. COMPLETE - wire capture into `ai_enhanced_ml.py` before the veto branch.
6. COMPLETE - tests proving capture happens, vetoes are captured, and behaviour is unchanged.
7. COMPLETE - ruff, format, strict mypy, targeted tests, audits.

## Current step

Complete.

## Decision rationale

**Recording sits before the veto branch.** `ai_enhanced_ml.py:116` `continue`s on a veto, so a
vetoed opinion currently leaves no trace anywhere. Vetoes are the rows most worth having — the whole
prospective question is "would the panel's refusals have helped?" — so capture must precede the
branch, not follow it.

**A recording failure must never break the strategy.** This inverts the repository's fail-closed
default, deliberately and narrowly. Fail-closed is correct when a component has authority: refusing
to act on bad data protects money. This component has no authority by construction. If a full disk
could stop a strategy from trading, the observer would have acquired exactly the power the design
exists to deny it. Journal errors are caught, counted on `advisory_write_failures`, and logged at
ERROR. The counter matters: silently swallowed failures would produce a dataset with invisible gaps,
which is the flaw this work was built to avoid, so the gaps are made countable instead.

**`ExecutionMode.UNDETERMINED` is new, and it is an admission rather than a default.**
`MultiAgentConsensusEngine.evaluate()` returns one aggregate `AIOpinion` and flattens its members to
a list of rationale strings, so per-advisor provenance is destroyed inside the engine before the
strategy sees anything. At this call site the mode is genuinely unknowable. The alternatives were to
guess `LIVE_MODEL` — recreating the fail-open this whole effort exists to expose — or to refuse to
record and lose the data. Recording `UNDETERMINED` keeps the row and makes the gap countable: a
future analysis can measure precisely how much of the dataset has unestablished provenance.
Eliminating it requires per-advisor capture inside `alpha/**`, which is a non-goal here and is
written up in the handoff.

**`AdvisorInterface.AGGREGATE` is new for the same reason.** A panel verdict is not a CLI call, a
direct API call, or a heuristic. Labelling it as any of those three would be false.

**The panel roster is captured even though the modes are not.** `engine.advisors` is read-only
attribute access — no model is re-invoked — so `panel_advisors` records which advisors were on the
panel at decision time. That is real provenance available without touching `alpha/**`, and it is
what makes a later "which advisor vetoes correlate with losses" question answerable at all.

**The observation, not the rendered prompt, is what gets fingerprinted.** Each advisor builds its
own prompt text privately inside `evaluate_opportunity`; the strategy never sees it. What the
strategy *can* attest to is the exact input handed to the panel — symbol, side, strength, and the
technical summary. `observation_fingerprint` hashes that canonically into `prompt_sha256`. Values
are stringified before hashing so a `NaN` in an indicator series cannot raise inside the hash and
cost a record.

**`recorded_at` is wall clock; `observation_window_end` is `ctx.current_time.date()`.** These are
different facts and conflating them would break hindsight computation. `ctx.current_time` is naive
in the existing fixture, so only its date is taken and it is never treated as UTC. The clock is
injectable for deterministic tests, matching the `EvidenceStoreConfig.clock` idiom.

**Rejected alternative: record after the veto branch.** Simpler, and silently drops every veto.
That is the one row type the dataset cannot do without.

**Rejected alternative: make the journal a required constructor argument.** Would change every
existing caller and the registry default. `None` means disabled and the strategy behaves exactly as
before, which is what keeps the pre-existing test's exact signal count valid as proof.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run ruff check` (owned paths) | PASS | `All checks passed!` (one import-order fix applied via `--fix`) |
| `uv run ruff format --check` (owned paths) | PASS | `10 files already formatted` |
| `uv run mypy --strict src` | PASS | `Success: no issues found in 118 source files` |
| `uv run pytest tests/test_advisory_{records,journal,isolation,capture_wiring}.py` | PASS | **149 passed** |
| `uv run pytest tests/test_ai_enhanced_ml.py tests/test_strategies.py tests/test_ai_advisor.py` | PASS | **11 passed**, all unmodified |
| `git diff --stat src/quant_system/strategies/ai_enhanced_ml.py` | +94 / -2 | both deletions are import lines replaced by wider ones; no behaviour removed |
| `scripts/audit-agent-claims.ps1` | PASS | exit 0 |
| `scripts/audit-disk-layout.ps1` | PASS | exit 0 |

The pre-existing `test_ai_enhanced_ml_strategy_signal_generation` asserts an exact signal count
(`len(signals) == 1`) and passes unmodified. That, plus
`test_signals_are_identical_with_and_without_a_journal`, is the evidence that observation changed
no decision.

Full-suite counts remain unclaimable: other agents are still editing `modeling/`, `execution/`, and
`core/` in this checkout. See the completed substrate record for the measured instability.

## Files changed

- `src/quant_system/strategies/ai_enhanced_ml.py`: optional journal, capture before the veto branch
- `src/quant_system/advisory/records.py`: recursive secret scan; `UNDETERMINED`, `AGGREGATE` members
- `src/quant_system/advisory/capture.py`: `observation_fingerprint`
- `src/quant_system/advisory/__init__.py`: exports
- `tests/test_advisory_capture_wiring.py`: new

## Finding discovered during wiring

**`MultiAgentConsensusEngine.evaluate()` discards every advisor's metadata.** Both the veto path and
the approval path rebuild the aggregate's metadata as `{"individual_opinions": [op.rationale ...]}`.
Rationales survive; `mode`, `provider`, `key_id`, `rag_grounding_used` and everything else are
dropped before any caller sees them.

This was found by two tests failing that assumed propagation, and it strengthens the
`ExecutionMode.UNDETERMINED` decision considerably: the aggregate does not carry an *unreliable*
provenance marker, it carries **none at all**. No caller downstream of the engine can establish how
a panel verdict was produced — not this strategy, not any future one. Per-advisor capture inside
`alpha/**` is the only fix.

It also relocates the credential-leak risk. Since metadata is dropped but rationales are kept, the
real leak path is an advisor writing a key into its rationale text, which then lands either in the
aggregate rationale (veto path, which concatenates them) or inside the `individual_opinions` list
(approval path). The latter is a credential nested one level inside a list — precisely what a flat
metadata scan walks past, and why `reject_secret_material` was made recursive in step 2. Both paths
are covered by tests.

## Blockers and conflicts

None. `strategies/ai_enhanced_ml.py` is claimed by no other active record; the three records that
mention `strategies/` name `ml_equity.py` only, which is untouched here.

## Stop point

Complete and verified. Working tree carries the changes uncommitted.

## Next safe action

Per-advisor capture inside `MultiAgentConsensusEngine.evaluate()`, which would replace every
`UNDETERMINED` with a real mode and record one row per advisor instead of one per panel. Needs a
record claiming `alpha/**`.
