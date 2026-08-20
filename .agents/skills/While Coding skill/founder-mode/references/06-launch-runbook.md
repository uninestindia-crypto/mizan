# 06 — The Launch Runbook

P7 preparation, P8 execution, P9 watch. Hour by hour.

**The premise of this file:** launch day should be boring. Every decision that could be made in
advance, by calm people, has been made in advance by calm people. What remains on the day is
execution and observation.

## Contents

- [T-7 days: prepare](#t-7-days--prepare)
- [T-3 and T-1 days: prove and freeze](#t-3-days--freeze-and-prove)
- [T-0: staged launch](#t-0--the-window)
- [T+1h through T+72h: watch](#t1h-t6h-t24h-t48h-t72h--the-watch)
- [Postmortem and runbook template](#p9--postmortem)

---

## T-7 days — Prepare

**Owner:** `launch-engineer`.

1. **Write the runbook** (template at the bottom of this file). Numbered steps, exact commands,
   expected output at each step, and an abort condition. Written for someone who did not build
   this.
2. **Capture the baseline.** Before anything changes, record the current production numbers:
   error rate, p50/p95/p99 latency, throughput, the business metric (signups, orders, messages —
   whatever the product's heartbeat is), DB connections, memory, queue depth. **Without a baseline
   you cannot distinguish "elevated" from "Tuesday," and every launch-day judgment becomes a
   guess.**
3. **Set the thresholds now**, as numbers, while nobody is under pressure:

   | Signal | Promote if | Hold if | **Roll back if** |
   |---|---|---|---|
   | Error rate | ≤ baseline × 1.1 | ≤ baseline × 1.5 | > baseline × 2 for 5 min |
   | p95 latency | ≤ baseline × 1.2 | ≤ baseline × 1.5 | > baseline × 2 for 5 min |
   | Business metric | ≥ baseline × 0.95 | ≥ baseline × 0.9 | < baseline × 0.8 for 15 min |
   | New-code errors | 0 unknown types | known + handled | any data-integrity error, immediately |
   | Support volume | normal | +50% | +200%, or one report of data loss |

   Fill in the real numbers for this product. The row that matters most is the last column: it is
   the decision you are pre-authorizing your 2am self to make without debate.
4. **Rehearse the rollback.** Execute it, against realistic data, and time it. Record the time in
   the runbook. If rollback takes 40 minutes, that changes your entire launch strategy and you need
   to know now.
5. **Fire every alert.** Deliberately trigger each monitor and confirm it reaches a human on the
   channel they will actually be watching. Alerts that route to an unmonitored channel are worse
   than no alerts.
6. **Verify the environment contract**: every env var, secret, credential, quota, DNS record, TLS
   cert expiry, third-party webhook registration, and IAM permission present in the target.
7. **Back up, and test the restore** to a different machine. Untested backups are folklore.
8. **Name the crew.** Who is executing, who is watching, who decides on a rollback, who talks to
   users. Confirm they are actually available for the window.

---

## T-3 days — Freeze and prove

1. **Feature freeze.** Only Blocker fixes. Every admitted fix restarts verification for the areas
   it touches — a fix is a change, and changes are untrusted until proven.
2. **Full clean-state verification** (`verifier`, mandatory): fresh clone → install → migrate from
   zero → seed → full test suite → build → start → critical path. Raw output, every step.
3. **Deploy to a production-like environment** and exercise the entire critical path *there*, with
   production-like data volume and production-like configuration.
4. **Time the migration** on a production-scale copy. Record: total duration, longest lock, whether
   the app remains serving. If it locks a hot table for four minutes, you need a different
   migration strategy — find that out now, not during the window.
5. **Dry-run the runbook end to end** in the staging environment, with the person who will execute
   it on the day doing the execution and the author only observing. Every place they hesitate is a
   runbook defect. Fix the runbook, not the person.
6. **Support brief to the support crew** (`scribe`): what is changing, the five likely questions,
   known limitations, and how to escalate.

---

## T-1 day — Final checks

1. Steps 1-14 of `11-pre-launch-procedure.md` walked in order and recorded `READY` for the exact
   candidate revision; this includes the full G7 checklist in `03-gates.md`.
2. Confirm the crew and the window; confirm nobody is deploying anything else.
3. Confirm rollback is still valid against the current state of production.
4. Pre-write the user comms: the "we're live" note, and the "we hit a problem" note. Writing the
   bad-news message while calm produces a message you will be glad to send.
5. **Sleep.** Launching tired is a decision to make worse decisions.

**Do not launch:** Friday afternoon, the last day before a holiday, the last hour of the day, when
the person who can roll back is unreachable, or when anyone with a veto has an unresolved concern.
If the founder overrides any of these, say the risk in one sentence, get the acknowledgment, record
it, and proceed.

---

## T-0 — The window

**Announce start.** "Launching X. Window 14:00–17:00. Watching: <names>. Rollback decision:
<name>. Status updates every 30 minutes in <channel>."

### Stage 0 — Internal (hold: 30 min)
Deploy behind a flag, enabled only for the team. Run the production smoke suite. Walk the critical
path manually, as a user, on production. **Look at the actual screens.**

### Stage 1 — Canary, 1–5% (hold: 60 min minimum)
Enable for a small slice of real traffic. Watch the thresholds. One hour minimum — many failures
need volume or time to appear, and a 10-minute canary proves only that the process started.

### Stage 2 — Ramp, 25% (hold: 60 min)
Watch for the failures that only appear at concurrency: lock contention, queue backlog, connection
pool exhaustion, cache stampede.

### Stage 3 — Majority, 50–75% (hold: 60 min)
Watch capacity and cost signals as well as errors.

### Stage 4 — Full (watch: continuous through T+72h)
Run the full production smoke suite once more. Announce completion.

**Rules for every stage:**
- Run the smoke suite after each stage. Not just at the end.
- **Hold the full time even when everything looks perfect.** The hold is where slow failures
  surface; skipping it because the graph is flat is skipping the entire point of staging.
- Never leave a stage unattended.
- One change at a time. If you deploy two things and metrics degrade, you have no idea which.
- If a threshold trips: **execute the pre-agreed action.** Do not renegotiate at 2am. Your calm
  self already made this decision and had better information than your tired self does.

### If you roll back
Rolling back is a **success of the process**, not a failure of the team. Say so plainly.

1. Execute the rehearsed rollback. Follow the runbook; do not improvise.
2. Confirm production is healthy against the baseline — do not assume the rollback worked, verify.
3. Notify users if they were affected, plainly and quickly.
4. **Preserve the evidence**: logs, metrics, the exact failing requests, DB state. Capture before
   anything is cleaned up or rotated away.
5. Root-cause before re-attempting. A second launch of the same code with "we think we fixed it" is
   how a bad day becomes a bad week.

---

## T+1h, T+6h, T+24h, T+48h, T+72h — The watch

At each checkpoint, record — not glance at, **record**:

| Check | What you are looking for |
|---|---|
| Error rate and new error *types* | A new error type at low volume matters more than a familiar one at high volume |
| p95 / p99 latency | p99 degrading while p95 is flat = a subset of users having a bad time |
| The business metric | The only signal that tells you whether the product still works for humans |
| Queue depth and job success rate | Backlogs grow quietly and then all at once |
| DB connections, slow queries, locks | The most common delayed failure after a deploy |
| Memory and disk trend | Leaks and log-volume surprises appear on day 2, not hour 1 |
| Support volume **and themes** | Themes matter more than count: three people confused the same way is a design bug |
| Your P5 predictions | You wrote down what you thought would break. Check each one specifically. |

**T+24h to T+48h is the dangerous window.** Hour one is watched by everyone. Day two is when the
edge-case users arrive, the first daily jobs run, the first invoices generate, caches expire, the
first token refreshes, and attention has moved on. Most real launch damage is discovered on day
two.

---

## P9 — Postmortem

Write it within 72 hours, while memory is accurate. **Blameless and specific** — those two words
together: blameless means no names attached to faults, specific means the mechanism is described
exactly. Vague postmortems are comfortable and useless.

```
POSTMORTEM — <what launched> — <date>

WHAT SHIPPED        one paragraph, in user terms
WHAT WE PREDICTED   the risks named in P0/P5 that actually happened  ← proof the process worked
WHAT SURPRISED US   what we did not see coming, and why we could not have
WHAT THE GATES CAUGHT  the defects stopped before users saw them, with the gate that caught each
                       ← this is the ROI section; without it the process looks like pure overhead
WHAT THE GATES MISSED  every defect that reached users, and which ring should have caught it
TIMELINE            what happened when, including the decisions and who made them
USER IMPACT         how many, how badly, for how long, and what we did about it
THE ONE CHANGE      exactly one process change, adopted now, written into the skill or project docs
```

**Why exactly one change.** A postmortem with fifteen action items produces zero adopted changes.
One change, actually made and written down, compounds across every future launch. Pick the one that
would have caught the worst thing that happened.

---

## Runbook template

Copy to the configured launch-state directory (default `.launch/RUNBOOK.md`). Every step
needs an expected output; a step whose success cannot be observed is not a step, it is a hope.

```markdown
# RUNBOOK — <release name> — <date>

## Facts
Version/commit:            <sha>
Rollback target:           <sha>
Rollback duration (measured): <mm:ss>     ← measured, not estimated
Migration duration (measured, prod scale): <mm:ss>
Max lock duration:         <mm:ss>
Executor:                  <name>     Watcher: <name>
Rollback decision maker:   <name>     User comms: <name>
Abort condition:           <the single sentence that stops everything>

## Pre-flight
[ ] PRELAUNCH.md says READY for this exact revision
[ ] G7 passed, evidence linked
[ ] Baseline metrics captured: err <x> | p95 <y>ms | <business metric> <z>/hr
[ ] Backup taken at <time>; restore tested at <time> on <machine>
[ ] Rollback rehearsed at <time>, duration <mm:ss>
[ ] All alerts fired and received at <time>
[ ] Crew confirmed available for the full window
[ ] No other deploys scheduled in this window

## Steps
1. <exact command>
   EXPECT: <exact output or observable state>
   IF NOT: <what to do — usually: stop and roll back>
2. …

## Smoke suite (run after every stage)
1. <command / manual check>   EXPECT: <…>

## Stages
Stage 0 internal    hold 30m   promote if: <…>
Stage 1 canary 5%   hold 60m   promote if: <…>
Stage 2 ramp 25%    hold 60m   promote if: <…>
Stage 3 50-75%      hold 60m   promote if: <…>
Stage 4 full        watch 72h

## Rollback
Trigger (any one): <numeric conditions>
1. <exact command>   EXPECT: <…>
2. Verify health against baseline: <how>
3. Notify: <who, what to say>
4. Preserve evidence: <logs, metrics, DB snapshot — before rotation>

## Watch schedule
T+1h  <name>   T+6h  <name>   T+24h <name>   T+48h <name>   T+72h <name>
```
