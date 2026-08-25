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

## 4. What an adjudicator must still establish

These are the open questions; none is answered by the above.

1. **Reproducibility.** Do the campaign drivers produce the same model hashes from the same cache?
   Nothing here re-ran them.
2. **Is the re-deflation real?** `0.217695` appears in a record. Locate the computation, or
   recompute it from the store, and confirm the final count used was 50.
3. **Cache provenance.** The ten-year cache underlies every v2 result. Is it point-in-time honest,
   and does it match the acquisition manifests?
4. **Search accounting.** CURRENT.md records six pre-declared screens run *outside* the governed
   store. Is total multiplicity across governed and ungoverned search correctly accounted, or is
   the deflation understated by the screens that never spent an ordinal?
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
