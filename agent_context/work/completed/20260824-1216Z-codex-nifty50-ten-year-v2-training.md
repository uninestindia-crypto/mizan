# Retired work: ten-year real-data NIFTY 50 schema-v2 training campaign

STATUS: RETIRED_RESEARCH_ONLY
OWNER: Codex — governed real-data training campaign
TOOL: Codex
STARTED_UTC: 2026-08-24T12:16:05Z
STARTING_REVISION: `3d003e724b9bcfd963d655377a05ff6ed11bd289`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; exact disjoint paths claimed below)

## Objective

Run the existing governed ridge campaign over ten calendar years of real Upstox daily history for
all 50 members in the current official NIFTY 50 constituent file. Use feature schema v2, a fresh
EvidenceStore, one uniform train-only threshold rule, final campaign multiplicity, real NSE
corporate-action documents, and no synthetic or generated market data.

## Owned paths

- `agent_context/work/active/20260824-1216Z-codex-nifty50-ten-year-v2-training.md` (initial visible claim, now retired)
- `agent_context/work/completed/20260824-1216Z-codex-nifty50-ten-year-v2-training.md` (this file)
- `agent_context/handoffs/20260824-nifty50-ten-year-v2-training.md` (new, only if work remains)
- `tmp/training-runs/nifty50-v2-10y-20260824/**`
- `tmp/real-training-evidence-v2-nifty50-20160822-20260821/**`
- `tmp/nse-corporate-actions-nifty50-20160822-20260821/**`
- `tmp/nse-authorities/nifty50-20260824/**`
- `scripts/run_cached_nifty50_ridge_campaign.py` (new)
- `scripts/cached_nifty50_evidence.py` (new cache codec and fail-closed reuse support)
- `scripts/cached_nifty50_costs.py` (new explicit research-cost adapter)
- `scripts/cached_nifty50_io.py` (new durable authority/summary I/O support)
- `scripts/cached_nifty50_catalog.py` (new one-scan verified acquisition catalog)
- `tests/test_cached_nifty50_campaign.py` (new)
- `agent_context/decisions/20260824-nifty50-ten-year-cache-and-cost-proxy.md` (new)
- `data/evidence/market-cache/nifty50-current-20160822-20260821/**` (runtime, persistent real-data cache)
- `data/evidence/models/nifty50-current-20160822-20260821-schema-v2/**` (runtime, persistent trial evidence)
- `data/evidence/models/nifty50-current-20160822-20260821-schema-v2-source-bound/**` (runtime, post-commit trial evidence)
- `data/evidence/models/nifty50-current-20160822-20260821-schema-v2-source-bound-v2/**` (runtime, optimized post-commit trial evidence)
- `data/evidence/training-runs/nifty50-current-20160822-20260821-schema-v2/**` (runtime logs and summaries)

Read-only inputs:

- `.env` (credential values must never be printed or persisted)
- `scripts/run_universe_ridge_campaign.py`
- `scripts/run_governed_ridge_training.py`
- `data/authorities/nse-nifty50-constituents.csv`
- `src/quant_system/data/**`, `src/quant_system/modeling/**`, and `src/quant_system/evidence/**`

## Non-goals

- No edit under `src/quant_system/**`, tracked authority, launch-state, CURRENT.md, server,
  execution, or modeling. A new isolated delivery runner and focused tests are in scope.
- No synthetic fallback, generated bar, placeholder authority, or reuse of pre-v2 evidence.
- No model promotion, final-holdout opening, shadow/paper/live session, or broker write.
- No claim that current-member studies form a historical point-in-time NIFTY 50 portfolio. This
  design is survivorship-biased and will be reported as 50 current-member single-stock studies.
- No tuning after observing results; threshold remains the predeclared training-partition base rate.
- No staging, editing, or cleanup of another agent's tracked or untracked paths.

## Frozen campaign contract

- Universe: 50 rows from the official NSE-linked constituent CSV, re-downloaded and compared before
  execution; current membership only.
- Date range: 2016-08-22 through 2026-08-21, ending on the latest fully closed NSE session before
  this run and staying within the ten-year request bound.
- Data: Upstox V3 real daily NSE equity history; exact typed provider failures remain results.
- Features: governed six-feature schema v2, canonical trailing 21 available bars.
- Labels: next eligible open to following open, net of the repository's effective-dated NSE cost
  engine; one share per decision.
- Validation: tail 63 sessions, two-session embargo, train-only preprocessing.
- Threshold: `auto`, each instrument's own training-partition base rate; uniform rule.
- Trial count: fresh store starting ordinal 1; every started attempt contributes to final campaign
  multiplicity.
- Verdict ceiling: `RESEARCH_ONLY`; no promotion action is authorized.

## Plan

1. DONE — verify official current constituent bytes, credential availability, date bounds,
   clean fresh output roots, and runner/schema identities.
2. DONE — the one-symbol canary acquired real history and built schema-v2 features, then stopped
   before labels because the dated cost catalog has no 2016 exchange, pre-2020 stamp-duty, or
   pre-GST indirect-tax rule.
3. DONE — implemented the user-authorized, explicitly identified research-cost proxy and immutable
   persistent acquisition cache; proved real miss/write and provider-free verified hit behavior.
4. DONE — reran all 50 from verified cache into a fresh source-bound store and reconciled every
   model, trial, ordinal, schema, result, source revision, and final-count deflation.
5. DONE — repository claim/layout audits exited 0; exact commands and raw paths recorded; this
   record retired; only owned tracked paths are staged for the final coordination commit.

## Current step

No work remains in scope. The durable market cache and source-bound research evidence are preserved
under the claimed ignored runtime roots; no provider extraction is needed for an identical rerun.

## Decision rationale

A fresh store is mandatory because schema-v2 feature arithmetic is incompatible with the 40
historical pre-v2 model artifacts. The ten-year endpoint is the latest fully closed session rather
than an in-progress trading day. A canary is run before 49 more provider acquisitions so an
authentication, range, authority, or schema refusal does not create avoidable traffic. Current
membership is used because it is the concrete 50-stock universe the user requested and the public
runner supports one static authority snapshot; the resulting survivorship limitation is explicit.
On 2026-08-24 the user chose to retain the full ten-year range and explicitly required all acquired
data to be saved so provider extraction is not repeated after a failure. The pre-catalog convention
is therefore frozen as a research-only proxy: exchange turnover `0.0000345` on both sides through
2017-03-31, indirect-tax component `0.18` of statutory charges through 2017-06-30, and stamp duty
`0.000150` on buys through 2020-06-30. Rule IDs and persisted cost hashes must identify every proxy;
none may be described as historically authoritative. Canonical provider bars and provenance will
be committed atomically to a dedicated EvidenceStore before feature or model work, then verified
and reused on rerun without credentials or raw HTTP payloads in the cache.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Required startup sequence | RUN | HEAD `3d003e7`; six unrelated untracked paths preserved; two live worktrees/branches discovered; all active claims inspected |
| Skill routing | RUN | quant-model-governance, point-in-time-market-data, financial-model-craft, and nse-execution-craft contracts loaded |
| Credential-name preflight | PRESENT | `.env` exists and names `UPSTOX_ACCESS_TOKEN`; value was neither printed nor persisted |
| Existing universe inspection | 50 ROWS | SHA-256 `9fb8832853c279448d2bc05f0e7dd5f460ed2ff35332fea8c40fc1250362ad28` |
| Official NSE page and CSV check | MATCH | downloaded 3,352 bytes / 50 rows; byte-identical and symbol-set-identical to tracked input; SHA-256 `9fb8832853c279448d2bc05f0e7dd5f460ed2ff35332fea8c40fc1250362ad28` |
| Fresh-root check | CLEAN | final evidence and corporate-action roots absent before the run |
| Credential-value preflight | PRESENT | `UPSTOX_ACCESS_TOKEN` loaded as non-empty; value never printed or persisted |
| First schema probe | COMMAND ERROR | imported constants from the wrong module; `ImportError`; no provider request or evidence write occurred |
| Second schema probe | COMMAND ERROR | token presence printed, then incorrect attribute lookup raised `AttributeError`; no provider request or evidence write occurred |
| Correct schema probe | V2 | `quantos.ridge_technical_six`, version 2, canonical window 21 bars |
| ADANIENT ten-year canary | STOPPED, exit 1 | Real acquisition and feature construction reached; labels stopped on `ValueError: No effective rule found for component=EXCHANGE_TURNOVER, segment=EQUITY_DELIVERY on trade_date=2016-09-22` |
| Canary side-effect inspection | BOUNDED | real 4,242-byte ADANIENT corporate-action document downloaded; canary EvidenceStore has no published files; final EvidenceStore absent |
| Equity-delivery cost coverage probe | GAP CONFIRMED | 2016 lacks exchange, stamp, and GST/service-tax equivalents; 2017-04 lacks stamp and GST/service-tax; 2017-07 through 2020-06 lacks stamp; all six components first coexist on 2020-07-01 |
| User continuation | AUTHORIZED | Retain at least ten years and persist acquired real data so reruns reuse verified local evidence instead of repeating Upstox extraction |
| Failing-first cache/proxy test | EXPECTED FAILURE | `uv run pytest -q tests/test_cached_nifty50_campaign.py -x` failed on the asserted missing durable runner before implementation |
| Focused cache/proxy tests | 5/5 | Verified exact EvidenceStore round-trip, cache-hit provider bypass, corruption refusal, full-universe subset authority, and proxy boundary behavior |
| Focused Ruff check | CLEAN | `uv run ruff check scripts/run_cached_nifty50_ridge_campaign.py tests/test_cached_nifty50_campaign.py` |
| Focused mypy invocation | TOOLING BOUNDARY | Failed on repository package/import configuration and pre-existing imported-runner `Any` errors; no runner-specific diagnostic was isolated by that invocation |
| Runner CLI smoke | EXIT 0 | `uv run python scripts/run_cached_nifty50_ridge_campaign.py --help` |
| Real cache-miss canary | EXIT 0 | ADANIENT: 2,476 real bars; discovery/governed/NSE corporate actions all `CACHE_MISS_SAVED`; schema-v2 model published in isolated canary store |
| Real cache-hit canary | EXIT 0 | Same ADANIENT metrics with `CACHE_HIT/CACHE_HIT` and corporate-action `CACHE_HIT`; no provider extraction |
| First 50-name campaign | EXIT 0, REHEARSAL ONLY | 50 `SUCCEEDED`; 21 positive Sharpes; median `-0.2278`; mean `-0.6834`; best/worst `+3.2207/-5.2615`; best final-count DSR `0.217695`; source revision still `3d003e7`, which does not include the uncommitted runner |
| Cache reconciliation | VERIFIED | 100 dataset resources: 50 discovery + 50 governed, exact two per symbol; 50 readable NSE corporate-action files; 19,652,184 cache bytes |
| Rehearsal model reconciliation | VERIFIED | 50 models + 50 trial starts + 50 `SUCCEEDED` outcomes; ordinals exactly 1..50; schema `quantos.ridge_technical_six` v2; 615,569 evidence bytes |
| Governed range reconciliation | 50/50 VERIFIED | Deterministic `REVERSE_ORDER` repair recorded for provider-descending responses; five later listings have real shorter histories: ETERNAL 1,261, HDFCLIFE 2,170, JIOFIN 746, MAXHEALTH 1,490, SBILIFE 2,201 bars |
| Relevant regression slice | 122/122 | Cache, dataset evidence, Upstox acquisition, features, labels, trials, replay, and campaign deflation |
| Code/Test Craft checkers | CLEAN | Modularized the original delivery script into four focused files; both repository structural checkers now report clean |
| Post-refactor cache-hit canary | EXIT 0 | ADANIENT again produced identical metrics from `CACHE_HIT/CACHE_HIT`; no market or authority re-download |
| First post-commit source-bound attempt | STOPPED BY OWNER | Reached 12 source-bound models with only cache hits, then was interrupted because the original lookup verified all 100 datasets twice per symbol; partial atomic evidence preserved and not used as final |
| Indexed catalog regression slice | 123/123 | Added one-scan verified acquisition catalog coverage; prior 122 relevant tests remain green |
| Indexed cache canary | EXIT 0 | One initial full-catalog verification followed by ADANIENT `CACHE_HIT/CACHE_HIT`; identical metrics; no provider call |
| Delivery source commits | COMMITTED | `54ff557` runner/cache/proxy/test; `5a7185a` one-scan verified catalog optimization |
| Final source-bound v2 campaign | EXIT 0 | 50/50 `SUCCEEDED`; every acquisition and corporate-action access was a verified cache hit; raw exit code 0 |
| Final artifact reconciliation | VERIFIED | 50 models, 50 starts, 50 outcomes, ordinals 1..50, 50 schema-v2 bindings, 50 `RESEARCH_ONLY` verdicts, and source revision `5a7185aadf528a856beb13532264a560b99f44bb` on every start |
| Final aggregate | RESEARCH RESULT | 21/50 positive Sharpes; median `-0.2278`; mean `-0.6834`; best/worst `+3.2207/-5.2615`; best final-count DSR `0.217695263874` against gate `0.95` |
| Final result replay | EXACT MATCH | All 50 per-symbol result rows matched the earlier rehearsal byte-for-value after excluding summary metadata/root fields |
| Mandatory claim audit | EXIT 0 | `scripts/audit-agent-claims.ps1` found every registered workspace visibly claimed and every workspace claim resolvable |
| Mandatory disk audit | EXIT 0 | `scripts/audit-disk-layout.ps1` found only canonical QuantOS roots and buckets |

## Exact final command and raw evidence

```powershell
uv run python scripts/run_cached_nifty50_ridge_campaign.py `
  --universe-csv tmp/nse-authorities/nifty50-20260824/ind_nifty50list-20260824.csv `
  --from-date 2016-08-22 `
  --to-date 2026-08-21 `
  --cache-root data/evidence/market-cache/nifty50-current-20160822-20260821 `
  --evidence-root data/evidence/models/nifty50-current-20160822-20260821-schema-v2-source-bound-v2 `
  --summary-file data/evidence/training-runs/nifty50-current-20160822-20260821-schema-v2/source-bound-v2-full-summary.json `
  --corporate-actions-dir data/evidence/market-cache/nifty50-current-20160822-20260821/corporate-actions `
  --start-ordinal 1 `
  --sleep-seconds 0
```

- Raw stdout: `data/evidence/training-runs/nifty50-current-20160822-20260821-schema-v2/source-bound-v2-full.stdout.log`
  - SHA-256 `1978b402e02b03c440f88b9b0a5f650fea8d65e3d11dfc34bba220ae6cb54fb9`
- Machine summary: `data/evidence/training-runs/nifty50-current-20160822-20260821-schema-v2/source-bound-v2-full-summary.json`
  - SHA-256 `6c877192627301250b5d74f998484232d60189384fd8d802eaef7b9318f957a0`
- Final EvidenceStore: `data/evidence/models/nifty50-current-20160822-20260821-schema-v2-source-bound-v2/`
  - 615,590 bytes; all 150 trial/model resources independently opened and verified.
- Durable market cache: `data/evidence/market-cache/nifty50-current-20160822-20260821/`
  - 19,652,184 bytes; 100 verified dataset resources plus 50 readable NSE corporate-action files.

## Files changed

- This retired work record.
- New `scripts/run_cached_nifty50_ridge_campaign.py`.
- New `scripts/cached_nifty50_evidence.py`.
- New `scripts/cached_nifty50_costs.py`.
- New `scripts/cached_nifty50_io.py`.
- New `scripts/cached_nifty50_catalog.py`.
- New `tests/test_cached_nifty50_campaign.py`.
- New `agent_context/decisions/20260824-nifty50-ten-year-cache-and-cost-proxy.md`.
- Claimed temporary official constituent download under `tmp/nse-authorities/nifty50-20260824/`.
- Raw canary output at `tmp/training-runs/nifty50-v2-10y-20260824/canary-adani-ent.stdout.log`.
- Real NSE ADANIENT corporate-action response under the claimed temporary corporate-action root.

## Limitations and conflicts

- Broad historical modeling claims remain active; all existing modeling, evidence, and runner
  source is read-only. Only the newly claimed delivery runner and focused test file may be edited.
- The current-member static universe is not a historical membership series. No portfolio or
  point-in-time constituent-performance claim may be made from this run.
- If real acquisition returns a typed failure, or official authority bytes mismatch, stop and
  report the exact result rather than substituting data or weakening validation.
- The ten-year canary exposed a real financial-authority boundary. Before 2020-07-01 the repository
  lacks complete equity-delivery cost coverage. The user chose the explicit research proxy above;
  outcomes remain `RESEARCH_ONLY` and cannot substantiate historical-cost or promotion claims.

## Stop point

The durable cache contains both real acquisition layers for all 50 symbols and all 50 NSE
corporate-action responses. The final source-bound v2 store contains 50 research models and exact
trial evidence at revision `5a7185a`. Earlier rehearsal/canary/partial stores remain preserved and
are not the reported final store. No promotion, final-holdout, shadow/paper/live, or broker action
was taken.

## Next safe action

Use the source-bound v2 EvidenceStore and machine summary for research review. Any future historical
index claim requires point-in-time constituent membership and authoritative pre-2020 cost inputs;
do not promote or deploy these static-current-member, research-proxy results.
