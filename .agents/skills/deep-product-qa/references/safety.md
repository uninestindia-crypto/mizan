# QA Environment and Action Safety

## Contents

1. Environment policy
2. Action classification
3. Credentials and secrets
4. Test data and privacy
5. Payments and commerce
6. Messages, notifications, and external effects
7. Fault injection and load
8. Production testing
9. Repair safety
10. Cleanup and evidence retention

## 1. Environment policy

Use this precedence:

1. isolated local environment;
2. dedicated test environment;
3. staging environment with test data;
4. production only for authorized read-only observation.

Destructive, state-corrupting, fault-injection, payment, messaging, migration, permission-boundary, and bulk-data tests must run only in local/test/staging unless the user explicitly authorizes a narrowly described live action and the surrounding authorization policy permits it.

Do not interpret access as permission. Do not infer that a staging-looking URL is safe; verify the environment.

## 2. Action classification

Classify each planned action:

| Class | Examples | Default |
|---|---|---|
| Read-only | navigate public pages, view own test data, inspect logs already authorized | Allowed in identified target |
| Reversible test mutation | create/edit/delete isolated test record, upload test file | Local/test/staging only |
| External side effect | send email/SMS/push, call webhook, create shipment, publish content | Use sink/sandbox; otherwise obtain explicit authorization |
| Financial | authorize/capture/refund payment, purchase subscription | Provider sandbox/test mode only by default |
| Destructive/high impact | migration, bulk delete, role escalation test, fault injection, load test | Local/test/staging with exact target and recovery plan |
| Sensitive access | other users' data, secrets, privileged production records | Do not access without explicit scope and authorization |

When uncertain, block the scenario and state the minimum safe test facility required.

## 3. Credentials and secrets

- Use only task-relevant credentials already configured or explicitly supplied for the test.
- Never print, commit, embed, or include secrets in screenshots, logs, reports, command output, URLs, or evidence filenames.
- Prefer environment variables, secret stores, and test accounts.
- Redact authorization headers, cookies, API keys, session tokens, password-reset links, and signed URLs.
- Do not copy credentials between environments to bypass configuration.
- Do not repurpose or extract unrelated credentials.
- If a required account is missing, continue safe coverage and mark affected items blocked.

## 4. Test data and privacy

- Prefer synthetic data that is clearly identifiable as test data.
- Use the minimum data necessary for the scenario.
- Never use real personal, medical, financial, or customer data merely for realism.
- Avoid capturing unrelated user content in screenshots or recordings.
- Redact personal data before presenting or persisting evidence.
- Verify tenant and ownership boundaries using authorized isolated accounts, not real customers.
- Record test-data identifiers so mutations can be cleaned up without broad deletion.
- Preserve evidence needed for reproducibility while minimizing sensitive content.

## 5. Payments and commerce

- Confirm provider sandbox/test mode before entering any test instrument.
- Use documented test cards/accounts and non-fulfilling catalog/order settings.
- Prevent real capture, shipment, inventory reservation, tax filing, or accounting entry.
- Verify amount, currency, idempotency, provider state, internal state, and receipt in the sandbox.
- Test refunds and disputes only through supported sandbox behavior.
- If a real transaction would be required, mark the scenario blocked unless the user gives explicit authorization and all applicable controls permit it.

Never assume a small amount makes an unauthorized live transaction acceptable.

## 6. Messages, notifications, and external effects

- Route email, SMS, push, webhooks, analytics, support tickets, and notifications to test sinks or allowlisted test destinations.
- Confirm recipient before any real person-directed action.
- Prevent public posts, customer invitations, password resets, marketing sends, and account alerts to unintended recipients.
- Label test messages clearly when a real test recipient is explicitly authorized.
- Verify payload/content through provider sandbox, capture tool, or local fake.
- Block the test if the external effect cannot be contained.

## 7. Fault injection and load

- Run network failure, dependency outage, corruption, clock shift, disk pressure, and process-kill scenarios only in controlled local/test/staging targets.
- Define the exact fault, affected service, start condition, stop condition, and recovery step.
- Confirm the environment can be restored before injection.
- Avoid uncontrolled fuzzing, denial of service, or security exploitation.
- Keep performance/load tests within explicit environment capacity and task scope.
- Observe recovery and verify no residual broken state remains.

## 8. Production testing

Default production scope is read-only:

- navigate public and explicitly authorized private surfaces;
- verify non-mutating rendering, navigation, headers, and existing status;
- do not create/delete data, trigger messages, exercise payments, change roles, upload files, replay callbacks, inject faults, or load-test;
- do not bypass protections to reach hidden or unauthorized data;
- redact production identifiers and customer content from evidence.

For every destructive scenario that cannot safely run in production, create or retain a blocked ledger item. A staging pass does not prove production configuration, but it can provide behavior evidence; state the distinction.

## 9. Repair safety

Before Phase 2 changes:

- confirm approval followed the current audit report;
- inspect the working tree and preserve unrelated user edits;
- follow repository instructions;
- avoid destructive version-control operations;
- keep changes scoped to confirmed defects and necessary tests;
- do not weaken validation, authorization, accessibility, privacy, or tests merely to make a failure disappear;
- rebuild and rerun the affected real-interface journey;
- run full regression after the final change.

If a repair requires new authority, live migration, credential use outside normal task configuration, or external coordination, stop and ask for direction.

## 10. Cleanup and evidence retention

After testing:

1. Stop locally launched processes when they are no longer needed.
2. Remove or archive isolated test data using precise identifiers.
3. Restore controlled fault settings and verify service health.
4. Revoke temporary test tokens/accounts when appropriate.
5. Retain reports, coverage state, redacted evidence, and reproduction logs.
6. Do not delete original failure evidence after repair.
7. Disclose any test data or external side effect that could not be cleaned up.

Never use broad deletion paths, unresolved variables, or production-wide cleanup commands.
