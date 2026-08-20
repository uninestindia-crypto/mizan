# G10 — Operability

> **Purpose.** When it breaks at 3am, a human is woken, and that human knows exactly what to do.
>
> **Veto holder.** SRE. **Entry.** G9 passed. **Exit.** 18 checks resolved.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**The question this gate answers.** Not "does it work" — G1 through G8 answered that. It is: *when
it stops working, how long until somebody knows, and what do they do?* The gap between "it broke"
and "somebody knew" is the entire cost of an outage. A four-minute failure that pages someone
immediately is an inconvenience. The same failure discovered by a customer email nine hours later
is a reputation event.

**G10.06 is the check that defines this gate.** An alert that has never fired is a hypothesis.

---

#### G10.01 · Structured logs with correlation IDs, no secrets — `S0` `cmd`

- **Run** — `LRK run G10.01 -- bash -c '<make a request>; <print the last 20 log lines>'`
- **Pass** — logs are structured (JSON or key=value, machine-parseable); every entry carries a request/trace ID that lets you follow one user's journey across services; every entry has a timestamp with a timezone and a level; no secret, token, password, or personal datum appears anywhere (cross-references G9.16).
- **The test that matters** — take one request ID from a user complaint and find every log line for that request in under a minute. If you cannot, your logs will not help you during an incident.

#### G10.02 · Log levels correct, ERROR actionable, volume estimated — `S1` `manual`

- **Pass** — `ERROR` means a human should look; `WARN` means something is degraded; `INFO` is the audit trail; `DEBUG` is off in production. Every `ERROR` includes enough context to act without reproducing.
- **Estimate the volume** — lines per day × bytes per line × your provider's per-GB price. Log ingestion is a top-three cloud cost surprise, and the bill arrives a month after the launch that caused it.
- **The anti-pattern** — logging an expected condition at `ERROR` (a user typing a wrong password). It trains everyone to ignore errors, so the real one is invisible.

#### G10.03 · Metrics: rate, errors, duration, with a dashboard — `S0` `manual`

- **Pass** — for every service: request rate, error rate, and duration (p50/p95/p99); plus saturation of the constrained resources (CPU, memory, connection pool, queue depth). A dashboard exists that a human can open **and find** during an incident.
- **Attach a screenshot of the dashboard.** A dashboard nobody can locate at 3am does not exist.
- **Also include the business metric** — signups per hour, orders per hour, messages sent. Technical metrics can all be green while the product is entirely broken; the business metric is the only one that notices.

#### G10.04 · SLOs defined as numbers — `S0` `manual`

- **Do** — write them. A defensible starting set: availability 99.9% monthly (≈43 minutes of downtime), critical-path p95 under the G6.01 budget, error rate under 0.1%.
- **State the error budget** — 99.9% means 43 minutes a month. That is the number that decides whether you can ship on Friday.
- **Record** — `LRK manual G10.04 --status pass --note "SLO: 99.9% monthly availability (43m budget); checkout p95 < 800ms; error rate < 0.1%. Owner: <name>."`

#### G10.05 · An alert for every SLO breach and every G7 failure mode — `S0` `manual`

- **Do** — take the failure list from G7 and confirm each one produces an alert. At minimum: error rate spike; latency above SLO; the service being down; database connection failures; queue depth growing; job failure rate; disk and memory approaching limits; certificate expiring in under 30 days; a third-party dependency failing; and a **business-metric flatline** (zero orders in an hour when you normally get twenty).
- **The business-metric flatline is the most valuable alert you will ever configure.** Every technical signal can be green while the product silently does nothing useful — a broken payment webhook, a misconfigured feature flag, a failed deploy that rolled back to a version with a broken form. Only the business metric catches these.

#### G10.06 · EVERY ALERT FIRED ON PURPOSE — `S0` `manual`

**The check this gate exists for. An untested alert has roughly a coin-flip chance of working.**

- **Do** — for each alert, deliberately create the condition, then confirm the notification arrives on the device of the person who is actually on call. Not "the alert rule exists". Not "the query returns rows". **Somebody's phone buzzed.**

| Alert | How to fire it deliberately |
|---|---|
| Error rate | Deploy a temporary endpoint that throws, hit it in a loop |
| Latency | Add a `sleep` behind a flag, generate load |
| Service down | Stop the service in staging |
| Database | Stop the database in staging |
| Queue depth | Enqueue 10,000 items with the consumer stopped |
| Disk / memory | `fallocate` a large file; run a memory hog |
| Certificate expiry | Point the check at a deliberately expired test certificate |
| Business flatline | Block the metric's source for the alert window |

- **Record one entry per alert**, with a screenshot of the received notification:
  ```bash
  LRK manual G10.06 --status pass --by "<name>" \
    --note "9 alerts fired deliberately 2026-08-14 14:00-15:40. 7 reached PagerDuty and the on-call phone. 2 FAILED: 'queue depth' had a stale integration key (fixed, re-tested, now arrives in 40s); 'cert expiry' was never wired to a channel (fixed). Median time from condition to phone: 74 seconds." \
    --attach alert-firing-log.md
  LRK attach G10.06 ./pagerduty-notification.png --caption "Alert received on the on-call phone, 14:07"
  ```
- **Pass** — every alert fired, every one arrived at a human, and you know the median delay in seconds.
- **What you will find** — at least one alert routed to a Slack channel nobody watches, one with an expired integration key, one whose threshold is so high it could never fire, and one that fires so often everyone has muted it. This is the normal result. Finding four broken alerts before launch is exactly what this check is for.

#### G10.07 · Alert quality — `S1` `manual`

- **Do** — for each alert, estimate how often it will fire per week in normal operation.
- **Pass** — the total is a number a human can sustain. More than a handful of pages a week and people stop reading them; at that point you have no alerting, only noise.
- **Every alert must be actionable.** If the response is "look at it and see", it is a dashboard, not an alert. Demote it.

#### G10.08 · On-call rota with named humans — `S0` `manual`

- **Pass** — a named person is on call for the launch window and afterwards; there is a documented escalation path if they do not respond in N minutes; a secondary exists; and everyone involved knows they are on the list. Time zones are covered, or the gap is explicitly accepted.
- **For a solo developer or a small team** — this is still required, and the honest version is short: *"I am on call. Alerts go to my phone, which is not on silent. If I do not respond in 30 minutes, <co-founder> restarts the service using the runbook."* Write it down.

#### G10.09 · A runbook per alert — `S0` `manual`

- **Pass** — every alert links to a runbook with: what this alert means, what the user impact is, the first three things to check (with the exact commands), the most likely causes, how to mitigate, how to escalate, and how to confirm it is resolved.
- **The test** — someone who did not build the system can execute it at 3am, half-awake, without asking anyone. Have that person read it and mark every step they could not perform.
- Template: `templates/runbook.md`.

#### G10.10 · Distributed tracing on the critical path — `S2` `hybrid`

- **Pass** — you can see where the time goes across service boundaries for a single request. Not strictly required for a monolith with good logging; increasingly essential the moment there are two services.

#### G10.11 · Error tracking wired and PROVEN — `S0` `manual`

- **Do** — deliberately throw an error in the deployed environment and confirm it appears in the error tracker with a usable stack trace, the release version, and the user context.
- **Run** — `LRK run G10.11 -- curl -s "$BASE/api/__test_error"` (a temporary endpoint, removed before launch), then screenshot the tracker.
- **Pass** — arrived, grouped correctly, and someone gets notified. Source maps uploaded so the stack trace is readable rather than minified gibberish (cross-references G1.15).
- **Also confirm** — unhandled promise rejections and uncaught exceptions are captured, not just errors you explicitly reported. Those are the ones you do not know about.

#### G10.12 · Kill switch for every risky feature, tested both ways — `S0` `hybrid`

- **Do** — for each risky new feature, turn the flag off in a production-like environment and confirm the system is healthy without it. Then turn it back on.
- **Pass** — both directions work, the change takes effect **without a deploy**, and you know how long it takes to propagate (seconds, or the length of a cache TTL?).
- **Test the flag flipping mid-flow** — a user halfway through a flagged feature when it is turned off must not be left in a broken state.
- **Why it is S0** — a kill switch is the difference between a two-minute mitigation and a full rollback under pressure. It is the cheapest insurance in this entire document.

#### G10.13 · Config change and revert without a deploy — `S1` `manual`

- **Pass** — the procedure is written, rehearsed once, and reversible. Somebody other than the author has done it.

#### G10.14 · Production access is least-privilege and audited — `S0` `manual`

- **Pass** — you can name every person who can deploy, every person who can read production customer data, and every person who can delete it. Access is logged. Nobody uses a shared account. There is a documented process for removing access when someone leaves.
- **Also** — production credentials differ from staging; no developer has standing write access to the production database (break-glass with an audit trail instead).

#### G10.15 · Support readiness — `S1` `manual`

- **Do** — write the five questions users will most likely ask in week one, with the answers. Confirm each answer is findable in the shipped documentation.
- **Pass** — support (even if support is you) can answer without reading the source code.
- Template: `templates/support-brief.md`.

#### G10.16 · Status page / comms channel ready — `S1` `manual`

- **Pass** — a place exists to tell users something is wrong, somebody knows how to post to it, and it is **not hosted on the same infrastructure as the product** — a status page that goes down with the product is worse than none.

#### G10.17 · Pre-launch baseline captured — `S0` `manual`

- **Do** — immediately before launch, record the current numbers: error rate, p50/p95/p99 latency, request rate, the key business metric, CPU, memory, and database connections.
- **Pass** — the numbers are written down with a timestamp.
- **Why it is S0** — during the launch you must answer "is this normal?" within seconds. Without a baseline, every number is meaningless and every decision is a guess. G12 compares against this and cannot run without it.

#### G10.18 · Cost and billing alarms — `S1` `manual`

- **Pass** — a billing alert exists at a threshold somebody chose deliberately (based on G6.12), and it goes to a human who can act. Also set a per-service alarm on whatever scales with traffic — egress, log ingestion, per-call APIs.

---

## Exit bar for G10

```bash
LRK status --gate G10
```

Three questions:

1. **How many seconds from "it breaks" to "a phone buzzes"?** You measured this in G10.06. If you cannot say a number, this gate is not passed.
2. **Can someone who did not build this fix a common failure using only the runbook?** (G10.09)
3. **Could you turn the riskiest new feature off in the next sixty seconds?** (G10.12)
