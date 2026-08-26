# Handoff: cross-sectional execution, two adjudications, two repairs

FILED_UTC: 2026-08-26
FROM: Claude Code — `20260826-claude-cross-sectional-execution-path.md` (now in `work/completed/`)
STATUS: work complete; three items remain, none of them mine to close

## What is done and verified

| Item | Evidence |
|---|---|
| Cross-sectional governed execution path | `execution/cross_sectional_strategy.py` + 36 tests. Committed at `c5143c90` |
| Recheck of the training-path adjudication | `.launch/reports/RECHECK-ADJUDICATION-TRAINING-PATH.md` |
| Independent adjudication of today's three subsystems | `.launch/reports/ADJUDICATION-TODAYS-SUBSYSTEMS-RECHECK.md` — BLOCKED, 1 P1 + 1 P2 |
| P1 repair (MizanStrategy on an execution surface) | `research_only = True`; `StrategyRegistry.create("Mizan")` now REFUSED |
| P2 repair (assistant fabricated risk limits) | reads live `_CURRENT_RISK_LIMITS`; proven to track changes |
| Cost sensitivity screen | `work/completed/20260826-claude-cost-sensitivity-screen.md` — falsified the cost hypothesis |
| Research design brief | `.launch/RESEARCH-DESIGN-BRIEF-NEXT-CAMPAIGN.md`, corrected after the screen |

Gates at handoff: **1019 tests passed**, ruff clean, `ruff format --check` clean across 468 files,
`mypy src launcher.py scripts` clean across 166 source files, both audit scripts PASS.

## Remaining item 1 — the P1/P2 repairs want an independent recheck

I found both defects **and** repaired them, on explicit founder instruction. That collapses the
author/adjudicator boundary the recheck existed to enforce, so the repairs carry my word rather than
an independent verdict. A third party should confirm:

- `StrategyRegistry.create("Mizan")` and `create("MizanStrategy")` are refused at the shadow surface.
- No research or backtest path was broken by the refusal.
- `_handle_inspect_risk_limits` reports live state and never invents a cap.

## Remaining item 2 — two documents still overstate

- `.launch/reports/ADJUDICATION-TRAINING-PATH.md` needs its section 1 attribution corrected and its
  N=110 figure changed from `0.169377` to `0.133380`. The exact replacement text is in section 7 of
  my recheck. Its verdict survives.
- `.launch/reports/ADJUDICATION-TODAYS-SUBSYSTEMS.md` should be relabelled an author self-assessment,
  not an independent adjudication.

Neither is mine to edit; both belong to their author. Details in
`work/active/20260826-NOTICE-adjudication-reports-need-recheck.md`.

## Remaining item 3 — Major #1 is marked CLOSED with half of it undone

The CI workflow half is genuinely closed (run `#32936340154`, green, 3m30s). Branch protection is
**not set and cannot be set** on this account: `gh api .../branches/main/protection` returns
`403 Upgrade to GitHub Pro or make this repository public`. `.launch/STATE.md` now drops the
requirement rather than recording it blocked, so a reader learns the gates run but not that nothing
enforces them on merge. See `work/active/20260826-NOTICE-branch-protection-unavailable-on-plan.md`.

## Not done, deliberately

The live Mizan paper harness. Three blockers remain and are named in the completed record: no
library kernel for the v3 fifteen-feature family (it lives in `scripts/build_mizan_feature_store.py`
in float), no live point-in-time source for the three macro features, and
`realtime_shadow.py:464` serves one symbol per decision. The verdict gate is a fourth and is not an
engineering task.
