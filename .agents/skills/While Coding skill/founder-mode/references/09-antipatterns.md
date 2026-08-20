# 09 — Antipatterns

Every entry is a real, observed failure pattern. Each has a **tell** (how you notice it), a
**mechanism** (why it hurts), and a **counter** (what to do instead). Read this when something
feels off, and *always* before believing a report that is entirely green.

## Contents

- [Process antipatterns](#process-antipatterns)
- [Engineering antipatterns](#engineering-antipatterns)
- [Judgment antipatterns](#judgment-antipatterns)

---

## Process antipatterns

### 1. Demo-driven development
**Tell.** The path being tested is always the path being demoed. Someone says "let me show you"
and clicks the same six things.
**Mechanism.** The code is optimized for the rehearsed path, so every other path is untouched
until a user finds it. The team's confidence is proportional to their rehearsal, not to quality.
**Counter.** Ring 5 and Customer Zero, who is not permitted to learn the rehearsed path.

### 2. "We'll harden it later"
**Tell.** Failure states, error messages, and empty states deferred to a "polish phase."
**Mechanism.** The polish phase gets compressed when the date arrives — it always does, because it
is the only phase with no visible deliverable. The failure states never get built, and the first
user to hit one gets a white screen.
**Counter.** Law 6. Failure states ship in the same slice as the happy path. Not the same sprint —
the same slice.

### 3. Horizontal slicing
**Tell.** "First we do all the models, then all the APIs, then the UI."
**Mechanism.** Nothing is demonstrable until the end, so all the risk of integration is stacked at
the end, where there is no schedule left. Progress looks great for weeks and then stalls.
**Counter.** Vertical slices, each ending in something a human can see, run, or call (P3).

### 4. Easy-first ordering
**Tell.** The plan starts with the parts everyone knows how to build.
**Mechanism.** The unknown work — the third-party integration, the migration, the device-specific
behavior — moves to the end, where discovering it is hard means the launch date is already public.
**Counter.** Law 3. Risk first. Slice 1 should be uncomfortable.

### 5. Green status theater
**Tell.** Every status update is green. Nothing is ever amber.
**Mechanism.** Real projects have real problems; a project with no reported problems has a broken
reporting channel, not a perfect execution. Problems surface later and larger.
**Counter.** Report `NOT DONE` and `RISKS OPENED` in every phase report. An amber status delivered
early is a gift; a red one delivered late is a crisis.

### 6. The infinite RC
**Tell.** "One more fix and we'll re-verify." Repeatedly, for days.
**Mechanism.** Each fix is a change; each change invalidates the verification; the team ends up
shipping the *least*-verified version — the one with the most recent, least tested changes.
**Counter.** Real freeze. Only Blockers admitted. Each admitted fix explicitly restarts
verification for what it touched, and if that happens three times, the RC is not an RC — go back
to P5.

### 7. Process as ceremony
**Tell.** Gates are marked passed without evidence; templates are filled in after the fact to
match what was already done.
**Mechanism.** The documents become archaeology instead of decisions, and everyone learns the
checklist is theater — which means the one time it would have caught something, it does not.
**Counter.** Evidence or BLOCKED (Law 4). And scale honestly (`10-scaling.md`) — a T1 change with a
full T3 ceremony is what teaches people the process is fake.

### 8. Scope creep by adjacency
**Tell.** "While I was in there, I also…"
**Mechanism.** The change grows beyond what was specified, reviewed, and tested. The extra work
carries none of the gates the planned work carried, so quality is inverse to how much of it there
is.
**Counter.** Note it, finish the slice, raise it at the gate. Adjacent improvements are their own
slice with their own gate.

### 9. The hero deploy
**Tell.** One person deploys, at night, alone, because they know the steps.
**Mechanism.** The knowledge is not written down, so it cannot be checked, improved, or executed by
anyone else during an incident — including at 3am when that person is unreachable.
**Counter.** A runbook a stranger can execute, dry-run by someone else before the day (P7 step 5).

### 10. Postmortem inflation
**Tell.** A postmortem with fifteen action items.
**Mechanism.** Fifteen items means no owner, no priority, and no adoption. Zero changes actually
happen, and the same failure repeats.
**Counter.** Exactly one process change, adopted immediately, written back into the skill.

---

## Engineering antipatterns

### 11. "It works locally"
**Tell.** Evidence is a local run.
**Mechanism.** Local means warm caches, seeded data, one user, fast network, permissive env, an
already-migrated database, and dev-mode error handling. Every one of those differs in production.
**Counter.** Clean-state verification (fresh deps, fresh DB, migrations from zero) plus a
production-like environment run before G7.

### 12. Tests that cannot fail
**Tell.** The suite has never gone red on its own. Tests assert "did not throw."
**Mechanism.** Coverage numbers rise while defect detection stays at zero. The team's confidence
is entirely unearned.
**Counter.** Break the implementation deliberately and watch the test go red. Do it once per slice
on the most important test. Mutation testing on domain logic if the stack allows.

### 13. Flaky-test tolerance
**Tell.** "Just re-run it, it passes on the second try."
**Mechanism.** The suite stops being a signal. Real failures get re-run away. The flake is often a
genuine race condition — the test is correctly detecting a real bug that will also happen in
production, just less conveniently.
**Counter.** A flaky test is a failing test. Fix the race or delete the test. Never re-run until
green.

### 14. Mock-shaped confidence
**Tell.** Integration tests where every dependency is mocked.
**Mechanism.** You have tested that your mocks match your assumptions — which is precisely the
thing that was never in doubt. The actual integration is untested.
**Counter.** Mock at the network/process boundary only. Real DB, real migrations for R3.

### 15. Untested rollback
**Tell.** The rollback exists as a paragraph in a document.
**Mechanism.** Rollback is executed exactly once, under maximum stress, by someone who has never
run it, while users are affected. That is when you learn it does not work.
**Counter.** Execute it, against realistic data, timed, before T-3 days. Record the duration.

### 16. Migration tested at toy scale
**Tell.** "The migration ran fine" — on a dev database with 40 rows.
**Mechanism.** At production scale it locks a hot table for six minutes and takes the site down;
or it times out halfway and leaves the schema in a state neither version of the code understands.
**Counter.** Run it on a production-scale copy. Time it. Measure the longest lock. Test the *old*
code against the *new* schema, because that combination exists during every rolling deploy.

### 17. Silent failure
**Tell.** `catch (e) {}`, a default value substituted for an error, a job that logs and returns.
**Mechanism.** The system produces wrong answers confidently. Nobody notices for months. The
damage compounds and the audit trail is already wrong.
**Counter.** Family 12 of `05-hardening.md`. Every swallowed error is a finding; escalate silent
failures one severity level.

### 18. Alerts that have never fired
**Tell.** "Monitoring is configured."
**Mechanism.** Configured is not working. Wrong threshold, wrong channel, wrong credentials,
notification muted, or the alert queries a metric that stopped being emitted two refactors ago.
**Counter.** Fire every alert deliberately; confirm a human received it (G7.7).

### 19. No baseline
**Tell.** During launch: "is 340ms bad?"
**Mechanism.** Without pre-launch numbers, no signal is interpretable. Every launch-day decision
becomes a debate about whether this is normal.
**Counter.** Capture the baseline at T-7 days, and set thresholds *relative to it* as numbers.

### 20. The unread config
**Tell.** A new env var that defaults to something reasonable when missing.
**Mechanism.** It is missing in production; the reasonable default is wrong; nothing fails, so
nobody knows — until the behavior is discovered to have been wrong for weeks.
**Counter.** Fail loudly at startup on any missing required config. A contract test that asserts
every required variable is declared and present.

### 21. Permission by UI
**Tell.** The button is hidden for users who may not do the thing.
**Mechanism.** The API does not check. Anyone who reads the network tab has admin.
**Counter.** Family 2. Test every endpoint directly, with every role, ignoring the UI entirely.

### 22. The trusted client
**Tell.** Price, quantity, permission, discount, or user ID taken from the request body.
**Mechanism.** All of it is attacker-controlled. Prices become zero; user IDs become someone
else's.
**Counter.** Recompute every consequential value server-side from server-held state. The client
sends intent, never facts.

### 23. Float money
**Tell.** `price * quantity` on a floating-point type.
**Mechanism.** 0.1 + 0.2 ≠ 0.3. Errors accumulate silently and the ledger stops balancing, usually
discovered by an accountant months later.
**Counter.** Integer minor units or a decimal type, end to end. Blocker severity, always.

### 24. Retry without idempotency
**Tell.** A retry policy on a non-idempotent operation.
**Mechanism.** Double charges, duplicate orders, doubled emails. The first timeout that is actually
a slow success does the damage.
**Counter.** Idempotency keys on every mutating operation that can be retried, tested by replaying
the same request.

### 25. Pagination without a stable sort
**Tell.** `ORDER BY created_at` with no tiebreaker, paged.
**Mechanism.** Rows shift between pages as data changes; users see duplicates and miss items.
Exports silently lose records — the worst version, because nobody sees it happen.
**Counter.** Always sort by a unique tiebreaker; prefer cursor pagination for anything exported.

### 26. The lonely index
**Tell.** A query that is fast on dev data.
**Mechanism.** Dev has 200 rows; every query is fast without indexes. Production has 2M and the
same query takes 40 seconds under load.
**Counter.** Test at production scale (Family 6), count queries per request, and check the actual
query plan on the biggest table.

### 27. Timezone by accident
**Tell.** Dates stored without timezone, or "it works, we're all in one country."
**Mechanism.** DST arrives, or one user travels, or the server moves region. Reports shift by a
day; scheduled jobs run twice or not at all.
**Counter.** UTC everywhere in storage, explicit timezone at the boundary, and the date test cases
from `04-test-matrix.md`.

---

## Judgment antipatterns

### 28. Believing the summary
**Tell.** A subagent or a tool reports "all tests pass" and it becomes your claim.
**Mechanism.** Summaries drop the failures. Agents optimize for a satisfying report. You relay it,
the founder acts on it, and the truth surfaces later at greater cost.
**Counter.** Read the raw output before repeating a claim. Especially "all tests pass."

### 29. Optimism as a status
**Tell.** "Should work," "looks good," "I believe it's fine," "this ought to handle it."
**Mechanism.** These are feelings formatted as facts. They are indistinguishable, downstream, from
verified statements — which is exactly why they are dangerous.
**Counter.** Say what you ran and what it printed. If you did not run it, say "not verified" in
those words.

### 30. The confident unknown
**Tell.** Answering a question about behavior you have not observed.
**Mechanism.** A plausible-sounding answer about how the system behaves is worse than "I don't
know" because it stops the investigation that would have found the truth.
**Counter.** Go look. The code is right there, and running it takes less time than reasoning about
it.

### 31. Sunk-cost architecture
**Tell.** "We've already built it this way."
**Mechanism.** A design known to be wrong survives because changing it feels wasteful, and every
subsequent slice makes it more expensive to change.
**Counter.** Discovering the design is wrong is a *success* of risk-first ordering. The cost of
changing it is lowest right now and rises every day. Return to P2.

### 32. Politeness over accuracy
**Tell.** Softening a red result to avoid disappointing the founder.
**Mechanism.** The founder makes decisions on false information, and the correction arrives when
it is expensive and public.
**Counter.** Bad news first, in the first sentence, with a number and a recommendation. Founders
do not want cheerful; they want accurate, early, and actionable.
