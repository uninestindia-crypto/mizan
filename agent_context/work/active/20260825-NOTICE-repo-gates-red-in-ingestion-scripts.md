# NOTICE — three repository gates are red in the data-ingestion scripts

TASK_ID: 20260825-NOTICE-repo-gates-red-in-ingestion-scripts
AGENT: Claude Code (Opus 5), owner of `20260825-claude-program-majors`
STATUS: NOTICE (additive; no other record is edited; none of these files touched)
DATE_UTC: 2026-08-25

Filed under PROTOCOL 8.4, addressed to whoever owns the market-data ingestion and analysis scripts.

## What is red, measured at `0316410e`

```
ruff check .              FAIL
ruff format --check .     FAIL
mypy src launcher.py scripts   FAIL   7 errors
```

Attributed file by file, not assumed:

| file | ruff lint | format | mypy |
|---|---:|---:|---:|
| `scripts/ingest_nse_delivery_data.py` | 18 | ✓ | |
| `scripts/ingest_all_market_data.py` | 16 | ✗ | |
| `scripts/build_multidim_feature_store.py` | 15 | ✗ | |
| `scripts/analyze_market_universe.py` | 8 | ✗ | **7** |
| `scripts/ingest_intraday_candles.py` | 6 | ✗ | |
| `scripts/analyze_multidim_dataset.py` | 3 | ✗ | |

Also `agent_context/work/active/20260825-NOTICE-loop-in-test-comprehension-false-positive.md` fails
`ruff format --check` (ruff formats fenced code blocks in markdown).

## The mypy errors look like one root cause

All seven are in `analyze_market_universe.py`, and six of them read like a single mis-annotation
propagating:

```
:208 Incompatible types in assignment (expression has type "PointInTimeBar",
                                       variable has type "dict[str | Any, str | Any]")
:209 "dict[str | Any, str | Any]" has no attribute "close"
:210 … no attribute "open"     :211 … no attribute "high"     :213 … no attribute "volume"
:303 Need type annotation for "tier_adtvs"
```

A variable inferred as `dict` is being assigned a `PointInTimeBar`, so every attribute access after
it fails. Annotating the variable as `PointInTimeBar` will likely clear six at once. This is the
same shape as three `object` annotations I repaired in the cached-campaign scripts: one loose type
silences or breaks the checker on everything downstream.

## Why I did not fix them

They are yours, they are live, and PROTOCOL 4 puts a repository-wide formatter run under
single-owner coordination while other agents are active. Reformatting or retyping six of someone's
scripts mid-flight is the highest-risk, lowest-value action available to me.

## Something that may help

`scripts/run-gates.ps1` (added at `0316410e`) runs the full gate set locally — the same commands as
`ci/gates-workflow.yml`, one summary table, exit 1 on any failure:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-gates.ps1 -SkipSlow
```

`-SkipSlow` drops the reverse-order suite for a fast loop; do not cite such a run as a gate result.

## Not an accusation

The tests pass — **929 normal, 929 reverse**. This is lint, format and typing on newly landed
scripts, which is exactly what one expects from work in progress. It is filed because `main` is
currently not gate-green, and anyone citing a green gate from this tree would be wrong.
