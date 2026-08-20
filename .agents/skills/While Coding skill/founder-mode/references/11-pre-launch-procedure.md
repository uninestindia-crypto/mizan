# 11 - Pre-launch Procedure

Use this file as the single ordered entry point for a production release. It sequences the detail
in `03-gates.md`, `04-test-matrix.md`, `05-hardening.md`, and `06-launch-runbook.md`; it does not
replace their exit bars.

The pre-launch verdict is binary:

- `READY`: every required step from 1 through 14 passed against the same immutable revision.
- `BLOCKED`: any required result failed, was not tested, is stale, or lacks evidence.

Never use `READY WITH NOTES`. Record a tier-permitted `NOT APPLICABLE` result with its reason and
veto holder. Never mark a critical-path, money, auth, tenancy, data-integrity, migration, rollback,
or production-safety requirement not applicable merely to protect a date.

## Contents

- [Rules before starting](#rules-before-starting)
- [The ordered procedure](#the-ordered-procedure)
- [What testing means](#what-testing-means)
- [Automated gate runner](#automated-gate-runner)
- [Evidence ledger](#evidence-ledger)
- [Go or no-go](#go-or-no-go)
- [Tier scaling](#tier-scaling)

## Rules before starting

1. Read and apply repository instructions and domain skills first.
2. Confirm that the request authorizes the intended actions. A readiness review does not authorize
   repository writes, live migrations, deployments, alert drills, production access, or rollback.
3. Select the tier from `10-scaling.md` and name the veto holder for G7.
4. Discover and verify project commands through `08-bootstrap.md`; never guess commands.
5. Create or update the evidence ledger only when project-state writes are authorized.
6. Redact secrets and personal data from every stored log. Keep the complete safe failure output.
7. Stop on the first required failure. Fix it, create a regression test, and restart every affected
   downstream step on the new revision.

## The ordered procedure

### 1. Confirm scope and acceptance

- Freeze the release scope and non-goals.
- Map every acceptance criterion and failure state to a test or human check.
- Name the two to five critical user journeys and the measurable launch success signal.
- Record the release tier, owners, veto holders, window, and abort condition.

**Pass evidence:** approved scope, criteria-to-test map, critical journeys, and named owners.

### 2. Bind one source revision

- Record the full commit identifier and release artifact digest.
- Verify the candidate comes from a clean checkout and that generated artifacts match it.
- Reject evidence produced from a different revision or from an unidentified working tree.
- Freeze feature work; admit only Blocker fixes and restart affected verification after each fix.

**Pass evidence:** immutable revision, clean-tree output, artifact digest, and freeze log.

### 3. Prove clean setup and environment contracts

- Install dependencies from lockfiles in a fresh environment.
- Validate language and toolchain versions.
- Start from an empty datastore when the product has persistence.
- Validate required configuration, permissions, quotas, service reachability, and secret presence
  without printing secret values.
- Build and start the production-mode artifact locally or in CI.

**Pass evidence:** exact commands, exit statuses, safe raw output, and environment-contract result.

### 4. Run static and build checks (R0)

- Run typecheck, lint, format check, dead-code detection, secret scan, dependency audit, and build.
- Require zero findings, or enforce the explicitly approved baseline policy in `04-test-matrix.md`.
- Treat warnings hidden in successful exit codes as findings.

**Pass evidence:** command output and finding counts for every configured R0 check.

### 5. Run unit tests (R1)

- Exercise every branch and boundary of changed domain logic.
- Cover money, time, permissions, parsing, units, and idempotency with the part-specific cases in
  `04-test-matrix.md`.
- Break one important implementation deliberately and confirm its test fails before restoring it.

**Pass evidence:** passing results plus mutation or watched-failure proof for critical logic.

### 6. Run contract tests (R2)

- Pin API requests, responses, errors, events, schemas, public exports, and configuration contracts.
- Test authentication, authorization, role matrices, and cross-tenant read and write isolation.
- Prove consumers cannot observe an accidental incompatible boundary change.

**Pass evidence:** contract output and the explicit auth/tenancy matrix where applicable.

### 7. Run integration and data tests (R3)

- Run real module wiring against the real test datastore and real constraints.
- Apply migrations from zero and test old-code/new-schema compatibility when rolling deploys occur.
- Test transactions, concurrency, retries, duplicate delivery, and partial failure.
- Execute rollback in an isolated realistic environment when data or schema changes are involved.

**Pass evidence:** integration output, migration transcript, rollback transcript, and timings.

### 8. Run critical journeys end to end (R4)

- Start from an empty account and real runtime.
- Run every critical journey through the UI, API, CLI, or worker boundary users actually use.
- Verify success, the specified failure states, refresh/retry behavior, and persisted outcomes.
- Confirm the test would fail when a critical step is intentionally broken.

**Pass evidence:** per-journey transcript, screenshots where useful, and persisted-state assertions.

### 9. Attack the integrated system (R5)

- Run all twelve attack families in `05-hardening.md`, emphasizing seams between slices.
- Inject dependency timeouts, 429/500 responses, malformed data, expired sessions, dropped networks,
  duplicate actions, and concurrent writes.
- Run security review, dependency scanning, secret scanning, and abuse/authorization probes.
- Fix every finding with a regression test or obtain a written founder risk acceptance where the
  gate permits one.

**Pass evidence:** ranked red-team report, reproductions, dispositions, and regression tests.

### 10. Prove non-functional budgets (R6)

- Measure latency, throughput, memory, bundle size, load, and soak at realistic volume.
- Run accessibility tooling and the required keyboard, zoom, contrast, screen-reader, viewport,
  motion, and platform checks for user interfaces.
- Exercise internationalization, timezones, degraded networks, capacity, and cost guardrails where
  they apply.
- Compare numbers with budgets written before the measurement.

**Pass evidence:** measured results against pre-agreed numeric budgets, not impressions.

### 11. Complete human QA and UAT (R7)

- Have Customer Zero begin from an empty account without the rehearsed path.
- Complete product-owner acceptance against the criteria and project design law.
- Test supported real devices, browsers, operating systems, and assistive technology.
- Walk loading, empty, error, offline, stale, partial, permission-denied, and overflow states.
- Confirm support can answer the five most likely questions from the supplied documentation.

**Pass evidence:** UAT signoff, friction log, device matrix, accessibility walkthrough, and support
readiness result. Automated tests do not substitute for this step.

### 12. Rehearse in a production-like environment

- Deploy the exact candidate to production-like staging only with the required authorization.
- Run the full critical path there with production-like configuration and data volume.
- Time migrations and longest locks on a production-scale copy.
- Rehearse the numbered runbook and rollback with a different actor executing it.
- Re-run affected steps after every candidate change.

**Pass evidence:** staging revision, critical-path output, migration and rollback timings, and dry-run
transcript.

### 13. Prove recovery and operational readiness

- Capture current production baselines and set numeric promote, hold, and rollback thresholds.
- Take a backup and restore it to a separate isolated environment when persistent data is affected.
- Deliberately fire every release-critical alert and confirm a named human receives it.
- Confirm dashboards, logs, quotas, on-call coverage, support brief, status communication, and the
  rollback decision maker.
- Confirm the rollback remains valid against the current production state.

**Pass evidence:** baseline numbers, thresholds, restore proof, per-alert receipt, crew list, and
runbook.

### 14. Hold the go/no-go gate (G7)

- Walk every G7 item in `03-gates.md` and link its evidence.
- Require zero open Blockers and zero unaccepted Majors.
- Confirm every result belongs to the frozen revision and every required actor has signed off.
- Record `READY` or `BLOCKED`; never infer approval and never waive a gate for the founder.

**Pass evidence:** signed decision record with revision, open-risk list, and all G7 links.

### 15. Launch in stages and watch (R8)

Enter this step only after step 14 is `READY` and deployment is explicitly authorized.

- Follow the stages and minimum holds in `06-launch-runbook.md`.
- Run the production smoke suite after every stage and compare metrics with the baseline.
- Stop, hold, or roll back immediately when a pre-agreed threshold triggers.
- Preserve evidence before cleanup and never improvise an unrehearsed recovery during an incident.
- Record checks at T+1h, T+6h, T+24h, T+48h, and T+72h; then complete G9.

**Pass evidence:** rollout timeline, smoke output per stage, metrics, incident log, watch log, and
postmortem. Step 15 completes the release; it is not evidence that steps 1-14 were optional.

## What testing means

Do not collapse these disciplines into one "QA" label:

| Discipline | Main question | Founder Mode evidence |
|---|---|---|
| Static analysis | Can tooling find structural defects before execution? | R0 |
| Unit testing | Does isolated logic handle every important branch and boundary? | R1 |
| Contract testing | Will boundaries remain compatible and authorized? | R2 |
| Integration testing | Do real modules, migrations, constraints, and transactions work together? | R3 |
| End-to-end testing | Can users complete the critical journeys in the real runtime? | R4 |
| Adversarial/security testing | How does the integrated system break or get abused? | R5 |
| Non-functional testing | Does it meet measured performance, load, accessibility, and resilience budgets? | R6 |
| Human QA/UAT | Can a stranger use it, and does the owner accept it? | R7 |
| Production verification | Does the released system remain healthy under real traffic and time? | R8 |

## Automated gate runner

Use `scripts/run-prelaunch-gates.mjs` only for reviewed, deterministic R0-R6 commands in local,
test, or CI environments. Do not use it for manual checks or stateful release operations.

Create `.launch/prelaunch-gates.json` from verified commands in `COMMANDS.md`:

```json
{
  "schemaVersion": 1,
  "release": "release-name",
  "revision": "0123456789abcdef0123456789abcdef01234567",
  "environment": "local",
  "requireCleanTree": true,
  "evidencePath": ".launch/evidence/release-name-automated.md",
  "gates": [
    {
      "id": "r0-typecheck",
      "ring": "R0",
      "name": "Typecheck",
      "command": "corepack pnpm typecheck",
      "cwd": ".",
      "safety": "read-only-check",
      "required": true,
      "timeoutSeconds": 900
    }
  ]
}
```

Run it from the repository root:

```text
node <founder-mode-skill>/scripts/run-prelaunch-gates.mjs --root . --config .launch/prelaunch-gates.json
```

Before running, read every configured command. Do not put credentials or secret values in the
config. The release-specific config may remain untracked because it contains the frozen revision;
the runner excludes only that exact file from the untracked-file check and records its SHA-256
digest. Every other product or generated source file must be clean.

The runner verifies the revision, config digest, and clean product tree; refuses production
environments and known deployment/destructive commands; runs gates in file order; stores redacted
output; and stops at the first failure. Its safeguards are defense in depth, not authorization.

The runner can prove only the automated portion of steps 3-10. Record `NOT TESTED` for every
required automated check that has no configured command. Never let an automated `PASS` clear steps
1-2 or 11-15.

## Evidence ledger

When state writes are authorized, write `.launch/PRELAUNCH.md` and keep one row per step:

```markdown
# PRE-LAUNCH - <release>

Revision: <full commit>
Artifact digest: <digest>
Tier: <T0-T4>
Decision owner: <name>

| Step | Verdict | Owner | Evidence | Notes |
|---:|---|---|---|---|
| 1 | PASS | <name> | <link or command output> | |
| 2 | BLOCKED | <name> | git could not identify HEAD | Stop here |
| 3-15 | NOT TESTED | | | Blocked by step 2 |

Overall: BLOCKED
```

Use only `PASS`, `BLOCKED`, `NOT TESTED`, or tier-permitted `NOT APPLICABLE`. Identify the complete
artifact when raw output is too large to embed. Never paste secrets or personal data.

## Go or no-go

Declare `READY` only when the decision record answers all of these with evidence:

1. What exact revision and artifact will launch?
2. What user scope and non-goals are frozen?
3. Which R0-R7 results passed on that revision?
4. Are there zero Blockers and zero unaccepted Majors?
5. What production baselines and numeric thresholds control promotion and rollback?
6. How long did migration, rollback, backup restore, and alert delivery take in rehearsal?
7. Who executes, watches, decides rollback, communicates, and holds each veto?
8. What is the staged rollout sequence and 72-hour watch schedule?

If any answer is missing, stale, or qualitative where a number is required, declare `BLOCKED`.

## Tier scaling

Keep all fifteen rows visible at every tier so omissions cannot hide:

- **T0-T1:** compress unchanged areas. Run R0 and affected tests, smoke the affected critical path,
  verify rollback and monitoring, and explain each permitted `NOT APPLICABLE` row.
- **T2:** run steps 1-11. If the change enters production, also run steps 12-15; a production
  destination makes release mechanics applicable regardless of feature size.
- **T3:** run all steps uncompressed with different Build, Break, and Prove actors.
- **T4:** run all steps twice where `10-scaling.md` requires independent verification, with the
  founder present at every gate.

Anything on a critical path requires R0-R8 above T0. Tier changes ceremony, not the pass bar for
applicable safety requirements.
