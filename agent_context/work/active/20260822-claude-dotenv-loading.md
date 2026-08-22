# Active work: project-level .env loading

STATUS: COMPLETE — implemented and verified; not adjudicated  
OWNER: Claude Code — dotenv loading  
TOOL: Claude Code  
STARTED_UTC: 2026-08-22T21:30:00Z  
STARTING_REVISION: `b9377f1`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, disjoint paths)

## Objective

Nothing in this project loads `.env`. There is no `python-dotenv` in `pyproject.toml` or `uv.lock`
and no `load_dotenv` anywhere in `src/`. Three subsystems read credentials straight from the process
environment and therefore cannot see a `.env` the user has correctly filled in:

- `src/quant_system/data/upstox.py:95-96` — `UPSTOX_API_KEY`, `UPSTOX_ACCESS_TOKEN`
- `src/quant_system/data/provenance.py:45` — token-presence gate, so the product reports "no
  credential configured" when one *is* configured
- `src/quant_system/alpha/key_pool.py:128,131` — AI provider keys

Found while running the governed training runner: a correct `.env` produced a non-retryable
`PROVIDER_UNAUTHORIZED` before any HTTP request was issued. Currently worked around by a private
parser inside `scripts/run_governed_ridge_training.py`, which fixes one script and no product path.

Replace that workaround with one shared loader and wire it at the real entry points.

## Owned paths

- `src/quant_system/config/env.py` (new)
- `src/quant_system/config/__init__.py`
- `launcher.py`
- `tests/test_config_env.py` (new)
- `scripts/run_governed_ridge_training.py` (already owned by my completed runner record)
- `agent_context/work/active/20260822-claude-dotenv-loading.md` (this file)

Ownership checked at `b9377f1`: no active record claims `data/upstox.py`, `data/provenance.py`,
`config/**`, or `launcher.py`. `launcher.py` appears in other records only inside gate command
lines (`mypy src launcher.py scripts`), which is a measurement, not a claim.

## Non-goals

- **Adding `python-dotenv`.** That means editing `pyproject.toml` and `uv.lock`, which PROTOCOL §4
  lists as single-owner high-conflict files. The parser is ~20 lines; the dependency is not worth
  the coordination cost.
- **Loading `.env` at package import.** Rejected below.
- Editing `src/quant_system/alpha/**` (uncommitted Antigravity work), `modeling/**`, `execution/**`,
  or `server/**`. The fix reaches them without edits because it populates `os.environ`, which their
  existing `os.getenv` calls already read.
- `src/quant_system/data/live_feed.py` — claimed by `20260822-claude-s9b2-repair-and-cadence.md`.
- Declaring anything PASS or CERTIFIED.

## Decision rationale

**Explicit loading at entry points, not at package import.** Loading `.env` inside
`quant_system/__init__.py` would need zero call-site edits and would fix every consumer at once. I
checked whether it would break the existing suite and it would not: `test_data_provenance.py:44-45`
and `test_server_api.py:581` `monkeypatch.delenv` before asserting, and
`test_upstox_data.py:11-14` deliberately asserts only `isinstance(client.is_authenticated, bool)`
with a comment acknowledging the environment dependency.

Rejected anyway. Import-time file reads make behaviour depend on an untracked local file,
invisibly. The next test that constructs `UpstoxClient()` and asserts `is_authenticated is False`
would pass in CI and fail on a developer machine that has `.env`. This repository already has a
demonstrated fixture-versus-real divergence problem; adding a hidden environment dependency to
`import quant_system` makes it worse. The cost of the explicit approach is that a future entry point
can forget to call the loader — a visible, greppable omission rather than an invisible one.

**The environment always wins over the file.** A value already exported in the shell is never
overwritten. The process environment stays the authority and a stale `.env` cannot silently shadow
a deliberately exported credential. `override=True` exists for callers that genuinely want the file
to win, but no caller here uses it.

**Values are never returned, logged, or printed.** The loader reports only the *names* it set. This
matches the existing discipline in `provenance.market_data_credentials_configured()`, whose
docstring already states that only presence is inspected so a live credential never reaches an
evidence artifact.

## Plan

1. COMPLETE — confirm the gap and enumerate every consumer.
2. COMPLETE — ownership check; create this record.
3. Write `src/quant_system/config/env.py` and export it.
4. Wire `launcher.py` so the desktop entry point loads credentials before its prerequisite checks.
5. Replace the private parser in `scripts/run_governed_ridge_training.py` with the shared loader.
6. Add `tests/test_config_env.py`.
7. Verify: ruff, ruff format, strict mypy, and the new plus adjacent tests.

## Current step

All seven steps complete.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `grep -rn "dotenv" src/ pyproject.toml` | RUN | zero matches; nothing loaded `.env` |
| `grep -rn "os.getenv" src/quant_system/` | RUN | credential reads at `upstox.py:95-96`, `provenance.py:45`, `key_pool.py:128,131` |
| `uv run pytest -q` (baseline, my changes stashed) | RUN | the three tests I later broke all passed at `b9377f1`, establishing that I caused them |
| `uv run pytest -q` | **508 passed** | 497 pre-existing + 11 new. Three intermediate failures were mine and are described below. |
| `uv run ruff check src launcher.py scripts tests/test_config_env.py` | PASS | `All checks passed!` |
| `uv run ruff format --check ...` | PASS | `116 files already formatted` |
| `MYPYPATH=src uv run mypy src launcher.py` | PASS | `Success: no issues found in 111 source files` |
| `uv run vulture src launcher.py scripts --min-confidence 80` | PASS | exit 0, zero findings |
| `node scripts/check-code.mjs` | PASS for my files | `launcher.py` back to its exact baseline 2 findings; `config/env.py` zero |
| Real end-to-end runner check | PASS | `loaded UPSTOX_ACCESS_TOKEN, UPSTOX_API_KEY from .env`, 498 real bars, stopped at the corporate-actions guard, no evidence written, no multiplicity ordinal consumed |

### Three failures I caused, and what they taught

1. `test_launcher_warns_when_no_credentials_are_configured`. I first put `load_env_file()` inside
   `run_prerequisite_checks()`. That test calls the function directly after clearing the token, so
   my code reloaded the repository's real `.env` and the expected `[WARN]` became a pass. This is
   exactly the environment-dependent fragility I rejected import-time loading to avoid, reintroduced
   one layer up. Fixed by moving the load into `main()`; `run_prerequisite_checks` is an inspection
   of the environment it is given and must not mutate it.

2 and 3. `test_upstox_historical_request_without_token_raises_typed_error` and
   `test_missing_access_token_returns_unauthorized_without_transport_call`. My own tests leaked.
   `monkeypatch.delenv(name, raising=False)` records nothing when the variable is absent, so when
   `load_env_file` then wrote it, teardown had nothing to undo and the credential survived into
   unrelated tests asserting an unauthenticated client. Fixed with an autouse snapshot/restore
   fixture in `tests/test_config_env.py`.

Both were caught only because the full suite was run. Neither would have been caught by running the
new tests alone, which passed 11/11 from the start.

### Pre-existing flaky test, observed but not mine

`tests/test_modeling_campaign_deflation.py::test_published_deflated_sharpe_is_frozen_at_its_own_ordinal`
failed once in four full-suite runs and passes in isolation and on every re-run. I did not touch
`modeling/**`, and `tests/test_modeling_*.py` is claimed by
`20260821-1048Z-claude-slice4-redteam-repair.md`, so this is recorded rather than investigated.
**The suite should not be described as reliably green until this is understood.**

## Files changed

- `src/quant_system/config/env.py`: new. Dependency-free dotenv loader. Environment wins over file;
  returns names, never values; `only=` restricts which names load.
- `src/quant_system/config/__init__.py`: export `load_env_file`, `default_env_path`, `parse_env_text`.
- `launcher.py`: new `load_startup_environment()` called from `main()` before the preflight checks.
- `tests/test_config_env.py`: new. 11 regression tests including the two original defect paths
  (`UpstoxClient` and the provenance gate) plus an autouse environment-restore fixture.
- `scripts/run_governed_ridge_training.py`: private parser replaced by a delegation to the shared
  loader, still restricted to `UPSTOX_*` because the runner spawns `git` as a subprocess.

## Blockers and conflicts

None. All owned paths were unclaimed at `b9377f1`.

## Stop point

Implemented and verified. Working tree carries the five files above plus this record.

## Next safe action

The remaining item from the same review is the model-execution adapter: nothing outside `modeling/`
consumes `RidgeFittedStateV1`, `predict_ridge_scores`, or `ModelCardV1`, and `execution/` and
`server/` import nothing from `modeling/`, while `strategies/ml_equity.py:17` defines a second
ungoverned ridge that execution does use. That work needs `execution/**` and `modeling/**`, both
claimed by live records, so it needs founder ownership clearance first. Scope already drafted in
`20260822-claude-model-execution-adapter-scope.md`.
