# Adjudication brief — the training path and its research results

STATUS: OPEN — awaiting an independent adjudicator
PREPARED_BY: Claude Code (Opus 5), 2026-08-25
PREPARED_AT_REVISION: `38d8c81d`

## Why this brief exists

`agent_context/CURRENT.md` records: *"Neither Red Team nor an independent clean-clone Verifier has
adjudicated the training runner, the campaign driver, or any of these research results."* The
governed **execution** path has since been adjudicated; the **training** path has not. It is the
largest remaining evidence gap in the programme.

This brief does not close that gap. It makes it adjudicable: what to check, where the evidence is,
and which claims I was able to corroborate independently so an adjudicator can start from a
narrower surface.

**I am not independent of part of this scope.** I wrote `modeling/promotion_pipeline.py` and
`scripts/run_governed_promotion.py`, and I repaired `holdout.py`, `stress.py` and `ledger.py`. An
adjudicator must treat those as unverified regardless of anything below. I did **not** write the
training runner, the campaign drivers, or any of the research results, which is why the
corroboration in section 3 is worth something.

## 1. Scope to adjudicate

| Component | Path |
|---|---|
| Training runner | `scripts/run_governed_ridge_training.py` |
| Universe campaign driver | `scripts/run_universe_ridge_campaign.py` |
| Cached-universe campaign | `scripts/run_cached_nifty50_ridge_campaign.py`, `cached_nifty50_*.py` |
| Promotion pipeline **(mine — not independent)** | `src/quant_system/modeling/promotion_pipeline.py` |
| Promotion runner **(mine — not independent)** | `scripts/run_governed_promotion.py` |
| Research results | `agent_context/CURRENT.md` — INFY trials 1-3, NIFTY 50 v1 and v2 campaigns |

## 2. Evidence locations

Evidence stores are **local and gitignored** (`.gitignore:25` admits only `*.log`). They cannot be
adjudicated from a clean clone — an adjudicator needs this machine or a copy of these directories,
and that limitation is itself worth recording.

```
data/evidence/models/nifty50-current-20160822-20260821-schema-v2
data/evidence/models/nifty50-current-20160822-20260821-schema-v2-source-bound
data/evidence/models/nifty50-current-20160822-20260821-schema-v2-source-bound-v2   <- the v2 campaign
data/evidence/market-cache/…                                                        <- ten-year cache
```

## 3. What I corroborated independently, and how

Read directly from the v2 store via `EvidenceStore.list_verified(MODEL)`, not from any record:

| Claim in CURRENT.md | Independent reading | Verdict |
|---|---|---|
| 50 published models | **50** MODEL resources | corroborated |
| every model schema v2 | `('quantos.ridge_technical_six', 2)` on all | corroborated |
| verdict RESEARCH_ONLY | **50 of 50** | corroborated |
| nothing promotable | **0 of 50** reach the 0.95 gate | corroborated |
| best campaign DSR `0.217695` | store's max **published** DSR is `0.584510` | **see below — not a contradiction** |

### The DSR figures measure different things

The store's maximum published DSR is `0.584510`, against CURRENT.md's `0.217695`. I initially read
that as a discrepancy. It is not, and the check that settles it is the multiplicity ordinal.

`multiplicity_count` across the 50 models is **1, 2, 3 … 50 — one model at each value**. Each model
was scored against the number of attempts spent *at the moment it ran*. The `0.584510` model carries
ordinal **1**: it was the first trial, deflated against a single attempt. `0.217695` is the
re-deflation against the campaign's final count of 50.

Both are correct measurements of different quantities, and CURRENT.md already documents this
mechanism for the v1 campaign (GRASIM published `0.696673`, re-deflated to `0.397794`). An
adjudicator should expect the gap and check that the re-deflation was done, **not** treat the
published figure as the headline.

**The conclusion survives the most generous reading available.** Even taking each model's
flattering published DSR at its own low ordinal, **zero of fifty** reach the `0.95` gate. Median
published DSR is `0.017352`.

## 3b. Questions 2 and 4, answered by computation

Two of the six open questions below were answerable without re-running anything. Both were computed
by reading the store and calling `OverfittingDiagnostics.deflated_sharpe_ratio` directly. Moments
are approximated as normal (`skew=0, kurt=3`) because the return series are not in the manifests, so
treat the values as accurate to about two decimals, not exact.

### Q2 — is the `0.217695` re-deflation real, or only a claim?

**Real, and it identifies the same model.** Method validated first: recomputing the best *published*
model at its own ordinal 1 gives `0.584056` against the stored `0.584510` — agreement to four
decimals, so the approach is sound.

Re-deflating that same model to 50 gives `0.019527`, nowhere near `0.217695`. The headline therefore
does **not** belong to the best-published model, which is the trap here: the best model *after*
re-deflation is a different one, because published rank depends on the ordinal a model happened to
draw.

Re-deflating all 50 against the final count gives a maximum of **`0.250826`**, on a model with
**sharpe 3.2207** — which matches CURRENT.md's stated v2 best (`+3.2207`) exactly. Same model,
same conclusion; the residual gap to `0.217695` is my normal-moments approximation.

### Q4 — is total multiplicity understated by the ungoverned screens?

**Yes, and it does not change the verdict.** The same best model, deflated against progressively
honest attempt counts:

| attempts | DSR | what is included |
|---:|---:|---|
| 50 | 0.250826 | v2 campaign only — what was actually used |
| 101 | 0.176943 | + the 51-trial v1 campaign |
| 104 | 0.174317 | + the 3 INFY trials |
| 110 | 0.169377 | + the 6 pre-declared ungoverned screens |

Using 50 rather than 110 overstates the best result by roughly 48%. But the `0.95` gate is cleared
at **none** of these counts, so "nothing promotable" is robust to a 2.2x increase in the attempt
count. The accounting should still be corrected — it flatters the candidate — but no conclusion
rests on it.

## 3c. Questions 1 and 3, answered as far as reading the evidence allows

### Q1 — integrity half: **answered**

`EvidenceStore.scan_integrity()` on the v2 store returns:

```
valid_resource_ids  = 150      invalid_resource_ids = ()      orphan_blob_hashes = ()
```

Those 150 are **50 models + 50 `trial_nifty50_10y_NNN` starts + 50 `_outcome` records**. Every
resource verifies against its content hashes; nothing is corrupt; no blob is orphaned. The trial
registry is therefore complete and its size independently corroborates the multiplicity count of 50.

**Not answered:** whether the drivers are *deterministic* — that needs a re-run, which would spend
fresh ordinals, and CURRENT.md forbids it. Integrity and determinism are different claims.

### Q3 — cache integrity: **answered**

The store root is nested one level deeper than the campaign directory
(`…/nifty50-current-20160822-20260821/store/`). Scanned there:

```
valid = 100     invalid = 0     orphans = 0     DATASET resources = 100
```

100 datasets across 50 instruments is exactly **two per instrument**, which matches the bookkeeping
artifact CURRENT.md already records ("the cache holds two DATASET resources per symbol and counting
both doubled n"). The cache is intact and internally consistent.

**Not answered:** point-in-time honesty against the provider. An intact store proves nothing was
altered after publication; it does not prove what was published was correctly point-in-time.

### A misreading worth pre-empting

There are three model stores — `schema-v2`, `schema-v2-source-bound`, `schema-v2-source-bound-v2` —
holding 50, 12 and 50 models. That looks like three campaigns and would push total multiplicity past
110. It is not. Comparing `model_id` sets: the 50 in `schema-v2` and the 50 in `-source-bound-v2`
**overlap completely**, the 12 are a subset of both, and the union across all three is **50 distinct
models**. They are progressive re-publications of one campaign. Total distinct governed trials in
these stores is 50, and the Q4 accounting stands.

## 4. What an adjudicator must still establish

Six were posed. **Two are fully answered in 3b, two partially in 3c.** Two remain untouched.

1. **Reproducibility — partially answered in 3c.** Store integrity is proven (150 resources, zero
   invalid, zero orphans). Driver *determinism* is not: it needs a re-run, which would spend fresh
   ordinals.
2. ~~**Is the re-deflation real?**~~ **Answered in 3b** — real, same model, sharpe 3.2207.
   An adjudicator should still confirm the exact value with the true return-series moments.
3. **Cache provenance — partially answered in 3c.** The cache store is intact (100 datasets, zero
   invalid). Point-in-time honesty against the provider is still unproven; an intact store shows
   nothing was altered after publication, not that publication was correct.
4. ~~**Search accounting.**~~ **Answered in 3b** — understated by roughly 48%, and the verdict is
   unchanged at every count up to 110. The accounting still needs correcting.
5. **My own contributions**, listed in the header, which no one has reviewed.
6. **Gitignored evidence.** Decide whether research evidence that cannot be adjudicated from a
   clean clone is acceptable, and if not, what should change.

## 5. Commands

```bash
# inventory a store
python -c "from quant_system.evidence import *; s=EvidenceStore(EvidenceStoreConfig(root=...));
           print(len(s.list_verified(EvidenceResourceType.MODEL)))"

# full gate set, as CI now runs it
uv run ruff check . && uv run ruff format --check .
uv run mypy src launcher.py scripts
uv run pytest tests/ -q
```

## 6. What must not be inferred from this brief

Nothing here is a PASS. Section 3 narrows the surface; it does not certify the training path. The
`RESEARCH_ONLY` verdict on all 50 models is the **model's own label**, not a certification, and
CURRENT.md's standing instruction holds: do not re-run these campaigns, because a repeat spends
fresh multiplicity ordinals for no new information.
