# 06 — The day-zero gate

The single question this file answers: **may slice 1 start?**

It is answered by a program, not by a discussion.

```bash
node scripts/verify-day-zero.mjs
```

Exit `0` means yes. Anything else means no. There is no middle verdict, and "mostly ready" is not
one of the outcomes.

---

## 1. The nine criteria

The seven from `founder-mode/references/08-bootstrap.md`, plus two the script can check for free.

| # | Criterion | Law | Checkable? |
|---|---|---|---|
| 1 | Typecheck / lint / format configured | 6 | automatic |
| 2 | Test runner present, with a real test | 2 | automatic |
| 3 | **A test you watched fail, then pass** | 2 | **human** |
| 4 | **Migration tool with a rollback you executed** | 7 | **human** |
| 5 | CI runs the full set on every push | 6 | automatic |
| 6 | **A deploy, and a rollback you executed** | 7 | **human** |
| 7 | Config contract: `.env.example` + boot-time validation | 3 | automatic |
| 8 | One health endpoint and one metric | 8 | automatic |
| 9 | Versions pinned, lockfile committed | 1 | automatic |

### The four statuses

| Status | Meaning |
|---|---|
| `OK` | Proven by a signal in the repository, or by a recorded human attestation |
| `FAIL` | The signal is absent. Fix it. |
| `TODO` | Cannot be proven by inspecting files. Needs a human who watched it happen. |
| `??` | The stack was not recognized, so absence is not evidence of absence — check by hand |

**`??` is deliberate.** A checker that guesses on an unfamiliar stack and reports `OK` is worse
than one that admits it does not know, because a false green is load-bearing in exactly the way a
gate must never be.

---

## 2. The three the script cannot check

Criteria 3, 4, and 6 have one thing in common: **a file's existence proves nothing about them.**

- A test file does not prove the suite can fail.
- A `migrations/` folder does not prove a `down` has ever run.
- A deploy script does not prove a rollback has ever been executed.

Each requires a human to have *watched something happen*. The gate holds them at `TODO` until
attested, by name:

```bash
node scripts/verify-day-zero.mjs --attest test-watched-failing --by "Your Name"
node scripts/verify-day-zero.mjs --attest migration-rollback   --by "Your Name"
node scripts/verify-day-zero.mjs --attest deploy-rollback      --by "Your Name"
```

The attestation is written to `.project-zero.json` with a name and a timestamp. **Commit it** — it
is project evidence, and it is the answer to "who said this was ready, and when".

An unsigned attestation is rejected. That is intentional: `founder-mode` Law 4 is *evidence or it
did not happen*, and an anonymous claim is not evidence. Attesting from memory, without having run
the thing, is the one way to defeat this entire skill — do not do it, and do not let a
time-pressured moment be the first time you find out whether the rollback works.

---

## 3. Walking the gate

Run it early and often. On the first commit it should be a wall of red, and that wall is your
to-do list.

```
project-zero — day-zero gate
repo:  /path/to/app
stack: node
------------------------------------------------------------------------------
  OK    Typecheck / lint / format configured
  OK    Test runner present, with a real test
  TODO  A test you watched FAIL, then pass
  TODO  Migration tool with a rollback you executed
  OK    CI runs the full set on every push
  TODO  A deploy, and a rollback you executed
  OK    Config contract: .env.example + boot-time validation
  OK    One health endpoint and one metric
  OK    Versions pinned, lockfile committed
```

Other useful forms:

```bash
node scripts/verify-day-zero.mjs --json     # for a CI step or a dashboard
node scripts/verify-day-zero.mjs ../other   # check a different directory
node scripts/verify-day-zero.mjs --self-test
```

Wiring it into CI is reasonable once it passes, so day-zero properties cannot silently regress —
a deleted `.env.example` or a dropped lockfile then fails the build.

---

## 4. The manual review, after the script is green

The script checks that things *exist and were done*. These are the judgments it cannot make. Walk
them once, before the first feature:

**Layout and boundaries**
- [ ] Code is grouped by domain, not by layer — no `services/` + `controllers/` split
- [ ] There is no `utils/`, `helpers/`, `common/`, or `shared/`
- [ ] The import direction is enforced by a lint rule, not just documented
- [ ] There are no import cycles

**Config and secrets**
- [ ] `.env` is in `.gitignore`, and no real `.env` is committed
- [ ] No `process.env` read anywhere except `config.ts`
- [ ] Production secrets come from a secret manager, not a file

**Errors and logging**
- [ ] No bare `throw new Error(...)` in application code
- [ ] Every boundary wraps unknown throws with `toAppError()`
- [ ] 5xx responses do not leak internal messages — check one by hand
- [ ] Logs are one JSON object per line, with a correlation id
- [ ] A secret-looking field was logged deliberately once, and came out redacted

**Deploy**
- [ ] The deploy is one command or one merge, with no ordered human steps
- [ ] You know what the rollback does *not* undo, and it is written down
- [ ] Staging exists, or its absence has been raised as a launch risk

**The skeleton**
- [ ] It is embarrassing — it does almost nothing
- [ ] No auth, no queue, no cache, no speculative abstraction
- [ ] `/health` was observed returning degraded with the database stopped

---

## 5. Handing off

When the gate is green, day zero is over. Hand to `founder-mode` at P1 (Definition), where the
`spec-writer` turns the first real feature into acceptance criteria.

State the handoff plainly, with the evidence:

```
[DAY ZERO COMPLETE · <repo>]

STACK        <language / runtime / framework / database / hosting, with versions>
GATE         node scripts/verify-day-zero.mjs → exit 0
ATTESTED     test-watched-failing, migration-rollback, deploy-rollback — <name>, <date>
SKELETON     <the one path that works end to end>
DEPLOYED     <environment, version>
ROLLBACK     deploy <n>s (measured), migration up/down verified in CI
NOT DONE     <anything deferred, and why — e.g. no staging environment yet>

Slice 1 may start.
```

**The `NOT DONE` line is not optional.** A handoff that implies completeness while quietly omitting
"there is no staging environment" converts a known gap into an unknown one, and unknown gaps are
what take products down on launch day.
