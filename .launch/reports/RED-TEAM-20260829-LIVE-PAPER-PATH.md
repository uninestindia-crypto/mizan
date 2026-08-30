# Red Team report - the live paper-trading path (2026-08-26 .. 2026-08-29)

STATUS: COMPLETE
VERDICT: **NOT READY.** 8 P1 Critical, 11 P2 Major, 2 P3 Minor.
BRIEF: `.launch/RED-TEAM-BRIEF-20260829-LIVE-PAPER-PATH.md`
ADJUDICATOR: Claude Code, Red Team pass. Did not author any commit in scope.
REPO REVISION UNDER TEST: `c5593cae` (branch `main`)
RUN_UTC: 2026-08-30

This file was written incrementally, one claim at a time, by design: a previous attempt at this
adjudication was terminated mid-run and produced nothing because it batched the write to the end.
Every claim below carries a verdict; none was left unreached.

## Commits in scope

| Commit | What it claims to do | Adjudication |
|---|---|---|
| `c5143c90` | cross-sectional execution strategy (`execution/cross_sectional_strategy.py`) | `CrossSectionalModelStrategy` has **zero production callers** (10.1) |
| `fa9fb9fa` | canonical 400-bar window + shared Mizan v3 kernel (`modeling/mizan_features.py`) | 400 is genuinely derived (C1); kernel reproduces 13 of 15 features exactly (C2) |
| `e18a0e0e` | clears 44 ruff findings, "three real defects among them" | Gate claims verified TRUE; AST-identity claim verified TRUE (C10) |
| `7fb85e83` | live cross-section built by the shared kernel (`execution/mizan_live_features.py`) | Shared kernel confirmed; the "bit-identical" claim is false (C2) |
| `1ca08813` | unattended pre-open refresh + scheduled session (`scripts/run_scheduled_paper_session.py`) | Holiday guard inverted; `--skip-refresh` bypasses every guard (C9) |
| `21b604ac` | `.gitattributes` autocrlf fix; equal-weight selection | Fix works; 264 files left corrupt (C8); sizing not faithful to the screen (C7) |
| `3b9b265a` | test that opens a committed evidence store | Covers COMMITTED markers only, not payloads or caches (C8) |
| `b3e626b5` | portfolio held across sessions (`execution/paper_portfolio.py`) | Cash exact; P&L wrong (C3); hold off by two (C4); drawdown switch inert (10.2) |

## Verdict summary

| # | Claim | Verdict | Highest finding |
|---|---|---|---|
| 1 | 400-bar canonical window is derived, not chosen | PROVEN (arithmetic) / **PARTIALLY DISPROVEN** (the harder half) | P2 Major |
| 2 | Kernel fidelity vs published store; float not Decimal | **PROVEN for 13 features / DISPROVEN for the ranks** - "bit-identical" is false | P2 Major |
| 3 | Carry-forward arithmetic reconstructs cash exactly | PROVEN for cash / **DISPROVEN for P&L** | **P1 Critical** |
| 4 | Rebalance clock hold length equals measured hold | **DISPROVEN** - off by **two**, not one | **P1 Critical** |
| 5 | Exit-rule gating fix is complete | **PROVEN for the fix / DISPROVEN for the class** | **P1 Critical** |
| 6 | `MAX_STANDARDIZED_DEVIATION = 25.0` is derived | **PARTLY DERIVED** - mechanism right, both supporting claims overstated | P2 Major |
| 7 | Equal-weight sizing faithful to the screen | **DISPROVEN** - five divergences, one recreating the defect it fixed | **P1 Critical** |
| 8 | autocrlf fix verified through a checkout cycle | **PROVEN for the fix / DISPROVEN for the verification** | P2 Major |
| 9 | Scheduled runner guards (exit 2/3/4/5) are sufficient | **DISPROVEN** - three unguarded paths; the holiday guard is inverted | **P1 Critical** |
| 10 | Anything overstated and not caught | **CONFIRMED** - four more, two of them P1 | **P1 Critical** |

---

## Findings ranked by severity

### P1 Critical - each blocks the gate on its own

| # | Finding | Where |
|---|---|---|
| P1-1 | A `RESEARCH_ONLY` model executes on the paper surface; the verdict gate lives in a class with zero production callers | 10.1 |
| P1-2 | Cross-session round trips report realized P&L inflated by the entire entry-side statutory cost | Claim 3 |
| P1-3 | The executed hold is 12 sessions against a measured 10 - two independent off-by-ones | Claim 4 |
| P1-4 | A rebalance session where no name clears `score_threshold` liquidates the whole book, on a rule the screen never had | 5.1 |
| P1-5 | `per_name_alloc` is sized from a fixed nominal, not the persisted portfolio, recreating the concentration defect it replaced | 7.1 |
| P1-6 | The holiday guard runs the session on the holiday and blocks the trading day after it | 9.1 |
| P1-7 | `--skip-refresh` bypasses all three data guards and still trades and persists state | 9.2 |
| P1-8 | The total-drawdown kill switch resets every session, so a multi-session decline cannot trip it | 10.2 |

### P2 Major

| # | Finding | Where |
|---|---|---|
| P2-1 | `preprocessing_input_hash` binds 51 bars; the values it certifies depend on the full prefix | Claim 1 |
| P2-2 | "verified bit-identical against the published feature store" is asserted with no test, and is false | Claim 2 |
| P2-3 | `state_from_ledger` overwrites cumulative realized P&L with the session figure | Claim 3 |
| P2-4 | Entry loop ungated; non-idempotent loops; buy-before-sell ordering; swallowed exception still advances state | 5.2-5.5 |
| P2-5 | `CrossSectionCoverage.skipped_extreme` is never populated; the coverage gate runs before refusals | 6.3 |
| P2-6 | Live selection adds an unmeasured score threshold and rounds the count the other way | 7.2-7.3 |
| P2-7 | The screen cited as the measurement authority fits a different model (8 rank features vs 15 raw) | 7.6 |
| P2-8 | 264 tracked evidence files are CRLF against LF blobs; `git status` reports clean | Claim 8 |
| P2-9 | SUCCESS banner and exit 0 on a failed reconciliation, with a hardcoded "0.00 Paisa Discrepancy" | 9.3 |
| P2-10 | `newest_cached_bar_date()` is a global max, so a 499/500 failed refresh passes guard 4; no alarm for absence of signal | 9.4-9.5 |
| P2-11 | `MizanModelCard.model_card_hash` changes on every construction and is served as an identity | 10.3 |

### P3 Minor

| # | Finding | Where |
|---|---|---|
| P3-1 | `apply_cross_sectional_ranks` sorts round-tripped 10dp text; 244 published rows on 115 dates are unreproducible | Claim 2 |
| P3-2 | "every limit from 25 to 200 refused exactly the same single name" generalises from one day; 411 of 2,427 dates disagree | 6.2 |

### What survived attack

- `(13/14)**400 = 1.3369853590130496e-13`. The window size is derived, and 400 carries ~80 bars of
  margin over the 320 that text-equality actually needs.
- The carry-forward **cash** reconstruction is exact. 400 randomised portfolios, a 500-holding case,
  half-paisa and long-tail average costs, a 33-billion-rupee holding: worst drift **0**.
- The 13 instrument-level features reproduce the published store **text-identically** at 48 sampled
  rows across three symbols, including across the 400-bar cap.
- The `.gitattributes` fix works: a real `core.autocrlf=true` checkout now produces byte-exact
  evidence.
- The exit-rule fix itself is complete for the defect it names.
- Ruff clean, mypy clean on 140 files, **1104 tests passing in 65.90s**. `data/universe.py` is
  AST-identical across its 586-line diff, exactly as `e18a0e0e` claimed.

**Every P1 in this report is invisible to all three gates.**

### Coverage

Twelve failure families walked. Twelve executable probes written against real code and real
published data: `probe_claim1.py`, `probe_claim2.py`, `probe_claim2_ranks.py`,
`probe_claim2_ranks_full.py`, `probe_claim3.py`, `probe_claim3b.py`, `probe_claim3c.py`,
`probe_claim4.py`, `probe_claim5.py`, `probe_claim6.py`, `probe_claim6b.py`, `probe_claim9.py`,
plus a real `git checkout-index` cycle under `core.autocrlf=true`.

Data touched: 1,015,831 published Mizan feature rows swept exhaustively twice; three real
acquisitions from the all-market evidence store; the real macro series; the real model card and
preprocessor; the real `DecimalLedger`. Static gates and the full 1104-test suite run to completion.

Targets read: `modeling/mizan_features.py`, `modeling/pooled.py`, `modeling/mizan_model.py`,
`modeling/labels.py`, `modeling/rows.py`, `execution/paper_portfolio.py`,
`execution/mizan_live_features.py`, `execution/cross_sectional_strategy.py`,
`execution/governed_strategy.py`, `execution/paper_pilot.py`, `risk/governor.py`, `core/ledger.py`,
`core/domain.py`, `scripts/run_paper_pilot_session.py`, `scripts/run_scheduled_paper_session.py`,
`scripts/screen_mizan_out_of_sample.py`, `scripts/build_mizan_feature_store.py`,
`scripts/daily_auto_sync.ps1`, `.gitattributes`, `tests/test_committed_evidence_integrity.py`,
`tests/test_mizan_pooled.py`.

---

## Claim 1 - the 400-bar canonical window is derived, not chosen

**VERDICT: the 400 is derived. The stated reason for leaving `MIZAN_WINDOW_BARS = 51` is factually
true and materially incomplete - it is a real inconsistency, not a cosmetic one, and it is
demonstrable.**

### Half one: is 400 derived? PROVEN.

The arithmetic is correct, independently recomputed:

```
$ python -c "for n in (51,100,200,300,350,400,450,500): print(n, (13/14)**n)"
51 0.02283395537985447
100 0.0006046884354123091
200 3.6564810392138634e-07
300 2.2110317987170053e-10
350 5.437018616113912e-12
400 1.3369853590130496e-13
450 3.2877022802855197e-15
500 8.084595849107653e-17
```

`(13/14)**400 = 1.3369853590130496e-13` matches the figure cited at
`src/quant_system/modeling/mizan_features.py:24` and in
`agent_context/work/active/20260826-NOTICE-mizan-v3-reintroduces-window-dependence.md:55`
to every digit stated. The estimator identification is also right: `wilder_rsi`
(`mizan_features.py:83-84`) is `avg = (avg*(period-1) + x)/period`, an EMA with
`alpha = 1/period = 1/14`, so seed influence decays exactly as `(13/14)^n`. The seed itself
(`mizan_features.py:79`) is the simple mean of the first 14 changes, bounded by the data, so the
decay factor is the whole story.

Sanity bound in the direction that matters - the store writes `{:.10f}`, so any error below `5e-11`
in the feature is invisible in the published text. `log(5e-11)/log(13/14) = 320.06`, so **320 bars
already suffices for text-identical output** and 400 carries ~80 bars of margin. 400 is
conservative, derived, and cheap. No objection.

### Half two: is the 51 a rationalisation? The stated reason is TRUE.

`src/quant_system/modeling/pooled.py:88` - `for ordinal in range(MIZAN_WINDOW_BARS - 1, len(records))`

`src/quant_system/modeling/pooled.py:96` - `consumed = records[ordinal - MIZAN_WINDOW_BARS + 1 : ordinal + 1]`

`src/quant_system/modeling/pooled.py:121-128` - `preprocessing_input_hash` is a `canonical_sha256`
over `[record.to_canonical_dict() for record in consumed]`.

So raising 51 to 400 would (a) move the loop start from index 50 to index 399, and (b) change every
row's `preprocessing_input_hash`. Row loss quantified from the published store metadata
(`data/evidence/feature-store/mizan/mizan_feature_store_metadata.json`: `total_rows 1015831`,
`symbols 423`): up to `423 x 349 = 147,627` rows, **~14.5% of the store**. The author's three stated
consequences are all real. Nothing in the stated reason is false.

### But the thing left in place is a defect, and here it is reproduced

`preprocessing_input_hash` is named, and used, as the binding between a published feature row and
the inputs that produced it. **It binds 51 records. The values it accompanies were computed from the
entire prefix** - `scripts/build_mizan_feature_store.py:119` calls `wilder_rsi(closes)` on the whole
series, up to 2,479 bars. The hash therefore does not determine the feature values, and by the
author's own measurement the unbound history moves `rsi_14_centered` by up to `1.29e-02`
(NOTICE line 100), about a tenth of that feature's standard deviation.

Reproduced against the real `build_mizan_feature_dataset`, two 181-bar histories with a
**bit-identical trailing 61 bars** and different prehistory (`scratchpad/probe_claim1.py`, seed 7):

```
rsi_14_centered from full prefix A = -0.0047331247
rsi_14_centered from full prefix B = -0.0058194657
absolute difference               = 0.0010863411
in published feature sd (0.12234317) = 0.0089 sd

row A preprocessing_input_hash = 1cede0942a3e3e3a8800b61a45a4d72ea2fd45866b2fdcfe76f606fbf73e4b9c
row B preprocessing_input_hash = 1cede0942a3e3e3a8800b61a45a4d72ea2fd45866b2fdcfe76f606fbf73e4b9c
HASHES EQUAL                   = True
feature values equal           = False
A rsi feature = -0.0047331247
B rsi feature = -0.0058194657

bars bound by the hash: 51 of 181 supplied
```

Two governed feature rows, identical `preprocessing_input_hash`, different published feature values.
An auditor re-deriving a row from what the hash commits to cannot reproduce it, and cannot detect
that they failed to.

The same 51-bar slice is also what `pooled.py:97-102` point-in-time-checks and what `pooled.py:116`
uses for `information_cutoff_at`. Bars 52..N back, which the values genuinely depend on, are never
checked against the session close and never appear in the cutoff.

### Judgement

The author's reason is a true statement about cost, offered where a statement about correctness was
required. The disclosures at `mizan_features.py:15-30` and `cross_sectional_strategy.py:59-75`
describe the *kernel's* window honestly; neither says that the **evidence hash on the published
training rows under-binds their own inputs**. The NOTICE says "No published research result is
invalidated" (line 103) and justifies it by both sides feeding full prefixes - true for the *values*
and silent about the *hash*. That is the gap.

FINDING   `preprocessing_input_hash` binds 51 bars; the feature values it certifies depend on the full prefix
FAMILY    Data integrity / assumption archaeology
REPRO     `python scratchpad/probe_claim1.py` - two histories, same hash, different values
OBSERVED  Identical `preprocessing_input_hash` for rows whose `rsi_14_centered` differs by 0.0089 sd (up to ~0.1 sd on real data per the NOTICE)
EXPECTED  The hash either commits to every input the row depends on, or is documented as a partial commitment
BLAST     All 1,015,831 published Mizan v3 feature rows. Silent: reproduction failure is undetectable from the evidence
SEVERITY  P2 Major (escalated from Minor because the failure is silent; not P1 only because no published result changes and nothing executes off these rows)

---

## Claim 2 - kernel fidelity

**VERDICT: the thirteen instrument-level features reproduce the published store text-identically at
every index sampled, including across the 400-bar cap. The two cross-sectional rank features do NOT.
The claim "verified bit-identical against the published feature store"
(`src/quant_system/execution/mizan_live_features.py:10-11`) is false as written, and no test in the
repository would ever have detected that.**

### The thirteen instrument-level features: PROVEN

`scratchpad/probe_claim2.py` loads the real acquisitions from
`data/evidence/market-cache/all-market-20160822-20260821/store`, the real macro from
`macro-regimes-20160822-20260821`, and the real published rows from
`data/evidence/feature-store/mizan/mizan_feature_store.csv.gz`, then recomputes each sampled row
through `canonical_mizan_window` -> `compute_mizan_feature_values` and compares the **emitted text**.

```
macro: VIX 2478d NIFTY 2479d
published rows loaded in 6s: GRASIM=2424, RELIANCE=2427, TCS=2424
acquisitions: {'GRASIM': 2476, 'RELIANCE': 2479, 'TCS': 2476}

=== RELIANCE: 2479 bars, 2427 published rows ===
  idx    50 2016-11-04 win=  51: TEXT-IDENTICAL
  idx   100 2017-01-16 win= 101: TEXT-IDENTICAL
  idx   200 2017-06-13 win= 201: TEXT-IDENTICAL
  idx   350 2018-01-17 win= 351: TEXT-IDENTICAL
  idx   399 2018-04-03 win= 400: TEXT-IDENTICAL
  idx   400 2018-04-04 win= 400: TEXT-IDENTICAL
  idx   401 2018-04-05 win= 400: TEXT-IDENTICAL
  idx  1000 2020-09-07 win= 400: TEXT-IDENTICAL
  idx  2000 2024-09-17 win= 400: TEXT-IDENTICAL
  idx  2478 2026-08-21 win= 400: TEXT-IDENTICAL
  -> 16 rows compared; worst per-feature abs diff: none
```

Same result for GRASIM and TCS: 48 rows across three symbols, 13 features each, **zero character of
difference**, including the transition at idx 399/400/401 where the kernel stops being a full prefix
and starts being a truncated window. This half of the claim holds, on real data, which is what the
brief asked for.

### The two rank features: DISPROVEN, on real published data

`apply_cross_sectional_ranks` (`modeling/mizan_features.py:221`) sorts by
`float(cross_section[s][source])` - the value **after** it has been round-tripped through the
10-decimal text. `scripts/build_mizan_feature_store.py:174` sorts by the **raw float**:
`sorted(range(count), key=lambda k: rows[k][1][source])`. The comment at `mizan_features.py:219`
claims "Sort by the source value, matching the builder." It does not match: two names whose raw
`return_5` differs below `1e-10` are a tie to the kernel (broken alphabetically) and are ordered by
the builder.

Reproduced by feeding the store's own published `return_5` / `volume_zscore` columns back into the
kernel's ranking function and comparing to the store's own published rank columns
(`scratchpad/probe_claim2_ranks.py`):

```
2016-11-07: n=407 momentum mismatches=  0 volume mismatches=  0  (published text ties: return_5=3)
2018-04-06: n=417 momentum mismatches=  0 volume mismatches=  0
2020-03-23: n=415 momentum mismatches=  2 volume mismatches=  0
    M HCC: kernel=-0.0783132530 published=-0.0759036145 return_5=-0.2075471698
    M IRB: kernel=-0.0759036145 published=-0.0783132530 return_5=-0.2075471698
2024-09-20: n=423 momentum mismatches=  0 volume mismatches=  0
2026-08-21: n=423 momentum mismatches=  0 volume mismatches=  0
```

HCC and IRB share the published text `-0.2075471698` but not the underlying float. Full sweep over
every published row (`scratchpad/probe_claim2_ranks_full.py`):

```
dates=2427  rows=1,015,831  elapsed=9s
cs_rank_momentum_5   mismatching rows: 244 (0.0240%) on 115 dates
cs_rank_volume_surprise mismatching rows: 0 (0.0000%) on 0 dates
worst momentum dates: [('2019-05-10', 4, 416), ('2019-08-07', 4, 416), ('2019-11-13', 4, 415),
                       ('2020-03-16', 4, 415), ('2020-05-20', 4, 415), ('2020-07-21', 4, 415),
                       ('2023-05-16', 4, 423), ('2016-11-23', 2, 409)]
```

**244 rows on 115 of 2,427 dates - 4.7% of trading dates carry at least one row the kernel cannot
reproduce.** Each is an adjacent-rank swap worth `1/n ~ 0.0024`, about `0.008` of the rank feature's
own standard deviation (`1/sqrt(12) = 0.289` for a uniform rank), so the economic impact of any
single one is small. The defect is not the magnitude; it is that a claim of bit-identity is false
and was believed.

### The float choice: attacked, and it survives on this evidence, for a narrower reason than stated

`mizan_features.py:10-13` argues float over Decimal on fidelity grounds, citing the B3 precedent.
That argument is sound for what it covers and the 48-row check above confirms it empirically. Two
residual exposures it does not cover, neither of which I can close here:

- **`math.log` / `math.sqrt` are libm calls.** The published store, my verification, and the paper
  runner all executed on the same Windows ARM64 machine. The repository's CI gate runs on x86-64
  GitHub Actions. A 1-ULP libm difference is ~1e-18 relative against a 1e-10 text quantum, so it can
  only bite at an exact rounding boundary - but nothing measures it, and the store cannot be rebuilt
  to check.
- **Nothing regression-tests fidelity at all.** `tests/test_mizan_features.py` holds 23 tests and
  none of them opens `mizan_feature_store.csv.gz`; `grep -n "store\|published\|csv"` returns only a
  docstring and a format test. The bit-identity claim is an assertion about a manual run, restated
  in a module docstring as a standing property. It is precisely the class of claim the repository's
  own NOTICE ends on: "A schema declaring a fixed window should be required to **prove** each member
  is reproducible from it. Nothing currently enforces that."

FINDING   `apply_cross_sectional_ranks` sorts round-tripped 10dp text; the builder sorted raw floats. 244 published rows are unreproducible
FAMILY    Data integrity / assumption archaeology
REPRO     `python scratchpad/probe_claim2_ranks_full.py` -> 244/1,015,831 mismatches on 115 dates
OBSERVED  Kernel emits a different `cs_rank_momentum_5` than the store published, for rows tied at 10dp
EXPECTED  Either exact reproduction, or the divergence documented instead of "bit-identical"
BLAST     0.024% of published rows; 4.7% of decision dates carry at least one. Adjacent-rank swap, ~0.008 sd
SEVERITY  P3 Minor

FINDING   "verified bit-identical against the published feature store" is asserted in a module docstring with no test behind it, and is false
FAMILY    Operability / assumption archaeology
REPRO     `grep -n "store\|published\|csv" tests/test_mizan_features.py` -> two hits, neither opens the store
OBSERVED  A one-off manual verification is presented as a standing property; the sweep above disproves it
EXPECTED  A regression test that opens the committed store, or a claim scoped to what was checked
BLAST     Every future reader of `mizan_live_features.py`; any regression in the kernel ships silently
SEVERITY  P2 Major (escalated: the failure is silent and the claim is load-bearing for execution fidelity)

---

## Claim 3 - carry-forward arithmetic

**VERDICT: the cash reconstruction is exact - I could not break it, and I tried hard. But the answer
to the brief's second question (is the zero-fee replay honest, or does it hide a cost?) is that
it hides the entry cost from realized P&L, and separately that cumulative realized P&L is destroyed
every session.**

### The exactness claim: PROVEN. No drift found.

The mechanism is sound, and the reason is that both sides quantize *the same product*:
`PortfolioHolding.cost_basis` (`paper_portfolio.py:75`) is `(average_cost * quantity).quantize("0.01")`,
and `DecimalLedger.process_fill` (`core/ledger.py:284`) debits
`fill.net_cash_delta.quantize(_PAISA)` = `-(price * Decimal(quantity)).quantize("0.01")` for a
zero-fee buy. Identical expression, identical default `ROUND_HALF_EVEN`. They cancel by
construction, not by luck, and per-holding quantization means many holdings cannot accumulate error.

Attacked adversarially (`scratchpad/probe_claim3.py`) with every trap the brief named:

```
getcontext().prec = 28
plain, 2dp average cost                              n=   1 funding=         112345.60 cash_after=         100000.00 drift=0.00
average cost 100.005 x 3 (half-paisa)                n=   1 funding=         100300.02 cash_after=         100000.00 drift=0.00
average cost 100.015 x 1                             n=   1 funding=         100100.02 cash_after=         100000.00 drift=0.00
average cost 1/3-style long tail                     n=   1 funding=         102333.33 cash_after=         100000.00 drift=0.00
500 holdings, 9dp average costs                      n= 500 funding=        2296464.29 cash_after=         100000.00 drift=0.00
1 holding, 10,000,000 shares @ 3333.333333333        n=   1 funding=    33333433333.33 cash_after=         100000.00 drift=0.00
fuzz: 400 random portfolios                          worst drift = 0
```

400 randomised portfolios, up to 60 holdings each, average costs built as n/3, n/7, n/11, n/13,
n/97 to force long non-terminating tails, quantities to 5,000, cash to 8 figures.
**Worst drift across all of it: exactly 0.** This half of the claim is correct.

### But the replay does hide a cost, and it is exactly the entry fee

`scratchpad/probe_claim3c.py` runs the identical economic trade two ways - same session, and
across sessions through the carry-forward path:

```
SAME-session round trip : realized_pnl = 9538.00   cash = 1009538.00
CROSS-session round trip: realized_pnl = 9758.00   cash = 1009538.00

overstatement = 220.00  (exactly the entry fee, 220.00)
cash agrees   = True
```

Buy 100 @ 1000.00 with a 220.00 statutory fee, sell 100 @ 1100.00 with a 242.00 fee. Held within one
session the ledger reports the truth: **9538.00**. Held across a session boundary it reports
**9758.00** - inflated by the entry fee, because the fresh ledger never saw it and
`carry_forward_fills` (`paper_portfolio.py:120`) sets `fee=Decimal("0.00")`.

Cash is right in both cases, which is why this is silent. The number that is wrong is the one a
human reads. `PaperPilotEngine.end_session` sets
`total_realized_pnl=self.ledger.realized_pnl` (`execution/paper_pilot.py:833`), and the runner writes
it straight into the session JSON (`run_paper_pilot_session.py:1202`) and into the markdown summary
(`:1264`). Nothing in the report discloses the omission: the `total_fees_paid` line shows only the
current session's fees, so a reader cannot back the entry cost out.

The docstring at `paper_portfolio.py:107-111` says charging the fee again "would make the portfolio
look worse than it is for a reason that never happened". That is true of **cash** and false of
**realized P&L**, and the code does not distinguish them. The module exists (docstring lines 3-7)
because paying a full round trip daily "shows a loss for reasons that have nothing to do with the
signal". The repair reintroduces the same class of bias with the sign reversed: **every cross-session
round trip now shows a gain larger than the one that happened**, by exactly the entry-side statutory
cost. On a ~950,000 deployed book at the repository's own 0.224% round trip that is on the order of
Rs 1,000 of phantom profit per rebalance cycle, systematically one-directional.

The same mechanism inflates `total_unrealized_pnl` for any carried position, since
`Position.unrealized_pnl` (`core/domain.py:232`) is `(price - average_price) * quantity` and
`average_price` is the carried gross basis with the entry fee already stripped into a previous
session's cash.

### And cumulative realized P&L is destroyed every session

`state_from_ledger` (`paper_portfolio.py:258`) writes `realized_pnl=realized_pnl.quantize(...)` -
it **ignores `previous.realized_pnl` entirely**. The line immediately above it,
`total_fees=(previous.total_fees + fees_paid)`, does accumulate. The asymmetry is not commented on
anywhere.

Five sessions through the real functions (`scratchpad/probe_claim3b.py`):

```
  2026-08-24: ledger.realized=      0.00  saved.realized_pnl=      0.00  cash=   899780.00  fees_to_date=  220.00  holdings=1
  2026-08-25: ledger.realized=      0.00  saved.realized_pnl=      0.00  cash=   899780.00  fees_to_date=  220.00  holdings=1
  2026-08-26: ledger.realized=   9758.00  saved.realized_pnl=   9758.00  cash=  1009538.00  fees_to_date=  462.00  holdings=0
  2026-08-27: ledger.realized=      0.00  saved.realized_pnl=      0.00  cash=  1009538.00  fees_to_date=  462.00  holdings=0
  2026-08-28: ledger.realized=      0.00  saved.realized_pnl=      0.00  cash=  1009538.00  fees_to_date=  462.00  holdings=0

  TRUE cumulative realized P&L = 9538.00
  persisted state.realized_pnl  = 0.00   <-- what the next session reads
  persisted state.total_fees    = 462.00     (this one DOES accumulate)
  cash                          = 1009538.00  (equity is intact; only the P&L record is not)
```

The state file is hash-protected, schema-versioned and atomically written, and the number inside it
is wrong. `run_paper_pilot_session.py:1136-1140` logs it as
"Portfolio saved: cash Rs %s, %d holding(s), realized Rs %s, fees to date Rs %s" - a cumulative
label on a per-session figure, sitting next to a genuinely cumulative one.

FINDING   Cross-session round trips report realized P&L inflated by the full entry-side statutory cost
FAMILY    Money and counting
REPRO     `python scratchpad/probe_claim3c.py` - identical trade, 9538.00 same-session vs 9758.00 across sessions
OBSERVED  `realized_pnl` in the session JSON and the markdown summary omits the entry fee for any position opened on an earlier session
EXPECTED  Realized P&L net of both legs, or the omission disclosed in the report
BLAST     Every cross-session trade, i.e. every trade the rebalance clock is designed to produce. Systematic, one-directional, silent, and it flatters the strategy
SEVERITY  **P1 Critical** (wrong money on the primary output of the whole live-paper path; escalated because it is silent and self-flattering)

FINDING   `state_from_ledger` overwrites cumulative realized P&L with the session's figure
FAMILY    Data integrity / money and counting
REPRO     `python scratchpad/probe_claim3b.py` - after the winning trade and two idle days, `state.realized_pnl == 0.00`
OBSERVED  `paper_portfolio.py:258` ignores `previous.realized_pnl`, one line below `total_fees` which accumulates
EXPECTED  Accumulate, or rename the field to `session_realized_pnl` so the log line is honest
BLAST     The persisted portfolio record. Cumulative P&L is unrecoverable from it after one idle session
SEVERITY  P2 Major (escalated from Minor: silent, and it defeats the audit purpose of a hash-protected state file)

---

## Claim 4 - the rebalance clock

**VERDICT: DISPROVEN. The executed hold is 12 sessions against a measured 10. It is off by two, not
by one, and the two sessions come from two independent mistakes that compound.**

### What was measured

`scripts/screen_mizan_out_of_sample.py:50,97-100`:

```python
HOLD_SESSIONS = 10
...
for i in range(len(opens) - HOLD_SESSIONS - 1):
    ...
    opens[i + 1 + HOLD_SESSIONS] / opens[i + 1] - 1.0 - ROUND_TRIP_COST
```

Entry at `opens[i+1]`, exit at `opens[i+11]`. **Ten sessions held.**

The model card agrees, once its own contract is read. `src/quant_system/modeling/labels.py:40`:

> ``horizon_sessions`` counts decision -> entry -> exit, so the default 2 holds for one session.

So `label_horizon_sessions = h` means `h - 1` sessions held. Confirmed against the real card:

```
$ python -c "from quant_system.modeling.mizan_model import MizanModel; ..."
model_id           : mizan-v1
model_name         : Mizan Flagship Alpha (NSE 50)
label_horizon_sessions = 11
score_threshold    : 0.071454840454
```

`11 - 1 = 10`. The screen and the card do not disagree at all; both say ten.

### What executes

`scripts/run_paper_pilot_session.py:640-641` passes the raw card value as the threshold:

```python
horizon = int(model.config.label_horizon_sessions)  # 11
rebalancing = portfolio.rebalance_due(horizon)
```

and `paper_portfolio.py:134` is `return self.sessions_since_rebalance >= horizon_sessions`.

Simulated with the real `rebalance_due` and the real `state_from_ledger`
(`scratchpad/probe_claim4.py`), no mocks:

```
horizon_sessions = 11
session ssr_at_check rebalance_due  action
      0            0          True  REBALANCE (sell+buy)
      1            0         False  hold
      2            1         False  hold
      3            2         False  hold
      4            3         False  hold
      5            4         False  hold
      6            5         False  hold
      7            6         False  hold
      8            7         False  hold
      9            8         False  hold
     10            9         False  hold
     11           10         False  hold
     12           11          True  REBALANCE (sell+buy)

entry session index        = 0
next rebalance (exit) index= 12
EXECUTED hold length       = 12 sessions
MEASURED hold length       = 10 sessions
OFF BY                     = 2 sessions
```

### The two independent errors

**1. `horizon` is used where `horizon - 1` was meant (+1 session).** The runner's own comment at
`run_paper_pilot_session.py:636-638` states the premise wrongly: "The model was measured entering at
an open, holding `label_horizon_sessions`, then re-ranking". It was measured holding
`label_horizon_sessions - 1`. `paper_portfolio.py:14-15` states both true facts side by side --
"held ``HOLD_SESSIONS = 10``" and "the model's own card records ``label_horizon_sessions = 11``" --
without noticing they are the same number expressed in two conventions, and then uses the larger one.

**2. `sessions_since_rebalance` lags the true age by one (+1 session).** `state_from_ledger`
(`paper_portfolio.py:262`) writes `0 if rebalanced else previous.sessions_since_rebalance + 1`. On
the rebalance session itself it saves 0, and the counter only reaches 1 at the *end* of the first
hold session. So at the check on session `R+k` the counter reads `k-1`, and the trigger `>= 11`
fires at `k = 12`, not `k = 11`. The docstring at `paper_portfolio.py:130` says "the holding must
have aged past the model's declared horizon" -- the counter is not the holding's age, it is the age
minus one.

Each error alone would give 11. Together they give 12.

### Why this matters beyond one session

The screen's Sharpe is annualised as `sqrt(252 / HOLD_SESSIONS)`
(`screen_mizan_out_of_sample.py:123`), so hold length is not a free parameter: it is baked into the
reported statistic. Executing a 12-session hold means the live path is not sampling the strategy
that was screened. It also samples 20% fewer rebalances per year (21 vs 25.2 at 252 sessions), so
any live-vs-screen comparison is comparing different things -- and it does so silently, because
nothing anywhere prints or asserts the realised hold length.

FINDING   Executed hold is 12 sessions where the screen measured 10; two independent off-by-ones compound
FAMILY    Assumption archaeology / state machine
REPRO     `python scratchpad/probe_claim4.py` - entry index 0, next rebalance index 12
OBSERVED  `rebalance_due(11)` first returns True on the 12th session after entry
EXPECTED  Exit on the 10th session after entry, matching `opens[i+1+10]/opens[i+1]` and `labels.py:40`
BLAST     Every position the live paper path ever opens. The live series is not a sample of the screened strategy, and the discrepancy is invisible in every report
SEVERITY  **P1 Critical** (escalated: silent, and it invalidates the only comparison the live path exists to make)

---

## Claim 5 - exit rule gating

**VERDICT: the specific fix is complete and correct. The same class of bug is still live in four
other places in the same script, one of which reopens the exact failure the fix was written to
close.**

### The fix itself: PROVEN complete

`run_paper_pilot_session.py:660-664` sets `mizan_scores = {}`, `mizan_ranked = ()`,
`mizan_picks = ()` on a hold session, and `:956` gates the exit loop:

```python
for sym, pos in list(engine.positions.items()) if rebalancing else []:
    if pos.quantity > 0 and sym not in top_picks:
```

On a hold session the loop body never runs. Nothing else in the script issues a SELL. Verified by
`grep -n "Side.SELL" scripts/run_paper_pilot_session.py` returning only this block. The stated defect
is closed.

### But the same class is live in four more places

**5.1 (P1 Critical) The full-liquidation path is still reachable, on a rebalance session.**
`select_top_fraction` (`mizan_live_features.py:151-152`) filters the top fraction by
`pair[1] > score_threshold` and can return the empty tuple. When it does, `rebalancing` is still
`True`, so line 956 runs with `top_picks == []` and `sym not in top_picks` is true for every
holding. Reproduced with the real functions and the real card threshold
(`scratchpad/probe_claim5.py`):

```
model score_threshold = 0.071454840454
423 names, all just below threshold -> picks = ()  (len 0)
exit loop  (run_paper_pilot_session.py:956-957) sells : ['AAA', 'BBB', 'CCC']
entry loop (run_paper_pilot_session.py:912-914) buys  : []

=> every holding liquidated, nothing bought, 100% cash, full exit cost paid.
```

This is not a hypothetical regime. The model's own recorded selection edge over the equal-weight
benchmark is on the order of `-0.000022` (per `agent_context/CURRENT.md`), so scores cluster near
zero against a `0.0715` floor; a session where no name in the top 20% clears it is ordinary, not
extreme. **And the screen applied no threshold at all** -
`screen_mizan_out_of_sample.py:199-201` is `take = max(1, int(len(scores) * SELECTION_FRACTION))`
followed by `statistics.fmean(...)`, with no score filter anywhere in the file. So the go-to-cash
rule that liquidates the book was never measured, is not in the screen, and fires silently. The
comment at `mizan_live_features.py:135-139` defends the *threshold's value* against a hardcoded
0.035 while missing that the screen's rule had no threshold term at all.

**5.2 (P2 Major) The entry loop is not gated on `rebalancing` - only incidentally protected.**
`:912` is `for sym in top_picks:` with no `if rebalancing`. It is safe today only because
`mizan_picks` happens to be `()` on hold sessions. The invariant "act only on a rebalance session"
is enforced explicitly in one loop and implicitly in the other, forty lines apart. The comment at
`:658-659` records that the cross-section is deliberately not built on hold sessions "because
computing a decision that will not be acted on invites reading it as one" - the moment anyone
reverses that for the dashboard, the entry loop starts buying on hold sessions and nothing stops it.

**5.3 (P2 Major) Neither loop is idempotent, and both re-run every 15-minute step.** The `while`
loop at `:822` runs ~25 times per session. The entry guard is `current_held == 0` (`:913`) and the
exit guard is `pos.quantity > 0` (`:957`) - both read *filled* position state, neither consults
open orders. A partially filled SELL therefore gets a second full-size SELL proposal on the next
step while the first still has remaining quantity; a BUY whose order was cancelled gets re-proposed.
The ledger catches the oversell (`core/ledger.py:296-300`) and the engine cancels the remainder
(`paper_pilot.py:670-679`), so this degrades to duplicate rejected orders rather than a short - but
it is the double-click family, in a loop that fires 25 times a day.

**5.4 (P2 Major) Buys are proposed before exits, in the same step.** Entry loop `:912`, exit loop
`:956`. On a rebalance session the book is fully invested, so at step 1 `avail_cash = engine.cash`
(`:915`) is only the ~5% buffer. Every buy is sized against pre-exit cash, the orders reach
`process_quote` at step 2, and the ledger refuses them for insufficient cash - logged as
`FILL_LEDGER_REJECTED` and cancelled (`paper_pilot.py:670`). It self-corrects at step 3 because
`current_held` is still 0, so the net effect is wasted steps and a misleading audit trail rather
than lost trades. On a slow or short session it would not self-correct.

**5.5 (P2 Major) A crash mid-loop still advances the portfolio and resets the rebalance clock.**
`:1104` is a bare `except Exception as err: logger.exception(...)`, after which control falls
through to `end_session` and `save_portfolio` with `rebalanced=rebalancing`. A session that raised
after the exits filled but before the buys did will persist a book that is half-liquidated **and**
write `sessions_since_rebalance = 0`, so the next rebalance is a full horizon away. The comment at
`:1118-1121` says the save is "written after reconciliation so a session that fails to reconcile
does not advance the portfolio" - but reconciliation failure sets `reconciliation.reconciled =
False` and is only *logged* (`:1146-1148`); the save has already happened at `:1134`. The stated
protection does not exist.

FINDING   A rebalance session where no name clears `score_threshold` liquidates the entire book; the screen had no threshold
FAMILY    State machine / assumption archaeology
REPRO     `python scratchpad/probe_claim5.py` - all 423 scores below 0.0715 gives `picks = ()`, sells = every holding, buys = none
OBSERVED  100% cash, full exit round trip paid, on a rule that appears nowhere in `screen_mizan_out_of_sample.py`
EXPECTED  Either hold the existing book when the selection is empty, or measure the go-to-cash rule before executing it
BLAST     The whole portfolio, on any rebalance session in a weak-score regime. Silent - the log prints "Mizan picks: 0 of 423" and nothing flags the liquidation
SEVERITY  **P1 Critical** (unmeasured rule moving the entire book; escalated because the report shows a normal session)

FINDING   Entry loop ungated, non-idempotent loops, buy-before-sell ordering, and a swallowed exception that still advances state
FAMILY    Concurrency and ordering / failure injection / the human path
REPRO     Read `run_paper_pilot_session.py:912-914`, `:956-957`, `:1104`, `:1134`
OBSERVED  4 further instances of "the guard is somewhere else, or absent"
EXPECTED  One explicit `rebalancing` gate covering both loops; order-aware idempotence; no state advance on a swallowed exception
BLAST     Duplicate orders daily; a crashed session silently resets the rebalance clock
SEVERITY  P2 Major

---

## Claim 6 - the extreme-row guard

**VERDICT: partly derived. The mechanism is correctly identified and the percentile figure is close
to right. The two sentences that make 25 sound *chosen by evidence rather than taste* are both
overstated, and one of them generalises from a single day. Separately, the guard's refusals are
invisible in the coverage report because the field that would carry them is never populated.**

The claim under test, `src/quant_system/execution/mizan_live_features.py:176-182`:

> Chosen from measurement, not taste. Across a live 499-name NIFTY 500 cross-section the largest
> standardized deviation per name has median 1.5, p90 2.1 and p99 7.0; the training partition's own
> p99.9 lands near 16. A limit of 25 sits clear of all of them. It is also insensitive: on the
> cross-section that motivated it, every limit from 25 to 200 refused exactly the same single name.

Measured against the real published store and the real model preprocessor
(`scratchpad/probe_claim6.py`, 1,015,831 rows):

```
published rows = 1,015,831   (19s)
  median     1.659
  p90        3.416
  p99        8.477
  p99.9     17.762   <- docstring says 'near 16'
  p99.99    61.276
  max     84130.693   at 2020-09-21 ROUTE via volume_zscore

  rows the guard would refuse at limit    10:    5,944  (0.5851%)
  rows the guard would refuse at limit    16:    1,296  (0.1276%)
  rows the guard would refuse at limit    25:      511  (0.0503%)
  rows the guard would refuse at limit    50:      147  (0.0145%)
  rows the guard would refuse at limit   100:       43  (0.0042%)
  rows the guard would refuse at limit   200:       10  (0.0010%)
```

### What holds

`p99.9 = 17.76` against "near 16" is close enough that the author clearly measured something real.
The mechanism story is also right: among the 511 rows above 25, **472 (92%) are bound by
`volume_zscore`**, exactly the unbounded heavy-tailed member the docstring blames. And the single
worst row in ten years of data is `ROUTE` on 2020-09-21 at **84,131 standard deviations** via
`volume_zscore` - which is a stronger argument for the guard's existence than the one given.

### What does not hold

**6.1 "A limit of 25 sits clear of all of them" - 511 training rows are above 25.** The model was
fitted on data that includes rows the execution guard now refuses, up to 84,131 sd. The guard is not
"clear of" the training distribution; it sits above its 99.9th percentile and cuts into its tail.
That is defensible policy, but the sentence claims the opposite of what the data says, and it is the
sentence that makes 25 look derived.

**6.2 "It is also insensitive: every limit from 25 to 200 refused exactly the same single name" -
true for one day, false on 17% of days.** (`scratchpad/probe_claim6b.py`):

```
dates in store: 2427
  limit   25: refuses   511 rows on   421 dates (17.35% of dates)
  limit   50: refuses   147 rows on   136 dates (5.60% of dates)
  limit  100: refuses    43 rows on    42 dates (1.73% of dates)
  limit  200: refuses    10 rows on    10 dates (0.41% of dates)

dates where limit 25 and limit 200 disagree: 411
```

**411 of 2,427 cross-sections would be refused differently at 25 than at 200 - a 51x difference in
total rows refused.** The insensitivity is a property of the one cross-section the author happened
to be looking at, restated as a property of the constant. This is the same error the repository's
own `20260822-NOTICE-dsr-two-point-boundary-crash.md` records being caught twice before: "Cite the
proportion and the mechanism, never a specific p". Here a single sampled day is cited as the
mechanism.

So: 25 is a percentile choice (roughly p99.95 of the training distribution) dressed as a robustness
result. It is not a statement about where the linear model stops working, and nothing measures that.
The honest version is "25 refuses about 0.05% of rows, of which 92% are volume spikes" - which
would be fine, and is not what is written.

### 6.3 (P2 Major) The refusal is invisible in the coverage report

`CrossSectionCoverage.skipped_extreme` (`mizan_live_features.py:55`) exists and is printed by
`summary()` (`:66`, `"{len(self.skipped_extreme)} extreme"`). It is **never assigned by any code**:

```
$ grep -rn "skipped_extreme" --include=*.py .
./src/quant_system/execution/mizan_live_features.py:55:    skipped_extreme: tuple[str, ...] = ()
./src/quant_system/execution/mizan_live_features.py:66:            f"{len(self.skipped_extreme)} extreme"
```

`build_live_cross_section` constructs the coverage at `:115-120` without it, and the runner calls
`refuse_extreme_rows` at `:674` *after* it has already logged
`"Mizan cross-section: %s" % coverage.summary()` at `:667`. So the session log always reports
`0 extreme`, and the coverage fraction the `MIN_CROSS_SECTION_COVERAGE` gate checks (`:668`) is
computed **before** any refusal. The docstring at `:200-203` argues a refusal is preferable to a clip
because "a refusal is visible in the coverage report". It is not in the coverage report. It appears
only as a `logger.warning` (`:692`), and the guarded coverage minimum never sees it.

FINDING   `CrossSectionCoverage.skipped_extreme` is never populated; the coverage gate runs before refusals
FAMILY    Operability / assumption archaeology
REPRO     `grep -rn "skipped_extreme" --include=*.py .` - two hits, neither an assignment
OBSERVED  Session log reports "0 extreme" regardless; `MIN_CROSS_SECTION_COVERAGE` is checked at `:668` before `refuse_extreme_rows` at `:674`
EXPECTED  Refusals counted in coverage, and the coverage minimum applied to the post-refusal cross-section
BLAST     Every session. A cross-section that loses names to the guard passes the coverage gate as if it had not
SEVERITY  P2 Major (escalated: silent, and it defeats the stated reason for preferring refusal over clipping)

FINDING   "insensitive: every limit from 25 to 200 refused exactly the same single name" generalises from one day
FAMILY    Assumption archaeology
REPRO     `python scratchpad/probe_claim6b.py` - 411 of 2,427 dates disagree between limit 25 and limit 200
OBSERVED  511 rows refused at 25 vs 10 at 200, a 51x difference
EXPECTED  The claim scoped to the day it was measured on, or measured at scale
BLAST     Any future agent re-tuning the constant on the strength of a stated robustness property that does not exist
SEVERITY  P3 Minor

---

## Claim 7 - equal-weight sizing

**VERDICT: DISPROVEN. Equal weighting is the right idea and it is a genuine improvement on the fixed
Rs 150,000 stake it replaced. But it is not faithful to the screen in five measurable ways, and one
of them recreates the exact failure the change was written to fix.**

The claim, `run_paper_pilot_session.py:720-724`:

> Equal-weight is the default because it is how the model was measured: the out-of-sample screen
> averaged the forward target across the selected top 20% (`statistics.fmean`), giving every chosen
> name the same weight. The previous fixed stake of Rs 150,000 per name meant 56 picks against
> Rs 1,000,000 filled only the first ~6 in rank order and left the other 50 unexpressed -- a
> concentrated bet on the head of a ranking, which nobody validated.

The screen's actual construction, `scripts/screen_mizan_out_of_sample.py:198-202`:

```python
scores.sort(key=lambda item: -item[0])
take = max(1, int(len(scores) * SELECTION_FRACTION))
selected.append(statistics.fmean([target for _, target in scores[:take]]))
equal_weight.append(statistics.fmean([target for _, target in scores]))
```

### 7.1 (P1 Critical) The sizing base is a constant, not the portfolio. The persistence commit broke it.

`run_paper_pilot_session.py:729-730`:

```python
usable = initial_cash * (Decimal("1") - Decimal(str(risk_limits.min_cash_buffer_pct)))
per_name_alloc = (usable / Decimal(len(mizan_picks))).quantize(_PAISA)
```

`initial_cash` is the CLI constant (`:493` default `Decimal("1000000.00")`, `:1380`
`Decimal(str(args.capital))`). It is **not** `portfolio.cash`, not `ledger_funding()`, and not
equity. Before `b3e626b5` that was harmless: every session started fresh, so `initial_cash` *was*
the equity. `b3e626b5` made the portfolio persist and did not change this line.

Consequence, in the direction that matters. Suppose the book is down 30% after some weeks - which
the model's own card considers ordinary, its recorded `total_return` being `-0.3157`. Equity is
700,000; `per_name_alloc` is still `950,000 / N`. The entry loop iterates `for sym in top_picks:`
(`:912`), and `select_top_fraction` returns names **strongest first** (`mizan_live_features.py:145`,
`key=lambda pair: (-pair[1], pair[0])`). The first names are funded, cash runs out, and the ledger
refuses the rest (`core/ledger.py:286-289`, cancelled at `paper_pilot.py:670`).

**That is "only the first ~N in rank order filled, the rest unexpressed - a concentrated bet on the
head of a ranking, which nobody validated" - the exact sentence written to describe the defect being
repaired.** The repair removed one route to it and left another open, reachable by nothing more
exotic than the portfolio losing money. In the opposite direction the book dilutes: at equity
2,000,000 the strategy still deploys only 950,000 and holds the rest idle, silently halving the
measured effect.

### 7.2 (P2 Major) A score threshold the screen never had

The screen applies **no score filter**. `take = max(1, int(len(scores) * 0.20))` and then
`fmean(scores[:take])` - every one of the top 20% is held, whatever its score. The live path adds
`score_threshold=float(model.config.score_threshold)` = `0.071454840454`
(`run_paper_pilot_session.py:707`), which can cut the selection to any size including zero (see
Claim 5.1). Live selects a subset of what the screen selected, on a criterion that was never
measured, so the two cannot be compared even in principle.

### 7.3 (P3 Minor) The count rounds the other way

Screen: `int(...)` truncates. Live: `math.ceil(round(fraction * population, 9))`
(`mizan_live_features.py:149`). Measured (`scratchpad/probe_claim5.py`):

```
   n=  50: screen takes   10, live takes   10
   n= 100: screen takes   20, live takes   20
   n= 423: screen takes   84, live takes   85  DIFFER
   n= 499: screen takes   99, live takes  100  DIFFER
   n= 500: screen takes  100, live takes  100
```

Both guarantee at least one name; they disagree whenever `0.2 * n` is not an integer, which is the
usual case for a real universe. The docstring at `mizan_live_features.py:132-134` justifies rounding
up on its own terms without noting the screen rounds down.

### 7.4 (P3 Minor) 95% invested against a 100%-invested measurement

`usable = initial_cash * (1 - min_cash_buffer_pct)` holds back 5%. The screen's `fmean` over the
selected targets is a fully-invested portfolio. Live returns are therefore 95% of the screened
construction plus whatever the idle 5% does, which is a systematic scale difference on every
reported figure. Disclosed in the log line at `:732-736`; not reconciled anywhere.

### 7.5 (P3 Minor) Integer share truncation is not equal weight

`qty = int(target_alloc / price)` (`:918`) truncates, so each name receives between
`target_alloc - price` and `target_alloc`. Names whose single share costs more than the allocation
are dropped entirely (`:919-927`). At `950,000 / 85 = Rs 11,176` per name, any NSE name above
Rs 11,176 disappears from the portfolio. The comment at `:920-921` acknowledges this
("under equal weight this is how a high-priced name drops out") - it is acknowledged, and it is
still a divergence from `fmean` over the top 20%.

### 7.6 (P2 Major) The screen measured a different model

The docstring cites `screen_mizan_out_of_sample.py` as the authority for how "the model" was
measured. That screen fits a ridge on **eight cross-sectionally rank-transformed features**
(`:54-63`, `_ranks()` applied to every column) trained on 43 governed names. The model that executes
is `MizanModel.default_model()` - **fifteen features, raw values standardized against stored
means/scales**, whose coefficients come from `model_1f936eadcb8d44154f28af13` /
`trial_mizan_h11_002` (`mizan_model.py:551-554`). Different feature set, different transform,
different fit, different training population. The sizing rule is inherited from a measurement of
something else.

FINDING   `per_name_alloc` is derived from a fixed nominal, not the persisted portfolio's equity
FAMILY    Money and counting / assumption archaeology
REPRO     `run_paper_pilot_session.py:729-730` uses `initial_cash`; nothing in the file makes it a function of `portfolio.cash` or equity
OBSERVED  A drawn-down book funds only the head of the ranking and cancels the tail; a grown book leaves capital idle
EXPECTED  Size against current equity, now that the portfolio persists
BLAST     Every rebalance after the first drawdown or gain. Recreates the concentration defect the change was written to remove, silently
SEVERITY  **P1 Critical** (wrong money; escalated because the failure presents as ordinary cancelled orders)

FINDING   Live selection adds a score threshold and rounds the count up; the screen did neither
FAMILY    Assumption archaeology
REPRO     `screen_mizan_out_of_sample.py:199-201` vs `run_paper_pilot_session.py:704-708` and `mizan_live_features.py:149-152`
OBSERVED  85 vs 84 names at n=423, plus an unmeasured score filter that can select zero
EXPECTED  The executed selection rule to be the measured one, or the divergence stated
BLAST     Every rebalance; makes live-vs-screen comparison invalid
SEVERITY  P2 Major

---

## Claim 8 - the autocrlf fix

**VERDICT: the fix works - reproduced. The verification claim is overstated: 264 tracked evidence
files are still CRLF in this working tree, differ byte-for-byte from their committed blobs, and
`git status` reports the tree clean. The new test cannot see them.**

### The fix is real. Reproduced.

`.gitattributes` ends with `data/evidence/** -text`, and it applies:

```
$ git config --get core.autocrlf
true
$ git check-attr -a -- data/evidence/market-cache/all-market-20160822-20260821/corporate-actions/nse-corporate-actions-COMMITTED.json
... text: unset
... eol: lf
$ git ls-files --eol data/evidence/ | awk '{print $3}' | sort | uniq -c
  16677 attr/-text
```

All 16,677 tracked evidence files carry `-text`. A real checkout cycle with `core.autocrlf=true`,
materialised through `git checkout-index --prefix=` into a scratch directory and hashed against the
blobs:

```
--- fresh checkout (autocrlf=true, current .gitattributes) vs blob ---
  CLEAN  data/evidence/feature-store/mizan/mizan_feature_store_metadata.json
  CLEAN  data/evidence/feature-store/feature_store_metadata.json
  CLEAN  data/evidence/market-cache/all-market-20160822-20260821/corporate-actions/nse-corporate-actions-COMMITTED.json
```

A fresh clone on Windows today gets byte-exact evidence. The diagnosis was right and the remedy
works. `tests/test_committed_evidence_integrity.py` passes:

```
$ .venv/Scripts/python.exe -m pytest tests/test_committed_evidence_integrity.py -q
tests\test_committed_evidence_integrity.py ...                           [100%]
============================== 3 passed in 2.55s ==============================
```

### What was not verified: this working tree was never cleaned

`git ls-files --eol` over `data/evidence/`, at HEAD `c5593cae`:

```
$ git ls-files --eol data/evidence/ | awk '{print $1, $2}' | sort | uniq -c | sort -rn
   8669 i/lf w/lf
   4335 i/-text w/-text
   3409 i/none w/none
    264 i/lf w/crlf        <-- index says LF, working tree holds CRLF
```

**264 tracked files are CRLF on disk against an LF blob.** Byte-checked, not inferred:

```
data/evidence/feature-store/feature_analysis_summary.json
   worktree sha=04d24b65a6d746e4c774d8bab9182ec02efa59e6bfb582a55f1456b88dae16b1 size=16488
   blob     sha=98657b639406619f804ea24354d6b3bad842a68b2ef0408374cea7ad4b7f7eda size=15892
   MATCH=NO
data/evidence/feature-store/feature_store_metadata.json
   worktree sha=2a7665c97c20739731de54e741402569e2358a7eb657b43759b6cd68851c8710 size=672
   blob     sha=446b22f1e1f55418464dd816c70e9517c47e00810ea46a37f54c1f6408664216 size=641
   MATCH=NO
data/evidence/feature-store/mizan/mizan_feature_store_metadata.json
   worktree sha=01a42e8151db4c197d80e723d74fe316c18d6f5a17f1c91fa5678f5872c96d20 size=783
   blob     sha=3bc29d3f30dadfdb884ef511a8f86b0ee2849838b30a2f456a0a7e9289fe670a size=756
   MATCH=NO
```

And `git status --short -- data/evidence` prints **nothing**. It is clean because the index's cached
stat matches the converted file on disk; git will not re-hash until an mtime change. The corruption
is present and invisible to the tool that would normally show it.

Where they are:

```
    201 data/evidence/market-cache/nse-delivery-20160822-20260821
     51 data/evidence/market-cache/intraday-liquid-20230822-20260821
      5 data/evidence/market-cache/macro-regimes-20160822-20260821
      3 data/evidence/market-analysis
      3 data/evidence/feature-store
      1 data/evidence/feature-store/mizan
```

Two things make this worse than a cosmetic residue.

**Five of them are the macro inputs the live path reads.** `macro_INDIAVIX.json`,
`macro_NIFTY50.json`, `macro_NIFTYBANK.json`, `macro_NIFTYIT.json`, `macro_regimes_summary.json`
are all in the CRLF set. `run_paper_pilot_session.py` loads India VIX and NIFTY from that directory
for every session's features. JSON parses regardless, so no value changes - but the bytes the
running system reads are not the bytes the repository committed, which is exactly the property an
evidence store exists to provide.

**The daily automation will commit them.** `scripts/daily_auto_sync.ps1:48` runs `git add -A` and
`:55` commits. With `-text` now in force there is no check-in conversion, so the first operation
that touches any of these 264 files (a rebase, a `checkout`, a `stash`, an editor save) makes git
re-hash it and the next unattended sync commits the CRLF version into the repository. The commit
that fixed the attribute set up the conditions for the corruption to be committed rather than
merely to be present.

### The new test cannot catch this

`tests/test_committed_evidence_integrity.py:52-66` checks `git ls-files data/evidence/**/COMMITTED`
for `\r`. **Zero of the 264 are COMMITTED markers** (`grep -c COMMITTED` over the list returns 0),
so the test passes. Its docstring says "the byte-level test below is what gives repository-wide
coverage" - the coverage is over markers only, not over resource payloads or cache files. The third
test opens exactly one store, `data/evidence/models/mizan-v1`, and none of the market caches the
whole training and execution path depends on.

The commit message claims "the affected markers were restored from their blobs and both caches
verify 499/499 and 50/50 clean". That is literally true - *markers* were restored, and the two named
caches do verify. It is the scope that is overstated: the claim reads as "the evidence stores are
clean" and 264 tracked evidence files are not.

FINDING   264 tracked files under `data/evidence/` are CRLF on disk against LF blobs; `git status` reports clean
FAMILY    Data integrity / operability
REPRO     `git ls-files --eol data/evidence/ | awk '$1=="i/lf" && $2=="w/crlf"' | wc -l` -> 264; byte hashes above
OBSERVED  Working-tree bytes differ from committed bytes for 264 evidence files, including all five macro inputs the live feature path reads
EXPECTED  The restore that fixed the COMMITTED markers extended to every file the old attributes had converted
BLAST     This install root. Silent. `scripts/daily_auto_sync.ps1:48` (`git add -A`) will commit the corrupted versions once anything touches them
SEVERITY  P2 Major (escalated from Minor: silent, and the guard test is scoped so it can never see it)

---

## Claim 9 - the scheduled runner's guards

**VERDICT: DISPROVEN. Three separate paths run a full session and write a plausible report without
tripping any guard, and the holiday guard is inverted - it lets the holiday through and blocks the
trading day after it.**

The guards under test, `scripts/run_scheduled_paper_session.py:161-184`, and the claim at `:11-13`:

> **Today must be a trading day.** This repository holds no NSE holiday calendar, so that cannot be
> asserted in advance. It is inferred after the fact: if the provider has no bar for the previous
> session, or the refresh returns nothing new, the run stops.

### 9.1 (P1 Critical) The holiday inference is off by one session, in both directions

The pre-open run on day D refreshes to `to_day = D - 1 calendar day` (`:169`), so it always pulls
**the previous trading session's bar, which the previous run had not yet seen**. On the first
holiday after a trading day the refresh therefore does advance, and `after <= before` is false.

Replayed over one week with a Wednesday NSE holiday, using the runner's exact guard sequence and an
honest provider that has bars only on trading days (`scratchpad/probe_claim9.py`):

```
    run date  day  trading?       before       to_day        after  verdict
  2026-09-04  Fri   TRADING   2026-09-02   2026-09-03   2026-09-03  *** SESSION RUNS AND TRADES ***
  2026-09-05  Sat   weekend            -            -            -  exit 2 (weekend)
  2026-09-06  Sun   weekend            -            -            -  exit 2 (weekend)
  2026-09-07  Mon   TRADING   2026-09-03   2026-09-06   2026-09-04  *** SESSION RUNS AND TRADES ***
  2026-09-08  Tue   TRADING   2026-09-04   2026-09-07   2026-09-07  *** SESSION RUNS AND TRADES ***
  2026-09-09  Wed   HOLIDAY   2026-09-07   2026-09-08   2026-09-08  *** SESSION RUNS AND TRADES ***   <== TRADES ON A CLOSED MARKET
  2026-09-10  Thu   TRADING   2026-09-08   2026-09-09   2026-09-08  exit 4 (bars did not advance)   <== SKIPS A REAL TRADING DAY
  2026-09-11  Fri   TRADING   2026-09-08   2026-09-10   2026-09-10  *** SESSION RUNS AND TRADES ***
```

Two wrong outcomes from one off-by-one:

- **The holiday session runs.** `enforce_market_hours=False` (`run_paper_pilot_session.py:747`), and
  the order book is synthesised from whatever `fetch_upstox_live_quotes` returns - on a closed
  market, the previous close. So the session fills orders at stale prices, charges real statutory
  fees, writes a full markdown report, and advances the portfolio and the rebalance clock. Nothing
  in the report says the market was shut.
- **The day after every holiday is refused.** On Thursday the last completed session genuinely is
  Tuesday, so a session is legitimate; the guard reads the unchanged bar date and logs
  "treating today as non-trading". A real trading day is silently skipped, and per Claim 4 the
  rebalance clock does not advance either, so the hold stretches further.

The guard only fires on the **second** consecutive non-trading weekday. It has the semantics of
"did the previous calendar day trade?", not "does today trade?", and those differ on exactly the
days that matter.

### 9.2 (P1 Critical) `--skip-refresh` disables guards 3, 4 and 5 and still trades

`:168` - `if not args.skip_refresh:` wraps every one of the empty-cache, bars-not-advancing and
macro-coverage checks. The flag's help text is "use the cache as-is; for rehearsing the wiring
outside market hours" (`:155`), but the branch it skips is the only thing distinguishing a rehearsal
from a session. With it set, the runner goes straight to `run_paper_pilot_session.py --realtime`
(`:186-200`), which fetches live quotes, submits orders, fills them, persists
`logs/paper_runs/portfolio_state.json`, and writes
`logs/paper_runs/paper_session_<date>_<id>.md` - identical in every respect to a guarded run. A
rehearsal on week-old bars is indistinguishable from a real session in the artifacts it leaves,
and it advances `sessions_completed` and `sessions_since_rebalance` permanently.

### 9.3 (P2 Major) A failed reconciliation prints SUCCESS and exits 0

`run_paper_pilot_session.py:1389-1398`:

```python
rec_str = "PASS" if res["reconciliation"]["reconciled"] else "FAIL"
print(f"\n[PAPER PILOT SUCCESS] Session {res['session_id']} completed successfully.")
...
print(f"Reconciliation: {rec_str} (0.00 Paisa Discrepancy)")
...
return 0
```

The banner says SUCCESS unconditionally, the exit code is 0 unconditionally, and
`"(0.00 Paisa Discrepancy)"` is **hardcoded text printed next to a `FAIL` verdict**. The scheduled
runner returns `completed.returncode` (`:202`), so an unattended scheduler sees a clean 0 for a
session whose penny-exact reconciliation failed. Combined with the loop's blanket
`except Exception` (`:1104`), a session that crashed halfway also exits 0.

### 9.4 (P2 Major) `newest_cached_bar_date()` is a global max over a partially-refreshed store

`:55-60` takes the maximum `records[-1].exchange_date` across **all** datasets in the refresh cache.
If the ingester advances one symbol and rate-limits on the other 499, `after > before` and guard 4
passes. Downstream, `_require_one_decision_date` (`mizan_live_features.py:156-173`) does catch the
mixed dates and raises, so this degrades to a loud crash rather than a wrong report. But the guard
that exists to detect a failed refresh cannot detect a 499/500 failed refresh, and the thing that
does is in another module and was written for a different purpose.

### 9.5 (P2 Major) There is no alarm for absence of signal

Nothing detects that the scheduled job did not run at all. `logs/paper_runs/portfolio_state.json`
carries `sessions_completed` and `last_rebalance_on`, and neither is compared against a calendar by
anything. A machine that was asleep for a week resumes as if nothing happened, and per Claim 4 the
rebalance clock counts *sessions the runner completed*, not sessions the exchange held, so missed
days silently lengthen every hold.

FINDING   The holiday guard runs the session on the holiday and blocks the trading day after it
FAMILY    State machine / scale
REPRO     `python scratchpad/probe_claim9.py` - table above, Wed 2026-09-09 runs, Thu 2026-09-10 exits 4
OBSERVED  A full session trades and reports on a closed market at stale prices; a real trading day is skipped
EXPECTED  A holiday refused, and the day after a holiday allowed
BLAST     Every NSE holiday (roughly 15 a year) plus the trading day after each. Silent - the holiday report looks normal
SEVERITY  **P1 Critical** (fabricated session on a closed market plus a missed real session; escalated because both are silent)

FINDING   `--skip-refresh` bypasses all three data guards and still trades and persists state
FAMILY    Assumption archaeology / operability
REPRO     `run_scheduled_paper_session.py:168` gates the entire guard block on `not args.skip_refresh`
OBSERVED  A rehearsal writes a real session report, real fills, and a permanently advanced portfolio
EXPECTED  A rehearsal that cannot trade, or artifacts marked as a rehearsal
BLAST     Any operator following the flag's own help text
SEVERITY  **P1 Critical** (unrecoverable state advance from a documented rehearsal path)

FINDING   SUCCESS banner and exit 0 on a failed reconciliation, with a hardcoded "0.00 Paisa Discrepancy"
FAMILY    Operability
REPRO     Read `run_paper_pilot_session.py:1389-1398`
OBSERVED  `Reconciliation: FAIL (0.00 Paisa Discrepancy)` printed under `[PAPER PILOT SUCCESS]`, exit 0
EXPECTED  Non-zero exit and no success banner when `reconciled` is false; the discrepancy printed, not asserted
BLAST     Every unattended run. The one number the reconciliation exists to produce is a string literal
SEVERITY  P2 Major

---

## Claim 10 - anything overstated and not caught

**VERDICT: yes. Four more, and the first is the largest single finding in this report. Also, three
of the author's claims survived attack and are recorded as verified.**

Baseline first, so nothing below is confused with a broken repository:

```
$ .venv/Scripts/python.exe -m ruff check .
All checks passed!
$ .venv/Scripts/python.exe -m mypy src
Success: no issues found in 140 source files
$ .venv/Scripts/python.exe -m pytest -q
================= 1104 passed, 1 warning in 65.90s (0:01:05) ==================
```

**Everything in this report is invisible to all three gates.**

### 10.1 (P1 Critical) A RESEARCH_ONLY model executes daily, and three docstrings say it cannot

`MizanModel.default_model()` (`modeling/mizan_model.py:548-558`) returns a card carrying
`verdict: RESEARCH_ONLY`, `sharpe_ratio: -0.4108`, `total_return: -0.3157`,
`deflated_sharpe_ratio: 0.1760` against a 0.95 gate. Its own docstring:

> Enforcement lives at the execution boundary, so this model is legitimate for research, packaging
> and backtesting **and is refused for execution.**

Two more places state the same guarantee:

- `execution/governed_strategy.py:107-108` - "REJECT and RESEARCH_ONLY appear nowhere, so they
  cannot execute anywhere."
- `execution/cross_sectional_strategy.py:24-25` - "``RESEARCH_ONLY`` and ``REJECT`` execute on no
  surface, here as everywhere."

**The surface that actually trades never reaches any of those gates.**
`scripts/run_paper_pilot_session.py:56` imports `MizanModel` directly, `:610` calls
`MizanModel.default_model()`, and `:697` calls `model.predict_scores(...)`. It imports no strategy
class at all - the only execution import is `mizan_live_features` (`:316`). The verdict gate lives
in `SURFACE_ALLOWED_VERDICTS` inside `GovernedModelStrategy` / `CrossSectionalModelStrategy`, and
neither is on the path.

`CrossSectionalModelStrategy` - the headline deliverable of commit `c5143c90` - has **zero
production callers**:

```
$ grep -rn "CrossSectionalModelStrategy(" --include=*.py .
./src/quant_system/execution/cross_sectional_strategy.py:340:class CrossSectionalModelStrategy(BaseStrategy):
./tests/test_cross_sectional_strategy.py:198:    return CrossSectionalModelStrategy(
./tests/test_cross_sectional_strategy.py:352:    strategy = CrossSectionalModelStrategy(_bundle(), ExecutionSurface.SHADOW, incomplete)
./tests/test_cross_sectional_strategy.py:364:    strategy = CrossSectionalModelStrategy(_bundle(), ExecutionSurface.SHADOW, reordered)
```

`GovernedModelStrategy` has exactly one, `scripts/run_governed_shadow_session.py:243` - the runner
that `agent_context/CURRENT.md` records as never having completed a session.

The `research_only = True` declaration on `strategies/mizan_strategy.py:47` is likewise irrelevant
here: the only thing that reads it is `realtime_shadow.py:260`, a different runner. The scheduled
paper path goes around the strategy layer entirely.

This is the identical shape of the defect `agent_context/CURRENT.md` records as closed at
`85ff535`: "The system that executed was not the system that was validated... every governed
guarantee in `.launch/` described code that no live path called." The governed cross-sectional
adapter was built, tested, and left unreachable, while the reachable path calls the model object
directly and no verdict is ever consulted.

### 10.2 (P1 Critical) The persistence commit made the total-drawdown kill switch inert

`run_paper_pilot_session.py:741` constructs `PreTradeRiskGovernor(limits=risk_limits)` with **no
`initial_equity`**, so `governor.py:26-28` sets both `_daily_peak_equity` and
`_all_time_peak_equity` to `Decimal("0.00")`. `evaluate_order` calls `update_peaks(current_equity)`
on its first invocation, so the "all-time" peak becomes **this session's** first observed equity and
rises only within the session. Nothing calls `restore_state`:

```
$ grep -rn "restore_state" --include=*.py scripts/ src/quant_system/execution/paper_pilot.py
(no matches)
```

Before `b3e626b5` the portfolio was rebuilt from `initial_cash` every day, so "session peak" and
"all-time peak" were the same thing and `max_total_drawdown_pct` was meaningful. Now the portfolio
persists and the governor does not. A book that declines 30% over six weeks trips nothing:
`_all_time_peak_equity` resets each morning to that morning's equity, so `total_dd` is measured
against a high-water mark that follows the decline down.

`max_total_drawdown_pct=0.12` (`:604`) and `0.08` on the sprint profile (`:605`) are therefore
duplicates of the daily limit. The model's own card names `max_drawdown_limit: "0.15"` and its own
recorded `total_return` is `-0.3157` - precisely the scenario the switch is named for, and precisely
the one it cannot see. The dashboard reports the limits as if they were live
(`run_paper_pilot_session.py:1088-1091`).

### 10.3 (P2 Major) `model_card_hash` is not reproducible, and is served as an identity

`mizan_model.py:282` - `created_at: str = field(default_factory=lambda: utc_text(datetime.now(UTC)))`
- and `:304-319` folds `created_at` into the payload that becomes `model_card_hash`. Two calls, ten
milliseconds apart:

```
created_at A: 2026-08-29T23:09:31.979162Z
created_at B: 2026-08-29T23:09:31.989877Z
hash A      : 844ff144bae73ac8b525493f9258fc313e9423a4c304c91764739c82081d8ad7
hash B      : 4df5a0b280b6172bc4bec586d116024029b6703ddf24a5ee1db1b4660374ced8
STABLE      : False
```

The same weights produce a different card hash every time the process starts. It is surfaced as an
identifier by `server/app.py:617` (an HTTP response field, `schemas.py:556`) and by
`mizan_cli.py:156` (`"Model Card Hash    : ..."`). Two API calls to the same server return two
different hashes for the same model. Anything that recorded one to bind a decision to a model has
recorded a timestamp.

(This is specific to `MizanModelCard`. `ModelCardV1` in `promotion.py` hashes a stored
`_unsigned_dict()` and is not affected - `governed_strategy.py:182`'s "must re-derive" check is
sound.)

### 10.4 (P2 Major) The card's own operating limits are read by nothing

`MizanModelCard` declares `monitoring_limits = {"max_drawdown_limit": "0.15", "min_hit_rate": "0.48",
"staleness_bars_limit": "5"}` and `halt_and_rollback_policy = "Halt immediately if rolling Sharpe
breaches -1.5 or data freshness budget expires."` (`mizan_model.py:284-299`).

```
$ grep -rn "halt_and_rollback\|monitoring_limits\|max_drawdown_limit" --include=*.py scripts/ src/quant_system/execution/
scripts/run_governed_shadow_session.py:152:        monitoring_limits={...}
scripts/run_governed_shadow_session.py:153:        halt_and_rollback_policy="halt on monitoring breach; ..."
```

Both hits are the *shadow* runner writing a card, not any runner reading one. No rolling Sharpe is
computed anywhere in the paper path; no staleness budget is enforced; `min_hit_rate` is never
evaluated. The card documents an operating envelope that no code observes, and the paper path
carries its own unrelated `RiskLimits` literals instead (`:601-607`, `:611-617`).

### What survived attack, and is recorded as verified

- **`e18a0e0e`'s gate claims are true.** Ruff and mypy are clean at HEAD, on 140 source files.
- **`e18a0e0e`'s "data/universe.py is formatting only - AST verified identical" is true.** Checked
  independently: `ast.dump(ast.parse(before)) == ast.dump(ast.parse(after))` returns `True` across a
  586-line diff.
- **`7fb85e83`'s core claim is true.** The live path does compute its features through
  `modeling.mizan_features` rather than by hand, and the thirteen instrument-level features
  reproduce the published training store text-identically (Claim 2).

The residual on `e18a0e0e`: its own commit message says of the three runtime defects it fixed,
"None of the three had a test." The commit did not add one - `git show --stat` lists a single test
file touched, `tests/test_live_universe_robustness.py`, by 4 lines. All three would regress silently.

FINDING   A RESEARCH_ONLY model executes on the paper surface; the verdict gate is in a class with zero production callers
FAMILY    Identity and authorization / assumption archaeology
REPRO     `grep -rn "CrossSectionalModelStrategy(" --include=*.py .` - tests only; `run_paper_pilot_session.py:610,697` calls the model object directly
OBSERVED  Three docstrings assert RESEARCH_ONLY "cannot execute anywhere"; the one path that executes never consults a verdict
EXPECTED  The trading surface routed through the gated adapter, or the guarantee withdrawn from the docstrings
BLAST     Every scheduled session. The governance guarantee the repository most relies on is unenforced on its only live surface
SEVERITY  **P1 Critical** (security/governance bypass; escalated because three separate comments assert the opposite)

FINDING   The total-drawdown kill switch resets every session, so it cannot see a multi-session decline
FAMILY    State machine / money and counting
REPRO     `run_paper_pilot_session.py:741` omits `initial_equity`; no call to `restore_state` exists in `scripts/`
OBSERVED  `_all_time_peak_equity` starts at 0.00 each session and tracks only that session's high
EXPECTED  The peak persisted with the portfolio that `b3e626b5` made persistent
BLAST     Any sustained drawdown. The dashboard reports the limit as active. Silent
SEVERITY  **P1 Critical** (a risk control that reports itself as enforced and is not)

FINDING   `MizanModelCard.model_card_hash` changes on every construction and is served as an identity
FAMILY    Data integrity
REPRO     Construct `MizanModel.default_model().model_card` twice; hashes differ
OBSERVED  `created_at = datetime.now(UTC)` is inside the hashed payload (`mizan_model.py:282,307`)
EXPECTED  A hash over the model's content, or the field not presented as an identifier
BLAST     `server/app.py:617` API consumers, `mizan_cli.py:156`, and any record citing the hash
SEVERITY  P2 Major (escalated: silent, and it defeats the audit purpose of publishing a card hash)

---

## NOT PROBED

This is the most important section. Everything here is an unknown that stayed unknown, and none of
it may be read as passing.

**No live session was ever executed.** Every finding about
`scripts/run_paper_pilot_session.py` and `scripts/run_scheduled_paper_session.py` comes from reading
the code and from replaying its logic in isolated probes. I did not run a session, because
`--realtime` reaches the Upstox API with real credentials and because a run would write
`logs/paper_runs/portfolio_state.json` and mutate state I was told not to touch. Consequences:

- The end-to-end interaction of P1-3 (12-session hold), P1-4 (empty-selection liquidation),
  P1-5 (fixed sizing base) and P1-2 (inflated realized P&L) is unmeasured. They plausibly compound;
  I cannot say by how much.
- The buy-before-sell ordering (Claim 5.4) is argued from control flow. I did not observe an actual
  `FILL_LEDGER_REJECTED` audit event.
- Whether partial fills actually occur at the synthesised depth of 1,800 shares per name
  (`run_paper_pilot_session.py:853-864`) is unmeasured.

**No existing `logs/paper_runs/` artifact was inspected.** I did not open any session report,
`portfolio_state.json`, or `live_paper_status.json`, so I cannot say whether the defects above have
already produced wrong numbers in a report that exists on this machine. **This is the highest-value
next check and it is cheap**: read `logs/paper_runs/portfolio_state.json` and compare
`realized_pnl` and `sessions_since_rebalance` against the session reports beside it.

**The NSE holiday reproduction uses a synthetic calendar.** `scratchpad/probe_claim9.py` places a
holiday on Wednesday 2026-09-09 because the repository holds no NSE holiday calendar - which is the
same reason the guard is wrong. The *logic* is the runner's verbatim, but I have not confirmed a
specific real 2026 NSE holiday date. Confirm against the published NSE calendar before quoting a
date.

**Cross-platform float reproducibility is untested.** The kernel's `math.log`/`math.sqrt` are libm
calls. My fidelity check (Claim 2) ran on the same Windows ARM64 machine that built the store. CI
runs x86-64. A 1-ULP divergence is ~8 orders below the 10dp text quantum, so it can only bite at an
exact rounding boundary - but nothing measures it and the store cannot be rebuilt to check.

**The kernel fidelity check sampled 48 rows, not 1,015,831.** Three symbols (GRASIM, RELIANCE, TCS)
at 16 indices each. The rank sweep *was* exhaustive (all 1,015,831 rows); the instrument-feature
check was not. A symbol-specific divergence - a corporate action, a zero-volume day, a price of
exactly 0 - would not appear in this sample.

**`refuse_extreme_rows` was never exercised on a live cross-section.** Claim 6's numbers come from
the training store. The docstring's motivating example (BBTC on 2026-08-27, standardized 272) sits
in a live 499-name NIFTY 500 cross-section I could not reconstruct.

**Upstox behaviour on a closed market is assumed, not observed.** Claim 9.1 asserts the holiday
session fills at the previous close. That follows from `enforce_market_hours=False` and the book
being synthesised from whatever `fetch_upstox_live_quotes` returns, but I did not call the provider
on a holiday.

**The rest of `paper_pilot.py` (36 KB) was read only where the claims led.** `orderbook_sim.py`,
`replay_feed.py`, `realtime_shadow.py`, the server, the dashboard, and the AI assistant surfaces are
entirely unprobed. `server/app.py:617` was read for one line only.

**Concurrency was not probed at all.** Two scheduled sessions overlapping, two processes writing
`portfolio_state.json`, or a session running while `daily_auto_sync.ps1` commits, are all untested.
`save_portfolio` uses `write_text` + `replace` with no lock and no `fsync`; I did not attempt to
race it or to kill a process mid-write.

**Security surface: not probed.** No injection, SSRF, path traversal, upload, CORS, secrets-in-logs
or rate-limit testing was done. `fetch_upstox_live_quotes` and the token path were not examined. The
brief did not ask, and I did not volunteer.

**The 264 CRLF evidence files were spot-checked, not fully verified.** Three were byte-compared
against their blobs; the other 261 rest on `git ls-files --eol` reporting `i/lf w/crlf`. I did not
verify that every hash-enforced resource under a `/store/` directory still verifies, only that none
of the 264 lives in one.

**I did not attempt to reproduce the author's own measurements** in
`20260826-NOTICE-mizan-v3-reintroduces-window-dependence.md` (the 300-random-series RSI error
table). I checked the analytic backing and the real-data reproduction, not the simulation.

**Severity calls on money are mine, not measured against a live book.** P1-2's "on the order of
Rs 1,000 of phantom profit per rebalance cycle" is an arithmetic estimate from the repository's own
0.224% round-trip figure and a ~950,000 deployed book. The mechanism is proven exactly; the
magnitude is an estimate.
