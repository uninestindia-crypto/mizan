# G7 — Reliability & Failure Injection

> **Purpose.** Every dependency has been killed on purpose, and the system behaved.
>
> **Veto holder.** SRE. **Entry.** G6 passed. **Exit.** 15 checks resolved.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`. Detailed injection recipes: `failure-injection.md`.

**The premise.** Everything you depend on will be unavailable at some point, usually without
warning and usually at the worst moment. The only question is whether you have seen what happens
when it does. Reading the retry code is not seeing it.

**The bar for every check in this gate** — the failure must be **safe** (no data loss, no
half-committed state, no money moved twice), **visible** (a log, a metric, an alert, and something
honest shown to the user), and **recoverable** (when the dependency returns, the system returns,
without a human restarting anything).

---

#### G7.01 · Every external dependency killed, one at a time — `S0` `cmd`

- **Do** — take the inventory from G0.10. Kill each one individually and observe. Never two at once; you want to know which behaviour belongs to which dependency.

| Dependency | How to kill it |
|---|---|
| Database | Stop the container: `docker compose stop db` |
| Cache / Redis | `docker compose stop redis` |
| Queue broker | Stop the broker |
| Third-party HTTP API | Point its base URL at a dead port: `export STRIPE_API_BASE=http://127.0.0.1:1` |
| Object storage | Revoke the credential, or point at a dead endpoint |
| Email / SMS | Same — dead endpoint |
| DNS | Add a hosts entry pointing the hostname at `0.0.0.0` |

- **Run one per dependency** so each gets its own record:
  ```bash
  LRK run G7.01 --title "redis down: browse, checkout, login" -- bash -c '<probe script>'
  LRK run G7.01 --title "payment API unreachable" -- bash -c '<probe script>'
  ```
- **Pass, per dependency** — you can state in one sentence what the user sees, what the log says, whether data is safe, and whether it recovers on its own when the dependency returns.
- **The finding this always produces** — one dependency you believed was optional turns out to be required. A cache outage taking down login is the classic version.

#### G7.02 · Latency injected into each dependency — `S0` `hybrid`

- **Do** — make each dependency **slow** rather than dead. Slow is far more dangerous than dead, because dead fails fast and slow exhausts your resources.
- **How** — `tc qdisc add dev eth0 root netem delay 5000ms` inside the container, or a proxy like Toxiproxy, or a stub server that sleeps.
- **Pass** — your timeout (G6.15) fires, the request fails cleanly, the connection is released, and other requests are unaffected.
- **What you are looking for** — thread-pool or connection-pool exhaustion. One slow dependency consuming every worker until the entire service stops answering, including endpoints that never touch that dependency. This is the mechanism behind most "the whole site went down" incidents.

#### G7.03 · Each dependency returns 500, 429, and garbage — `S0` `hybrid`

- **Do** — stub each dependency to return, in turn: `500`, `503`, `429` with `Retry-After`, `429` without it, `401` (expired credential), a malformed JSON body, an empty body, an HTML error page with a `200` status, and a response that is valid JSON of the wrong shape.
- **Pass** — each handled distinctly. Specifically: a `429` must back off rather than retry immediately; a `401` must not be retried at all (it will never succeed); an HTML error page must not crash the parser.
- **The one everyone misses** — `200 OK` with an HTML body. Cloud providers return this from their edge during incidents. `JSON.parse("<html>...")` throws in a place nobody wrote a handler for.

#### G7.04 · Database down and read-only — `S0` `hybrid`

- **Do** — both, separately. Stop the database entirely; then set it read-only (`ALTER DATABASE x SET default_transaction_read_only = on;`) which is what a failover or a full disk actually looks like.
- **Pass** — the app returns a clear error, does not accept writes it cannot persist, does not show the user a success message for work that was discarded, and recovers when the database returns without a restart.
- **Health checks must reflect this.** If the database is down and `/health` still returns 200, the load balancer keeps sending traffic to a service that cannot serve it. Cross-references G7.12.

#### G7.05 · Network interrupted mid-operation — `S0` `hybrid`

- **Do** — start a multi-step operation (checkout, upload, multi-table write) and sever the connection halfway.
- **Pass** — no partial write; either the whole operation committed or none of it did; the user's input survives; retrying does not duplicate the effect (cross-references G3.10).
- **On the client too** — kill the browser tab mid-submit, and put the phone into airplane mode mid-upload.

#### G7.06 · Process SIGKILLed mid-write — `S0` `hybrid`

- **Do** — `kill -9` the process during a write (not `kill -15`; you want no cleanup at all). Restart it. Inspect the data.
- **Run** — `LRK run G7.06 -- bash -c '<start a long write> & sleep 1; kill -9 %1; <restart>; <query for half-committed state>'`
- **Pass** — no half-committed state, no orphaned rows, no lock left held, no job stuck in `processing` forever.
- **The specific bug** — a job marked `processing` before the crash and never reclaimed. It sits there permanently while the user waits for something that will never finish.

#### G7.07 · Disk full and out of memory — `S1` `hybrid`

- **Do** — fill the disk (`fallocate -l <size> /tmp/filler`) and separately constrain memory (`docker run -m 256m`).
- **Pass** — fails loudly and safely. No silent truncation of writes, no corrupted files, no log rotation failure that then takes the disk down, and the OOM killer does not leave data in an inconsistent state.

#### G7.08 · Retries have backoff, jitter, and a cap — `S0` `hybrid`

- **Run** — `LRK run G7.08 -- git grep -nE "retry|retries|maxAttempts|backoff|axios-retry|tenacity|resilience4j" -- . | head -40`
- **Pass** — every retry loop has (1) exponential backoff, (2) **jitter**, (3) a hard maximum attempt count, and (4) a rule that only retriable errors are retried (never a `400` or a `401`).
- **Why jitter specifically** — without it, every client that failed at the same moment retries at the same moment. The dependency comes back up, is immediately hit by every retry simultaneously, and falls over again. This is a retry storm, and it turns a thirty-second blip into a thirty-minute outage.
- **Also check for nesting** — 3 retries at the client × 3 at the gateway × 3 at the service is 27 requests for one user action.

#### G7.09 · Circuit breaker engages and recovers — `S1` `hybrid`

- **Do** — hold a dependency down long enough to trip the breaker. Confirm requests then fail fast rather than waiting for the timeout every time. Bring the dependency back and confirm the breaker closes without intervention.
- **Pass** — both directions. A breaker that opens and never closes is worse than none — it requires a human to notice and restart.

#### G7.10 · Queue behaviour — `S0` `hybrid`

- **Test all five**:
  1. **Double delivery** — deliver the same message twice. Exactly one effect. (Queues are at-least-once. This *will* happen.)
  2. **Out of order** — deliver messages in reverse. The outcome is still correct, or ordering is explicitly enforced.
  3. **Poison message** — one that always throws. It must be quarantined to a dead-letter queue after N attempts, not block the queue forever.
  4. **Visibility timeout** — a job that runs longer than its timeout gets redelivered *while still running*. Confirm two workers on the same job do not both complete it.
  5. **Backlog** — enqueue 100,000 items. Measure the drain rate. Confirm memory stays flat and the consumer does not fetch everything into RAM.
- **Pass** — all five, each recorded separately.

#### G7.11 · Graceful shutdown — `S0` `hybrid`

- **Do** — send `SIGTERM` while requests are in flight.
- **Pass** — in this exact order: (1) the readiness endpoint starts failing so the load balancer stops sending new traffic, (2) in-flight requests complete, (3) queue consumers finish or return their current message, (4) connections close, (5) the process exits — all within the platform's grace period (Kubernetes default: 30s).
- **The bug** — the process exits immediately on `SIGTERM`, dropping every in-flight request. During a rolling deploy, that is a burst of 502s on every single release, which everyone learns to ignore. Then a real burst of 502s gets ignored too.

#### G7.12 · Health, readiness, and liveness endpoints tell the truth — `S0` `cmd`

- **Run** — `LRK run G7.12 -- bash -c 'curl -s "$BASE/health"; echo; curl -s "$BASE/ready"; echo'` — then again with the database stopped.
- **Pass** — three distinct things:
  - **Liveness** — "the process is alive". Should almost never fail; failing it triggers a restart.
  - **Readiness** — "I can serve traffic **right now**". Must check the database and critical dependencies, and must go red when they are down.
  - **Health/deep** — a fuller diagnostic for humans, listing each dependency's state.
- **Faked by** — `app.get('/health', (_, res) => res.send('ok'))`. That endpoint proves the HTTP server is listening and nothing else. It will happily report healthy while every request 500s, and the load balancer will keep routing traffic into the fire.

#### G7.13 · Single points of failure enumerated — `S0` `manual`

- **Do** — list everything with exactly one of it: one database instance, one region, one API key, one certificate, one queue, one person who knows how to deploy, one cron host, one domain registrar account with one owner.
- **For each** — a mitigation, or an explicitly accepted risk with a name attached.
- **Record** — attach the list. This document is what the on-call engineer reads at 3am when trying to work out what could possibly be wrong.

#### G7.14 · Clock skew, DNS failure, expired certificate — `S1` `hybrid`

- **Clock skew** — set the container clock forward by ten minutes. Do JWTs still validate? Do signed webhooks still verify? Do TOTP codes still work? Skew tolerance should exist and be bounded.
- **DNS failure** — point a dependency's hostname at `0.0.0.0` in `/etc/hosts`. Does the failure surface quickly, or hang for the full resolver timeout?
- **Certificate expiry** — record every certificate's expiry date and confirm renewal is automated **and monitored**. Auto-renewal that has been silently failing for two months is discovered by the outage.

#### G7.15 · Full-outage recovery test, timed — `S0` `hybrid`

- **Do** — stop everything: application, database, cache, queue. Then bring it all back up in the documented order.
- **Run** — `LRK run G7.15 -- bash -c 'time (docker compose down && docker compose up -d && until curl -sf "$BASE/health"; do sleep 1; done)'`
- **Pass** — the system returns to correct operation with no manual data repair, in a time you have measured and written down. In-flight work at the moment of the outage is either completed or cleanly failed — never silently lost.
- **This number is your real RTO** for an application-layer outage, and someone will ask for it during the first incident.

---

## Exit bar for G7

```bash
LRK status --gate G7
```

You have passed when you can hand someone a table with one row per dependency, and every row says
what the user sees, what the operator sees, and whether it heals itself. Anything you did not
actually kill is a row you cannot fill in — and an untested failure mode is just an outage that
has not happened yet.
