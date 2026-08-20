# 07 — Artifact Templates

Copy these into the configured launch-state directory (default `.launch/`) only when project
state writes are authorized. Keep them short: every artifact should fit on one or two screens.

## Contents

- [Charter and PRD](#chartermd--p0)
- [ADR and architecture](#adr-nnnmd--p2)
- [Slices and slice reports](#slicesmd--p3)
- [Risks and state](#risksmd--maintained-from-p0-to-p9)
- [Release candidate and postmortem](#rc-report--p7)

---

## CHARTER.md — P0

```markdown
# CHARTER — <name>

TIER: T<0-4>            DATE: <yyyy-mm-dd>            FOUNDER: <who decides>

## The one sentence
<What we are building, in your words, confirmed by the founder.>

## The user
<A specific role in a specific situation. Not "users". If several, rank them —
 the primary user wins every trade.>

## The job to be done
<In the user's language, not ours.>

## "No problems for users" means
MUST NEVER HAPPEN:   <data loss / wrong money / leaked data / silent failure / …>
MUST ALWAYS WORK:    <the critical path, even degraded>
MAY BE IMPERFECT:    <what we accept at launch — answer this honestly>

## The first ten minutes
<Prose. A stranger arrives. What happens, step by step, until they get value?
 This narration is the real spec — every later decision is judged against it.>

## Kill criteria
<Conditions under which we stop, postpone, or cut. Written now, while nobody is invested.>

## Success metric
<One number, measurable after launch.>
```

---

## PRD.md — P1

```markdown
# PRD — <name>

## Stories
As a <specific role>, I need to <job>, so that <outcome>.

## Acceptance criteria
AC-1  GIVEN <state>  WHEN <action>  THEN <observable outcome>
AC-2  …
<Every one machine- or checklist-verifiable. Zero unquantified adjectives:
 "fast" → "p95 < 400ms on the seeded dataset". "intuitive" → "Customer Zero
 completes it unaided in < 90s". Describe user outcomes, not implementation —
 "returns 201" is a failed criterion.>

## Non-goals — the cut line          ← MAY NOT BE EMPTY
- <thing we are explicitly not doing, and when we might>

## Failure states (per story)
EMPTY:          <what the user sees with no data>
LOADING:        <…>
ERROR:          <what it says, and what the user does next>
OFFLINE:        <…>
UNAUTHORIZED:   <…>
SLOW:           <…>
PARTIAL/STALE:  <…>
TOO MUCH DATA:  <…>
CONCURRENT:     <two people, same object, same moment>

## Ambiguity log
| # | Ambiguity | Assumption made | Who must confirm | Blocking? |
```

---

## ADR-nnn.md — P2

```markdown
# ADR-<nnn>: <decision in five words>

STATUS: proposed | accepted | superseded by ADR-<n>     DATE: <yyyy-mm-dd>

## Context
<The forces. What is true that makes this a decision rather than an obvious choice?>

## Options
### A — <name>          ← chosen
Pros / Cons / Cost
### B — <name>
Pros / Cons / Cost — and why it lost

## Decision
<What we are doing.>

## Consequences
GOOD:      <…>
BAD:       <what we are accepting — this section may not be empty>
OPERATIONAL: <what this adds to run, monitor, back up, or pay for>

## We would reverse this if
<Concrete, observable conditions. This is what stops the decision being
 re-litigated by opinion in month four.>
```

---

## ARCHITECTURE.md — P2

```markdown
# ARCHITECTURE — <name>

## Shape
<Diagram or prose. What talks to what.>

## Contracts
### <boundary name>
REQUEST:   <exact shape>
RESPONSE:  <exact shape>
ERRORS:    <code → meaning → what the caller should do>
AUTH:      <who may call it, checked where>

## Data model
NEW/CHANGED: <tables, columns, indexes, constraints>
MIGRATION:   <forward steps>
ROLLBACK:    <backward steps>  ← and how it will be REHEARSED
BACKFILL:    <how existing rows are handled; how long it takes at prod scale>

## Failure behavior (per dependency)
| Dependency | Timeout | Retry | Idempotent? | Degraded mode | User sees |

## Observability
LOG:    <events, with what context>
COUNT:  <metrics>
PAGE:   <what wakes a human, and at what threshold>
TRACE:  <correlation id, propagated how>

## Permission model
| Role | Resource | Action | Allowed? | Enforced where | Test that proves it |
```

---

## SLICES.md — P3

```markdown
# SLICES — <name>

Ordered by RISK, not by ease. Slice 1 is the scariest thing.

| # | Slice | Demo (one sentence) | Part types | Rings | Depends on | Status |
|---|-------|---------------------|-----------|-------|-----------|--------|
| 1 | <the riskiest unknown> | <what you show when done> | api, db, money | R0-R5 | — | ⬜ |
| 2 | … | | | | | |

Status: ⬜ not started · 🟡 building · 🟠 red team · 🟢 G4 passed

## Why slice 1 is the riskiest
<One line. If you cannot justify it, the order is wrong.>
```

---

## Slice report — P4, one per slice

```markdown
[P4 · slice <n>/<total> · G4 <PASSED|BLOCKED>]

SLICE        <name>
CRITERIA     <the ACs this slice satisfies>

WHAT CHANGED
- path/to/file.ts — <one line>

EVIDENCE
$ <the exact command>
<RAW OUTPUT — the actual text, not a summary>

FAILURE STATES     each one, and how it was demonstrated
RED TEAM           <n> findings — <n> Blocker, <n> Major, <n> Minor; disposition of each
REGRESSION TESTS   one per finding, each verified to fail without the fix
CLEAN VERIFY       fresh deps + fresh DB + migrations from zero → <raw output>

NOT DONE           what was in scope and isn't finished, and why
RISKS OPENED       new failure modes this introduces
NEXT               slice <n+1>: <name>
```

---

## RISKS.md — maintained from P0 to P9

```markdown
# RISK REGISTER

| # | Risk | Likelihood | Impact | Detected by | Mitigation | Owner | Status |
|---|------|-----------|--------|-------------|------------|-------|--------|
| 1 | <what could go wrong> | H/M/L | H/M/L | <which ring or monitor> | <what we did> | | open |

## Accepted risks     ← founder-signed only
| # | Risk | Why accepted | Who accepted | Date |
```

Add a row the moment a risk is named — in P0, in an ADR, in a red team finding, in a gate. The
value of this file is that at G7 you can read it top to bottom and ask "is each of these still
true?"

---

## STATE.md — the company's memory

```markdown
# STATE — <name>

TIER: T<n>     PHASE: P<n>     UPDATED: <yyyy-mm-dd hh:mm>

## Gates
G0 ✅ <date>  G1 ✅ <date>  G2 ✅ <date>  G3 ✅ <date>
G4 🟡 slice 4/7   G5 ⬜  G6 ⬜  G7 ⬜  G8 ⬜  G9 ⬜

## Blocked on
<the single most important thing right now, or "nothing">

## Open Blockers/Majors
| # | Severity | Description | Owner | Since |

## Decisions made this session
- <decision> — <why> — <who decided>

## Founder overrides
| Gate | What was waived | Risk accepted | Date |

## Next action
<the literal next thing to do, specific enough to start cold>
```

Update this **at every gate**, without exception. It is what lets a new session, or a different
person, resume without re-deriving anything — and the "Next action" line is what makes a cold start
take thirty seconds instead of an hour.

---

## RC report — P7

```markdown
[P7 · release candidate · G7 <PASSED|BLOCKED>]

VERSION        <sha>          ROLLBACK TARGET <sha>
FROZEN SINCE   <date>         CHANGES SINCE FREEZE <list, or none>

CLEAN-STATE VERIFICATION
$ <every command, in order>
<RAW OUTPUT>

PRODUCTION-LIKE RUN     env: <…> · critical path exercised: <…> · result: <…>
ROLLBACK REHEARSAL      executed <date> · duration <mm:ss> · data <realistic?>
MIGRATION TIMING        prod-scale · duration <mm:ss> · max lock <mm:ss>
MONITORS FIRED          <n>/<n> confirmed received by a human
BASELINE CAPTURED       err <x> · p95 <y>ms · <business metric> <z>
ENV CONTRACT            <n>/<n> vars, secrets, quotas verified present
BACKUP + RESTORE        taken <time> · restored to <machine> · verified <how>
DOCS                    release notes ✅ · support brief ✅ · migration guide ✅

KNOWN LIMITATIONS       <shipped-with, and documented for support>
OPEN RISKS              <from RISKS.md, still open at RC>
GO / NO-GO              <recommendation, with the one-sentence risk statement>
```

---

## POSTMORTEM.md — P9

See the full template in `06-launch-runbook.md`. The two sections people skip, and must not:
**WHAT THE GATES CAUGHT** (the return on the entire process — without it, the process looks like
pure cost) and **THE ONE CHANGE** (exactly one, adopted now, written back into the skill).
