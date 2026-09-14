# Corporate-action correctness: what was wrong, what was measured, what is still unresolved

**Headline: two defects were found and repaired, and the second one had already been shipped into
the adjustment code. Neither was visible to any gate — 28 unit tests, ruff and mypy all passed with
both defects present, because the tests encoded the same wrong premises as the code.**

**Then an independent adjudication found three more (2026-09-11), and the verification of *those*
repairs found the P1 fix incomplete (2026-09-14).** The same root cause runs through all three
rounds: the parser gates the guarantee, so anything it fails to recognise is invisible to the
guarantee and to the measurement of the guarantee at the same time. Start at
[Rights issues: the fail-closed rule, verified end to end](#rights-issues-the-fail-closed-rule-verified-end-to-end-2026-09-14)
for the current state of the rights path.

Reproduce with:

```bash
.venv/Scripts/python.exe scripts/validate_demerger_factors.py
```

```bash
.venv/Scripts/python.exe -m pytest tests/test_corporate_actions.py tests/test_adjustment_provenance.py tests/test_adjusted_label_economics.py -q
```

## Defect 1 — the gap-verification tolerance was blind for 27% of the corpus

The rule under repair applied a published structural ratio when
`|observed_gap − published_factor| ≤ 0.20` — an **absolute tolerance in factor space**.

That test has two hypotheses:

| Hypothesis | Predicted ex-date gap |
|---|---|
| Provider already applied the action | ≈ 1.0 |
| Provider did not apply it | ≈ published factor |

It cannot separate them whenever `|1 − factor| ≤ 0.40`, because a single observation satisfies both —
and it broke ties toward "not applied", **double-adjusting a series the provider had already fixed**.

Measured across the 423-name research universe against the all-market cache:

| | Count |
|---|---:|
| Published-ratio structural actions with a bar on their own ex-date | **212** |
| Of those, inside the blind band `\|1 − f\| ≤ 0.40` | **57 (27%)** |
| Kind of every one of those 57 | bonus — 1:10, 1:5, 1:4, 1:3, 1:2 |

Affected names include ICICIBANK, NTPC, POWERGRID, GAIL, BEL, CONCOR, PFC, RECLTD, LT, IOC, HINDPETRO
and MOTHERSON. A double-applied 1:10 bonus rescales all prior history by 0.909 — a spurious +10% day,
and every trailing feature crossing it corrupted.

### The repair

Score both hypotheses in **log-return space** and take the nearer, subject to a residual bound. Log
space because returns compound multiplicatively: an absolute tolerance in factor space treats a
halving and a doubling as different sizes of event when they are the same size.

`MAX_LOG_RESIDUAL = 0.15` is calibrated from the corpus rather than chosen. Across all 212 actions the
largest `|ln(gap)|` is **0.1035** (ASTRAL, 2019-09-16), so 0.15 admits every one with margin while
still excluding a 1:10 bonus that had genuinely not been applied (`|ln(0.9091)| = 0.0953` away).

Under the repaired rule all **212 of 212** resolve to `ALREADY_APPLIED`, unanimously.

### Mutation-verified

Reinstating the historical absolute-tolerance rule fails exactly the tests that encode the defect:

```text
FAILED test_a_bonus_the_provider_already_applied_is_not_applied_a_second_time[Bonus 1:10-...]
FAILED test_a_bonus_the_provider_already_applied_is_not_applied_a_second_time[Bonus 1:5-...]
FAILED test_a_gap_matching_neither_hypothesis_is_unresolved_not_forced
```

## Defect 2 — gap inference for demergers had to be removed, not tuned

The brief was explicit: *"A price gap alone is not proof of the adjustment amount; genuine market
movement must not disappear."* On this corpus that is not a theoretical concern.

Of **54** ratio-less actions with a measurable ex-date gap, the previous 20%-threshold rule would have
fired on three with **positive** gaps:

| Symbol | Ex-date | Gap | Market median that day | Factor the old rule would have applied |
|---|---|---:|---:|---:|
| NMDC | 2022-10-27 | **+71.04%** | +0.49% | 1.7104 — scaling six years of history *up* by 71% |
| BAJAJELEC | 2023-09-14 | +32.21% | +0.70% | 1.3221 |
| SCI | 2023-03-31 | +30.00% | +1.06% | 1.3000 |

A demerger cannot raise the parent's price. Those gaps are market movement or a provider adjustment,
and dividing them out would have erased a genuine move **and** invented a fake one in its place.

### The repair

`build_adjustment_factors` no longer sizes a ratio-less action from price at all. It reports it as
`UNRESOLVED`, and every feature window and label window spanning one is dropped rather than measured.
A factor may still be *supplied* by a caller that established it from evidence outside the gap.

## Independent validation: attempted, and it produced zero factors

`scripts/validate_demerger_factors.py` checks value continuity against the **resulting company's own
first traded price** — a second instrument, independent of the parent's gap:

```text
parent_close_cum  ≈  parent_open_ex  +  ratio × resulting_first_open
```

The ratio is an input from the issuer filing (`data/authorities/nse-demerger-entitlements.json`),
never an inference.

| Outcome | Count |
|---|---:|
| Ratio-less actions examined | 54 |
| **Independently validated** | **0** |
| Refused — `NO_FILING_RATIO` | 54 |
| Refused — `NO_EX_DATE_BAR` | 2 |

**Zero validated is the correct result, not a failure of the tool.** Entitlement ratios are legal
facts published by issuers, and this repository holds one such filing. Filling in the other 53
requires a human reading 53 filings; until then those windows stay refused, which costs a handful of
observations and keeps the dataset honest.

### The market control, and what it shows

Every ex-date gap is reported next to the same-day cross-sectional median move, so the part of the
gap that is market movement stays visible instead of being absorbed:

| Symbol | Ex-date | Gap | Market median | Excess |
|---|---|---:|---:|---:|
| NIITLTD | 2023-06-08 | −77.27% | −0.60% | −76.67% |
| ALLCARGO | 2025-11-12 | −68.70% | +0.50% | −69.21% |
| SIEMENS | 2025-04-07 | −50.29% | **−3.72%** | −46.57% |
| NMDC | 2022-10-27 | **+71.04%** | +0.49% | +70.55% |

SIEMENS is the instructive one: 3.7 percentage points of its 50.3% gap were the market, not the
entitlement. Inferring a factor from the raw gap would have absorbed a real market move into a
"corporate action".

## HEG: an unpriced entitlement, and why that is the honest answer

HEG's demerger has ex-date and record date **2026-09-07**. This cache's `received_end` is
**2026-08-21**. The resulting company has **no price anywhere in this repository**.

The validator returns `NO_EX_DATE_BAR` for it. That refusal is the point: it is what lets the
XS-Monthly book disclose an **unpriced asset** rather than book either the full −64.3% quote drop as a
loss or an invented recovery. The entitlement is recorded in the authority file with the filing cited
and a note that the ratio must be re-verified against the issuer's own disclosure — the issuer site
returned HTTP 403 on direct retrieval, so the cited source is a reproduction.

## The discovery worklist, and its honest limits

For each unresolved action the tool shortlists candidate resulting companies — instruments that first
traded within 60 days of the ex-date — ranked so a human has a reading list rather than 54 blind
filings. 44 of 54 actions have a shortlist.

**The price-fit ranking alone is close to useless, and this was measured rather than assumed.**
Ranking candidates by how well their first traded price implies a clean entitlement ratio gives a
**false-discovery rate of 8.51%**: 178 of 2,091 candidate/action pairs clear the tolerance. Ten clean
ratios each with an 8% window cover about that much of the plausible price range.

The concrete failure: for ABFRL's 2025-05-22 demerger the **correct** resulting company (ABLBL,
implied 1.0237) ranked **fourth**, behind SILKY (0.9997) — an unrelated listing that happened to fit
better. ARVIND's top price-fit candidate was an **ETF**.

So the shortlist is ordered by **shared name stem** first, with the price fit only breaking ties. A
demerged entity usually keeps the parent's brand — SKFINDIA → SKFINDUS, ABFRL → ABLBL — and an
unrelated IPO in the same window shares nothing. That is a genuine discriminator where the price fit
is not.

**It remains discovery, not validation.** A name match is a lead. The ratio is still a legal fact in
the filing, and nothing in the worklist writes a factor.

## The issuer's own filing names the resulting company — 17 of 56 actions

`scripts/fetch_demerger_announcements.py` replaces the name-stem heuristic above with a **citation**.
An Indian scheme of arrangement labels its parties in the filing text itself, and NSE's
corporate-announcements API returns that text:

```text
Scheme of Arrangement between SKF India Limited ("Demerged Company") and
SKF India (Industrial) Limited ("Resulting Company")
```

```bash
.venv/Scripts/python.exe scripts/fetch_demerger_announcements.py
```

Output: `reports/corporate_action_validation/demerger-resulting-companies.json`.

| | Count |
|---|---:|
| Unresolved actions searched | 56 |
| Distinct issuers queried (0 fetch failures) | 49 |
| **Resulting company named by the issuer** | **17** |
| Of those, carrying a qualifying flag | 1 |
| Matches found but rejected as unusable | 4 |
| Named actions carrying a filing attachment URL | 17 |

The 17: AARTIIND → Aarti Pharmalabs, ABFRL → Aditya Birla Lifestyle Brands, ANANTRAJ → Anant Raj
Global, BAJAJELEC → Bajel Projects, BEML → BEML Land Assets, GHCL → GHCL Textiles, HEG → HEG
Graphite, NMDC → NMDC Steel, PRAKASH → Prakash Pipes, RAYMOND → Raymond Lifestyle (2024 only), SCI →
*(truncated, flagged)*, SKFINDIA → SKF India (Industrial), STLTECH → STL Networks, SUNDARMFIN →
Sundaram Finance Holdings, TATACHEM → Tata Consumer Products, VAKRANGEE → VL E-Governance & IT
Solutions, VEDL → Vedanta Aluminium Metal.

**ABFRL is the one that matters**, because it is the case the name-stem worklist got *fourth*. The
issuer names Aditya Birla Lifestyle Brands Limited directly, which confirms the ABLBL lead and
retires SILKY — the unrelated listing whose price fit ranked first.

### Two rejected matches, and why rejecting them is the point

A wrong citation is worse than no citation, so a match that cannot be trusted is reported as
**unnamed** rather than as a name:

| Action | Flag | What the filing actually said |
|---|---|---|
| RELIANCE 2023-07-20 | `FILER_IS_RESULTING_COMPANY` | `Reliance Industries Limited ("Company" or "Resulting Company")` — RIL describing an **inbound merger in which it survives**, a different transaction that merely fell inside the ±540-day window |
| STAR 2024-12-06 | `BARE_SUFFIX_NO_NAME` | `allotment of Equity Shares by Onesource (Resulting Company)` — the filing used a short alias, so nothing citable remains |

RELIANCE is the instructive one: **the extraction was correct and the announcement was wrong.** No
better parsing fixes that, because the text genuinely names RIL as a Resulting Company — of another
scheme. It is detected by the filing's own alias: an Indian issuer calls itself "the Company", so a
Resulting Company aliased as bare `"Company"` *is* the filer.

That check first shipped anchored on quote characters and **silently never fired**. NSE's stored text
is mojibake — each smart quote arrives as three `U+FFFD` replacement characters — so the pattern
matched nothing and RELIANCE passed through named. It now matches on words.

### One flagged name

SCI 2023-03-31 returns `Land and Assets Limited` with `NAME_MAY_BE_TRUNCATED`. The filing reads
`Shipping Corporation of india Land and Assets Limited` — the issuer typed **india** in lower case,
which reads to the parser as a connective and cuts the name in half. It is flagged by testing the
stopping word against the filing's own *demerged* company name, and **not repaired**: a guessed
repair is exactly the failure this work exists to prevent.

### This still does not supply a single ratio

Checked across SKFINDIA, ABFRL and RAYMOND — 4,073 announcements — **zero** ratio patterns appear in
any API text field. The entitlement ratio lives in the PDF attachment. Parsing 53 PDFs to extract it
would produce *validated-looking* factors that are wrong wherever the parse slipped, which is worse
than the current refusal. So the attachment URL is recorded for a human and **nothing here writes a
factor**.

What changed is the size of the human job: from "identify the company, then find the ratio" to
"confirm the ratio" for 17 of 56 actions. The other 39 are unchanged.

## Independently adjudicated 2026-09-11, verdict BLOCKED — three defects, all now repaired

`.launch/reports/ADJUDICATION-CORPORATE-ACTIONS-20260911.md`, by a third agent that authored none of
this code and was instructed to verify from the data rather than from any record. Brief:
`.launch/ADJUDICATION-BRIEF-CORPORATE-ACTIONS.md`.

**28 of 33 claims PROVEN, 2 DISPROVEN, 1 partially disproven, 2 NOT TESTED. Final verdict BLOCKED.**

The load-bearing claim held under independent re-measurement: scanning the raw cache with its own
regexes and its own log arithmetic, the adjudicator got **212 of 212 `ALREADY_APPLIED`**, largest
`|ln(gap)|` 0.1035 (ASTRAL 2019-09-16) — and corroborated it from the other end, finding the
production feature store applied **4,590 factors, every one a dividend**. It also recomputed **8,714
committed manifest hashes**: 8,714 match, 0 mismatch. Both A/B arms reproduced byte-identically.

### The root cause it found, which neither author could see

**The parser is simultaneously the denominator of the "212 of 212" measurement and the gate of the
"unresolved windows are refused" guarantee.** So an action the parser does not recognise is invisible
to both at once: it never enters the denominator, and it never becomes unresolved. That is the third
shared premise, and it is structural rather than a typo.

| Defect | Severity | What it was |
|---|---|---|
| **1. Rights issues published a fabricated return** | P1 | A rights record matched *no* hint, so it produced no factor **and** no unresolved record. `spans_unresolved` returned `False` and the ex-rights gap was published as a real return. **39** in the research universe. Reproduced on HCC 2025-12-05, gap **-22.94%** |
| **2. 9.7% of dividends silently unpriced** | P2 | `_DIVIDEND_RE` rejected the `/-` suffix that `_SPLIT_RE` two lines above already allowed, so `Dividend - Rs 4/- Per Share` parsed to nothing. **493 of 5,083** records; max unremoved payout 6.23% of cum close |
| **3. One wrong issuer citation** | P3 | RAYMOND 2025-05-14 was named from filings dated 2024-06-30 and 2024-07-10 — the *same two* the 2024-07-11 row cites. The 2025 action is the Raymond **Realty** demerger |

### And the test suite was certifying defect 1 as correct

The adjudicator's mutation testing killed 27 of 32 mutants; **5 survived all 1,477 tests**. Worse,
when defect 1 was repaired an existing test *failed* — because `"Rights"` sat in a list named
`test_actions_with_no_price_effect_produce_no_factor`, asserting `needs_inference is False`.

**The suite did not merely miss the defect; it asserted the defect was the requirement.** The premise
is plainly false — a discounted rights issue dilutes, and the theoretical ex-rights price sits below
the cum price. This is the concrete answer to "do the tests encode the same premises as the code?"

### Repairs

All three are fixed, and the fix for 1 is a **fail-closed rule rather than a new parser**: a
structural action that is *recognised but not sized* is now reported unresolved, so every window
crossing it is refused.

```python
structural_hinted = bool(
    _SPLIT_HINT.search(subject)
    or _BONUS_HINT.search(subject)
    or _RIGHTS_HINT.search(subject)
    or _RATIOLESS_HINT.search(subject)
)
structural_sized = any(kind in _STRUCTURAL_KINDS for kind in kinds)
needs_inference = structural_hinted and not structural_sized
```

That also closes a second hole in the same line: the old rule used `not kinds`, so a record carrying
a dividend *and* a demerger priced the dividend and declared the demerger resolved. Buybacks are
deliberately **not** swept in — a tender offer has a record date but no ex-date adjustment, and
refusing 140 windows for it would be a cost with no benefit.

> **Superseded 2026-09-14.** The rule above is kept because the paragraphs around it describe it, but
> it is no longer what the code does: it asks one question about the whole subject line, so any one
> sized component vouches for every other. See
> [Rights issues: the fail-closed rule, verified end to end](#rights-issues-the-fail-closed-rule-verified-end-to-end-2026-09-14)
> below for the per-component rule that replaced it and the measurement that no published number
> moved.

Defect 3 is fixed by arbitration rather than by narrowing the window: when two ex-dates of one issuer
cite the same filing, the row whose ex-date most closely *follows* the announcement keeps it and the
others are blocked as `FILING_BELONGS_TO_ANOTHER_EX_DATE`. That is the temporal structure of a
scheme, not a guess.

New regression tests pin all three, each citing the real case it came from.

**The repairs themselves are unadjudicated.** They were written by an author of the original code,
which is exactly the arrangement the adjudication existed to correct. A further pass should confirm
them.

### What the repairs change in the data, measured

Re-measured independently against the all-market corporate-action store (423 universe symbols,
6,384 records, 5,083 of them dividend-bearing):

| | Before | After |
|---|---:|---:|
| Dividend records left unpriced | 493 (9.7%) | **52 (1.0%)** |
| Actions reported unresolved that were silently ignored | 0 | **43** (40 rights across 34 symbols, 3 bonuses) |

The first repair needed a second pass. Fixing the `/-` suffix alone recovered 331 of the 493; the
rest use the abbreviated `Per Sh` spelling. The remaining 52 are records like `Interim Dividend` that
state **no amount at all** — left unpriced deliberately, because guessing one fabricates a return.

**And the suffix fix introduced a misprice before it was caught.** Accepting `/-` made
`Dividend/Face Value Split From Rs 10/- Per Share To Rs 2/- Per Share` read the split's *face value*
as a Rs 10 dividend that does not exist. The old regex had avoided this only by accident, by
rejecting the `/-` form entirely. Amounts falling inside the split match are now skipped, and a
regression test pins both halves. It was caught by re-measuring the repair on the real corpus, not by
the suite — the same lesson as the defect it was repairing.

### Consequence: the feature store and the A/B are stale

`mizan-adjusted-v1` was built with the defective parser. The adjudicator measured it as applying
**4,590 factors, every one a dividend** — so it is missing up to 441 dividend adjustments and it
never refused the 40 rights windows.

**The published A/B figures were computed on that data.** The expectation recorded here was: no
change to the conclusion, because a dividend add-back lifts the model and its benchmark together and
cancels in the *selection edge*, and 40 refused windows out of ~900,000 rows is immaterial.

**That has now been rerun, and the expectation held.** `data/evidence/feature-store/mizan-adjusted-v2`
was built from the identical authority (`e68c8e1c…`) with only the parser repaired — 5,028 factors
(+438), 99 unresolved actions (+43), 4,905 blacked-out rows. Full result:
[`reports/mizan_ab_screen_v2/README.md`](../mizan_ab_screen_v2/README.md).

| | Arm A RAW (control) | Arm B v1 | Arm B **v2** |
|---|---:|---:|---:|
| Selection edge | -0.000022 | -0.000185 | **-0.000236** |
| t | -0.07 | -0.66 | **-0.86** |
| Windows refused | 0 | 532 | **962** |

**Arm A reproduces to the digit** (-0.000022, t -0.07, 902,582 rows), which proves the repairs did not
disturb the harness — every Arm B difference is the data. The edge stays negative and insignificant,
equal-weight still wins, and all eight coefficient signs are preserved. `mizan-adjusted-v1` is
retained rather than overwritten.

**The six short-horizon trials and the governed retrain still read v1 and were deliberately not
rerun** — the ledger declared six trials and six are spent, so re-running on corrected data is a new
experiment with a fresh ordinal rather than a refresh.

## Rights issues: the fail-closed rule, verified end to end (2026-09-14)

Adjudication **DEFECT-1 (P1)** was repaired at `c01cb89c` by an author of the original code, and the
adjudication's own closing note said so: *"The repairs themselves are unadjudicated."* This section
is the verification pass, by a session that wrote none of that repair. It re-measured the claim from
the committed corpus rather than from the record, found the repair sound but its rule incomplete, and
closed the remainder.

Reproduce with:

```bash
.venv/Scripts/python.exe -m pytest tests/test_corporate_actions.py -q
```

### The four adjudicated reproductions, re-run against the real cache

Through the module's public API, against the committed authorities and the all-market bar cache — not
against a fixture:

| Symbol | Ex-date | Authority subject (verbatim) | Observed gap | Before | Now |
|---|---|---|---:|---|---|
| BHARTIARTL | 2019-04-23 | `Rights 19:67 @ Premium Rs 215 Per Share` | **-6.98%** | published as real | `UnresolvedRecord` |
| HCC | 2025-12-05 | `Rights 277:630 @ Premium Rs 11.50/-` | **-22.94%** | published as real | `UnresolvedRecord` |
| CCAVENUE | 2025-06-26 | `Rights 67:267 @ Premium Rs 9/-` | **-9.01%** | published as real | `UnresolvedRecord` |
| INTELLECT | 2017-07-17 | `Rights 5:22 @ Premium Rs 81/-` | **-8.96%** | published as real | `UnresolvedRecord` |

Every gap reproduces the adjudicator's figure to the digit, which is what makes the "now" column a
statement about the repair rather than about a different measurement. All four are pinned by
regression tests carrying the verbatim subject line and the measured gap.

### The rule was still incomplete, and this is the hole

`needs_inference = structural_hinted and not structural_sized` asks **one question about the whole
subject line**, so a single sized component vouches for every other one. A record carrying a rights
issue *alongside* a bonus or split was therefore sized on the bonus and declared resolved — the
rights issue silently dropped, exactly as before:

```
'Bonus 1:1/Rights 1:5 @ Premium Rs 100'            -> kinds=('bonus',)  needs_inference=False
'Face Value Split From Rs 10 To Rs 2/Rights 1:5'   -> kinds=('split',)  needs_inference=False
```

This is the adjudication's own root cause recurring one level down: the parser gates the guarantee,
so whatever it fails to recognise is invisible to the guarantee. The test is now made **per
component** — each recognised structural effect answers for itself, and a rights issue is never
sizeable from the subject line whatever else the record carries.

**State this honestly: no published number was affected.** Measured over the entire all-market cache,
**0 of 255** rights records bundle with a sized structural action. The hole is in the rule, not in the
data. It is fixed because the corpus is not the specification — a fail-closed guarantee that depends
on issuers never combining two effects in one line is not fail-closed, and the next NSE record is not
bound by the last 19,941.

### What changed in the data: nothing, and that is measured rather than asserted

The committed `HEAD` module and the repaired one were loaded side by side and run over every record
in the cache:

| | Records compared | Differences |
|---|---:|---:|
| Structural factor | 19,941 | **0** |
| Dividend factor | 19,941 | **0** |
| Parsed kinds | 19,941 | **0** |
| `needs_inference` (refuse-or-allow) | 19,941 | **0** |

So no window changes from refused to published or back, on this corpus. **No committed evidence hash
moves either**, and that needed checking rather than assuming: `factor_set_hash` is computed over the
`unresolved` tuple including each `reason` string, so relabelling a refusal *would* move it. No file
under `data/` or `reports/` carries a `factor_set_hash` at all — the only tracked mention of the term
is inside the adjudication report's own mutation discussion — so there is nothing bound to invalidate.

### Post-repair census, by component

| | Research universe (423 names) | Whole all-market cache |
|---|---:|---:|
| Symbol files | 423 | 3,359 |
| Authority records examined | 6,384 | 19,941 |
| Records matching the rights hint | 40 | 255 |
| **Rights records not failing closed** | **0** | **0** |
| Unresolved components: rights | 40 | 255 |
| Unresolved components: demerger | 56 | 111 |
| Unresolved components: unparsed bonus | 4 | 9 |

The 6,384 reproduces the adjudicator's census exactly, which is the check that this is the same
corpus they measured.

One record carries **two** unsized effects at once and is worth naming, because it is the case that
decides how the refusal is reported. TVSMOTOR 2025-08-25 is `Scheme Of Arrangement - Bonus Ncrps 4:1`
— a bonus whose wording `_BONUS_RE` cannot read (it expects `Bonus a:b`, not `Bonus Ncrps 4:1`)
*and* a scheme of arrangement that publishes no ratio. The two refusals have different reasons, so
reporting only whichever was checked first would drop a real finding from the trail. Both are
enumerated, under `MULTIPLE_UNSIZED_ACTIONS`, and a regression test pins it.

### The refusal now says something true

All four cases were refused as `RATIO_NOT_PUBLISHED` — *"no usable ratio could be parsed from this
action"* — against a subject line that prints `Rights 19:67`. The refusal was right and its stated
reason was false.

A rights issue publishes its ratio. What NSE does not publish is the **subscription price** that
turns the ratio into a theoretical ex-rights price. Since the next step in this workflow is a human
opening the filing to find the missing piece, an audit trail that names the wrong missing piece sends
that reader after something that was never absent. Rights issues are now refused as
`RIGHTS_NOT_SIZEABLE`; demergers keep `RATIO_NOT_PUBLISHED`, which for them is accurate.

### Do these tests actually bite?

The adjudication's sharpest finding was not a defect but a measurement: **5 deliberate defects
survived all 1,477 tests**, including a test suite that asserted the rights defect *was* the
requirement. A repair defended by tests of unknown strength is not obviously better than no repair,
so the new tests were mutation-checked in an isolated copy of `src/` and `tests/` — never in the
install root, because the automated `sync: evidence checkpoint` committer does directory-wide
`git add`:

| Mutant | Result |
|---|---|
| Restore the aggregate `structural_sized` rule (the hole above) | **KILLED** — 2 failed |
| Remove the rights branch entirely (the original DEFECT-1 state) | **KILLED** — 15 failed |
| Refuse rights correctly but relabel it `RATIO_NOT_PUBLISHED` | **KILLED** — 2 failed |
| Sweep buybacks into unresolved (over-broad fail-closed) | **KILLED** — 2 failed |

**4 of 4 killed.** The last one matters as much as the others: fail-closed must stay targeted, or it
discards 140 buyback windows to no purpose and calls that safety.

### Scope of this pass

Verified end to end through the real consumer contract — `build_adjustment_factors` ->
`UnresolvedAction` -> `spans_unresolved` — which is the chain `modeling/labels.py:309` uses to drop a
label whose holding window spans an unresolved action. The label path itself was **read and verified,
not modified**; it needed no change, because it already refuses on the unresolved record that rights
issues now produce.

Not in scope, and untouched: DEFECT-2 (repaired at `c01cb89c`, not re-opened), DEFECT-3, any evidence
store write, any multiplicity ordinal, any model promotion, and every live-money path. Nothing here
promotes anything or alters what may execute.

## What still is not resolved

- **53 of 54 demerger entitlement ratios are unknown here, and that is unchanged.** Naming the
  resulting company does not size the entitlement. Every window spanning one is still refused.
  Closing them is filing-reading work, not code.
- **39 of 56 actions are still unnamed.** The issuer's filing text either does not use the
  `Resulting Company` boilerplate, or the announcement falls outside the +/-540-day window.
- **A named company is a lead, not a validated fact.** The window can admit a different scheme --
  RELIANCE is the caught example, and it was caught by a flag that had itself been broken. Read the
  cited quote and attachment before acting on any of the 17.
- **The candidate shortlist can miss entirely.** A conglomerate demerger that renames the resulting
  entity shares no stem, and a resulting company that never listed on NSE is absent from the cache.
- **Two actions have no ex-date bar at all**, so neither hypothesis can even be scored for them.
- **Dividends are removed without corroboration** when the basis is total return. That is deliberate
  and stated: no gap can distinguish "already applied" from "correctly quoted" for a payout, so
  removing one is a return-definition choice rather than the repair of a provider error. It also
  makes training returns inconsistent with both paper books, neither of which credits a dividend.
