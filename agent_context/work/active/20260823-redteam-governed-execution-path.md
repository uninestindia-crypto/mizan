# Red Team: governed execution path

STATUS: IN_PROGRESS  
AGENT: Claude Code — Red Team (independent of the author)  
COORDINATION_RECORD_BY: the authoring agent, who created this file for visibility only and performs
no part of the adjudication  
STARTED_UTC: 2026-08-23T02:00:00Z  
STARTING_REVISION: `1e5beb5`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (read-only to the Red Team)

## Why this record exists

The governed execution path was written in this session by one agent, who also wrote its tests and
the records asserting it works. Every "verified" in those records is self-reported. QuantOS
governance requires that an author not adjudicate their own work, and
`.launch/reports/quarantine/README.md` documents what happened the last time that boundary slipped.

## Target

| File | What it claims to do |
|---|---|
| `src/quant_system/execution/governed_strategy.py` | Bind execution to a promoted model's artefacts; long-only; verdict-gated |
| `src/quant_system/execution/bar_history.py` | Serve point-in-time bars filtered to `available_at <= decision_time` |
| `src/quant_system/execution/maturity.py` | Prevent a two-session model from closing intraday |
| `src/quant_system/execution/realtime_shadow.py` (the parts changed at `11ee334`, `e6f42b1`, `9470d97`) | Populate `GOVERNED_BARS_KEY`; guard maturity |
| `src/quant_system/modeling/features.py`, `preprocessing.py` | Kernel promotion; no arithmetic change claimed |
| `scripts/run_governed_shadow_session.py` | Reconstruct a bundle from real evidence without inventing a verdict |

## Owned paths (Red Team)

- `agent_context/work/active/20260823-redteam-governed-execution-path.md` (this file)
- `.launch/reports/RED-TEAM-GOVERNED-EXECUTION.md` (final report)

Nothing else is written. The adjudication is read-only against the tree.

## Standing instruction to the adjudicator

Do not trust any work record. Verify every claim against code and by running it.

## Findings

To be written by the Red Team.
