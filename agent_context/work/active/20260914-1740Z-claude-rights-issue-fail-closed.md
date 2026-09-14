# Active work: fail-closed treatment for rights issues (adjudication DEFECT-1)

STATUS: ACTIVE
OWNER: Claude Code (Opus 5) — session `quant-system-c2`
TOOL: Claude Code
STARTED_UTC: 2026-09-14T17:40Z
STARTING_REVISION: `a4cfa22e429aa648463297884a6ed0bfe4010a22`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout; claimed paths below)
AUTHORIZATION: founder instruction, 2026-09-14 — "Implement and verify a fail-closed treatment for
rights issues in the corporate-action authority and adjusted-label path: detect or conservatively
mark them unresolved so affected windows are excluded, add regression tests using the adjudication
examples, and update the corporate-action validation evidence. Coordinate with existing active path
claims; do not alter live-money scope or spend a model-trial ordinal."

## Objective

Close **DEFECT-1 (P1)** from `.launch/reports/ADJUDICATION-CORPORATE-ACTIONS-20260911.md`: a rights
issue produced neither a factor nor an `UnresolvedRecord`, so `spans_unresolved` returned `False`
and a return measured straight through the ex-rights gap was published as real.

## Non-goals

- **DEFECT-2** (the `/-` dividend suffix). Already repaired at `c01cb89c`; not re-opened here.
- **DEFECT-3** (the RAYMOND 2025 citation). Belongs to the demerger-citation work.
- Sizing a rights issue. The theoretical ex-rights price needs the subscription price, which the
  subject line does not carry. Refusal is the deliverable, not a factor.
- Any evidence store write, any multiplicity ordinal, any model promotion, any live-money path.
- Re-running any campaign, screen or retrain.

## Ownership resolution (PROTOCOL §2, §4, §8)

Scanned every `## Owned paths` block in `agent_context/work/active/` at `a4cfa22e`.

| Path | Prior claim | Resolution |
|---|---|---|
| `src/quant_system/data/corporate_actions.py` | `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md`, STATUS **ACTIVE** (inherited from its predecessor record) | **Explicit partial adoption** — see below |
| `tests/test_corporate_actions.py` | same record | **Explicit partial adoption** |
| `reports/corporate_action_validation/CORPORATE-ACTION-VALIDATION.md` | same record | **Explicit partial adoption** |
| `src/quant_system/modeling/labels.py` | same record (adopted from `20260821-1048Z`) | **Not touched.** Read and verified only |
| `src/quant_system/data/adjustment_provenance.py` | same record | **Not touched.** Read and verified only |
| `scripts/build_mizan_feature_store.py` | same record | **Not touched.** Imported read-only from a scratchpad probe |
| `reports/corporate_action_validation/store-manifest-index.json` | same record | **Not touched.** Copied to scratchpad and read there, so the committed evidence file is never rewritten |

### Adoption notice for `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md`

That record is `STATUS: ACTIVE`, but its own **Stop point** reads *"All work that this session can
execute is complete"*, and its **Next safe action** names, as work belonging to others, *"a third
agent on the unadjudicated corporate-action work"*. The adjudication it triggered ends with
*"Owner of the corporate-action code decides on DEFECT-1 and DEFECT-2."* The owner then repaired
DEFECT-2 and part of DEFECT-1 at `c01cb89c` and stopped.

This is that explicit adoption, and it is **partial and named**, not a takeover of its claim:

- Adopted: the three paths in the table above, only.
- Not adopted, and left entirely alone: every other path in its owned-paths block, including all of
  `research_short_horizon/**`, `reports/short_horizon/**`, `modeling/labels.py`,
  `data/adjustment_provenance.py`, `scripts/train_mizan.py` and every evidence-store directory.

Its record is **not edited** (PROTOCOL §3). This record is the visible declaration. Coordination
messages were sent to both live peer sessions (`quant-system-5f`, `quant-system-9f`) before any
edit, naming the three paths and offering to stop.

## Owned paths

- `src/quant_system/data/corporate_actions.py`
- `tests/test_corporate_actions.py`
- `reports/corporate_action_validation/CORPORATE-ACTION-VALIDATION.md`
- `agent_context/work/active/20260914-1740Z-claude-rights-issue-fail-closed.md`

## Starting state, measured not assumed

`c01cb89c` (2026-09-13) already added `_RIGHTS_HINT` and wired it into `parse_subject_factor`. Both
were verified from source and re-measured against the real committed corpus before any edit:

| Measurement | Result |
|---|---|
| Research universe (423 names), authority records | 6,384 — reproduces the adjudication's own census exactly |
| Records matching the rights hint | 40, **all 40 fail closed** |
| Whole all-market cache (3,359 symbol files), records | 19,941 |
| Records matching the rights hint | 255, **all 255 fail closed**, 0 leaks |
| Adjudication's four reproductions | All four now emit `UnresolvedRecord`; gaps reproduce to the digit (BHARTIARTL -6.98%, HCC -22.94%, CCAVENUE -9.01%, INTELLECT -8.96%) |

**So the headline defect is already closed.** What remains is stated below as findings of this
session, not as the founder's premise restated.

## Findings this session, and the plan

1. **A latent leak in the fail-closed rule (this session's finding, not the adjudication's).**
   `needs_inference = structural_hinted and not structural_sized` aggregates across the whole
   subject line, so a record carrying a rights issue *alongside a sized bonus or split* is declared
   resolved and the rights issue is silently ignored:

   ```
   'Bonus 1:1/Rights 1:5 @ Premium Rs 100'            -> kinds=('bonus',)  needs_inference=False
   'Face Value Split From Rs 10 To Rs 2/Rights 1:5'   -> kinds=('split',)  needs_inference=False
   ```

   This is the same class of error as DEFECT-1, one level deeper. **It does not occur in the current
   corpus** — 0 of 255 rights records across the full cache — so no published number changes. It is
   a defect in the rule, not an active corruption, and it is reported that way.

2. **The reason code is inaccurate for a rights issue.** All four reproductions emit
   `RATIO_NOT_PUBLISHED` with detail *"no usable ratio could be parsed"*, against a subject line that
   plainly carries `Rights 19:67`. The ratio **is** published; what is missing is the subscription
   price. An auditor reading that trail is told something false about the evidence.

Plan: make the unsized test per-component rather than aggregate; give rights a distinct, accurate
reason; add regression tests using the four real adjudication subject lines plus the bundled case;
re-run both censuses; update the validation evidence.

## What was changed

`src/quant_system/data/corporate_actions.py`

1. **Per-component unsized detection.** `needs_inference` was
   `structural_hinted and not structural_sized` -- one question about the whole subject line, so any
   one sized component vouched for every other. Each recognised structural effect now answers for
   itself, and a rights issue is never sizeable from the text whatever else the record carries.
2. **`SubjectComponents.unsized`**, a new tuple naming which components were recognised but not
   sized. `needs_inference` is unchanged and is now exactly `bool(unsized)`, so every existing
   reader keeps working.
3. **Accurate refusal reasons.** `_UNSIZED_REASONS` and `_unresolved_reason()`. Rights issues are
   refused as `RIGHTS_NOT_SIZEABLE` naming the missing subscription price; demergers keep
   `RATIO_NOT_PUBLISHED`, which for them is true. A `VALIDATED` factor is no longer hardcoded to
   `kinds=("demerger",)`.

`tests/test_corporate_actions.py` -- **55 -> 66 tests**. Ten pin the rights path; the eleventh pins `MULTIPLE_UNSIZED_ACTIONS`, a code path this change introduced, against the one real record in the universe that exercises it (TVSMOTOR 2025-08-25, `Scheme Of Arrangement - Bonus Ncrps 4:1` -- a bonus whose wording `_BONUS_RE` cannot read *and* a ratio-less scheme, refused for two different reasons at once).

`reports/corporate_action_validation/CORPORATE-ACTION-VALIDATION.md` -- new section
"Rights issues: the fail-closed rule, verified end to end (2026-09-14)"; the stale code snippet in
"Repairs" marked superseded rather than deleted, since the prose around it describes it.

## Commands and outcomes

| Command | Outcome |
|---|---|
| Census, 423-name research universe | 6,384 records -- **reproduces the adjudicator's census exactly**; 40 rights records, **40 fail closed, 0 leaks** |
| Census, whole all-market cache | 3,359 symbol files, 19,941 records, 255 rights records, **255 fail closed, 0 leaks** |
| Reproduction of the four adjudicated cases against the real cache | All four emit `UnresolvedRecord`; gaps reproduce to the digit: BHARTIARTL -6.98%, HCC -22.94%, CCAVENUE -9.01%, INTELLECT -8.96% |
| A/B, committed `HEAD` module vs repaired, over all 19,941 records | **0 differences** in structural factor, dividend factor, parsed kinds, and `needs_inference` |
| Mutation check, isolated copy of `src/` + `tests/` in scratchpad | **4 of 4 mutants killed** (aggregate rule restored; rights branch removed; rights relabelled `RATIO_NOT_PUBLISHED`; buybacks swept in) |
| `ruff check` + `ruff format --check` on both edited files | All checks passed; 2 files already formatted |
| `mypy src/quant_system/data/corporate_actions.py` | Success, no issues |
| `mypy src launcher.py scripts` (CI invocation) | **Success, 210 source files.** An earlier run had 1 error in another session's in-progress `scripts/rescore_short_horizon_multiplicity.py`; reported to its owner, who fixed it |
| `pytest tests/ -q` | **1,578 passed**, 0 failed, 520.36s |
| `pytest` reverse file order (CI's own invocation) | **1,578 passed**, 0 failed, 544.20s |
| `pytest tests/test_corporate_actions.py -q` | **66 passed** (was 55 at `a4cfa22e`) |
| `scripts/audit-disk-layout.ps1` | **PASS**, exit 0 |
| `scripts/audit-agent-claims.ps1` | **PASS**, exit 0 -- every workspace has a visible claim and every claim resolves |

Mutation testing ran in an isolated copy under this session's scratchpad, never in the install root,
because the automated `sync: evidence checkpoint` committer does directory-wide `git add`.
No evidence store was written. No multiplicity ordinal was spent. No model was promoted.
`reports/corporate_action_validation/store-manifest-index.json` was copied to scratch and read there,
so the committed evidence file was never rewritten.

## Findings, stated at their real strength

- **The headline defect was already closed before this session started**, at `c01cb89c` (2026-09-13).
  That is recorded as the starting state, not claimed as this session's work. What this session adds
  is the independent verification the adjudication asked for, a hole in the repaired rule, an
  accurate refusal reason, and tests that demonstrably bite.
- **The bundled-rights hole is latent, not active.** 0 of 255 rights records in the whole cache
  bundle with a sized structural action. No published number changes; the A/B proves it at 0
  differences over 19,941 records. It is fixed because the corpus is not the specification.
- **No committed evidence hash moves.** This needed checking rather than assuming: `factor_set_hash`
  is computed over the `unresolved` tuple *including each `reason` string*, so relabelling a refusal
  would move it. No file under `data/` or `reports/` carries a `factor_set_hash` at all.
- **Rights issues are refused, not sized.** Nothing here computes a theoretical ex-rights price. That
  needs the subscription price, which the subject line does not carry. Refusal is the deliverable.

## Blockers and conflicts

None blocking. One downstream consequence filed as an additive notice rather than edited:
`20260914-NOTICE-demerger-worklist-now-includes-rights-and-bonus.md`. Since `c01cb89c`,
`scripts/validate_demerger_factors.py` selects candidates on `needs_inference` alone, which now
means "any unsized structural action" rather than "ratio-less demerger" -- 99 records in the universe
against a committed 54-entry worklist. That script is owned by `20260910-1615Z` and was **not**
edited; the new `unsized` field gives its owner a one-line filter.

Coordination: both live peer sessions were messaged before any edit. `quant-system-9f` confirmed it
holds none of these three paths and is editing a disjoint subset of the same record
(`reports/short_horizon/**`, `research_short_horizon/**`, and two new files). Agreed with it: explicit
path staging only, no repository-wide formatter while either is live.

## Verification status

All three gates green on the **final** code. Both suites were re-run from scratch after the last
refactor, because an earlier pair of runs had collected the pre-refactor files and their numbers
would not have described what is committed.

| Gate | Result |
|---|---|
| `pytest tests/ -q` | **1,578 passed**, 0 failed, 8m40s |
| `pytest` reverse file order | **1,578 passed**, 0 failed, 9m04s |
| `mypy src launcher.py scripts` | **Success, 210 source files** |

Reverse order is the CI invocation (`Get-ChildItem tests/test_*.py | Sort-Object Name -Descending`)
and is run because a suite that is green forwards and red backwards is not green.

A caveat that must travel with the 1,578 figure: the shared checkout also carries another session's
in-flight work (`quant-system-9f`, short-horizon re-scoring), so that total is the whole tree at the
moment of the run and **not** an attribution to this task. The attributable delta is exact and
separately measured: **`tests/test_corporate_actions.py` went 55 -> 66.**

## Stop point

**COMPLETE.** Code, tests and evidence written and verified; all gates green on the final code;
both audits PASS. Committed as explicit paths only, never `git add -A`, because the checkout is
shared with a live session.

## Next safe action

1. **The owner of `scripts/validate_demerger_factors.py`** decides on the notice above. Until then,
   do not re-run it and do not regenerate `ratioless-action-worklist.json`: the output would carry 43
   non-demerger actions and the `0 validated / 56 refused` figure would silently change denominator.
2. **An independent agent should adjudicate this repair**, as with the one before it. This session
   did not write `c01cb89c` but did write everything it is now vouching for, which is the same
   arrangement the 2026-09-11 adjudication existed to correct.
3. **Do not attempt to size a rights issue from its ex-date gap.** The gap is the dilution plus the
   day's market movement, and nothing separates them -- the identical mistake that condemned gap
   inference for demergers (NMDC +71.0%, BAJAJELEC +32.2%, SCI +30.0%). Sizing one needs the
   subscription price from the filing, which is filing-reading work, not code.
4. Nothing here changes release state, promotes any model, or touches live-money scope.
