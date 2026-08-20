# Whole-Platform Test Catalog

## Contents

1. Applying the catalog
2. Universal journey matrix
3. Launch, navigation, and lifecycle
4. Forms, input, and user data
5. Authentication, roles, and permissions
6. Core business workflows
7. Search, filtering, sorting, and discovery
8. Files, media, import, and export
9. Payments, subscriptions, and transactional actions
10. Notifications and communication
11. APIs, persistence, workers, and integrations
12. Failure, resilience, and recovery
13. Concurrency and repeated actions
14. Visual, responsive, and interaction states
15. Accessibility
16. Performance and resource behavior
17. Localization, time, and numeric behavior
18. Privacy, security, and trust checks
19. Installation, update, migration, and compatibility
20. Observability and supportability
21. Exploratory consumer passes
22. Completion check

## 1. Applying the catalog

Use this as a scope-expansion checklist, not as one giant test item.

For every section:

1. Decide whether it applies from codebase and runtime evidence.
2. If applicable, create atomic ledger items for each meaningful role/platform/state combination.
3. If not applicable, record the reason in the audit notes.
4. If uncertain, investigate; do not mark it inapplicable merely to reduce scope.
5. Execute through the real interface and verify downstream behavior.

Prioritize risk for execution order, but do not let priority remove lower-risk items from the inventory.

## 2. Universal journey matrix

Apply these states to every customer or operator journey when meaningful:

| Dimension | Cases |
|---|---|
| Entry | first launch, direct navigation, deep link, notification, restored session, referral |
| Identity | signed out, new user, returning user, expired session, suspended/deleted user |
| Permission | allowed, denied, limited, revoked during use, role changed during session |
| Data | valid, empty, minimum, maximum, boundary, malformed, duplicate, stale, deleted elsewhere |
| Network | normal, slow, offline, timeout, dropped mid-action, reconnect, partial downstream failure |
| Action | single, double/repeated, cancel, back, refresh, retry, resume, concurrent device/tab |
| Result | loading, empty, success, validation error, server error, partial success, delayed success |
| Lifecycle | background/foreground, browser reload, process restart, device rotation, app upgrade |
| Presentation | narrow/wide, zoom/text scale, light/dark, keyboard/touch, assistive technology |

For a critical journey, test at least the happy path, invalid input, interruption, retry/recovery, repeated action, persistence after restart, and every privileged role boundary.

## 3. Launch, navigation, and lifecycle

- Build every distributable target from a clean or documented state.
- Start every required service and verify real readiness, not only an open port.
- Launch from normal entry points, direct routes, deep links, associated files, and notifications.
- Verify first-run, returning-session, expired-session, and signed-out landing behavior.
- Verify every visible navigation item reaches the correct destination.
- Verify browser history, native back, breadcrumbs, tabs, menus, drawers, and modal dismissal.
- Verify unknown, removed, unauthorized, and malformed routes.
- Verify refresh/reload on nested routes and preservation of meaningful state.
- Verify background/foreground, sleep/wake, process death, relaunch, and restored navigation.
- Verify logout clears protected state and back navigation cannot reveal private content.
- Verify maintenance, version mismatch, required update, and unsupported-client behavior when implemented.

## 4. Forms, input, and user data

For every input:

- empty, whitespace-only, minimum, maximum, above maximum, and representative valid values;
- Unicode, emoji, combining marks, right-to-left text, pasted text, and line breaks when allowed;
- formatting, masks, autocomplete, autofill, copy/paste, keyboard type, and password-manager behavior;
- invalid syntax, wrong type, extreme number, negative/zero, decimal precision, and scientific notation when relevant;
- leading/trailing spaces, case sensitivity, duplicate values, and locale-specific formats;
- client validation, server validation, error placement, error wording, and focus movement;
- submit by primary control and keyboard action;
- double submit, slow submit, cancel, navigate away, refresh, and retry;
- saved result, displayed result, reload persistence, edit, undo/cancel, and deletion;
- unsaved-change warnings and draft recovery when intended.

Verify labels, required indicators, hints, units, defaults, and destructive confirmations. Ensure error messages preserve user input where safe and identify a recovery action.

## 5. Authentication, roles, and permissions

- Sign-up, verification, sign-in, sign-out, password reset, password change, and account recovery.
- Social/enterprise identity flows, callback failure, canceled consent, mismatched account, and revoked access.
- Valid, invalid, expired, reused, and already-consumed tokens or links.
- Session expiry while idle and during a critical action.
- Multiple sessions/devices, logout-all, credential change, and revoked session behavior.
- Every role's visible navigation, direct route access, API authorization, and data boundaries.
- Ownership changes, organization switching, invitations, removed members, and changed entitlements.
- Permission allowed, denied, limited, revoked in settings, and changed while open.
- Deleted, suspended, locked, unverified, or partially onboarded accounts.
- Sensitive actions requiring recent authentication or confirmation when specified.

Hiding a button is not authorization. Verify the service boundary rejects forbidden operations and that no protected data leaks in responses, cached screens, logs, or history.

## 6. Core business workflows

Identify the product's core promise from the codebase and product copy. Decompose each journey into entry, prerequisites, action, feedback, persisted outcome, downstream effect, revisit, edit/cancel, and recovery.

Test:

- new user and experienced user paths;
- default and alternate supported paths;
- prerequisites missing or completed out of order;
- partial completion, save/resume, cancel, and abandonment;
- success feedback and next-step guidance;
- edit, duplicate, archive, restore, and irreversible deletion when supported;
- downstream effects in every dependent service;
- history/audit record and user-visible status;
- consistency between customer, admin, support, and reporting views;
- lifecycle after refresh, logout/login, restart, and upgrade.

Any failure that prevents the core promise is critical unless evidence shows otherwise.

## 7. Search, filtering, sorting, and discovery

- Empty query, exact match, partial match, case, whitespace, typo, punctuation, Unicode, and no result.
- Relevant ranking, deterministic tie behavior, highlighting, and result counts.
- Each filter alone and meaningful combinations.
- Clear/reset, default state, persisted state, URL/deep-link state, and back navigation.
- Each sort direction, null/missing values, equal values, stable pagination, and newly changed data.
- Pagination/infinite scroll boundaries, duplicate/missing results, loading, retry, and end state.
- Permissions and tenant boundaries in results, suggestions, counts, and cached queries.
- Mobile keyboard and responsive controls.
- Accessibility names, focus order, and result announcements.

## 8. Files, media, import, and export

- Supported and unsupported type, correct/incorrect extension, MIME mismatch, empty file, corrupt file, and boundary size.
- Multiple files, duplicate names, cancel, retry, interrupted upload, and progress feedback.
- Camera/gallery/file-picker permission states and external provider failures.
- Preview, crop/edit, rotate, metadata, orientation, playback, captions, and download.
- Filename Unicode and reserved characters; path traversal strings must not escape intended storage.
- Virus/malware scanning behavior only through approved benign test mechanisms.
- Export with no data, typical data, maximum data, Unicode, locale formats, and correct permissions.
- Import validation, row-level errors, partial success policy, idempotent retry, rollback, and audit trail.
- Generated file opens in the intended consumer application and contains accurate data.

## 9. Payments, subscriptions, and transactional actions

Use authorized sandbox/test facilities only.

- Successful, declined, canceled, timed-out, pending, duplicated, and delayed payment.
- Retry with same and different payment method.
- Double click, browser refresh, app kill, callback replay, and network loss around authorization.
- Correct currency, amount, tax, discount, shipping, rounding, and displayed total at every step.
- Idempotency: one consumer action must not produce duplicate charge/order/refund.
- Order/status reconciliation after delayed or out-of-order webhooks.
- Refund, partial refund, cancellation, failure, and retry.
- Subscription start, trial, upgrade, downgrade, renewal, failed renewal, grace period, and cancellation.
- Entitlements before, during, and after state changes.
- Receipt/invoice accuracy and communication behavior.
- Customer, admin, ledger, and provider state agreement.

Never use a real charge merely because the interface permits it. A visually successful screen without provider and persisted-state agreement is a failure.

## 10. Notifications and communication

- In-app, push, email, SMS, webhook, and system notification variants found in code.
- Trigger accuracy, recipient/tenant correctness, content, locale, time, links, and data redaction.
- Permission allowed/denied, invalid destination, provider rejection, timeout, retry, duplicate prevention, and delayed delivery.
- Read/unread, badge counts, dismiss, mark all, pagination, and cross-device synchronization.
- Deep-link destination when signed in, signed out, expired, unauthorized, or content removed.
- Preference and unsubscribe behavior, including required transactional exceptions.
- Test sinks or sandboxes prevent accidental real communication.

## 11. APIs, persistence, workers, and integrations

For each operation:

- valid request and exact response contract;
- missing, malformed, extra, boundary, duplicate, and stale inputs;
- authentication, authorization, ownership, tenant isolation, and entitlement;
- pagination, filtering, sorting, versioning, content type, and encoding;
- error status/body consistency and absence of sensitive internal details;
- idempotency, retry, ordering, timeout, and rate-limit behavior;
- transaction boundaries and rollback on partial failure;
- cache freshness and invalidation;
- persistence, constraints, search index, object storage, and audit record;
- queue enqueue, worker processing, retry schedule, dead-letter state, and replay;
- webhook signature/identity checks through safe test facilities, duplicate callback, and out-of-order callback;
- graceful behavior when an integration is slow, invalid, unavailable, or recovers.

Correlate UI action, API call, persistence, worker, external effect, and final UI state for critical journeys.

## 12. Failure, resilience, and recovery

- Service unavailable before launch and during active use.
- DNS/connectivity failure, latency, timeout, disconnect, reconnect, and response truncation.
- Database unavailable, transaction conflict, stale replica, cache unavailable, queue unavailable, and storage failure through controlled test mechanisms.
- Malformed or schema-incompatible downstream response.
- Partial multi-step success and compensation/rollback.
- Crash, forced termination, browser reload, device restart, and process restart.
- Expired session or changed permission mid-action.
- User retry, automatic retry, retry exhaustion, and recovery after dependency restoration.
- Clear status, preserved safe work, no duplicate effect, and actionable recovery guidance.

Never inject faults into production. In local/staging, use reversible, controlled mechanisms and restore the environment afterward.

## 13. Concurrency and repeated actions

- Rapid double click/tap and repeated keyboard submission.
- Same action from two tabs, windows, devices, or users.
- Simultaneous edits, stale versions, conflict resolution, and last-write policy.
- Duplicate callbacks, jobs, imports, uploads, payments, and retries.
- Ordering changes and delayed events.
- Locking, uniqueness, idempotency, and user feedback.
- Refresh or navigation while an operation is pending.

Verify both visible outcome and backend invariants. “Only one toast appeared” does not prove only one transaction occurred.

## 14. Visual, responsive, and interaction states

- Every route/screen in loading, empty, typical, dense/long, error, success, disabled, selected, focused, hovered, pressed, and validation states.
- Narrow phone, common phone, tablet, laptop, and wide desktop where web applies.
- Every source-defined breakpoint at one pixel below, at, and one pixel above.
- Portrait/landscape, cutouts/safe areas, browser chrome, software keyboard, and resized windows.
- Zoom and text scaling; long words, translated text, large numbers, and user-generated content.
- Light/dark/high-contrast themes and system changes while open.
- Alignment, grid, spacing, typography, wrapping, truncation, overlap, clipping, scrolling, layering, and sticky elements.
- Icons, images, placeholders, aspect ratio, loading, failure, and high-density rendering.
- Motion start/end state, reduced motion, interruption, repeated activation, and performance.
- Pointer, touch, keyboard, stylus, and screen-reader feedback where supported.

Capture evidence at stable states. Hide or redact personal data and secrets.

## 15. Accessibility

- Semantic structure and meaningful accessible names.
- Complete keyboard navigation and visible focus.
- Logical focus order and focus restoration after modal/navigation changes.
- Screen-reader announcements for errors, loading, dynamic updates, and success.
- Labels, instructions, error association, required state, and programmatic roles/states.
- Color contrast and non-color cues.
- Text zoom, font scaling, reflow, orientation, and spacing.
- Touch/pointer target size and adequate separation.
- Captions, transcripts, alt text, and controls for time-based media.
- Reduced motion and flashing limits.
- Timeout warning/extension and accessible authentication.
- Platform accessibility services on native apps.

Automated scanners are a baseline, not completion. Execute critical journeys with keyboard and appropriate assistive technology when available.

## 16. Performance and resource behavior

Measure, do not describe subjectively.

- Cold/warm launch, route/screen transition, interaction response, and critical journey timing.
- Slow network and low-capability device/CPU conditions representative of supported consumers.
- Large/maximum realistic data and long sessions.
- Memory, CPU, battery, disk, network, and bundle/download size where relevant.
- Scrolling, animation, typing, search, upload/download, sync, and background work.
- Cache effectiveness and stale behavior.
- Resource cleanup after navigation, cancellation, logout, and repeated journeys.
- Backend latency, throughput within authorized non-destructive limits, queue delay, and timeout budget.

Use product budgets when defined. Otherwise report measured values and consumer impact without inventing a universal pass threshold.

## 17. Localization, time, and numeric behavior

- Every shipped locale loads without missing keys or fallback leakage.
- Long translated text, right-to-left layout, mixed-direction content, and locale switching.
- Date/time, timezone, daylight-saving transition, midnight/month/year boundary, leap day, and relative-time wording.
- Currency, decimals, grouping, negative values, percentages, units, tax, and rounding.
- Name, address, phone, postal code, and sorting formats relevant to supported markets.
- Pluralization, grammar, truncation, search, export, notification, and server/client agreement.
- Locale/timezone change while a session or scheduled action exists.

## 18. Privacy, security, and trust checks

Keep checks non-destructive and within authorized scope.

- Sensitive data is not exposed to the wrong role, tenant, screen, URL, log, analytics event, notification, cache, history, or export.
- Protected routes and service operations enforce authorization.
- Secrets are absent from source-controlled client bundles and user-visible errors.
- Session/logout/revocation behavior is correct.
- Consent, privacy choices, data export, deletion, and retention UI work as implemented.
- External links, downloads, uploads, and user-generated content receive safe handling expected by the product.
- Destructive or high-impact actions communicate consequence and require suitable confirmation.
- Security/privacy messaging matches actual behavior and does not make unsupported claims.

Do not perform exploit development, uncontrolled scanning, denial of service, or access to other users' data. Escalate specialized security review when the product risk requires it.

## 19. Installation, update, migration, and compatibility

- Clean install/build from documented prerequisites.
- Upgrade from each supported prior version or representative migration baseline.
- Preserved settings, sessions, user data, files, and entitlements.
- Schema/data migration success, interruption, resume, and supported rollback.
- Required-update, optional-update, skipped-update, and version mismatch behavior.
- Package signing, permissions, architecture, OS/browser/device version, and store/release configuration.
- Uninstall/reinstall and expected retained/removed data.
- Backward/forward compatibility across clients and services during rollout when applicable.

## 20. Observability and supportability

- Errors produce useful, non-sensitive logs with correlation identifiers.
- Critical operations can be traced across UI, API, worker, and integration.
- Health/readiness checks reflect real dependency state.
- Metrics and alerts distinguish success, failure, retry, and backlog where implemented.
- Customer-visible reference codes map to support evidence without leaking internals.
- Admin/support tools show accurate state and enforce permissions.
- Audit logs capture high-impact actions with correct actor and time.

Observability does not replace customer-facing recovery, but its absence can make production failures materially harder to resolve.

## 21. Exploratory consumer passes

After scripted coverage, run fresh sessions without following code structure:

- first-time novice trying the core promise;
- returning user trying to finish quickly;
- hurried or distracted user making plausible mistakes;
- user with slow network or low-capability device;
- keyboard/screen-reader or large-text user;
- power user using shortcuts, bulk actions, and multiple windows/tabs;
- user returning after a long absence with stale state;
- support/admin resolving a failed customer journey.

Follow curiosity when the product behaves oddly. Add every newly exposed surface or state to the ledger.

## 22. Completion check

Before Phase 1 report, confirm:

- every applicable catalog section was considered;
- every discovered item is terminal (`passed`, `failed`, or `blocked`);
- unsupported sections are documented, not silently ignored;
- critical paths contain failure and recovery cases;
- runtime, persistence, and downstream effects were correlated;
- visual and accessibility passes used the rendered product;
- evidence identifies the tested build and environment;
- progress numbers come from the ledger.
