# 07 — Product types

**All ten laws apply to every product.** What changes is which ones are load-bearing, and where the
thresholds move.

A 200-line function is bad everywhere. But an unhandled failure is an inconvenience in a local
script, a corrupted dataset in a pipeline, an outage in a service, and an unrecoverable device in
firmware. Same law, four different costs — so four different amounts of care.

Record your product type in the profile. If a project is two things (a service plus a CLI), it is
two profiles, and each part follows its own row.

---

## Library / SDK

**Your mistakes become everyone else's migrations.** You cannot fix a caller's code, and you cannot
know what they depend on.

| Tightens | Why |
|---|---|
| **The public surface is the product** | Everything not deliberately public must be private. What you export, you support. |
| **Backward compatibility is a contract** | A breaking change in a patch release breaks builds at 3am for people who never met you. |
| **Zero global state** | A library that holds process-wide state cannot be used twice in one process, and cannot be tested. |
| **No I/O the caller did not ask for** | No logging to stdout, no reading env vars, no network on import. Take a logger; do not find one. |
| **Errors are typed and documented** | The caller must be able to branch without string-matching. |
| **Dependencies are a tax you levy on others** | Every transitive dependency becomes theirs, including its vulnerabilities and its version conflicts. |

- Export the smallest thing that works. Adding to a public API later is easy; removing is a major version.
- Semantic versioning is a promise, not a formality.
- No `panic`/`exit`/`process.exit` in library code — you do not own the process.
- Deprecate before removing: a release that warns, then a release that removes.

---

## Service / API

**It fails while people are using it**, and the failure is concurrent, partial, and observed.

| Tightens | Why |
|---|---|
| **Every external call has a timeout** | Without one, a slow dependency becomes your outage, and connection pool exhaustion is silent until total. |
| **Idempotency for anything that writes** | Retries are automatic and invisible — the client, the proxy, and the queue will all retry. Twice-charged is a real bug with a real refund. |
| **Failure is a first-class path** | Law 5 is the whole job. Partial failure is normal, not exceptional. |
| **Observability is not optional** | Correlation ids, structured logs, one business metric. See `project-zero/references/03-errors-and-logging.md`. |
| **Concurrency is the default** | Two requests touch the same row. Law 8 is load-bearing; assume simultaneity. |
| **Input from the network is hostile** | Validate at the boundary into a trusted shape (Law 4). Size limits on everything. |

- Distinguish retryable from terminal failures, and never retry a non-idempotent call on a timeout —
  the work may still be in flight.
- Backpressure over unbounded queues. An unbounded queue is a memory leak with extra steps.
- Graceful shutdown: stop accepting, finish in-flight, then exit.

---

## CLI / script

**It runs inside other programs' pipelines**, and its interface is its exit code and its streams.

| Tightens | Why |
|---|---|
| **Exit codes are the API** | `0` success, non-zero failure, distinct codes for distinct failures. A script that exits 0 on failure breaks every `&&` downstream. |
| **stdout is data; stderr is everything else** | Logs, progress, and warnings on stdout corrupt the pipe. This is the single most common CLI defect. |
| **Never prompt unless attached to a TTY** | An interactive prompt in CI hangs the build until the timeout. Check, and fail with a clear message instead. |
| **Fail fast and loudly** | In shell: `set -euo pipefail`, always, first line. |
| **Flags over positional arguments** | Beyond two positionals, nobody remembers the order. |

- `--help` that actually explains, and `--version`.
- Read from stdin when no file is given; it makes the tool composable.
- Do not colorize when not a TTY; the escape codes end up in log files.
- Destructive operations need a confirmation *or* an explicit `--force`, never a bare default.

---

## Data / ML pipeline

**It reruns over history and must agree with itself.** A bug is not an error message; it is a
number that is quietly wrong for six months.

| Tightens | Why |
|---|---|
| **Determinism** | The same input must produce the same output. Seed every random source; never let wall-clock time leak into a transform. |
| **Idempotent reruns** | Rerunning a partition must replace, not append. Otherwise a retry doubles the revenue. |
| **Schema evolution is explicit** | Upstream columns change. Fail loudly on an unexpected schema, never silently coerce. |
| **Validate at the boundary, then trust** | Law 4. Row counts, null rates, ranges — assert them and fail the run. |
| **Partial failure must not corrupt** | Write to a staging location, then atomically swap. A half-written output is worse than no output. |

- Every output carries provenance: which code version, which inputs, which run.
- Null is a value with meaning — decide what it means per column, and write it down.
- A silent `dropna()` is a data loss bug wearing a helpful face.
- Prefer explicit types over inferred ones; inference changes with the data.

---

## Embedded / systems

**There is no operator and no restart.** The cost of a defect is a truck roll or a brick.

| Tightens | Why |
|---|---|
| **Allocation is a design decision** | Prefer static or pool allocation. An allocation failure at hour 10,000 has no operator to see it. |
| **Bounded time and bounded memory** | Unbounded recursion, unbounded buffers, and unbounded loops are all defects. |
| **Every failure is explicit** | No exceptions where they are not available; check every return. |
| **Integer overflow is real** | Sizes, types, and wraparound behavior are decisions, not accidents. |
| **Concurrency is interrupts** | Shared state with an ISR needs the right qualifier and the right barrier. Law 8 is safety-critical here. |

- No dynamic allocation after initialization, where the domain demands it.
- Watchdogs, and a defined safe state on fault.
- Deterministic timing beats average-case speed.

---

## Game / realtime

**A pause is a defect the user feels**, even when nothing is logically wrong.

| Tightens | Why |
|---|---|
| **No allocation in the hot loop** | A collection pause is a dropped frame, and dropped frames are the product being bad. |
| **The frame budget is a hard constraint** | 16.6ms at 60fps for everything. It is a budget, not a target. |
| **Data layout matters** | Cache locality often beats algorithmic cleverness at these sizes. |
| **Determinism where it is simulated** | Fixed timestep for physics; never tie simulation to frame rate. |

- Profile before optimizing, but design the hot path with allocation in mind from the start.
- Law 7 (duplication over wrong abstraction) tightens: an abstraction with a virtual call in the
  inner loop can cost more than the duplication it removed.

---

## UI application

Anything the user sees belongs to the design law — `apple-grade-ui` or the project's own. This skill
governs the code behind it.

| Tightens | Why |
|---|---|
| **State is the hard part** | Law 8. Most UI bugs are two sources of truth disagreeing. |
| **Business logic never lives in a view** | Law 6. A view is a delivery mechanism; logic in it cannot be tested or reused. |
| **Every async state is a real state** | Loading, error, empty, stale, partial — see the design law's Law 9. |

---

## When a product is several things

A repository with a service, a CLI, and a shared library follows **all three** rows, per directory.
The shared library is the strictest, because both others depend on it — and a change there is a
change to everything at once.

Write it in the profile as one section per part, with the boundary between them stated. The most
common failure here is the service importing the CLI's helpers, which quietly makes the CLI a
dependency of production.
