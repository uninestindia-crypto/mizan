# G12 — Launch & 72-Hour Watch

> **Purpose.** The rollout was staged, watched, measured, and learned from.
>
> **Veto holder.** Release manager. **Entry.** G11 passed, certificate says GO.
> **Exit.** 12 checks resolved, 72 hours after 100% rollout.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**Launch is a phase, not a moment.** "We deployed and it looked fine" is not a launch; it is a coin
flip you have not finished flipping. This gate runs for three days, and the last check in it is
what makes the next launch better than this one.

**Before the first command:** open the runbook (G11.04) and the baseline (G10.17) side by side, and
put the rollback command in a terminal you are not going to close.

---

#### G12.01 · Baseline captured immediately before the first stage — `S0` `manual`

- **Do** — in the ten minutes before you start, record the numbers as they are right now: error rate, p50/p95/p99, request rate, the key business metric, CPU, memory, database connections, queue depth.
- **Record** — `LRK manual G12.01 --status pass --note "Baseline 2026-08-15 09:52 IST: err 0.02%, p95 240ms, p99 610ms, 42 rpm, 3 orders/hr, CPU 18%, mem 340MB, db conns 6/20, queue 0." --attach baseline-dashboard.png`
- **Not last week's numbers.** Ten minutes before. Traffic patterns move, and "is this normal?" is a question about *now*.

#### G12.02 · Canary deployed, smoke passed, held for the planned duration — `S0` `manual`

- **Do** — deploy to the first stage from the plan in G11.09. Run the production smoke suite (G11.12) against it. Then **wait the full planned time**.
- **Pass** — smoke green, and the stage was held for its planned duration.
- **The most common launch failure is impatience.** The canary looked fine for four minutes so it was promoted to 100%, and the problem that only appears under real concurrency, or after a cache expires, or when the hourly cron runs, arrives at full traffic. Set a timer. Do not promote early. There is no prize for finishing the rollout quickly.

#### G12.03 · Metrics compared to baseline at every stage — `S0` `manual`

- **Do** — at each stage, write down the same numbers as G12.01 and compare them.
- **Record one entry per stage:**
  ```bash
  LRK manual G12.03 --status pass --note "Stage 2 (10%), 11:20: err 0.04% (baseline 0.02%, +0.02 — within +0.1 threshold), p95 268ms (baseline 240ms, +12% — within +25%), orders 4/hr (baseline 3/hr). PROMOTE." --attach stage2-metrics.png
  ```
- **Compare against the thresholds you wrote in G11.09, not against your feelings.** The whole reason those numbers were written in advance is that judgement under launch pressure is systematically optimistic.

#### G12.04 · Every promotion decision recorded with its numbers — `S0` `manual`

- **Pass** — for each promotion: the time, the numbers, the threshold they were compared against, and who decided.
- **Why** — if something surfaces at hour six, this log is how you find which stage introduced it. Without it you are guessing across four deploys.

#### G12.05 · Rollback still available and valid at every stage — `S0` `manual`

- **Do** — at each stage, confirm out loud: the previous version is still deployable, the rollback command still works, and the data written since the deploy does not prevent it.
- **Pass** — confirmed at each stage.
- **The thing that invalidates a rollback mid-launch** — a migration that ran at stage 3, or enough new-format data that the old version can no longer read the table. The moment rollback stops being possible, you have crossed a one-way door. Know when you cross it, and say so.

#### G12.06 · Full production smoke passed at 100% — `S0` `cmd`

- **Run** — `LRK run G12.06 -- <smoke command> --env=production`
- **Pass** — every critical path green against real production at full rollout.
- **Then do it by hand as well.** Open the product as a real user, on your phone, on the real domain, and buy something. Automated smoke tests check what you thought to check; your eyes catch the layout that broke because the production CDN serves a stale stylesheet.

#### G12.07 · Structured watch at T+1h / 6h / 24h / 48h / 72h — `S0` `manual`

- **Do** — at each checkpoint, record the same set of numbers plus anything new. Do it even when everything is fine; that is what makes "fine" mean something.

| Checkpoint | Pay particular attention to |
|---|---|
| **T+1h** | Error spikes, latency, the first real user reports |
| **T+6h** | Memory growth, connection leaks, queue depth, the first scheduled jobs |
| **T+24h** | A full daily cycle: peak traffic, nightly jobs, backups, log volume, **the first day's bill** |
| **T+48h** | Slow leaks, retention behaviour, support themes emerging |
| **T+72h** | Weekly jobs, the full picture, the success metric |

- **Record one entry per checkpoint.** Five entries. A single entry saying "watched for 72 hours, all good" is not a watch; it is a claim about one.
- **T+24h is where the surprises live**: the nightly batch job that has never run against this schema, the backup that now takes four hours, the log bill, and the cache that fills up exactly once a day.

#### G12.08 · Every incident triaged — `S0` `manual`

- **For each** — severity, what users experienced, when it started, when it was detected (**and by whom — a monitor, or a customer?**), when it was mitigated, when it was resolved, and the root cause.
- **The single most informative number in this gate**: *how did we find out?* If a customer told you before your monitoring did, G10.05 has a gap, and that gap is the most valuable finding of the entire launch.

#### G12.09 · Support themes reviewed at T+24h and T+72h — `S1` `manual`

- **Do** — read the actual support messages, reviews, and social mentions. Group them. Count them.
- **Pass** — the top three themes are written down with counts, and each has a disposition: fix now, fix next release, or document.
- **Confusion is a defect.** Ten people asking the same question is not ten users being slow; it is one design problem with ten reports. This is the cheapest, highest-quality user research you will ever get, and it is available for exactly one week.

#### G12.10 · Success metric measured against target — `S1` `manual`

- **Pass** — the metric defined before launch, measured now, compared to the target, with the gap explained.
- **Measure it even when it is bad.** Especially when it is bad. A launch that shipped cleanly and achieved nothing is a specific, addressable outcome, and it is invisible if nobody looks.

#### G12.11 · Postmortem written — `S1` `manual`

- **Do** — write it within a week, while it is still accurate. Four sections:
  1. **What we predicted correctly** — which risks were real, which gates earned their cost.
  2. **What surprised us** — everything that was not on the list.
  3. **Which gate caught it** — for each real problem found before launch, name the check. This is how you learn which parts of the process are paying for themselves.
  4. **Which gate should have caught it** — for each problem found *after* launch, name the check that missed it, and why. This is the most valuable section in the document.
- **Blameless.** The output is a process change, never a person's name. A postmortem that assigns fault teaches everyone to report less next time, which is precisely the opposite of the goal.
- Template: `templates/postmortem.md`.

#### G12.12 · Exactly ONE process improvement written back — `S2` `manual`

- **Do** — pick the single highest-value change and make it. Edit this skill's catalogue or gate files, or the project's own docs. Then stop.
- **Deliberately limited to one.** A postmortem that generates fifteen action items generates zero — everyone agrees, nobody owns them, and the next postmortem produces fifteen more. One change, actually made, compounds across every future launch.
- **Where to put it**:
  - A missing check → add it to `scripts/catalog.py` and its gate file.
  - A check that was ambiguous → rewrite that check's wording.
  - A stack-specific command that was wrong → fix `stack-playbooks.md`.
- **Record** — `LRK manual G12.12 --status pass --note "Added G7.16: verify the nightly batch job runs against the new schema before rollout. Missed because G5.04 only covers the API's old code, not scheduled jobs. Written into gate-G7.md and catalog.py."`

---

## During the launch: the abort decision

You wrote the abort condition in G11.04 and the numeric triggers in G11.09. Honour them.

**Roll back immediately, without discussion, when:**
- Any threshold from G11.09 is crossed
- Any data-corruption or data-loss signal appears — **no threshold, no discussion, no waiting**
- Any security issue appears
- You do not understand what you are seeing

**That last one is the important one.** "I don't know why that number moved" is a complete and
sufficient reason to roll back. The rollback is cheap — you timed it in G11.07 and it takes
seconds. Understanding an anomaly at full production traffic is expensive. Roll back, understand it
calmly, and try again tomorrow.

**Nobody has ever regretted rolling back too early.** The regret is always in the other direction,
and it is always described afterwards as "we thought it would recover on its own."

---

## Exit bar for G12

```bash
LRK status --gate G12
LRK report && LRK certify && LRK bundle
```

Seventy-two hours after 100% rollout, with five watch entries recorded, every incident triaged, the
postmortem written, and exactly one improvement made.

Then run `bundle` one final time. That zip — the complete evidence trail from G0 through G12 —
is the artifact. Keep it. It is what you hand to the customer who asks how you test, to the auditor
who asks for evidence of change control, and to yourself in six months when you cannot remember
whether you ever checked something.
