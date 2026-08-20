# 04 — Idempotency and reliability

**The network will deliver your request twice.** Not might — will. The client retries on timeout,
the proxy retries on a reset, the queue redelivers on a missed ack, the user double-clicks, the
mobile app resends when the tunnel comes back.

A timeout tells you the *answer* was lost. It tells you nothing about whether the *work* happened.

Without an idempotency mechanism, one payment becomes two, one email becomes five, and one order
becomes a duplicate that support has to unpick by hand.

---

## 1. Idempotency keys (Law 5)

Every unsafe write accepts a client-generated key:

```
POST /v1/payments
Idempotency-Key: 8f14e45f-ea1d-4a2c-9b1e-5c6a7d8e9f01
```

**The server contract:**

1. First request with this key → do the work, **store the key with the response**, return it.
2. Repeat with the same key **and the same body** → return the stored response. Do not redo the work.
3. Repeat with the same key and a **different** body → `422`. The key identifies one intent; reusing
   it for another is a client bug worth surfacing loudly.
4. A request still in flight → `409`, so the client backs off rather than racing itself.

**Storage details that decide whether this actually works:**

- **Insert the key in the same transaction as the effect.** If the key is written after the work
  commits, a crash in between leaves the work done and the key absent — and the retry duplicates it.
  A unique constraint on the key is what makes this atomic.
- **Store the full response**, not just "done". A retry must get the original body, including the
  created id.
- **Expire keys** after a documented window (24 hours is common). Say so in the docs.
- Scope keys per consumer, so two clients cannot collide.

**Where a key is not available**, use a natural unique constraint — one refund per charge, one
order per cart version. A database unique index is the most reliable idempotency mechanism you
have, because it holds even when two instances of your service race.

## 2. Which methods need it

| Method | Idempotent by definition | Needs a key |
|---|---|---|
| `GET`, `HEAD` | yes | no |
| `PUT` | yes — full replace at a known id | no |
| `DELETE` | yes — end state is the same | no |
| `POST` | **no** | **yes** |
| `PATCH` | usually not | yes, unless provably idempotent |

`PATCH` with `{"status": "cancelled"}` is idempotent. `PATCH` with `{"balanceDelta": -10}` is not,
and is a design mistake — **prefer absolute values to deltas** in any API that can be retried.

## 3. Timeouts

**Every call that leaves the process has a timeout.** Without one, a slow dependency becomes your
outage: connections pile up, the pool exhausts, and partial degradation becomes total.

- Set connect and read timeouts separately.
- A caller's timeout should exceed the callee's, or the caller gives up on work that would have
  succeeded — and then retries it, doubling the load on something already struggling.
- **Publish your own timeout.** A consumer cannot choose theirs sensibly without it.
- Budget across a chain: if the edge allows 3s and there are three hops, each hop cannot have 3s.

## 4. Retries — yours and theirs

**Retry only what is safe:**

- Retry `429`, `502`, `503`, `504`, connection resets, and timeouts **on idempotent operations**.
- Never retry `4xx` other than `429` — the request will not become valid by repetition.
- **Never blindly retry a non-idempotent call after a timeout.** Use a key, or do not retry.

**Exponential backoff with jitter**, always. Fixed-interval retries from many clients synchronize
into a thundering herd that keeps a recovering service down. Bound total attempts; infinite retry
is an outage amplifier.

**Tell consumers what to do:** `Retry-After` on `429` and `503` is not decoration. Without it,
every client invents a backoff, and their collective guess is your next incident.

## 5. Rate limiting

Every public endpoint has a limit. It protects the service from one badly written consumer, which
is a certainty rather than a risk.

```
429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1755254400
```

- Return the remaining budget on **every** response, not just on rejection — that lets a good
  client slow down before it is throttled.
- Limit per consumer, not per IP, wherever you have identity.
- Different limits for different costs: a search that scans is not a point read.
- Document the limits. An undocumented limit is a surprise outage for someone.

## 6. Concurrency and lost updates

Two clients read a resource, both edit, both write. Last write silently destroys the first — and
the loser never learns.

```
GET /v1/orders/42          → 200, ETag: "v7"
PUT /v1/orders/42          → If-Match: "v7"
                             200 if still v7; 412 Precondition Failed if not
```

Return `412` and let the client re-read and merge. **Silent overwrite is data loss that leaves no
trace**, which makes it far worse than an error the client must handle.

## 7. Partial failure

Any operation touching several things can half-succeed. Decide explicitly, per endpoint:

- **All-or-nothing** — a transaction, or a compensating action.
- **Best-effort with a per-item report** — `207`-style, returning which succeeded and which failed,
  each with its own error code.

The wrong answers are returning `200` because most of it worked, and throwing after the completed
part is already committed and invisible. Both hide state someone discovers later, by accident.

For anything crossing a system boundary, prefer the **outbox pattern** — write the intent in the
same transaction as the state change, and publish from the outbox — over a distributed transaction.

## 8. Webhooks: you are now the unreliable caller

Everything above applies in reverse when you call someone else:

- **Sign every payload** (HMAC over body + timestamp) so the receiver can verify it came from you.
- **Include a timestamp and reject old ones** at the receiver, or a captured request can be replayed.
- **Include a unique event id** and deliver at-least-once — receivers must dedupe, so tell them how.
- **Retry with backoff**, over hours, and expose the delivery history.
- **Expect the receiver to be slow or down.** Queue; never block your own transaction on their
  endpoint.
- Document the shape, the signature scheme, and the retry schedule. A webhook without a documented
  signature scheme cannot be trusted by anyone competent.
