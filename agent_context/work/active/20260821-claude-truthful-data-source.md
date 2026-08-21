# Active work: Truthful runtime data-source declaration

STATUS: HANDOFF_REQUIRED  
OWNER: Claude Code (Opus 5) session 21d82993  
TOOL: Claude Code  
STARTED_UTC: 2026-08-21T05:10:00Z  
STARTING_REVISION: `6a17d5e`  
WORKTREE_OR_BRANCH: `D:\quant_system_wt\data-provenance` on `claude/truthful-data-source`

## Objective

Make every runtime surface state truthfully which data it used. The certified Slice 1 Upstox V3
client requires a bearer token and fails closed without one, but no production path calls it: the
API server and the daily pipeline both run on `SyntheticDataGenerator` random walks while emitting
language and artifacts that imply real market ingestion. Close that honesty gap without
pre-empting Slice 6 (governed API) or Slice 9 (live read-only shadow).

## Owned paths

- `.env.example`
- `launcher.py`
- `scripts/daily_pipeline.py`
- `src/quant_system/data/provenance.py`
- `src/quant_system/server/app.py`
- `src/quant_system/server/schemas.py`
- `configs/upstox_config.yaml`
- `tests/test_data_provenance.py`
- `tests/test_daily_pipeline.py`
- `tests/test_server_api.py`
- `agent_context/work/active/20260821-claude-truthful-data-source.md`
- `agent_context/work/completed/20260821-claude-truthful-data-source.md`

## Non-goals

- Wiring live Upstox acquisition into the server or pipeline. That is Slice 9 scope and is not
  authorized here.
- Editing anything claimed by `20260820-codex-slice4-ridge-training.md` or
  `20260821-codex-financial-model-skill.md`.
- Editing `src/quant_system/data/market_data.py` or `market_data_evidence.py`. Both carry certified
  Slice 1/3 evidence hashes and one is inside the Slice 4 craft gate scope.
- Changing `pyproject.toml`, `uv.lock`, or any `.launch/` state file. `.launch/STATE.md` is claimed;
  Major #4 must be closed by the coordinator, not by me.
- Handling, storing, or requesting any real credential value.

## Plan

1. COMPLETE - confirm the gap with repository evidence and locate every synthetic runtime path.
2. COMPLETE - add a single provenance vocabulary and apply it to pipeline, server, and launcher.
3. COMPLETE - add failing-first tests for each declaration and prove them by mutation.
4. COMPLETE - run the repository gates in this worktree and record raw outcomes.
5. PENDING - merge after Slice 4 certification lands; coordinator to reassess Major #4.

## Current step

All code, tests, and gates are complete and green in the worktree. Nothing is committed. Awaiting
a decision on committing and on the shared-tooling defect recorded below.

## Decision rationale

Evidence for the gap: `UpstoxClient(` is constructed only in tests; `acquire_historical_daily` has
no caller in `src/` or `scripts/` outside its own compatibility adapter; the server calls
`SyntheticDataGenerator.generate_equity_bars` at `app.py:149,355,414` and the pipeline at
`daily_pipeline.py:98` while `daily_pipeline.py:93` logged "Ingesting and validating point-in-time
market data". `configs/upstox_config.yaml` declared `${UPSTOX_API_KEY}` but has zero readers
repo-wide and `ConfigLoader.load_yaml` performs no environment expansion, so the placeholder was a
trap that invites a live key into a tracked file.

Chose a separate worktree over the shared checkout because this task adds source files and tests,
which shifts repository-wide gate counts. The Slice 4 record pins exact evidence numbers and is
awaiting independent verification, so mutating those counts in the shared checkout would corrupt
another agent's certification. PROTOCOL section 1 requires isolation when work touches tests or
repository-wide gate artifacts.

Absent credentials are reported as `[WARN]`, never `[FAIL]`. Running without a provider token is a
supported research configuration; failing the boot would break every existing user to make a
disclosure point.

`SyntheticSourcedResponse` defaults to the synthetic labels rather than requiring each endpoint to
opt in. A future endpoint backed by real acquisition must override them explicitly, so the failure
mode of forgetting is understating realness rather than overstating it.

Rejected: expanding `${VAR}` placeholders inside `ConfigLoader`. That would make a dead config file
look live and would create a second credential path competing with `os.getenv` in `upstox.py`. One
credential source is safer than two.

Rejected: fixing `scripts/check-tests.mjs`. The defect is real (see Blockers) but the file is shared
gate tooling that the active Slice 4 gate depends on, and PROTOCOL section 4 reserves it for
single-owner coordination.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git worktree add /d/quant_system_wt/data-provenance -b claude/truthful-data-source HEAD` | PASS | Isolated at `6a17d5e`; main checkout untouched. |
| `ruff format --check .` | PASS | 199 files already formatted. |
| `ruff check .` | PASS | All checks passed. |
| `mypy src` | PASS | No issues in 83 source files. |
| `mypy src launcher.py scripts` | PASS | No issues in 86 source files. First clean run of this invocation; `.launch/COMMANDS.md` records it as FAIL. |
| `pytest --cov=quant_system` | PASS | 272 passed; 5,830 statements / 660 missed / 89%. `provenance.py` at 100%. |
| `vulture src launcher.py scripts --min-confidence 80` | PASS | Zero findings. |
| `detect-secrets scan --all-files` (gate-exact exclusions) | PASS | 0 candidates after one `pragma: allowlist secret` on a variable-name constant. |
| `node scripts/check-code.mjs` (owned paths) | PASS | New files clean; pre-existing legacy findings unchanged at 8 (measured against base by stash). |
| `node scripts/check-tests.mjs` (owned tests) | PASS | Clean after annotating a checker defect; see Blockers. |
| Five source mutations applied and restored | PASS | Every mutation turned the intended test red; zero `MUTANT` markers remain. |

### Mutation evidence

| Mutation | Test killed |
|---|---|
| `market_data_credentials_configured` always returns `True` | 5 tests across provenance, launcher, and diagnostics |
| Original "Ingesting and validating point-in-time market data" log restored | `test_daily_pipeline_does_not_claim_to_ingest_market_data` |
| `BacktestRunResponse` drops `SyntheticSourcedResponse` | `test_api_results_declare_their_data_source[backtest]` |
| `RuntimeDataSource.UPSTOX_HISTORICAL` set to a parallel spelling | `test_real_source_label_matches_the_governed_vocabulary` |
| Markdown report disclosure banner removed | `test_daily_pipeline_declares_synthetic_source_in_every_artifact` |

## Files changed

- `src/quant_system/data/provenance.py`: NEW. Single runtime data-source vocabulary, disclosure
  text, and a presence-only credential check that never returns or logs the token value. The live
  label is bound to the governed `UPSTOX_HISTORICAL_SOURCE` constant rather than respelled.
- `scripts/daily_pipeline.py`: replaced the misleading ingest log with an explicit synthetic
  warning; added `data_source` and `data_source_disclosure` to `DailyPipelineSummary` and its JSON
  artifact; added a disclosure banner above the first figure in the markdown report; corrected the
  module docstring. Also fixed a strict-Mypy re-export error by importing `RiskLimits` from its
  defining module `quant_system.risk.checks`.
- `src/quant_system/server/schemas.py`: added `SyntheticSourcedResponse` base carrying
  `data_source` and `data_source_disclosure`; `BacktestRunResponse`, `MonteCarloResponse`, and
  `PortfolioOptimizeResponse` now inherit it; `DiagnosticsReport` gained `market_data_source` and
  `market_data_credentials_configured`.
- `src/quant_system/server/app.py`: declares the source explicitly at each of the three
  synthetic-backed response sites and reports credential presence in diagnostics.
- `launcher.py`: added preflight check 6 disclosing credential state, so a clean preflight can no
  longer be read as "connected to live data". Absent credentials warn and still boot.
- `configs/upstox_config.yaml`: removed the never-expanded `${UPSTOX_API_KEY}` /
  `${UPSTOX_ACCESS_TOKEN}` placeholders and documented that credentials are environment-only.
- `.env.example`: NEW. Names the two variables with empty values and documents that there is no
  config-file or dotenv credential path.
- `tests/test_data_provenance.py`: NEW. 11 cases covering credential presence detection, the
  behavioural env-var-name sync with `UpstoxClient`, token non-disclosure, vocabulary binding, and
  both launcher states.
- `tests/test_daily_pipeline.py`: 2 added cases proving every artifact declares the source and that
  no log claims ingestion.
- `tests/test_server_api.py`: 3 added cases (one parameterized over all three endpoints) proving
  responses declare their source and that diagnostics never echoes the token.

## Blockers and conflicts

No path conflicts. Every owned path is disjoint from both active Codex records, and the worktree
lives outside the repository so it cannot appear in the shared checkout's `git status`.

Two items need a coordinator decision:

1. **Shared-tooling defect, not fixed here.** `scripts/check-tests.mjs` `caseBody()` (line 207)
   stops collecting a test body at the first line indented at or below the `def`, and its
   closing-bracket guard `/^\s*[})\]]*\s*$/` does not match Python's `) -> None:`. Every multi-line
   Python test signature therefore reports a false `no-assertion`. Seven of my tests are annotated
   `test-allow: no-assertion` with that reason; one was collapsed to a single line because it fit
   within 100 characters. The correct fix is in the checker, but it is shared gate tooling under
   PROTOCOL section 4 and changing it could surface new findings in Slice 4 files mid-certification.
2. **Major #4 is only partially addressed.** Runtime surfaces now tell the truth, but the
   underlying gap — certified acquisition with no production caller — remains until Slice 9.
   `.launch/STATE.md` is claimed by the Slice 4 record, so I did not touch it.

## Stop point

All work complete and green in the worktree at branch `claude/truthful-data-source`, based on
`6a17d5e`. Nothing staged, nothing committed. Working tree contains 7 modified and 4 new files.

## Next safe action

Commit the branch, then merge into `main` only after Slice 4 certification completes, so the added
tests do not perturb the Slice 4 gate counts under independent verification. On merge, re-run the
repository gates and let the coordinator reassess open Major #4 in `.launch/STATE.md`.
