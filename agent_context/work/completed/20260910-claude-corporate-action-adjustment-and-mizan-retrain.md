# Active work: corporate-action price adjustment and the Mizan retrain

STATUS: COMPLETED (reclaimed 2026-09-10T13:35Z on founder instruction; A/B delivered, governed retrain deliberately not run -- see the A/B result)
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-09-10
STARTING_REVISION: `ee1b0cb3`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, disjoint paths)
AUTHORIZATION: founder instruction, 2026-09-10 — "retrain the mizan model with the corrected
corporate action data", then explicitly "all four steps, retrain included" and "full total-return
adjustment" when the sequence and the dividend policy were put to them.

## Record-keeping correction

This record was created **after** editing began, which PROTOCOL §2 forbids. The preceding record
`20260910-claude-corporate-action-authority-refresh-cadence.md` covered the ingest fix; this work
grew out of it into new paths without a new claim being filed first. Recorded rather than tidied
away. No other agent's path was touched in the interval — verified by an owned-paths scan across all
active records before the first edit.

## Objective

Retraining alone was a no-op: nothing in the repository applies corporate actions to prices, so the
model would have read bit-identical inputs. Build the missing adjustment, refresh the authorities,
rebuild the feature store on adjusted bars, then retrain.

## Owned paths

- `src/quant_system/data/corporate_actions.py` (new)
- `tests/test_corporate_actions.py` (new)
- `scripts/build_mizan_feature_store.py`
- `data/evidence/feature-store/mizan/` (rebuild output)
- `data/evidence/market-cache/all-market-20160822-20260821/corporate-actions/` (refetch only)
- `agent_context/work/active/20260910-claude-corporate-action-adjustment-and-mizan-retrain.md`

Verified unclaimed by an owned-paths-block scan across all active records. `src/quant_system/
modeling/**` is claimed by several records and is **read and called, never edited**.

## Non-goals

- No edit to `src/quant_system/modeling/**`. Claimed by `20260820-codex-slice4-ridge-training.md`
  and others. `train_mizan.py` and the screens call it; nothing here changes it.
- No promotion. Whatever the retrain produces stays `RESEARCH_ONLY` unless it clears the gate on
  its own evidence.
- No change to either paper book, its strategy, or its portfolio state.
- No rewrite of existing dataset manifests. They are immutable evidence and keep the authority they
  were written with.

## The four steps

| Step | State | Ordinal cost |
|---|---|---|
| 1. Build corporate-action adjustment | **DONE** — 28 tests pass | 0 |
| 2. Refetch all-market authorities (3,359) | IN PROGRESS | 0 |
| 3. Rebuild the Mizan feature store on adjusted bars | pending | 0 |
| 4. Retrain (governed) | **BLOCKED — see below** | 1 |
| 4b. Out-of-sample screen A/B (ungoverned) | substituted for 4 | **0** |

## THE PREMISE WAS WRONG. Corrected here, measured not argued.

I told the founder that **250 structural corporate actions sit in the training data as fake
±30-60% days, affecting ~59% of names**. That is **false**, and acting on it was destructive.

`Upstox already back-adjusts splits and bonuses.` The manifest's `status: RAW` label describes the
*provenance*, not the arithmetic. Measured across every parsed action in the NIFTY500 cache that has
a bar on its own ex-date:

| Action | n | Gap at ex-date ~1.0 (provider already applied) | Gap ~ published ratio (unapplied) |
|---|---:|---:|---:|
| Split / bonus | 78 | **78** | **0** |
| Dividend | 1,801 | quote drops by the payout, as it should | — |
| Ratio-less demerger | 7 | — | **4 with real gaps** |

**How it was caught.** The 5-symbol smoke build produced `return_1 = +9.458572` for TATASTEEL on
2026-07-28 — **+945%**. The RAW value was `+0.045857`, an ordinary day. The provider had already
applied the 10:1 split and my code applied the published ratio a second time, scaling six years of
prior history by 0.1. A full rebuild on that logic would have silently corrupted the entire feature
store, and the corruption would have looked like signal.

It was caught by a five-symbol smoke test that cost ~20 minutes, before the full rebuild and before
any ordinal was spent. No gate would have caught it: 28 unit tests passed, ruff passed, mypy passed.
They all encoded the same wrong premise as the code.

**The corrected rule: measure, do not assume.** A published structural ratio is applied only when
the bars show the provider has *not* already applied it — the observed ex-date gap must corroborate
the published factor within tolerance. This needs no per-provider configuration and stays correct if
the provider's behaviour changes. Demergers keep the gap-inference path, because those the provider
genuinely does not apply: ABFRL -63.6%, VEDL -62.6%, SIEMENS -50.3%, TMPV -39.5%, HEG -64.3%.
Dividends are applied when `total_return=True` without gap verification, because no gap can
distinguish "already applied" from "correctly quoted" — removing a payout is a return-definition
choice, not the repair of a provider error.

**What this does to the task.** The real defect in the training corpus is a handful of demergers,
not 250 structural breaks. The case for spending an ordinal on a retrain is correspondingly much
weaker than the one I put to the founder, and that has to be said plainly rather than buried.

## Step 4 is blocked, and the reason is a provenance one

Discovered while wiring step 3, not assumed.

**Features and labels come from different places.** `train_mizan.py:134` loads the CSV feature store
and passes those values into `build_mizan_feature_dataset`, so **features** would be adjusted after
the rebuild. But `_constituent` (`train_mizan.py:107`) builds **labels** with
`build_label_dataset(features, acquisition, ...)`, and that reads next-open prices straight off
`acquisition.records` — RAW bars. Adjusting one side and not the other is worse than adjusting
neither: the model would be fitted on corrected features against 250 fake ±30-60% targets.

**The label path cannot be corrected from here.** `src/quant_system/modeling/labels.py` is claimed by
`20260821-1048Z-claude-slice4-redteam-repair.md` (`src/quant_system/modeling/*.py`, STATUS
HANDOFF_REQUIRED). PROTOCOL §5 says an active record stays until another agent explicitly adopts it.

**And feeding adjusted bars in through the unclaimed script would write a false provenance claim.**
`DatasetManifest` (`src/quant_system/data/market_data.py:276`) has **no `adjustment` field at all**.
`to_canonical_dict` emits the literal `"adjustment": {"method": "PROVIDER_UNSPECIFIED",
"status": "RAW"}` at line 310. So any governed evidence produced from adjusted bars would declare
itself RAW, permanently and immutably — which is precisely the defect class this whole line of work
exists to remove. Making it honest requires editing that governed contract, which sits under the
same HANDOFF_REQUIRED claim.

**Therefore the ordinal is not spent.** Instead, step 4 is answered by
`screen_mizan_out_of_sample.py`, which writes no evidence store, spends no ordinal, and produces the
measurement that actually matters: whether correcting corporate actions moves the -0.000022
selection edge. Its `forward_returns` now adjusts labels with the same kernel as the features, so
both sides of that screen are on one basis.

**What would unblock the governed retrain**, in order: an `adjustment` field on `DatasetManifest`
that records method and authority instead of a literal; `build_label_dataset` consuming adjusted
bars; then one ordinal. All three touch paths under another agent's claim.

## Correction to a figure given to the founder

I told the founder the retrain would cost "~50 fresh multiplicity ordinals". **That is wrong.** That
figure came from the old per-instrument campaigns (51, then 50 trials, one ordinal per name).
`scripts/train_mizan.py` is explicitly *"one pooled cross-sectional governed model, at one
multiplicity ordinal"* — Mizan is a single study that ranks instruments against each other, so the
retrain costs **one** ordinal. The decision was materially cheaper than I framed it, and the founder
chose to proceed under the inflated figure, so the correction only widens the margin.

## Decision rationale

**Why the adjustment had to be built first.** `grep -c corporate scripts/build_mizan_feature_store.py`
returned **0**, `src/` contains no adjustment logic at all, and `market_data.py:310` hardcodes
`"adjustment": {"method": "PROVIDER_UNSPECIFIED", "status": "RAW"}`. Every input to the existing
feature store was last written at `966a4961`; the authority refetch at `ee1b0cb3` touched none of
them. Retraining first would have spent the ordinal to reproduce the same coefficients.

**How large the defect is.** 250 structural actions (split, bonus, demerger, consolidation) fall
inside the research universe and the training window — roughly 59% of names carry at least one. Each
sits in the training series as a genuine ±30-60% day.

**Total return, on founder instruction.** Dividends are removed as well as structural actions. This
makes training returns **inconsistent with both paper books, which credit no dividends** — flagged
before the choice was made, chosen anyway, and recorded here because it changes how any result must
be read. A model trained on total return and traded on price return is being evaluated against a
different return definition than it learned.

**What the parser refuses to do.** NSE publishes demergers with no ratio — the entire vocabulary is
`Demerger`, `Scheme Of Demerger`, `Scheme Of Arrangement Of Demerger`. The size is inferred from the
ex-date gap and **only** when the gap exceeds 20%, which no ordinary NSE session reaches and every
measured structural break in this cache exceeds. Below that the action is reported and left
unadjusted, because inferring from a small gap would fabricate a correction nothing asked for.
Measured on the real corpus: **26 inferred, 28 refused**. Roughly half of ratio-less actions are
therefore left in the data, and that is a stated limitation rather than a solved problem.

## Commands and outcomes

| Command | Result |
|---|---|
| `pytest tests/test_corporate_actions.py` | **28 passed** |
| `pytest tests/test_ingest_corporate_action_authority.py` | 11 passed |
| `ruff check` / `format --check` (owned files) | clean |
| `mypy scripts/build_mizan_feature_store.py src/.../corporate_actions.py` | **Success, no issues** |
| Coverage audit over the real corpus | 394/423 symbols get ≥1 factor; **4,790 factors** (4,764 PARSED, 26 INFERRED); kinds: dividend 4,558, bonus 133, split 81, demerger 26; 28 refused |

## Defect caught during integration, worth recording

Renaming the `date` loop variable in `_instrument_rows` exposed that the row tuple still referenced
`date` — which, once `datetime.date` was imported at module scope for the ex-date parser, would have
silently resolved to the **class object** and written a type into the date column of every feature
row. Ruff and mypy both passed with the bug present. Found by reading the call site after the
rename, not by a gate.

## Blockers and conflicts

None. `modeling/**` is read-only here by design.

## A/B RESULT — the correction does not rescue the model

Both arms complete, on the committed tree at `9dd5b62f`. Arm A is the control; it reproduces the
published baseline exactly, which is what makes Arm B interpretable.

| | Arm A — RAW | Arm B — corporate-action adjusted |
|---|---:|---:|
| Labels | RAW opens | adjusted, total return |
| Test rows (380 names) | 902,582 | **899,840** |
| Model: mean / t / Sharpe | +0.006528 / +5.86 / +0.60 | +0.007249 / +6.61 / +0.68 |
| Equal-weight: mean / t / Sharpe | +0.006550 / +6.80 / +0.69 | +0.007433 / +7.73 / +0.79 |
| **Selection edge** | **-0.000022** | **-0.000185** |
| **t** | **-0.07** | **-0.66** |
| Sharpe | -0.01 | -0.07 |

**Arm A reproduces `-0.000022, t = -0.07` to the digit.** The harness measures what it is believed
to measure, so Arm B carries information rather than noise about the plumbing.

**The edge stays negative and moves slightly further negative** — from -0.000022 to -0.000185, t from
-0.07 to -0.66. Neither is significant; the correction does not turn a loss into a win, or a null
into a signal. Equal-weight beats the model in both arms, and beats it by *more* after correction.

**Why both absolute levels rose** (+0.65% -> +0.72% per period): that is the dividend add-back from
the total-return basis, and it lifts the model arm and the benchmark arm together. It cancels in the
difference, which is exactly why the selection edge is the number to read and the absolute return is
not.

**Why Arm B has 2,742 fewer test rows**: 56 unresolved ratio-less actions on 49 symbols black out the
windows that span them. That is the fail-closed path working — those observations are refused rather
than published as fabricated returns.

**Fitted coefficients are stable across arms.** Every sign is preserved and magnitudes barely move
(e.g. `sma_20_distance` +0.008082 -> +0.008177, still the only positive of the eight). The model
learns the same thing from corrected data; there was no hidden signal that bad corporate-action
handling was masking.

### Conclusion

**Do not spend the ordinal.** The retrain was justified on the premise that corrected corporate
actions would change the measured edge. Measured: it does not. The governed retrain would publish
another `RESEARCH_ONLY` model and consume a multiplicity ordinal to reproduce a null that two
ungoverned screens have now established at 902,582 and 899,840 test rows.

Caveat that travels with this: the demerger correction here is **exclusion, not repair**. The
validated-factor pass returned **0 validated / 56 refused** out of 54 ratio-less actions -- the
value-continuity method could not confirm a single one -- so no demerger was actually re-sized. Arm B
therefore measures "dividends added back, contaminated windows dropped", not "demergers corrected".
A future validated-factor source would change what Arm B means, though on this evidence it is very
unlikely to change the sign.

## Reclaimed 2026-09-10T13:35Z — A/B running from an isolated snapshot

Founder instruction: *"take it back and finish the A/B"*. PROTOCOL §8.3 makes that the sanctioned
route to resolve ownership.

**The successor's files are not being seized.** It is live -- `corporate_actions.py` was rewritten
three times inside one 45-second window -- and it has already repaired the broken caller this record
reported, adding `AdjustmentPlan`, `ValidatedFactor`, authority-hash binding, and demerger factors
validated against the resulting company's first traded price rather than the parent's gap. Taking
those files would destroy live work that is better than what it replaced.

The A/B therefore runs against a **pinned snapshot** of the successor's code in
`<scratch>/ab/`, reading the shared caches, writing only to scratch. Rationale and consequences:
`20260910-NOTICE-predecessor-reclaims-ab-on-founder-instruction.md`.

## Superseded stop point (2026-09-10T13:20Z)

Superseded by `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (same owner,
broader founder authorization covering the governed contract changes this record listed as blocked).
That record explicitly inherits every path here.

**The A/B the founder asked for was not completed.** The full rebuild failed at exit 1 because the
successor rewrote `build_adjustment_factors` to return an `AdjustmentPlan` while
`build_mizan_feature_store.py:166` still unpacks the old two-tuple. Editing that file to match would
have meant writing into a live claim, so it was left alone and recorded instead:
`20260910-NOTICE-predecessor-left-uncommitted-screen-edit-and-broken-caller.md`.

Banked and verified before handover:

| | |
|---|---|
| Adjustment module | 30 tests, including the +945% regression |
| All-market authority refetch | 3,359/3,359 FETCHED, 0 stale, 0 unavailable |
| Provider-already-adjusts finding | 78/78 split-bonus, measured |
| Demergers unadjusted | ABFRL, VEDL, SIEMENS, TMPV, HEG |

Not done: full feature-store rebuild, both A/B arms, the governed retrain. The full test suite was
**not** re-run after the module rewrite — it was killed mid-run to free memory for the rebuild and
the tree has changed under it since.

## Next safe action

Finish the refetch, rebuild the feature store on adjusted bars, run
`screen_mizan_out_of_sample.py` on both the RAW baseline and the adjusted store for a free
before/after on the -0.000022 selection edge, then spend the single ordinal on `train_mizan.py`.
