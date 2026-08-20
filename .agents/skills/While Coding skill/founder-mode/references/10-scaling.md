# 10 — Scaling: Sizing the Process to the Stakes

A process that costs more than the work it protects gets abandoned — and a process that is
abandoned protects nothing. This file is how founder-mode stays used.

**The core principle:** account for every phase; its *depth* scales. Execute, compress, or mark a
phase not applicable as the tier table permits. Never omit one silently.

## Contents

- [Declare the tier](#declaring-the-tier)
- [Requirements by tier](#what-each-tier-requires)
- [Tier playbooks](#tier-playbooks)
- [Safe compression](#compressing-without-breaking)
- [Match the request](#reading-the-room)

---

## Declaring the tier

Do it in your first message, out loud: **"This is T2."** Then size everything to it.

| Tier | Name | Examples | Blast radius if wrong |
|---|---|---|---|
| **T0** | Trivial | Typo, copy change, comment, dependency patch bump, log message | Nobody notices |
| **T1** | Contained | One bug fix, one endpoint, one component, an internal script | A few users, quickly reversible |
| **T2** | Substantial | A feature, a new screen, a schema change, a new dependency, a refactor across modules | Many users; a bad day |
| **T3** | Launch | New product, public launch, data migration, auth change, a rewrite, a new region | Every user; reputation |
| **T4** | Betting the company | Money movement, irreversible data migration, security model change, compliance-bearing work, anything where "undo" does not exist | Existential — money, legal, or trust |

**Choosing between two tiers: go up.** Over-testing costs hours; under-testing costs the product's
reputation, and reputation has no rollback. The asymmetry is not close.

**Automatic tier escalation.** Regardless of how small the change looks, it is **at least T2** if it
touches: money, authentication, authorization, tenancy, personal data, a database migration, a
public API contract, anything a third party integrates with, or the critical path. And it is
**at least T3** if it is irreversible.

---

## What each tier requires

| | **T0** | **T1** | **T2** | **T3** | **T4** |
|---|---|---|---|---|---|
| **P0 Charter** | N/A | 1 sentence | ½ page | full + founder | full + founder + written kill criteria |
| **P1 Define** | N/A | ACs only | full PRD | full PRD | full PRD + independent review |
| **P2 Architect** | N/A | N/A unless design changes | ADR + contracts | full + rollback rehearsal plan | full + a second architect reviews |
| **P3 Slice** | N/A | list of steps | SLICES.md | SLICES.md + risk order justified | + dependency and failure mapping |
| **P4 Build** | direct | build loop, compressed | full build loop | full build loop | full + pair/review on every slice |
| **P5 Harden** | affected tests | R5 on the change | R5 full + R6 | R5 + R6 full system | R5 + R6 **twice**, second by a different actor |
| **P6 Taste** | N/A | glance if user-visible | full if user-visible | full | full + founder demo |
| **P7 RC** | N/A | verify + deploy | clean verify + runbook | full G7 | full G7 + full dry run in staging |
| **P8 Launch** | direct | direct | staged if possible | full staged rollout | staged + war room + founder present |
| **P9 Watch** | none | check it works | 24h watch | 72h watch + postmortem | 72h + postmortem + external review |
| **Rings** | R0 + affected | R0–R3, R5 on change | R0–R6 | R0–R8 | R0–R8, twice |
| **Roles** | you | you + recorded solo exception | three actors, crew approved | full roster (crew) | full roster + independent verifier |
| **Gates needing evidence** | — | G4 | G4, G5, G7 | all | all, twice |

---

## Tier playbooks

### T0 — Trivial

```
1. Make the change.
2. Run R0 (static) + any test touching the file.
3. Verify the actual rendered/observable result if it is user-visible.
4. Report: what changed, evidence, done.
```

The one trap: **a "typo fix" in a string that is a key, a URL, an enum value, a translation key,
or a config name is not T0.** It is T1 or T2, because something depends on the exact text. Check
what references it before you decide it is trivial.

### T1 — Contained

```
P1(¶)  One paragraph: what, for whom, acceptance criteria, what is NOT included.
P3     List the steps in order. Riskiest first.
P4     Build loop: test-first → happy path → failure states → R0 → red team hat → clean verify.
P5     R5 on the changed surface only: input boundaries, auth if touched, concurrency if mutating.
P7     Verify from clean, then deploy.
P9     Confirm it works in production. Watch briefly.
```

Typical shape: 30–60 minutes of process around a few hours of work. If the process exceeds the
work, you are at the wrong tier — either drop to T0 or you have discovered it is really T2.

### T2 — Substantial

The full pipeline, honestly executed, compressed where the artifact is obvious. Use three actors;
if crew mode is not approved, report the T2 review as blocked on independent verification.
The things that must **not** be compressed at T2:

- **G4.8** — clean-state verification per slice
- **R5** — red team on every slice, with the stance change
- **Failure states** in the same slice as the happy path
- **A regression test for every bug found**
- **G5.12** — re-run the suite after the fixes

Those five are where T2 defects escape. Everything else can be a paragraph instead of a page.

### T3 — Launch

Everything, uncompressed, crew mode. Additional requirements:

- Founder present at G0, G6, and G7
- A production-like environment is mandatory — no exceptions, and if one does not exist, building
  it is slice 1
- The 72-hour watch is scheduled with named people at each checkpoint before launch day
- Written comms plan for both outcomes (success and rollback)
- Rollback rehearsed **and timed**, with the duration in the runbook

### T4 — Betting the company

Everything in T3, plus:

- **A second, independent verification pass** by an actor who did not see the first one. Not a
  re-run — an independent design of the verification.
- **P5 run twice**, the second time by a different actor with no knowledge of the first findings.
  The second pass consistently finds things the first missed, because the first pass's coverage was
  shaped by its own assumptions.
- **A full dry run in staging**, including the migration, the rollback, and the comms.
- **A dated decision record** for every founder acceptance of risk.
- **An explicit abort point**: the moment after which rolling back becomes impossible, named in the
  runbook, with the founder's confirmation required to cross it.
- Consider whether it needs to be T4 at all — the most senior move available is to redesign the
  change so it is reversible. **A reversible T3 beats an irreversible T4 every time**, and finding
  that design is worth days.

---

## Compressing without breaking

**Safe to compress:** the length of documents, the number of ADRs, the formality of handoffs, the
size of the crew, the depth of R6, the number of rollout stages.

**Never compress, at any tier above T0:**

1. **Failure states in the same slice as the happy path.** This is the compression that always
   looks harmless and is always the one users hit.
2. **A regression test for every bug found.** Skipping this guarantees the bug comes back.
3. **Clean-state verification before claiming done.** The gap between "works here" and "works from
   zero" is where the largest share of escaped defects live.
4. **An adversarial pass.** T2+ requires someone other than the author. T1 may use the recorded
   solo stance-switch exception when crew mode was not requested or approved.
5. **Evidence in reports.** The moment claims replace output, every downstream decision is built on
   sand.
6. **A rehearsed rollback for anything that touches production data.**

If the schedule cannot accommodate those six, the schedule is wrong, and that is a founder
conversation — not a thing to silently absorb by lowering quality. Say it plainly, with the trade:
"we can ship Thursday without a rehearsed rollback, or Friday with one — I recommend Friday because
this migration is not reversible by hand."

---

## Reading the room

Founder-mode is a tool, not an identity. Match the register to the request:

- **"Just fix this typo"** → T0. Fix it. Do not narrate a pipeline. Announcing "declaring tier T0"
  for a one-word change is its own antipattern and it teaches people to route around the process.
- **"Can you add X?"** → usually T1–T2. Do the process, mention only what matters: the acceptance
  criteria you assumed, and the evidence.
- **"Are we ready to launch?"** → this is a G7 audit. Walk the checklist and report honestly,
  including everything that is not ready. This is the question the whole skill exists for.
- **"Build me a product"** → T3. Full pipeline, and start at P0 with actual questions.
- **"Why did this break?"** → P9 postmortem, plus the missing ring gets written into the matrix.

The process should be **invisible when small and unmistakable when large**. A founder should never
have to ask you to be careful about a payment migration, and should never have to sit through a
gate review for a copy change.
