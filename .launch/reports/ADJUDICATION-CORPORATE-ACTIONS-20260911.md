# Adjudication — the corporate-action correction

ADJUDICATOR: Claude Opus 5, third independent session, invoked 2026-09-11 on
`.launch/ADJUDICATION-BRIEF-CORPORATE-ACTIONS.md`.
REPOSITORY: `D:\quant_system`, branch `main`, HEAD `9aa3bd8e`.
SCOPE: exactly the brief's claim list, A1 through I2.
VERDICT: **BLOCKED**. Three defects, each reproduced below, two of them silent by construction.

## 1. Independence statement

I authored **none** of the files in scope: `corporate_actions.py`, `adjustment_provenance.py`,
`adjusted_acquisition.py`, `market_data.py`, `modeling/labels.py`, `validate_demerger_factors.py`,
`fetch_demerger_announcements.py`, `ingest_all_market_data.py`, their tests, or anything under
`reports/mizan_ab_screen/`. I have made no commit to this repository. The only files I have written
are this report and `agent_context/work/completed/20260911-2330Z-claude-adjudication-corporate-actions.md`.
Every in-scope source and test file is byte-identical to `HEAD` after my work: `git diff --stat` over
them is empty.

I accepted no claim on the strength of a work record, a narrative report, or
`agent_context/CURRENT.md`. Every measured claim was re-measured by me from the committed market
cache, the committed authorities, and code I wrote for this adjudication. Two artifacts under
`reports/` are read here as *objects of* the adjudication rather than as evidence for it:
`mizan_ab_screen/*.txt`, whose two arms I re-ran end to end, and
`corporate_action_validation/demerger-resulting-companies.json`, whose internal consistency and
quoted filing text I checked directly. Where I could not re-measure — the live NSE announcement
queries behind H1 — I say so and do not claim more.

Mutation testing was done in an **isolated copy** of `src/` and `tests/` under this session's
scratchpad, never in the install root. That is deliberate: this repository has an automated
`sync: evidence checkpoint` committer doing directory-wide `git add`, which has already swept other
sessions' uncommitted work into commits (`c897efce`). Mutating source in place would risk committing
a deliberate defect to `main`.

## 2. Verdict table

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| A1 | 212 of 212 published-ratio structural actions already show an ex-date gap of ~1.0 | **PROVEN** | §4.1. My own scan of the 423-name universe against the all-market cache: 212 scored, 212 `ALREADY_APPLIED`, largest `\|ln(gap)\|` 0.1035 (ASTRAL 2019-09-16). Count, verdict and extremum all reproduce. Independently corroborated by the production artifact `mizan-adjusted-v1`, whose `factors_applied: 4590` equals the dividend-only factor count — no structural factor was ever needed |
| A2 | Re-applying the ratio turns TATASTEEL into +945% and BEL into +952% | **PROVEN** | §4.2. TATASTEEL 2022-07-28 close-to-close +4.586% -> **+945.9%**; BEL 2017-03-16 +5.258% -> **+952.6%**. Reproduces to the digit on a close-to-close basis; the open-based figures are +922.4% / +915.8% |
| A3 | `status: RAW` describes provenance, not arithmetic | **PROVEN** | Follows from A1 plus `market_data.py:339-343`, where the literal is emitted unconditionally whenever `adjustment is None`. It is a fixed string, never a measurement of the bars |
| B1 | The old absolute-0.20 rule could not separate the hypotheses when `\|1-factor\| <= 0.40`, and broke ties toward "not applied" | **PROVEN** | Arithmetically necessary, and the corpus instance is B2. The old code is not in the tree, so the tie-break direction is verified from its corpus consequence rather than from the old source |
| B2 | The blind band covered 57 of 212 (27%), every one a bonus | **PROVEN** | §4.1. My scan: **57 of 212**, `Counter({('bonus',): 57})` — every one a bonus, no exceptions |
| B3 | The replacement scores both hypotheses in log space against `MAX_LOG_RESIDUAL = 0.15` | **PROVEN** | `corporate_actions.py:330-346`; mutations M01, M02, M03 all killed |
| B4 | The test is correct at the boundaries anywhere in the real corpus | **PROVEN (corpus-scoped), residual measured** | §4.3. Tightest real margin is 0.0453 in log space — ICICIBANK 2017-06-20, a 1:10 bonus — so that day would have had to fall a further **4.42%** to flip. Against each symbol's own overnight-gap distribution the largest single-action flip probability is 0.364%, and the expected number of misclassifications across all 212 is **0.03**. Residual: for 26 of 212 the hypotheses sit under 0.30 apart in log space, where the verdict is decided by the day's market move rather than by the tolerance |
| C1 | Gap inference was removed entirely, not tuned | **PROVEN** | No code path sizes an action from a gap. `FactorSource` has no `INFERRED`; `INFERRED_GAP_THRESHOLD` has zero users outside its definition and `__all__`; `FactorValidation.GAP_INFERRED_ONLY` has zero producers in `src/`, `scripts/` or `tests/` |
| C2 | It would have inferred upward corrections for NMDC +71.04%, BAJAJELEC +32.21%, SCI +30.00% | **PROVEN** | §4.1. Exactly three ratio-less actions have a gap above +20%: NMDC 2022-10-27 **+71.04%**, BAJAJELEC 2023-09-14 **+32.21%**, SCI 2023-03-31 **+30.00%** |
| C3 | `validate_demerger_factors.py` returns 0 validated / 56 refused | **PROVEN, and weaker than it sounds** | §4.4. Re-ran it with every output redirected to scratch: `validated 0, refused 56` (54 `NO_FILING_RATIO`, 2 `NO_EX_DATE_BAR`), 54 ratio-less actions with a bar. But the entitlement table holds **one** entry (HEG) and it was refused for want of an ex-date bar, so the value-continuity check that alone can emit a `VALIDATED` factor **has never executed on any input** and has no test |
| C4 | Windows spanning an unresolved action are dropped, not published with a fabricated return | **DISPROVEN** | §5 DEFECT-1. True for actions the module *records* unresolved (M06, M07, M23, M24, M30 all killed). False as a guarantee: rights issues are never parsed, never gap-tested and never recorded unresolved, so `spans_unresolved` returns `False` across them. Reproduced on four real symbols, one of them a **-22.94%** single-day return published as real |
| D1 | Every previously committed manifest hash is byte-for-byte unchanged | **PROVEN** | §4.5. I recomputed **8,714** committed dataset manifests across all six market-cache stores with today's `canonical_sha256`: 8,714 match their recorded identity, 0 mismatch, every one `schema_version 1` carrying the exact `PROVIDER_UNSPECIFIED`/`RAW` literal. Mutation M19 (altering that literal) is killed |
| D2 | A set adjustment forces `schema_version` 2, so derived data cannot declare itself RAW | **PROVEN** | `market_data.py:389-393`, plus `AdjustmentReference.__post_init__` refusing RAW-with-factors. M18 and M20 killed |
| D3 | `derive_adjusted_acquisition()` yields a separate artifact; the original is preserved | **PROVEN, one guard untested** | `adjusted_acquisition.py:110-165`; M28 (content hash left describing the raw records) killed. But **M27 — deleting the check that the reference binds the supplied acquisition — survives the whole suite** |
| D4 | The reference binds method, authorities, timestamps, hashes and code revision | **PROVEN, with a caveat** | `adjustment_provenance.py:230-255` binds all of them. The sole production caller, `scripts/train_mizan.py:145`, passes `authority_publication_date=None`, and nothing anywhere compares that field to anything |
| E1 | Return measured on adjusted bars, `entry_notional` from the raw fill price | **PROVEN** | `labels.py:358-367`. I re-derived the arithmetic by hand for a 1:1 bonus: raw ratio -0.5, economic return 0, cost fraction 1/100. M21 and M22 both killed |
| E2 | No double-counting of a cash or share entitlement | **PROVEN** | The gross return and the cost fraction are fractions of the same raw economic position. M21 (notional priced on the adjusted bar) killed |
| E3 | Refused quotes are tracked separately rather than silently dropped | **PROVEN in code, untested** | `labels.py:96-112` does it. **M26 — counting a refused quote as used — survives the whole suite** |
| E4 | No future-dated corporate action can influence a past decision | **PROVEN for feature values; not enforced** | §4.6. All six v1 features are exactly invariant under the uniform rescaling a future back-adjustment produces — measured, identical to the last digit — and a factor dated after the exit cancels in the label ratio. Not enforced: nothing compares an authority publication date to a decision time |
| F1 | Arm A reproduces the published `-0.000022, t = -0.07` | **PROVEN** | §6. I re-ran `screen_mizan_out_of_sample.py --no-adjust` on the committed raw feature store and got `mean=-0.000022 t= -0.07 sharpe= -0.01`, n=2413, identical to `reports/mizan_ab_screen/arm-a-raw.txt` line for line |
| F2 | Arm B gives `-0.000185, t = -0.66` | **PROVEN** | §6. Re-ran against the committed adjusted store `data/evidence/feature-store/mizan-adjusted-v1/`: `mean=-0.000185 t= -0.66 sharpe= -0.07`, 899,840 test rows, 532 windows refused — identical to `arm-b-adjusted.txt` |
| F3 | No signal was masked by bad corporate-action handling | **PROVEN as an inference from F1/F2** | Both arms' selection edges are negative and insignificant, and the fitted signs are unchanged. The inference is sound *for the corrections actually applied*, which are dividend add-back plus window exclusion — DEFECT-1 and DEFECT-2 mean the arm is not a full correction |
| F4 | No evidence store written and no multiplicity ordinal spent | **PROVEN, with one precision** | `screen_mizan_out_of_sample.py` opens an `EvidenceStore` read-only (`list_verified`, `open_verified`) and has no write call. An empty store skeleton exists at `data/evidence/models/mizan-adjusted-v1/` (created 2026-09-10 22:58) holding **no trial, no model, no ordinal** |
| G1 | Three defects existed in the authority cadence | **NOT TESTED** | The pre-`ee1b0cb3` code is not in my tree and I did not reconstruct it. I verified current behaviour instead (G3) |
| G2 | Fixing only the first would have been worse than fixing none | **NOT TESTED** | A counterfactual about code that no longer exists |
| G3 | Freshness requires FETCHED, `effective_from <= start`, `effective_to >= end`, age <= 24h | **PROVEN** | `ingest_all_market_data.py:185-208` implements exactly that conjunction, lower bound and non-negative age included |
| G4 | 3,359 authorities re-pulled: 3,359 FETCHED, 0 stale, 0 unavailable | **PROVEN as stated, with a caveat** | §4.7. 3,359 authorities, 3,359 provenance sidecars, `{'FETCHED': 3359}`, window 2016-08-22..2026-09-10, all inside a 34-minute run. Caveat: **1,269 of 3,359 (37.8%) hold an empty list**, and `_request_corporate_actions` treats an HTTP 200 with an empty body as a successful fetch, so `FETCHED` cannot distinguish "no actions" from "empty response". Within the 423-name universe only 8 are empty and all 8 are ETFs or post-2021 listings |
| H1 | 18 of 56 named; 49 issuers queried; 0 fetch failures | **PROVEN from the artifact, not re-fetched** | `reports/corporate_action_validation/demerger-resulting-companies.json` is internally consistent: 56 result rows, 18 named, 49 distinct issuers, `fetch_failures: []`. I did not re-run the live NSE queries |
| H2 | RELIANCE 2023-07-20 rejected as `FILER_IS_RESULTING_COMPANY` | **PROVEN** | That action carries 1 rejected match, `flags: ['FILER_IS_RESULTING_COMPANY']`, `usable: false`, `named_resulting_company: null` |
| H3 | SCI flagged `NAME_MAY_BE_TRUNCATED` and not repaired | **PROVEN** | SCI 2023-03-31 carries exactly that flag and keeps "Land and Assets Limited". Note: two other matches on the same action quote the full correct name and the selection took the truncated one |
| H4 | No entitlement ratio is extracted anywhere; nothing writes a factor | **PROVEN by grep** | `fetch_demerger_announcements.py` has no numeric-ratio regex — its six `re.compile` calls are all name and scheme matchers — and exactly one write, `args.out`, the report JSON. `--validated` is read-only input |
| H5 | Spot-check the 18 names against the quoted filing text | **DISPROVEN — one wrong citation** | §5 DEFECT-3. **RAYMOND 2025-05-14 is named "Raymond Lifestyle Limited" on the strength of filings dated 2024-06-30 and 2024-07-10** — the same two filings the artifact cites for the *2024-07-11* ex-date, a separate row in the same file. The 2025 action is the Raymond **Realty** demerger. The ±540-day window admitted the earlier scheme and nothing flagged it |
| I1 | The three test files collect 90 tests and all pass | **PROVEN** | §4.8. `90 passed in 0.50s`; 90 collected, 0 skipped, 0 xfail |
| I2 | Do the tests encode the same premises as the code? | **PARTIALLY DISPROVEN** | §4.9. 32 mutations across the four source files: **26 killed, 6 survived** the three named files; re-run against every test file that touches these modules, **5 still survive**, one of them a guard whose own docstring cites a prior Red Team defect as the reason it exists |

`NOT TESTED`: G1, G2. Both are counterfactual claims about code that no longer exists in the tree.
I did not reconstruct the pre-`ee1b0cb3` implementation, so I can neither confirm nor refute them;
I verified the current behaviour instead.

## 3. What I ran, and how independent it is

The measurement code for A1, B2, B4, C2 and the two defects is mine, written for this adjudication
and importing **nothing** from `quant_system`: it reads the gzipped JSONL blobs out of the evidence
store directly, parses the NSE subject lines with regexes I wrote from the raw strings, and does its
own log-space arithmetic. Where I needed to judge the module's own behaviour — C1, C4, the parser
coverage census — I called its public API and report what it returned.

Store index built independently from the manifest headers: **3,322 manifests, 3,267 distinct
symbols, 55 symbols carrying two DATASET resources**, which is the dedup rule the authors' own
builder uses. I selected per symbol by (row count, provider instrument id), the same rule, so my
denominator cannot differ from theirs by dataset choice.

## 4. Raw output of the re-measurements

### 4.1 A1 / B2 / C2 — my own scan of the 423-name universe

```
$ .venv/Scripts/python.exe scratchpad/measure_a1.py index.json a1.json
universe symbols: 423
published-ratio structural actions with an ex-date bar: 212
  (structural actions total incl. no-ex-date-bar: 212)
verdict counts: Counter({'ALREADY_APPLIED': 212})
largest |ln(gap)| : 0.1035  ASTRAL 2019-09-16 observed=1.1091 published=0.8000
old-rule blind band |1-factor|<=0.40 : 57 of 212
  kinds in band: Counter({('bonus',): 57})
ratio-less (demerger) actions: 56
  ratio-less with gap > +20% (would have been 'corrected' upward): 3
    NMDC         2022-10-27 gap +71.04%
    BAJAJELEC    2023-09-14 gap +32.21%
    SCI          2023-03-31 gap +30.00%
  ratio-less gap range: -77.269% .. +71.043%
symbols missing from store index: 0 []
subject lines with a structural keyword my parser could not size: 4
  reasons: Counter({'BONUS_KEYWORD_NO_RATIO': 4})
```

A1, B2 and C2 reproduce exactly, including the extremum and the fact that every blind-band member is
a bonus. The 56 ratio-less actions split 54 with an ex-date bar and 2 without (HEG 2026-09-07,
INDIAGLYCO 2026-09-02, both after the cache's 2026-08-21 end), which reconciles the module
docstring's "54" with the validator's "56".

### 4.2 A2 — what applying the ratio on top would do

```
TATASTEEL 2022-07-28: prev_close=95.95 ex_open=98.1 ex_close=100.35
   open/prev_close  = +2.2408%   -> applying 0.1 gives +922.4%
   close/prev_close = +4.5857%   -> applying 0.1 gives +945.9%
BEL 2017-03-16: prev_close=47.55 ex_open=48.3 ex_close=50.05
   open/prev_close  = +1.5773%   -> applying 0.1 gives +915.8%
   close/prev_close = +5.2576%   -> applying 0.1 gives +952.6%
```

### 4.3 B4 — how close the real corpus comes to the decision boundary

The verdict flips where `ln(observed) = ln(published)/2`. Distance from that boundary, tightest first:

```
 margin_ln  flip_move symbol       exdate          gap%  published
    0.0453     -4.42% ICICIBANK    2017-06-20     -0.24     0.9091
    0.0763     -7.35% ASTRAL       2021-03-18     -6.53     0.7500
    0.0798     -7.67% BEL          2017-09-28     +3.26     0.9091
    0.0862     -8.26% CONCOR       2017-04-05     -2.50     0.8000
    0.0866     -8.29% CUB          2017-07-13     +3.97     0.9091
    0.0897     -8.58% BERGEPAINT   2023-09-22     -0.14     0.8333
    0.0916     -8.75% OIL          2017-01-12     -5.09     0.7500
worst (smallest) margin: 0.0453 ln -> the day would have to move a further 4.42% to flip the verdict
median margin: 0.3567
|ln(published)| <= 0.30 (tolerance alone cannot separate): 26 of 212
```

Scored against each symbol's own empirical overnight-gap distribution:

```
 P(flip)   thresh    days symbol       exdate      published actual gap
  0.364%   -4.65%    9/2475 KTKBANK      2020-03-17     0.9091     +5.60%
  0.364%   -4.65%    9/2475 ICICIBANK    2017-06-20     0.9091     -0.24%
  0.323%   -4.65%    8/2475 BEL          2017-09-28     0.9091     +3.26%
actions where at least one historical day would have flipped the verdict: 19 of 212
max flip probability on a single action: 0.364% (KTKBANK 2020-03-17)
expected number of the 212 misclassified: 0.03
```

So B4 holds on the real corpus with room to spare, and the log-space test is a genuine improvement
over the absolute-tolerance one. It is not structurally safe, though: for a 1:10 bonus the provider
*had* applied, a -4.7% session would be enough to double-adjust the series. The safety here is
empirical, not guaranteed.

### 4.4 C3 — re-running the demerger validator (outputs redirected to scratch)

```
$ .venv/Scripts/python.exe scripts/validate_demerger_factors.py --out <scratch> --discovery-out <scratch> --index-cache <scratch>
universe     : 423 symbols
entitlements : 1 filing-sourced ratios
listing dates: 3267 symbols (manifest headers only)
bars loaded  : 423 of 424 requested
candidates   : 1244 instruments listed within 60d of a ratio-less ex-date
ratio-less actions : 54
validated          : 0
refused            : 56
  NO_FILING_RATIO                        54
  NO_EX_DATE_BAR                         2
```

Reproduces the committed artifact exactly. Read it for what it is: 54 of the 56 refusals are
"nobody supplied a ratio", not "a ratio was checked and failed". The one entitlement in the table is
HEG, refused for having no ex-date bar. **The value-continuity arithmetic has never run on a real
input, and no test exercises it** — there is no `tests/test_*demerger*` file at all.

### 4.5 D1 — recomputing every committed manifest hash

```
$ .venv/Scripts/python.exe scratchpad/d1_hashes.py
market-cache stores scanned : 6
committed dataset manifests : 8714
  schema_version 1 (RAW)    : 8714
  schema_version 2 (ADJUSTED): 0
  adjustment == the exact v1 literal: 8714
recomputed hash MATCHES recorded identity : 8714
recomputed hash MISMATCH                  : 0
no recorded identity                      : 0
```

A wider scan of the whole evidence tree found **0 of 9,072** `manifest.json` files carrying an
`ADJUSTED` adjustment block. The D2/D3 mechanism is real and tested, but nothing in this repository
has ever published evidence through it.

### 4.6 E4 — leakage probe

```
--- A. features on the RAW series vs on a series back-adjusted for a FUTURE action ---
decision bar 2024-02-10, future ex-date 2024-02-25 (factor 0.5)
  raw close at decision      : 106.7929201909006932108995797
  adjusted close at decision : 53.39646009545034660544978985
    return_1             raw=0.004                adjusted=0.004
    return_5             raw=0.005984884049       adjusted=0.005984884049
    return_10            raw=0.019110942108       adjusted=0.019110942108
    rsi_14_centered      raw=0.426631024099       adjusted=0.426631024099
    sma_20_distance      raw=0.01571215688        adjusted=0.01571215688
    atr_14_normalized    raw=0.019699852268       adjusted=0.019699852268
  every v1 feature identical : True

--- B. an action dated after the whole series ---
  without: factors=[] unresolved=[]
  with   : factors=[] unresolved=[('2030-01-01', 'NO_EX_DATE_BAR')]
```

Every v1 feature is exactly scale-invariant, so halving the whole window changes nothing. That is
what makes back-adjustment safe *for this feature family*; it is a property of these six features,
not a guard, and a future family with a level-dependent feature would leak with nothing to stop it.
A far-future action does create an `UNRESOLVED` record, which can black out a window — the window is
in the future, so no past decision is affected, but the mechanism is date-blind.

### 4.7 G4 — the authority sweep

```
authority files   : 3359
provenance files  : 3359
provenance missing: 0
status            : {'FETCHED': 3359}
effective_from    : {'2016-08-22': 3359}
effective_to      : {'2026-09-10': 3359}
fetched_at range  : 2026-09-10T12:14:26Z .. 2026-09-10T12:48:22Z
authority files that are an EMPTY list: 1269
```

### 4.8 I1 — the named test files

```
$ .venv/Scripts/python.exe -m pytest tests/test_corporate_actions.py tests/test_adjustment_provenance.py tests/test_adjusted_label_economics.py -q
collected 90 items
tests\test_corporate_actions.py ........................................ [ 44%]
....                                                                     [ 48%]
tests\test_adjustment_provenance.py ...................................  [ 87%]
tests\test_adjusted_label_economics.py ...........                       [100%]
============================= 90 passed in 0.50s ==============================
```

### 4.9 I2 — mutation testing

Thirty-two deliberate defects, applied one at a time to an isolated copy of `src/` and reverted
after each run. Against the three test files the brief names:

```
BASELINE: 90 passed in 0.43s

[killed]   M01 MAX_LOG_RESIDUAL 0.15 -> 1.0            1 failed
[killed]   M02 nearest-hypothesis verdicts swapped     15 failed
[killed]   M03 tie-break restored to the old bias      6 failed
[killed]   M04 bonus factor inverted                   6 failed
[killed]   M05 split factor inverted                   7 failed
[killed]   M06 ratio-less action silently dropped      6 failed
[killed]   M07 MATCHES_NEITHER silently dropped        1 failed
[killed]   M08 adjust_bars off-by-one on the ex-date   8 failed
[killed]   M09 volume no longer rescaled               1 failed
[killed]   M10 ascending-bar-order guard removed       1 failed
[killed]   M11 dividend removed when total_return=False 2 failed
[killed]   M12 validated factor needs no evidence      1 failed
[killed]   M13 GAP_INFERRED_ONLY becomes corroborated  1 failed
[killed]   M14 spans_unresolved ignores uncorroborated 1 failed
[killed]   M15 spans_unresolved always False           7 failed
[killed]   M16 carry_factor window closed-closed       1 failed
[SURVIVED] M17 factor_set_hash ignores unresolved      90 passed
[killed]   M18 RAW-with-factors guard removed          1 failed
[killed]   M19 RAW adjustment literal changed          2 failed
[killed]   M20 adjusted manifest keeps schema_version 1 1 failed
[killed]   M21 entry_notional priced on adjusted bar   1 failed
[killed]   M22 gross_return measured on raw bars       6 failed
[killed]   M23 unresolved-window refusal removed       1 failed
[killed]   M24 unresolved window narrowed to one day   1 failed
[SURVIVED] M25 per-bar execution identity check removed 90 passed
[SURVIVED] M26 refused quotes counted as used          90 passed
[SURVIVED] M27 derive_adjusted source-binding removed   90 passed
[killed]   M28 content hash describes the RAW records  6 failed
[SURVIVED] M29 dividend relabelled GAP_CONFIRMED       90 passed
[killed]   M30 unresolved dropped from provenance      1 failed
[SURVIVED] M31 exit priced on the entry bar's close    90 passed
[killed]   M32 adjust_bars applies refused VALIDATED   1 failed

SURVIVING MUTANTS: 6 of 32
RESTORED BASELINE: 90 passed in 0.42s
```

Re-run against **every** test file that touches these modules — `test_adjusted_label_economics`,
`test_adjustment_provenance`, `test_corporate_actions`, `test_ingest_corporate_action_authority`,
`test_modeling_labels`, `test_modeling_partitions`, `test_modeling_provider_replay`,
`test_short_horizon_mapping`, `test_mizan_store_fidelity`, `test_committed_evidence_integrity` —
one more mutant dies and **five survive**:

```
BASELINE: 1 failed, 135 passed, 2 skipped
  pre-existing failure: test_committed_evidence_integrity.py::test_gitattributes_exempts_evidence...
[SURVIVED] M17 factor_set_hash ignores unresolved actions
[SURVIVED] M25 labels: per-bar execution instrument identity check removed
[SURVIVED] M26 labels: refused quotes counted as used
[SURVIVED] M27 derive_adjusted: source-binding check removed
[SURVIVED] M29 derive_adjusted: dividend relabelled PARSED_AND_GAP_CONFIRMED
[killed]   M31 labels: exit priced on the entry bar's close   (4 new failures in test_modeling_labels)
```

The answer to the brief's question is therefore: **mostly no, with five real holes.** The premises
that were re-derived on 2026-09-10 — nearest-hypothesis scoring, never sizing a demerger from its
gap, refusing a window that spans one, costs on the raw notional — are all genuinely defended by
tests that fail when the behaviour changes. What is *not* defended:

- **M25** deletes the per-bar instrument identity check in `_validate_execution_source`. Its own
  docstring says it exists because "a Red Team recheck already found [this] once on this codebase,
  where a symbol was bound by map key rather than by each bar's own identity". The guard added in
  response to a known, previously-shipped defect has no test. The two tests that *look* like they
  cover it (`test_an_execution_acquisition_for_a_different_symbol_is_refused`) exercise the
  **manifest-level** check three lines above, not the per-record loop.
- **M26** makes a refused cost quote count as used — exactly claim E3 — and nothing notices.
- **M27** deletes the check that an `AdjustmentReference` binds the acquisition it is applied to,
  so an adjusted series could be derived with another dataset's provenance.
- **M29** relabels a dividend factor `PARSED_AND_GAP_CONFIRMED`, asserting gap corroboration for a
  factor no gap can corroborate. This is the exact evidence-overstatement the taxonomy exists to
  prevent, and it is invisible to the suite.
- **M17** drops `unresolved` from the factor-set hash, so two adjustment references that differ only
  in what they could not size collide on one identity.

## 5. Defects

Three, none of them repaired by me. The first two share one root cause, and it is the third shared
premise the brief asked me to look for.

### The root cause, stated once

The corpus measurement that produced A1 counted **only the actions the module's own parser can
size**. The conclusion drawn from it — "the provider back-adjusts, so measure rather than assume" —
was then relied on for the whole corporate-action surface. But the safety argument only works for
actions the parser *sees*: an action it cannot parse produces no factor, no `ALREADY_APPLIED` note,
no `MATCHES_NEITHER` verdict and **no unresolved record**, so `spans_unresolved` returns `False` and
the fabricated return is published. The parser is the denominator of A1 and the gate of C4 at the
same time, so a parsing gap is invisible to both.

Census over the 423-name universe, using the module's own `parse_subject_factor`:

```
authority records examined: 6384
  sized structurally: 212   reported unresolved: 56   dividend-only: 4488
  STRUCTURAL-KEYWORD records the parser makes completely invisible: 183
  Counter({'buy back': 74, 'buyback': 66, 'rights': 40, 'bonus': 3, 'scheme': 2})
```

Buybacks are correctly ignored — a tender offer does not rebase a continuing share. The other 45 are
not.

### DEFECT-1 (P1) — a rights issue is neither adjusted nor flagged

39 rights records in the universe. The parser has no rights branch at all: `grep -rn "rights"` over
`src/quant_system/data/`, `src/quant_system/modeling/` and `validate_demerger_factors.py` returns
**nothing**. A rights issue dilutes at a discount, so the ex-date quote drops by the theoretical
ex-rights adjustment, exactly as a bonus does — and unlike a bonus, the provider does not appear to
remove it.

Reproduction, through the module's public API against the real committed authorities and cache
(`scratchpad/repro_rights.py`):

```
=== BHARTIARTL rights ex-date 2019-04-23 ===
  authority subject           : [' Rights 19:67 @ Premium Rs 215 Per Share']
  observed ex-date gap        : -6.98%  (prev close 342.95, ex open 319)
  factor produced on that date: []
  unresolved record           : []
  spans_unresolved(2019-04-22, 2019-04-23) = False
  -> a label held across this date is PUBLISHED with gross return -6.98%

=== HCC rights ex-date 2025-12-05 ===
  authority subject           : ['Rights 277:630 @ Premium Rs 11.50/-']
  observed ex-date gap        : -22.94%  (prev close 25.94, ex open 19.99)
  factor produced on that date: []
  unresolved record           : []
  spans_unresolved(2025-12-04, 2025-12-05) = False
  -> a label held across this date is PUBLISHED with gross return -22.94%

=== CCAVENUE 2025-06-26 gap -9.01% ... spans_unresolved = False
=== INTELLECT 2017-07-17 gap -8.96% ... spans_unresolved = False
```

For BHARTIARTL the theoretical ex-rights factor is about -7.6% to -8.2% against an observed -6.98%:
the published return is very largely the dilution, not a loss. Applying the module's **own**
nearest-hypothesis test to the 32 rights records whose price basis is comparable gives
`ALREADY_APPLIED 17 / NOT_APPLIED 15 / MATCHES_NEITHER 0` — that is, it cannot tell, which by the
module's own doctrine is precisely the case that must be reported **unresolved** rather than
published. HEG's -64.3% demerger is the event that started this whole work; HCC's -22.94% is the
same error, one third the size, still in the data.

### DEFECT-2 (P2) — the TOTAL_RETURN basis silently misses 9.7% of dividends

`_DIVIDEND_RE` is `(?:rs|re)\.?\s*(\d+(?:\.\d+)?)\s*per\s+share`. The split regex three lines above
it explicitly allows the `/-` suffix (`(?:/-)?`); the dividend regex does not. NSE's dominant format
carries it.

```
$ .venv/Scripts/python.exe -c "import re; DIV=re.compile(r'(?:rs|re)\.?\s*(\d+(?:\.\d+)?)\s*per\s+share', re.I); ..."
'Annual General Meeting/Dividend - Rs 4/- Per Share' -> None
'Annual General Meeting/Dividend Rs 40/- Per Share'  -> None
'Interim Dividend Rs 11/- Per Share'                 -> None
'Dividend - Rs 5 Per Sh'                             -> None
'Interim Dividend Rs - 0.50 Per Share'               -> None
'Dividend - Rs 10 Per Share'                         -> 10
```

Measured over the 423-name universe:

```
dividend-hinted authority records                          : 5083
  priced into a TOTAL_RETURN factor                        : 4590
  silently NOT priced                                      : 493  (9.7%)
  of the unpriced, recoverable by allowing the '/-' suffix : 441
unremoved payout as a fraction of the cum close (names with no later split):
  median 0.6232%, mean 0.9152%, max 6.2284%
largest: COALINDIA 2021-12-06 6.23%, COALINDIA 2017-03-14 6.23%, NHPC 2017-01-19 5.70%,
         PGHH 2017-05-17 4.50%, MRPL 2017-08-10 4.46%, ONGC 2019-02-28 3.69%
```

So on 493 ex-dates the series the module calls `TOTAL_RETURN` still reads a payout as a loss, a
typical 0.6-0.9% fabricated negative return, concentrated in 2016-2019. No unresolved record is
written, so nothing downstream can refuse it. This is the same failure shape as DEFECT-1 and it
directly weakens F3: Arm B is "dividends *mostly* added back", not "dividends added back".

### DEFECT-3 (P3) — one wrong issuer citation

`reports/corporate_action_validation/demerger-resulting-companies.json`, RAYMOND 2025-05-14, is
named `Raymond Lifestyle Limited` from two matches dated **2024-06-30** and **2024-07-10**. Those
are the same two filings the artifact cites for the RAYMOND **2024-07-11** row. The 2025-05-14
action is the Raymond Realty demerger; the ±540-day search window reached back into the previous
scheme, and no flag fired. The artifact carries a generic warning that this can happen; this is the
instance, and it is the failure mode H5 exists to catch — a wrong name is worse than no name,
because the next step is a human looking up "the ratio" in the wrong filing.

### Also worth recording (not defects)

- `AJANTPHARM 2022-06-22 "Bonus- 1:2"` is invisible to the parser: `_BONUS_RE` requires
  `bonus\s*\d`, and the hyphen defeats it. Harmless here (the measured gap is +2.67%, i.e. the
  provider had applied it) but it is a published ratio the module neither applies nor reports.
  `BRITANNIA`'s two `"Scheme Of Arangement- Bonus - 1 Debenture..."` records are invisible for a
  second reason: NSE misspells "Arrangement", so `_RATIOLESS_HINT` misses it too.
- `LabelRowV1.entry_price` is written from the **adjusted** bar while `component_costs` were priced
  on the **raw** bar. Internally consistent inside `labels.py`, but a consumer recomputing
  `cost / (entry_price * quantity)` from an exported label row would not reproduce the net return.
  No current consumer does.
- Out of scope but found in passing: `nse-research-universe-liquid-10y.csv` declares
  `YearsActive 10.00` for MEDPLUS, STARHEALTH and EMIL, whose cached series hold 1,920 / 1,207 / 959
  bars against ~2,476 for a full window, and whose manifests nonetheless report
  `received_range.start 2016-08-22`. Someone who owns the universe builder should look at that; it
  does not change any number in this report.

- There is no de-duplication of authority records. 92 `(symbol, ex_date)` pairs in the universe
  carry more than one record; 3 carry a byte-identical duplicate, and where that duplicate is a
  dividend the payout is removed twice (`ANANTRAJ 2018-09-19 Re 0.24`, `JAMNAAUTO 2023-07-21
  Rs 1.10`, both listed twice verbatim). Where two *genuine* payouts share an ex-date the code
  multiplies `(P-D1)/P` by `(P-D2)/P` instead of using `(P-D1-D2)/P`; the difference is
  `D1*D2/P^2`, which on real prices is order 1e-5 and does not matter.

## 6. The A/B screen, re-run

Arm A, on the committed raw feature store, my run:

```
$ .venv/Scripts/python.exe scripts/screen_mizan_out_of_sample.py --no-adjust
train symbols (governed) : 45
test  symbols (untouched): 378
labels          : RAW (unadjusted)
training rows (43 names) : 108,585
test rows (380 names)    : 902,582

fitted coefficients (trained on the 43 only):
   return_1                      -0.001982
   return_5                      -0.002382
   return_21                     -0.003125
   rsi_14_centered               -0.001066
   sma_20_distance               +0.008082
   sma_50_distance               -0.005073
   volume_zscore                 -0.001033
   money_flow_multiplier         -0.000545

OUT-OF-SAMPLE on the 380 names that never produced the hypothesis:
long top 20% by Mizan score        n=2413 mean=+0.006528 t= +5.86 sharpe= +0.60  vs equal-weight +0.006550
equal-weight all names (bench)     n=2413 mean=+0.006550 t= +6.80 sharpe= +0.69  vs equal-weight +0.006550

selection edge over benchmark      n=2413 mean=-0.000022 t= -0.07 sharpe= -0.01  vs equal-weight +0.000000
```

Identical to `reports/mizan_ab_screen/arm-a-raw.txt` line for line, coefficients included. F1 holds.

Arm B, on the committed adjusted feature store
`data/evidence/feature-store/mizan-adjusted-v1/mizan_feature_store.csv.gz`, my run:

```
$ .venv/Scripts/python.exe scripts/screen_mizan_out_of_sample.py --feature-store data/evidence/feature-store/mizan-adjusted-v1/mizan_feature_store.csv.gz
  refused 532 windows spanning an unsized corporate action
labels          : corporate-action adjusted
training rows (43 names) : 108,158
test rows (380 names)    : 899,840

fitted coefficients (trained on the 43 only):
   return_1                      -0.001850
   return_5                      -0.001738
   return_21                     -0.003767
   rsi_14_centered               -0.001448
   sma_20_distance               +0.008177
   sma_50_distance               -0.003675
   volume_zscore                 -0.000730
   money_flow_multiplier         -0.000964

long top 20% by Mizan score        n=2413 mean=+0.007249 t= +6.61 sharpe= +0.68  vs equal-weight +0.007433
equal-weight all names (bench)     n=2413 mean=+0.007433 t= +7.73 sharpe= +0.79  vs equal-weight +0.007433
selection edge over benchmark      n=2413 mean=-0.000185 t= -0.66 sharpe= -0.07  vs equal-weight +0.000000
```

`diff` against `reports/mizan_ab_screen/arm-b-adjusted.txt`: **identical**. Both arms are fully
reproducible from the committed tree, which is more than most results in this repository can say.

One correction to the record that travels with this: `arm-b-feature-store-rebuild.txt` says the
adjusted store was written to another session's temp directory. It was, but an identical store is
also committed at `data/evidence/feature-store/mizan-adjusted-v1/`, and that is what I used. The
committed store's own metadata independently corroborates A1 — `factors_applied: 4590`,
`symbols_adjusted: 391`, `validated_demerger_factors: 0`, `unresolved_actions: 56` — and 4,590 is
exactly the number of *dividend* records my scan found the parser prices. Every factor in the
production artifact is a dividend. Not one structural factor was needed across 423 names and ten
years, which is what A1 asserts, arrived at from the other end.

F3's inference is therefore sound within its own terms and narrower than it sounds: Arm B is
"dividends mostly added back and demerger windows dropped". It is not a corporate-action-corrected
series, because rights issues were never corrected (DEFECT-1) and 9.7% of dividends were never
removed (DEFECT-2). Neither defect plausibly reverses a `t = -0.66`, and I am not claiming it does.

## 7. The five survivors, against the entire suite

To remove any doubt that some distant test covers them, each survivor was run against the whole
suite in the isolated copy:

```
BASELINE: 12 failed, 1465 passed, 2 skipped in 495.43s
  (all 12 are artifacts of the isolated copy -- release packaging, the desktop launcher,
   .gitattributes and a decision-record citation, none of which I copied. They are constant
   across every run and are excluded from the differential.)

[SURVIVED] M17 factor_set_hash ignores unresolved actions        12 failed, 1465 passed
[killed?]  M25 per-bar execution identity check removed          13 failed, 1464 passed
           new failure: tests/test_server_supervisor.py::test_supervisor_heartbeats_and_progress_tracking
[SURVIVED] M26 refused quotes counted as used                    12 failed, 1465 passed
[SURVIVED] M27 derive_adjusted source-binding removed            12 failed, 1465 passed
[SURVIVED] M29 dividend relabelled PARSED_AND_GAP_CONFIRMED      12 failed, 1465 passed
[killed]   M31 exit priced on the entry bar's close              19 failed, 1458 passed
RESTORED: 12 failed, 1465 passed, 2 skipped in 497.91s
```

M25's apparent kill is **not real**. `tests/test_server_supervisor.py` contains zero references to
`labels`, that run took 613s against a 495s baseline because the machine was also running the Arm B
screen, and the file is one of the known `sleep-in-test` flakiness risks. Probed directly:

```
does test_server_supervisor.py import anything from modeling.labels?  0
  M25 applied, run 1: 10 passed in 13.71s
  M25 applied, run 2: 10 passed in 13.56s
  M25 applied, run 3: 10 passed in 13.52s
```

So the final tally is **32 mutations, 27 killed, 5 surviving the entire 1,477-test suite**: M17,
M25, M26, M27, M29. Two of them — M25 and M29 — delete or invert guards that exist specifically
because an earlier defect of that exact shape shipped.

## 8. Verdict

**BLOCKED.**

Most of this work is sound, and I want that on the record before the reasons. A1 is true and I
re-measured it from the cache rather than accepting it: 212 of 212, largest `|ln(gap)|` 0.1035, and
the production artifact independently agrees by applying 4,590 factors of which every single one is
a dividend. B2 is exact. C2 is exact. The log-space test is a real improvement and is empirically
safe on this corpus. Both A/B arms reproduce byte-identically from the committed tree. 8,714
committed manifest hashes are untouched. The refusal-to-guess doctrine on demergers is implemented,
not merely asserted, and the tests defend it.

It is blocked on these, in order:

1. **DEFECT-1 (P1).** The C4 guarantee — "a window spanning an action of unknown size is refused
   rather than published" — does not hold for rights issues, of which there are 39 in the research
   universe. They are never parsed, so they never become "unknown size"; `spans_unresolved` returns
   `False` and a fabricated return is published. Reproduced on four real symbols, worst case
   **-22.94%** in a single session. This is the same class of error as the HEG demerger that started
   the whole correction, still present, and invisible because the parser is simultaneously the
   denominator of the A1 measurement and the gate of the C4 guarantee.
2. **DEFECT-2 (P2).** 493 of 5,083 dividend records (9.7%) in the universe are silently unpriced
   because `_DIVIDEND_RE` does not allow the `/-` suffix that the split regex on the line above it
   does allow. The `TOTAL_RETURN` series therefore reads a typical 0.6-0.9% payout as a loss on each
   of those ex-dates, with no unresolved record and nothing downstream able to refuse it.
3. **I2 is partially disproven.** Five deliberate defects survive all 1,477 tests, including the
   removal of the per-bar instrument-identity check whose own docstring cites the Red Team finding
   that caused it to be written, and the relabelling of a dividend as gap-confirmed — an
   evidence-strength claim no gap can support, in the one taxonomy whose entire purpose is to stop
   exactly that overstatement.
4. **H5 is disproven** on one citation: RAYMOND 2025-05-14 is named from the previous year's scheme.
   Low severity on its own; high severity as a pattern, because the next step in that workflow is a
   human opening the cited filing to find "the ratio".
5. **C3 is true but hollow.** "0 validated / 56 refused" is 54 "nobody supplied a ratio" plus 2 "no
   bar". The value-continuity check that alone can promote a demerger factor has never run on any
   input and has no test. Nothing downstream should treat it as a working validation path yet.

What would clear the block, stated as evidence rather than as instructions: a demonstration that a
rights ex-date either produces a corroborated factor or an `UnresolvedRecord`; a dividend census
showing the unpriced count at zero; tests that fail under M17, M25, M26, M27 and M29; a corrected or
withdrawn RAYMOND 2025 citation; and one exercised, tested run of the value-continuity validator.

None of it was repaired by me. `git diff --stat` over every file in scope is empty, no evidence store
was written, and no multiplicity ordinal was spent.
