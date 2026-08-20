# 08 — The contract review checklist

Walk this before shipping any contract change. Every line passes or you state the exception and
why. **A contract you cannot take back deserves more care than the code behind it.**

Automated first:

```bash
node scripts/check-api.mjs
```

It reports `UNKNOWN` and exits 0 when it finds neither a spec nor recognizable routes — that is not
a pass, it means nothing was checked and everything below is manual.

---

## The change itself

- [ ] The contract was written before the implementation (Law 2)
- [ ] It is classified: **additive** or **breaking** — and if unsure, treated as breaking
- [ ] If breaking: a new version exists, and a deprecation plan with dates
- [ ] A spec diff ran in CI, or a human compared old and new field by field
- [ ] No internal type, table name, or enum leaked into the contract (Law 1)

## Shape

- [ ] Path is a plural noun; the method is the verb — no verbs in paths
- [ ] Path is lowercase and hyphenated, with a consistent trailing-slash convention
- [ ] Nesting is at most one level deep
- [ ] Version segment present (Law 3)
- [ ] Identifiers are opaque strings, not sequential integers where enumeration matters

## Methods and status codes

- [ ] `GET` has no side effects — it will be prefetched and retried
- [ ] Status codes are honest: `201` + `Location` on create, `204` on delete, `422` on validation
- [ ] Never `200` with an error inside (Law 8)
- [ ] `DELETE` on an already-deleted resource returns `204`, not `404`
- [ ] `404` vs `403` decision is deliberate and documented for sensitive resources
- [ ] Long-running work returns `202` with a job resource to poll

## Payload

- [ ] Field naming convention consistent with the rest of the API
- [ ] Money has a currency and is not a float
- [ ] Timestamps are RFC 3339 UTC and end in `At`; dates are not timestamps
- [ ] Durations name their unit (`timeoutMs`, not `timeout`)
- [ ] Identifiers are strings, even the numeric ones
- [ ] Enums are lowercase, closed, documented — with stated consumer behavior on an unknown value
- [ ] No boolean that will predictably need a third state
- [ ] Unknown request fields are rejected, not silently ignored
- [ ] Every body, array, and string has a size limit

## Errors (Law 7)

- [ ] One error shape across every endpoint, including framework and gateway defaults
- [ ] Stable machine-readable `code`; `message` is human and never branched on
- [ ] All validation errors returned at once, not the first
- [ ] `requestId` returned and logged
- [ ] No stack trace, hostname, or SQL in any 5xx body
- [ ] Error responses documented in the spec, not just success

## Lists (Law 6)

- [ ] **Paginated.** No endpoint returns "all of them"
- [ ] Cursor-based unless numbered pages are genuinely required
- [ ] Default limit and maximum limit both set
- [ ] Sort is total — a unique tiebreaker is always appended
- [ ] Every filterable and sortable field is indexed and whitelisted
- [ ] Unknown filter parameters rejected with `422`, not ignored
- [ ] `hasMore` explicit; `nextCursor: null` unambiguously means the end

## Reliability (Law 5)

- [ ] Every unsafe write accepts an idempotency key, or has a natural unique constraint
- [ ] The key is stored **in the same transaction** as the effect
- [ ] A replay with the same key returns the stored response and does not redo the work
- [ ] A replay with the same key and a different body returns `422`
- [ ] Every outbound call has a timeout, and the API's own timeout is published
- [ ] Retries only on transient failures, with backoff, jitter, and a bound
- [ ] **No blind retry of a non-idempotent call after a timeout**
- [ ] Rate limits exist, are documented, and return `Retry-After`
- [ ] Concurrent edits handled — `ETag`/`If-Match` and `412`, not silent overwrite
- [ ] Partial failure has a decided, documented behavior

## Data and migrations (Law 9)

- [ ] Constraints live in the database, not only in application code
- [ ] The migration is safe with the **previous** code version still running
- [ ] The migration is safe with the **next** version running (rollback path)
- [ ] Nothing is renamed or dropped in one step — expand/contract is planned across deploys
- [ ] Lock behavior checked for **this** database at **production** size
- [ ] `lock_timeout` set so a blocked migration fails rather than queueing the service
- [ ] Backfills are batched, throttled on replication lag, resumable, and out-of-band
- [ ] The `down` has been executed against realistic data
- [ ] Destructive steps have a verified backup and a stated point of no return

## Documentation (Law 10)

- [ ] The spec is generated or validated against the implementation, not hand-maintained
- [ ] Every endpoint documents its errors, limits, and idempotency behavior
- [ ] Deprecations carry `Deprecation` and `Sunset` headers and a migration link
- [ ] Tolerant-reader expectations stated: consumers must ignore unknown fields

## For non-HTTP interfaces

- [ ] **GraphQL** — depth/complexity limits, batched loaders, per-field authorization, max page size
- [ ] **gRPC** — field numbers reserved on retirement, package versioned, deadlines set
- [ ] **Events** — past-tense names, unique id for dedupe, at-least-once assumed, DLQ with alerting,
      published from an outbox
- [ ] **Webhooks** — signed, timestamped, replay-protected, retried with backoff, schedule documented
- [ ] **Files** — atomic rename, manifest with count and checksum, empty result distinguishable
      from failure

## Before you report done

- [ ] `node scripts/check-api.mjs` clean, or findings annotated with reasons
- [ ] Contract tests pass, **with the output seen**
- [ ] The change was exercised against a real client, not only a unit test
- [ ] Anything skipped is stated explicitly, with the reason

**An unverified compatibility claim is an unsupported claim.** "It should be backward compatible"
is the sentence that precedes most integration outages.
