# Mizan corporate-action A/B — RAW vs adjusted

Ungoverned screen. **No evidence store written, no multiplicity ordinal spent.** Its only job was to
decide whether a governed retrain on corporate-action-corrected data was warranted. It is not.

Run on the committed tree at `9dd5b62f`, via `scripts/screen_mizan_out_of_sample.py`.

## Result

| | Arm A — RAW | Arm B — corporate-action adjusted |
|---|---:|---:|
| Labels | RAW opens | adjusted, total return |
| Test rows (380 names) | 902,582 | 899,840 |
| Model: mean / t / Sharpe | +0.006528 / +5.86 / +0.60 | +0.007249 / +6.61 / +0.68 |
| Equal-weight: mean / t / Sharpe | +0.006550 / +6.80 / +0.69 | +0.007433 / +7.73 / +0.79 |
| **Selection edge** | **-0.000022** | **-0.000185** |
| **t** | **-0.07** | **-0.66** |
| Sharpe | -0.01 | -0.07 |

**Arm A is the control and it reproduces the published `-0.000022, t = -0.07` to the digit**
(`20260825-1500Z-claude-mizan-pooled-model.md:313`). That is what makes Arm B interpretable rather
than a statement about the harness.

## Reading it

**The correction does not rescue the model.** The selection edge stays negative and moves slightly
further negative. Neither figure is significant, so this is not "correcting the data made it worse" —
it is "correcting the data changed nothing that matters". Equal-weight beats the candidate in both
arms, and by more after correction.

**Both absolute levels rose** (+0.65% -> +0.72% per period) purely from the dividend add-back in the
total-return basis. It lifts the model arm and the benchmark arm together and cancels in the
difference, which is why the selection edge is the number to read and the absolute return is not.

**Arm B has 2,742 fewer test rows.** 56 unresolved ratio-less actions on 49 symbols black out the
windows spanning them — the fail-closed path refusing observations rather than publishing fabricated
returns.

**Fitted coefficients are stable across arms**, every sign preserved and magnitudes barely moved
(`sma_20_distance` +0.008082 -> +0.008177, still the only positive of eight). The model learns the
same thing from corrected data; no signal was being masked by bad corporate-action handling.

## The caveat that must travel with this

**The demerger handling here is exclusion, not repair.** `scripts/validate_demerger_factors.py`
returned **0 validated / 56 refused** across 54 ratio-less actions — value-continuity against the
resulting company's first traded price could not confirm a single one. So no demerger was re-sized.
Arm B measures *"dividends added back, contaminated windows dropped"*, not *"demergers corrected"*.
A working validated-factor source would change what Arm B means, though on this evidence it is very
unlikely to change the sign.

## Conclusion

Do not spend the multiplicity ordinal on a governed retrain of this candidate. It would publish
another `RESEARCH_ONLY` model to reproduce a null now established on ~900,000 test rows in each arm.

Full reasoning and the two premise corrections made along the way:
`agent_context/work/active/20260910-claude-corporate-action-adjustment-and-mizan-retrain.md`.
