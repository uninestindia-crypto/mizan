# G6 — Performance & Capacity

> **Purpose.** It is fast enough at real volume, and you know precisely where it breaks.
>
> **Veto holder.** Performance owner. **Entry.** G5 passed. **Exit.** 15 checks resolved.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**The rule that makes this gate honest.** *Write the budget before you take the measurement.* A
budget invented after the number arrives is not a budget; it is a description. Do G6.01 first,
literally first, before running anything else in this gate.

**"Feels fast" is not a measurement.** Neither is a single request from your laptop against an
empty database on a warm cache over office wifi.

---

#### G6.01 · Written performance budget, written BEFORE measuring — `S0` `manual`

- **Do** — write the numbers now. Reasonable defaults if the team has none:

| Thing | Default budget |
|---|---|
| API read endpoint, p95 | < 300 ms |
| API write endpoint, p95 | < 800 ms |
| API p99 | < 2× the p95 budget |
| Page LCP (mid-tier mobile, throttled 4G) | < 2.5 s |
| Page INP | < 200 ms |
| Page CLS | < 0.1 |
| Initial JS bundle, gzipped | < 200 KB |
| Cold start (serverless / container) | < 1 s |
| Background job p95 | < the interval it runs on |
| Error rate under expected peak | < 0.1% |

- **Record** — `LRK manual G6.01 --status pass --note "Budgets: read p95 300ms, write p95 800ms, LCP 2.5s, bundle 200KB gz, error rate <0.1% at 200 rps. Set 2026-08-14 before any measurement."`
- **Also state the volume the budget applies at** — "300ms p95" is meaningless without "at 200 requests per second with 2 million rows in `orders`".

#### G6.02 · p50 / p95 / p99 per critical endpoint at realistic volume — `S0` `cmd`

- **Prerequisite** — the database must contain a realistic row count. Measuring against 40 rows measures nothing. Seed it to production scale first.
- **Run** — pick whichever tool exists:
  ```bash
  LRK run G6.02 -- npx autocannon -c 50 -d 30 -l "$BASE/api/orders"
  LRK run G6.02 -- hey -z 30s -c 50 "$BASE/api/orders"
  LRK run G6.02 -- k6 run load/orders.js
  LRK run G6.02 -- ab -n 2000 -c 50 "$BASE/api/orders"
  ```
- **Pass** — p95 and p99 within budget for every critical endpoint.
- **Report p99, not just the average.** The average hides everything. p99 is one request in a hundred — at a thousand requests a minute that is ten unhappy users every minute.

#### G6.03 · Frontend field metrics on a throttled profile — `S1` `cmd`

- **Run** — `LRK run G6.03 -- npx lighthouse "$URL" --preset=desktop --output=html --output-path=./lh-desktop.html --quiet` and again with `--preset=perf` / mobile emulation and CPU throttling ×4.
- **Then attach the reports** — `LRK attach G6.03 ./lh-mobile.html --caption "Lighthouse, mobile, 4× CPU throttle"`
- **Pass** — LCP, CLS, INP, and TTFB all within budget on the **mobile, throttled** run. The desktop number is not the number your users experience.

#### G6.04 · Bundle / binary size against budget — `S1` `cmd`

- **Run** — `LRK run G6.04 -- npx source-map-explorer 'dist/**/*.js'` or `npx vite-bundle-visualizer` or `du -sh` the artifact.
- **Pass** — within budget, and you can name the three largest dependencies. If a date library or an icon set is 40% of your bundle, that is the finding.

#### G6.05 · Cold start timed — `S1` `cmd`

- **Run** — `LRK run G6.05 -- bash -c 'time (<start command> & sleep 0.2; until curl -sf "$BASE/health" >/dev/null; do sleep 0.1; done)'`
- **Pass** — within budget. For serverless, measure a genuine cold start (deploy fresh, or wait out the idle window) — not the warm invocation you get on the second try.

#### G6.06 · Load test at expected peak — `S0` `cmd`

- **Do** — state your expected peak concurrency first, and say where the number comes from ("500 signups on launch day, ~20 concurrent"). Then generate that load for at least five minutes against a production-like environment.
- **Run** — `LRK run G6.06 -- k6 run --vus 50 --duration 5m load/critical-path.js`
- **Pass** — latency within budget, error rate under 0.1%, no memory growth, no connection-pool exhaustion, no queue backing up.
- **Load-test the whole journey, not one endpoint.** Real users log in, list, filter, open a detail page, and submit. That mix stresses caches and pools in ways a single-endpoint hammer never will.

#### G6.07 · Find the breaking point — `S0` `cmd`

- **Do** — ramp the load until something fails. Keep going until it does. **The number you are looking for is where it breaks, and you must find it.**
- **Run** — `LRK run G6.07 -- k6 run --stage 1m:50,2m:200,2m:500,2m:1000 load/critical-path.js`
- **Record three things** — the concurrency at which latency exceeds budget; the concurrency at which errors begin; and *what* broke first (database connections, memory, CPU, a third-party rate limit, the queue).
- **Pass** — the breaking point is a known number, and it is comfortably above expected peak. If it is *below* expected peak, this is a Blocker and no amount of optimism changes that.
- **Why it is S0** — "we don't know how much traffic it can take" means you cannot answer the only question that matters on launch day.

#### G6.08 · Soak test, minimum one hour — `S0` `cmd`

- **Run** — `LRK run G6.08 --timeout 5400 -- k6 run --vus 20 --duration 60m load/critical-path.js`, while sampling memory:
  ```bash
  LRK run G6.08 --title "memory over the soak" -- bash -c 'for i in $(seq 1 60); do date -Is; ps -o rss= -p <PID>; sleep 60; done'
  ```
- **Pass** — memory, file handles, and connection counts are **flat**, not climbing. A slow climb over one hour is a production outage on day three.
- **Also watch** — open file descriptors (`lsof -p <pid> | wc -l`), database connections, and any unbounded in-memory cache or array.

#### G6.09 · Graceful degradation at capacity — `S0` `hybrid`

- **Do** — push past the breaking point found in G6.07 and watch *how* it fails.
- **Pass** — it sheds load: queues, returns 429 with `Retry-After`, or serves degraded results. It does **not** crash, corrupt data, lose queued work, or take out the database for everything else.
- **The worst failure mode** — the application stays up and slowly returns wrong or partial answers. Failing loudly is always better than being quietly incorrect.

#### G6.10 · Database performance under load — `S1` `cmd`

- **Run during the load test** — `LRK run G6.10 -- psql -c "SELECT query, calls, mean_exec_time, total_exec_time FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;"`
- **Pass** — the slow query log is reviewed and the worst offenders are fixed or explained. Cross-references G5.13 and G5.14.

#### G6.11 · Cache hit rate and stampede — `S1` `hybrid`

- **Do** — measure the hit rate under load. Then expire a hot key and watch what happens when a hundred requests all miss simultaneously.
- **Pass** — hit rate is known; a stampede does not multiply into the database. Use request coalescing, a lock, or a stale-while-revalidate window.

#### G6.12 · Cost modelled at launch volume and at 10× — `S1` `manual`

- **Do** — the arithmetic. Compute, database, storage, egress, third-party per-call charges, log ingestion (this one surprises people constantly), and observability.
- **Record** — `LRK manual G6.12 --status pass --note "Launch: ~$340/mo. 10x: ~$2,100/mo, dominated by log ingestion and egress. Billing alert set at $600."`
- **Why it is here** — a cost surprise ends products just as effectively as an outage, and unlike an outage there is no rollback.

#### G6.13 · Third-party quotas checked against expected volume — `S0` `manual`

- **Do** — for every external service from G0.10, look up the actual rate limit and quota on your actual plan. Compare against your expected launch volume, and against the 10× case.
- **Watch for** — email providers (daily sending caps and reputation limits on new accounts), SMS (per-second caps), payment providers (test-mode limits differ from live), map and geocoding APIs (expensive per call), AI/LLM APIs (tokens per minute), and any free tier that silently becomes an error at the boundary.
- **Pass** — every quota is known, is above expected peak, and someone knows what happens when one is hit.
- **The launch-day classic** — a brand-new transactional email account is rate-limited to 200/day, and the two-thousandth signup never receives a verification link.

#### G6.14 · Autoscaling tested in both directions — `S1` `hybrid`

- **Do** — generate enough load to trigger a scale-out, and confirm new instances actually take traffic (health check passes, they are added to the pool, and they warm up fast enough to matter). Then stop the load and confirm it scales back in without dropping in-flight requests.
- **Pass** — both directions work, and the scale-out is fast enough that the spike does not outrun it.
- **The trap** — scaling that takes four minutes to react to a spike that lasts ninety seconds. The instances arrive after the incident.

#### G6.15 · Timeouts set at every layer and correctly ordered — `S0` `manual`

- **Do** — write down the timeout at every layer and confirm the ordering:
  ```
  client (30s) > CDN/LB (25s) > gateway (20s) > service (15s) > outbound HTTP (10s) > database (8s)
  ```
- **Pass** — each inner layer times out **before** the layer outside it, so the failure is attributed correctly and resources are released.
- **If any layer has no timeout, that is a Blocker.** A missing timeout means one slow dependency holds a connection forever; the pool fills; every request queues; the whole service dies from one slow third party. This is the single most common cascading-failure mechanism in production systems.

---

## Exit bar for G6

```bash
LRK status --gate G6
```

Leave this gate able to complete these four sentences with numbers you measured:

1. "At expected peak, p95 is **___** ms and the error rate is **___**%."
2. "It breaks at **___** concurrent users, and the first thing to break is **___**."
3. "Over one hour of sustained load, memory went from **___** to **___**."
4. "At launch volume it costs **___** per month; at 10× it costs **___**."
