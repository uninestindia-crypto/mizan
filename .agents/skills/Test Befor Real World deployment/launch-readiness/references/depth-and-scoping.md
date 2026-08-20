# Depth & Scoping

Match the ceremony to the stakes. A full production readiness review on a typo wastes a day and
teaches everyone that the process is theatre.

---

## The five depths

| Depth | Trigger | Gates | Rough effort |
|---|---|---|---|
| **D0 Patch** | Copy change, dependency bump, one-line fix, config tweak | G1 + G2 + the one gate the change touches | 15–30 min |
| **D1 Feature** | A feature going to existing users; a new endpoint; a UI change | G1–G5, G8, G11 — S0 only | 2–4 hours |
| **D2 Release** | A versioned release; a new surface; a schema change; anything users will notice | G0–G12, S0 and S1 everywhere | 1–3 days |
| **D3 Launch** | First public launch; GA; a new product; a data migration; a new region | Everything, uncompressed. No S0 waivers without the owner. | 1–2 weeks |
| **D4 Critical** | Money movement, health or safety, identity, irreversible data transformation, a security model change | Everything, plus a second independent pass by a different actor | 2–4 weeks |

**Declare the depth in your first message.** "Running D2." It determines everything after.

**When torn between two, take the higher one.** The cost of over-verifying is hours. The cost of
under-verifying is the product's reputation, which has no rollback.

---

## Reading the depth from the change

| If the change... | Minimum depth |
|---|---|
| Touches money, payment, pricing, tax, or credit | **D4** |
| Touches authentication, authorization, or tenancy | **D4** |
| Transforms or deletes existing data irreversibly | **D4** |
| Handles health, biometric, financial, or children's data | **D4** |
| Is the first time real users will use this at all | **D3** |
| Changes the database schema | **D2** minimum |
| Adds a new external dependency | **D2** minimum |
| Changes anything in the deploy or infrastructure | **D2** minimum |
| Is user-visible in any way | **D1** minimum |
| Cannot be rolled back in under five minutes | **one level up from wherever you landed** |

That last row is the most useful heuristic in this file. **Reversibility is the real variable.**
A change you can undo in thirty seconds deserves far less ceremony than one you cannot undo at all,
regardless of how large it looks.

---

## What each depth actually runs

### D0 — Patch (15–30 min)

```bash
LRK run G1.01 -- <build>
LRK run G1.03 -- <typecheck>
LRK run G2.02 -- <full test suite from clean>
# plus the one gate the change touches — e.g. a copy change → G8.10; a dep bump → G1.12
LRK report
```

Even at D0, run the **full** suite, not just the affected tests. The whole reason a one-line change
is dangerous is that nobody expects it to break something distant.

### D1 — Feature (2–4 hours)

G1 and G2 in full. Then the S0 checks of G3 (states, forms, destructive actions), G4 (authz on any
new endpoint), G5 (if the schema moved), G8 (keyboard, a11y scan, the new screens), and G11
(rollback rehearsed).

Skip G6, G7, G9, G10, and G12 unless the feature specifically touches them — but **say that you
skipped them** in the NOT TESTED line.

### D2 — Release (1–3 days)

All thirteen gates. Every S0 and every S1. S2 and S3 by judgement.
This is the default for a real release and the depth most teams should be running.

### D3 — Launch (1–2 weeks)

All thirteen gates, every severity, nothing compressed. Additionally:
- Customer Zero (G8.13) with a **real human**, not an agent
- A full 72-hour watch (G12.07) with all five checkpoints
- Load and soak (G6.06–G6.08) at real duration, not shortened
- Every alert fired (G10.06), no exceptions
- The runbook executed by a second person (G11.05), not cold-read

### D4 — Critical (2–4 weeks)

Everything in D3, plus:
- **A second independent pass** on G3, G4, and G5 by a different actor who has not seen the first pass's results. Not a re-read — a fresh execution.
- Rollback rehearsed **twice**, including once by the second person.
- The restore drill (G5.05) performed against a genuine production backup, not a synthetic one.
- Every waiver signed by the owner personally.
- A dry run of the full launch, including the comms, on the production-like environment.

---

## Compressing without breaking

**You may compress a gate. You may not skip one.** The difference:

- **Compressing G6** at D1: skip the soak test, run a five-minute load test instead of thirty, and record why. *The gate ran.*
- **Skipping G6** at D1: no performance evidence at all, and nobody knows it is missing. *The gate did not run, and the report implies it did.*

Compression is recorded in the note:

```bash
LRK manual G6.08 --status na \
  --note "D1 depth. Soak test skipped: change is a UI-only copy edit with no server-side code path touched. Full soak was run at the v1.0.0 release two weeks ago (evidence in that bundle) and nothing in this change affects memory behaviour."
```

That is a defensible compression. A reader can disagree with it, which is the point.

---

## The three gates you never compress

Regardless of depth, if the change touches the relevant area:

1. **G1.10 — secret scanning.** Thirty seconds. There is no change small enough to justify skipping it.
2. **G2.02 — full suite from a clean state.** The single highest-yield check per minute spent.
3. **G11.07 — rollback rehearsed.** If you cannot undo it, you should not do it. This applies to a one-line change as much as a rewrite.

---

## Scoping to the diff

For D0 and D1, you are certifying a *change*, not the whole system. Scope the work accordingly:

```bash
# What actually changed?
git diff --stat <last-release-tag>..HEAD
git diff --name-only <last-release-tag>..HEAD | sed 's|/[^/]*$||' | sort -u
```

Then map the changed areas to gates:

| Changed | Gates that must run |
|---|---|
| `migrations/`, `schema.prisma`, `models/` | G5 in full |
| `auth/`, `middleware/`, `permissions/`, `policies/` | G4 in full — **no compression** |
| `api/`, `routes/`, `controllers/` | G3, G4.01–G4.06, G4.20 |
| `components/`, `pages/`, `views/`, `*.css` | G3.02, G8 |
| `package.json`, `requirements.txt`, any lockfile | G1.12, G1.13, G1.14, G2.02 |
| `Dockerfile`, `k8s/`, `terraform/`, CI workflows | G7, G10, G11 |
| `jobs/`, `workers/`, `tasks/`, `cron` | G7.10, G3.10 |
| Anything under `payments/`, `billing/`, `pricing/` | **D4. Everything.** |

**Nothing changed but a dependency?** That is still G1.12, G1.13, G2.02, and G11.07 — supply-chain
compromises arrive through exactly this door, wearing the costume of a routine bump.

---

## Time-boxing when the deadline is real

Sometimes there are four hours, not three days. Run them in this order and stop when time runs out —
this sequence is ordered by *damage prevented per minute*:

| Order | Check | Minutes | Prevents |
|---|---|---|---|
| 1 | G1.10 secret scan (full history) | 2 | A permanent credential leak |
| 2 | G1.17 no committed secrets or data | 1 | The same |
| 3 | G2.02 full suite from clean | 10 | Shipping something already known broken |
| 4 | G1.12 dependency vulnerabilities | 3 | A known RCE |
| 5 | G11.07 rollback rehearsed and timed | 20 | Being unable to undo |
| 6 | G4.01–G4.06 access control | 45 | The data breach |
| 7 | G5.02 migration rollback executed | 20 | Unrecoverable data damage |
| 8 | G1.11 no sandbox/localhost endpoints in prod | 3 | Payments that silently do nothing |
| 9 | G3.02 the nine states, critical screens | 40 | The product appearing broken |
| 10 | G10.06 fire one alert | 15 | Finding out from a customer |
| 11 | G11.11 environment contract in the target | 20 | The deploy failing on a missing variable |
| 12 | G6.02 latency at realistic volume | 20 | The launch-day slowdown |

**Two hours of this list is worth more than two weeks of unstructured testing.** Then report exactly
what you ran and what you did not:

```
NOT TESTED (deliberate — 4-hour time box):
  G6.06-G6.08  no load, stress, or soak testing. Breaking point unknown.
  G7           no failure injection. Behaviour when a dependency dies is unknown.
  G8.13        no Customer Zero. Nobody outside the team has used this.
  G9           no privacy or compliance review.
  G12          no watch plan exists.
```

That block is not an admission of weakness. It is the most useful paragraph in the report — it tells
the owner exactly where the unlit corners are, which is the one thing they cannot work out for
themselves.
