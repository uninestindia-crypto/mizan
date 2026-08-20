# Launch Readiness Certificate

    ******************************************************************
    VERDICT: NO-GO
    ******************************************************************

| Field | Value |
|---|---|
| Product | demo-shop |
| Version | 1.0.0 |
| Owner | Demo Owner |
| Profile | web, api, db, auth, payments, pii, multitenant, cloud |
| Git commit | `08f4a684fc74c112491191e10e26cb588bbe9228` |
| Git branch | master  **WORKING TREE DIRTY** |
| Certified at | 2026-08-15T03:38:01+05:30 |
| Host | Zeaul_Rahman / Windows 11 (ARM64) |

## Coverage

| Metric | Count |
|---|---|
| Checks in catalogue | 216 |
| Applicable to this profile | 199 |
| Passed | 8 |
| Failed | 11 |
| Not tested | 179 |
| Waived | 1 |
| Not applicable | 0 |

### Strength of proof

| Level | Count | Meaning |
|---|---|---|
| Executed | 15 | Proven by a recorded command, with raw output and a hash |
| Attached | 1 | Proven by an attached artifact (screenshot, log, document) |
| Asserted | 3 | Somebody wrote that it was fine. Weakest form of evidence. |

## BLOCKERS -- launch is forbidden while these are open

| ID | Reason | Check |
|---|---|---|
| `G0.01` | **NOT TESTED** | Version control clean: on a release branch/tag, no uncommitted changes, no untracked source |
| `G0.02` | **NOT TESTED** | Stack detected and written down: languages, frameworks, package managers, runtimes |
| `G0.04` | **NOT TESTED** | Clean-clone install from zero succeeds in an empty directory with no caches |
| `G0.06` | **NOT TESTED** | .env.example lists every variable; app fails LOUDLY at startup when one is missing |
| `G0.07` | **FAILING** | Dependency lockfile exists, is committed, and install is reproducible from it |
| `G0.10` | **NOT TESTED** | External dependency inventory: every third-party API, DB, queue, storage, mail, payment provider |
| `G0.11` | **NOT TESTED** | Target environments enumerated: production URL(s), staging, regions, tenants |
| `G1.03` | **NOT TESTED** | Type check passes with ZERO errors |
| `G1.10` | **FAILING** | Secret scan over the FULL git history (not just HEAD) finds zero live credentials |
| `G1.11` | **FAILING** | No localhost / 127.0.0.1 / staging hostnames / test API keys reachable on a production code path |
| `G1.12` | **NOT TESTED** | Dependency vulnerability audit: zero CRITICAL, zero HIGH, or each one waived with reasoning |
| `G1.17` | **FAILING** | No .env file, private key, database dump, or real customer data committed to the repository |
| `G2.02` | **NOT TESTED** | Full suite passes from a CLEAN state: fresh dependencies, fresh database, migrations from zero |
| `G2.12` | **NOT TESTED** | Unit tests cover every branch of domain logic per the part-type matrix |
| `G2.13` | **NOT TESTED** | Contract tests pin every boundary: API request/response, DB schema, event payloads, error taxonomy |
| `G2.14` | **NOT TESTED** | Integration tests run against a REAL database with real migrations, not mocks |
| `G2.15` | **NOT TESTED** | End-to-end test covers every critical path from a genuinely empty starting state |
| `G2.18` | **NOT TESTED** | CI runs the same commands as local, and CI is GREEN on the exact release commit |
| `G3.01` | **NOT TESTED** | Every acceptance criterion demonstrated one by one, with proof per criterion |
| `G3.03` | **NOT TESTED** | First-run experience walked from a genuinely empty account -- no seed data, no pre-existing state |
| `G3.04` | **NOT TESTED** | Every form: client validation, server validation, inline field errors, and double-submit protection |
| `G3.05` | **NOT TESTED** | Every destructive action has confirmation and either undo or a documented recovery path |
| `G3.07` | **FAILING** | Money correctness: rounding both directions, zero, negative, maximum, precision, currency mixing, and NO floating point |
| `G3.08` | **NOT TESTED** | Date/time correctness: DST both directions, offsets east and west, half-hour offsets, leap year, server tz != user tz != db tz |
| `G3.10` | **FAILING** | Every mutating endpoint is idempotent, or documented as unsafe to retry with a client-side guard |
| `G3.11` | **NOT TESTED** | Concurrency: two actors mutate the same resource at the same instant -- outcome is correct and deterministic |
| `G4.01` | **NOT TESTED** | Every protected route enumerated and tested unauthenticated -- all deny |
| `G4.02` | **NOT TESTED** | Authorization matrix: every role x every resource x every action, implemented as a table-driven test |
| `G4.03` | **FAILING** | Cross-tenant READ is blocked and proven by a test |
| `G4.04` | **NOT TESTED** | Cross-tenant WRITE is blocked and proven by a SEPARATE test |
| `G4.05` | **NOT TESTED** | IDOR: requesting another account's object by its raw ID is denied on every resource type |
| `G4.06` | **NOT TESTED** | Privilege escalation blocked: cannot self-grant a role, change own tenant, or mass-assign role/isAdmin fields |
| `G4.07` | **NOT TESTED** | Sessions: expire, revoke on logout, rotate on privilege change; cookies are Secure + HttpOnly + SameSite |
| `G4.08` | **NOT TESTED** | Credentials stored with a modern KDF (argon2id / bcrypt / scrypt / PBKDF2 at current cost), never reversible, never plaintext |
| `G4.09` | **FAILING** | Injection: every query parameterised -- SQL, NoSQL, shell, LDAP, template. No string-built queries on user input |
| `G4.10` | **NOT TESTED** | XSS: stored, reflected, and DOM-based tested; output encoded; Content-Security-Policy present and not 'unsafe-inline' |
| `G4.11` | **NOT TESTED** | CSRF protection active on every state-changing request |
| `G4.12` | **NOT TESTED** | SSRF: any user-supplied URL fetched server-side is validated against an allowlist and blocks internal/metadata addresses |
| `G4.13` | **NOT TESTED** | Path traversal impossible in any filesystem path built from user input |
| `G4.14` | **NOT TESTED** | Unsafe deserialization, prototype pollution, and mass assignment tested and blocked |
| `G4.15` | **NOT TESTED** | Rate limiting and brute-force protection on login, password reset, OTP, and every expensive endpoint |
| `G4.17` | **NOT TESTED** | TLS valid: certificate chain good, TLS 1.2+, HTTP redirects to HTTPS, no mixed content, expiry date recorded |
| `G4.18` | **NOT TESTED** | CORS is not a wildcard when credentials are allowed; allowed origins are an explicit list |
| `G4.19` | **NOT TESTED** | Runtime secrets come from a secret store or environment, never the repo; rotation procedure documented |
| `G4.20` | **NOT TESTED** | Error responses leak nothing: no stack traces, SQL fragments, internal paths, or framework versions in production mode |
| `G4.23` | **NOT TESTED** | Admin surfaces are authenticated, not publicly discoverable, and every default credential is removed |
| `G4.25` | **NOT TESTED** | An automated security scan was run (SAST and/or DAST and/or dependency scan) and its raw output is attached |
| `G4.26` | **NOT TESTED** | A line-by-line security review of the release diff was performed by a reviewer who did not write it |
| `G4.27` | **NOT TESTED** | Inbound webhooks verify signatures and reject replays (timestamp window + seen-ID cache) |
| `G5.01` | **NOT TESTED** | Migrations run forward successfully from a completely empty database |
| `G5.02` | **FAILING** | ROLLBACK EXECUTED -- not merely written -- and the elapsed time recorded in seconds |
| `G5.03` | **NOT TESTED** | Migration rehearsed on a production-scale data copy; total time and lock duration measured |
| `G5.04` | **NOT TESTED** | Backward compatibility proven: the OLD code runs correctly against the NEW schema (the rolling-deploy window) |
| `G5.05` | **NOT TESTED** | BACKUP RESTORE DRILL performed end to end into a scratch environment, and the data verified |
| `G5.06` | **NOT TESTED** | RPO and RTO stated as numbers and proven by the drill's measured timings |
| `G5.08` | **NOT TESTED** | No destructive migration ships without a backup taken immediately before it, verified restorable |
| `G5.09` | **NOT TESTED** | PII inventory written: what personal data is stored, where, why, and for how long |
| `G5.10` | **NOT TESTED** | Sensitive data encrypted at rest and in transit; key management documented |
| `G5.11` | **NOT TESTED** | User data export and deletion actually work end to end and are timed |
| `G5.12` | **NOT TESTED** | No seed, demo, or test data is reachable in production; no test accounts with weak passwords |
| `G6.01` | **NOT TESTED** | A written performance budget exists and was written BEFORE the measurements were taken |
| `G6.02` | **NOT TESTED** | p50 / p95 / p99 latency measured for every critical endpoint at realistic data volume |
| `G6.06` | **NOT TESTED** | Load test at expected peak concurrency; throughput, latency, and error rate recorded |
| `G6.07` | **NOT TESTED** | Load test at 3-10x expected peak: the breaking point is FOUND and its number written down |
| `G6.08` | **NOT TESTED** | Soak test of at least one hour: memory, file handles, and connections are flat, not climbing |
| `G6.09` | **NOT TESTED** | At capacity the system degrades gracefully -- queues, sheds load, or returns 429 -- it does not crash or corrupt |
| `G6.15` | **NOT TESTED** | Timeouts set at every layer and ordered correctly: client < gateway < service < database |
| `G7.01` | **NOT TESTED** | Every external dependency killed one at a time; the observed behaviour is acceptable and documented per dependency |
| `G7.02` | **NOT TESTED** | Latency injected into each dependency; no cascading failure, no thread-pool exhaustion |
| `G7.04` | **NOT TESTED** | Database down and database read-only both simulated; the app degrades safely and says so |
| `G7.05` | **NOT TESTED** | Network interrupted mid-operation; no partial writes, no lost user work, clear recovery |
| `G7.06` | **NOT TESTED** | Process SIGKILLed mid-write; on restart there is no half-committed state |
| `G7.11` | **NOT TESTED** | Graceful shutdown: readiness flips first, in-flight requests drain, then the process exits |
| `G7.12` | **NOT TESTED** | Health, readiness, and liveness endpoints exist and tell the truth -- they are not hardcoded 200s |
| `G7.13` | **NOT TESTED** | Every single point of failure enumerated, each with a mitigation or an explicitly accepted risk |
| `G7.15` | **NOT TESTED** | Full-outage recovery test: everything down, then restarted -- state is correct and the recovery is timed |
| `G8.01` | **NOT TESTED** | Keyboard only: every critical path completed with no mouse, no focus trap, focus always visible |
| `G8.02` | **NOT TESTED** | Screen reader: one complete critical path traversed; every control announces a name, role, and state |
| `G8.03` | **NOT TESTED** | Automated accessibility scan run on every major screen: zero critical, zero serious violations |
| `G8.06` | **NOT TESTED** | Device and browser support matrix declared, and every entry actually tested |
| `G9.01` | **NOT TESTED** | Privacy policy and Terms exist, are reachable from the product, and accurately describe what the code actually does |
| `G9.02` | **NOT TESTED** | Consent for non-essential cookies/tracking implemented where required; non-essential defaults to OFF |
| `G9.03` | **NOT TESTED** | Data processing record: what is collected, the lawful basis, where it is stored, and data residency |
| `G9.04` | **NOT TESTED** | Every third party receiving user data is disclosed, and a processing agreement is in place |
| `G9.05` | **NOT TESTED** | User rights work end to end: access, export, correction, deletion -- each performed once and timed |
| `G9.07` | **NOT TESTED** | Age gating / children's data handling addressed if the product is reachable by minors |
| `G9.12` | **NOT TESTED** | Payment compliance scope stated; raw card data never touches your servers unless you are PCI-certified |
| `G9.13` | **NOT TESTED** | Regulated-domain requirements identified (health, finance, education, employment) and addressed |
| `G9.15` | **NOT TESTED** | Breach notification procedure written: who decides, who is told, within what deadline |
| `G9.16` | **NOT TESTED** | Telemetry audited: no PII in logs or analytics; every collected field justified and disclosed |
| `G10.01` | **NOT TESTED** | Structured logs with a request/correlation ID on every entry; zero secrets or PII in log output |
| `G10.03` | **NOT TESTED** | Metrics exist for rate, errors, and duration on every service, with a dashboard that a human can open |
| `G10.04` | **NOT TESTED** | SLOs defined as numbers, with a stated error budget |
| `G10.05` | **NOT TESTED** | An alert exists for every SLO breach and for every failure mode discovered in G7 |
| `G10.06` | **FAILING** | EVERY ALERT FIRED ON PURPOSE and confirmed to reach a named human -- proof per alert |
| `G10.08` | **NOT TESTED** | On-call rota exists with named humans, contact method, and an escalation path |
| `G10.09` | **NOT TESTED** | A runbook exists per alert: symptom -> diagnosis -> action, executable by someone who did not build this |
| `G10.11` | **NOT TESTED** | Error tracking wired up and PROVEN by deliberately throwing a test error and seeing it arrive |
| `G10.12` | **NOT TESTED** | Feature flag or kill switch exists for every risky feature, and was tested ON and OFF in production configuration |
| `G10.14` | **NOT TESTED** | Production access is least-privilege and audited: who can deploy, who can read customer data |
| `G10.17` | **NOT TESTED** | Pre-launch baseline captured: current error rate, latency, and the key business metric, with numbers |
| `G11.01` | **NOT TESTED** | Version assigned, artifact immutably tagged, and the build reproducible from that tag alone |
| `G11.03` | **NOT TESTED** | Feature freeze in effect; every post-freeze change restarts verification of the affected gates |
| `G11.04` | **NOT TESTED** | Deploy runbook: numbered steps, the expected output of each, and an explicit abort condition |
| `G11.05` | **NOT TESTED** | The runbook was executed or cold-read by someone who did not write it, and every gap fixed |
| `G11.06` | **NOT TESTED** | Deployed to a production-LIKE environment and every critical path exercised there, not locally |
| `G11.07` | **NOT TESTED** | ROLLBACK REHEARSED on the production-like environment and TIMED -- the number of seconds is recorded |
| `G11.08` | **NOT TESTED** | Data rollback is possible, or explicitly declared impossible with the compensating control named |
| `G11.09` | **NOT TESTED** | Staged rollout plan with NUMERIC promotion thresholds and numeric automatic-rollback triggers |
| `G11.10` | **NOT TESTED** | Kill switch tested: the feature was turned off in a production-like environment and the system stayed healthy |
| `G11.11` | **NOT TESTED** | Environment contract verified IN THE TARGET: every env var, secret, permission, quota, DNS record, and certificate |
| `G11.12` | **NOT TESTED** | A production smoke suite exists, runs in under five minutes, and has been rehearsed |
| `G11.13` | **NOT TESTED** | Go/No-Go decision held; named humans said GO; the decision and its date recorded |
| `G11.16` | **NOT TESTED** | Migration guide published for existing users or integrators if anything is breaking |
| `G12.01` | **NOT TESTED** | Baseline metrics captured in the minutes immediately before the first stage |
| `G12.02` | **NOT TESTED** | Canary stage deployed to a small share of traffic; production smoke passed; held for the planned duration |
| `G12.03` | **NOT TESTED** | Metrics compared against baseline at every stage, with the actual numbers recorded |
| `G12.04` | **NOT TESTED** | Every promotion decision recorded together with the numbers that justified it |
| `G12.05` | **NOT TESTED** | Rollback confirmed still available and still valid at each stage |
| `G12.06` | **NOT TESTED** | Full production smoke suite passed at 100% rollout |
| `G12.07` | **NOT TESTED** | Structured watch checks logged at T+1h, T+6h, T+24h, T+48h, and T+72h |
| `G12.08` | **NOT TESTED** | Every incident triaged with severity, owner, timestamps, and resolution |

## Warnings -- fix, or accept in writing

| ID | Reason | Check |
|---|---|---|
| `G0.05` | NOT TESTED | A stranger can get it running from the README alone -- no tribal knowledge |
| `G0.08` | NOT TESTED | Runtime versions pinned (.nvmrc / .python-version / engines / toolchain file) |
| `G0.12` | WEAK EVIDENCE | Cut line written: what is in v1.0 and what is explicitly NOT, agreed before verification starts |
| `G1.04` | NOT TESTED | Lint passes with zero errors and zero warnings, or a recorded baseline with zero new |
| `G1.06` | NOT TESTED | No TODO / FIXME / HACK / XXX / 'temporary' markers on any critical path file |
| `G1.07` | FAILING | No debug artifacts shipped: console.log, print, debugger, pdb, binding.pry, alert() |
| `G1.13` | NOT TESTED | License compliance: LICENSE present; no copyleft licence incompatible with how this ships |
| `G1.14` | NOT TESTED | No abandoned or known-malicious dependency on a critical path; every dep justified |
| `G1.15` | NOT TESTED | Source maps / debug symbols policy decided and enforced -- production source is not published by accident |
| `G1.18` | NOT TESTED | Strict mode on: strict types, no blanket 'any'/'unsafe' escapes on critical paths, warnings-as-errors where supported |
| `G2.03` | NOT TESTED | Suite passes with tests in randomised order |
| `G2.07` | NOT TESTED | Coverage measured; coverage on critical-path files meets a written bar |
| `G2.08` | NOT TESTED | No assertion-free tests -- every test asserts on a value, not merely 'did not throw' |
| `G2.10` | NOT TESTED | Tests are deterministic: frozen clock, fixed seed, fixed IDs, no live network |
| `G2.11` | NOT TESTED | Flake count is zero: suite run three times, identical results each time |
| `G2.16` | NOT TESTED | Every bug ever found has a regression test that fails without its fix |
| `G3.06` | NOT TESTED | List boundaries: zero results, one result, exact page boundary, past the last page, item inserted between page 1 and 2 |
| `G3.09` | NOT TESTED | Unicode, emoji, right-to-left text, and 10,000-character strings accepted, stored, and rendered without corruption |
| `G3.12` | NOT TESTED | Browser back, forward, and refresh mid-flow behave correctly; every screen is deep-linkable |
| `G3.14` | NOT TESTED | Outbound email / push / SMS actually sends and renders correctly in a real client -- screenshot from a real inbox |
| `G3.15` | NOT TESTED | Search: empty query, no results, special and regex characters, very long query, permission-filtered counts match visible rows |
| `G3.16` | NOT TESTED | Every documented error code is reachable by a test and produces a message a user can act on |
| `G4.16` | NOT TESTED | Security headers present: HSTS, CSP, X-Content-Type-Options, frame-ancestors, Referrer-Policy, Permissions-Policy |
| `G4.22` | NOT TESTED | Supply chain: lockfile integrity verified, no unexpected postinstall scripts, SBOM generated and stored |
| `G4.24` | NOT TESTED | Audit log records security-relevant events: login, failed login, permission change, data export, deletion |
| `G4.28` | NOT TESTED | API keys and tokens are scoped, expiring, and revocable; revocation tested |
| `G5.07` | NOT TESTED | Integrity constraints present where they matter: foreign keys, unique, check, not-null |
| `G5.13` | NOT TESTED | N+1 queries checked on every list and detail endpoint; query counts recorded |
| `G5.14` | NOT TESTED | Every critical-path query has a supporting index, proven with EXPLAIN output |
| `G5.15` | NOT TESTED | Connection pool sized deliberately; behaviour under pool exhaustion tested |
| `G5.16` | NOT TESTED | Replica lag / eventual consistency behaviour understood and handled on read-after-write paths |
| `G6.03` | NOT TESTED | Frontend field metrics measured on a throttled device profile: LCP, CLS, INP, TTFB |
| `G6.04` | NOT TESTED | Bundle / binary size measured against the budget; the largest contributors listed |
| `G6.05` | NOT TESTED | Cold start and first meaningful interaction timed |
| `G6.10` | NOT TESTED | Database performance under load measured; slow query log reviewed and the worst queries fixed |
| `G6.11` | NOT TESTED | Cache hit rate measured; cache stampede / thundering herd on expiry tested |
| `G6.14` | NOT TESTED | Autoscaling tested in BOTH directions -- scale out under load, and scale back in afterwards |
| `G7.07` | NOT TESTED | Disk full and out-of-memory behaviour observed; failure is loud, safe, and recoverable |
| `G7.09` | NOT TESTED | Circuit breaker or bulkhead engages under sustained failure AND recovers when the dependency returns |
| `G7.14` | NOT TESTED | Clock skew, DNS failure, and expired certificate scenarios simulated |
| `G8.05` | NOT TESTED | Layout works at 320px width and at an ultra-wide viewport; nothing clips, overlaps, or scrolls horizontally |
| `G8.09` | NOT TESTED | Zoom to 200% and 400% without loss of content or function |
| `G8.12` | NOT TESTED | Slow-network (throttled 3G) and fully-offline behaviour observed on every critical path |
| `G9.06` | NOT TESTED | Retention policy implemented in code -- data actually gets deleted, proven by a test or a job run |
| `G9.09` | NOT TESTED | Open-source licence obligations satisfied: attribution file generated and shipped with the product |
| `G9.14` | NOT TESTED | Security contact and vulnerability disclosure policy published (security.txt or equivalent) |
| `G10.02` | NOT TESTED | Log levels are correct, every ERROR is actionable, and log volume and cost are estimated |
| `G10.07` | NOT TESTED | Alert quality checked: expected pages per week is a number a human can sustain; no known false positives |
| `G10.13` | NOT TESTED | Config can be changed and reverted without a deploy; the procedure is written and rehearsed |
| `G10.15` | NOT TESTED | Support readiness: the top five predicted user questions are answerable from shipped documentation alone |
| `G10.16` | NOT TESTED | Status page or user communication channel exists and someone knows how to post to it |
| `G10.18` | NOT TESTED | Cost and billing alarms configured with thresholds |
| `G11.02` | NOT TESTED | Release notes / CHANGELOG written in the user's language, describing outcomes not commits |
| `G11.14` | NOT TESTED | Launch window chosen deliberately: not Friday evening, not during a dependency's maintenance window, humans available |
| `G11.15` | NOT TESTED | Communications ready and scheduled: users, support, stakeholders, status page |
| `G12.09` | NOT TESTED | Support themes reviewed at T+24h and T+72h -- what are real users actually confused by |
| `G12.10` | NOT TESTED | The success metric measured against the target set before launch |
| `G12.11` | NOT TESTED | Postmortem written: predicted correctly / surprised us / which gate caught it / which gate missed it |

## Waivers on record

**G6.12 (S1)** -- Infrastructure cost modelled at launch volume and at 10x; a billing surprise is impossible

- Waived by: Demo Owner (CTO) on 2026-08-15
- Reason: Pre-revenue; single region; fewer than 200 users expected in month one.
- Risk accepted: An unexpected traffic spike produces a surprise cloud bill. No hard spend cap is configured.
- Expires: 2026-11-01

## Signature block

This certificate was computed from recorded evidence, not from anyone's opinion.
Verify the evidence has not been altered:

```
python lrk.py verify
```

| Role | Name | Date | Decision |
|---|---|---|---|
| Engineering owner |  |  |  |
| Security reviewer |  |  |  |
| Operations / SRE |  |  |  |
| Product owner (final GO) |  |  |  |

> A NO-GO certificate may only be overridden by the product owner signing
> above **and** writing, in one sentence per blocker, the risk being accepted
> and who will be woken up when it happens.
