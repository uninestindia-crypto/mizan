# Active work: honest advisor names, honest default panel, real consensus vote

STATUS: COMPLETED  
OWNER: Claude Code (founder-directed)  
TOOL: Claude Code  
STARTED_UTC: 2026-08-22T19:55:00Z  
STARTING_REVISION: 1cdeff41221bc18028a9f64a41b2b86f3cc8152c  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; owned paths disjoint)

## Objective

Two founder-authorised behaviour changes to the advisory panel, chosen explicitly in session on
2026-08-22 after both were presented with alternatives:

1. **Rename the two rule advisors to what they are, and drop them from the default panel.**
   `CodexCLIAdvisor` and `AntigravityCLIAdvisor` never invoke a CLI; `AntigravityCLIAdvisor` derives
   `action_bias` directly from `quant_side` and so cannot disagree with the quant signal. They stay
   importable for anyone who explicitly wants a rule on the panel; they stop being default members.
2. **Replace `opinions[0].action_bias` with a majority vote, NEUTRAL on a tie.** The panel currently
   takes its direction from whichever advisor happens to be first in the list.

Unlike the previous three records, this one **does** change behaviour. That is the point, and it is
authorised. The scope of the change is stated precisely below rather than minimised.

## Owned paths

- `src/quant_system/alpha/ai_advisor.py`
- `src/quant_system/alpha/__init__.py`
- `src/quant_system/advisory/records.py` (one stale comment naming the old classes)
- `tests/test_ai_advisor.py`
- `tests/test_panel_provenance.py`
- `tests/test_advisory_records.py`
- `tests/test_advisory_capture_wiring.py`
- `agent_context/work/active/20260822-1955Z-claude-panel-honesty-and-vote.md`

## Non-goals

- Making the rule advisors call real CLIs. Explicitly rejected by the founder: it needs binaries
  that may not exist and puts three live model calls per bar in the decision path.
- Deleting the two advisors. Rejected: the rules are reusable, they are simply not models.
- `evidence/**`, `modeling/**`, `execution/**`, `core/**`, `strategies/ml_equity.py` — claimed by
  live records.
- `strategies/ai_enhanced_ml.py` beyond a docstring correction if its class list is now wrong.
- Giving the advisory layer a vote over anything outside the panel. Observer mode is unchanged.

## Plan

1. COMPLETE - claim check, create this record.
2. COMPLETE - classes renamed; dead `cli_command` / `is_available` removed.
3. COMPLETE - default panel is `[ClaudeCLIAdvisor]` plus configured direct-API advisors.
4. COMPLETE - majority vote with NEUTRAL on tie (`_majority_action_bias`).
5. COMPLETE - all references and characterization goldens updated.
6. COMPLETE - behaviour change measured; exact numbers below.
7. COMPLETE - ruff, format, strict mypy, audits.

## Current step

Complete.

## Decision rationale

**Names.** `TrendDivergenceRuleAdvisor` (was `CodexCLIAdvisor`) thresholds `sma_distance_pct` and
`return_5d`. `SignalStrengthRuleAdvisor` (was `AntigravityCLIAdvisor`) is closed-form in
`quant_strength`. Both drop `cli_command` and `is_available`, which were defined and never called —
carrying a PATH check for a binary the class never invokes is what made the misdescription
convincing in the first place.

**Default panel.** `MultiAgentConsensusEngine.__init__` built
`[ClaudeCLIAdvisor, CodexCLIAdvisor, AntigravityCLIAdvisor]`. The default becomes `[ClaudeCLIAdvisor]`
plus any direct-API advisors the key pool supports. A caller who wants the rules passes them
explicitly. This is the change that moves money-adjacent numbers: `avg_multiplier` and
`avg_confidence` are means over panel members, so removing a member that always returns
`weight_multiplier=1.0` stops the mean being pulled toward 1.0 by a vote that carried no
information.

**Majority vote.** After the veto check returns early, no `VETO` opinions remain, so the vote is
over the surviving directions. A tie yields `NEUTRAL`, which is the fail-toward-not-trading
direction and consistent with `agent_context/CURRENT.md`'s own finding that `NO_TRADE` beat the
ridge candidate on 26 of 40 published models.

**Measured scope of the behaviour change.** `AIEnhancedMLEquityStrategy` branches on the aggregate
only via `action_bias == "VETO"` or `weight_multiplier <= 0.0`; it never distinguishes BULLISH from
NEUTRAL from BEARISH. The vote change therefore cannot alter this strategy's decisions — it alters
what the aggregate *reports*, which matters for the journal and for any future consumer. The default
panel change **does** alter this strategy's decisions, through `avg_multiplier` and `avg_confidence`.
Both claims are pinned by tests rather than asserted.

**Rejected alternative: deprecation aliases for the old class names.** The platform is unreleased
(`.launch/STATE.md`: P5, release candidate, not shipped) and every reference is inside this
repository. Aliases would preserve the misleading names in the public surface indefinitely, which is
the exact thing being repaired.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv run ruff check src/quant_system tests/` | PASS | `All checks passed!` (2 import-order fixes applied) |
| `uv run ruff format --check` | PASS | `125 files already formatted` |
| `uv run mypy --strict src` | PASS | `Success: no issues found in 119 source files` |
| `uv run pytest` (10 affected files) | PASS | **202 passed** |
| `scripts/audit-agent-claims.ps1` | PASS | exit 0 |
| `scripts/audit-disk-layout.ps1` | PASS | exit 0 |

Own diff: `alpha/__init__.py` +8/-8, `alpha/ai_advisor.py` +120 net, `strategies/ai_enhanced_ml.py`
docstring only. The `core/ledger.py`, `modeling/holdout.py`, and `modeling/stress.py` changes in the
same tree belong to other agents and were not touched.

### Measured behaviour change

Run directly, old default panel versus new, on the deterministic synthetic fixture used by
`test_ai_enhanced_ml_strategy_signal_generation` (`train_window=30, top_n=2, threshold=0.50`):

| Panel | Members | Selected | strength | target_weight |
|---|---|---|---:|---:|
| Old default | Claude + TrendDivergence + SignalStrength | INFY | 0.316253 | 0.350000 |
| New default | Claude | INFY | **0.267498** | 0.350000 |

**What moved:** `strength`, by roughly 15%. `candidate_scores[symbol] = prob_up * ai_opinion.confidence`,
and `avg_confidence` was a mean over three members. `SignalStrengthRuleAdvisor` returns
`confidence = min(0.95, max(0.5, quant_strength + 0.05))`, which is above the fallback's confidence
here, so its vote was inflating the panel's stated conviction without contributing information.

**What did not move:** the instrument selected, and `target_weight`. The weight is unchanged only
because `min(0.35, base_weight * mult)` binds at the cap in this fixture; with more candidates than
`top_n`, or a smaller `base_weight`, the multiplier change would surface. Do not read the unchanged
weight as evidence that weights are unaffected in general.

**The vote change moved nothing in this strategy**, as predicted in the rationale:
`AIEnhancedMLEquityStrategy` branches on the aggregate only via `action_bias == "VETO"` or
`weight_multiplier <= 0.0` and never distinguishes BULLISH from NEUTRAL from BEARISH. The vote
changes what the aggregate *reports* — which is what the journal records and what any future
consumer would read — not what this strategy does. Pinned by
`test_the_vote_is_not_the_first_advisors_opinion` and the split-panel cases.

## Blockers and conflicts

`tests/test_ai_*.py` is listed as a non-goal by `20260821-1048Z-claude-slice4-redteam-repair`, so it
is unclaimed and free to edit. `alpha/**` remains unclaimed: its implementing record is COMPLETED
and the three records naming it list it as a non-goal.

## Files changed

- `src/quant_system/alpha/ai_advisor.py`: `CodexCLIAdvisor` -> `TrendDivergenceRuleAdvisor`,
  `AntigravityCLIAdvisor` -> `SignalStrengthRuleAdvisor`, dead `cli_command`/`is_available` removed,
  default panel reduced to `[ClaudeCLIAdvisor]`, `_majority_action_bias` replaces `opinions[0]`,
  module docstring corrected
- `src/quant_system/alpha/__init__.py`: renamed exports
- `src/quant_system/advisory/records.py`: two stale comments corrected
- `src/quant_system/strategies/ai_enhanced_ml.py`: class docstring no longer names Codex/Antigravity
- `tests/test_panel_provenance.py`: +6 cases for the default panel and the vote (26 total)
- `tests/test_ai_advisor.py`, `tests/test_advisory_records.py`: renamed references

## Stop point

Complete and verified. Working tree carries the changes uncommitted.

## Next safe action

Nothing required. Two observations for whoever picks this up:

1. **The default panel is now a single advisor**, so "consensus" is nominal until a second one that
   can reach a model is configured. `DirectAPIAdvisor` members are added automatically when the key
   pool holds keys for a provider, so supplying credentials is what makes the panel plural again.
2. **`ClaudeCLIAdvisor` still falls back silently to an RSI rule** when `claude` is not on PATH or
   the subprocess fails. That is now visible in the records as `HEURISTIC_FALLBACK`, but the panel
   itself does not surface it to the caller. Making the fallback loud is a separate decision.
