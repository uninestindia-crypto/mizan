# Coverage and Progress Model

## Contents

1. Purpose
2. Inventory unit
3. Status meanings
4. Fixed risk weights
5. Percentages
6. Scope revisions
7. Evidence rules
8. Gate rules
9. Progress communication
10. Ledger operations

## 1. Purpose

Use this model to answer two different questions honestly:

- **How much of the audit has been executed?**
- **How much of the product is currently verified and release-ready?**

Never collapse them into one number. A failed or blocked test is completed audit work, but it is not verified product coverage.

## 2. Inventory unit

Create one coverage item for one independently observable claim under one meaningful condition. A good item can be passed or failed without forcing a different behavior into the same status.

Good:

- `web.customer.sign-in.valid-password`
- `web.customer.sign-in.wrong-password-message`
- `android.customer.checkout.background-resume`
- `api.admin.refund.duplicate-request-idempotency`

Too broad:

- `test authentication`
- `test mobile app`
- `check all errors`

Every item must contain:

- stable ID;
- precise title;
- category;
- criticality;
- platform;
- product surface;
- role or actor;
- expected observable behavior when known;
- source of expectation when known;
- execution status;
- evidence for pass or failure;
- notes for assumptions, defects, or blockers.

Split across roles, permissions, platforms, states, and recovery paths when behavior can differ. Avoid useless multiplication: do not create separate items for combinations that the codebase and runtime prove equivalent. Record the equivalence evidence when collapsing them.

## 3. Status meanings

| Status | Meaning | Required proof |
|---|---|---|
| `not_started` | Discovered but not executed | Inventory source |
| `in_progress` | Execution has started but no verdict exists | Optional working evidence |
| `passed` | Expected behavior was observed on the tested build | Current runtime evidence |
| `failed` | A reproducible deviation or defect was observed | Runtime evidence and reproduction notes |
| `blocked` | Execution could not occur | Concrete blocker and unblocking action |

Do not use `blocked` for inconvenience or lack of time. Do not use `passed` for “code looks correct,” “test should pass,” or “another similar platform passed.”

## 4. Fixed risk weights

The bundled ledger assigns non-editable weights:

| Criticality | Weight | Use when failure could cause |
|---|---:|---|
| `critical` | 8 | safety/privacy breach, data loss, unauthorized access, incorrect payment, total launch failure, or inability to complete the product's core purpose |
| `high` | 5 | major journey failure, materially wrong data, unrecoverable user work, serious compatibility/accessibility failure, or broken key integration |
| `medium` | 3 | partial feature failure, confusing recovery, meaningful friction, inconsistent behavior, or important visual defect |
| `low` | 1 | minor polish, low-impact copy, small alignment issue, or rare non-blocking inconsistency |

Assign consequence, not developer effort. Do not lower criticality to improve the percentage. If uncertain between two levels, use the higher level until evidence supports the lower one.

## 5. Percentages

Let each item have weight `w`.

```text
total weight = sum(weight of every in-scope item)
terminal weight = sum(weight where status is passed, failed, or blocked)
passed weight = sum(weight where status is passed)

audit completion % = 100 × terminal weight / total weight
audit remaining % = 100 × (total weight − terminal weight) / total weight
verified coverage % = 100 × passed weight / total weight
remaining to release % = 100 × (total weight − passed weight) / total weight
```

Call this the **remaining item-coverage gap** in user-facing summaries. Track the seven chronological run milestones separately:

```text
milestone completion % = 100 × completed milestones / 7
milestone remaining % = 100 × incomplete milestones / 7
```

Do not average item coverage and milestone completion; that would create an arbitrary composite. A release requires both verified item coverage and milestone completion to reach 100%.

The helper truncates percentages to two decimals. It never rounds 99.99% to 100%.

If the inventory is empty, audit completion and verified coverage are 0%, while audit remaining and remaining to release are reported as 100%. This is an explicit initialization convention; an empty inventory is never complete.

Example:

- one critical item passed: weight 8;
- one high item failed: weight 5;
- one medium item blocked: weight 3;
- one low item not started: weight 1.

Then:

- total weight = 17;
- audit completion = 16/17 = 94.11%;
- verified coverage = 8/17 = 47.05%;
- remaining to release = 9/17 = 52.94%.

Also report raw item counts by status. Weighted percentages alone can hide many low-severity polish failures.

## 6. Scope revisions

Treat the denominator as provisional until structural, runtime, and behavioral discovery have run. After that, keep it open when new evidence appears.

When adding scope after testing starts:

1. Add the new item immediately.
2. State what revealed it.
3. Recalculate every percentage.
4. Explain any decrease as expanded verified scope, not lost work.
5. Never delete a valid item merely to improve progress.

Remove or merge an item only when it is genuinely duplicate or proven out of scope. Record the reason in run notes outside the ledger before removal; prefer retaining it with a note when audit history matters.

## 7. Evidence rules

Accept evidence that can independently support the stated observation:

- screenshot with route/screen and state context;
- short recording of interaction and result;
- UI automation trace tied to the build;
- command and complete test log;
- network request/response with secrets removed;
- application or system log with timestamp and scenario;
- accessibility tree or audit output;
- database or persisted-state verification;
- performance trace or measured timing;
- emulator/device details and build identifier.

For a critical journey, prefer at least two complementary forms, such as a recording plus persisted-state verification.

Evidence must identify the tested build, platform/configuration, scenario, and time. A screenshot of a final screen alone may not prove how the user reached it or whether data persisted.

The ledger accepts only structured runtime-evidence JSON records created with `qa_progress.py record-evidence`. Each record must identify the build, environment, platform, scenario, expected/actual behavior, and at least one existing non-empty artifact. The helper hashes every attached artifact and the canonical record metadata; validation rejects later alteration or deletion.

Static source files, manifests, assumptions, and an agent's bare assertion are not runtime evidence. Source inspection can create an inventory item or risk hypothesis, but it cannot satisfy `passed` or `failed`.

When changing `failed` to `passed`, attach new post-repair evidence. Historical failure evidence remains valid history and must not be removed.

## 8. Gate rules

### Audit gate

Pass only when:

- at least one inventory item exists;
- structural, runtime, and behavioral discovery milestones have evidence;
- every item is `passed`, `failed`, or `blocked`;
- every pass/failure has evidence;
- every blocker has a reason and unblocking action;
- coverage is reported by category and platform.

The audit gate can pass while the product is not ready.

### Release gate

Pass only when:

- the audit gate passes;
- every item is `passed`;
- verified coverage is exactly 100%;
- current runtime evidence exists after the final relevant change;
- full regression was executed against the build being released.
- the audit report, Phase 2 approval, final build identity, and post-final-change regression milestones have evidence.

No waiver, accepted defect, or unsupported platform equals a pass. If the user deliberately accepts residual risk, report `CONDITIONALLY READY` and retain the item as failed or blocked.

## 9. Progress communication

Show this compact block during work:

```text
Phase: Audit
Inventory: 428 items
Audit completion: 61.44% (38.56% unexecuted)
Verified coverage: 49.06% (50.94% item coverage remaining to release)
Passed 216 | Failed 19 | Blocked 7 | In progress 4 | Not started 182
Current focus: Android checkout interruption and recovery
Scope change: +12 items discovered from notification deep links
Run milestones: 3/7 (42.85% complete; 57.14% remaining)
```

Do not estimate completion from elapsed time or agent confidence. Use the ledger.

## 10. Ledger operations

Use `scripts/qa_progress.py` for deterministic calculations.

Useful commands:

```bash
python3 <skill-dir>/scripts/qa_progress.py summary --state <run-dir>/coverage.json
python3 <skill-dir>/scripts/qa_progress.py list --state <run-dir>/coverage.json --status failed
python3 <skill-dir>/scripts/qa_progress.py list --state <run-dir>/coverage.json --status blocked
python3 <skill-dir>/scripts/qa_progress.py validate --state <run-dir>/coverage.json --gate audit
python3 <skill-dir>/scripts/qa_progress.py validate --state <run-dir>/coverage.json --gate release
```

Create structured runtime evidence before setting a pass/failure:

```bash
python3 <skill-dir>/scripts/qa_progress.py record-evidence \
  --output <run-dir>/evidence/<case-id>.json \
  --kind log \
  --build <build-id> \
  --environment <local-or-staging> \
  --platform <platform> \
  --scenario <scenario> \
  --expected <expected-observation> \
  --actual <actual-observation> \
  --artifact <run-dir>/evidence/<runtime-log>
```

Complete chronological run milestones with `set-milestone`. Milestone evidence may be a non-empty report, discovery record, approval record, environment record, or regression log; it does not substitute for item-level runtime evidence.

For bulk inventory, create a JSON list with the same fields accepted by `add`, then use:

```bash
python3 <skill-dir>/scripts/qa_progress.py import-items \
  --state <run-dir>/coverage.json \
  --input <run-dir>/inventory-items.json
```

Do not edit weights manually. The validator rejects weight changes that disagree with criticality.
