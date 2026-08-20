# 03 — Errors, logging, and the one metric

Three things that are nearly free on day zero and nearly impossible to retrofit: a real error
taxonomy, structured logs, and a health check that actually checks something.

They are grouped here because they are one system. An error is thrown, logged with its correlation
id, and surfaces as a metric. Build them together or none of them works.

---

## 1. The error taxonomy (Law 4)

**Copy `assets/errors.ts`.** This section explains the model.

### What strings cost you

`throw new Error("payment failed")` gives the caller exactly one option: match on the text. So they
do, and within a year every layer string-matches, nobody can change a message without breaking a
retry loop somewhere, and the wording is frozen by accident.

An error must answer three questions **at the throw site**, where the answers are actually known:

| Question | Carried by | Used for |
|---|---|---|
| Whose fault is it? | `status` — 4xx theirs, 5xx ours | Alerting. 5xx pages someone; 4xx does not. |
| Should it be retried? | `retryable` | Retry loops, queue redelivery, circuit breakers |
| What may the client see? | `toClientJSON()` | Not leaking internals across the network |

### The set

| Class | Status | Retryable | Use for |
|---|---|---|---|
| `ValidationError` | 422 | no | Input we cannot accept. Carries per-field detail. |
| `UnauthenticatedError` | 401 | no | We do not know who you are |
| `ForbiddenError` | 403 | no | We know, and you may not |
| `NotFoundError` | 404 | no | Also used *instead of* 403 where existence is itself a secret |
| `ConflictError` | 409 | no | Duplicate, version mismatch, already-used token |
| `RateLimitError` | 429 | **yes** | Carries `retryAfterSeconds` |
| `UpstreamError` | 502 | **yes** | A dependency failed. Names the service. |
| `TimeoutError` | 504 | **yes** | A dependency did not answer in time |
| `InternalError` | 500 | no | The fallback. Every one is a bug worth an alert. |

**`TimeoutError` is deliberately separate from `UpstreamError`.** A timeout means the work may
*still be in flight* — the request might have succeeded and the answer got lost. Retrying a
non-idempotent call on a timeout is how one payment becomes two. The distinction has to exist in
the type or it will not exist in anyone's head at 3am.

### `code` is the API; `message` is for humans

`message` may be reworded freely. `code` is a stable public contract — callers branch on it. Add to
the union; never repurpose a member.

### The boundary rule

At every boundary — HTTP handler, job runner, queue consumer — wrap with `toAppError()`. An
unexpected throw becomes a 500 with a full stack in the logs instead of a crashed process or a
leaked internal message. **5xx messages are replaced before serialization**: `"connection refused
to pg-primary-3.internal:5432"` is a gift to an attacker and meaningless to a user. 4xx messages
pass through, because the caller caused it and needs to know what to change.

### Never

- `catch (e) {}` — silence is choosing to be blind later.
- `catch (e) { console.log(e) }` — that is not handling; it is a comment with overhead.
- Catching to rethrow the same thing with no added context.
- Using exceptions for control flow in the happy path.

---

## 2. Structured logging (Law 5)

**Copy `assets/logger.ts`.**

### One line, one JSON object, one event

`console.log("here", user)` cannot answer the only question that matters in an incident: *show me
every event for the request that failed.* Structured events can, at the same cost.

```jsonc
{"ts":"2026-08-15T10:32:01.221Z","level":"error","msg":"charge failed",
 "requestId":"5f3a…","userId":"u_91","event":"billing.charge.failed",
 "err":{"code":"UPSTREAM_FAILED","service":"stripe"}}
```

### The correlation id is the whole point

One id, generated at the edge, on **every** line produced while handling that request — including
from code five layers deep that knows nothing about HTTP. The shipped logger uses
`AsyncLocalStorage`, so this needs no context parameter threaded through every signature.

Without it you have a pile of lines. With it you have a story.

### Rules

- **Levels mean things.** `error` = a human must look. `warn` = it is degraded but handled.
  `info` = a business event happened. `debug` = off in production. If everything is `error`,
  nothing is.
- **Log events, not prose.** `event: "billing.charge.failed"` is greppable and countable forever;
  `"Failed to charge the card :("` is neither.
- **Never log secrets.** The shipped logger redacts by key name at write time, so being careless is
  not the same as leaking. Verified, not assumed.
- **Never log an entire request body** — that is how card numbers reach a log aggregator.
- **Log once, at the boundary.** Logging at every layer turns one failure into six lines that look
  like six failures.

---

## 3. Health and the one metric (Law 8)

### `/health` must actually check something

```ts
registerHealthCheck("database", () => db.query("select 1"));
registerHealthCheck("cache", () => redis.ping());
```

An endpoint that returns `200 OK` unconditionally reports that the process is running — which you
already knew — and will keep reporting healthy right through an outage.

Two properties the shipped implementation has, both non-obvious:

- **Every check is time-boxed.** A health check that can hang is worse than none: it converts a
  degraded dependency into an unresponsive load-balancer probe, and the platform kills a server
  that was merely slow.
- **It reports per-dependency status**, so the answer is "the database is unreachable" rather than
  "something is wrong".

### Liveness is not readiness

| Endpoint | Answers | If it fails |
|---|---|---|
| `/livez` | Is the process alive? | Restart it |
| `/readyz` | Can it serve traffic *right now*? | Take it out of the pool, do not restart |

Conflating them causes a restart loop during a brief database blip: the app is fine, the dependency
is not, and restarting makes it worse.

### The one metric

Exactly one, on day zero, and it is not CPU. **Pick the number that tells you the product is
working** — requests served, orders placed, jobs completed — and graph it.

The reason is narrow and practical: during an incident the only question is "is it affecting
users?", and a business metric answers it in one glance while infrastructure metrics start an
argument. Add latency and error rate next. Add the rest when something forces you to.
