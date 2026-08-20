# Codebase Discovery and Platform Execution

## Contents

1. Discovery order
2. Repository topology
3. Command selection
4. Environment preparation
5. Web applications
6. Android and cross-platform mobile
7. Apple applications
8. Desktop applications
9. Command-line and developer-facing interfaces
10. Backend, APIs, workers, and data
11. Integrations and multi-service systems
12. Unsupported runtime handling
13. Build identity and reproducibility

## 1. Discovery order

Perform all three passes:

1. **Structural discovery:** inspect the entire codebase.
2. **Runtime discovery:** launch every app and traverse every reachable interface.
3. **Behavior discovery:** inspect calls, persistence, logs, background work, and external effects.

Use `scripts/discover_codebase.py` for structural leads. It deliberately ignores generated dependency/build folders and does not parse every routing convention. Verify its output manually.

Do not begin with a single obvious frontend and assume it is the product. Monorepositories commonly contain customer web, admin web, mobile apps, desktop shells, APIs, workers, shared packages, infrastructure, and prototypes with different release status.

## 2. Repository topology

Inspect, in order:

- repository and nested `AGENTS.md` instructions;
- readmes, product docs, architecture notes, and contribution guides;
- workspace files and dependency manifests;
- build, run, test, release, and package scripts;
- CI/CD workflows and deployment manifests;
- route, navigation, screen, window, and menu declarations;
- auth, role, permission, entitlement, and feature-flag definitions;
- schemas, migrations, seed data, fixtures, and factories;
- API descriptions, controllers, handlers, GraphQL resolvers, RPC definitions, and clients;
- queues, workers, cron/scheduled jobs, webhooks, notifications, and deep links;
- localization resources, themes, platform variants, and build flavors;
- existing unit, integration, contract, end-to-end, visual, accessibility, and performance tests.

Build a topology table:

| Application/service | Root | Platform | Start/build command | Dependencies | Roles | Release status | Testability |
|---|---|---|---|---|---|---|---|

Do not treat demo, storybook, test harness, internal admin, or migration tool as customer-facing without evidence. Do not exclude it silently either; label its status and reason.

## 3. Command selection

Choose commands in this precedence order:

1. repository instructions;
2. package scripts, task runners, or make targets;
3. CI commands known to work;
4. framework-standard commands only when the repository provides no answer.

Never rewrite lockfiles, upgrade dependencies, or change product configuration merely to make Phase 1 easier. Record environment incompatibility as a blocker or defect. Installing locked dependencies and creating external QA artifacts are allowed when within task scope.

Preserve exact commands, working directories, environment names, exit codes, and log paths.

## 4. Environment preparation

Before launch:

1. Classify the target as local, test, staging, or production.
2. Use documented environment examples; never print secrets.
3. Identify required databases, object stores, queues, mail/SMS sinks, payment sandboxes, and third-party services.
4. Create isolated test users and data in local/staging when authorized.
5. Record unavailable credentials or services as blockers.
6. Confirm clocks, locale, timezone, and seed data when behavior depends on them.
7. Confirm whether feature flags and subscription entitlements can be exercised.
8. Capture the source revision and dirty working-tree state without discarding user changes.

Run the product in the same configuration consumers receive whenever possible. Development-only behavior can hide packaging, caching, permission, and production-build defects.

## 5. Web applications

Discover:

- server-rendered, client-rendered, static, PWA, embedded, admin, and marketing applications;
- file-system routes and programmatic routers;
- middleware, auth guards, layouts, error boundaries, and redirects;
- API routes, service workers, manifests, offline caching, and install behavior;
- browser support statements and responsive breakpoints;
- analytics, consent, payment, chat, map, upload, and identity integrations.

Execute through a controllable browser. For each supported browser class and relevant viewport:

- load from a clean profile;
- traverse with pointer, keyboard, and touch emulation when applicable;
- inspect console errors, failed requests, redirects, cookies/storage, and accessibility tree;
- test refresh, back/forward, duplicate tabs, deep links, expired sessions, and restored state;
- test CSS breakpoints at the breakpoint, one pixel below, and one pixel above;
- test long content, zoom, text scaling, reduced motion, dark mode, and high-contrast settings when supported;
- test install/offline/update behavior for PWAs.

Derive the viewport matrix from the product's CSS and support policy. If none exists, include narrow phone, common phone, tablet, laptop, and wide desktop widths. Do not declare cross-browser coverage after testing only a Chromium development browser.

## 6. Android and cross-platform mobile

Recognize Android native, React Native, Expo, Flutter, Capacitor, Cordova, Kotlin Multiplatform, and other mobile roots from manifests and build files.

Use an emulator or physical device capable of rendering and interacting with the actual application. Test:

- clean install, first launch, update install, relaunch, and uninstall/reinstall behavior;
- supported API levels, phone/tablet classes, portrait/landscape, cutouts, and system bars;
- touch, gestures, hardware/software back, keyboard appearance, focus, and autofill;
- permissions denied, allowed, limited, revoked, and changed in system settings;
- deep links, app links, notifications, share targets, file/camera/gallery pickers, and external intents;
- background/foreground, process death, low memory, interrupted flows, and state restoration;
- offline, slow, switching, captive, and failed network behavior;
- battery/resource pressure and long-running/background work where applicable;
- accessibility services, font scaling, display scaling, screen reader labels, and touch target sizes;
- store/release build differences, signing-dependent capabilities, and architecture variants when in scope.

For cross-platform code, do not assume Android and iOS behave the same. Shared source reduces implementation duplication; it does not prove platform equivalence.

## 7. Apple applications

Recognize iOS, iPadOS, macOS, watchOS, tvOS, Swift packages, Xcode workspaces/projects, and cross-platform Apple targets.

Use an appropriate simulator or device. Test applicable items from the mobile list plus:

- safe areas, dynamic type, VoiceOver, appearance changes, and platform navigation conventions;
- universal links, keychain/session behavior, privacy permission prompts, background tasks, and handoff;
- keyboard, pointer, multitasking, split view, and stage/window resizing on iPad;
- entitlement-, signing-, push-, in-app-purchase-, and device-only behavior using authorized sandbox facilities;
- clean install, upgrade, migration, restore, and app lifecycle transitions.

If the host cannot run the required Apple toolchain, keep Apple runtime items blocked. A successful cross-platform web or Android run is not iOS proof.

## 8. Desktop applications

Recognize Electron, Tauri, .NET desktop, native macOS/Windows/Linux, Java, Qt, Flutter desktop, and packaged web shells.

Test the packaged application, not only its development web view. Cover:

- installation, launch, single/multiple instance, update, rollback, uninstall, and retained data;
- window size, minimum size, maximize/fullscreen, multiple monitors, scaling, and high DPI;
- keyboard navigation and shortcuts, menus, context menus, tray/dock behavior, notifications, and file associations;
- file open/save, drag/drop, clipboard, printing, downloads, protocol/deep links, and OS permission prompts;
- offline/reconnect, sleep/wake, process crash/restart, update interruption, and state restoration;
- platform theme, accessibility services, screen readers, reduced motion, and text scaling;
- sandbox boundaries, auto-update signing, architecture, and supported OS versions.

Test every supported operating system or keep the untested one blocked. Development mode does not prove package behavior.

## 9. Command-line and developer-facing interfaces

Treat shipped CLIs, command palettes, SDK examples, local agents, and developer consoles as real product surfaces when discovered.

Inventory every command, subcommand, positional argument, flag, configuration source, environment variable, input/output format, and exit-code contract. Test:

- help at root and subcommand levels, version output, missing/unknown arguments, and conflicting options;
- valid, boundary, malformed, empty, Unicode, large, and piped input;
- stdout versus stderr, machine-readable output, terminal/no-terminal behavior, and stable exit codes;
- relative/absolute paths, missing files, permissions, symlinks, path collisions, and existing output handling;
- interactive prompts, non-interactive/CI mode, cancellation, signals, and partial-write recovery;
- config precedence, environment isolation, secret redaction, and platform-specific paths;
- repeated/concurrent invocation, idempotency, locks, and atomic output;
- install/package entry points and supported shell/operating-system behavior;
- completed-state immutability and explicit confirmation for overwrites or destructive actions.

Run commands in an isolated temporary directory and preserve exact commands, outputs, exit codes, and resulting files. Source inspection can suggest cases; it does not pass them.

## 10. Backend, APIs, workers, and data

Map every externally or internally invoked operation:

- REST, GraphQL, RPC, WebSocket, streaming, and file-transfer interfaces;
- authentication, authorization, rate limits, idempotency, pagination, validation, and error contracts;
- workers, queues, retries, dead-letter behavior, scheduled jobs, email/SMS/push, exports, and webhooks;
- schemas, constraints, migrations, transactions, caching, search indexes, and object storage;
- admin/support operations and audit logs.

Verify both through the consumer UI and directly at the service boundary when useful. UI success without persisted or downstream success is a failure. Direct API success without consumer UI success does not pass the consumer journey.

Exercise malformed input, missing/expired authorization, duplicate requests, concurrency, ordering, partial downstream failure, timeout, retry, and recovery. Avoid uncontrolled load or security exploitation; follow task scope and safety rules.

For migrations, test representative existing data, forward migration, application compatibility, rollback only when supported, and data integrity afterward. Never test destructive migration scenarios against production.

## 11. Integrations and multi-service systems

Create an integration inventory with owner, environment, credentials, sandbox availability, inbound/outbound operations, failure modes, retry behavior, and observable evidence.

For each integration:

1. verify configuration is recognized without exposing secrets;
2. exercise the happy path in an authorized sandbox/local fake;
3. verify timeout, rejection, malformed response, rate limit, duplicate callback, and delayed callback behavior as applicable;
4. verify idempotency and recovery;
5. verify user-facing feedback and internal observability;
6. verify no real message, charge, shipment, or irreversible action occurs unintentionally.

For multi-service systems, start dependencies using documented orchestration. Confirm health checks are meaningful and verify actual cross-service journeys. “Container is running” is not evidence that the service works.

## 12. Unsupported runtime handling

When a required platform cannot run:

1. identify the exact missing runtime, device, account, permission, or service;
2. perform safe static discovery to understand risk, but do not mark runtime items passed;
3. mark each affected item blocked;
4. quantify the blocked weight and percentage;
5. state the minimum unblocking action;
6. keep the release verdict below `READY`.

Do not quietly narrow “whole platform” to the current host's capabilities.

## 13. Build identity and reproducibility

For every evidence batch, record:

- source revision and relevant uncommitted changes;
- application/service version;
- build flavor and environment;
- operating system/device/browser and version;
- build/start commands;
- configuration identifiers with secrets removed;
- test-data identity;
- timestamp;
- artifact paths.

After any product change, rebuild affected applications. Before the final verdict, run the full regression against one identified candidate build. If code changes after that regression, the release gate is no longer satisfied.
