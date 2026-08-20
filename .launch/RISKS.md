# RISK REGISTER

| # | Risk | Likelihood | Impact | Detected by | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|
| 1 | Financial result can be plausible but wrong at an uncovered boundary | M | H | R1/R5/mutation | Expand invariant, property, replay, rounding, and reconciliation tests | Engineering | open |
| 2 | Documentation overstates live/production capability | H | H | Product review/Customer Zero | Establish a capability matrix and truthful UI/docs | Product | open |
| 3 | Upstox/network failures may degrade acquisition | M | H | R3/R5 failure injection | Typed integration errors, explicit provenance, bounded retries, and timeout/status/malformed-response tests implemented in Slice 1; credentialed provider run remains | Engineering | mitigated |
| 4 | Public API is unauthenticated with wildcard CORS and mutable global state | H | H | Security/API review | Restrict local origins, document trust boundary, isolate/validate runtime state | Architecture | open |
| 5 | No version control or CI makes releases irreproducible | H | H | Bootstrap | Initialize repository policy, ignore generated state, add CI and clean build | Engineering | open |
| 6 | Existing Windows artifacts may not match current source | H | H | Clean build/manifest verification | Rebuild from an immutable revision and verify hashes/smoke tests | Release | open |
| 7 | Legacy Code Craft and Test Craft baselines are red (53 code findings, 10 test findings) | H | M | Craft checkers | Dedicated baseline-cleanup slices with regression checks; Ruff and strict Mypy are now green | Engineering | open |
| 8 | AI advisor labels imply external analysis even when using heuristics | H | M | Product/UX review | Expose advisor availability and source; never label fallback as remote consensus | Product | open |
| 9 | No automated browser E2E or accessibility proof | H | M | R4/R6/R7 | Add critical-journey E2E and accessibility checks | Engineering/Design | open |
| 10 | No dependency, secret, or supply-chain checks | M | H | R0/R6 | Add CI audits, lock verification, secret scanning, and artifact provenance | Security | open |
| 11 | Provider schema or historical range differs from the governed contract | M | H | R3/R5 | Strict Upstox V3 parsing, recorded fixtures, completeness manifests, and typed fail-closed outcomes implemented; credentialed real response still required | Data | mitigated |
| 12 | Worker crash, cancellation, or stale lease exposes partial evidence or blocks recovery | M | H | R2/R5/R6 | Spawn supervision, heartbeat deadline, staging-only writes, atomic publication, and crash-point tests | Engineering | open |
| 13 | Required effective-dated corporate-action or historical-universe authority is unavailable | H | H | Data acceptance/promotion gates | Keep affected datasets research-only and block promotion with named instruments/dates | Data/Product | open |
| 14 | Content-addressed evidence grows, corrupts, or becomes unreadable on Windows | M | H | Integrity scan/replay/disk monitor | Deterministic chunks, hashes, reserve preflight, read-back, retention design, and rollback rehearsal | Engineering/Release | open |

## Accepted risks

None. Founder acceptance must be explicit and dated.
