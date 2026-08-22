# Handoff: prove the governed training stack on real market data

STATUS: READY_FOR_ADOPTION  
FROM: Claude Code — real-data training runner  
TO: unassigned (requires an operator who can supply Upstox credentials)  
DATE_UTC: 2026-08-22T19:40:00Z  
ACTIVE_RECORD: `agent_context/work/completed/20260822-claude-real-data-training-runner.md`

## Objective and acceptance criteria

The governed training stack had no production caller. It now has one. What remains is the proof that
it works on real data.

Complete when one governed ridge trial has run end to end on real Upstox bars and published trial
evidence to a real `EvidenceStore` — that is, when `scripts/run_governed_ridge_training.py` exits 0
and stages 2 through 7 have demonstrably executed at least once.

## Completed

- `scripts/run_governed_ridge_training.py` written and committed. It chains real Upstox acquisition
  -> `build_feature_dataset` -> `build_label_dataset` -> `build_purged_fold` ->
  `run_persisted_ridge_trial` -> `EvidenceStore`.
- Static verification: Ruff lint clean, Ruff format clean, strict Mypy clean with `MYPYPATH=src`.
- CLI surface verified via `--help`.
- Real-environment identity helpers verified against this machine: `_source_revision()` returns
  `c5f7874dd555e33cff1f998945a4893199baaeaa`, `_environment_lock_hash()` returns
  `9c40ebf470a8c7021b849f72acdb23347e49a63053ecbd59e3832337d3a27498` (which matches the
  `uv_lock_sha256` recorded in `.launch/STATE.md` open Major 3), `_architecture()` returns
  `windows-arm64-cpython-3.13.15`.
- Real statutory cost path verified end to end for a single leg: `NSERuleEngine.calculate_costs`
  for a BUY of 1 share at Decimal("1500.00") on 2025-06-02 returns `stt=1.50`,
  `exchange_turnover=0.04`, `sebi_charges=0.00`, `stamp_duty=0.23`, `gst=0.01`, `brokerage=0.00`,
  binding six dated rule ids including `STT-EQ-DEL-20041001` and `SD-EQ-DEL-20200701`.
- Real acquisition attempted. Refused, non-retryable. Verbatim output in the work record.

## In progress

Nothing is partially edited. The runner is whole; it has simply never been past stage 1.

## Files and ownership

- `scripts/run_governed_ridge_training.py`: committed. Owned by this handoff's successor.
- `agent_context/work/completed/20260822-claude-real-data-training-runner.md`: committed.
- `agent_context/handoffs/20260822-claude-real-data-training-runner-handoff.md`: committed.

No other path was touched. The 17 modified and 5 untracked paths belonging to other agents at the
time of writing were left byte-identical.

## Verification

| Command | Result | Notes |
|---|---|---|
| `uv run python scripts/run_governed_ridge_training.py --symbol INFY --instrument-key "NSE_EQ\|INE009A01021" --from-date 2024-01-01 --to-date 2025-12-31 --evidence-root tmp/real-training-evidence` | FAIL (exit 3) | `PROVIDER_UNAUTHORIZED`, `retryable=False`. Stage 1 of 7. |
| `uv run ruff check scripts/run_governed_ridge_training.py` | PASS | `All checks passed!` |
| `uv run ruff format --check scripts/run_governed_ridge_training.py` | PASS | `1 file already formatted` |
| `MYPYPATH=src uv run mypy scripts/run_governed_ridge_training.py` | PASS | `Success: no issues found in 1 source file`, strict |
| `powershell -File scripts/audit-agent-claims.ps1` | PASS | exit 0 |
| `powershell -File scripts/audit-disk-layout.ps1` | PASS | exit 0 |
| Stages 2-7 on real data | **NOT RUN** | Never executed. See Known failures. |

## Known failures and risks

1. **Stages 2-7 are unproven on real data.** Feature building, labelling, folding, and the persisted
   trial have only ever run on synthetic fixtures. The runner passing strict Mypy proves the types
   line up; it proves nothing about whether real Upstox bars satisfy the governed validators.
   Reproduce by supplying a token and running the command above. Severity: this is the entire
   remaining question.

2. **The failure observed was local, not remote.** `provider_status` and `provider_code` are both
   `None` because `UpstoxClient.acquire_historical_daily` (`src/quant_system/data/upstox.py:118`)
   checks `is_authenticated` before issuing any request. Nothing reached `api.upstox.com`. Do not
   cite this run as evidence that the provider was contacted or that the HTTP path works.

3. **The session calendar is provider-derived by default.** Without `--calendar-file`, the calendar
   is built from the exchange dates the provider returned, so a provider that silently omits a
   trading day produces a calendar that agrees with its own gap. `SourceStatus.COMPLETE` is
   therefore not self-proving on that path. The calendar id is stamped
   `nse-cash-provider-derived` so this cannot be mistaken for an independent authority.

4. **A corporate-actions document is required and does not exist in this repo.** The run will exit 2
   with `CONFIGURATION REFUSED` until `--corporate-actions-file` points at a real document. This is
   deliberate: `AuthorityReference.content_hash` must be a real digest, and the runner will not
   emit a placeholder.

5. **The default universe is a single instrument.** Without `--universe-file`, the universe snapshot
   contains only the requested instrument. It is content-bound and therefore honest, but it is a
   stated universe, not an independent point-in-time membership authority, and it does nothing to
   address survivorship bias across a multi-name universe.

## Exact stop point

`uv run python scripts/run_governed_ridge_training.py --symbol INFY --instrument-key
"NSE_EQ|INE009A01021" --from-date 2024-01-01 --to-date 2025-12-31 --evidence-root
tmp/real-training-evidence` returned exit 3 at stage 1 of 7 with `PROVIDER_UNAUTHORIZED`.
`tmp/real-training-evidence` was never created. No evidence was published.

## Next safe action

1. Set a real `UPSTOX_ACCESS_TOKEN` (V3 bearer, market-data scope) in the environment or a `.env`.
2. Obtain the real NSE corporate-actions document covering the requested range.
3. Re-run the stop-point command with `--corporate-actions-file <path>`.
4. Expect the first real run to fail somewhere in stages 3-6. `INSUFFICIENT_HISTORY`,
   `CALENDAR_AUTHORITY_MISMATCH`, `ELIGIBLE_OPEN_MISSING`, `COST_QUOTE_MISMATCH`, and a quality
   rejection are all plausible. Each would be a genuine finding that fixtures cannot surface.
   Record the typed code verbatim; do not work around it by relaxing a validator.

## Do not do

- Do not substitute synthetic or generated bars to get a green run. The runner imports no generator
  by design. Adding one would defeat its purpose.
- Do not supply a placeholder corporate-action or calendar hash to get past validation. A report
  was already quarantined in this repository for claims that could not be reproduced; see
  `.launch/reports/quarantine/README.md`.
- Do not report a training result, Sharpe figure, or model metric that did not come from real data.
- Do not edit `src/quant_system/modeling/**`, `src/quant_system/execution/**`, or
  `src/quant_system/server/**` to make the runner pass. Those are claimed by other active records
  and were under Red Team adjudication when this runner was written. Fix the runner, or record the
  defect for their owners.
- Do not treat this handoff, or the committed runner, as evidence that the governed stack works on
  real data. It is evidence that a caller now exists.
