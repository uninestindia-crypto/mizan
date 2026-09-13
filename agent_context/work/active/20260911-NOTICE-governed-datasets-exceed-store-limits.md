# NOTICE: pooled governed datasets cannot be published — they exceed the evidence store's own limits

STATUS: NOTICE (additive; no other record is edited, and no claimed path was changed)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-11
FOR: `20260820-codex-slice4-ridge-training.md` (STATUS `ACTIVE`), which owns
  `src/quant_system/modeling/rows.py`, `modeling/evidence.py`, `modeling/training_evidence.py` and
  `src/quant_system/evidence/store.py`
RAISED_BY: `.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md`, which rated the governed
  retrain's "on consistent features/labels/P&L" claim **`NOT TESTED`** because the trial's
  `dataset_id` does not resolve

## Summary

The adjudication observed that **no evidence store in this repository publishes a single DATASET
resource**, so every trial's `dataset_id` / `dataset_hash` names a resource that does not exist. It
recommended publishing the dataset the trial binds to.

**That was attempted, and the store refuses it.** The cause is not a missing call in the runner. The
pooled governed datasets structurally exceed two of the evidence store's own limits, so the binding
cannot be made to resolve without a contract change.

## Measured, not inferred

```bash
.venv/Scripts/python.exe scripts/train_mizan.py --publish-datasets-only --horizon-sessions 11
```

That flag assembles the pooled datasets and attempts publication. It runs **no trial and spends no
multiplicity ordinal** — publishing data is not a trial. Result, on 43 instruments / 104,232 feature
rows / 103,699 label rows / 2,413 decision dates:

```text
dataset features : REFUSED -- EvidenceLimitExceeded: canonical evidence is 115934341 bytes;
                                                     limit is 104857600
dataset labels   : REFUSED -- EvidenceLimitExceeded: canonical metadata is 6948398 bytes;
                                                     limit is 1048576
```

| Refusal | Measured | Limit | Over by |
|---|---:|---:|---:|
| Feature dataset, canonical evidence | 115,934,341 B | 104,857,600 B (100 MiB) | **+10.6%** |
| Label dataset, canonical **metadata** | 6,948,398 B | 1,048,576 B (1 MiB) | **+563%** |

## The label-metadata refusal is the structural one

`pool_label_datasets` (`src/quant_system/modeling/pooled.py:288`) already deduplicates:

```python
quote_hashes = tuple(sorted({h for d in datasets for h in d.cost_quote_hashes}))
```

so the 6.9 MB is **not** duplication. Each label row carries its own dated `RoundTripCostQuoteV1` —
NSE statutory costs depend on price and date — so distinct quotes really are ~1 per row. At ~67 bytes
per hex hash entry, 103,699 rows produce ~6.9 MB.

**Therefore label-dataset metadata grows O(rows), against a fixed 1 MiB cap.** The governed store can
hold a pooled label dataset of roughly **15,000 rows at most**, whatever the data. Every pooled
research dataset this repository has built is far above that, which is a sufficient explanation for
why no DATASET resource has ever been published by anything.

This is not a defect in `train_mizan.py` and it is not an oversight by whoever wrote the runner. It
is a contract property that only becomes visible at real scale.

## Why this matters beyond tidiness

It is the mechanism behind an unverifiable governance claim. Because the dataset is unpublishable:

- a trial's `dataset_id` can never resolve, so a reader cannot confirm what a model was fitted on;
- the MODEL manifest carries no adjustment field, and `feature_schema_version` is identical either
  side of the corporate-action adjustment boundary, so neither can substitute;
- the adjustment provenance built at the `DatasetManifest` layer
  (`AdjustmentReference`, `data/adjustment_provenance.py`) is real but **unreachable** from published
  model evidence.

The integrity story is unaffected — the three mizan trials carry *distinct* `dataset_hash` values, so
the inputs genuinely differed and any re-run on different data stays detectable. **What is missing is
auditability, not integrity.**

## Suggested resolutions, for the owner to accept or reject

Offered as leads. All three touch claimed paths, so none was implemented:

1. **Replace the per-row hash list with a digest.** `cost_quote_hashes` could be one
   `cost_quote_set_hash` over the sorted distinct hashes. Metadata becomes O(1), the binding stays
   tamper-evident, and the per-row cost detail already lives on each `LabelRowV1`
   (`component_costs`, `cost_rule_ids`) so nothing is lost.
2. **Publish per-instrument datasets rather than the pooled artifact.** Each constituent is ~2,400
   rows and would publish comfortably; the pooled dataset could bind them by id.
3. **Raise the limits.** Least attractive — it treats a symptom, and an O(rows) metadata field will
   breach any fixed cap at some scale.

## What this filer did and did not change

- **Added** `--publish-datasets-only` to `scripts/train_mizan.py` (not a claimed path). It is the
  diagnostic that produced the measurement above, it spends no ordinal, and it will publish
  successfully once the contract permits it.
- **Changed nothing** under `src/quant_system/modeling/**` or `src/quant_system/evidence/**`.
- Static gate green after the change: `ruff check` clean, `ruff format --check` clean, `mypy src
  launcher.py scripts` clean across **208 source files**.
