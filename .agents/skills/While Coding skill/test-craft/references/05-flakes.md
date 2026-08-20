# 05 — Flakes

**A flaky test is a defect, not a nuisance** (Law 8). Not a defect in the test necessarily — very
often it is a real race in production code that the test is correctly detecting, intermittently.

The cost is not the failed build. It is that a suite with known flakes trains everyone to re-run
red builds without reading them, and after that the suite detects nothing at all. **One tolerated
flake is how a whole safety net stops working.**

---

## 1. The policy

When a test flakes:

1. **Reproduce it.** Run it 100 times in a loop, in parallel, in random order.
2. **Find the root cause** using the taxonomy below. Do not skip to step 3.
3. **Fix it, or delete it** — the same day. There is no third option.

**Never add a retry to make it green.** A retry on a flaky test hides a real race and converts a
loud intermittent failure into a silent one that now happens in production instead of CI.

**Quarantine is a last resort with an expiry date.** If a test must be quarantined, it gets a
ticket, an owner, and a date — otherwise the quarantine list becomes where tests go to die, and it
grows forever.

```bash
# Reproduce: run one test many times, in parallel
for i in $(seq 1 100); do <runner> -t "the flaky test name" || echo "FAILED on run $i"; done
```

## 2. The taxonomy — cause and fix

### Timing and asynchrony (the most common)

| Symptom | Cause | Fix |
|---|---|---|
| Passes locally, fails in CI | CI is slower; a sleep was tuned to a fast machine | Wait for a **condition**, never a duration |
| Fails under load | Race between the act and the assertion | Await the actual completion signal |
| Fails ~1 in 50 | Polling interval versus operation time | Poll for the condition with a generous timeout |

```
BAD    await sleep(500); expect(job.status).toBe('done')
GOOD   await waitFor(() => job.status === 'done', { timeout: 5000, interval: 25 })
```

**`sleep` is a race you decided to lose slowly** (Law 9): too short on a loaded CI box, wasted time
on every other run. `waitFor` is fast when the system is fast and patient when it is not.

**Unawaited promises** are the other half of this: a test that does not await its own act asserts
against a state that has not happened yet, and passes or fails depending on the scheduler.

### Order dependence

| Symptom | Cause | Fix |
|---|---|---|
| Fails only when run with others | Shared mutable state | Isolate: fresh state per test |
| Fails only in a specific order | One test depends on another's leftovers | Make each test create what it needs |
| Fails only in parallel | Shared row, port, file, or account | Unique per test; port 0; temp dirs |

**Run in random order permanently in CI.** It is the only way order dependence surfaces at the time
it is introduced rather than a year later.

### Time

| Symptom | Cause | Fix |
|---|---|---|
| Fails at midnight, or month end | Real clock in an assertion | Inject and pin the clock |
| Fails twice a year | DST boundary | Pin `TZ`; test the boundary explicitly |
| Fails on 29 February, or 31st | Naive date arithmetic | Test those dates deliberately |
| Fails for one colleague | Their machine's time zone | Pin `TZ` in the test environment |

### External dependencies

| Symptom | Cause | Fix |
|---|---|---|
| Fails when a service is slow | A real network call in a unit test | Fake it |
| Fails when a sandbox rate-limits | Shared external account | Fake it, or isolate the account |
| Fails on rebuild only | Stale recorded fixtures | Refresh, and pin versions |

### Resource leakage

| Symptom | Cause | Fix |
|---|---|---|
| Passes alone, fails in the suite | Connections/handles not released | Guaranteed teardown |
| Gets slower as the suite runs | Accumulating state | Clean up in `afterEach`, not `afterAll` |
| Fails after ~N tests | Connection pool exhausted | Close what you open |

### Nondeterministic data

| Symptom | Cause | Fix |
|---|---|---|
| Occasional assertion mismatch | Map/set iteration order | Sort before asserting |
| Random generator produces an edge case | Unseeded randomness | Fixed seed — and keep the case it found |
| Duplicate key errors | Colliding generated ids | Unique per test |

## 3. The flake that is a real bug

**Take this seriously: an intermittent test failure is often the only warning you will get about a
production race.**

Signs the production code is at fault, not the test:

- The failure is a genuine logical inconsistency, not a timeout
- It gets worse under parallelism or load
- It involves two operations touching the same row, key, or file
- The test is correct on its face and the assertion is reasonable

Before "fixing the test", ask: **could a real user hit this?** If two requests can interleave in the
way the test just demonstrated, the flake found a concurrency defect that would otherwise have been
found by a customer.

## 4. Preventing flakes structurally

- **No sleeps.** Ban them; the checker enforces it.
- **No real network** in unit or integration tests.
- **Random order + parallel** in CI from day one, so dependence never accumulates.
- **Guaranteed teardown**, including on failure.
- **Inject the clock** everywhere it is read.
- **Unique identifiers** per test.
- **Pin `TZ`, `LANG`, and locale** in the test environment.
- **Track flake rate as a metric.** A suite that fails 1% of the time on 300 tests fails most
  builds — a number makes that visible before intuition does.

## 5. Slow suites become dead suites

Speed is a correctness feature: a suite people will not run locally has stopped being a feedback
loop and become a deployment ritual.

- Profile it — a handful of tests are almost always most of the wall time.
- Push tests down a level where they can still catch the bug.
- Parallelize, once tests are genuinely independent.
- Share expensive setup across the *suite*, never mutable state across *tests*.
- Reuse one container/database for the run, with per-test transaction rollback.

**If the unit suite takes more than a minute or two, that is a defect in the suite.** Treat it as
one, with an owner, rather than as weather.
