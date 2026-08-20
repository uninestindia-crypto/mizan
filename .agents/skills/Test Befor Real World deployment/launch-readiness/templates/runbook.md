# Deploy Runbook — <PRODUCT> v<VERSION>

> **The test for this document:** someone who did not build this system can execute every step at
> 3am, half-awake, without asking anyone a question. If any step fails that test, rewrite it.
>
> Gate G11.04 requires this file. Gate G11.05 requires a second person to have read or executed it.

---

## Header

| | |
|---|---|
| Version being deployed | `v___` |
| Commit SHA | `___` |
| Previous version (rollback target) | `v___` @ `___` |
| Deploy window | ___ (date, time, timezone) |
| Executor | ___ |
| Second pair of eyes | ___ |
| Abort authority | ___ (who can call it, without debate) |
| Expected total duration | ___ minutes |
| Rollback duration (measured in G11.07) | ___ seconds |

---

## ABORT CONDITION — read this before starting

**Stop and roll back immediately, without discussion, if any of these is true:**

- Error rate exceeds ___% (baseline is ___%)
- p95 latency exceeds ___ ms (baseline is ___ ms)
- The business metric drops more than ___% below baseline
- Any data-corruption or data-loss signal appears — **no threshold, no waiting**
- Any security issue appears
- **You do not understand what you are seeing**

That last one is not a softer condition than the others. Rolling back costs ___ seconds. Debugging
an anomaly at full production traffic costs hours and happens in front of users.

**Rollback command — have this in an open terminal before you start:**

```bash
<EXACT ROLLBACK COMMAND>
```

---

## Pre-flight — do not start until every line is ticked

- [ ] Launch readiness certificate says GO — `.launch/CERTIFICATE.md`
- [ ] Zero open S0 blockers
- [ ] Feature freeze in effect since `___` (commit `___`)
- [ ] CI green on the exact release commit `___`
- [ ] Baseline metrics captured within the last 15 minutes (G10.17) → recorded below
- [ ] Backup taken and its restorability verified → backup ID `___`, taken at `___`
- [ ] Rollback rehearsed on the production-like environment, took `___` seconds
- [ ] On-call is awake, aware, and reachable: `___`
- [ ] No dependency has a maintenance window inside the next 4 hours
- [ ] Status page access confirmed working
- [ ] The rollback command is open in a second terminal

**Baseline captured at `___`:**

| Metric | Value |
|---|---|
| Error rate | ___% |
| p50 / p95 / p99 latency | ___ / ___ / ___ ms |
| Request rate | ___ /min |
| Business metric (___) | ___ /hour |
| CPU / memory | ___% / ___ MB |
| DB connections | ___ / ___ |
| Queue depth | ___ |

---

## Step 1 — Take the backup

```bash
<EXACT COMMAND>
```

**Expect:** ___
**Takes:** about ___ minutes
**Verify:** ___ (a command that proves the backup exists and is non-empty)
**If it fails:** STOP. Do not proceed without a backup. No exceptions.

---

## Step 2 — Run the migration

```bash
<EXACT COMMAND>
```

**Expect:** ___
**Takes:** about ___ (measured at production scale in G5.03)
**Verify:** ___
**Watch while it runs:** lock duration, replication lag, error rate
**If it fails:** run `<EXACT ROLLBACK MIGRATION COMMAND>`, confirm the schema is restored, then stop and diagnose. Do not retry blindly.

---

## Step 3 — Deploy the code

```bash
<EXACT COMMAND>
```

**Expect:** ___
**Takes:** about ___ minutes
**Verify the version is actually live:**
```bash
curl -s https://<host>/version    # must print v___
```
**If it fails:** `<ROLLBACK COMMAND>`

---

## Step 4 — Smoke test against production

```bash
<EXACT SMOKE COMMAND>
```

**Expect:** all ___ checks green, under 5 minutes
**If any fails:** `<ROLLBACK COMMAND>` — do not investigate first, roll back first.

Then, by hand, on a real phone, on the real domain:
- [ ] Sign in
- [ ] Complete critical path 1: ___
- [ ] Complete critical path 2: ___
- [ ] Complete critical path 3: ___

---

## Step 5 — Staged rollout

| Stage | Traffic | Hold | Promote if | Roll back if | Done at | Actual numbers |
|---|---|---|---|---|---|---|
| 1 | Internal | 30 min | Smoke green, 0 new error types | Any new error type | | |
| 2 | 1% | 1 h | err ≤ base+0.1%, p95 ≤ base+10% | err > base+0.5% or p95 > base+25% | | |
| 3 | 10% | 2 h | Same + business metric within 5% | Same, or metric down >10% | | |
| 4 | 50% | 2 h | Same | Same | | |
| 5 | 100% | — | — | Same, watched for 72 h | | |

**Promotion command:**
```bash
<EXACT COMMAND, with the percentage as a parameter>
```

**At each stage, before promoting, confirm out loud:**
- [ ] The numbers are within threshold (write them in the table)
- [ ] The rollback is still available and still valid
- [ ] The full hold time has elapsed — **no early promotion**

---

## Rollback procedure

**Trigger:** any abort condition above.
**Authority:** ___ can call it alone, without discussion.
**Measured duration:** ___ seconds (from G11.07).

```bash
# 1. Stop the bleeding — flip the kill switch first if one exists
<KILL SWITCH COMMAND>

# 2. Roll back the code
<EXACT ROLLBACK COMMAND>

# 3. Verify the previous version is serving
curl -s https://<host>/version    # must print v<PREVIOUS>

# 4. Roll back the data, if required and possible
<EXACT DATA ROLLBACK COMMAND, or "NOT POSSIBLE — see below">

# 5. Smoke test the rolled-back version
<SMOKE COMMAND>

# 6. Post to the status page
<how>
```

**Data written by the new version between deploy and rollback:** ___
(What happens to it? Is it readable by the old version? Does it need manual repair? **Answer this
now, not during the incident.**)

**Rollback is no longer possible after:** ___
(Usually a specific migration or a data transformation. Name it, and say what the alternative is.)

---

## Post-deploy watch

| When | Who | Checks | Done |
|---|---|---|---|
| T+15 min | | Error rate, latency, smoke | |
| T+1 h | | Same + first user reports | |
| T+6 h | | Same + memory, connections, queue depth, first scheduled jobs | |
| T+24 h | | Full daily cycle: peak, nightly jobs, backups, log volume, **the bill** | |
| T+48 h | | Slow leaks, support themes | |
| T+72 h | | Weekly jobs, success metric, close out | |

---

## Contacts

| Role | Name | How to reach | Timezone |
|---|---|---|---|
| Executor | | | |
| Abort authority | | | |
| On-call (primary) | | | |
| On-call (secondary) | | | |
| Database owner | | | |
| Support lead | | | |
| Hosting provider support | | account/plan: | |
| Payment provider support | | account: | |

---

## If everything goes wrong

1. **Roll back first, diagnose second.** Always this order.
2. Post to the status page. A vague honest message beats silence.
3. Wake the secondary if the primary is not responding in ___ minutes.
4. Start an incident log with timestamps — write it as you go; you will not remember later.
5. Do not make more than one change at a time while diagnosing.
6. When it is over, write the postmortem within a week, blameless, and make exactly one process change.
