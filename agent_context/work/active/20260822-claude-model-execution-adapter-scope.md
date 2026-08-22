# Scope — governed model to execution adapter

TASK_ID: 20260822-claude-model-execution-adapter-scope
AGENT: Claude Code (Opus 5)
STATUS: IN_PROGRESS (scope only; no source edited)
STARTED_UTC: 2026-08-22
STARTING_REVISION: c5f7874dd555e33cff1f998945a4893199baaeaa (main, install root)
WORKTREE_OR_BRANCH: D:\quant_system on main (no worktree; document-only task)

## Objective

Scope the missing component that lets a *promoted governed model* produce executable signals.
Today no such component exists, and no slice in `.launch/SLICES.md` covers it.

## Non-goals

- No source modification. This task produces a scope, not an implementation.
- No edits to any path claimed by another active record (see Ownership conflicts).
- Not a decision record. Requires founder/coordinator acceptance before implementation.

## Owned paths

- `agent_context/work/active/20260822-claude-model-execution-adapter-scope.md` (this file, only)

Paths the *implementation* would need are listed under Ownership conflicts. None are claimed here.

## The gap, stated precisely

Verified at c5f7874:

- `grep RidgeFittedStateV1|ModelCardV1|predict_ridge_scores` outside `modeling/` and `tests/`
  returns **zero results**. Nothing consumes a fitted model.
- `src/quant_system/server/**` contains **zero imports** of `quant_system.modeling`.
- `src/quant_system/execution/realtime_shadow.py:28` imports `BaseStrategy` from
  `quant_system.strategies.base`. Shadow and paper decisions come from hand-written strategies.
- `src/quant_system/strategies/ml_equity.py:17` defines `RollingRidgeClassifier`, a **second,
  ungoverned ridge implementation** with no purging, no multiplicity, no evidence. It is the one
  wired into execution. This violates SLICES.md slice rule 2 ("may not introduce a second
  calculation path").

The system that executes is not the system that was validated.

## Proposed contract

Two new types in a new module `src/quant_system/execution/governed_strategy.py`:

```python
@dataclass(frozen=True, slots=True)
class PromotedModelBundleV1:
    model_card: ModelCardV1
    fitted: RidgeFittedStateV1
    standardization: StandardizationStateV1
    # __post_init__ MUST fail closed on:
    #   fitted.preprocessing_state_hash != standardization.state_hash
    #   standardization.feature_names != FEATURE_NAMES_V1
    #   model_card.verdict not in EXECUTABLE_STATES
    #   model_card.candidate_id not bound to the fitted state


class GovernedModelStrategy(BaseStrategy):
    def __init__(self, bundle, surface: ExecutionSurface, abstain_band: str) -> None: ...
    def generate_signals(self, ctx: MarketContext) -> list[Signal]: ...
```

`fitted.preprocessing_state_hash` already exists and already binds the fit to its standardization
state, so the integrity check is cheap and real. Use it; do not add a parallel binding.

## Five hard problems (this is where the work actually is)

### P1 — Feature identity is the whole ballgame

Execution features MUST be computed by the same code as training features. If they diverge by even
a rounding mode, the model is scored on a distribution it was never fitted on and every metric in
the evidence store becomes a lie about live behaviour.

`_six_features()` is private at `src/quant_system/modeling/features.py:268`. It uses
`localcontext(prec=50, ROUND_HALF_EVEN)` and a 21-bar window (`FEATURE_WARMUP_BARS_V1`).

Required: promote it to a public shared kernel called by both the training dataset builder and the
adapter. **Do not reimplement it.** A reimplementation is how the second ridge got here.

Ring-1 test: property test asserting adapter-computed features are byte-identical to
`build_feature_dataset` output over the same bar window, across generated inputs.

### P2 — The bar-type gap breaks the point-in-time guarantee

| | training | execution |
|---|---|---|
| type | `PointInTimeBar` (`data/market_data.py:201`) | `PriceBar` (`core/domain.py:49`) |
| has `available_at` | **yes** | **no** |
| has `event_at` / `ingested_at` | yes | no |

`MarketContext.historical_bars` is `Mapping[str, Sequence[PriceBar]]`. `PriceBar` carries no
information-availability field, so the availability discipline the training pipeline enforces
**cannot be enforced at decision time**. This is the deepest design decision in the adapter.

**DECIDED 2026-08-22 — Option A.** Execution surfaces carry `PointInTimeBar` via a typed
`ctx.extra_data` key, sourced from the evidence store, filtered to `available_at <= decision_time`.
Rationale and rejected alternatives: `agent_context/decisions/20260822-point-in-time-bars-at-execution.md`.

Verifying the decision changed the sizing. `execution/realtime_shadow.py:327-334` passes
`current_bars={}` and `historical_bars={}` — the shadow engine gives strategies **no bar history at
all**, only the current quote. This is missing plumbing, not a type conversion. Three items not in
the original sizing are now required: an evidence-store reader serving point-in-time bar history to
execution; shadow and paper engines populating it; and a session-close decision cadence for governed
models, since `generate_signals` currently fires per quote while the model is a daily-close model.
That cadence item interacts with Red Team finding S9-B2 and must not be layered on top of it.

### P3 — Score to Signal is a lossy, undefined mapping

`predict_ridge_scores` returns unbounded Decimal text. `Signal.strength` is `float` in [0.0, 1.0]
and `Signal.side` is `Side | None`.

Needs a documented deterministic map: sign of score to side (targets were fitted as UP=+1/DOWN=-1),
magnitude squashed to [0,1], and an **abstention band** around zero inside which no signal is
emitted at all. Stay in Decimal until the final float conversion, and record the raw score in
`Signal.metadata` so a decision can be reconciled to the model.

A model that is barely above zero must abstain, not trade at strength 0.001.

### P4 — Verdict gating must fail closed

`PromotionState` (`modeling/promotion.py:26`) has REJECT, RESEARCH_ONLY, SHADOW, PAPER_PILOT, PAPER.
These are not interchangeable. The adapter must refuse:

- REJECT / RESEARCH_ONLY on any execution surface;
- a SHADOW-verdict model inside the paper pilot;
- any bundle whose `model_card_hash` does not re-derive.

Typed failure, never a silent downgrade. Note `ModelCardV1.monitoring_limits` and
`halt_and_rollback_policy` already exist on the card and are currently read by nothing — the
adapter is their natural consumer.

### P5 — Warmup and corporate actions

- Fewer than 21 bars for a symbol: emit **no** signal. Never a degraded one.
- Training features are validated against a corporate-action authority
  (`modeling/features.py:118`). Execution has no such authority. An unadjusted live series scored by
  a model fitted on adjusted history fails silently and looks like alpha decay. Needs an explicit
  rule before any live shadow run.

## Also in scope

Remove `RollingRidgeClassifier` from every execution path, or relabel `MLEquityStrategy`
research-only and block it at the surface. Leaving both is the second-calculation-path defect.

## Rejected alternatives

- **Teach `MLEquityStrategy` to load a fitted state.** Rejected: keeps the ungoverned feature
  computation, which is the actual defect.
- **Export predictions to a file for the executor to read.** Rejected: breaks the hash chain
  between model, features, and decision.
- **Compute features in the adapter from scratch.** Rejected: see P1.

## Test rings required

R1 feature identity property, score mapping, verdict gating, bundle integrity ·
R2 bundle to strategy to risk to ledger · R4 one promoted model drives a full shadow session ·
R5 short window, missing symbol, non-executable verdict, tampered bundle, hash mismatch,
standardization/fit mismatch · R6 clean suite.

Per SLICES.md rule 3, every one of these begins as a failing test.

## Ownership conflicts (binding, blocks implementation)

P1 requires editing `src/quant_system/modeling/features.py`. That path is claimed twice:

| Record | Status | Claim |
|---|---|---|
| `20260820-codex-slice4-ridge-training.md` | ACTIVE | `modeling/` files |
| `20260821-1048Z-claude-slice4-redteam-repair.md` | HANDOFF_REQUIRED | `src/quant_system/modeling/*.py` |

Implementation must not begin until those are resolved or the claim is released. The new module
itself (`execution/governed_strategy.py`) is unclaimed, but `execution/*` is under active Red Team
adjudication by `20260822-redteam-api-shadow-paper.md` — do not edit that package while it runs.

## Sizing

This is a slice, not a patch — comparable in weight to Slice 5. It changes a public contract
(`MarketContext` or its `extra_data` protocol), introduces a new evidence-bearing type, and
requires R1/R2/R4/R5/R6 under slice rule 4.

## Commands and outcomes

| Command | Outcome |
|---|---|
| `git rev-parse HEAD` | `c5f7874dd555e33cff1f998945a4893199baaeaa` |
| `grep -rn "RidgeFittedStateV1\|ModelCardV1\|predict_ridge_scores" src/` outside `modeling/` | zero results |
| `grep -rn "from quant_system.modeling" src/quant_system/server/` | zero results |
| `pytest tests/ -q` (install root, uncommitted repairs present) | `483 passed, 1 warning in 40.72s` |

## Blockers and conflicts

1. Ownership of `modeling/features.py` (above).
2. Three adjudications in flight; their findings may change the modeling and execution surfaces
   this adapter binds to. Scope is provisional until they land.
3. ~~P2 needs a founder/architect decision (Option A vs B).~~ RESOLVED 2026-08-22: Option A,
   `PointInTimeBar`. See `agent_context/decisions/20260822-point-in-time-bars-at-execution.md`.
   Resolving it enlarged the slice — see P2 for the three newly required items.

## Next safe action

Hold. Do not implement. Await the three adjudication reports, then re-validate this scope against
their findings, then seek acceptance for P2 Option A and release of the `modeling/` claim.
