# 01 — The contract: resources, methods, status codes

The shape a consumer codes against. Get this wrong and every later decision inherits the mistake.

---

## 1. Model nouns, not procedures

A resource is a **thing the consumer cares about**, named as a plural noun. The method supplies the
verb (Law 8).

| Do | Don't |
|---|---|
| `POST /v1/orders` | `POST /v1/createOrder` |
| `DELETE /v1/orders/42` | `POST /v1/deleteOrder` |
| `GET /v1/orders?status=open` | `GET /v1/getOpenOrders` |
| `POST /v1/orders/42/refunds` | `POST /v1/refundOrder` |

**Resources need not match tables.** They match what the consumer thinks about. Three tables may be
one resource; one table may be three. If the URL structure mirrors your schema, you have leaked the
implementation (Law 1) and can no longer refactor it.

### Actions that are not CRUD

Some operations genuinely are not create/read/update/delete: *publish*, *cancel*, *retry*, *send*.
Two acceptable shapes:

1. **A sub-resource that represents the event** — `POST /v1/orders/42/cancellation`. Preferred: it
   is a thing, it can be queried, it has its own id and timestamp.
2. **A state transition on the parent** — `PATCH /v1/orders/42 {"status":"cancelled"}`. Simple, but
   only when the transition carries no data of its own.

Both beat inventing `POST /v1/orders/42/doCancel`.

## 2. Path structure

```
/v{n}/{collection}/{id}/{sub-collection}/{sub-id}
/v1/orders/42/line-items/7
```

- **Lowercase, hyphenated.** Not `lineItems`, not `line_items` in a path.
- **Plural collections.** `/orders/42`, never `/order/42`.
- **No trailing slash**, consistently. Two spellings of one resource is two entries in every cache.
- **Nest at most one level.** `/a/1/b/2/c/3` is unreadable and couples three concepts. Past one
  level, make the sub-resource top-level and filter: `/v1/line-items?orderId=42`.
- **Identifiers are opaque strings** to the consumer. Never require them to parse an id, and never
  expose a sequential integer where enumeration matters.

## 3. Method semantics

| Method | Safe | Idempotent | Use |
|---|---|---|---|
| `GET` | yes | yes | Read. **Never changes state** — proxies and prefetchers will call it. |
| `HEAD` | yes | yes | Metadata only |
| `POST` | no | **no** | Create, or a non-idempotent action. Needs an idempotency key (Law 5). |
| `PUT` | no | yes | Full replace at a known id |
| `PATCH` | no | no* | Partial update. Make it idempotent where you can. |
| `DELETE` | no | yes | Remove. Deleting twice returns the same outcome. |

**"Safe" is not advice.** A `GET` with a side effect will be triggered by a link preview, a crawler,
a browser prefetch, or a retry — none of which asked for the effect.

**`DELETE` on an already-deleted resource returns `204`, not `404`.** The end state the caller
wanted is true. Returning `404` makes every retry look like a failure.

## 4. Status codes

Use the protocol's vocabulary. Generic clients, proxies, caches, and retry libraries all behave
based on these; `200` with an error inside defeats every one of them.

| Code | Means | Use for |
|---|---|---|
| `200` | OK | Successful read or update with a body |
| `201` | Created | Creation. Include a `Location` header |
| `202` | Accepted | Work queued but not done — see §5 |
| `204` | No content | Success with nothing to return (delete) |
| `400` | Malformed | Unparseable — bad JSON, wrong type |
| `401` | Unauthenticated | We do not know who you are |
| `403` | Forbidden | We know, and you may not |
| `404` | Not found | Absent — or hiding existence from an unauthorized caller |
| `409` | Conflict | State conflict: duplicate, already-transitioned |
| `412` | Precondition failed | Optimistic concurrency check failed |
| `422` | Unprocessable | Well-formed but semantically invalid — the common validation case |
| `429` | Too many requests | Rate limited. **Always** include `Retry-After` |
| `500` | Server error | Our bug. Never leak internals |
| `502/503/504` | Upstream/unavailable/timeout | A dependency failed. Retryable |

**`400` vs `422`:** `400` for "I cannot parse this", `422` for "I parsed it and it is wrong".
Consumers retry them differently — neither is retryable, but only one is fixable by editing a value.

**`404` vs `403`:** where the existence of a record is itself sensitive, return `404` for both.
Otherwise `403` is kinder and more debuggable. Decide per resource, and document it.

## 5. Long-running work

Never hold a connection open for a slow operation. Return `202 Accepted` with a location to poll:

```
POST /v1/exports          → 202 { "id": "exp_1", "status": "pending" }
                            Location: /v1/exports/exp_1
GET  /v1/exports/exp_1    → 200 { "status": "running",  "progress": 0.4 }
                          → 200 { "status": "succeeded", "resultUrl": "..." }
                          → 200 { "status": "failed",    "error": { ... } }
```

The job resource is real: it has an id, a status, a created time, and an outcome. `failed` is a
`200` on the *job* — the request to read the job succeeded; the job is what failed.

## 6. Headers that carry meaning

- **`Location`** on `201`, pointing at the created resource.
- **`ETag`** + `If-Match` for optimistic concurrency. Without it, two editors silently overwrite
  each other, and the loser never learns.
- **`Cache-Control`** explicitly on every `GET`. Omitting it delegates a correctness decision to
  whatever heuristic a proxy chose.
- **`Retry-After`** on `429` and `503`. Without it, clients invent a backoff, and their guess
  becomes your thundering herd.
- **`Idempotency-Key`** accepted on every unsafe write (Law 5).
- **A request id** echoed on every response, so a consumer reporting a problem can name it.

## 7. Consistency is a feature

Within one API, the same concept is spelled the same way everywhere: the same field name, the same
timestamp format, the same error shape, the same pagination style, the same id format.

**A consistent API can be learned once and predicted thereafter.** An inconsistent one must be
looked up every time, forever — and the lookup is a documentation page that is probably stale.
