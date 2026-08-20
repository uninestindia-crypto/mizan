# QuantOS — Quickstart & Collaborator Onboarding

Welcome to **QuantOS** (Institutional-Grade Modular Quantitative Trading, Backtesting, and Governance System).

This guide provides everything needed for a human developer or AI agent (Codex, Claude Code, Cursor, Antigravity) to pick up development immediately.

---

## 1. Prerequisites & Environment Setup

### System Requirements
- **Python**: `>=3.12` (Python 3.12 or 3.13 recommended)
- **Package Manager**: [uv](https://docs.astral.sh/uv/) (recommended) or standard `pip` / `venv`
- **Git**: Configured for private repository access

### Clone and Install
```bash
# Clone the private repository
git clone https://github.com/uninestindia-crypto/quant-system.git
cd quant-system

# Option A: Using uv (Fastest & Recommended)
uv sync --frozen --extra dev

# Option B: Using standard Python venv
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -e ".[dev]"
```

---

## 2. Verify Repository Health (Instant Smoke Test)

Run the full automated test suite to ensure your environment is 100% sound:

```bash
# Run pytest across the entire repository
uv run pytest
```
*Expected result: 205 passed tests with zero failures.*

To run the exact Slice 3 quality gate (unit tests, coverage, strict Mypy, Ruff, dead-code, and secret scan):
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-slice3-gates.ps1
```

---

## 3. Current Project State & Release Slices

QuantOS is built using rigorous, risk-ordered vertical slices under `.launch/`:

| Slice | Name | Status | Authoritative Docs |
|:---:|---|:---:|---|
| **Slice 1** | Real Point-in-Time Acquisition (Upstox V3) | ✅ **PASS** | `.launch/SLICE-01-EVIDENCE.md` |
| **Slice 2** | Canonical Content-Addressed Evidence Store | ✅ **PASS** | `.launch/SLICE-02-EVIDENCE.md` |
| **Slice 3** | Executable Point-in-Time Features & Labels | 🟡 **CANDIDATE** (205 tests passing, Red Team remediations committed) | `.launch/SLICE-03-EVIDENCE.md` |
| **Slice 4** | One Governed Ridge Fold & Preprocessing | ⏳ **NEXT UP** | `.launch/SLICES.md` |
| **Slice 5–12** | Holdout/Promotion, API/UI, Financial Research, Shadow Replay, Paper Pilot, Desktop | 📋 Planned | `.launch/SLICES.md` |

- Authoritative release gates and criteria: [`.launch/STATE.md`](.launch/STATE.md) and [`.launch/SLICES.md`](.launch/SLICES.md).

---

## 4. Multi-Agent & Cross-Tool Protocol

This repository is designed for concurrent multi-agent collaboration (Codex, Claude Code, Cursor, Antigravity, Human).

### Protocol Rules (`AGENTS.md` & `agent_context/`)
1. **Never edit without a work record**: Check [`agent_context/work/active/`](agent_context/work/active/) to see who is currently working on what.
2. **Create an active record**: Copy [`agent_context/templates/work-item.md`](agent_context/templates/work-item.md) into `agent_context/work/active/YYYYMMDD-agent-task.md` and declare exact owned paths before making edits.
3. **Move to completed on finish**: Move your record to [`agent_context/work/completed/`](agent_context/work/completed/) and write a handoff if unfinished work remains.
4. **Context Safety**: Never commit credentials, `.env` files, or private keys.

---

## 5. Where to Pick Up Next

1. **Review Context**: Read [`agent_context/CURRENT.md`](agent_context/CURRENT.md) and [`agent_context/handoffs/20260820-next-agent.md`](agent_context/handoffs/20260820-next-agent.md).
2. **Slice 3 Verification**: Independent Red Team recheck on candidate commit or proceed to **Slice 4** (One Governed Ridge Fold).
3. **Slice 4 Objective**: Fit the existing six-feature ridge family with train-side preprocessing, record every attempt, compare the four baselines, and reproduce prediction/metric hashes without data leakage.

---

## 6. Directory Map

- `src/quant_system/`: Core application modules
  - `modeling/`: Governed point-in-time features, labels, folds, and rows (Slice 3)
  - `evidence/`: Canonical content-addressed evidence store (Slice 2)
  - `data/`: Market data acquisition and parsing (Slice 1)
  - `alpha/`, `analytics/`, `backtest/`, `portfolio/`, `risk/`, `strategies/`, `server/`: System components
- `tests/`: Pytest suite with deterministic fixtures and adversarial regression tests
- `agent_context/`: Coordination system, active work logs, handoffs, and architectural decisions
- `.launch/`: Release state, formal slice specifications, and immutable verification evidence
