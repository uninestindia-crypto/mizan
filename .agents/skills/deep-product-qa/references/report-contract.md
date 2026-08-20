# Audit and Repair Report Contract

## Contents

1. Reporting principles
2. Severity model
3. Evidence package
4. Phase 1 audit report
5. Approval gate
6. Phase 2 repair report
7. Release verdicts
8. Progress updates during work

## 1. Reporting principles

Lead with the release outcome and customer risk. Make every claim traceable to a coverage item and evidence.

Separate:

- discovered scope;
- executed audit work;
- verified product behavior;
- failed behavior;
- blocked or unsupported behavior;
- subjective opportunities;
- untested unknowns.

Do not bury blockers in appendices. Do not say “mostly working” without percentages and risk context. Do not equate automated test count with customer coverage.

Preserve both reports. Phase 2 supplements Phase 1; it does not rewrite history.

Never overwrite an existing report or coverage ledger. Use a new run or versioned report path when another artifact is required.

## 2. Severity model

Assign severity from observed customer/business consequence:

| Severity | Meaning | Examples |
|---|---|---|
| P0 — Stop release | Catastrophic or unsafe; immediate broad harm | data loss, unauthorized sensitive access, incorrect real transaction, app cannot launch |
| P1 — Critical | Core promise or high-consequence journey fails with no acceptable recovery | cannot authenticate, checkout cannot complete, destructive duplicate action |
| P2 — Major | Important feature, role, platform, accessibility path, or recovery is materially broken | admin cannot resolve order, iOS deep links fail, form loses user work |
| P3 — Moderate | Product works but creates meaningful friction, inconsistency, or localized visual failure | unclear error recovery, responsive overlap on one range |
| P4 — Minor | Low-impact polish or copy issue | small spacing inconsistency, non-blocking wording issue |

Do not lower severity because a fix is difficult. Criticality weights in the ledger and defect severity should normally align; explain exceptions.

## 3. Evidence package

Organize run artifacts so another person can reproduce the verdict:

```text
<run-dir>/
├── codebase-discovery.json
├── coverage.json
├── coverage-dashboard.md
├── audit-report.md
├── repair-report.md                 # Phase 2 only
├── environment.md
├── commands/
├── evidence/
│   ├── records/                 # structured runtime-evidence JSON
│   ├── screenshots/
│   ├── recordings/
│   ├── logs/
│   ├── traces/
│   ├── accessibility/
│   └── performance/
└── defects/
```

Use relative links between the report and artifacts when possible. Redact credentials, personal data, tokens, payment information, and unrelated user content.

Every pass/failure link must resolve through a structured runtime-evidence record whose attached artifact hashes still validate. Never cite a source manifest as execution proof.

Record in `environment.md`:

- tested source revision and uncommitted-change summary;
- application versions/build identifiers;
- target environments;
- devices, OS versions, browsers, emulators, and simulators;
- commands and configuration identifiers;
- test accounts/data identifiers without secrets;
- known tool limitations.

## 4. Phase 1 audit report

Create `audit-report.md` with this exact top-level order.

### 1. Release verdict

State `NOT READY`, `CONDITIONALLY READY`, or `READY FOR PHASE-1 BASELINE ONLY`. Phase 1 does not authorize release merely because the audit completed.

Include:

- one-sentence outcome;
- audit completion percentage;
- verified coverage percentage;
- remaining item-coverage percentage;
- run milestone completion and remaining percentages;
- counts of P0–P4 defects;
- blocked item count and weight;
- most important customer risk;
- tested build/environment identity.

### 2. Progress dashboard

Embed or link `coverage-dashboard.md`. Show overall and by:

- platform/application;
- category;
- role when materially different;
- critical journey group.

Explain denominator changes discovered during the run.

### 3. Product topology and scope

List every discovered app, service, platform, role, route/screen group, integration, and background system. Mark each as tested, failed, blocked, or not applicable with reason.

State what the codebase could not establish about product intent or supported environments.

### 4. Critical journey results

For each core journey show:

| Journey | Role/platform | Happy path | Failure/recovery | Persistence/downstream | Experience | Evidence |
|---|---|---|---|---|---|---|

Do not use one green result to conceal a failed recovery or platform variant.

### 5. Defects by severity

Give every defect a stable ID and this complete record:

| Field | Required content |
|---|---|
| ID and title | Stable identifier and concrete failure |
| Severity | P0–P4 with consequence rationale |
| Ledger items | Affected coverage IDs |
| Build/environment | Exact tested target |
| Platform/role/state | Conditions required to reproduce |
| Preconditions | Data, account, and starting state |
| Steps | Minimal deterministic reproduction |
| Expected | Observable intended behavior and source |
| Actual | Observable behavior |
| Customer impact | Task, trust, data, money, access, or recovery consequence |
| Evidence | Relative links to screenshot/recording/log/trace |
| Recurrence | Reproduction count and variability |
| Scope | Known adjacent surfaces potentially affected |
| Likely source | Code location or subsystem, explicitly labeled as hypothesis |
| Fix direction | Concise approach, not an unapproved code change |

Group P0/P1 first. Keep usability, trust, accessibility, visual, and functional findings distinguishable.

### 6. Consumer experience scorecard

Use the 0–5 dimensions from `experience-review.md`. Report per critical journey and platform where results differ.

For each score include evidence and why it is not one point higher. Mark untested dimensions `N/T`.

Include:

- first-impression observations;
- likely confidence/confusion/anxiety/frustration triggers;
- trust-breaking inconsistencies;
- delight strengths;
- delight opportunities separate from defects;
- questions that require real target-user research.

### 7. Compatibility, accessibility, performance, and resilience

Report actual matrices and measured results. List untested browser/OS/device/runtime combinations as blockers or explicit out-of-scope decisions, never as implicit passes.

### 8. Blockers, assumptions, and blind spots

For every blocker state:

- affected scope and weight;
- exact reason;
- what was attempted;
- minimum unblocking action;
- risk of release without the test.

List ambiguous requirements and the assumption used. Explain that codebase-derived intent can reproduce an implementation mistake and may require product-owner confirmation.

### 9. Prioritized repair plan

Order proposed work by customer risk and dependency. For each batch state defects addressed, expected affected surfaces, likely files/subsystems, targeted verification, and required full-regression impact.

Do not implement this plan in Phase 1.

### 10. Approval request

End with a clear pause:

```text
Phase 1 is complete. No product repairs were made.
Approve Phase 2 to repair the confirmed defects, retest them through the real interfaces, and run the full regression.
```

After writing the report, register it as the `audit_report` milestone before advancing to `awaiting_approval`.

## 5. Approval gate

Treat only a clear approval after delivery of the current audit report as authorization for Phase 2. Earlier statements that the user eventually wants fixes define the workflow but do not waive this gate.

Save the approval as a concise run artifact and register the `phase2_approval` milestone. The ledger must reject the transition to `repair` without it.

If the user narrows or changes repair scope, retain all unapproved findings in the ledger. They prevent a full `READY` verdict.

## 6. Phase 2 repair report

Create `repair-report.md` with this top-level order.

### 1. Final release verdict

State `READY`, `CONDITIONALLY READY`, or `NOT READY`. Include audit completion, verified coverage, remaining item coverage, milestone completion/remaining, unresolved counts, build identity, and final regression timestamp.

### 2. Change summary

For each repair batch list:

- defect IDs;
- root cause;
- files/subsystems changed;
- behavior change;
- automated regression added or updated;
- risk and adjacent areas retested.

Preserve unrelated user changes and disclose any unavoidable interaction.

### 3. Defect verification matrix

| Defect | Original reproduction | Repair | Exact retest | Adjacent retest | Status | New evidence |
|---|---|---|---|---|---|---|

Use `passed` only with post-repair runtime evidence. Keep reopened or partially fixed defects unresolved.

### 4. Full regression results

Report the complete ledger, not only changed areas. Show overall, category, platform, role, and critical-journey results. State when the denominator grew and why.

### 5. Before/after experience comparison

For visual or usability repairs, show matched state/device evidence and explain the customer effect. Do not use unmatched screenshots to imply improvement.

### 6. Remaining risks and blockers

List every non-passed item. If none remain, state that all inventoried checks passed while acknowledging that testing cannot prove the absence of unknown future defects.

### 7. Reproduction package

Provide commands, artifact links, environment identity, and any ongoing manual checks needed for release operations.

Register `final_build_identity` and `full_regression_after_final_change` only after all final item statuses are recorded. A later inventory or status mutation invalidates them and requires a new candidate build/regression record.

## 7. Release verdicts

Use these definitions consistently:

- **READY:** release gate passes; every inventoried item passed with evidence on the final tested build.
- **CONDITIONALLY READY:** user explicitly accepts known failed/blocked scope or a non-critical environment gap. State conditions and residual risk. Verified coverage remains below 100%.
- **NOT READY:** any P0/P1 remains, core behavior is not verified, destructive/high-risk scope is untested, or remaining risk is not explicitly accepted.
- **READY FOR PHASE-1 BASELINE ONLY:** audit is complete and suitable to begin repairs; this is not a production release verdict.

Never output `READY` when verified coverage is below 100%.

## 8. Progress updates during work

Provide concise updates at meaningful milestones and at least often enough that a long-running task does not appear abandoned.

Use:

```text
Phase: Repair
Audit completion: 100.00%
Verified coverage: 84.27%
Remaining item coverage to release: 15.72%
Passed 361 | Failed 21 | Blocked 4 | In progress 6 | Not started 0
Current work: P1 checkout idempotency repair and adjacent order regression
New scope: +5 items from delayed webhook handling
Next gate: verify payment retry, then full multi-platform regression
Run milestones: 5/7 (71.42% complete; 28.57% remaining)
```

Do not provide time-based percentages, invented ETAs, or optimistic completion claims unsupported by the ledger.
