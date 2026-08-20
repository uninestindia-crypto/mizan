# 07 — Beyond HTTP: GraphQL, gRPC, events, batch

**The ten laws are protocol-neutral.** Versioning, additive-only evolution, idempotency,
pagination, documented errors, and expand/contract migrations bind every interface between two
programs. Only the spelling changes.

This file is the translation table.

---

## 1. GraphQL

GraphQL removes the URL design problem and replaces it with three harder ones.

**Versioning (Law 3/4).** The convention is *no versions* — evolve the schema additively and
deprecate fields with `@deprecated(reason: "...")`. That works only if you actually run the
deprecation process from `05-versioning-and-evolution.md`: instrument usage per field, contact the
consumers still selecting it, then remove. A schema with fifty `@deprecated` fields nobody removed
is worse than a v2.

**Pagination (Law 6).** Use the Connections pattern — `edges`, `node`, `cursor`, `pageInfo` — with
cursors, for the reasons in `03-pagination-and-filtering.md`. Enforce a **maximum page size in the
schema**, not just in docs.

**The problems unique to GraphQL, and they are the important part:**

- **Unbounded query cost.** A nested query can ask for the cross product of your database in one
  request. Mitigate with query depth limits, complexity scoring with a per-caller budget, and
  persisted queries (an allowlist of known documents) for first-party clients. **An unauthenticated
  GraphQL endpoint with no cost limit is a denial-of-service endpoint.**
- **N+1 by construction.** Every nested field is a resolver. Use a batching loader; without one,
  one query becomes a thousand.
- **Authorization per field, not per endpoint.** There is no route to hang a check on. Every
  resolver returning sensitive data must check independently, or a nested path will reach data the
  top-level query would have refused.
- **Errors are `200` with an `errors` array.** This is the protocol, so Law 8 binds differently:
  use stable machine-readable codes in `extensions.code`, and be consistent across every resolver.

## 2. gRPC / protobuf

The wire format enforces some of the laws for you, which is its main advantage.

- **Field numbers are the contract**, not names. Never reuse a number; `reserved` the ones you
  retire. Renaming a field is safe on the wire and breaks generated code — treat it as breaking.
- **Additive by design:** new optional fields are compatible. Removing a required field is not.
- **Version the package** — `package orders.v1;` — which is Law 3 in protobuf's spelling.
- **Errors use status codes** (`INVALID_ARGUMENT`, `NOT_FOUND`, `ALREADY_EXISTS`,
  `FAILED_PRECONDITION`) plus `google.rpc.ErrorInfo` for a stable `reason`. Same contract as an
  HTTP error body: a machine-readable code, a human message.
- **Deadlines are mandatory and propagate.** This is gRPC's biggest advantage over HTTP — use it,
  and do not set them to something absurd to make a test pass.
- **Pagination is explicit**: `page_size`, `page_token`, `next_page_token`. Same rules as §3 of
  `03-pagination-and-filtering.md`.
- **Streaming is not a way to avoid pagination.** A stream still needs flow control and a bound.

## 3. Events, queues, and message contracts

The most commonly under-designed interface, because it feels internal — until three teams depend on
it and it is a public API with no documentation.

**An event is a published contract.** Everything in Law 4 applies: additive only, no removed
fields, no changed meanings.

```jsonc
{
  "id": "evt_01H...",              // unique — the consumer's dedupe key
  "type": "order.completed",       // versioned name, past tense
  "version": 1,                    // schema version of THIS event type
  "occurredAt": "2026-08-15T10:32:01Z",
  "producer": "orders-service",
  "data": { "orderId": "ord_42" }
}
```

Rules:

- **Name events in the past tense** — `order.completed`, not `complete_order`. An event is a fact
  that happened, not a request. A command queue is a different thing; do not mix them in one topic.
- **Delivery is at-least-once. Always.** Exactly-once does not exist across a network boundary.
  **Consumers must be idempotent** — dedupe on `id`, or make the handler naturally idempotent.
  This is Law 5, and it is the consumer's obligation as well as yours.
- **Order is not guaranteed** unless the transport guarantees it within a partition key. Design
  handlers to tolerate out-of-order arrival, or partition by the entity id.
- **Include enough data to act**, or a stable id to fetch with. "Event carries everything" avoids a
  round trip and goes stale; "event carries an id" is always current and costs a call. Choose per
  event type and document which.
- **Schema registry or it did not happen.** An event schema that lives only in the producer's code
  is a contract nobody can validate.
- **Dead-letter queue, always**, with alerting. A poison message that retries forever is an
  infinite loop with a monthly bill; one that vanishes is silent data loss.
- **Publish from an outbox** written in the same transaction as the state change. Publishing after
  the commit means a crash in between loses the event; publishing before means an aborted
  transaction emits an event for something that never happened.

## 4. Webhooks

You become the unreliable caller. See `04-idempotency-and-reliability.md` §8 for the full contract:
sign the payload, include a timestamp and reject old ones, include a unique event id, retry with
backoff over hours, and expose the delivery history.

The rule most often skipped: **document the retry schedule and the signature scheme**. A receiver
cannot implement dedupe or verification against an undocumented one.

## 5. Batch and file interfaces

CSV drops, nightly exports, SFTP — old-fashioned, still everywhere, and usually the least specified
interface in the system.

- **The filename convention is the contract**: `orders_2026-08-15_v1.csv`. Include the date and the
  schema version.
- **Write to a temporary name and rename atomically**, or the consumer reads a half-written file.
  This is the single most common defect in file interfaces.
- **A manifest** with row count and a checksum, so the consumer can verify completeness rather than
  assume it.
- **Idempotent reprocessing** — the same file processed twice must not double anything. Key on
  (filename, row id).
- **An empty file is a valid result and must be distinguishable from a failed job.** "No file" is
  ambiguous; an empty file with a manifest saying zero rows is not.
- **Column order is part of the contract.** Adding a column at the end is additive; inserting one in
  the middle breaks every positional parser.

## 6. Internal service-to-service

The rules do not relax because both sides are yours. They relax slightly because you can deploy
both — but only if you actually can, at the same time, which is rarely true once there is a queue,
a cache, or a mobile client in between.

**Version internal contracts too.** The moment two services deploy independently, they are a
distributed system with a compatibility problem, and "we'll just deploy them together" stops being
true exactly when it matters most.
