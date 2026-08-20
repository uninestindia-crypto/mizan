# G11 — Release Mechanics

> **Purpose.** The deploy is rehearsed, the rollback is timed, and a stranger could execute both.
>
> **Veto holder.** Release manager. **Entry.** G10 passed. **Exit.** 16 checks resolved.
> **This is the strictest gate. Any single S0 failure here stops the launch.**

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**The three checks teams mark as done without doing** — G11.07 (rollback rehearsed and timed),
G11.11 (environment contract verified in the target), and G11.12 (a rehearsed production smoke
suite). They are also, reliably, the three that determine whether a bad launch is an inconvenience
or a catastrophe.

---

#### G11.01 · Version assigned, artifact tagged, build reproducible from the tag — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G11.01 -- git tag -a v1.0.0 -m "Release 1.0.0" && git describe --tags --exact-match
  LRK run G11.01 --title "build from a clean checkout of the tag" -- bash -c 'rm -rf /tmp/rc && git clone --branch v1.0.0 . /tmp/rc && cd /tmp/rc && <install> && <build>'
  ```
- **Pass** — the version is in the artifact (a `/version` endpoint, an `--version` flag, or a build-info file), the tag is immutable, and a clean checkout of the tag builds successfully.
- **Why the version must be queryable at runtime** — during an incident, the very first question is "which version is actually running?" If you cannot answer it in ten seconds you will spend the first twenty minutes of the outage finding out.

#### G11.02 · Release notes in the user's language — `S1` `manual`

- **Pass** — written in terms of what users can now do, what changed for them, and what to watch out for. Not a list of commit messages.
- **Compare**: *"refactor auth middleware, bump deps"* → *"You can now stay signed in for 30 days. If you use a shared computer, sign out when you finish."*
- **Include** — anything breaking, anything requiring user action, and known limitations. Users forgive a stated limitation and never forgive a surprise.

#### G11.03 · Feature freeze in effect — `S0` `manual`

- **Do** — declare the freeze and record the commit SHA it started at. From that point, only blocker fixes go in.
- **The rule that makes a freeze real** — **every post-freeze change restarts verification of the gates it touches.** A "one-line fix" to the payment handler at hour twenty means G3, G4, and G5 run again for that path. This is not bureaucracy: post-freeze changes are made under time pressure by a tired person, and they are statistically the most dangerous code in the release.
- **Record** — `LRK manual G11.03 --status pass --note "Freeze at 3f9a2c1, 2026-08-14 09:00. Two blocker fixes admitted since (a1b2c3d, e4f5g6h); G4 re-run for both, evidence recorded."`

#### G11.04 · Deploy runbook: numbered, with expected output and an abort condition — `S0` `manual`

- **Pass** — the runbook has, for every step: the exact command, the expected output, how long it should take, and what to do if it looks wrong. It states the abort condition up front — the specific observation that means "stop and roll back" — decided **now**, while nobody is under pressure.
- **It must include** — pre-flight checks, the backup step, the migration step, the deploy step, the smoke test, the promotion criteria, and the rollback procedure.
- Template: `templates/runbook.md`.

#### G11.05 · Runbook executed or cold-read by someone who did not write it — `S0` `manual`

- **Do** — hand it to a different person (or a fresh agent session with no context). Ask them to execute it, or at minimum read it aloud and mark every step they could not perform without asking a question.
- **Pass** — zero unanswerable steps. Every question they asked becomes a line in the runbook.
- **Why** — the author cannot see their own assumed knowledge. "Deploy the service" is complete to the person who wrote it and useless to everyone else. This check exists because the author is frequently the person who is unreachable during the incident.

#### G11.06 · Deployed to a production-LIKE environment and exercised there — `S0` `cmd`

- **Pass** — deployed somewhere that resembles production in configuration, data shape, TLS, DNS, and dependencies, and every critical path from G0.09 was exercised **there**, not locally.
- **"It works locally" is a category error.** Locally means warm caches, seeded data, one user, no network latency, permissive CORS, self-signed certificates accepted, debug mode on, and every environment variable set from a file you forgot exists.
- **If there is no staging environment** — record the failure honestly. Then, at minimum, deploy to a temporary production-configured environment for this verification and tear it down. The cost of that is hours. The cost of not doing it is the launch.

#### G11.07 · ROLLBACK REHEARSED and TIMED — `S0` `cmd`

**Execute it. On the production-like environment. With a stopwatch.**

- **Run** —
  ```bash
  LRK run G11.07 --title "deploy the RC"          -- <deploy command>
  LRK run G11.07 --title "ROLLBACK executed, timed" -- bash -c 'time <rollback command>'
  LRK run G11.07 --title "smoke after rollback"    -- <smoke command>
  ```
- **Pass** — the rollback completes, the previous version serves traffic correctly, data is intact, and **you have the number in seconds**.
- **Answer all six before leaving this check**:
  1. How many seconds did it take?
  2. Who can execute it? (More than one person, or that person is a single point of failure.)
  3. Does it require the CI system to be up? (If CI is the thing that is broken, can you still roll back?)
  4. What happens to data written by the new version between deploy and rollback?
  5. Is it still valid after the database migration has run? (Often not — this is the crux.)
  6. Does anything need to be done manually, and is it in the runbook?
- **An untested rollback is not a rollback.** It is a paragraph in a document, and it fails at exactly the moment you need it, because that is the first time anyone has run it.

#### G11.08 · Data rollback possible, or explicitly declared impossible — `S0` `manual`

- **Do** — state clearly: can you undo the *data* changes, or only the code?
- **Pass** — either a tested data rollback (cross-references G5.02), or a written statement: *"The migration is forward-only. If we roll back the code, orders created after 14:00 will be invisible to v1.0.9. The compensating control is the feature flag, which stops new orders using the new path within 30 seconds, plus the verified backup taken at 13:55."*
- **The scenario this prevents** — code rolled back successfully, and the old code cannot read data the new code wrote. The rollback "worked" and the product is broken in a new way.

#### G11.09 · Staged rollout with NUMERIC thresholds — `S0` `manual`

- **Pass** — the plan states, in numbers: the percentage at each stage, how long each stage is held, the metrics watched, the promotion threshold, and the automatic rollback trigger.
- **A defensible default**:

| Stage | Traffic | Hold | Promote if | Roll back if |
|---|---|---|---|---|
| 1 | Internal only | 30 min | Smoke passes, 0 new errors | Any new error type |
| 2 | 1% | 1 h | Error rate ≤ baseline+0.1%, p95 ≤ baseline+10% | Error rate > baseline+0.5%, or p95 > baseline+25% |
| 3 | 10% | 2 h | Same, plus business metric within 5% of baseline | Same, or business metric down >10% |
| 4 | 50% | 2 h | Same | Same |
| 5 | 100% | — | — | Same, for 72 h |

- **"We'll watch the dashboards and see how it looks" is not a plan.** Under launch pressure, with everyone hoping, an ambiguous signal always gets interpreted as fine. Decide the numbers now, while nobody is invested.

#### G11.10 · Kill switch tested — `S0` `hybrid`

- Cross-references G10.12. Confirm here that it works **in the production-like environment with production configuration**, and that you know the propagation delay in seconds.

#### G11.11 · Environment contract verified IN THE TARGET — `S0` `cmd`

- **Do** — not "we set the variables". Verify, **in the target environment**, that each one is present and correct.
- **Run** — `LRK run G11.11 -- <remote command listing the env keys, values redacted>`, plus a startup self-check endpoint that validates config and reports which items are missing.
- **The full list**: every environment variable; every secret (present **and** current — a rotated secret that was not updated everywhere is a classic); database connection string pointing at the right database; third-party keys in **live** mode, not test; DNS records resolving; TLS certificate valid and not expiring inside the launch window; CDN configured; storage bucket exists with the right permissions; queue exists; cron jobs scheduled; IAM permissions sufficient; quotas raised where G6.13 said they were needed; outbound email domain verified with SPF, DKIM, and DMARC.
- **The email one bites constantly** — a new sending domain without SPF/DKIM sends every verification email straight to spam. Nobody can sign up, and nobody reports it because they never got in.

#### G11.12 · Production smoke suite, under five minutes, rehearsed — `S0` `cmd`

- **Pass** — a script exists that exercises every critical path against a live environment, runs in under five minutes, is safe to run against production (uses a dedicated test account, cleans up after itself, moves no real money), and has been run at least once on the production-like environment.
- **Run** — `LRK run G11.12 -- <smoke command> --env=staging`
- **Why under five minutes** — you will run this after every rollout stage. A twenty-minute smoke test gets skipped at stage 3 by a tired person who is fairly sure it is fine.

#### G11.13 · Go/No-Go held, named humans said GO — `S0` `manual`

- **Do** — hold it, even if the team is one person. Walk the report. State the open risks out loud. Get an explicit yes.
- **Pass** — recorded: who, when, what they were told, what they accepted.
  ```bash
  LRK manual G11.13 --status pass --by "R. Patel (CTO)" \
    --note "Go/No-Go 2026-08-14 16:00. Attendees: R. Patel (eng), S. Nair (support), A. Kumar (SRE). Report reviewed: 0 blockers, 4 S1 warnings, 2 waivers (G6.12 cost model, G8.15 print view). Decision: GO for staged rollout starting 2026-08-15 10:00 IST. Abort authority: A. Kumar."
  ```
- **The value is the ritual.** Saying "we are launching, and here is what we know is imperfect" out loud, to other people, surfaces the objection somebody has been privately holding for a week.

#### G11.14 · Launch window chosen deliberately — `S1` `manual`

- **Pass** — not Friday afternoon; not the evening before a holiday; not during a dependency's scheduled maintenance; not while the person who knows the system is on a plane. Early in the day, early in the week, with the whole team available and awake for the following eight hours.
- **Check your dependencies' status pages and maintenance calendars** before committing to the window.

#### G11.15 · Communications ready and scheduled — `S1` `manual`

- **Pass** — drafted and ready to send: the user announcement, the support brief (G10.15), the stakeholder note, and — written **in advance** — the "we are investigating an issue" message. Writing that one calmly, today, is worth an hour of your future self's panic.

#### G11.16 · Migration guide for existing users or integrators — `S0` `manual`

Applies whenever anything breaks for someone already using the product.

- **Pass** — the guide states what changed, exactly what they must do, by when, and what happens if they do nothing. Old behaviour is supported for a stated deprecation window, not removed on the day.
- **For an API** — version it, support the old version for a defined period, and warn in the response headers before removal. Breaking integrators without notice is how a product loses the customers most invested in it.

---

## Exit bar for G11

```bash
LRK status --gate G11
LRK report && LRK certify
```

Every S0 in this gate `pass` with EXECUTED or ATTACHED proof. Before you continue to G12, state
these three out loud:

1. **The rollback takes ___ seconds** and I have run it myself.
2. **The abort condition is ___** — the specific number that means stop.
3. **___ and ___ can both execute the runbook** without calling anyone.

If any of those three has a blank in it, you are not ready, regardless of what the checklist says.
