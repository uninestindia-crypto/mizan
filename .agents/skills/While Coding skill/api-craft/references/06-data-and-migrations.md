# 06 — Data model and migration safety

`project-zero` establishes *that* the project has a migration tool with a rollback you have
executed. **This file owns whether a specific migration is safe to run** — a different and harder
question, because of one fact:

> **During any deploy, old code and new code are live at the same time.**

A migration that is only correct once every process has restarted will break during the minutes it
takes to get there. That window is where migration incidents happen.

---

## 1. Data model basics

- **One fact in one place.** Derived values are computed, not stored — unless you measured a need,
  in which case one side is authoritative and the other is explicitly a cache with a stated
  invalidation rule.
- **Constraints belong in the database.** `NOT NULL`, `UNIQUE`, `CHECK`, foreign keys. Application
  validation is a nicety; the database constraint is the guarantee, and it holds when two instances
  race, when a script runs, and when someone fixes data by hand.
- **A unique constraint is your best idempotency mechanism** — one refund per charge, one
  membership per (user, team).
- **Never reuse a column for a second meaning.** `notes` holding JSON for some rows is a parser and
  a bug.
- **Money in minor units as an integer, or a decimal type.** Never a float.
- **Timestamps are `timestamptz`, stored UTC.** A naive timestamp is a bug that surfaces in October.
- **Soft deletes need a plan.** `deleted_at` means every query must filter it, and one that forgets
  leaks deleted data. Decide once, enforce with a view or a default scope.
- **Index every column you filter, sort, or join on.** An unindexed filter exposed through an API is
  a performance vulnerability a consumer can trigger at will.

## 2. What is safe to run online

| Change | Safe? | How to do it |
|---|---|---|
| Add a nullable column | ✅ | Straightforward |
| Add a column with a default | ⚠️ | Instant on modern Postgres/MySQL 8; a full table rewrite on older versions — **check your version** |
| Add a table | ✅ | — |
| Add an index | ⚠️ | `CREATE INDEX CONCURRENTLY`. A plain `CREATE INDEX` locks writes for the duration |
| Drop an index | ✅ | `DROP INDEX CONCURRENTLY` |
| Add `NOT NULL` | ❌ as one step | Add nullable → backfill → validate → set the constraint |
| Add a `CHECK` / foreign key | ⚠️ | Add `NOT VALID`, then `VALIDATE CONSTRAINT` separately — the second takes a weaker lock |
| Rename a column or table | ❌ | Expand/contract (§3). Never in one step |
| Change a column type | ❌ | New column → backfill → swap |
| Drop a column | ❌ | Stop writing → deploy → wait → drop |
| Backfill a large table | ⚠️ | In bounded batches with pauses. Never one statement |

**`ALTER TABLE` takes a lock.** On a large table under load, a lock that is held while the table is
rewritten is an outage — the API stops, because every query queues behind it. Know which of your
operations rewrite and which only touch metadata, for **your** database and **your** version.

Also: a migration that waits for a lock **queues everything behind it**. A long-running read can
block your `ALTER`, which then blocks every subsequent query. Set a short `lock_timeout` and retry
rather than letting a migration take the service down while it waits politely.

## 3. Expand / contract — the whole discipline

Because both versions of the code are live, every incompatible change becomes a sequence of
compatible ones. Renaming `name` → `full_name`:

```
Deploy 1  EXPAND    add full_name (nullable). Nothing reads it.
Deploy 2  DUAL WRITE code writes BOTH columns; still reads name.
          BACKFILL   copy name → full_name in batches, until caught up.
Deploy 3  SWITCH     code reads full_name; still writes both.
                     ← this is the safe resting point. Stop here for a while.
Deploy 4  STOP WRITE code writes only full_name.
Deploy 5  CONTRACT   drop name.
```

Five deploys to rename a column, and every one is independently reversible. That is the cost of not
having an outage, and it is cheap compared to the alternative.

**Deploy 3 is the resting point.** Sit there long enough to be confident — days, not minutes. The
last two steps are the destructive ones and there is never a reason to rush them.

**Never combine a schema migration and a code change that requires it in one deploy.** That is the
single most common cause of migration incidents: the migration runs, the old pods are still up, and
they are now writing to a schema that no longer matches their assumptions.

## 4. Backfills

- **Batch, always.** `UPDATE ... WHERE id BETWEEN x AND y`, a few thousand rows at a time, with a
  pause. One statement over 10 million rows holds a transaction open, bloats the write-ahead log,
  and blocks vacuum.
- **Idempotent and resumable.** It will be interrupted. Record progress; re-running must be safe.
- **Throttle on replication lag.** A fast backfill that outruns the replicas takes down every read
  replica, which is usually most of your traffic.
- **Run it out-of-band**, not inside the migration transaction. Migrations should be fast; backfills
  are jobs.
- **Verify before contracting.** Count the rows that still need it, and confirm it is zero, before
  any destructive step.

## 5. Every migration has a `down` — and you have run it

`project-zero` requires the tooling; this is the per-migration bar:

- Write the `down` at the same time as the `up`, and **execute it against a database with data**.
- **Some things cannot be undone.** Dropping a column loses data; a `down` that recreates an empty
  column is a lie. For destructive steps, the rollback plan is *restore from backup* — and that
  means the backup must have been restored at least once, or it is a rumor.
- **Test the migration against production-sized data**, not an empty schema. A migration that runs
  in 40ms on a dev database can take 40 minutes on production and hold a lock the whole time.

## 6. The pre-flight checklist

Before any migration reaches production:

- [ ] Does it lock, and for how long, on **this** database at **production** size?
- [ ] Is it safe with the previous code version still running?
- [ ] Is it safe with the *next* version running (rollback path)?
- [ ] Is the backfill batched, throttled, resumable, and out-of-band?
- [ ] Has the `down` been executed against realistic data?
- [ ] If it is destructive, is there a verified backup and a stated point of no return?
- [ ] Is `lock_timeout` set so a blocked migration fails instead of queueing the service?
- [ ] Is there a plan to verify success — a query whose result proves it worked?

**A migration is the one change that a deploy rollback does not undo.** Every other mistake can be
fixed by shipping the previous version. This one cannot, which is why it gets its own checklist.
