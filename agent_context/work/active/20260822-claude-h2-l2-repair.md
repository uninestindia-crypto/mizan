# Repair H-2 (holdout single-use), L-2 (silent mark-to-cost), X-1 (Slice 5 unreachable)

TASK_ID: 20260822-claude-h2-l2-repair
AGENT: Claude Code (Opus 5)
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-22
STARTING_REVISION: b9377f1618b31d5c0ae558c81379c19d3d3e20df (main, install root)
WORKTREE_OR_BRANCH: D:\quant_system on main (shared checkout)

## Objective

Founder-directed repair of two Blockers from
`agent_context/work/active/20260822-redteam-money-paths.md`:

- **H-2** — holdout single-use is defeated by constructing a second `HoldoutVaultTracker()`;
  state is in-memory only, never persisted, never read back.
- **L-2** — `get_portfolio_snapshot` silently marks a position to its own average price when the
  symbol is missing from the price map.

## Non-goals

- Not repairing H-1, P-1, P-2, S-1, R-1..R-4, G-1..G-6, N-1, N-2, L-1.
  (X-1 was added to scope by the founder after H-2/L-2 landed; it is now repaired.)
- Not adding a new `EvidenceResourceType`. The consumption record reuses `BUNDLE` with its own
  `schema_id`, so `src/quant_system/evidence/models.py` is not modified.

## Ownership — explicit adoption, recorded before editing

| Path | Claim status | Basis for editing |
|---|---|---|
| `src/quant_system/core/ledger.py` | **unclaimed** | no active record names it |
| `tests/test_ledger_accounting.py` | **unclaimed** | no active record names it |
| `src/quant_system/modeling/holdout.py` | claimed by `20260821-1048Z-claude-slice4-redteam-repair` under glob `src/quant_system/modeling/*.py`, **STATUS: HANDOFF_REQUIRED** | **adopted** — see below |
| `tests/test_modeling_holdout.py`, `tests/test_modeling_promotion.py` | same record, glob `tests/test_modeling_*.py`, HANDOFF_REQUIRED | **adopted** |

**Adoption.** PROTOCOL section 5 states an active record stays in place "until another agent
explicitly adopts it". This record is that explicit adoption, limited to `modeling/holdout.py`,
`tests/test_modeling_holdout.py` and `tests/test_modeling_promotion.py`. The rest of that record's
claim — the other `modeling/*.py` files, `evidence/*.py`, the remaining test files — is **not**
adopted and remains its own. Its record is not edited.

**Adoption extended 2026-08-22 for X-1** (founder-directed, after H-2/L-2 landed) to:

- `src/quant_system/modeling/stress.py` — needs `draft_from_stress_report`, which does not exist
- `src/quant_system/modeling/promotion_pipeline.py` — **new file**, did not exist at any revision
- `tests/test_modeling_promotion_pipeline.py` — new file

Still not adopted, and still untouched: `trials.py`, `persisted_trials.py`, `preprocessing.py`,
`ridge.py`, `rows.py`, `partitions.py`, `evidence.py`, `validation.py`, `metrics.py`,
`training_evidence.py`, `errors.py`, `__init__.py`, `features.py`, `labels.py`, `folds.py`,
`authorities.py`, and all of `evidence/*.py`. `promotion.py` is **read** for its existing
`draft_from_promotion_record` but not modified.

**The other modeling claim does not cover these files.**
`20260820-codex-slice4-ridge-training.md` is STATUS: ACTIVE and must be respected, but it names its
files explicitly: `trials.py`, `persisted_trials.py`, `preprocessing.py`, `ridge.py`, `rows.py`,
`partitions.py`, `evidence.py`, `validation.py`, `metrics.py`, `training_evidence.py`, `errors.py`,
`__init__.py`, `analytics/multiplicity.py`, `evidence/store.py`. **`holdout.py` is not among them**,
and none of those files is touched here. In particular `evidence/store.py` is used but not modified.

## The two defects, read at b9377f1

### H-2 — `holdout.py:292-317`

`HoldoutVaultTracker.__init__` builds three plain dicts. Nothing is written anywhere and nothing is
read back. Its own docstring says "In-memory or store-backed"; there is no store backing. A second
`HoldoutVaultTracker()` — or any process restart — resets the vault, so the final holdout can be
unlocked again. Single use is the entire purpose of a final holdout, and it is the property most
able to manufacture a false positive: unlimited re-use of the holdout turns it into a second
validation set.

### L-2 — `ledger.py:549`

    price = current_prices.get(sym, pos.average_price)

A missing price silently marks the position to its own cost, so `unrealized_pnl` for it is exactly
`0.00` and `total_market_value` is wrong, with no signal to the caller. The method's own docstring
promises an "exact mark-to-market portfolio snapshot".

## Repair design

**L-2** — fail closed. A mark-to-market that cannot be computed must not be fabricated: a missing
price raises rather than substituting cost. This is a behaviour change for any caller passing a
partial price map, which is the point.

**H-2** — the tracker takes a **required** `EvidenceStore`. Consumption is committed to the store
as a `BUNDLE` resource carrying its own `schema_id`, and the tracker rebuilds consumed state from
the store on construction, so a fresh tracker over the same store sees every prior use.

The store is required rather than optional deliberately: an optional store leaves the default
construction exactly as unsafe as it is today, which does not close the finding.

Rejected alternative: persist to a side-channel JSON file. Rejected because ADR-001 makes the
content-addressed evidence store the single durable record, and a second persistence path is the
same defect class as the second ridge model.

## Plan

1. Create this record. (done)
2. L-2: failing-first regression, then repair.
3. H-2: failing-first regression proving a second tracker refuses a consumed holdout, then repair.
4. Full suite, ruff, mypy, both audits.

## Commands and outcomes

| Command | Outcome |
|---|---|
| `git rev-parse HEAD` | `b9377f1618b31d5c0ae558c81379c19d3d3e20df` |
| `grep -rn "HoldoutVaultTracker(" src/ tests/ scripts/` | 5 construction sites, all in adopted test files |

## Blockers and conflicts

1. Three adjudications remain IN_PROGRESS. `modeling/**` is in the money-paths Red Team's scope, and
   this repair changes findings it is still writing up. A notice is required, as for the S9/S10 work.
2. Requiring a store on `HoldoutVaultTracker` is a public API change.

## Outcome — all three repaired

### L-2 (COMPLETE)

`ledger.py:549` now raises `LedgerInvariantViolation` naming the symbol and held quantity instead of
substituting `pos.average_price`. Failing-first evidence: `Failed: DID NOT RAISE
LedgerInvariantViolation`. A companion test pins that a snapshot which *can* be computed still is,
so the guard cannot over-fire.

No caller broke. Both real callers (`paper_pilot.get_portfolio_snapshot`,
`shadow_replay._build_audit`) pass a price cache populated as quotes arrive, and a position can only
exist after a fill, which only follows a quote.

### H-2 (COMPLETE)

`HoldoutVaultTracker` now takes a **required** `EvidenceStore`, rebuilds consumed state from it in
`_load_consumption_from_store()`, and commits each use through `_publish_consumption()` **before**
trusting it in memory — so a failed commit leaves nothing marked consumed.

Failing-first evidence, two regressions:

    TypeError: HoldoutVaultTracker.__init__() takes 1 positional argument but 2 were given
    Failed: DID NOT RAISE TypeError

The first proves the store-backed constructor did not exist; the second pins that the store is
mandatory, since an optional store would leave default construction exactly as unsafe as the
finding describes.

A malformed consumption record raises rather than being skipped: a vault that cannot read its own
history must not report "unconsumed".

Five call sites updated, all inside adopted test files.

## Gate

| Gate | Result |
|---|---|
| `pytest tests/ -q` | **735 passed**, 1 warning (after the runner; suite grew from other agents' concurrent work) |
| `pytest` holdout + promotion + ledger | 22 passed |
| `ruff check .` | All checks passed! (2 import-order errors in my own files, fixed by path) |
| `ruff format --check .` | 321 files already formatted |
| `mypy src launcher.py scripts` | Success: no issues found in 125 source files |
| `scripts/audit-agent-claims.ps1` | see below |
| `scripts/audit-disk-layout.ps1` | see below |

The 631 figure is **not** attributable to this task alone — the suite grew substantially from other
agents' concurrent work during this session. It is a working signal, not a certification baseline.

## What is NOT fixed

Only H-2 and L-2 were in scope. Untouched from the money-paths record: L-1, H-1, P-1, P-2, S-1,
R-1..R-4, G-1..G-6, N-1, N-2, X-1 — several of which were separately addressed by the antigravity
repair round, which is a different agent's work.

X-1 remains true and is worth restating: Slice 5 still has **zero callers in `src/`**. This repair
makes the holdout vault correct; it does not make it reachable from the product.

Neither repair is certified. No Red Team recheck and no clean-clone Verifier has run against them.

### X-1 (COMPLETE)

Founder-directed after H-2/L-2. Not a defect in a function — an entire slice with no caller.
`evaluate_governed_holdout`, `run_mandatory_stress_suite` and `evaluate_promotion` had no caller in
`src/` outside their own defining modules, so no holdout, stress or promotion evidence was ever
published.

Three things were missing, not one:

1. **No publisher for stress at all.** `draft_from_holdout_*` and `draft_from_promotion_record`
   existed; there was no `draft_from_stress_report`. Added to `stress.py`.
2. **No way for a caller to reach the holdout start record.** It is built inside
   `evaluate_governed_holdout` and never returned. Added `HoldoutVaultTracker.get_evaluation_start`,
   which reads the dict the tracker already maintained.
3. **No pipeline.** Added `src/quant_system/modeling/promotion_pipeline.py` with
   `run_persisted_promotion`, chaining holdout -> stress -> promotion and committing every artefact.

The pipeline decides nothing itself: the verdict is whatever `evaluate_promotion` returns, and a
failing gate publishes as faithfully as a passing one. The holdout start record is committed only
*after* the unlock succeeds, so evidence never claims an unlock that did not happen.

Verification of the finding's own grep, run after the change:

    grep -rn "evaluate_promotion\|evaluate_governed_holdout\|run_mandatory_stress_suite" src/
      | grep -v <defining modules>
    -> 6 real call sites in promotion_pipeline.py

Five evidence kinds are now published by one call, confirmed by reading them back out of the store:
`holdout_evaluation_start`, `holdout_strategy_decision`, `holdout_evaluation_outcome`,
`stress_report`, `promotion_record` — plus `holdout_consumption` from the H-2 vault.

Two things found while building it, both recorded rather than smoothed over:

- `_HOLDOUT_REPORT_SCHEMA = "quantos.holdout_report"` in `holdout.py` **names nothing that is ever
  published**. `draft_from_holdout_report` emits its records under
  `"quantos.holdout_strategy_decision"`. The constant is dead. Not repaired — `holdout.py` is
  adopted but the constant is referenced by no caller and removing it is a separate cleanup.
- A whole stress report as one canonical record breaches the store's per-record chunk limit, so
  `draft_from_stress_report` emits one record per scenario, mirroring `draft_from_holdout_report`.

**What X-1 does NOT become.** The pipeline is reachable from `src/`, but nothing in the *product*
calls it: no API endpoint, no script, no UI. Closing the finding as written ("zero callers in
src/", "no evidence ever published") is not the same as making promotion a thing a user can do. A
runner script mirroring `scripts/run_governed_ridge_training.py` is the obvious next step and was
not built here.

### X-1 product surface — `scripts/run_governed_promotion.py` (COMPLETE)

Founder-directed after the pipeline landed. X-1 was closed as written (a caller in `src/`), but
nothing an operator could run. This script is that surface, the promotion analogue of
`scripts/run_governed_ridge_training.py`.

    train window  -> features -> labels -> purged fold -> run_persisted_ridge_trial
    full  window  -> features -> labels -> create_holdout_partition -> run_persisted_promotion

**Two acquisitions, deliberately.** `--train-to-date` ends the fit; `--holdout-from-date` opens the
holdout. A single acquisition would force the training fold and the holdout to be carved from the
same tail, because `_fold_from_tail` always takes the tail — that is look-ahead leakage of exactly
the kind this stack exists to prevent.

A discovery-only `LabelDatasetV1` was considered and rejected: `dataset_hash` is a field that
identity checks verify, not a derived value, so hand-rolling a reduced dataset would mean
fabricating an identity. Two disjoint windows are honest instead of clever.

`_refuse_leaky_windows` fails closed on: `--train-to-date` at or after `--holdout-from-date`;
a holdout after `--to-date`; and fewer than `--min-holdout-gap-days` (default 7) between the
windows, so a label opened on the last training session has matured before the holdout opens.
Seven regressions cover these, plus session resolution.

Every computation — acquisition, calendar, corporate-action and universe authorities, dated NSE
cost quotes, fold construction — is imported from `run_governed_ridge_training`, not reimplemented.
A second cost or calendar path is the defect class this repository keeps hitting.

Owned path added: `scripts/run_governed_promotion.py` (new file, unclaimed),
`tests/test_governed_promotion_runner.py` (new file, outside every existing claim).
`scripts/run_governed_ridge_training.py` is **imported, never modified** — it is claimed by
`20260822-claude-dotenv-loading`.

**Not run against the provider.** The guards are tested; the acquisition stages need real
credentials and were not exercised here. The script has no synthetic path, so it cannot silently
substitute one — but "it runs end to end on real data" is NOT claimed.

## Shared-checkout flakiness found while verifying (not repaired)

A full-suite run failed once in `tests/test_daily_pipeline.py` with
`FileNotFoundError` writing into its own `tmp_path`, then passed on re-run. Controlled A/B:
728 passed without my new test file, 735 with it — the failure was **flaky, not caused by this
work**.

Likely mechanism: `pyproject.toml` pins `addopts = "-ra -v --basetemp=tmp/pytest"`, a **fixed,
shared** base temp directory. Concurrent agents running pytest in the same install root share it,
and one session's cleanup removes another's numbered directories mid-run. This plausibly also
explains the `tests/test_config_env.py` setup error seen earlier in this session, which likewise
passed in isolation.

Not repaired: `pyproject.toml` is a PROTOCOL section 4 shared file requiring single-owner
coordination. Recorded for the coordinator. Any gate figure measured in the install root while
other agents are active should be treated as provisional for this reason.

## Notice filed

`agent_context/work/active/20260822-NOTICE-h2-l2-repair-affects-money-paths-redteam.md`, naming the
adoption boundary, the public API change, and the moved test counts.

## Next safe action

Await the three adjudication reports. Do not commit ahead of them without founder instruction.
