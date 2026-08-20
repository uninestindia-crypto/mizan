---
name: deep-product-qa
description: Audit a completed codebase end to end through its real user interfaces, inventory every discovered product surface across web, mobile, desktop, backend, admin, workers, and integrations, measure evidence-backed coverage, and judge functional and consumer-experience quality. Use after implementation when a user requests whole-platform visual QA, human-like product testing, consumer journey review, pre-release acceptance, exhaustive functional testing, or a chronological audit-report-approve-fix-retest workflow. Produce the read-only audit first, pause for approval, then repair and fully regress only after approval.
---

# Deep Product QA

## Operating contract

Treat this as a release-verification workflow, not a code-review checklist. Derive scope from the entire codebase, then exercise the built product through real interfaces. Inspect code to discover what exists; do not use static inspection as proof that a feature works.

Follow these non-negotiable rules:

1. Run the phases in order. Complete the audit and deliver its report before changing product code.
2. Pause after the audit report. Start repairs only after the user explicitly approves Phase 2 for that run.
3. Do not rush, sample silently, or stop because the run is long. Record every discovered surface in the denominator.
4. Never call an unexecuted, blocked, inferred, or visually unobserved test passed.
5. Never hide unsupported platforms or unavailable tools. Keep them blocked and therefore incomplete.
6. Report measured coverage, not a promise of zero unknown defects. Testing cannot prove that no future customer will find another defect.
7. Use observable proxies for consumer response. Do not claim to know a person's feelings; state the likely perception and the evidence that supports it.
8. Restrict destructive tests to local or staging environments. Keep production read-only unless the user explicitly authorizes a precisely scoped action.
9. Require runtime evidence for every pass and every claimed fix.
10. Reopen scope whenever runtime exploration reveals a new route, state, role, integration, or platform. A falling percentage after discovery is honest progress.

## Load the right references

Read these files before executing the corresponding work:

- Read [references/coverage-model.md](references/coverage-model.md) before creating the inventory or reporting percentages.
- Read [references/platform-execution.md](references/platform-execution.md) before discovering, building, or launching applications.
- Read [references/test-catalog.md](references/test-catalog.md) before expanding the test matrix or running tests.
- Read [references/experience-review.md](references/experience-review.md) before visual, usability, delight, trust, or emotional-experience review.
- Read [references/report-contract.md](references/report-contract.md) before producing Phase 1 or Phase 2 reports.
- Read [references/safety.md](references/safety.md) before using credentials, changing data, exercising payments, contacting third parties, or touching production.

## Establish the run

Perform these steps without editing tracked product files:

1. Locate the project root and all nested applications or services.
2. Read repository instructions, `AGENTS.md`, readmes, manifests, environment examples, build scripts, CI configuration, schemas, and existing tests.
3. Identify local, test, staging, and production targets. Default to local or staging.
4. Identify available UI-control, emulator, simulator, browser, API, logging, database, accessibility, and profiling tools.
5. Create an artifact directory outside tracked source when possible. Store discovery output, coverage state, screenshots, recordings, logs, traces, reports, and diffs there.
6. Set the current phase to `audit`. Do not make product changes during this phase.

Use the bundled discovery helper as the first deterministic pass:

```bash
python3 <skill-dir>/scripts/discover_codebase.py \
  --root <project-root> \
  --output <run-dir>/codebase-discovery.json
```

Treat its output as leads, not complete scope. Manually verify the topology and add anything it misses.

Initialize the coverage ledger:

```bash
python3 <skill-dir>/scripts/qa_progress.py init \
  --state <run-dir>/coverage.json \
  --project <project-name>
```

Keep a single ledger for the entire run. Display its summary after every substantial test batch and whenever the user asks for progress.

## Build the scope inventory

Inventory before testing. Traverse the whole repository rather than only the current application directory.

Create explicit coverage items for every applicable combination of:

- application, service, package, platform, build variant, and entry point;
- route, page, screen, window, tab, menu, command, deep link, and notification destination;
- public, authenticated, administrative, support, and system role;
- permission, entitlement, subscription tier, feature flag, locale, theme, and relevant configuration;
- primary journey, alternate route, validation failure, empty/loading/error/success state, interruption, recovery, and retry;
- API operation, background job, webhook, queue, scheduled task, import/export, migration, and external integration;
- supported device class, orientation, input method, viewport/breakpoint, browser, operating system, and accessibility mode.

Derive intended behavior from product copy, documentation, types, schemas, route definitions, tests, commit-local requirements, and surrounding code. Code describes implementation, not necessarily correct product intent. Record uncertain expectations as assumptions; do not silently turn them into passes.

Use stable hierarchical IDs such as `web.customer.checkout.card-decline-retry`. Split a test whenever one part could pass while another fails. Do not create a single item named “test checkout” for a multi-step, multi-state journey.

Add each item to the ledger. Assign criticality from customer and business consequence, not implementation complexity:

```bash
python3 <skill-dir>/scripts/qa_progress.py add \
  --state <run-dir>/coverage.json \
  --id web.customer.checkout.card-decline-retry \
  --title "Customer can recover from a declined card" \
  --category journey \
  --criticality critical \
  --platform web \
  --surface storefront \
  --role customer
```

Complete three discovery passes before freezing the initial denominator:

1. **Structural pass:** infer surfaces from files, manifests, routes, schemas, roles, flags, and integrations.
2. **Runtime pass:** traverse all reachable UI, menus, deep links, role-specific areas, and state-dependent branches.
3. **Behavior pass:** inspect network calls, logs, persistence, workers, and external effects to expose hidden flows.

Write a non-empty artifact describing the work, findings, commands, and remaining scope for each pass. Complete the three ledger milestones:

```bash
python3 <skill-dir>/scripts/qa_progress.py set-milestone \
  --state <run-dir>/coverage.json \
  --name structural_discovery \
  --evidence <run-dir>/discovery-structural.md

python3 <skill-dir>/scripts/qa_progress.py set-milestone \
  --state <run-dir>/coverage.json \
  --name runtime_discovery \
  --evidence <run-dir>/discovery-runtime.md

python3 <skill-dir>/scripts/qa_progress.py set-milestone \
  --state <run-dir>/coverage.json \
  --name behavior_discovery \
  --evidence <run-dir>/discovery-behavior.md
```

Continue discovery throughout the run. Add newly found items immediately and explain any percentage change.

## Phase 1 — Audit without repairs

### 1. Prove the product can start

Use documented repository commands and CI configuration before inventing new commands. Install only task-relevant dependencies. Build and launch every discovered application or service needed for realistic use.

Record build failures, missing configuration, unavailable accounts, unsupported host platforms, and tool limitations as defects or blockers. A successful compile is not a successful product test.

### 2. Run automated baselines

Run applicable existing lint, type, unit, integration, contract, end-to-end, accessibility, and build checks. Preserve exact commands and logs.

Use automated results to find risk and support evidence. Do not let unit or snapshot tests replace real-interface execution. Do not repair failing tests during Phase 1.

### 3. Exercise real consumer journeys

Operate the product through the interface a consumer actually receives:

1. Start with a black-box first-use pass before correlating problems with code.
2. Execute every primary journey from clean state to durable outcome.
3. Repeat for every applicable role, permission, platform, and configuration.
4. Exercise alternate, invalid, empty, loading, error, interrupted, resumed, duplicate, and recovery paths.
5. Verify the visible result, persisted data, downstream side effects, logs, and behavior after refresh, restart, backgrounding, or relaunch.
6. Return to the same journey through navigation, deep links, notifications, browser history, and other supported entry points.

Do not click mechanically. At every step ask: “Would a first-time consumer know what happened, what to do next, and whether the action succeeded?”

### 4. Perform the visual and experience review

Capture stable screenshots or recordings at representative and defective states. Inspect hierarchy, spacing, alignment, typography, contrast, responsiveness, touch targets, focus, motion, feedback, copy, consistency, trust, perceived quality, and recovery.

Run the persona and quality-dimension method in `references/experience-review.md`. Separate:

- objective defects, such as clipping, overlap, unreadable text, broken controls, lost data, or inaccessible focus;
- evidence-backed usability risks, such as unclear labels or high-friction sequencing;
- subjective preferences, which must not be reported as defects without product requirements or repeated evidence.

Never allow attractive visuals to compensate for broken behavior. Functional correctness is a prerequisite for delight.

### 5. Run compatibility, resilience, and edge passes

Apply all relevant sections of `references/test-catalog.md`. Include boundary values, slow/failing networks, restarts, concurrency, repeated actions, permissions, time and locale effects, accessibility, responsive breakpoints, install/upgrade, migration, resource pressure, integration failure, and recovery.

For native mobile or desktop applications, use an emulator, simulator, or device and exercise the rendered application. If the required runtime is unavailable, mark those items blocked; do not substitute a code review.

### 6. Record proof immediately

For each executed item, set exactly one status:

- `passed`: observed expected behavior with evidence;
- `failed`: reproduced a defect with evidence;
- `blocked`: could not execute, with a concrete reason and unblocking action;
- `in_progress`: currently executing;
- `not_started`: not yet executed.

Require a screenshot, recording, log, trace, persisted-state check, or reproducible observation for passed and failed items. Prefer two evidence types for critical journeys.

Never attach a screenshot, source file, or arbitrary log directly to a coverage status. First wrap one or more runtime artifacts in the structured evidence format. The helper records build, environment, platform, scenario, expected/actual behavior, hashes the canonical metadata and every artifact, and records artifact sizes:

```bash
python3 <skill-dir>/scripts/qa_progress.py record-evidence \
  --output <run-dir>/evidence/web-checkout-decline.json \
  --kind screenshot \
  --build <tested-build-id> \
  --environment staging \
  --platform web \
  --scenario "Customer retries checkout after card decline" \
  --expected "Cart remains intact and retry can complete" \
  --actual "Retry returns to an empty cart" \
  --artifact <run-dir>/evidence/checkout-decline.png
```

Use only runtime evidence records for `passed` and `failed`. Static source inspection may create a risk hypothesis or scope item, but it cannot satisfy the status gate.

```bash
python3 <skill-dir>/scripts/qa_progress.py set-status \
  --state <run-dir>/coverage.json \
  --id web.customer.checkout.card-decline-retry \
  --status failed \
  --evidence <run-dir>/evidence/web-checkout-decline.json \
  --notes "Retry returns to an empty cart"
```

After each batch, run:

```bash
python3 <skill-dir>/scripts/qa_progress.py summary \
  --state <run-dir>/coverage.json
```

### 7. Complete the audit gate

Finish every inventory item as `passed`, `failed`, or `blocked`. Audit completion may reach 100% with failures or blockers; verified coverage may not.

Validate the ledger and generate its dashboard:

```bash
python3 <skill-dir>/scripts/qa_progress.py validate \
  --state <run-dir>/coverage.json \
  --gate audit

python3 <skill-dir>/scripts/qa_progress.py report \
  --state <run-dir>/coverage.json \
  --output <run-dir>/coverage-dashboard.md
```

Produce the Phase 1 report exactly as specified in `references/report-contract.md`. Include defects, consumer impact, evidence, coverage by category and platform, assumptions, blockers, and a release verdict. Register the non-empty report as a milestone, set the phase to `awaiting_approval`, show the report, and stop:

```bash
python3 <skill-dir>/scripts/qa_progress.py set-milestone \
  --state <run-dir>/coverage.json \
  --name audit_report \
  --evidence <run-dir>/audit-report.md

python3 <skill-dir>/scripts/qa_progress.py set-phase \
  --state <run-dir>/coverage.json \
  --phase awaiting_approval
```

Do not change code while waiting. Ask the user to approve Phase 2.

## Phase 2 — Repair, retest, and regress

Begin only after explicit approval following the current Phase 1 report. Save a concise, non-secret record of that approval in the run artifacts, complete the approval milestone, and only then advance the phase:

```bash
python3 <skill-dir>/scripts/qa_progress.py set-milestone \
  --state <run-dir>/coverage.json \
  --name phase2_approval \
  --evidence <run-dir>/phase2-approval.md

python3 <skill-dir>/scripts/qa_progress.py set-phase \
  --state <run-dir>/coverage.json \
  --phase repair
```

### 1. Preserve the baseline

Keep the original report, evidence, ledger history, and reproduction steps. Check the working tree and preserve unrelated user changes. Do not erase or rewrite evidence to make the repaired product appear cleaner.

Confirm the phase is `repair` before editing product code. The ledger rejects inventory and status mutations while awaiting approval or after completion.

Treat completed ledgers and all generated reports as immutable history. Create a new run or new report path instead of overwriting them.

### 2. Repair by risk and dependency

Fix root causes in this order unless dependencies require otherwise:

1. safety, security, privacy, data-loss, payment, and access-control defects;
2. launch blockers and broken critical journeys;
3. incorrect data, persistence, integration, and recovery behavior;
4. accessibility and compatibility failures;
5. usability friction and misleading feedback;
6. visual polish and delight.

Make the smallest coherent change that resolves the cause. Add or improve automated regression tests where practical, but retain real-interface verification as the acceptance gate.

### 3. Verify each repair

For every defect:

1. reproduce the original failure before or against preserved evidence;
2. apply the repair;
3. rerun the exact failing scenario through the real interface;
4. test adjacent states, roles, platforms, and dependent journeys;
5. inspect logs, persistence, and external effects;
6. replace the coverage status with `passed` only when new evidence proves it;
7. record newly exposed defects as new inventory items rather than hiding them under the original ID.

### 4. Run full regression

After targeted repairs pass, rerun every inventory item—not only changed-code tests. Rebuild every application, repeat visual sweeps, and compare repaired states with the Phase 1 evidence. Reopen discovery for routes or behavior introduced by repairs.

Do not declare completion based only on changed tests, static analysis, or a clean build.

### 5. Apply the release gate

After recording every final regression result, identify the exact candidate build and store the complete post-final-change regression evidence. Complete these milestones last; later inventory or status changes automatically invalidate them:

```bash
python3 <skill-dir>/scripts/qa_progress.py set-milestone \
  --state <run-dir>/coverage.json \
  --name final_build_identity \
  --evidence <run-dir>/environment.md

python3 <skill-dir>/scripts/qa_progress.py set-milestone \
  --state <run-dir>/coverage.json \
  --name full_regression_after_final_change \
  --evidence <run-dir>/full-regression.log
```

Run:

```bash
python3 <skill-dir>/scripts/qa_progress.py validate \
  --state <run-dir>/coverage.json \
  --gate release
```

Declare `READY` only when all of these are true:

- audit completion is 100%;
- verified coverage is 100%;
- all seven chronological run milestones are 100% complete;
- every in-scope item is passed with valid evidence;
- no failed, blocked, in-progress, or not-started item remains;
- every critical journey has current post-repair runtime evidence;
- full regression has run after the final product change;
- the build being reported is the build actually tested.

If any condition is false, report `NOT READY` or `CONDITIONALLY READY` and show the precise remaining percentage, items, risks, and unblocking actions. Never round a value below 100% up to 100%.

Produce the Phase 2 report from `references/report-contract.md`. Explain that 100% means all inventoried checks passed, not that unknown future defects are impossible.

## Low-capability-model guardrails

When uncertain, follow these deterministic rules instead of improvising:

1. If it was discovered, add it to the ledger.
2. If it was not executed, do not pass it.
3. If it was not visibly or behaviorally observed, do not call it visual or functional proof.
4. If evidence is missing, downgrade the status from passed.
5. If a tool or environment is missing, block the item and state the exact need.
6. If expected behavior is ambiguous, record an assumption and test consistency; do not invent a requirement silently.
7. If a repair changes behavior, retest the entire dependent journey and then full regression.
8. If a new surface appears, increase the denominator even when progress falls.
9. If production is the only target, run read-only scenarios and block destructive ones.
10. If any release-gate condition fails, do not say ready.
