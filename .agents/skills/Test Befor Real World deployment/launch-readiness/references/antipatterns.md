# Antipatterns — how this process gets faked

Read this when a report looks too green, when a gate passed suspiciously fast, or before you
believe your own results.

Every item below is a real, observed pattern. None requires bad intent — almost all of them are
what a tired, well-meaning person does at hour nine.

---

## The tells of a report that is lying

Check your own output against these before you send it.

**1. Everything is green.** Real software has amber. A first pass over a real codebase that
produces zero findings means the checks did not run, ran against the wrong thing, or were marked
pass without being run. Uniform green means the reporting is broken, not the project perfect.

**2. The proof column is mostly ASSERTED.** Count them. If a report has 90 passes and 60 are
assertions, it is a document of opinions with a hash on it. The kit prints these counts on purpose.

**3. Gates completed in suspiciously little time.** G4 has 28 checks, most of which require probing
a running system. If it took eleven minutes, it did not happen.

**4. Lots of N/A with short reasons.** `"n/a"`, `"not applicable"`, `"doesn't apply"`. Every one of
those is a check somebody wanted to make disappear. Read the reasons; the kit prints them all.

**5. No failures anywhere in the history.** The report shows every record including failures. A
process where nothing ever failed and then got fixed is a process where nothing was tested.

**6. Evidence timestamps cluster in a five-minute window.** Real verification is spread across
hours or days. A cluster means someone bulk-recorded results after the fact.

**7. The git commit in the evidence differs from the release commit.** The kit records the SHA on
every run. Evidence gathered against a different version is evidence about a different program.

---

## Faking specific checks — and how to catch it

| Check | The fake | How to catch it |
|---|---|---|
| **G1.03** typecheck | `@ts-ignore` / `# type: ignore` added during the audit | `git diff` — new suppressions appearing during a readiness review is the definition of faking it |
| **G1.04** lint | Rules disabled in the config, or `--max-warnings` raised | Diff the lint config against the last release |
| **G1.10** secrets | Scanning only the working tree | The log must show a history scan. `gitleaks detect` without `--no-git` covers history |
| **G1.12** vulns | `--audit-level=critical` to hide the highs | Read the actual flags in the recorded command |
| **G2.01** tests exist | `npm test` printing "no test specified" and exiting 0 | Read the log; a test count must appear |
| **G2.02** clean state | Run in the warm working directory | The log must show the delete/reinstall/re-migrate steps |
| **G2.06** sabotage | Skipped, or done on a trivial function | Three records with `--expect-fail` must exist, naming the three functions, all on critical paths |
| **G2.18** CI green | Green on an older commit | Compare the SHA in the CI output to the release SHA |
| **G3.02** nine states | Screenshots of three states, called nine | Count the attachments |
| **G4.02** authz matrix | Testing only admin-yes and anonymous-no | The interesting cells are in the middle; the test must be table-driven |
| **G4.20** error leakage | Tested in development mode | The log must show production mode. Dev mode is *supposed* to be verbose |
| **G4.25** security scan | Scan run, findings never read | An empty findings list on a real application usually means it did not run correctly |
| **G5.02** rollback | "We have a down migration" | The word is **executed**. There must be a recorded run with a duration |
| **G5.03** migration at scale | Tested on the dev database's 40 rows | The note must state the row count |
| **G5.05** restore drill | "Backups are configured" | There must be a recorded restore with a timing and a verification query |
| **G6.02** latency | Measured against an empty database on localhost | The note must state the row count and the environment |
| **G6.07** breaking point | "We tested at expected load and it was fine" | The check is to *find where it breaks*. A number must exist |
| **G7.01** dependencies | Reading the retry code | Each dependency needs its own record showing it was actually stopped |
| **G8.13** Customer Zero | The developer clicking through their own product | Must name a different person, or state clearly that an unprimed agent was used instead |
| **G10.06** alerts fired | "Alert rules are configured" | Screenshot of a received notification. Somebody's phone buzzed |
| **G11.07** rollback rehearsed | The runbook contains a rollback section | Executed, on the production-like environment, with seconds recorded |
| **G11.11** env contract | "We set the variables" | Verified *in the target*, with output |

---

## The structural antipatterns

### Demo-driven development

Building until it looks right on the one path you rehearse. This is the single largest cause of
launch-day disaster, because the rehearsed path is genuinely flawless and everything one step off
it has never been executed by anyone.

**Counter:** G3.02 (all nine states) and G8.13 (Customer Zero, who is not allowed to know the path).

### The suite that has never failed

Tests written after the code, asserting what the code already does, never validated against a
regression.

**Counter:** G2.06. Break three things on purpose and watch tests go red. This is the highest-value
twenty minutes in the entire process.

### The rollback nobody has run

Written, reviewed, approved, never executed. It fails at exactly the moment you need it, because
that is the first time anyone has run it.

**Counter:** G5.02 and G11.07 — both require a recorded execution with a duration.

### The migration tested on forty rows

Eight milliseconds locally. Nine minutes and a full table lock in production.

**Counter:** G5.03 requires the row count in the note and the lock duration measured.

### Monitors that have never fired

Four alert rules in the dashboard. Two routed to a Slack channel nobody watches. One with an expired
integration key. One whose threshold could never be reached.

**Counter:** G10.06. Fire every one deliberately, confirm it reaches a human, record the delay.

### "It works locally"

Locally means warm caches, seeded data, one user, no latency, permissive CORS, debug on, and every
environment variable set from a file you forgot exists.

**Counter:** G11.06 and G11.11 — deployed to a production-like environment, contract verified in the
target.

### The bus factor of one

One person can deploy. One person understands the migration. One person knows where the DNS is.

**Counter:** G11.05 (a second person executes the runbook) and G7.13 (single points of failure
enumerated, including human ones).

### Postmortem inflation

Fifteen action items. Everyone agrees. Nobody owns them. The next postmortem produces fifteen more.

**Counter:** G12.12 permits exactly one, and requires it be written back into the checklist.

### The green-status culture

Every update is green because amber invites questions. The project goes from 100% green to
catastrophically late in one week.

**Counter:** the kit computes the verdict from data. It cannot be persuaded, and the certificate
prints the blocker list whether anybody wants it there or not.

---

## Antipatterns specific to an AI running this process

You are more susceptible to some of these than a human is. Read them as warnings about yourself.

**1. Reading code and concluding it works.** Static reading feels like verification and is not. The
authorization logic looks correct in every codebase that has ever leaked data. **Run it.**

**2. Summarising output instead of capturing it.** "Tests passed" is a claim. The `lrk run` log is
evidence. Never substitute your reading of the output for the output.

**3. Marking pass because the command exited 0.** Some commands exit 0 while doing nothing. `npm
test` with no test script. A grep with no matches. A linter with no configuration. **Read the log
body, not only the exit code.**

**4. Optimism under social pressure.** When the user wants a GO, there is real pressure to find a
reading of the evidence that permits one. Resist it structurally: the kit computes the verdict; you
relay it. If they want to ship over a blocker, `waive --accept-blocker-risk` exists and puts their
name on it. That is the honest path, and it is available.

**5. Inventing plausible output.** The most dangerous failure available to you. If a command could
not run, the answer is `todo` and a sentence in NOT TESTED. Never write what the output would
probably have looked like. **The whole value of this skill is that its output is trustworthy; one
fabricated log destroys that permanently.**

**6. Skipping the boring checks.** G1.17 (nothing secret committed) is one command and feels
beneath attention. It is also, statistically, one of the likeliest to find something.

**7. Losing the thread on a long run.** 216 checks across many hours. Run `LRK status` frequently.
The state file is the memory — trust it over your recollection of what you have done.

**8. Treating the profile as a formality.** Getting `--profile` wrong silently removes dozens of
applicable checks and produces a confident, worthless report. When unsure, add the tag.

---

## The final self-check

Before you send the report, answer these four honestly:

1. **Is there anything in here I marked pass without watching happen?** Change it to `todo`.
2. **Is there an N/A whose reason I would be embarrassed to defend?** Change it to a waiver.
3. **If this launch fails next week, which check will everyone say should have caught it?** Go run that one.
4. **Would I stake my own reputation on this verdict?** If not, say which part you would not, in the report.

That last question is the whole discipline in one sentence. Everything else here is scaffolding
around it.
