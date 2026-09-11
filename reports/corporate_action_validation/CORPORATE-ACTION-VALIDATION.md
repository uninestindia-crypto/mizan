# Corporate-action correctness: what was wrong, what was measured, what is still unresolved

**Headline: two defects were found and repaired, and the second one had already been shipped into
the adjustment code. Neither was visible to any gate — 28 unit tests, ruff and mypy all passed with
both defects present, because the tests encoded the same wrong premises as the code.**

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

## What still is not resolved

- **53 of 54 demerger entitlement ratios are unknown here.** Their windows are refused. Closing them
  is filing-reading work, not code.
- **The candidate shortlist can miss entirely.** A conglomerate demerger that renames the resulting
  entity shares no stem, and a resulting company that never listed on NSE is absent from the cache.
- **Two actions have no ex-date bar at all**, so neither hypothesis can even be scored for them.
- **Dividends are removed without corroboration** when the basis is total return. That is deliberate
  and stated: no gap can distinguish "already applied" from "correctly quoted" for a payout, so
  removing one is a return-definition choice rather than the repair of a provider error. It also
  makes training returns inconsistent with both paper books, neither of which credits a dividend.
