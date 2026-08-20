# 02 — The Phase Pipeline

The chronological order. Ten phases, ten gates. Every phase has an **entry condition** (what must
be true to start), a **work list** (what actually happens), an **exit artifact** (what it produces),
and a **gate** (what must be proven to leave). Gate checklists are in `03-gates.md`.

**The two pipeline rules:**
- Account for every phase: execute it, compress it, or mark it not applicable as the tier playbook
  permits. Never omit one silently.
- You may not enter a phase whose predecessor gate has not passed with evidence.

Announce your position in every message during founder-mode work:
`[P4 · slice 3/7 · G4 pending]`

## Contents

- [P0–P3: charter, definition, architecture, slicing](#p0--charter)
- [P4–P6: build, harden, taste](#p4--build-the-loop)
- [P7–P9: release, launch, watch](#p7--release-candidate)
- [Parallelism map](#parallelism-map-crew-mode-only)

---

## P0 — Charter

**Entry.** The founder has expressed an intent, however vaguely.

**Purpose.** Prevent the most expensive failure in software: building the right thing badly, or the
wrong thing beautifully. This phase costs minutes and saves weeks.

**Work.**
1. **Restate the intent in one sentence**, in your own words, and get it confirmed. If your
   restatement surprises the founder, you just saved the project.
2. **Name the user.** Not "users." A specific role in a specific situation with a specific problem.
   If there are several, name them separately and rank them — the primary user wins every trade.
3. **Define "no problems for users."** This is the phrase the founder actually cares about, and it
   is meaningless until it is operationalized. Write down the concrete version:
   - What must *never* happen? (data loss, wrong money, exposed data, silent failure)
   - What must *always* work, even degraded? (the critical path)
   - What is acceptable to be imperfect at launch? (this is a real question — answer it)
4. **Declare the tier** (T0–T4, see `10-scaling.md`). Everything downstream is sized by this.
5. **Kill criteria.** Under what conditions do we stop or postpone? Write them now, while nobody is
   emotionally invested. "If the payment provider's sandbox can't do partial refunds, we cut
   refunds from v1 and ship without them" is worth more in week one than any amount of week-nine
   heroics.
6. **The first ten minutes.** Narrate, as prose, what a stranger experiences from arrival to first
   value. This narration is the real spec (Law 1) and every later decision is judged against it.

**Exit artifact.** `.launch/CHARTER.md` — one page, no more.

**Gate G0.** The founder agrees with the restatement, the named user, the definition of "no
problems," and the tier.

**Time.** T0: skip (state the tier and move). T1: 2 minutes. T2: 15 minutes. T3–T4: a real
conversation, plus reading whatever product docs exist in the repo.

---

## P1 — Define

**Entry.** G0 passed.

**Lead.** Head of Product (`spec-writer`).

**Purpose.** Make "done" a thing that can be checked instead of felt.

**Work.**
1. **User stories** for the primary user, in their language.
2. **Acceptance criteria**, each in Given/When/Then form, each mechanically verifiable. Adjectives
   are converted to numbers or deleted: "fast" → "p95 under 400ms on the seeded dataset";
   "intuitive" → "Customer Zero completes it without assistance in under 90 seconds."
3. **The non-goals list.** Explicit. Non-empty. This is the cut line (Law 2), and it is as much a
   deliverable as the feature.
4. **Failure states enumerated per story** — empty, error, offline, unauthorized, slow, partial,
   too-much-data, concurrent. Each gets a specified behavior *now*, because "we'll handle errors
   later" means "the user will handle errors later" (Law 6).
5. **Success metric.** One number, measurable after launch, that tells us this worked.
6. **Ambiguity log.** Every place the request was unclear, the assumption made, and who should
   confirm it. Unlogged assumptions become launch-day surprises.

**Exit artifact.** `.launch/PRD.md`.

**Gate G1.** Every acceptance criterion is verifiable; non-goals are written; every story has its
failure states; ambiguities are logged and the blocking ones are resolved.

**Common failure here.** Writing criteria that describe the *implementation* ("the API returns a
201") instead of the *outcome* ("the supplier receives the RFQ and can see it in their inbox").
Implementation criteria pass while the product is broken.

---

## P2 — Architect

**Entry.** G1 passed.

**Lead.** Principal Architect (`architect`).

**Purpose.** Decide the shape once, in writing, so it is not re-decided badly under time pressure
in week six.

**Work.**
1. **Read the existing code before designing.** Every design that ignores what is already there
   generates an integration surprise. Find the existing patterns and follow them, or state
   explicitly why you are departing.
2. **ADR per significant decision** — context, options, decision, consequences, reversal
   conditions. "Significant" means: hard to reverse, affects more than one module, introduces a
   dependency, or touches data.
3. **Interface contracts.** Exact shapes for every boundary crossed: request/response, schema
   delta, event payloads, error taxonomy, module exports. The contract is what makes parallel work
   and independent testing possible; without it, everything must be integrated to be tested.
4. **Data model + migration plan** — forward migration, backward rollback, and how the rollback
   will be *rehearsed* (not "written").
5. **Failure architecture.** What happens when each dependency is down, slow, or lying? Timeouts,
   retries, idempotency keys, circuit breaking, degraded modes. Decide this here, not in an
   incident.
6. **Observability plan.** What we will log, what we will count, and what will page a human. Design
   this with the feature; instrumenting after launch means launching blind.
7. **The security and permission model** for the change: who can do what, to whose data, and what
   the test for that will be.

**Exit artifact.** `.launch/ARCHITECTURE.md` + ADRs.

**Gate G2.** Contracts are exact; the migration has a rehearsable rollback; failure behavior is
specified for every dependency; observability and permissions are designed, not deferred.

---

## P3 — Slice

**Entry.** G2 passed.

**Lead.** Architect + you.

**Purpose.** Convert the design into an ordered sequence of *vertical* slices where the scariest
work happens first.

**Work.**
1. **Cut vertically.** Each slice goes all the way through the stack and ends in something a human
   can see, run, or call. Never "all the models" then "all the endpoints" — horizontal layers hide
   risk until integration, which is exactly the wrong time to find it.
2. **Order by risk, not by ease** (Law 3). Rank every slice by: *if this turns out to be harder
   than we think, how much of the plan dies?* Highest first. The uncomfortable slice is slice 1.
   Common highest-risk candidates: third-party integrations nobody has actually called, migrations
   on real data volumes, anything involving money or time zones, anything requiring a real device,
   and anything where the requirement is still fuzzy.
3. **Size each slice to be finishable in one working session** including its tests. A slice too
   large to finish will be reported as "in progress" for days, which is how a project loses a week
   without anyone noticing.
4. **Define each slice's demo.** One sentence: what you will show when it is done. A slice with no
   demonstrable outcome is a horizontal layer wearing a disguise.
5. **Assign each slice its required test rings** from `04-test-matrix.md`, based on its part types.
   Do this now, at planning time, not at gate time — it changes the size estimate.
6. **Mark the dependencies** between slices, and note which slices could run in parallel if the
   founder wants crew mode.

**Exit artifact.** `.launch/SLICES.md` — a table: #, name, demo, part types, required rings,
dependencies, status.

**Gate G3.** Every slice is vertical and demonstrable; slice 1 is genuinely the riskiest; every
slice has its rings assigned; nothing in the plan is larger than one session.

---

## P4 — Build (the loop)

**Entry.** G3 passed.

**Lead.** You, as Staff Engineer. Red Team enters at step 6 of every slice.

**This phase is 40% of the effort and it is a loop, not a block.** Per slice:

```
1. RESTATE      the slice's acceptance criteria and its contract, in one line.
2. RED          write the test that fails for the right reason. Watch it fail.
3. GREEN        build the happy path until it passes. No more than that.
4. WHOLE        build every failure state from the PRD, in this same slice.  (Law 6)
5. STATIC       run R0. Zero findings. Not "only warnings."
6. BREAK        Red Team hat / `red-team` agent. Work the attack families.   (Law 5, pass 2)
7. REPAIR       fix every Blocker and Major. Add a regression test for each.
8. CLEAN        re-verify from a clean state: fresh deps, fresh DB, migrations
                from zero, full command, raw output.                          (Law 5, pass 3)
9. RECORD       update STATE.md and SLICES.md. Write the slice report.
                ── only now may slice N+1 begin ──
```

**Non-negotiables in this phase:**
- **No parallel half-slices.** Finishing beats starting. Two slices at 80% is worth zero.
- **No TODOs in a completed slice.** Either finish it, or it goes in the report's `NOT DONE`
  section where the founder can see it.
- **Every bug found gets a test before it gets a fix.** A fix without a test is a bug on a timer.
- **When a slice reveals the plan was wrong** — and one will — stop, say so, and return to P2 or P3
  for that piece. Discovering the design is wrong is a *success* of the risk-first ordering, not a
  failure. Grinding forward on a design you no longer believe in is the failure.

**Gate G4 (per slice, and again at the end of the phase).** All required rings pass with raw
evidence from a clean state; failure states exist; no Blocker or Major open; the demo works.

---

## P5 — Harden

**Entry.** All slices through G4.

**Lead.** Red Team, then Code Review.

**Purpose.** Slices were tested in isolation. Systems fail *between* the parts. This phase attacks
the assembled whole.

**Work.**
1. **Full-system adversarial pass (R5).** All twelve attack families from `05-hardening.md`, run
   against the integrated product, with emphasis on the seams between slices — the places where
   slice 3 assumed something slice 5 does not guarantee.
2. **Concurrency and ordering.** Two users, same resource, same millisecond. Requests arriving out
   of order. Retries arriving after the original succeeded. Anything with a queue, a job, or money
   gets this treatment specifically.
3. **Failure injection (R5).** Kill the database mid-transaction. Make the third-party time out.
   Return a 500, then a 429, then malformed JSON. Fill the disk. Expire the token mid-session.
   Take the network away in the middle of an upload. For each: does it fail *safely, visibly, and
   recoverably*? Silent failure is the worst outcome; louder is better than lossier.
4. **Non-functional (R6).** Performance against the budget with realistic data volume; load and
   soak; accessibility; bundle/memory; internationalization and time zones; dependency and secret
   scanning.
5. **Code Review (role 8).** Run the project's strongest available code and security review
   capabilities, not a skim. Do not assume a particular slash command exists.
6. **The migration rehearsal.** Run the migration on a production-scale copy. Time it. Then run the
   rollback. Time that too. Both numbers go in the runbook.
7. **Fix, then re-run.** A hardening pass that ends with "found 14 issues" and no re-run has proven
   nothing about the fixes.

**Gate G5.** Zero Blockers. Every Major has a fix with a regression test, or a founder-signed
written acceptance. Perf and a11y budgets met with numbers. Migration and rollback both rehearsed
and timed. Review findings resolved.

---

## P6 — Taste & Cut

**Entry.** G5 passed.

**Lead.** `taste-critic`, then `customer-zero`.

**Purpose.** The Jobs pass. Everything works; now decide whether it is *good*. This is the phase
that separates a product from a feature dump, and it is the phase most teams skip.

**Work.**
1. **Run the product as a product**, not as a test suite. Look at it. Use it. On a real device,
   on a real network, with real-looking data.
2. **The taste review.** If the project has a design law skill, load it and apply it as the
   standard. Judge: hierarchy, density, motion, copy, the empty states, the error messages, the
   moment of first value.
3. **Produce the remove list.** This is the point of the phase. What ships that should not?
   Candidates: options that should be defaults, three screens that should be one, a setting nobody
   will ever change, a feature that is 60% good and drags the whole product's average down, every
   word that is not doing work. **A P6 with an empty remove list did not happen.**
4. **Customer Zero.** Fresh eyes, no knowledge of the rehearsed path, real beginning (empty
   account, no fixtures), doing the wrong things on purpose. Their hesitations are the findings.
5. **The founder demo.** Show it. Get the verdict. Expect "this part isn't good enough" and treat
   that as the system working, not as a setback.
6. **Cut or fix.** Every item on the remove list is removed or explicitly kept by the founder.
   Every friction item from Customer Zero is fixed, cut, or documented as a known limitation for
   the Scribe.

**Gate G6.** Remove list executed. Customer Zero can complete the primary job unaided. Taste
standard met (or the project's design skill's checklist passes). Founder has seen it and said yes.

---

## P7 — Release Candidate

**Entry.** G6 passed.

**Lead.** `launch-engineer` + `scribe`.

**Purpose.** Freeze, prove, prepare. Nothing new gets built in this phase — that is what makes it a
candidate.

**Work.**
1. **Freeze.** Feature work stops. Only Blocker fixes are allowed in, and each one restarts the
   verification (a fix at RC is a change, and changes are not trusted until proven).
2. **Full clean-state verification (`verifier`, mandatory).** From zero: fresh clone, fresh
   install, migrations from empty, seed, full test suite, build, start. Raw output for every step.
3. **Deploy to a production-like environment** and run the entire critical path there. "Works
   locally" is not evidence of anything (see `09-antipatterns.md`).
4. **The runbook** — numbered, exact commands, expected output per step, abort condition,
   executable by someone who did not build this.
5. **Rehearse the rollback.** Execute it. Against realistic data. Time it. If it has not been run,
   it does not exist.
6. **Fire every monitor and alert on purpose** and confirm each reaches a human. A configured alert
   is not a working alert.
7. **Docs, release notes, support brief, migration guide** (`scribe`).
8. **The staged rollout plan** with numeric promotion and rollback thresholds.
9. **Environment contract check**: every required env var, secret, and permission documented and
   present in the target environment.

**Gate G7.** Clean-state verification PASSED with raw output. Deployed and exercised in a
production-like environment. Rollback rehearsed and timed. Monitors fired and received. Runbook
executable by a stranger. Docs and support brief complete. Rollout thresholds are numbers.

---

## P8 — Launch

**Entry.** G7 passed. Detailed hour-by-hour runbook in `06-launch-runbook.md`.

**Lead.** `launch-engineer`.

**Work.**
1. **Announce the window.** Who is watching, for how long, and how to reach them.
2. **Deploy in stages**, never all at once when a stage is possible: internal → canary % → ramp →
   full. Each stage holds long enough for the metrics to be meaningful, not just non-zero.
3. **Run the production smoke suite** after each stage — against production, with real
   credentials, on the real critical path.
4. **Watch the numbers, not the dashboard's color.** Error rate, latency p95/p99, the business
   metric (signups, orders, whatever the product's heartbeat is), and the specific new-code
   metrics. Compare to the pre-launch baseline you captured — if you did not capture a baseline,
   you cannot tell "elevated" from "normal."
5. **Promote or roll back on the pre-agreed thresholds.** The decision was made in P7 by people who
   were calm. Honor it. Do not renegotiate a rollback threshold at 2am while looking at a graph.
6. **Never leave a stage unattended.**

**Gate G8.** Production smoke passes at full rollout. Metrics within thresholds. No open Blocker.
Rollback still available and still rehearsed.

---

## P9 — Watch & Learn

**Entry.** G8 passed. Launch is not over.

**Work.**
1. **72-hour watch.** Structured checks at T+1h, T+6h, T+24h, T+48h, T+72h — errors, latency, the
   business metric, support volume and themes, and the specific failure modes you predicted in P5.
   Most launch damage surfaces in the *second* day, when the first real batch of edge-case users
   arrives.
2. **Triage in public.** Every incident gets severity, owner, and an ETA that is real.
3. **The postmortem, blameless and specific.** What we predicted correctly, what surprised us, what
   the gates caught (proof the process paid for itself), what they missed, and the *one process
   change* that would have caught the miss. One change — a postmortem generating fifteen action
   items generates zero.
4. **Feed it back.** Update the charter, the test matrix, and the hardening catalog with what this
   launch taught. A process that does not learn is ceremony.
5. **Close the loop with the founder**: what shipped, what was cut, what the success metric says,
   what is next.

**Gate G9.** 72h clean or all incidents resolved. Postmortem written. One process change adopted.
STATE.md closed out.

---

## Parallelism map (crew mode only)

Most of this pipeline is strictly sequential because each phase consumes the previous phase's
artifact. These are the only safe parallel pairs:

| Can run in parallel | Why it is safe |
|---|---|
| P4 slice N build **+** P4 slice N−1 red team | Different artifacts; red team is read-only |
| P5 hardening **+** P7 docs drafting | Docs describe behavior already frozen by G5 |
| P5 non-functional (R6) **+** P5 code review | Independent evidence streams |
| P7 runbook **+** P7 release notes | Different authors, no shared artifact |
| Multiple independent slices, **only if** their contracts were fixed at G2 | Contracts prevent merge surprise |

**Never parallel:** definition with architecture (design without a spec is guessing); building with
architecting the same slice; taste with hardening (taste on unstable software judges the wrong
thing); anything with launch.
