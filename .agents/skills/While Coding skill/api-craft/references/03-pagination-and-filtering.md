# 03 — Pagination, filtering, sorting

**Every endpoint returning more than one thing is paginated, from its first version** (Law 6).

The reason is not theoretical. The table has 40 rows in development and 4 million in year two. The
endpoint that was fine for two years becomes the outage — and by then a hundred consumers depend on
receiving everything, so you cannot add pagination without a new version.

Adding pagination on day one costs ten minutes. Adding it later costs a major version.

---

## 1. Cursor over offset

| | Cursor (keyset) | Offset (`LIMIT/OFFSET`) |
|---|---|---|
| Cost at page 10,000 | Constant | The database scans and discards 200,000 rows |
| Rows inserted while paging | Stable | **Items shift; the consumer silently skips or repeats** |
| Jump to page 500 | Not supported | Supported |
| Total count | Expensive/omitted | Natural |

**Default to cursor pagination.** The correctness problem with offset is the decisive one: on a
list sorted by newest-first, one insert between page 1 and page 2 pushes an item down, and the
consumer never sees it. That is silent data loss in a loop that looks correct.

Offset is acceptable only for a UI that genuinely needs numbered pages over a small, stable set.

```
GET /v1/orders?limit=50
→ { "items": [...], "nextCursor": "eyJpZCI6ImFiYyJ9", "hasMore": true }

GET /v1/orders?limit=50&cursor=eyJpZCI6ImFiYyJ9
→ { "items": [...], "nextCursor": null, "hasMore": false }
```

### Cursor rules

- **Opaque to the consumer.** Base64 an internal structure. The moment a cursor is a readable
  timestamp, someone constructs one by hand and you can never change the encoding.
- **Encodes the sort key plus a tiebreaker.** Sorting by `createdAt` alone breaks on ties — always
  include a unique column: `(createdAt, id)`.
- **`hasMore` is explicit.** Do not make the consumer infer the end from a short page; a page can
  legitimately be short after filtering.
- **`nextCursor: null` means the end**, unambiguously.
- **A cursor is not a permalink.** Document its lifetime, and return `400` on a malformed or
  expired one rather than silently starting over.

## 2. Limits

- **Always have a default** (25–50 is usually right). A missing `limit` must never mean "all".
- **Always have a maximum** (100–1000). Clamp silently and say so in the docs, or reject with `422`
  — either is fine, but pick one.
- **Never let the consumer request unbounded data.** `limit=999999999` is a denial-of-service
  request with a polite name.

## 3. Total counts

`COUNT(*)` over a large filtered set is often slower than the page itself. Options, in order:

1. **Omit it.** Most consumers need "is there more", which `hasMore` answers.
2. **Make it opt-in** — `?includeTotal=true` — so the cost is only paid when needed.
3. **Return an approximate count**, clearly named `approximateTotal`.

Never make every request pay for a count that most callers discard.

## 4. Filtering

Filters are query parameters named after fields:

```
GET /v1/orders?status=open&createdAfter=2026-01-01&customerId=cus_42
```

- **Every filterable field must be indexed.** An unindexed filter is a full table scan that a
  consumer can trigger at will — a performance vulnerability, not just a slow query.
- **Publish the filterable set.** Accepting arbitrary field filters means you can never change a
  column, and invites unbounded queries.
- **Multiple values:** repeat the key (`?status=open&status=paid`) or use a documented separator.
  Choose one and apply it everywhere.
- **Ranges are two parameters:** `createdAfter` / `createdBefore`. Clearer than a mini-language,
  and trivially indexable.
- **Reject unknown filters with `422`.** Ignoring `?statuss=open` silently returns everything,
  which the consumer will read as "there are no closed orders".

**Do not invent a query language.** `?filter=status:open,amount>100` is a parser you now own, a
security surface you did not want, and something no generated client can type-check. If consumers
genuinely need arbitrary querying, that is a different product — a reporting endpoint, or GraphQL.

## 5. Sorting

```
GET /v1/orders?sort=-createdAt,id
```

- Leading `-` for descending. One convention, documented.
- **Whitelist sortable fields**, and index every one.
- **Sorting must be total.** Always append a unique tiebreaker, or pagination becomes
  non-deterministic and pages overlap.
- Have a documented default sort. "Whatever the database returns" is not a default; it changes
  under you when the plan changes.

## 6. Expansion and sparse fields

Two opposite problems: too many round trips, and too much payload.

```
GET /v1/orders/42?expand=customer,lineItems     # embed related resources
GET /v1/orders?fields=id,status,totalAmount     # return only these
```

Both are optional conveniences. Rules:

- **Whitelist what can be expanded**, and bound the depth to one level. Unbounded expansion is an
  N+1 query generator that a consumer controls.
- **Never expand by default.** The default response is the small one.
- Sparse fields must never omit `id` — a consumer cannot correlate results without it.

## 7. Consistency across the API

Every collection endpoint uses **the same parameter names, the same envelope, and the same cursor
format**. A consumer who learns one list endpoint should be able to guess the next one correctly.

The most common failure here is not a bad choice; it is three different choices in one API, made by
three people, none of whom knew about the others.
