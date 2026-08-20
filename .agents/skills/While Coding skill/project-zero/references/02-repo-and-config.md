# 02 — Repo layout and the configuration contract

Two decisions that look like housekeeping and are actually architecture: where code lives, and how
the program learns about its environment.

---

## 1. The layout encodes the architecture (Law 9)

A directory tree is a dependency diagram that everyone can see without opening a file. Decide the
boundaries on day zero, because moving a file later is a merge conflict with every open branch.

### The default layout

```
.
├── src/
│   ├── config.ts            ← the configuration contract (Law 3)
│   ├── errors.ts            ← the error taxonomy (Law 4)
│   ├── logger.ts            ← structured logging + health (Laws 5, 8)
│   ├── <domain>/            ← one folder per business concept, NOT per layer
│   │   ├── <domain>.service.ts
│   │   ├── <domain>.repository.ts
│   │   └── <domain>.test.ts
│   ├── http/                ← the delivery mechanism: routes, middleware
│   └── index.ts             ← composition root: wire everything, start
├── migrations/              ← every one with a `down`
├── scripts/
│   └── verify-day-zero.mjs
├── docs/adr/
├── .github/workflows/ci.yml
├── .env.example             ← every variable, no values
├── .nvmrc
└── README.md
```

### Group by domain, not by layer

The single most consequential layout choice, and the one most often made wrong:

| Do this | Not this |
|---|---|
| `src/billing/{service,repository,test}` | `src/services/`, `src/repositories/`, `src/models/` |

Layer-grouping (`controllers/`, `services/`, `models/`) looks organized and is actively harmful:
every feature is spread across four directories, so every change is a four-directory diff, and
nothing tells you where a concept begins or ends. Domain-grouping means **a feature is a folder**,
deleting a feature is deleting a folder, and the blast radius of a change is visible in the tree.

### The dependency direction, and enforcing it

```
http/  →  <domain>/  →  (nothing)
              ↓
        config, errors, logger  ← leaves; import from anywhere, import nothing
```

Three rules, all mechanically checkable:

1. **Domain code never imports from `http/`.** Business logic must not know it is behind HTTP, or
   it cannot be tested without one and cannot be reused by a job or a queue consumer.
2. **Domains do not import each other's internals.** Cross-domain access goes through the other
   domain's public entry, or through the composition root.
3. **No cycles, ever.** A cycle means the two modules are one module that has not admitted it.

Enforce these on day zero with a lint rule (`eslint-plugin-boundaries`, `import/no-cycle`,
`depcruise`, Go's internal packages). **A boundary that is documented but not enforced is a
boundary that will be crossed in week three,** by someone in a hurry, and never restored.

### Naming

- **No `utils/`, `helpers/`, `common/`, `shared/`, or `lib/`.** These are where code goes when
  nobody decided where it belongs. They only grow, they become import magnets, and they eventually
  contain the whole application. Name the module for what it does: `money.ts`, `retry.ts`, `slug.ts`.
- **Filenames match their export.** `UserService` lives in `user.service.ts`.
- **Tests live beside the code** they test. A test three directories away gets deleted with the
  wrong file and is never read.

### On monorepos

Do not start with one. A monorepo solves the problem of several deployables sharing code; on day
zero you have one deployable and no shared code, so it is pure tooling cost. Split when you have
the second deployable and can name what they share.

---

## 2. The configuration contract (Law 3)

**Copy `assets/config.ts`.** This section explains what it does and why it is shaped that way.

### The failure it prevents

```ts
// Somewhere, four directories deep, inside a function:
const key = process.env.STRIPE_KEY;
```

Three things are now true, all bad:

1. The set of variables this service requires is **unknowable** without reading every file.
2. A typo — `STRIPE_KEY` vs `STRIPE_API_KEY` — is `undefined`, which becomes `"undefined"` in a
   header, which is an authentication failure three layers from its cause.
3. The service **boots successfully** into a state where it cannot do its job. The error surfaces
   on first customer request rather than on deploy.

### The four rules

| # | Rule | Why |
|---|---|---|
| 1 | **One schema, one file.** Every variable declared in `config.ts`. | Makes the contract knowable |
| 2 | **Parse once, at boot.** Not lazily, not per request. | Fails at deploy, not at first use |
| 3 | **Refuse to start when wrong.** Exit non-zero with every problem listed. | Turns an incident into a failed deploy |
| 4 | **Never read `process.env` elsewhere.** Import `config`. | Rule 1 stays true |

Rule 3 says **every** problem, not the first. Fixing configuration one redeploy at a time is how an
afternoon disappears — the shipped implementation collects all problems and prints them together.

### `.env.example` is part of the contract

Commit it, with every variable and **no real values**. It is the documentation a new engineer reads
first, and the gate checks that it exists.

```bash
# .env.example
DATABASE_URL=postgres://user:pass@localhost:5432/app_dev
PORT=3000
LOG_LEVEL=info
```

### Secrets

- **`.env` is in `.gitignore` from the first commit**, before it exists. The day-zero gate fails
  the build if a real `.env` is committed.
- **A secret committed once is compromised**, even after deletion — it is in the history, and the
  history is on every clone. Rotate it; do not just delete it.
- **In production, secrets come from the platform's secret manager**, not from a file.
- Secrets never reach logs. The shipped `logger.ts` redacts by key name, and the shipped
  `config.ts` never echoes a secret's value in an error — both are verified behaviors, not
  intentions.
