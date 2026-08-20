# 02 — Payloads and errors

The body is the part consumers actually write code against. Its field names outlive your database,
your framework, and usually your employment.

---

## 1. Field naming

Pick one convention and never deviate: `camelCase` or `snake_case`. Record it in the profile.
Mixing them within one API is the most visible sign that nobody was in charge.

| Rule | Why |
|---|---|
| Names are the consumer's words, not your schema's | A column rename must not be a contract break |
| Booleans read as assertions — `isActive`, `hasAccess` | Not `active_flag`, not `status` |
| Timestamps end in `At` — `createdAt`, `expiresAt` | Instantly recognizable, uniformly formatted |
| Durations name their unit — `timeoutMs`, `ttlSeconds` | `timeout: 30` is thirty of what? |
| Collections are plural | `items`, not `itemList` |
| No abbreviations you invented | `qty` is fine; `crtdBy` is not |

**Never expose an internal enum.** `status: "PENDING_INTERNAL_REVIEW_V2"` tells the consumer about
your workflow engine and freezes it. Map to a small, stable, documented vocabulary.

## 2. Types that do not betray you later

- **Money is never a float.** `{"amount": 1999, "currency": "USD"}` in minor units, or a decimal
  string. `0.1 + 0.2` is a reconciliation failure.
- **Timestamps are RFC 3339 UTC with an offset:** `2026-08-15T10:32:01Z`. Never a local time, never
  a bare epoch integer without documenting the unit.
- **A date is not a timestamp.** A birthday is `2026-08-15` — no time, no zone.
- **Identifiers are strings.** Even when they are numeric today. A numeric id becomes a string
  eventually, and that is a breaking change you could have avoided for free.
- **Enums are strings**, lowercase, documented, and closed. Document what a consumer should do on
  an unrecognized value — because you *will* add one.
- **Prefer a nullable field to omitting it**, and be consistent: a field that is sometimes absent
  and sometimes `null` forces every consumer to handle two cases for one meaning.

**Avoid booleans that will grow a third state.** `isActive` becomes active/paused/archived more
often than not. A small enum costs nothing now and saves a version later.

## 3. Response shape

Return the object. Do not wrap it in ceremony that carries no information:

```jsonc
// Good — a resource is a resource
{ "id": "ord_42", "status": "open", "totalAmount": 1999, "currency": "USD" }

// Pointless — `data` adds a level of nesting and no meaning
{ "data": { "id": "ord_42" } }

// Harmful — a success flag that duplicates the status code
{ "success": true, "data": { ... } }
```

An envelope is justified when it carries something real — pagination cursors, or a partial-failure
report. Then it is an envelope *because* it has fields; not by default.

**Collections do need an envelope**, because the page metadata has to live somewhere:

```jsonc
{ "items": [ ... ], "nextCursor": "eyJpZCI6NDJ9", "hasMore": true }
```

## 4. The error body is part of the contract (Law 7)

One shape, on every error path, from every endpoint:

```jsonc
{
  "error": {
    "code": "INSUFFICIENT_FUNDS",      // stable, machine-readable, documented
    "message": "The card was declined.", // human, may be reworded freely
    "requestId": "req_01H...",           // for support and correlation
    "fields": {                          // validation only
      "expiryMonth": "must be between 1 and 12"
    }
  }
}
```

**`code` is the API; `message` is not.** A consumer branching on `message` breaks the day someone
improves the wording. Publish the code list and treat it like any other part of the contract.

Rules:

- **Return all validation errors at once**, not the first. Fixing a form one round-trip per field
  is a terrible experience and an easy thing to get right.
- **Never leak internals** in a 5xx message — no stack traces, no hostnames, no SQL. Return a
  `requestId` instead; support can correlate it.
- **Never return `200` with an error inside** (Law 8).
- The error shape is identical whether the failure came from your handler, your framework, or your
  gateway. A consumer that must parse two error formats will parse neither correctly. Configure the
  framework's default error handler to match.

## 5. Requests

- **Reject unknown fields** rather than ignoring them — silently discarding a misspelled field
  means the consumer believes they set something they did not. Strict parsing turns a silent
  data-loss bug into an immediate, obvious error.
- **Size-limit every body**, every array, and every string. An unbounded request is a memory
  exhaustion vector and, eventually, an incident.
- **Validate into a trusted type at the boundary**, once, then trust it inside (`code-craft` Law 4).
- **`PATCH` semantics must be documented.** Does `{"tags": []}` clear the tags, and does omitting
  `tags` leave them alone? Both are defensible; only silence is not. JSON Merge Patch cannot express
  "set to null" versus "leave alone" — if you need that distinction, say so explicitly.

## 6. Nulls, absence, and partial responses

Three different things that consumers routinely confuse:

| Meaning | Representation |
|---|---|
| Known to be empty | `"middleName": null` |
| Not requested / not expanded | Field absent, and documented as such |
| Not permitted for this caller | Field absent — never `null`, which implies you know it is empty |

Document which applies. A field that is absent for three different reasons is unusable.

## 7. Content negotiation

- JSON unless there is a reason. Say `Content-Type: application/json; charset=utf-8` and mean it.
- Accept `Accept-Encoding: gzip` — a large list response compresses by an order of magnitude.
- For a binary or file result, return a short-lived signed URL rather than the bytes inline. It
  keeps the API cacheable, resumable, and out of your process memory.
