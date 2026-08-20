# 06 — Integration and end-to-end tests

Unit tests prove each piece behaves. **Integration tests prove the pieces fit** — and the most
common real-world failure is a suite full of unit tests where every seam is mocked, so every unit
passes and the system does not work.

---

## 1. Integration tests

**Scope:** several real components together, with a real database, real serialization, real wiring.
Fake only what leaves your system.

```
Real:  your code · the database · the ORM · serialization · routing · transactions
Fake:  third-party APIs · payment providers · email/SMS · the clock
```

### What only an integration test can catch

- **The query is wrong.** A mocked repository returns whatever you told it to; the SQL is never
  executed. This is the single biggest blind spot in over-mocked suites.
- **The migration and the code disagree** — a column renamed in one place.
- **Transactions and rollback** actually behave as intended.
- **Serialization round-trips** — dates, decimals, nulls, unicode surviving the boundary.
- **Constraints fire** — unique, foreign key, `NOT NULL`.
- **Dependency wiring** is correct, and the app actually boots.
- **Connection pooling and timeouts** under concurrency.

### Rules

- **Use a real database of the same engine and major version as production.** SQLite standing in for
  Postgres tests a different database — different types, different constraint behavior, different
  SQL. Containers make this cheap; there is no longer an excuse.
- **Isolate per test** — transaction rollback by default (see `04-fixtures-and-data.md` §4).
- **Test through the real entry point** — the HTTP handler, the job runner — not by calling the
  service class directly. The wiring is part of what you are testing.
- **Assert on observable state**, read back through the same interface a caller would use.
- Keep them focused: one behavior each, same as a unit test.

## 2. End-to-end tests

**Scope:** the whole system as a user experiences it — usually through a browser or a real client.

**Use them for a handful of critical journeys, and nothing else.** They are the slowest, flakiest,
and most expensive tests you will own. Their value is proving the whole thing hangs together; that
value does not increase with quantity.

`founder-mode/references/04-test-matrix.md` names the critical paths for the project. If those are
not written down, that is the finding — a team that cannot name its critical journeys cannot decide
what to E2E test.

### How many

Typically **three to seven**. Sign up, the core value action, checkout — whatever, if broken, means
the product has no reason to exist. Not "every feature".

### Rules that keep E2E from becoming a liability

- **Select by role or test id, never by CSS class or text.** `getByRole('button', { name: 'Pay' })`
  or `data-testid="submit"`. A class selector breaks on every restyle; a text selector breaks on
  every copy edit and in every other language.
- **Never sleep. Wait for a condition** — the framework's auto-waiting, or an explicit
  `waitFor(element is visible)`.
- **Each test creates its own data** through the API, not the UI. Signing up through the interface
  to test checkout makes every checkout test depend on the signup form.
- **Never depend on a shared account.** Two parallel runs will race.
- **Run against a production-like build**, not a dev server with hot reload.
- **Capture a screenshot, the DOM, and a trace on failure.** An E2E failure with only a stack trace
  is nearly undebuggable; a trace makes it a two-minute fix.
- **Bound the run time.** If E2E takes 40 minutes, it will be run once a day, which means it stops
  gating anything.

## 3. Contract tests

Between two services you both own, or against a published API. See `api-craft` for the contract
itself; the testing pattern:

- **The consumer publishes what it depends on**; the provider's build verifies it. The provider then
  learns about a break *before* release rather than from an incident.
- **Version the contract** and test every supported version.
- **Replay recorded real requests** from production against the new build.

Without a mechanical contract check, "backward compatible" is an opinion — usually held by the
person who wants to ship.

## 4. Testing against third parties

| Approach | Speed | Realism | Use |
|---|---|---|---|
| Fake your own wrapper | Fast | Low | Unit tests — the default |
| Local stub server | Fast | Medium | Integration: real HTTP, real status handling |
| Recorded fixtures | Fast | Medium, **decays silently** | Snapshot of real shapes |
| Provider sandbox | Slow | High | **One** scheduled contract test |

**Recorded fixtures go stale silently** — the provider changes, your recording does not, and your
tests keep passing against last year's API. Refresh them on a schedule, and keep exactly one real
sandbox test running nightly. That test is the only thing that will tell you the provider changed.

**Always test the failure modes**: timeout, 500, 429, malformed body, connection reset, and a
response that arrives after you gave up. Those paths run in production and never run locally.

## 5. Test environments

- **Ephemeral over shared.** A per-run container beats a shared staging database that three teams
  mutate.
- **Same engine and version as production**, for anything stateful.
- **Seeded identically every run** — a test environment that drifts produces failures nobody can
  reproduce.
- **Never real customer data.** Not "temporarily", not "just one table". It becomes permanent and it
  is a breach waiting for a misconfigured bucket.

## 6. Where a bug should be caught

When a defect escapes to production, the postmortem question is not "why was there no test" but
**"at which level should this have been caught, and why was it not?"**

| Defect | Belonged in |
|---|---|
| Wrong calculation | Unit |
| Wrong query, wrong column | Integration |
| Broken wiring, app will not boot | Integration / smoke |
| Contract break for a consumer | Contract test |
| Journey broken across pages | E2E |
| Wrong under concurrency | Integration, with parallelism |
| Only fails with production data volume | Load / a production smoke check |

Answer it each time and write the missing test at that level. `founder-mode` tracks escaped defects
for exactly this reason: **every escape names a ring that was missing**, and fixing the ring is
worth more than fixing the bug.
