# 04 — CI, deploy, and the two rollbacks

The machine that ships the product. Built on day zero, when it is trivial, because it never gets
cheaper.

---

## 1. CI (Law 6)

**Copy `assets/ci.github.yml`** and change the three marked lines.

### Why day zero and not "once we have something"

Adding CI to a four-file repo takes ten minutes and passes immediately. Adding it to a
four-hundred-file repo means it goes red on day one against a backlog nobody has time to fix — and
a red pipeline everyone ignores is strictly worse than no pipeline, because it trains the team to
ignore signals.

### What runs on every push

| Stage | Command | Fails the build when |
|---|---|---|
| Install | `npm ci` | The lockfile and manifest disagree |
| Typecheck | `tsc --noEmit` | Any type error |
| Lint | `eslint .` | Any error-level rule |
| Format | `prettier --check` | Any file is unformatted |
| Test | the full suite | Any test fails |
| Build | the production build | It does not build |
| Migrate up → down → up | migration commands | The rollback path is broken |
| Audit | `npm audit --audit-level=high` | A known-exploitable dependency |
| Secret scan | gitleaks | A credential appears in history |

**The migrate up/down/up step is the one people leave out**, and it is the highest-value step in
the list. It exercises the rollback path automatically on every push, which is the only way a
`down` migration stays correct — an untested `down` is written once, never run, and wrong by the
time you need it.

### Non-negotiables

- **Red main is an emergency**, not a ticket. The next person to push inherits a broken signal.
- **Every job has a timeout.** A hung job must fail, not burn an hour.
- **Cancel superseded runs** (`concurrency`), or a busy branch queues runs until feedback is useless.
- **Least privilege**: `permissions: contents: read` at the workflow level, more only where needed.
- **Checks keep running after one fails** (`if: '!cancelled()'`), so one push surfaces every problem
  rather than one problem per push.
- **CI is the source of truth.** "It works on my machine" is a statement about your machine.

---

## 2. Deploy

### The rules

1. **Automated from the first deploy.** The first one is the most worth automating, because it is
   the one you repeat most while the project is young. Deploying by hand "just to see" means the
   real procedure is a memory.
2. **One command, or one merge.** If the deploy has steps a human performs in order, it has steps a
   human will perform out of order at 2am.
3. **Immutable artifacts.** Build once, promote that exact artifact through environments. Rebuilding
   per environment means production runs something no environment tested.
4. **Deploy is not release.** Ship code dark behind a flag, then turn it on. Separating them means
   the risky moment is a config change you can undo in seconds, not a deploy.

### Environments

| Environment | Purpose | Data | Must have |
|---|---|---|---|
| Local | Development | Seeded fake | One command to start from a clean clone |
| CI | Verification | Ephemeral | Full suite on every push |
| Staging | Production-like rehearsal | Anonymized or synthetic | The same deploy path as production |
| Production | Real | Real | Rollback, monitoring, alerting |

**Never real customer data outside production.** Not "temporarily", not "just the one table". It
becomes permanent, and it is a breach waiting for a misconfigured bucket.

If there is no staging, `founder-mode` treats that as a G7 blocker for anything above T2 — raise it
on day zero rather than discovering it three days before launch.

---

## 3. The two rollbacks (Law 7)

There are two, they fail differently, and **both must be executed on day zero** — not written down.

### Deploy rollback

Return to the previous version.

```
1. What is the exact command?        <the command>
2. How long does it take?            <measured, in seconds>
3. Who can run it?                   <names, and how they are reached>
4. What does it NOT undo?            <migrations, sent emails, charged cards,
                                      published events, third-party writes>
```

Question 4 is the one that matters. A deploy rollback returns your *code*; it does not un-send an
email or un-charge a card. Knowing the boundary before an incident is the difference between a
rollback and a cleanup.

### Migration rollback

**Every migration ships with a `down` that has been executed.** Not written — executed, against a
database with data in it.

| Change | Reversible? | How to make it safe |
|---|---|---|
| Add nullable column | Yes | Trivial |
| Add table / index | Yes | Build indexes concurrently |
| Add NOT NULL column | Risky | Add nullable → backfill → add constraint, in three deploys |
| Rename column | **No, as one step** | Expand/contract: add new → write both → backfill → read new → drop old |
| Drop column / table | **No** | Stop writing → wait a full retention period → then drop |
| Change a type | **Usually not** | New column, backfill, swap |

**The expand/contract pattern is the whole discipline**, and it exists because of one fact: during
a deploy, old code and new code run *at the same time*. A migration that only works after every
process restarts will break during the thirty seconds it takes to get there.

A destructive migration is a **one-way door**. Take a backup you have restored from — an untested
backup is a rumor — and stage the destruction across releases.

### Rehearse it on day zero

```bash
# Deploy something trivial, then undo it. Paste both outputs.
<deploy command>              # note the version
<rollback command>            # note the time it took

# Migrate up, then down, against a database with rows in it.
<migrate up>
<migrate down>
<migrate up>
```

This costs twenty minutes on day zero and is nearly impossible to arrange under pressure — which
is exactly when you will need it. A greenfield project that reaches its first launch without a
rehearsed rollback has to invent one during its first incident, from memory, while users are
affected.

**The day-zero gate marks both rollbacks `TODO` until a human attests to having run them**, by
name and date:

```bash
node scripts/verify-day-zero.mjs --attest deploy-rollback --by "Your Name"
```

The attestation is recorded in `.project-zero.json`. Commit it — it is project evidence.
