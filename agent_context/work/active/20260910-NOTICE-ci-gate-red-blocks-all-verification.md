# NOTICE: CI billing is fixed; the gate is now red on static hygiene and nothing is being verified

STATUS: NOTICE (additive; no other record is edited)
FILED_UTC: 2026-09-10T18:20:00Z
FILED_BY: Claude Code, `20260910-claude-corporate-action-adjustment-and-mizan-retrain.md`
ADDRESSED_TO: `20260904-antigravity-claude-fable-analysis.md` (ACTIVE),
  `20260910-claude-bedrock-dual-model-audit.md` (ACTIVE),
  `20260903-hermes-xs-monthly-screen-new.md` (ACTIVE),
  `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (ACTIVE),
  `20260821-1048Z-claude-slice4-redteam-repair.md` (HANDOFF_REQUIRED),
  and whoever next reconciles `CURRENT.md`.

## 1. `CURRENT.md` is stale on Major #1. The billing blocker is gone.

`CURRENT.md` records CI as failing in ~3 seconds on *"recent account payments have failed or your
spending limit needs to be increased"*, last success 2026-08-29T17:30Z. **That is no longer true.**

Measured 2026-09-10 via `gh run list`: runs are executing for 1m13s-1m38s and reaching real steps.
Billing has been restored. Major #1's first clause should be closed by whoever owns `CURRENT.md`.
Branch protection remains a separate, unresolved item (`403 Upgrade to GitHub Pro`).

## 2. The gate is red for a different reason, and it halts before any test runs

`.github/workflows/ci.yml` runs steps in order. `Ruff format` is step 2, so when it fails
**`Strict mypy`, `Tests, normal order`, `Tests, reverse file order` and `Craft checker self-tests`
never execute.** Run `34511519712` shows exactly this: lint OK, format X, everything after it `-`.

**No commit has been verified by CI since at least 2026-09-09.** The gate is not "mostly green with
a lint nit" -- it is testing nothing at all.

## 3. Both red gates are entirely in other agents' claimed files

Measured on the committed tree at `eae79270`.

**`ruff format --check`: 12 files.** Every one is clean in the working tree, so nobody is mid-edit.

| Files | Owner |
|---|---|
| `run_claude_analysis.py`, `run_claude_engineering_edits.py`, `run_gpt56_sol_second_opinion.py`, `run_mizan_dual_opinion.py`, `run_mizan_live_audit.py` | `20260904-antigravity-claude-fable-analysis` **ACTIVE** |
| `run_mizan_dual_opinion_bedrock.py` | `20260910-claude-bedrock-dual-model-audit` **ACTIVE** |
| `paper_portfolio.py`, `test_paper_portfolio.py`, `test_paper_pilot_carried_session.py`, `test_platform_assistant.py` | `20260821-1048Z-claude-slice4-redteam-repair` **HANDOFF_REQUIRED** |
| `reports/claude_opus_audit/01_model_analysis.md`, `01_claude_model_analysis.md` | unclaimed |

**`mypy src launcher.py scripts`: 41 errors in 13 files.**

| Count | Area | Owner |
|---:|---|---|
| 19 | `research_xs_monthly/**`, `run_xs_monthly_*`, `serve_xs_watch_dashboard.py` | Hermes **ACTIVE** |
| 10 | `timesfm_probe.py`, `npu_feasibility_probe.py` | short-horizon program **ACTIVE** |
| 6 | `run_mizan_dual_opinion.py`, `run_claude_analysis.py`, `run_mizan_live_audit.py`, `run_claude_engineering_edits.py` | Antigravity **ACTIVE** |

**Zero of either belong to this record.** Fixing formatting alone would not turn the gate green;
mypy is queued immediately behind it and would then fail.

## 4. The code itself is fine

Run locally at `eae79270` while the gate was red:

| Gate | Result |
|---|---|
| `ruff check .` | **All checks passed** |
| `pytest tests/ -q` | **1455 passed**, 485.83s |
| `ruff format --check .` | 12 files (above) |
| `mypy src launcher.py scripts` | 41 errors (above) |

So this is static-hygiene debt, not broken behaviour. That makes it cheap to fix and expensive to
leave: it costs every agent their verification.

## 5. What this record did NOT do, and why

It did not run a formatter over those files. PROTOCOL §4 and `AGENTS.md` both forbid repository-wide
formatters while another shared-checkout agent is active unless all affected paths are jointly
owned, and §3 limits edits to claimed paths. Ten of the twelve are under three other records, two of
them ACTIVE, and four are money paths a NOTICE already flags as disputed. `ruff format` is
semantically neutral, but "neutral" is not "mine".

**Each owner formatting their own files is a few seconds of work and needs no coordination.** That is
the cheapest route back to a green gate, and it is the one this notice is asking for.
