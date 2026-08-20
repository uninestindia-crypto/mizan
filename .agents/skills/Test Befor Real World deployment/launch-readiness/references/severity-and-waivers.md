# Severity & Waivers

What blocks a launch, what merely worries you, and how to ship anyway — honestly.

---

## The four severities

| | Name | Definition | Verdict effect |
|---|---|---|---|
| **S0** | Blocker | Failure means data loss, a security breach, money moving incorrectly, a legal violation, or the product not working for real users | Must be `pass` with EXECUTED or ATTACHED proof, or `na` with a reason. Anything else → **NO-GO** |
| **S1** | Major | Failure means significant user harm, operational pain, or an incident that is hard to diagnose | Must be fixed or waived in writing → otherwise **GO WITH CONDITIONS** |
| **S2** | Minor | Failure degrades quality but users can still succeed | Fix, or record a dated follow-up |
| **S3** | Advisory | Worth knowing, no launch impact | Record the answer |

### What makes something S0

An S0 has at least one of these properties:

- **Irreversible** — data lost, money moved, an email sent, a record destroyed
- **Silent** — it fails without anyone noticing, so the damage accumulates
- **Universal** — it affects every user, not an edge case
- **A door for someone else** — an attacker, a scraper, a competitor
- **Legally binding** — a regulator, a contract, or a court is involved

Note what is *not* on that list: severity, ugliness, and embarrassment. A hideous but functional UI
is S2. A beautiful checkout that occasionally charges twice is S0.

---

## The verdict, precisely

The kit computes it. This is the exact rule, from `_verdict()` in `lrk.py`:

```
For every APPLICABLE check that is not N/A:

  S0 and status == fail                          → BLOCKER (FAILING)
  S0 and status == todo                          → BLOCKER (NOT TESTED)
  S0 and status == waived                        → BLOCKER (BLOCKER WAIVED)
  S0 and status == pass and proof == asserted    → BLOCKER (ASSERTED WITHOUT PROOF)
  S0 and status == pass and proof == none        → BLOCKER (NO EVIDENCE RECORDED)

  S1 and status == fail                          → WARNING
  S1 and status == todo                          → WARNING
  S1 and status == pass and proof is weak        → WARNING (WEAK EVIDENCE)

  S2/S3 and status == fail                       → WARNING (minor)

any blockers  → NO-GO
any warnings  → GO WITH CONDITIONS
neither       → GO
```

**NOT TESTED counts as FAILED.** The burden of proof is always on the claim, never on the doubt.
This is the single most important line in the whole policy: it means silence cannot pass a gate.

---

## Waivers — the honest shortcut

A waiver is not a failure of the process. It is the process working: a shortcut with a **name**,
a **reason**, and a **stated risk** attached to it, recorded permanently.

Every real launch has waivers. A launch with zero waivers usually means somebody quietly marked
things N/A.

```bash
python lrk.py waive G6.12 \
  --by "R. Patel, CTO" \
  --reason "Pre-revenue. Single region, expecting fewer than 200 users in month one." \
  --risk "An unexpected traffic spike produces a surprise cloud bill. No hard spend cap is configured; a billing alert at $600 exists but is reactive, not preventive." \
  --expires 2026-11-01
```

### The four required parts

1. **`--by`** — a named human, with their role. Not "the team", not "engineering". A waiver with no
   name is an anonymous decision, and anonymous decisions get made carelessly.
2. **`--reason`** — why it is not being fixed now. "It's hard" is honest and acceptable.
   "It's fine" is not a reason.
3. **`--risk`** — **the important one.** What actually happens if this goes wrong, stated as an
   outcome a non-engineer understands. If you cannot write a plausible bad outcome, either the
   check does not apply (mark it N/A instead) or you have not understood it.
4. **`--expires`** — when it must be revisited. Waivers without expiry dates become permanent, and
   permanent waivers are how a codebase accumulates known holes nobody remembers agreeing to.

### The test for a legitimate waiver

Read the `--risk` line out loud to the person whose name is on it, then ask: **"Are you comfortable
with this being read back to you during the incident?"**

If yes, it is a real waiver. If they flinch, it is a fix.

---

## S0 waivers

S0 checks refuse to be waived by default:

```
ERROR: G1.10 is an S0 BLOCKER. S0 checks are not waivable by default.
If the owner is knowingly accepting this risk, re-run with --accept-blocker-risk.
It will be printed in red on the certificate.
```

With `--accept-blocker-risk`, the waiver is recorded, the certificate still says **NO-GO**, and the
override appears in red permanently. This is deliberate: a launch that proceeds over a known
blocker should carry a document that says so, forever, with a name on it.

**Occasionally this is the right call.** A regulatory deadline; a demo that cannot move; a
competitor's launch. The point is not to prevent it — it is to make sure it is a *decision* rather
than a drift, and that the person making it knows they are making it.

---

## Not-applicable, correctly

N/A is legitimate and common. A CLI tool has no accessibility gate. A static site has no migration
rollback. A single-tenant internal tool has no cross-tenant isolation.

```bash
python lrk.py manual G4.03 --status na \
  --note "Single-tenant by design. One deployment per customer, separate database per deployment, no shared tables. Confirmed by reading the schema: no tenant_id column exists anywhere."
```

**The kit refuses an N/A with no note.** Whatever you write is printed in the report, where anyone
can challenge it.

### The N/A abuse test

Ask: *"If the worst version of this check's failure happened tomorrow, would I feel that marking it
N/A was reasonable?"*

- "No accessibility work because it's an internal tool" — until a colleague with low vision is hired. **Not N/A. It is a waiver.**
- "No load testing because we expect ten users" — reasonable, if the reason includes what happens at a thousand. **Waiver with a stated risk, not N/A.**
- "No app-store review because we do not ship to an app store" — genuinely N/A.

**The distinction:** N/A means the check *cannot apply to this thing*. A waiver means it applies and
you are choosing not to do it. Conflating the two is how a report becomes a lie by omission.

---

## Fixing versus waiving — a rough guide

| Situation | Do this |
|---|---|
| Under an hour to fix | Fix it. Always. The waiver takes ten minutes to write properly. |
| S0, any cost | Fix it, or move the launch date. |
| S1, a day of work, low likelihood | Waive with an expiry, file the ticket. |
| S1, a day of work, high likelihood | Fix it. "Likely" plus "significant harm" is effectively S0. |
| S2, any cost | Waive freely. Record it. Move on. |
| Requires a resource you do not have (a staging env, a second human, a paid tool) | Waive, and name the resource. This is how the resource eventually gets bought. |

---

## Re-verification after a fix

When you fix something a check caught:

1. **Re-run the exact same check.** The kit keeps both records; the report shows the failure and
   then the pass, in order. That sequence is itself excellent evidence — it shows the process
   working.
2. **Re-run anything the fix could have broken.** A fix to the authorization layer means G4 runs
   again, not just the one check that failed.
3. **Add a regression test** so this specific failure cannot return silently.

**A fix that was never re-verified is a change with unknown effect** — and fixes made under launch
pressure are statistically the most dangerous code in any release.

---

## Reporting severity to the user

Never soften it, and never inflate it. The exact shape:

```
NO-GO — 3 blockers.

  G1.10  Secret scan found a live Stripe key in git history (commit 3f2a11, Jan 2026).
         Must be rotated, not just deleted. History is permanent.
  G5.02  Rollback has never been executed. There is a down migration; nobody has run it.
  G10.06 No alert has ever fired. Four alert rules exist; none has been tested end to end.

Everything else: 118 passed, 12 waived, 41 N/A, 4 S1 warnings.

Shortest path to GO: rotate the key (30 min), execute the rollback on staging (1 h),
fire the four alerts (1 h). Roughly half a day.
```

**Always end with the shortest path to GO.** A blocker list without a route is discouraging. A
blocker list with "half a day" next to it is a plan, and it is why people come back and use this
process again.
