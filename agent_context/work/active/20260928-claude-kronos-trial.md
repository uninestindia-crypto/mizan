# Active work: Kronos zero-shot trial (short-horizon trial 10)

STATUS: ACTIVE  
OWNER: Claude Code session, on founder instruction (2026-09-28: "yes" to planning a governed Kronos
trial, then "yes go ahead" to the explained plan, its downloads and its three conflicts)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-28T05:40:00Z  
STARTING_REVISION: e787ac462fe9c9d188ab8974109c3bdbd59b46b2  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, new files only, disjoint paths
with written claims). Isolated environment, not a Git checkout:
`D:\quant_system_workspaces\scratch\kronos-trial-20260928`

## Objective

Run one pre-declared, cost-aware test of Kronos, the finance-pretrained foundation model (MIT), on
the same NSE data, subset, labels and costs as short-horizon trials 1-9. Record the result whatever
it is.

## Founder decisions recorded here (2026-09-28)

1. **Override of the standing instruction "Do not run a tenth trial"** in
   `reports/short_horizon/TRIAL-LEDGER.md`. The founder chose to run exactly one Kronos trial as
   trial 10. Every short-horizon DSR would re-deflate against 10, and later candidates face a higher
   bar. No further Kronos variant, retraining or sweep follows, whatever the result.
2. **New files only.** Files claimed by
   `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` are imported, never edited.
   A notice tells that record what this trial changes.
3. **The window uses the final year** the short-horizon program reserved as its holdout.
4. **Downloads approved:**
   - the Kronos model code, pinned to `67b630e67f6a18c9e9be918d9b4337c960db1e9a`;
   - `NeoQuasar/Kronos-Tokenizer-base`, `Kronos-small` and `Kronos-base`;
   - PyTorch and helper packages, into the isolated environment only.

## Owned paths

- `agent_context/work/active/20260928-claude-kronos-trial.md` (this record)
- `agent_context/work/active/20260928-NOTICE-kronos-trial-10-declared.md` (new)
- `reports/kronos_trial/**` (new)
- `scripts/generate_kronos_forecasts.py` (new)
- `scripts/run_kronos_trial.py` (new)
- `tests/test_kronos_trial.py` (new)
- Workspace `D:\quant_system_workspaces\scratch\kronos-trial-20260928` (created by this task)

## Non-goals

- No edit to any short-horizon file, the QuantOS `.venv`, `pyproject.toml` or `uv.lock`.
- No fine-tuning, no second model size after results, no hold other than 3, no threshold search.
- No change to either paper book, its tasks or its code, and no compute during market hours.
- Nothing is promoted and no live-money path exists, whatever the result.

## Plan

1. Record and claims. DONE.
2. Isolated environment; download and read the pinned Kronos code. DONE (native ARM64).
3. Frozen declaration, `reports/kronos_trial/TRIAL-LEDGER.md`, before any real forecast. DONE and
   committed.
4. Download the weights. DONE. Timing probe on synthetic bars after 16:30 IST; fix the scope by the
   declared rule (Amendment 1).
5. Generator, scorer and tests. DONE. Forecasts run off-hours.
6. Score once, record SPENT, report to the founder.

## Current step

4: the probe waits for the market to close. The founder's flagship session is running today, and
the declaration keeps weekday market hours for the paper books.

## Decision rationale

- **Why Kronos and not another general model.** Independent evidence (Rahimikia, Ni, Wang, arXiv
  2511.18578) found off-the-shelf time-series foundation models "perform poorly" on financial data.
  Models pre-trained on financial data did better. Kronos is the only open model of that kind. It
  is MIT-licensed, so it could sit in a commercial path.
- **Why only dates from 2024-07-01.** The Kronos paper (arXiv 2508.02739) says its pre-training
  data "extends up to June 2024" and lists India (XNSE) among its in-distribution exchanges. Any
  earlier target could have been memorised.
- **Why a fixed cost threshold instead of the C1 abstention grid.** The clean window is about 530
  sessions, too short for the harness's 756-session minimum training span. A fixed rule, "forecast
  beats the 0.224% round trip", has nothing to calibrate, so the whole window is out of sample and
  is scored exactly once.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Download `model/{__init__,kronos,module}.py` at `67b630e6` | PASS | git blob SHA-1 matches the commit for all three; read in full: no network except the Hub, no file writes, no subprocess |
| `uv venv` with native ARM64 CPython 3.12.10 | PASS | PyPI has no `win_arm64` torch; `torch 2.14.0+cpu` came from download.pytorch.org |
| Weights download | PASS after one retry | The Hub cache needs symlinks the account cannot create (WinError 1314). Plain `local_dir` folders are used instead; revisions and SHA-256 are in the ledger and in `weights/pinned-revisions.json` |
| QuantOS loaders under the isolated interpreter | PASS | `train_mizan`, `build_mizan_feature_store`, `run_short_horizon_experiment` import in 1.2 s |
| `pytest tests/test_kronos_trial.py` | PASS | 27 passed |
| `node scripts/check-tests.mjs` on the new tests | PASS | clean after one loop became a parametrized case |
| `ruff check`, `ruff format --check`, `mypy src launcher.py scripts` | PASS | 220 source files |

## Files changed

- `reports/kronos_trial/TRIAL-LEDGER.md` (new): the frozen declaration.
- `scripts/generate_kronos_forecasts.py` (new): probe and forecast, run under the isolated
  interpreter.
- `scripts/run_kronos_trial.py` (new): scores once, refusing an existing results file.
- `tests/test_kronos_trial.py` (new).
- `agent_context/work/active/20260928-NOTICE-kronos-trial-10-declared.md` (new).
- This record.

## Blockers and conflicts

- Other agents are active today in other paths: the retail-redesign worktree, the live-dashboard
  CSP and the live risk card. None of them claims a path above.
- The laptop was on battery at 15% at 10:59 IST. Heavy compute waits for mains power and
  off-market hours.

## Stop point

Record created; nothing downloaded yet.

## Next safe action

Create the isolated environment and download the pinned Kronos code.
