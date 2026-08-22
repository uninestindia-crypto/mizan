# Active work: real-data governed ridge training runner

STATUS: COMPLETED — scope delivered. **The real-data path is NOT proven.** The runner exists and
stops correctly at a typed provider refusal; stages 2-7 have never executed on real bars. Work
remains and is carried by
`agent_context/handoffs/20260822-claude-real-data-training-runner-handoff.md`.  
OWNER: Claude Code — real-data training runner  
TOOL: Claude Code  
STARTED_UTC: 2026-08-22T19:05:00Z  
STARTING_REVISION: `c5f7874dd555e33cff1f998945a4893199baaeaa`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, disjoint paths)

## Objective

The governed training stack in `src/quant_system/modeling/` is implemented and tested but has no
production caller: `run_persisted_ridge_trial()`
(`src/quant_system/modeling/training_evidence.py:131`) is reachable only from tests. Build the
missing entry point — a runner that chains real Upstox acquisition -> `build_feature_dataset` ->
`build_label_dataset` -> `build_purged_fold` -> `run_persisted_ridge_trial`, writing to a real
`EvidenceStore` — and attempt the real-data path.

## Owned paths

- `scripts/run_governed_ridge_training.py` (new file, created by this record)
- `agent_context/work/completed/20260822-claude-real-data-training-runner.md` (this file, moved here
  from `work/active/` at completion)
- `agent_context/handoffs/20260822-claude-real-data-training-runner-handoff.md`

Nothing else in the repository will be written. Everything else is read-only to me.

## Non-goals

- **Editing `src/quant_system/modeling/**`.** Claimed by `20260820-codex-slice4-ridge-training.md`
  and `20260821-1048Z-claude-slice4-redteam-repair.md`. Import only.
- **Editing `src/quant_system/execution/**` or `src/quant_system/server/**`.** Under live Red Team
  adjudication (`20260822-redteam-api-shadow-paper.md`, `20260822-redteam-money-paths.md`).
- Touching the uncommitted working-tree changes in `src/`, `tests/`, or the three modified
  `work/active/` records. They belong to other agents.
- `.launch/**` — claimed by `20260821-0530Z-claude-slice4-certification.md`.
- Declaring anything PASS, CERTIFIED, or COMPLETE. This record produces a runner and an
  observation, not an adjudication.
- **Substituting synthetic data for real market data.** No `SyntheticDataGenerator`, no generated
  bars, no fabricated authority hashes. If real data cannot be obtained, the typed failure is the
  deliverable.

## Plan

1. COMPLETE — AGENTS.md startup sequence: README, CURRENT, PROTOCOL, DISK-LAYOUT, `.launch/STATE.md`,
   `.launch/SLICES.md`, quarantine README, `git status`, `git worktree list`, `git branch --list`,
   and all 13 active records.
2. COMPLETE — read the modules to be chained (read-only) and confirm every constructor signature.
3. COMPLETE — create this record before editing.
4. COMPLETE — write `scripts/run_governed_ridge_training.py`.
5. COMPLETE — run it against the real provider; record the exact typed outcome verbatim.
6. COMPLETE — report. No PASS/CERTIFIED/COMPLETE marking.

## Current step

Stopped at stage 1 of 7. Runner written and statically verified; real acquisition attempted and
refused with a non-retryable typed failure, recorded verbatim below. Stages 2-7 have never executed.

This record was moved to `work/completed/` on founder instruction. The move records that this
task's scope is delivered — it does **not** record that the governed stack runs on real data, which
remains undemonstrated. Per AGENTS.md ("create a handoff when work remains") the outstanding work is
carried by `agent_context/handoffs/20260822-claude-real-data-training-runner-handoff.md`. Read that
handoff before citing anything here.

## Decision rationale

**Why a new file under `scripts/`.** Every module that would naturally host this is claimed by
another active record. `scripts/` has no active claim and the repo already carries runners there
(`daily_pipeline.py`, `build_dist.py`). A new uniquely-named file collides with nobody.

**Two-phase acquisition.** `build_feature_dataset` requires a governed manifest carrying a calendar
reference, `expected_sessions`, a corporate-action authority, and a universe authority. But
`expected_sessions` must list the real NSE trading dates in the range, which are not knowable before
the provider answers. The runner therefore issues a **discovery** request first (no
`expected_sessions`), derives the session calendar from the exchange dates the provider actually
returned, then issues the **governed** request whose `expected_sessions` are those real dates. Both
phases hit the real provider; neither invents a bar.

**The calendar is derived from provider data, and the runner says so.** NSE cash-equity session
hours (09:15-15:30 IST) are a published exchange fact, not generated data, and the session *dates*
come from the provider response. This is still weaker than an independent NSE calendar authority:
a provider that silently omits a trading day would produce a calendar that agrees with its own gap,
so `SourceStatus.COMPLETE` cannot be self-proving. The runner stamps the calendar id
`nse-cash-provider-derived` so no reader can mistake it for an independent authority, and
`--calendar-file` accepts a real independent calendar when one exists. Recorded as a known
limitation, not resolved.

**Corporate-action authority is required, never fabricated.** `AuthorityReference.content_hash`
must be a real 64-hex digest. The test fixtures use a repeated-character placeholder. The runner
refuses that: it takes `--corporate-actions-file` and hashes the actual bytes of the
operator-supplied document. With no file, it exits with a typed configuration refusal rather than
emitting a governed dataset bound to an authority that does not exist.

**Costs come from the real dated rule engine.** `RoundTripCostQuoteV1` needs component costs. Rather
than the fixtures' flat tenth-of-a-rupee constant, the runner calls
`NSERuleEngine.calculate_costs(EQUITY_DELIVERY, ...)` per leg at each leg's real trade date, so STT,
exchange turnover, SEBI, stamp duty, GST and brokerage are the statutory dated values. The
`cost_rule_set_hash` is `canonical_sha256` over the rule ids and hashes the engine actually applied.

**Rejected alternatives.** (a) Importing `tests/modeling_fixtures.py` — those are synthetic by
construction and the task forbids it. (b) Defaulting `--corporate-actions-file` to a placeholder
hash — that is the fabrication the quarantined report was withdrawn for. (c) Writing the runner
inside `modeling/` next to the code it calls — correct on cohesion, forbidden by ownership.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`, `git worktree list`, `git branch --list` | RUN | 1 worktree (install root), 1 branch (`main`), HEAD `c5f7874`; 16 modified + 2 untracked paths, all left untouched |
| `ls -la .env*` | RUN | Only `.env.example`. No `.env`. |
| `python -c` env probe | RUN | `UPSTOX_ACCESS_TOKEN set: False`. No token in the environment either. |
| `uv run python scripts/run_governed_ridge_training.py --symbol INFY --instrument-key "NSE_EQ\|INE009A01021" --from-date 2024-01-01 --to-date 2025-12-31 --evidence-root tmp/real-training-evidence` | **FAILED at ACQUISITION (stage 1 of 7)** | Exit code 3. Typed failure `PROVIDER_UNAUTHORIZED`, `retryable=False`, recovery `Configure a valid UPSTOX_ACCESS_TOKEN and retry.` Verbatim output in Stop point. |
| `uv run ruff check scripts/run_governed_ridge_training.py` | PASS | `All checks passed!` |
| `uv run ruff format --check scripts/run_governed_ridge_training.py` | PASS | `1 file already formatted` (after one `ruff format` pass) |
| `MYPYPATH=src uv run mypy scripts/run_governed_ridge_training.py` | PASS | `Success: no issues found in 1 source file` under `strict = true`. `MYPYPATH=src` is required: without it mypy resolves `quant_system` from site-packages, which ships no `py.typed`, and reports 10 spurious `import-untyped` errors plus one derived `no-any-return`. The repo gate runs `mypy src`, which does not cover `scripts/`. |
| `powershell -File scripts/audit-agent-claims.ps1` | PASS | Exit 0. `every workspace has a visible claim and every claim resolves`; this record is listed. |
| `powershell -File scripts/audit-disk-layout.ps1` | PASS | Exit 0. `no stray QuantOS directories`. |
| Full test suite / other gates | NOT RUN | Out of scope for this record, and would measure other agents' uncommitted working-tree changes rather than mine. |

## Files changed

- `scripts/run_governed_ridge_training.py`: new. The end-to-end real-data governed training runner.
  No existing file was modified.

## Blockers and conflicts

**BLOCKED on real market data, by environment, not by code.** There is no `.env` and no
`UPSTOX_ACCESS_TOKEN`. The provider returns a non-retryable `PROVIDER_UNAUTHORIZED` before any bar
is fetched, so stages 2-7 of the chain have never executed against real data and are **unproven**.

The hard prohibition was honoured: no synthetic fallback was substituted, and no training result is
reported. The runner has no synthetic code path to fall back to — it imports no generator.

Two things remain unproven and must not be read as working:

1. Everything after acquisition. Feature build, labelling, folding, and the persisted trial have
   only ever run on fixtures, never on real bars.
2. Whether a real multi-year Upstox response satisfies `build_feature_dataset`'s governed-input
   validation on the first attempt.

## Stop point

Runner complete at `scripts/run_governed_ridge_training.py`. Real acquisition attempted and refused.
Verbatim output:

```
[0/7] credential                      : UPSTOX_ACCESS_TOKEN is not set; the provider will be asked anyway
[1/7] real acquisition (discovery)    : NSE_EQ|INE009A01021 INFY 2024-01-01..2025-12-31

ACQUISITION FAILED - no synthetic fallback exists in this runner.
  stage                 : discovery
  code                  : PROVIDER_UNAUTHORIZED
  retryable             : False
  retry_after_seconds   : None
  provider_status       : None
  provider_code         : None
  recovery_action       : Configure a valid UPSTOX_ACCESS_TOKEN and retry.
  detected_at           : 2026-08-22T13:00:41.370594+00:00

STOPPING. No feature dataset, no labels, no fold, no trial, no evidence was written.
EXIT CODE: 3
```

**Precision about where that failure came from.** `provider_status` and `provider_code` are both
`None` because no HTTP request was ever issued. `UpstoxClient.acquire_historical_daily`
(`src/quant_system/data/upstox.py:118-125`) checks `is_authenticated` first and returns the typed
`PROVIDER_UNAUTHORIZED` failure locally. Nothing reached `api.upstox.com`. The failure is the
codebase's own fail-closed contract working correctly; it is not a response from Upstox, and this
record does not claim the provider was contacted.

`tmp/real-training-evidence` does not exist — the runner never reached the stage that creates it.

Working tree: the two files listed under Files changed are untracked additions. Nothing is staged,
nothing is committed. The 16 modified paths belonging to other agents are byte-identical to how I
found them.

## Next safe action

Provide a real `UPSTOX_ACCESS_TOKEN` (V3 bearer, market-data scope) and a real corporate-actions
document, then re-run the exact command in the table above with `--corporate-actions-file`. The
first genuine unknown is whether a real multi-year response passes governed-input validation
unmodified; expect `INSUFFICIENT_HISTORY`, `CALENDAR_AUTHORITY_MISMATCH`, or a quality rejection to
surface real defects that fixtures cannot. Do not treat stages 2-7 as working until that run
produces evidence.
