---
name: api-craft
description: >-
  The contract law for anything another program calls. Load this BEFORE designing or changing any
  endpoint, route, schema, payload, query, event, or migration — in any protocol and any language.
  Triggers on: "API", "endpoint", "route", "REST", "GraphQL", "gRPC", "webhook", "event", "queue",
  "message", "request", "response", "payload", "status code", "HTTP", "pagination", "paginate",
  "cursor", "filter", "sort", "idempotent", "idempotency", "retry", "rate limit", "versioning",
  "v1", "v2", "breaking change", "backward compatible", "deprecate", "schema", "data model",
  "database design", "table", "column", "index", "foreign key", "migration", "migrate", "alter
  table", "backfill", "OpenAPI", "swagger", "contract", "SDK", "integration". Owns the contract
  between systems: resource shape, method semantics, status codes, error bodies, pagination,
  idempotency, versioning and deprecation, the data model, and migrations that can run while old
  and new code are both live. Protocol-agnostic — the same laws bind REST, GraphQL, gRPC, events,
  and webhooks. Ships a contract checker that reads OpenAPI or scans routes in any framework it
  recognizes. If you are about to add an unversioned endpoint, a list that returns everything, a
  POST that is unsafe to retry, or a migration with no expand/contract plan, you needed this skill
  and did not load it.
---

# API Craft — The Contract Law

An API is a promise you cannot take back. Internal code can be refactored on a Tuesday; a published
contract is depended on by software you cannot see, run by people you will never meet, on release
schedules you do not control.

**The governing asymmetry:** adding to a contract is cheap and reversible. Removing from it, or
changing what it means, is neither. Design accordingly — start small, because everything you ship
you support.

## Scope — what this skill owns, and what it does not

| Concern | Owned by |
|---|---|
| Day-zero setup: the migration tool, its rollback, CI, config | `project-zero` |
| The inside of a function, naming, module boundaries | `code-craft` |
| **The contract between systems** — shape, semantics, evolution, data model | **this skill** |
| Authentication, authorization, injection, secrets | `secure-by-default` |
| How much testing the contract gets, and its gates | `founder-mode` |
| Anything a human looks at | `apple-grade-ui` |

The overlap worth naming: `project-zero` establishes *that* migrations have a rollback.
**This skill owns whether a given migration is safe to run at all** — which is a different and
harder question, because during a deploy old and new code are live at the same time.

---

## The ten laws (non-negotiable)

**Law 1 — The contract is the product; the implementation is private.**
Consumers depend on the shape, the names, the status codes, and the meanings — never on your
tables, your framework, or your internal types. Leaking an internal model into a response makes
every future refactor a breaking change.

**Law 2 — Design the contract before the code.**
Write the request and response for the real cases first. If you cannot describe the contract
without describing your database, you are designing the wrong thing.

**Law 3 — Everything is versioned from the first release.**
`/v1` on day one, when it costs nothing. Retrofitting a version onto a live unversioned API means
maintaining an unnamed legacy contract forever.

**Law 4 — Adding is safe; removing and changing meaning are not.**
Add optional fields freely. Never remove a field, narrow a type, add a required request field, or
change what a value *means* without a new version and a deprecation period.

**Law 5 — Every write is idempotent, or it is a duplicate waiting to happen.**
Networks retry: the client, the proxy, the queue, and the user's finger. A timeout does not mean
the work did not happen. Without an idempotency mechanism, one payment becomes two.

**Law 6 — Every list is paginated, from the first version.**
No endpoint returns "all of them". The table has 40 rows in development and 4 million in year two,
and the endpoint that worked fine becomes the outage.

**Law 7 — Errors are part of the contract, not an afterthought.**
Stable machine-readable codes, a documented shape, and the same shape on every path. A consumer
must be able to branch programmatically without matching on prose.

**Law 8 — Say what you mean, in the protocol's own vocabulary.**
Correct status codes, correct methods, correct cache semantics. `200 OK` with `{"error": ...}`
inside breaks every generic client, proxy, and retry policy ever written.

**Law 9 — Migrations run while both versions are live.**
During any deploy, old code and new code touch the same database simultaneously. A migration that
is only correct after every process restarts will break during the minutes it takes to get there.
Expand, migrate, contract — never rename in one step.

**Law 10 — The contract is documented and the documentation is generated.**
Hand-written API docs are wrong within a month. Generate from the spec or the types, publish it,
and make the spec the thing reviewers actually review.

---

## Step 0 — Install the contract checker (once per project, ~1 minute)

| Copy this file | To | Purpose |
|---|---|---|
| `scripts/check-api.mjs` | `scripts/check-api.mjs` | Contract rules: versioning, verbs in paths, list pagination, documented errors, path naming |

```bash
node scripts/check-api.mjs
```

It reads an OpenAPI/Swagger document if the project has one — that is the richest source — and
otherwise scans source for route registrations in any framework it recognizes. It reports
`UNKNOWN` rather than guessing when it can find neither.

**What it cannot check** is most of this document: whether a resource is the right abstraction,
whether a field means what its name says, whether a change is genuinely backward compatible for
real consumers. Those need judgment and belong in review.

---

## Workflow — every contract change

### 1. Write the contract first (Law 2)
The request and the response, for the success case and at least two failure cases. In OpenAPI, in a
`.proto`, in a schema file — something a consumer could code against before you have written a
line of the implementation.

### 2. Check it against the laws
Versioned? Paginated? Idempotent? Errors documented? Status codes honest?

### 3. Classify the change (Law 4)
**Additive** (new optional field, new endpoint) → ship it.
**Breaking** (removal, narrowing, new required field, changed meaning) → it needs a new version and
a deprecation plan. See `references/05-versioning-and-evolution.md`.

If you are not sure which it is, assume breaking. The cost of being wrong in that direction is a
version nobody needed; the cost of the other direction is somebody's production outage.

### 4. For any schema change, write the migration plan (Law 9)
Expand → backfill → switch reads → contract, across separate deploys.
`references/06-data-and-migrations.md` has the table of what is safe.

### 5. Verify
```bash
node scripts/check-api.mjs
```
Then the project's own contract tests, and `references/08-review-checklist.md`.

---

## What ships with this skill

| Path | What it is |
|---|---|
| `scripts/check-api.mjs` | The contract checker. Reads OpenAPI/Swagger, or scans routes across common frameworks; `UNKNOWN` over guessing |

No code assets: a contract is expressed in the project's own schema language, and a canned handler
in one framework would be wrong everywhere else. The laws and the checker are the portable parts.

## References — load what the task needs

| File | Load it when |
|---|---|
| `references/01-contract.md` | Designing any endpoint: resources, methods, status codes, naming |
| `references/02-payloads-and-errors.md` | Request/response shape, the error body, content negotiation |
| `references/03-pagination-and-filtering.md` | Any endpoint that returns more than one of something |
| `references/04-idempotency-and-reliability.md` | Any write, retry, timeout, rate limit, or long-running operation |
| `references/05-versioning-and-evolution.md` | Changing an existing contract; deprecating anything |
| `references/06-data-and-migrations.md` | Schema design, and any migration — **read before writing one** |
| `references/07-beyond-http.md` | GraphQL, gRPC, events, queues, webhooks, batch and file interfaces |
| `references/08-review-checklist.md` | Before shipping any contract change |

Related skills, where installed: `project-zero` (migration tooling and rollback), `code-craft`
(the code behind the handler), `secure-by-default` (authn/authz, injection, rate limits as a
control), `founder-mode` (the gates). Not installed is not a blocker.

---

## The failure modes that give it away

- **Verbs in paths** — `/getUser`, `/createOrder`, `/user/delete`. The method is the verb.
- **`200 OK` with an error inside.** Every proxy, cache, and retry policy now behaves wrongly.
- **A list endpoint with no limit.** Fine at 40 rows, an outage at 4 million.
- **A POST with no idempotency key** that charges money or sends mail.
- **Internal enum values leaking** — `status: "PENDING_INTERNAL_REVIEW_V2"`.
- **A database column name in a JSON response** — now the column cannot be renamed.
- **Timestamps with no timezone**, or a date and a datetime using the same field name.
- **Money as a float**, or money with no currency.
- **A boolean that later needs a third state** — almost every `is_active` eventually does.
- **A `data` field wrapping everything, with nothing else in the envelope.** Pure ceremony.
- **A migration that renames a column in one step.** It breaks during the deploy, not after.
- **`ALTER TABLE` on a large table with no lock analysis.** Locks the table; the API goes down.
- **A webhook with no retry policy, no signature, and no replay protection.**

---

## Scope discipline

This skill makes a contract correct; it does not make it *larger*. Do not add endpoints nobody
asked for, options nobody set, or a GraphQL layer over a REST API that was working. **Every field
you add is a field you support forever** — the most valuable thing this document can do is stop
you shipping one you did not need.
