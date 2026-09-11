# Active work: independent adjudication — training path, governed retrain, short-horizon program

STATUS: COMPLETED (item 1 of 4; scope adjudicated, gaps named)
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-09-11T08:10:00Z
STARTING_REVISION: `e9041b7b`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; read-only adjudication)
AUTHORIZATION: founder instruction, 2026-09-11 — "all one by one", against the four-item priority
list this session proposed, of which adjudication was item 1.

## Independence declaration — read this before any verdict below

Adjudication is worthless if the adjudicator reviews their own work, so the boundary is drawn first
and explicitly.

**I am independent of, and may adjudicate:**

| Scope | Author |
|---|---|
| `scripts/run_governed_ridge_training.py`, `run_universe_ridge_campaign.py`, `run_cached_nifty50_ridge_campaign.py` | earlier sessions |
| `modeling/promotion_pipeline.py`, `scripts/run_governed_promotion.py`, `holdout.py`, `stress.py`, `ledger.py` | the brief's author — **this is the brief's own open Q5** |
| Governed Mizan retrain `trial_mizan_h11_003` and its DSR 0.2466 claim | `20260910-1615Z-…-short-horizon-program` |
| Short-horizon experiment, 6 trials, QuantOS vs TimesFM | same |

**I am NOT independent of, and must NOT adjudicate:**

| Scope | Why |
|---|---|
| `src/quant_system/data/corporate_actions.py` | I wrote its first version |
| `reports/mizan_ab_screen/**` — the RAW vs adjusted A/B | I ran both arms |
| `scripts/ingest_all_market_data.py` authority cadence repair | I wrote it |
| The CI format/mypy repair | I made it |

Anything in the second table stays **unadjudicated** and must be reviewed by someone else. Recording
that is part of the job; quietly reviewing my own work would void every verdict in the first table
by association.

## Objective

Close as much of `.launch/ADJUDICATION-BRIEF-TRAINING-PATH.md` as an independent reader can, and
adjudicate the two newest unreviewed claims — the governed retrain and the short-horizon result —
which item H of the short-horizon record marks `PARTIAL — no independent adjudication`.

## Owned paths

- `agent_context/work/active/20260911-claude-adjudicate-training-and-retrain.md` (this file)
- `.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md` (new)

Everything else is **read-only**. No source, test, evidence store, record or configuration is
modified by this work.

## Non-goals

- No re-run that spends a multiplicity ordinal. `CURRENT.md` forbids reopening the campaign, and an
  adjudication that inflates the search it is auditing is self-defeating.
- No edit to another agent's record, including the ones whose claims are adjudicated here.
- No verdict on my own work — see the independence declaration.
- No promotion, no model execution, no change to either paper book.

## Method

Read the evidence stores directly with `EvidenceStore`, not the records. Where a record states a
number, recompute it from the store and report agreement or disagreement. Where recomputation is
impossible without spending an ordinal, say so rather than inferring.

## Current step

DONE. Report: `.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md`.

## Outcome

| Claim | Verdict |
|---|---|
| `h11_003` DSR 0.2466, ordinal 3, RESEARCH_ONLY | **PROVEN** |
| Nothing promotable in `mizan-v1` | **PROVEN** — best 0.246622 vs 0.95 gate |
| `mizan-v1` store integrity | **PROVEN** — 9 valid, 0 invalid, 0 orphans |
| Retrain ran "on consistent features/labels/P&L" | **NOT TESTED** |
| Short-horizon: 6 trials, ledger honoured, all fail gate | **PROVEN** |
| Neither ridge nor TimesFM has an edge | **PROVEN**, and both lose to the noise control |

Nothing was DISPROVEN.

### The material finding

The governed retrain's **inputs are not auditable**. Its TRIAL binds
`dset_b48a93253fabe3209621673b`, which exists nowhere under `data/`; the MODEL manifest carries no
adjustment field; and `feature_schema_version` is `1` on both the pre-adjustment trial
(`trial_mizan_001`) and the post-adjustment retrain. The dataset *hashes differ*, so the inputs
demonstrably changed and the hash stays tamper-evident — what is missing is any record of *how*.

Systemic, not Mizan-specific: no model store in the repository publishes DATASET resources
(mizan-v1 0, schema-v2 0, source-bound 0, source-bound-v2 0).

### Two things the evidence says more sharply than the records do

- **The retrained candidate is fourth of five strategies.** RIDGE sharpe `0.1672` against
  BUY_AND_HOLD `1.4037` and PREVIOUS_SIGN `1.6312`, with accuracy `0.4843` — *below* NO_TRADE's
  `0.4895` — while taking 3,080 positions.
- **The noise control beats both real models.** Hold 3: noise `0.419649`, TimesFM `0.191369`,
  ridge `0.094711`. Without that control, TimesFM's hold-3 number was the best real figure in the
  table and could have been misread as a faint signal.

### Provenance inversion

The ungoverned short-horizon artifacts bind `feature_store`, `corporate_action_authority_sha256`,
`code_revision`, `noise_seed` and `abstention_calibrated_on`. The **governed** evidence store binds
less than that. The research artifacts have better provenance than the governed ones.

## Commands and outcomes

| Command | Result |
|---|---|
| `EvidenceStore.scan_integrity()` on `mizan-v1` | 9 valid, 0 invalid, 0 orphans |
| `list_verified(MODEL)` | 3 models, ordinals 1/2/3, DSR 0.000903 / 0.175990 / 0.246622 |
| `list_verified(TRIAL)` | 6 records; 3 dataset bindings, **none resolvable** |
| recursive search for the 3 `dset_*` ids | NOT FOUND |
| `list_verified(DATASET)` across all 4 model stores | 0, 0, 0, 0 |
| read `results-{ridge,timesfm,noise-control}.json` | 9 trials, `gate_passed=False` on all |

No re-run. No ordinal spent. Nothing written outside the two owned paths.

## Stop point

A written adjudication with each claim marked PROVEN, DISPROVEN or NOT TESTED, and an explicit list
of what remains unadjudicated including my own work.
