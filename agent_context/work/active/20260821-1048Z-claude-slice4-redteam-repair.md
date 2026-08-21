# Active work: Slice 4 Red Team repair round

STATUS: HANDOFF_REQUIRED  
OWNER: Claude Code (Opus 5), successor to the Slice 4 certification record  
TOOL: Claude Code  
STARTED_UTC: 2026-08-21T10:48:57Z  
UPDATED_UTC: 2026-08-21T16:05:00Z  
STARTING_REVISION: `46e99f90ed3ab580daaedc321969444ac26e9870`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Adoption notice

`agent_context/work/active/20260821-0530Z-claude-slice4-certification.md` plan step 8 records the
repair round as out of its own scope and assigns it to "the Slice 4 implementation record or its
successor". This record is that successor. Authority: founder instruction in session
("work on whats left"), which `.launch/STATE.md` "Next action" resolves to exactly this task.

Per PROTOCOL section 3 neither the certification record nor
`agent_context/work/active/20260820-codex-slice4-ridge-training.md` is edited here.

## Objective

Repair every finding in `.launch/reports/RED-TEAM-SLICE-04.md` — 4 Blockers, 7 Majors, 7 Minors —
each beginning with a failing regression test that reproduces the Red Team's exact attack, then
re-establish the Slice 4 gate green at an exact revision so a Red Team recheck and an independent
clean-state Verifier can run.

## Owned paths

- `src/quant_system/modeling/*.py`
- `src/quant_system/evidence/*.py`
- `tests/test_modeling_*.py`
- `tests/test_evidence_store.py`
- `tests/test_evidence_process_recovery.py`
- `tests/test_dataset_evidence.py`
- `tests/modeling_fixtures.py`
- `tests/modeling_training_fixtures.py`
- `agent_context/work/active/20260821-1048Z-claude-slice4-redteam-repair.md`

> `.launch/**` is **not** owned here. It is claimed by
> `20260821-0530Z-claude-slice4-certification.md`, which has already committed `STATE.md` and
> the adjudication reports twice (`10407e1`, `46e99f9`). Ownership split agreed in session
> 2026-08-21T15:40Z: that record owns `.launch/**`, this record owns `src/**` and `tests/**`.

## Non-goals

- Declaring Slice 4 PASS or flipping G4. Repair is not adjudication; a Red Team recheck and an
  independent Verifier must run at the repair revision.
- Performing that recheck or verification myself — self-adjudication voids the result.
- Any `src/quant_system/alpha/**` or `tests/test_ai_*.py` path. Those carry uncommitted Antigravity
  work (`agent_context/work/completed/20260821-antigravity-ai-multi-provider-keypool.md`).
- Editing another agent's work record, or removing any workspace clone under
  `D:\quant_system_workspaces\`.
- Slice 5 scope: no holdout, no promotion evaluation.

## Plan

1. COMPLETE - concurrency and ownership check; create this record.
2. COMPLETE - Blocker 1: training label maturing into the validation window fails closed.
3. COMPLETE - Blocker 2: forged model metrics rejected by re-deriving strategy summaries.
4. COMPLETE - Blocker 3: staged resource verified before publish; inputs bounded at write time.
5. COMPLETE - Blocker 4: reserved `_outcome` trial-id suffix rejected.
6. COMPLETE - Majors 1, 2, 3, 5, 6, 7. Major 3 was handed over by `quant-system-7c`.
7. COMPLETE - Major 4 and Minors 1, 3, 4, 5, 6. Minor 2 accepted with rationale; Minor 7 is `.launch/`.
8. IN PROGRESS - commit (awaiting founder authorisation), then hand the exact repair revision to `quant-system-7c` for clean-clone
   re-baselining, a Red Team recheck, and an independent Verifier.

## Current step

Every finding is repaired or explicitly accepted. Full gate green in the shared checkout:
315 tests at 88.08% coverage, focused Slice 4 suite 123 passed across 14 files, Ruff lint and
format clean, strict Mypy across 86 files, vulture clean, both craft checkers exit 0.

One gate is RED, and it is **not** in this record's paths - see "Secret-scan gate failure" below.
Nothing is committed yet; committing needs founder authorisation.

## Findings status

| Finding | Status | Repair |
|---|---|---|
| Blocker 1 | DONE | Training label maturing at/after `validation_start` fails `PARTITION_INVALID` |
| Blocker 2 | DONE | Strategy summaries re-derived from published decisions; mutation-killed |
| Blocker 3 | DONE | Staged resource verified before publish; metadata bounded; bool `schema_version` refused |
| Blocker 4 | DONE | `trial_id` may not end with the reserved `_outcome` suffix |
| Major 1 | DONE | `rebuild_index()` reports `orphan_blob_hashes`, making tail-deletion rollback detectable |
| Major 2 | DONE | `campaign_deflated_sharpe_ratios()` re-deflates published models against the final attempt count |
| Major 3 | DONE | Handed over by `quant-system-7c`; ambiguous symbol join fails `DATASET_INTEGRITY_INVALID`; mutation-killed here |
| Major 4 | DONE | Original diagnosis preserved via `add_note`; bounded lease wait added |
| Major 5 | DONE | `_float_decimal` no longer emits non-canonical `-0` |
| Major 6 | DONE | Zero-variance return series fails `DEGENERATE_RETURN_SERIES` instead of publishing DSR 0.5 |
| Major 7 | DONE | `label_horizon_sessions` must equal `LABEL_HORIZON_SESSIONS_V1` |
| Minor 1 | DONE | Terminal-trial message names the state and where the result is published |
| Minor 2 | ACCEPTED | See rationale below; destructive blast radius removed and regression-tested |
| Minor 3 | DONE | `type(x) is not int` guards on both classes |
| Minor 4 | DONE | A non-zero Sharpe requires a non-zero published volatility |
| Minor 5 | DONE | `dataset_id` bounded by `dset_[a-z0-9][a-z0-9_-]{0,91}` |
| Minor 6 | DONE | One-period fold fails closed with a typed code |
| Minor 7 | NOT MINE | Documentation defect in `.launch/SLICE-04-EVIDENCE.md`; closed by `quant-system-7c` in `e9d7580` |

## Minor 2 - accepted, not repaired

`evaluate_governed_ridge_fold` still accepts a caller-supplied `TrialRegistryV1`. Repairing it as
stated would mean making the evaluator take an `EvidenceStore`, turning the one pure, directly
testable function in the slice into one that requires a filesystem. Rejected as disproportionate to
a Minor.

What was done instead:

- The governed entry point `run_persisted_ridge_trial` already loads the registry from the immutable
  catalog itself, so the path that publishes evidence is bound.
- The destructive half of this finding is gone. Publishing an under-counted evaluation previously
  made every later catalog read fail permanently (Blocker 3C). It no longer does:
  `test_undercounted_model_publish_no_longer_bricks_the_catalog` proves the catalog stays readable,
  reports no invalid resources, and leaves no orphan blobs.
- The function's docstring now states that the registry is not an authority and that its
  `deflated_sharpe_ratio` must never be quoted without the `multiplicity_count` beside it.

Residual risk, stated plainly: a caller who bypasses the persisted path can still compute and
report a deflated Sharpe against a fabricated attempt count. Nothing that reaches immutable
evidence is affected.

## Secret-scan gate failure - outside this record's ownership

`scripts/run-slice4-gates.ps1` stops at the application secret scan with 1 candidate. Located by
elimination, not guessed:

| Scan scope | Candidates |
|---|---|
| `src/quant_system/modeling`, `src/quant_system/evidence`, all five of my test files, fixtures | 0 |
| `src/quant_system/alpha`, `tests/test_ai_*.py` (uncommitted Antigravity work) | 0 |
| `.launch`, `agent_context`, `scripts` | **1** |

The candidate is `.launch/reports/RED-TEAM-SLICE-04.md` line 89, type `Hex High Entropy String`:

```text
outcome: [('trial_tamper','SUCCEEDED','<24-hex-elided>')]
```

It is a deterministic hash from the Red Team's own Blocker 2 reproduction output, not a secret. It
entered the tree in commit `10407e1`, which is owned by
`20260821-0530Z-claude-slice4-certification.md` (`.launch/**` per the agreed seam).

**Deliberately not fixed here.** Two reasons: `.launch/**` is not in this record's Owned paths, and
the file is a completed adjudication report - altering evidence documents is exactly what PROTOCOL
section 3 guards against, even for a one-line annotation.

The fix, for whoever owns it: append `<!-- pragma: allowlist secret - deterministic Red Team
reproduction output, not a credential -->` on that line, matching how
`tests/test_modeling_training_replay.py` annotates its pinned replay hashes. Alternatively exclude
`.launch/reports/` from the scan, though annotating is the narrower change.

Until then no full-gate run can pass, so no repair revision can be certified.

## Handoff notes for the `.launch/` owner

The peer session `quant-system-7c` ended before these could be delivered. Recording them here so
they survive.

1. **Minor 2 is an explicit accept, not a silent drop.** Record it in the evidence sheet with the
   rationale and residual risk under "Minor 2 - accepted, not repaired" above. A silently dropped
   finding fails the round; an argued accept does not.
2. **The pinned replay hashes did NOT move.** `tests/test_modeling_training_replay.py` passes
   unchanged, so the three manifest hashes at `b24b4eb` still reproduce. The adjudication brief
   (`a4f499c`) predicts they will change; that prediction is wrong and should be corrected before a
   Verifier reads it and treats a stable hash as suspicious.
3. **Slice 5 inheritance** - the question raised twice and never answered - is answered in "Note for
   Slice 5" below. Give it to the Red Team as a named starting point.
4. The focused suite widening (`5200741`) worked: the focused run went 91 to 123 tests and now
   executes all four of this round's new regression files.

## Note for Slice 5

The Red Team flagged that Slice 5's holdout inherits this fold machinery. Blocker 1's repair is
the one that matters there: `_validate_removed_rows` now requires every training label to mature
strictly before `validation_start`, which makes the purge set exactly derivable from the label
data rather than merely declared. The embargo's *lower* bound is still not derivable inside
`evaluate_governed_ridge_fold`, because it never receives the session calendar - a fold can still
declare `embargo_sessions=5` and remove nothing without that being visible from the label rows
alone. Anyone opening a holdout should either pass the calendar into the evaluator or re-derive
the embargo from `build_purged_fold` rather than trusting the declared spec.

## Decision rationale

Order follows `.launch/STATE.md`: Blocker 1 first because it is the only finding that corrupts the
fitted model rather than the evidence around it, and the Red Team flagged that Slice 5's holdout
inherits the same machinery.

Every repair starts from a failing regression test that reproduces the Red Team's documented attack,
so the fix is proven to bind rather than asserted to.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch` | PASS | Only uncommitted work is Antigravity `alpha/`, disjoint |
| `git worktree list` / `git branch --list` | PASS | Install root only, `main` only |
| `pytest tests/ -q` after Blocker 1 | PASS | 282 passed |
| `scripts/audit-disk-layout.ps1` | PASS | No stray QuantOS directories; 7 verification clones, 1 worktree entry |
| `scripts/audit-agent-claims.ps1` | PASS | 7 active records, no worktree or branch beyond the install root and `main` |
| `scripts/run-slice4-gates.ps1` (shared checkout) | PARTIAL | Every gate green except the application secret scan; 315 tests at 88.08%, focused suite 123 across 14 files |
| `pytest tests/ -q` after Blocker 2 | PASS | 282 passed |
| Blocker 2 mutation kill | PASS | Removing the re-derivation check turns the new tamper test red, restoring it turns it green |

## Files changed

- `src/quant_system/modeling/validation.py`: reject any training label maturing at or after
  `validation_start` (Blocker 1); require `label_horizon_sessions == LABEL_HORIZON_SESSIONS_V1`
  (Major 7).
- `src/quant_system/modeling/metrics.py`: new `strategy_report_from_records` re-derives a
  strategy report, its metrics, `metrics_hash`, and `prediction_hash` from published decisions.
- `src/quant_system/modeling/persisted_trials.py`: `_rebuild_strategy_reports` now re-derives
  each report and rejects a summary that does not bind its decision records (Blocker 2).
- `tests/modeling_training_fixtures.py`: `rebound_journey` and `leaky_zero_removal_fold`
  helpers reproducing the Red Team zero-removal fold attack.
- `tests/test_modeling_validation.py`: Blocker 1 and Major 7 regressions.
- `tests/test_modeling_evidence_tamper.py`: new. Blocker 2 forgery regression plus an
  honest-path guard.
- `agent_context/work/active/20260821-1048Z-claude-slice4-redteam-repair.md`: this record.

## Blockers and conflicts

### RESOLVED - concurrent edit collision with session `quant-system-7c [88e245]`

Discovered 2026-08-21T15:27Z while adding the Major 3 regression. Another interactive Claude
session on this machine is editing the same uncommitted files at the same time. `ListAgents`
shows it started roughly three minutes before discovery. It has **no visible active work
record** in `agent_context/work/active/`.

Evidence of the collision, all in the shared checkout:

1. `tests/test_modeling_validation.py` contains **two** definitions of
   `test_two_instruments_sharing_one_symbol_fail_closed` - one mine, one theirs.
2. We independently named the same new failure code differently:
   I added `ModelingFailureCode.DEGENERATE_RETURN_SERIES` to `errors.py`; their test asserts
   `ModelingFailureCode.DEGENERATE_NO_EXPOSURE`, which is not defined anywhere. The tree is
   therefore internally inconsistent right now.
3. `validation.py` carries both my `_return_moments` zero-variance guard and their
   `_require_deflatable_returns` call.
4. `tests/modeling_training_fixtures.py` contains their `symbol_collision_features` helper
   alongside my `rebound_journey` / `leaky_zero_removal_fold` helpers.

Their Major 3 repair in `validation.py` (a duplicate-key check when building `feature_index`)
is more complete than mine, which was still only a failing test.

Action taken, per PROTOCOL sections 3 and 7:

- Stopped all edits to `src/` and `tests/` immediately on discovery.
- Did **not** revert, stash, check out, or delete any of their work.
- Sent a collision notice to `quant-system-7c` naming this record, my claimed paths, the exact
  conflicting symbols, and what I have already completed, and proposed either a split of the
  remaining findings or that one agent stand down.
**Resolution, 2026-08-21T15:40Z.** `quant-system-7c` identified itself as the
`20260821-0530Z-claude-slice4-certification.md` record, acknowledged that its own Non-goals forbid
changing any `src/` or `tests/` file, and stood down from both trees. It reverted its
`DEGENERATE_NO_EXPOSURE` code, its `_require_deflatable_returns` call, and its duplicate test
definitions, and handed over its Major 3 repair plus the `symbol_collision_features` fixture.

Agreed split, now recorded in both directions:

| Owner | Paths |
|---|---|
| This record | `src/**`, `tests/**` - all remaining findings |
| `20260821-0530Z-claude-slice4-certification.md` | `.launch/**` - evidence, STATE, SLICES, COMMANDS, reports |

Their Major 3 repair was kept rather than replaced with mine: it is a real fix, mine was still only
a failing test. I mutation-killed it to confirm it binds - reverting the `feature_index` collision
check to the old dict comprehension turns
`test_two_instruments_sharing_one_symbol_fail_closed` red, restoring it turns it green.

Their handover also supplied the reason the Major 3 test is hard to write: rebuilding the poisoned
feature dataset moves its `dataset_hash`, so the label dataset no longer binds and the evaluator
stops at `TRAINING_INPUT_MISMATCH` before reaching the symbol join. Their fixture rebinds both
datasets; I found the start pins the label identity as well, so the test now rebinds the trial start
and its registry too and can assert `DATASET_INTEGRITY_INVALID` strictly.

No work was lost on either side. Nothing was reverted, stashed, or checked out by this agent.

## Stop point

Every Red Team finding in this record's scope is repaired or explicitly accepted, and the working
tree is green on every gate except the secret scan, whose single candidate is in a `.launch/` file
this record does not own.

Measured in the shared checkout via `scripts/run-slice4-gates.ps1 -PythonEnvironment .venv`:

| Gate | Result |
|---|---|
| Ruff lint | PASS |
| Ruff format | PASS - 222 files |
| Strict Mypy | PASS - 86 source files |
| Repository tests | PASS - 315 passed, 88.08% coverage |
| Slice 4 focused suite | PASS - 123 passed across 14 files |
| Dead-code scan | PASS |
| Application secret scan | **FAIL - 1 candidate in `.launch/reports/RED-TEAM-SLICE-04.md:89`** |
| Code Craft / Test Craft | exit 0 |

These figures come from a shared checkout that also carries uncommitted third-party Antigravity work
under `src/quant_system/alpha/`, whose tests are inside the 315. They are a working signal, **not** a
certification baseline. The honest figure must be re-measured from a clean detached clone at a
committed revision.

**Commit status.** This agent did not commit. The code and the first version of this record were
committed by another actor at `2556515` while this agent was running audits; the uncommitted
Antigravity `alpha/` work landed separately at `9b5a98a` rather than being swept in, which is the
correct separation. A peer session asked this agent to commit and was declined, because a peer
cannot authorise an action on the user's behalf. The later edits to this record - the secret-scan
diagnosis, the Minor 2 rationale, and the handoff notes - remain uncommitted.

Both mandatory pre-handoff audits pass at this revision:

```text
scripts/audit-disk-layout.ps1   RESULT: PASS - no stray QuantOS directories.
scripts/audit-agent-claims.ps1  RESULT: PASS - every workspace has a visible claim and every claim resolves.
```

## Next safe action

1. Founder authorises the commit. Stage explicitly - never `git add -A`, which would sweep in the
   uncommitted Antigravity `alpha/` work belonging to a third party:

   ```
   git add src/quant_system/modeling src/quant_system/evidence            tests/test_modeling_*.py tests/test_evidence_*.py            tests/modeling_training_fixtures.py            agent_context/work/active/20260821-1048Z-claude-slice4-redteam-repair.md
   ```

2. Annotate or exclude the secret-scan candidate in `.launch/reports/RED-TEAM-SLICE-04.md:89`. That
   file belongs to `20260821-0530Z-claude-slice4-certification.md`, so its owner or the founder
   should make the change, not this record.

3. Re-measure the full gate from a fresh detached clone at the committed revision via
   `scripts/new-workspace-clone.ps1`, and record those figures - not the shared-checkout ones.

4. Commission an independent Red Team recheck, then an independent clean-state Verifier, both at
   that revision. Neither may be this agent or the certification agent. G4 stays open and Slice 4
   must not be marked PASS until both have run and are recorded in `.launch/reports/`.
