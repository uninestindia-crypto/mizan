# Completed work: QuantOS financial model craft skill

STATUS: COMPLETE
OWNER: Codex root agent
TOOL: Codex
STARTED_UTC: 2026-08-20T22:45:50Z
COMPLETED_UTC: 2026-08-20T23:21:53Z
STARTING_REVISION: `8d09ec4ecb597aaef551b30200f1818554f7e399`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

Create and validate a project skill that makes financial calculations, cost-aware research,
ledger reconciliation, risk metrics, and promotion evidence conform to QuantOS's accepted finance
contracts.

## Owned paths

- `.agents/skills/financial-model-craft/**`
- `agent_context/work/active/20260821-codex-financial-model-skill.md`
- `agent_context/work/completed/20260821-codex-financial-model-skill.md`

## Non-goals

- Authorizing live-money routing, changing production finance/model code, or replacing the
  point-in-time, model-governance, and NSE-execution skills.
- Defining generic investment advice or unsupported corporate-valuation workflows.

## Work completed

1. Derived the skill's decision-changing rules from accepted QuantOS contracts.
2. Wrote a discriminating entrypoint and conditional financial-integrity protocol.
3. Validated its structure and independently forward-tested it against realistic QuantOS finance
   paths using 45 focused tests plus adversarial in-memory probes.
4. Added forward-test requirements for rejected-event atomicity, independent reconciliation,
   risk-state persistence, cost-consumer versus authority-producer boundaries, user-visible claim
   review, and carefully bounded statistical floating point.

## Decision rationale

The skill is scoped to the financial-integrity seam across research, accounting, execution costs,
and promotion. Existing specialized skills remain authoritative for market-data ingestion,
predictive-model governance, and NSE execution mechanics. Production finance defects found by the
forward test remain program work rather than being hidden inside this skill-only change.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Read `skill-creator/SKILL.md` | PASS | Required anatomy, scope, validation, and forward-test guidance loaded. |
| Inspect finance ACs and adjacent skills | PASS | Scope boundaries and accepted Decimal/reconciliation contracts identified. |
| Initial `quick_validate.py .agents/skills/financial-model-craft` | PASS | `Skill is valid!` |
| Independent 45-test forward review | PASS | Correctly held the codebase at deterministic `RESEARCH_ONLY`; reproduced ledger, cost, risk, and metric defects omitted by current tests. |
| Final `quick_validate.py .agents/skills/financial-model-craft` | PASS | Amendments retained valid skill structure. |

## Files changed

- `.agents/skills/financial-model-craft/SKILL.md`: routing, invariants, refusal conditions, and
  required review questions.
- `.agents/skills/financial-model-craft/references/financial-integrity-protocol.md`: effective-dated
  rules, exact accounting, risk governor, metrics, adverse cases, and proof requirements.
- This completed coordination record.

## Findings handed to the program

- The legacy ledger can mutate cash on a rejected naked sell and can double-post duplicate fills.
- Existing reconciliation is not an independent reconstruction and realized P&L omits entry fees.
- Legacy NSE costs are timeless/stale and accept invalid negative quantities.
- The risk governor does not enforce all declared limits or persist critical risk state.
- Legacy metrics and tearsheet claims exceed their financial evidence.
- A finance-integrity implementation slice is required before opening a real final holdout or
  claiming shadow/paper readiness.

## Stop point

The skill is structurally valid, independently useful, and complete. No production finance code was
changed. Live-money routing remains excluded.
