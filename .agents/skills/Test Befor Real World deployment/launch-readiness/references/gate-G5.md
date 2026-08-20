# G5 — Data & Migration Safety

> **Purpose.** Data survives the deploy, survives the rollback, and survives the disaster.
>
> **Veto holder.** Whoever owns the data. **Entry.** G4 passed. **Exit.** 16 checks resolved.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**Why this gate is uniquely unforgiving.** Every other category of failure is recoverable. A slow
page recovers. A broken feature recovers. Lost or corrupted customer data does not recover, and no
amount of engineering afterwards undoes it. **G5.02 and G5.05 — the executed rollback and the
executed restore — are the two checks in the entire 216 that teams most often mark as done without
doing.**

---

#### G5.01 · Migrations run forward from an empty database — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G5.01 -- bash -c '<drop and recreate an empty database> && <migrate command>'
  ```
  e.g. `npx prisma migrate reset --force`, `alembic upgrade head`, `python manage.py migrate`, `rails db:schema:load`
- **Pass** — every migration applies in order against nothing, with no manual steps.
- **If a migration needs a manual step** — that step is part of the deploy and must be in the runbook (G11.04). An undocumented manual step is how a deploy fails at 2am with the database half-migrated.

#### G5.02 · ROLLBACK EXECUTED and TIMED — `S0` `cmd`

**Executed. Not written. Not "we have a down migration". Run it.**

- **Run** —
  ```bash
  LRK run G5.02 --title "migrate up"   -- <migrate command>
  LRK run G5.02 --title "ROLLBACK executed and timed" -- <rollback command>
  LRK run G5.02 --title "re-apply after rollback" -- <migrate command>
  ```
  e.g. `alembic downgrade -1`, `npx prisma migrate resolve --rolled-back <name>`, `rails db:rollback`, or the hand-written down-SQL.
- **Pass** — the rollback completes, the schema returns to its previous shape, existing data is intact, and **the duration is recorded** (the kit records it automatically).
- **If there is no down migration** — that is a finding. Either write one, or declare the migration irreversible and provide the compensating control (a feature flag, a dual-write period, a verified backup taken immediately before). Record which. Cross-references G11.08.
- **The trap** — a down migration that drops a column you added. Running it destroys any data written to that column since the deploy. Test with real rows present and state explicitly what is lost.

#### G5.03 · Migration rehearsed at production scale, timed, lock duration measured — `S0` `cmd`

- **Do** — restore a production-sized copy (or generate one at the same row counts) and run the migration against it. Measure total time **and** how long any table is locked.
- **Run** — `LRK run G5.03 -- bash -c 'time <migrate command>'`, and while it runs, in another shell: `SELECT pid, state, wait_event, query FROM pg_stat_activity WHERE state != 'idle';`
- **Pass** — the migration completes within the deploy window, and no lock is held long enough to time out live traffic.
- **The classic disaster** — `ALTER TABLE users ADD COLUMN ... NOT NULL DEFAULT ...` tested on 40 rows takes 8ms; on 40 million rows it takes an `ACCESS EXCLUSIVE` lock for nine minutes and every request in the application times out. **Testing a migration on your dev database's 40 rows proves nothing.**

#### G5.04 · Old code against new schema — `S0` `cmd`

- **Do** — deploy the new schema, then run the **previous release's** test suite against it.
  ```bash
  git stash && git checkout <previous-release-tag>
  LRK run G5.04 --title "old code vs new schema" -- <test command>
  git checkout - && git stash pop
  ```
- **Pass** — green.
- **Why it is S0** — during any rolling deploy there is a window of minutes where old and new code run simultaneously against one database. If the new migration renames or drops a column the old code still reads, every request served by an old instance fails during that window. This is what "the deploy caused a five-minute outage" usually means.
- **The safe pattern** — expand, then migrate, then contract, across two releases. Never rename in one step.

#### G5.05 · BACKUP RESTORE DRILL performed end to end — `S0` `cmd`

**A backup that has never been restored is not a backup. It is a hope with a storage bill.**

- **Do** — take the most recent production backup, restore it into a scratch environment, and verify the data is actually there and correct. Time every phase.
- **Run** —
  ```bash
  LRK run G5.05 --title "backup taken"       -- <backup command>
  LRK run G5.05 --title "RESTORE into scratch, timed" -- bash -c 'time <restore command>'
  LRK run G5.05 --title "verify restored data" -- <query proving row counts and a spot-check record>
  ```
- **Pass** — restored, verified, timed. Record: how old the backup was, how long the restore took, and what was lost.
- **Check all four** — backups are (1) actually running on schedule, (2) stored somewhere the production credentials cannot delete, (3) encrypted, (4) restorable by someone other than the person who set them up.
- **The failure mode this catches** — backups that have been silently failing for seven months, discovered on the day they are needed.

#### G5.06 · RPO and RTO stated as numbers and proven — `S0` `manual`

- **RPO** (Recovery Point Objective) — how much data you can afford to lose. If backups run nightly, your RPO is 24 hours. Say so out loud; it is often a surprise to whoever signs off.
- **RTO** (Recovery Time Objective) — how long a full restore takes. You measured this in G5.05. Use the measured number, not the aspirational one.
- **Record** — `LRK manual G5.06 --status pass --note "RPO 15 min (PITR / WAL archiving). RTO measured 41 min for 180GB, including DNS. Both accepted by <owner> on <date>."`

#### G5.07 · Integrity constraints present — `S1` `cmd`

- **Run** — `LRK run G5.07 -- <dump the schema>` then read it.
- **Pass** — foreign keys exist and are enforced (not just documented); unique constraints on anything that must be unique (email, slug, external ID); `NOT NULL` on anything required; `CHECK` constraints on enums, ranges, and non-negative amounts.
- **Why in the database rather than only in code** — application-level validation is bypassed by every migration script, admin tool, background job, and future service. The database is the last line, and it is the only one that always runs.

#### G5.08 · No destructive migration without a verified backup immediately before — `S0` `manual`

- **Do** — scan this release's migrations for `DROP`, `TRUNCATE`, `DELETE`, `ALTER ... DROP COLUMN`, and any type change that narrows (varchar(255) → varchar(50), bigint → int, timestamp → date).
  ```bash
  LRK run G5.08 --title "destructive migration scan" -- git grep -niE "drop table|drop column|truncate|delete from|alter column|drop constraint" -- migrations db/migrate prisma
  ```
- **Pass** — none, or each is preceded in the runbook by an explicit backup step with a verified restore.
- **The safest pattern** — never drop in the same release that stops using. Stop writing in release N, drop in release N+2, after you have confirmed nothing reads it.

#### G5.09 · PII inventory — `S0` `manual`

- **Do** — write the table. Every column that identifies a person: name, email, phone, address, IP, device ID, photo, location, payment detail, health data, government ID, free-text notes (which always end up containing personal data).
- **For each** — where it is stored, why it is needed, how long it is kept, who can read it, whether it is encrypted, and whether it leaves your infrastructure.
- **Record** — attach the table. `LRK attach G5.09 ./pii-inventory.md --caption "PII inventory: 14 columns across 5 tables"`
- **You cannot do G9 without this.** Every privacy obligation is derived from this table.

#### G5.10 · Sensitive data encrypted at rest and in transit — `S0` `hybrid`

- **Pass** — database volume encryption on; backups encrypted; TLS everywhere including between internal services; application-level encryption for the most sensitive fields (government IDs, health data, payment tokens); keys managed by a key service, not committed and not in an environment variable if it can be avoided.

#### G5.11 · Data export and deletion work — `S0` `hybrid`

- **Do** — actually export one user's data and actually delete one user. Time both.
- **Check on delete** — is it a soft delete or a hard delete? Are backups covered by the deletion policy? Are copies in the analytics warehouse, the email provider, the CRM, and the log aggregator also deleted? Is the deletion cascaded correctly, or does it leave orphaned rows and broken foreign keys?
- **Pass** — both work end to end, and you can state exactly what remains after a deletion and why.

#### G5.12 · No seed or test data in production — `S0` `cmd`

- **Run** — `LRK run G5.12 -- git grep -nlE "seed|fixture|demo|sample|faker|test@|admin@example|password123|changeme" -- . | head -40`
- **Pass** — no seeding runs in production; no test account exists with a weak or known password; no demo tenant with real-looking data.
- **The classic** — a `seed.ts` that creates `admin@example.com / admin123` and is wired into the deploy script "just for staging".

#### G5.13 · N+1 queries checked on every list endpoint — `S1` `cmd`

- **Do** — enable query logging, load each list endpoint with 25 records, and count the queries.
- **Run** — `LRK run G5.13 -- bash -c '<enable query log> && curl -s "$BASE/api/orders?limit=25" > /dev/null && <count queries in the log>'`
- **Pass** — the query count does not scale with the row count. 3 queries for 25 rows is fine. 76 queries for 25 rows is an N+1 and it will take the database down the first time somebody has 500 records.

#### G5.14 · Every critical-path query has a supporting index — `S1` `cmd`

- **Run** — `LRK run G5.14 -- <psql/mysql> -c "EXPLAIN ANALYZE <the actual query>"`
- **Pass** — no sequential scan on a large table on a critical path; every foreign key used in a join is indexed; every column used in a `WHERE`, `ORDER BY`, or `JOIN` on a hot path is covered.
- **Also check** — indexes that are never used (they cost write performance for nothing): `SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0;`

#### G5.15 · Connection pool sized; exhaustion tested — `S1` `hybrid`

- **Do** — state the pool size, and multiply: pool size × number of application instances must be under the database's `max_connections`, with headroom for migrations and admin sessions.
- **Test** — saturate the pool and observe. A request should queue and then fail with a clear error, not hang forever.
- **The serverless trap** — every serverless function instance opens its own connection. A hundred concurrent invocations means a hundred connections. Use a pooler.

#### G5.16 · Replica lag / read-after-write — `S1` `hybrid`

- **Do** — if reads go to a replica, write a record and immediately read it back.
- **Pass** — the user sees their own write. If not, route read-after-write to the primary, or make the UI reflect the pending state honestly.
- **The bug users report** — "I saved it and it disappeared." They refresh, it is there. Nobody can reproduce it. It is replica lag.

---

## Exit bar for G5

```bash
LRK status --gate G5
```

Confirm, out loud, three specific numbers before you leave this gate:

1. **How long the rollback took** (G5.02) — in seconds.
2. **How long a full restore takes** (G5.05) — in minutes.
3. **How much data you would lose** in the worst case (G5.06) — in minutes or hours.

If you cannot state all three from measurements you personally took, this gate is not passed —
whatever the checklist says.
