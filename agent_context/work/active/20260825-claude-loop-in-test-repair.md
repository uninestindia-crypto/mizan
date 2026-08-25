# Active work: the loop-in-test findings (program Major #2, continued)

STATUS: COMPLETE — every finding in an unclaimed file resolved; 20 remain in claimed files
OWNER: Claude Code — test craft
TOOL: Claude Code
STARTED_UTC: 2026-08-25T12:10:00Z
STARTING_REVISION: `fb0fc15f`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## The finding count was not the defect count

31 `loop-in-test` findings. The rule is one line regex — `/^\s*(for|while|forEach\s*\()\b/` at
`scripts/check-tests.mjs:310` — applied to every line of a case body. Python writes a multi-line
comprehension with its `for` clause at the start of a line, so **a comprehension matches the loop
rule**. Classified all 31 with `ast` rather than by eye:

| | Count |
|---|---:|
| Genuine `For`/`While` statements | 22 |
| Comprehension clauses, no loop statement in the body | **9** |

Three of the nine are in `test_advisory_isolation.py` and are *already* `@pytest.mark.parametrize`d —
the finding recommends the fix that the code has already applied.

## What the rule is actually protecting against, and where that was true

The stated hazard is "a loop can run zero times and assert nothing". That is only reachable when the
loop iterates something **computed** and the assertion lives **inside** it. Splitting the 22 genuine
loops that way:

| Shape | Verdict |
|---|---|
| Setup loop over a literal (`("INFY","TCS","WIPRO")`, `range(1,4)`), assertion outside and total | Not a defect. Zero iterations fails the assertion below |
| Assertion inside a loop over a **computed** collection | **Genuine defect.** Vacuous pass |

## One real defect, and it was on a secrets test

`test_advisor_key_material_never_reaches_the_journal` looped over `records = _all_records(...)` — a
computed collection — with both assertions inside the loop. If `_all_records` ever returned empty,
the test passed having asserted **nothing**, and what it guards is advisor key material leaking into
the journal.

Rewritten to assert non-emptiness first, then compare a total set, naming what leaked. Proved by
mutation rather than claimed — the test body was executed with `_all_records` replaced:

| Input | Result |
|---|---|
| `[]` | **fails**: "no records were captured, so a leak assertion over them would be vacuous" |
| one record leaking `key_id` | **fails**: "advisor key material reached the journal: ['key_id']" |
| one record leaking `masked_key` | **fails**: names `masked_key` |
| one clean record | passes |

The first row is the defect. The old loop passed on `[]`.

`test_rule_based_advisors_declare_themselves_as_rules` looped over two advisors with the assertion
inside, so a first-advisor failure meant the second was never checked. Unrolled into two explicit
asserts through a local `mode_of` helper — table-driven at the scale two cases deserve. Not
`parametrize`, because the argvalues would have to be evaluated at collection time and this file
deliberately imports `quant_system.alpha.*` inside test bodies, in three places, rather than at
module level.

## The rest were annotated, with the reason at the site

Ten findings — four setup loops over literals, six comprehensions — carry
`# test-allow: loop-in-test - <reason>` naming why the hazard is not reachable there. Annotating a
false positive is what the escape hatch documented at `check-tests.mjs:17` is for. `unexplained-escape`
reports 0, so every one of them states a reason.

## Verification

| Check | Before | After |
|---|---:|---:|
| `loop-in-test`, repo-wide | 31 | **20** |
| `loop-in-test`, unclaimed files | 12 | **0** |
| `unexplained-escape` | 0 | **0** |
| Ruff lint + format on the 6 changed files | clean | **clean** |
| Those 6 files | 179 passed | **179 passed** |
| Full suite | 929 passed | **929 passed** |

The suite count is identical because one loop was unrolled rather than parametrized. No test was
added, removed, weakened, or skipped.

## Owned paths

- `tests/test_advisory_capture_wiring.py`
- `tests/test_advisory_records.py`
- `tests/test_advisory_journal.py`
- `tests/test_advisory_registry.py`
- `tests/test_advisory_isolation.py`
- `tests/test_evidence_publish_atomicity.py`
- `agent_context/work/active/20260825-claude-loop-in-test-repair.md` (this file)
- `agent_context/work/active/20260825-NOTICE-loop-in-test-comprehension-false-positive.md`

## Non-goals

- `scripts/check-tests.mjs`. The regex is the real fix for 9 of the 31 findings and I cannot make it:
  the file is claimed by `20260821-claude-check-tests-casebody.md`. Filed as a notice instead.
- The 20 findings in claimed files. Ownership below.

## Left alone, deliberately

Ownership was determined by parsing the `## Owned paths` block of every active record, not by
grepping for filenames — a filename grep matches records that name a file only as a **non-goal**, and
would have manufactured claims that do not exist.

| File | Findings | Claimed by |
|---|---:|---|
| `tests/test_server_api.py` | 9 | `20260821-claude-check-tests-casebody.md` [HANDOFF_REQUIRED], `20260824-codex-real-journey-api-wiring.md` |
| `tests/test_realtime_shadow.py` | 3 | `20260822-claude-s9b2-repair-and-cadence.md` [IN_PROGRESS] |
| `tests/test_modeling_stress.py` | 3 | `20260821-1048Z-claude-slice4-redteam-repair.md` (via `tests/test_modeling_*`) |
| `tests/test_ui_journeys.py` | 2 | `20260824-codex-real-journey-api-wiring.md` |
| `tests/test_paper_pilot.py` | 1 | `20260822-claude-s9b2-repair-and-cadence.md`, `20260823-claude-api-shadow-paper-remainder.md` |
| `tests/test_modeling_promotion_pipeline.py` | 1 | `20260821-1048Z-claude-slice4-redteam-repair.md` (glob) |
| `tests/test_modeling_campaign_deflation.py` | 1 | `20260821-1048Z-claude-slice4-redteam-repair.md` (glob) |

Of those 20, the `ast` classification says 17 are genuine loop statements and 3 are comprehension
false positives (`test_modeling_stress.py:80`, `:113`, `test_realtime_shadow.py:766`). Seven of the
genuine ones assert inside a loop over a collection that may be computed, so the owners should check
for the same vacuous-pass shape found above. That is a pointer for them, not an adjudication — I did
not read those bodies closely enough to call them defects.

## Next safe action

Nothing here. The remaining 20 need their owners, and the checker regex needs the owner of
`scripts/check-tests.mjs`.
