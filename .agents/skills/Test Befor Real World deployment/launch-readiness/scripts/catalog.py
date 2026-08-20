# -*- coding: utf-8 -*-
"""
catalog.py -- The Launch Readiness check catalog.

SINGLE SOURCE OF TRUTH. The reference docs explain HOW to run each check;
this file defines WHICH checks exist, their severity, and when they apply.

Entry format:
    (id, title, severity, tags, mode)

severity:
    S0  BLOCKER   -- launch is forbidden while this is failing or untested.
    S1  MAJOR     -- must be fixed, or waived in writing by the owner with a stated risk.
    S2  MINOR     -- should be fixed; may ship with a recorded follow-up.
    S3  ADVISORY  -- record the answer; no launch impact.

tags: applicability. A check applies if it is tagged "always" OR any of its
      tags is in the project profile. If none apply, the check auto-resolves
      to N/A with a recorded reason.

mode:
    cmd     -- ONLY provable by a recorded command execution (lrk run).
    manual  -- provable by observation; REQUIRES an attachment (screenshot/file)
               or a written finding. Never provable by a bare assertion.
    hybrid  -- either, depending on stack.
"""

SEVERITIES = {
    "S0": "BLOCKER  - launch forbidden while open",
    "S1": "MAJOR    - fix, or written waiver from the owner",
    "S2": "MINOR    - fix or record a dated follow-up",
    "S3": "ADVISORY - record the answer only",
}

# Tag glossary -- used by `lrk init` to build the project profile.
TAGS = {
    "always":     "Applies to every project without exception.",
    "web":        "Serves HTTP to a browser.",
    "api":        "Exposes an API consumed by another program.",
    "ui":         "Has a human-visible interface of any kind.",
    "db":         "Persists data in a database.",
    "auth":       "Has user accounts, login, or any authorization.",
    "multitenant":"More than one customer's data lives in the same system.",
    "payments":   "Moves money, computes prices, tax, credits, or quotas.",
    "mobile":     "Ships an iOS/Android/desktop app binary.",
    "cli":        "Ships a command-line tool.",
    "lib":        "Ships a library other developers import.",
    "queue":      "Has background jobs, workers, cron, or a message queue.",
    "thirdparty": "Calls an external service it does not control.",
    "upload":     "Accepts files from users.",
    "i18n":       "Ships in more than one language or locale.",
    "store":      "Distributed through an app store or marketplace.",
    "pii":        "Stores personal data about identifiable people.",
    "cloud":      "Runs on infrastructure you deploy and operate.",
}

GATES = [
    ("G0",  "Inventory & Command Map",
            "Nothing can be verified until we know what this is and which commands are real.",
            "Executor"),
    ("G1",  "Build & Static Integrity",
            "The artifact builds clean from zero and contains nothing it should not.",
            "Executor"),
    ("G2",  "Test Truth",
            "The test suite exists, is honest, and would actually catch a regression.",
            "Verifier"),
    ("G3",  "Functional Correctness & States",
            "Every promised behaviour works, including the eight ways it can go wrong.",
            "Verifier"),
    ("G4",  "Security",
            "A motivated stranger cannot read, write, or break what is not theirs.",
            "Security reviewer"),
    ("G5",  "Data & Migration Safety",
            "Data survives the deploy, the rollback, and the disaster.",
            "Data owner"),
    ("G6",  "Performance & Capacity",
            "It is fast enough at real volume, and we know where it breaks.",
            "Performance owner"),
    ("G7",  "Reliability & Failure Injection",
            "Every dependency has been killed on purpose and the system behaved.",
            "SRE"),
    ("G8",  "UX, Accessibility & Devices",
            "A real person on a real device, including one using a screen reader, can finish the job.",
            "Design owner"),
    ("G9",  "Privacy, Legal & Compliance",
            "Shipping this does not create a legal or ethical liability.",
            "Owner / counsel"),
    ("G10", "Operability",
            "When it breaks at 3am, a human is woken and knows exactly what to do.",
            "SRE"),
    ("G11", "Release Mechanics",
            "The deploy is rehearsed, the rollback is timed, and a stranger could run both.",
            "Release manager"),
    ("G12", "Launch & 72-Hour Watch",
            "The rollout was staged, watched, measured, and learned from.",
            "Release manager"),
]

CATALOG = [
    # ------------------------------------------------------------------ G0
    ("G0.01", "Version control clean: on a release branch/tag, no uncommitted changes, no untracked source", "S0", ["always"], "cmd"),
    ("G0.02", "Stack detected and written down: languages, frameworks, package managers, runtimes", "S0", ["always"], "cmd"),
    ("G0.03", "Command map discovered AND each command proven to actually execute (install/build/test/lint/typecheck/start/migrate/e2e)", "S0", ["always"], "cmd"),
    ("G0.04", "Clean-clone install from zero succeeds in an empty directory with no caches", "S0", ["always"], "cmd"),
    ("G0.05", "A stranger can get it running from the README alone -- no tribal knowledge", "S1", ["always"], "manual"),
    ("G0.06", ".env.example lists every variable; app fails LOUDLY at startup when one is missing", "S0", ["always"], "hybrid"),
    ("G0.07", "Dependency lockfile exists, is committed, and install is reproducible from it", "S0", ["always"], "cmd"),
    ("G0.08", "Runtime versions pinned (.nvmrc / .python-version / engines / toolchain file)", "S1", ["always"], "cmd"),
    ("G0.09", "Critical paths ('money paths') enumerated in writing -- between 2 and 5 of them", "S0", ["always"], "manual"),
    ("G0.10", "External dependency inventory: every third-party API, DB, queue, storage, mail, payment provider", "S0", ["always"], "manual"),
    ("G0.11", "Target environments enumerated: production URL(s), staging, regions, tenants", "S0", ["cloud", "web", "api"], "manual"),
    ("G0.12", "Cut line written: what is in v1.0 and what is explicitly NOT, agreed before verification starts", "S1", ["always"], "manual"),

    # ------------------------------------------------------------------ G1
    ("G1.01", "Production build succeeds from a clean state", "S0", ["always"], "cmd"),
    ("G1.02", "Build run twice produces an equivalent artifact -- no nondeterministic failures", "S2", ["always"], "cmd"),
    ("G1.03", "Type check passes with ZERO errors", "S0", ["always"], "cmd"),
    ("G1.04", "Lint passes with zero errors and zero warnings, or a recorded baseline with zero new", "S1", ["always"], "cmd"),
    ("G1.05", "Format check passes -- the committed code is the formatted code", "S2", ["always"], "cmd"),
    ("G1.06", "No TODO / FIXME / HACK / XXX / 'temporary' markers on any critical path file", "S1", ["always"], "cmd"),
    ("G1.07", "No debug artifacts shipped: console.log, print, debugger, pdb, binding.pry, alert()", "S1", ["always"], "cmd"),
    ("G1.08", "No large commented-out code blocks in shipped source", "S2", ["always"], "cmd"),
    ("G1.09", "Dead code, unused exports, and unused dependencies identified and removed", "S2", ["always"], "cmd"),
    ("G1.10", "Secret scan over the FULL git history (not just HEAD) finds zero live credentials", "S0", ["always"], "cmd"),
    ("G1.11", "No localhost / 127.0.0.1 / staging hostnames / test API keys reachable on a production code path", "S0", ["always"], "cmd"),
    ("G1.12", "Dependency vulnerability audit: zero CRITICAL, zero HIGH, or each one waived with reasoning", "S0", ["always"], "cmd"),
    ("G1.13", "License compliance: LICENSE present; no copyleft licence incompatible with how this ships", "S1", ["always"], "cmd"),
    ("G1.14", "No abandoned or known-malicious dependency on a critical path; every dep justified", "S1", ["always"], "hybrid"),
    ("G1.15", "Source maps / debug symbols policy decided and enforced -- production source is not published by accident", "S1", ["web", "mobile"], "hybrid"),
    ("G1.16", "Build artifact size measured against a written budget", "S2", ["always"], "cmd"),
    ("G1.17", "No .env file, private key, database dump, or real customer data committed to the repository", "S0", ["always"], "cmd"),
    ("G1.18", "Strict mode on: strict types, no blanket 'any'/'unsafe' escapes on critical paths, warnings-as-errors where supported", "S1", ["always"], "cmd"),

    # ------------------------------------------------------------------ G2
    ("G2.01", "A test suite exists and runs with one documented command", "S0", ["always"], "cmd"),
    ("G2.02", "Full suite passes from a CLEAN state: fresh dependencies, fresh database, migrations from zero", "S0", ["always"], "cmd"),
    ("G2.03", "Suite passes with tests in randomised order", "S1", ["always"], "cmd"),
    ("G2.04", "Suite passes twice in a row in the same environment -- no state bleed between runs", "S1", ["always"], "cmd"),
    ("G2.05", "Zero skipped / .only / .skip / xit / pending tests, or every one justified in writing", "S1", ["always"], "cmd"),
    ("G2.06", "SABOTAGE PROOF: three critical functions deliberately broken, a test went RED for each, code restored", "S0", ["always"], "cmd"),
    ("G2.07", "Coverage measured; coverage on critical-path files meets a written bar", "S1", ["always"], "cmd"),
    ("G2.08", "No assertion-free tests -- every test asserts on a value, not merely 'did not throw'", "S1", ["always"], "hybrid"),
    ("G2.09", "No branching logic (if/try-catch-as-control) inside tests", "S2", ["always"], "cmd"),
    ("G2.10", "Tests are deterministic: frozen clock, fixed seed, fixed IDs, no live network", "S1", ["always"], "hybrid"),
    ("G2.11", "Flake count is zero: suite run three times, identical results each time", "S1", ["always"], "cmd"),
    ("G2.12", "Unit tests cover every branch of domain logic per the part-type matrix", "S0", ["always"], "manual"),
    ("G2.13", "Contract tests pin every boundary: API request/response, DB schema, event payloads, error taxonomy", "S0", ["api", "lib", "queue"], "hybrid"),
    ("G2.14", "Integration tests run against a REAL database with real migrations, not mocks", "S0", ["db"], "cmd"),
    ("G2.15", "End-to-end test covers every critical path from a genuinely empty starting state", "S0", ["web", "ui", "api", "mobile"], "cmd"),
    ("G2.16", "Every bug ever found has a regression test that fails without its fix", "S1", ["always"], "manual"),
    ("G2.17", "Total suite runtime recorded and acceptable for the team's cadence", "S3", ["always"], "cmd"),
    ("G2.18", "CI runs the same commands as local, and CI is GREEN on the exact release commit", "S0", ["always"], "cmd"),

    # ------------------------------------------------------------------ G3
    ("G3.01", "Every acceptance criterion demonstrated one by one, with proof per criterion", "S0", ["always"], "manual"),
    ("G3.02", "All nine states implemented on every user-visible surface: default, loading, empty, error, partial/stale, disabled, offline, permission-denied, too-much-data", "S0", ["ui"], "manual"),
    ("G3.03", "First-run experience walked from a genuinely empty account -- no seed data, no pre-existing state", "S0", ["ui", "web", "mobile"], "manual"),
    ("G3.04", "Every form: client validation, server validation, inline field errors, and double-submit protection", "S0", ["ui", "web"], "manual"),
    ("G3.05", "Every destructive action has confirmation and either undo or a documented recovery path", "S0", ["ui", "api"], "manual"),
    ("G3.06", "List boundaries: zero results, one result, exact page boundary, past the last page, item inserted between page 1 and 2", "S1", ["api", "ui", "db"], "hybrid"),
    ("G3.07", "Money correctness: rounding both directions, zero, negative, maximum, precision, currency mixing, and NO floating point", "S0", ["payments"], "cmd"),
    ("G3.08", "Date/time correctness: DST both directions, offsets east and west, half-hour offsets, leap year, server tz != user tz != db tz", "S0", ["always"], "hybrid"),
    ("G3.09", "Unicode, emoji, right-to-left text, and 10,000-character strings accepted, stored, and rendered without corruption", "S1", ["always"], "hybrid"),
    ("G3.10", "Every mutating endpoint is idempotent, or documented as unsafe to retry with a client-side guard", "S0", ["api", "payments", "queue"], "hybrid"),
    ("G3.11", "Concurrency: two actors mutate the same resource at the same instant -- outcome is correct and deterministic", "S0", ["db", "api", "payments"], "hybrid"),
    ("G3.12", "Browser back, forward, and refresh mid-flow behave correctly; every screen is deep-linkable", "S1", ["web"], "manual"),
    ("G3.13", "Upload boundaries: empty file, 1 byte, max size, max+1, wrong magic bytes, hostile filename, interrupted upload", "S1", ["upload"], "hybrid"),
    ("G3.14", "Outbound email / push / SMS actually sends and renders correctly in a real client -- screenshot from a real inbox", "S1", ["thirdparty", "web", "mobile"], "manual"),
    ("G3.15", "Search: empty query, no results, special and regex characters, very long query, permission-filtered counts match visible rows", "S1", ["api", "ui"], "hybrid"),
    ("G3.16", "Every documented error code is reachable by a test and produces a message a user can act on", "S1", ["api"], "hybrid"),

    # ------------------------------------------------------------------ G4
    ("G4.01", "Every protected route enumerated and tested unauthenticated -- all deny", "S0", ["auth", "api", "web"], "cmd"),
    ("G4.02", "Authorization matrix: every role x every resource x every action, implemented as a table-driven test", "S0", ["auth"], "cmd"),
    ("G4.03", "Cross-tenant READ is blocked and proven by a test", "S0", ["multitenant"], "cmd"),
    ("G4.04", "Cross-tenant WRITE is blocked and proven by a SEPARATE test", "S0", ["multitenant"], "cmd"),
    ("G4.05", "IDOR: requesting another account's object by its raw ID is denied on every resource type", "S0", ["auth", "api"], "cmd"),
    ("G4.06", "Privilege escalation blocked: cannot self-grant a role, change own tenant, or mass-assign role/isAdmin fields", "S0", ["auth"], "cmd"),
    ("G4.07", "Sessions: expire, revoke on logout, rotate on privilege change; cookies are Secure + HttpOnly + SameSite", "S0", ["auth", "web"], "hybrid"),
    ("G4.08", "Credentials stored with a modern KDF (argon2id / bcrypt / scrypt / PBKDF2 at current cost), never reversible, never plaintext", "S0", ["auth"], "hybrid"),
    ("G4.09", "Injection: every query parameterised -- SQL, NoSQL, shell, LDAP, template. No string-built queries on user input", "S0", ["db", "api"], "cmd"),
    ("G4.10", "XSS: stored, reflected, and DOM-based tested; output encoded; Content-Security-Policy present and not 'unsafe-inline'", "S0", ["web"], "hybrid"),
    ("G4.11", "CSRF protection active on every state-changing request", "S0", ["web"], "hybrid"),
    ("G4.12", "SSRF: any user-supplied URL fetched server-side is validated against an allowlist and blocks internal/metadata addresses", "S0", ["api", "thirdparty"], "hybrid"),
    ("G4.13", "Path traversal impossible in any filesystem path built from user input", "S0", ["upload", "api"], "hybrid"),
    ("G4.14", "Unsafe deserialization, prototype pollution, and mass assignment tested and blocked", "S0", ["api"], "hybrid"),
    ("G4.15", "Rate limiting and brute-force protection on login, password reset, OTP, and every expensive endpoint", "S0", ["auth", "api", "web"], "hybrid"),
    ("G4.16", "Security headers present: HSTS, CSP, X-Content-Type-Options, frame-ancestors, Referrer-Policy, Permissions-Policy", "S1", ["web"], "cmd"),
    ("G4.17", "TLS valid: certificate chain good, TLS 1.2+, HTTP redirects to HTTPS, no mixed content, expiry date recorded", "S0", ["web", "api"], "cmd"),
    ("G4.18", "CORS is not a wildcard when credentials are allowed; allowed origins are an explicit list", "S0", ["api", "web"], "hybrid"),
    ("G4.19", "Runtime secrets come from a secret store or environment, never the repo; rotation procedure documented", "S0", ["always"], "manual"),
    ("G4.20", "Error responses leak nothing: no stack traces, SQL fragments, internal paths, or framework versions in production mode", "S0", ["api", "web"], "cmd"),
    ("G4.21", "Upload security: content-type AND magic bytes validated, size capped, stored outside the web root, scanned if scanning is claimed", "S0", ["upload"], "hybrid"),
    ("G4.22", "Supply chain: lockfile integrity verified, no unexpected postinstall scripts, SBOM generated and stored", "S1", ["always"], "cmd"),
    ("G4.23", "Admin surfaces are authenticated, not publicly discoverable, and every default credential is removed", "S0", ["auth", "web"], "hybrid"),
    ("G4.24", "Audit log records security-relevant events: login, failed login, permission change, data export, deletion", "S1", ["auth", "pii"], "hybrid"),
    ("G4.25", "An automated security scan was run (SAST and/or DAST and/or dependency scan) and its raw output is attached", "S0", ["always"], "cmd"),
    ("G4.26", "A line-by-line security review of the release diff was performed by a reviewer who did not write it", "S0", ["always"], "manual"),
    ("G4.27", "Inbound webhooks verify signatures and reject replays (timestamp window + seen-ID cache)", "S0", ["thirdparty", "payments"], "hybrid"),
    ("G4.28", "API keys and tokens are scoped, expiring, and revocable; revocation tested", "S1", ["api", "auth"], "hybrid"),

    # ------------------------------------------------------------------ G5
    ("G5.01", "Migrations run forward successfully from a completely empty database", "S0", ["db"], "cmd"),
    ("G5.02", "ROLLBACK EXECUTED -- not merely written -- and the elapsed time recorded in seconds", "S0", ["db"], "cmd"),
    ("G5.03", "Migration rehearsed on a production-scale data copy; total time and lock duration measured", "S0", ["db"], "cmd"),
    ("G5.04", "Backward compatibility proven: the OLD code runs correctly against the NEW schema (the rolling-deploy window)", "S0", ["db"], "cmd"),
    ("G5.05", "BACKUP RESTORE DRILL performed end to end into a scratch environment, and the data verified", "S0", ["db"], "cmd"),
    ("G5.06", "RPO and RTO stated as numbers and proven by the drill's measured timings", "S0", ["db", "cloud"], "manual"),
    ("G5.07", "Integrity constraints present where they matter: foreign keys, unique, check, not-null", "S1", ["db"], "cmd"),
    ("G5.08", "No destructive migration ships without a backup taken immediately before it, verified restorable", "S0", ["db"], "manual"),
    ("G5.09", "PII inventory written: what personal data is stored, where, why, and for how long", "S0", ["pii"], "manual"),
    ("G5.10", "Sensitive data encrypted at rest and in transit; key management documented", "S0", ["pii", "payments"], "hybrid"),
    ("G5.11", "User data export and deletion actually work end to end and are timed", "S0", ["pii"], "hybrid"),
    ("G5.12", "No seed, demo, or test data is reachable in production; no test accounts with weak passwords", "S0", ["db"], "cmd"),
    ("G5.13", "N+1 queries checked on every list and detail endpoint; query counts recorded", "S1", ["db", "api"], "cmd"),
    ("G5.14", "Every critical-path query has a supporting index, proven with EXPLAIN output", "S1", ["db"], "cmd"),
    ("G5.15", "Connection pool sized deliberately; behaviour under pool exhaustion tested", "S1", ["db"], "hybrid"),
    ("G5.16", "Replica lag / eventual consistency behaviour understood and handled on read-after-write paths", "S1", ["db", "cloud"], "hybrid"),

    # ------------------------------------------------------------------ G6
    ("G6.01", "A written performance budget exists and was written BEFORE the measurements were taken", "S0", ["always"], "manual"),
    ("G6.02", "p50 / p95 / p99 latency measured for every critical endpoint at realistic data volume", "S0", ["api", "web"], "cmd"),
    ("G6.03", "Frontend field metrics measured on a throttled device profile: LCP, CLS, INP, TTFB", "S1", ["web"], "cmd"),
    ("G6.04", "Bundle / binary size measured against the budget; the largest contributors listed", "S1", ["web", "mobile"], "cmd"),
    ("G6.05", "Cold start and first meaningful interaction timed", "S1", ["web", "mobile", "cloud"], "cmd"),
    ("G6.06", "Load test at expected peak concurrency; throughput, latency, and error rate recorded", "S0", ["api", "web", "cloud"], "cmd"),
    ("G6.07", "Load test at 3-10x expected peak: the breaking point is FOUND and its number written down", "S0", ["api", "web", "cloud"], "cmd"),
    ("G6.08", "Soak test of at least one hour: memory, file handles, and connections are flat, not climbing", "S0", ["cloud", "queue", "api"], "cmd"),
    ("G6.09", "At capacity the system degrades gracefully -- queues, sheds load, or returns 429 -- it does not crash or corrupt", "S0", ["api", "cloud"], "hybrid"),
    ("G6.10", "Database performance under load measured; slow query log reviewed and the worst queries fixed", "S1", ["db"], "cmd"),
    ("G6.11", "Cache hit rate measured; cache stampede / thundering herd on expiry tested", "S1", ["cloud", "api"], "hybrid"),
    ("G6.12", "Infrastructure cost modelled at launch volume and at 10x; a billing surprise is impossible", "S1", ["cloud"], "manual"),
    ("G6.13", "Every third-party quota and rate limit checked against expected launch volume", "S0", ["thirdparty"], "manual"),
    ("G6.14", "Autoscaling tested in BOTH directions -- scale out under load, and scale back in afterwards", "S1", ["cloud"], "hybrid"),
    ("G6.15", "Timeouts set at every layer and ordered correctly: client < gateway < service < database", "S0", ["api", "cloud"], "manual"),

    # ------------------------------------------------------------------ G7
    ("G7.01", "Every external dependency killed one at a time; the observed behaviour is acceptable and documented per dependency", "S0", ["thirdparty", "cloud"], "cmd"),
    ("G7.02", "Latency injected into each dependency; no cascading failure, no thread-pool exhaustion", "S0", ["thirdparty", "cloud"], "hybrid"),
    ("G7.03", "Each dependency made to return 500, 429, and a malformed body; each handled distinctly and safely", "S0", ["thirdparty"], "hybrid"),
    ("G7.04", "Database down and database read-only both simulated; the app degrades safely and says so", "S0", ["db"], "hybrid"),
    ("G7.05", "Network interrupted mid-operation; no partial writes, no lost user work, clear recovery", "S0", ["always"], "hybrid"),
    ("G7.06", "Process SIGKILLed mid-write; on restart there is no half-committed state", "S0", ["db", "queue"], "hybrid"),
    ("G7.07", "Disk full and out-of-memory behaviour observed; failure is loud, safe, and recoverable", "S1", ["cloud"], "hybrid"),
    ("G7.08", "Retries have exponential backoff, jitter, and a hard cap -- a retry storm is impossible", "S0", ["thirdparty", "queue"], "hybrid"),
    ("G7.09", "Circuit breaker or bulkhead engages under sustained failure AND recovers when the dependency returns", "S1", ["thirdparty", "cloud"], "hybrid"),
    ("G7.10", "Queue behaviour proven: double delivery, out-of-order, poison message quarantine, and backlog drain rate", "S0", ["queue"], "hybrid"),
    ("G7.11", "Graceful shutdown: readiness flips first, in-flight requests drain, then the process exits", "S0", ["cloud", "api"], "hybrid"),
    ("G7.12", "Health, readiness, and liveness endpoints exist and tell the truth -- they are not hardcoded 200s", "S0", ["cloud", "api"], "cmd"),
    ("G7.13", "Every single point of failure enumerated, each with a mitigation or an explicitly accepted risk", "S0", ["cloud"], "manual"),
    ("G7.14", "Clock skew, DNS failure, and expired certificate scenarios simulated", "S1", ["cloud", "thirdparty"], "hybrid"),
    ("G7.15", "Full-outage recovery test: everything down, then restarted -- state is correct and the recovery is timed", "S0", ["cloud"], "hybrid"),

    # ------------------------------------------------------------------ G8
    ("G8.01", "Keyboard only: every critical path completed with no mouse, no focus trap, focus always visible", "S0", ["ui", "web"], "manual"),
    ("G8.02", "Screen reader: one complete critical path traversed; every control announces a name, role, and state", "S0", ["ui", "web"], "manual"),
    ("G8.03", "Automated accessibility scan run on every major screen: zero critical, zero serious violations", "S0", ["web"], "cmd"),
    ("G8.04", "Colour contrast meets WCAG AA everywhere: 4.5:1 for text, 3:1 for interactive boundaries", "S1", ["ui"], "hybrid"),
    ("G8.05", "Layout works at 320px width and at an ultra-wide viewport; nothing clips, overlaps, or scrolls horizontally", "S1", ["web", "ui"], "manual"),
    ("G8.06", "Device and browser support matrix declared, and every entry actually tested", "S0", ["web", "mobile"], "manual"),
    ("G8.07", "Dark mode, light mode, and forced-colours/high-contrast all render correctly", "S1", ["ui"], "manual"),
    ("G8.08", "prefers-reduced-motion respected -- no unavoidable animation", "S2", ["ui"], "hybrid"),
    ("G8.09", "Zoom to 200% and 400% without loss of content or function", "S1", ["web"], "manual"),
    ("G8.10", "Copy review: every error message is specific and actionable; no raw codes, no 'Something went wrong'", "S1", ["ui"], "manual"),
    ("G8.11", "i18n: longest-language strings do not break layout; RTL correct if supported; locale number, date, and currency formats correct", "S1", ["i18n"], "manual"),
    ("G8.12", "Slow-network (throttled 3G) and fully-offline behaviour observed on every critical path", "S1", ["web", "mobile"], "manual"),
    ("G8.13", "CUSTOMER ZERO: a person with no knowledge of the build completed the primary job unaided; friction log written", "S0", ["ui"], "manual"),
    ("G8.14", "No blank frozen frame: any wait longer than one second shows progress the user can interpret", "S1", ["ui"], "manual"),
    ("G8.15", "Print, export, share, and embed surfaces work if the product claims them", "S2", ["ui", "web"], "manual"),
    ("G8.16", "Mobile specifics: safe areas, rotation, background/foreground resume, and every OS permission denied", "S0", ["mobile"], "manual"),

    # ------------------------------------------------------------------ G9
    ("G9.01", "Privacy policy and Terms exist, are reachable from the product, and accurately describe what the code actually does", "S0", ["pii", "web", "mobile"], "manual"),
    ("G9.02", "Consent for non-essential cookies/tracking implemented where required; non-essential defaults to OFF", "S0", ["pii", "web"], "manual"),
    ("G9.03", "Data processing record: what is collected, the lawful basis, where it is stored, and data residency", "S0", ["pii"], "manual"),
    ("G9.04", "Every third party receiving user data is disclosed, and a processing agreement is in place", "S0", ["pii", "thirdparty"], "manual"),
    ("G9.05", "User rights work end to end: access, export, correction, deletion -- each performed once and timed", "S0", ["pii"], "hybrid"),
    ("G9.06", "Retention policy implemented in code -- data actually gets deleted, proven by a test or a job run", "S1", ["pii"], "hybrid"),
    ("G9.07", "Age gating / children's data handling addressed if the product is reachable by minors", "S0", ["pii"], "manual"),
    ("G9.08", "Accessibility legal obligation identified (ADA / EN 301 549 / WCAG level) and the target level stated", "S1", ["ui"], "manual"),
    ("G9.09", "Open-source licence obligations satisfied: attribution file generated and shipped with the product", "S1", ["always"], "cmd"),
    ("G9.10", "Product name, logo, and domain checked for trademark conflict", "S2", ["always"], "manual"),
    ("G9.11", "App store / marketplace review guidelines walked item by item", "S0", ["store"], "manual"),
    ("G9.12", "Payment compliance scope stated; raw card data never touches your servers unless you are PCI-certified", "S0", ["payments"], "manual"),
    ("G9.13", "Regulated-domain requirements identified (health, finance, education, employment) and addressed", "S0", ["pii"], "manual"),
    ("G9.14", "Security contact and vulnerability disclosure policy published (security.txt or equivalent)", "S1", ["web", "api"], "hybrid"),
    ("G9.15", "Breach notification procedure written: who decides, who is told, within what deadline", "S0", ["pii"], "manual"),
    ("G9.16", "Telemetry audited: no PII in logs or analytics; every collected field justified and disclosed", "S0", ["pii", "always"], "hybrid"),

    # ------------------------------------------------------------------ G10
    ("G10.01", "Structured logs with a request/correlation ID on every entry; zero secrets or PII in log output", "S0", ["cloud", "api"], "cmd"),
    ("G10.02", "Log levels are correct, every ERROR is actionable, and log volume and cost are estimated", "S1", ["cloud"], "manual"),
    ("G10.03", "Metrics exist for rate, errors, and duration on every service, with a dashboard that a human can open", "S0", ["cloud", "api"], "manual"),
    ("G10.04", "SLOs defined as numbers, with a stated error budget", "S0", ["cloud", "api"], "manual"),
    ("G10.05", "An alert exists for every SLO breach and for every failure mode discovered in G7", "S0", ["cloud", "api"], "manual"),
    ("G10.06", "EVERY ALERT FIRED ON PURPOSE and confirmed to reach a named human -- proof per alert", "S0", ["cloud", "api"], "manual"),
    ("G10.07", "Alert quality checked: expected pages per week is a number a human can sustain; no known false positives", "S1", ["cloud"], "manual"),
    ("G10.08", "On-call rota exists with named humans, contact method, and an escalation path", "S0", ["cloud"], "manual"),
    ("G10.09", "A runbook exists per alert: symptom -> diagnosis -> action, executable by someone who did not build this", "S0", ["cloud"], "manual"),
    ("G10.10", "Distributed tracing enabled on the critical path", "S2", ["cloud", "api"], "hybrid"),
    ("G10.11", "Error tracking wired up and PROVEN by deliberately throwing a test error and seeing it arrive", "S0", ["cloud", "web", "api"], "manual"),
    ("G10.12", "Feature flag or kill switch exists for every risky feature, and was tested ON and OFF in production configuration", "S0", ["cloud", "web"], "hybrid"),
    ("G10.13", "Config can be changed and reverted without a deploy; the procedure is written and rehearsed", "S1", ["cloud"], "manual"),
    ("G10.14", "Production access is least-privilege and audited: who can deploy, who can read customer data", "S0", ["cloud", "pii"], "manual"),
    ("G10.15", "Support readiness: the top five predicted user questions are answerable from shipped documentation alone", "S1", ["always"], "manual"),
    ("G10.16", "Status page or user communication channel exists and someone knows how to post to it", "S1", ["cloud", "web"], "manual"),
    ("G10.17", "Pre-launch baseline captured: current error rate, latency, and the key business metric, with numbers", "S0", ["cloud", "web", "api"], "manual"),
    ("G10.18", "Cost and billing alarms configured with thresholds", "S1", ["cloud"], "manual"),

    # ------------------------------------------------------------------ G11
    ("G11.01", "Version assigned, artifact immutably tagged, and the build reproducible from that tag alone", "S0", ["always"], "cmd"),
    ("G11.02", "Release notes / CHANGELOG written in the user's language, describing outcomes not commits", "S1", ["always"], "manual"),
    ("G11.03", "Feature freeze in effect; every post-freeze change restarts verification of the affected gates", "S0", ["always"], "manual"),
    ("G11.04", "Deploy runbook: numbered steps, the expected output of each, and an explicit abort condition", "S0", ["cloud", "web", "api", "mobile"], "manual"),
    ("G11.05", "The runbook was executed or cold-read by someone who did not write it, and every gap fixed", "S0", ["cloud"], "manual"),
    ("G11.06", "Deployed to a production-LIKE environment and every critical path exercised there, not locally", "S0", ["cloud", "web", "api"], "cmd"),
    ("G11.07", "ROLLBACK REHEARSED on the production-like environment and TIMED -- the number of seconds is recorded", "S0", ["cloud", "web", "api", "mobile"], "cmd"),
    ("G11.08", "Data rollback is possible, or explicitly declared impossible with the compensating control named", "S0", ["db"], "manual"),
    ("G11.09", "Staged rollout plan with NUMERIC promotion thresholds and numeric automatic-rollback triggers", "S0", ["cloud", "web", "api"], "manual"),
    ("G11.10", "Kill switch tested: the feature was turned off in a production-like environment and the system stayed healthy", "S0", ["cloud", "web"], "hybrid"),
    ("G11.11", "Environment contract verified IN THE TARGET: every env var, secret, permission, quota, DNS record, and certificate", "S0", ["cloud", "web", "api"], "cmd"),
    ("G11.12", "A production smoke suite exists, runs in under five minutes, and has been rehearsed", "S0", ["cloud", "web", "api"], "cmd"),
    ("G11.13", "Go/No-Go decision held; named humans said GO; the decision and its date recorded", "S0", ["always"], "manual"),
    ("G11.14", "Launch window chosen deliberately: not Friday evening, not during a dependency's maintenance window, humans available", "S1", ["always"], "manual"),
    ("G11.15", "Communications ready and scheduled: users, support, stakeholders, status page", "S1", ["always"], "manual"),
    ("G11.16", "Migration guide published for existing users or integrators if anything is breaking", "S0", ["api", "lib"], "manual"),

    # ------------------------------------------------------------------ G12
    ("G12.01", "Baseline metrics captured in the minutes immediately before the first stage", "S0", ["cloud", "web", "api"], "manual"),
    ("G12.02", "Canary stage deployed to a small share of traffic; production smoke passed; held for the planned duration", "S0", ["cloud", "web", "api"], "manual"),
    ("G12.03", "Metrics compared against baseline at every stage, with the actual numbers recorded", "S0", ["cloud", "web", "api"], "manual"),
    ("G12.04", "Every promotion decision recorded together with the numbers that justified it", "S0", ["cloud", "web", "api"], "manual"),
    ("G12.05", "Rollback confirmed still available and still valid at each stage", "S0", ["cloud", "web", "api"], "manual"),
    ("G12.06", "Full production smoke suite passed at 100% rollout", "S0", ["cloud", "web", "api"], "cmd"),
    ("G12.07", "Structured watch checks logged at T+1h, T+6h, T+24h, T+48h, and T+72h", "S0", ["always"], "manual"),
    ("G12.08", "Every incident triaged with severity, owner, timestamps, and resolution", "S0", ["always"], "manual"),
    ("G12.09", "Support themes reviewed at T+24h and T+72h -- what are real users actually confused by", "S1", ["always"], "manual"),
    ("G12.10", "The success metric measured against the target set before launch", "S1", ["always"], "manual"),
    ("G12.11", "Postmortem written: predicted correctly / surprised us / which gate caught it / which gate missed it", "S1", ["always"], "manual"),
    ("G12.12", "Exactly ONE process improvement written back into this checklist", "S2", ["always"], "manual"),
]


def gate_of(check_id):
    return check_id.split(".")[0]


def by_gate():
    out = {}
    for item in CATALOG:
        out.setdefault(gate_of(item[0]), []).append(item)
    return out


def validate():
    """Self-check the catalog. Returns a list of problems (empty == healthy)."""
    problems = []
    seen = set()
    gate_ids = {g[0] for g in GATES}
    for cid, title, sev, tags, mode in CATALOG:
        if cid in seen:
            problems.append("duplicate id: %s" % cid)
        seen.add(cid)
        if gate_of(cid) not in gate_ids:
            problems.append("%s: unknown gate" % cid)
        if sev not in SEVERITIES:
            problems.append("%s: bad severity %r" % (cid, sev))
        if mode not in ("cmd", "manual", "hybrid"):
            problems.append("%s: bad mode %r" % (cid, mode))
        if not tags:
            problems.append("%s: no tags" % cid)
        for t in tags:
            if t not in TAGS:
                problems.append("%s: unknown tag %r" % (cid, t))
        if len(title) < 15:
            problems.append("%s: title too vague" % cid)
    return problems


if __name__ == "__main__":
    probs = validate()
    print("checks: %d   gates: %d" % (len(CATALOG), len(GATES)))
    if probs:
        for p in probs:
            print("PROBLEM:", p)
        raise SystemExit(1)
    print("catalog OK")
