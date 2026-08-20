---
name: launch-readiness
description: >-
  The pre-launch certification process big technology companies run before software touches real
  users — Google's Production Readiness Review, Amazon's Operational Readiness Review, Microsoft's
  ship room — turned into 216 numbered checks across 13 gates, an evidence engine that records raw
  proof, and a GO/NO-GO certificate computed from data rather than opinion. Load this when the code
  is ALREADY BUILT and the question is whether it may ship. Triggers on: "is it ready", "production
  ready", "ready for real users", "not a beta", "launch checklist", "pre-launch", "release
  readiness", "go live", "go/no-go", "ship it", "v1.0", "GA", "general availability", "cutover",
  "production readiness review", "PRR", "ORR", "operational readiness", "launch audit", "release
  audit", "certify this release", "test everything before deploying", "what could go wrong in
  production", "sign off on this release", "QA before launch", "hardening pass", "final check
  before deploy". Produces a self-contained HTML report, a hashed evidence bundle, and a signed
  certificate a human can open and check. Codebase-agnostic and stack-agnostic. If you are about to
  tell someone their software is ready to launch and you cannot hand them a file that proves it,
  you needed this skill and did not load it.
---

# Launch Readiness

The code is written. Somebody is about to point real people at it. This skill decides whether that
is allowed, and produces the paperwork either way.

**It is not a discussion. It is 216 checks, a machine that records what actually ran, and a verdict
computed from the recording.**

---

## The one law

> **A claim without recorded evidence is not a pass. It is a lie with good intentions.**

Every other rule in this file is a consequence of that one. You may not write "tests pass" — you
run the tests through the recorder and the raw output goes in the bundle. You may not write
"rollback works" — you execute the rollback, timed, and the timing goes in the bundle. You may not
write "no security issues" — you run the scan and attach it.

Three levels of proof exist. The kit labels every check with the one it actually earned:

| Level | Earned by | Good enough for |
|---|---|---|
| **EXECUTED** | A command ran through `lrk run`; stdout, stderr, exit code, duration and a SHA-256 hash are stored | Anything |
| **ATTACHED** | A file was attached: screenshot, scan output, export, signed document | Manual checks |
| **ASSERTED** | Somebody typed that it was fine | S2 and S3 only — **never an S0** |

An S0 check marked pass with only an assertion is reported as a **blocker**, and the certificate
says NO-GO. This is not adjustable. It is the entire point.

---

## What this is, and what it is not

| | |
|---|---|
| **This skill** | The final exam. The code exists; prove it is safe to release. |
| **`founder-mode`** | The whole company process from idea to postmortem. Load that to *build*. |

They compose: `founder-mode` phases P5 through P8 are exactly where this runs. If the user is still
designing or building, stop and load `founder-mode` instead. If they are asking *"can we ship?"* —
you are in the right place.

If the project has a `CLAUDE.md`, `AGENTS.md`, or its own design/review skill, **those outrank this
file** on anything they cover. This supplies the skeleton; the project supplies the law.

---

## RUN THIS — the mechanical loop

Do these in order. Do not improvise. Every step says what to type, what you should see, and what to
do when it goes wrong.

### Step 0 — Locate the kit and prove it works

```bash
python "<SKILL_DIR>/scripts/lrk.py" selftest
```

`<SKILL_DIR>` is the directory this file is in. Expect `SELF-TEST PASSED: 11/11`.
If Python is missing, stop and tell the user: *"This needs Python 3.8 or newer on PATH."*
Nothing else in this skill works until this line prints.

### Step 1 — Set the scene, in the project's own directory

```bash
cd <PROJECT_ROOT>
python "<SKILL_DIR>/scripts/lrk.py" detect
```

Read the output. It lists the stack it found and the commands it *guesses*. **Guesses are not
facts** — Step 3 makes you prove each one.

### Step 2 — Initialise with the correct profile

The profile decides which of the 216 checks apply. Getting it wrong is the most common way this
process produces a worthless report. Ask the user, or determine from the code, and pick **every**
tag that is true:

| Tag | Include it when |
|---|---|
| `web` | It serves HTTP to a browser |
| `api` | Another program calls it |
| `ui` | A human looks at it |
| `db` | It stores data in a database |
| `auth` | It has login or any permission logic |
| `multitenant` | More than one customer's data shares the system |
| `payments` | It touches money, price, tax, credit, or quota |
| `mobile` | It ships an app binary |
| `cli` | It ships a command-line tool |
| `lib` | Other developers import it |
| `queue` | It has background jobs, workers, or cron |
| `thirdparty` | It calls a service you do not control |
| `upload` | Users send it files |
| `i18n` | More than one language or locale |
| `store` | It goes through an app store |
| `pii` | It stores data about identifiable people |
| `cloud` | You deploy and operate the infrastructure |

```bash
python "<SKILL_DIR>/scripts/lrk.py" init \
  --name "Acme Checkout" --version "1.0.0" --owner "Name of the human who signs" \
  --profile web,api,db,auth,pii,payments,cloud
```

> **When in doubt, add the tag.** An extra check costs minutes. A missing one costs the launch.

### Step 3 — Walk the gates in order, G0 first

Read `references/gate-G0.md`, then do exactly what it says. Then `gate-G1.md`. Then G2. In order.

**Never skip a gate because it "looks fine".** Gates are ordered by dependency: you cannot trust a
test result (G2) until the build is honest (G1), and you cannot trust the build until you know
which commands are real (G0).

For every check, the pattern is always one of these three:

```bash
# Something a machine can prove — the default, always prefer this:
python "<SKILL_DIR>/scripts/lrk.py" run G1.03 -- npm run typecheck

# Something only a human can see — must carry a file:
python "<SKILL_DIR>/scripts/lrk.py" manual G8.13 --status pass \
  --by "Priya" --note "Empty account, 38 min, finished checkout unaided. 4 friction points logged." \
  --attach ./friction-log.md

# Something that genuinely does not apply — must carry a reason:
python "<SKILL_DIR>/scripts/lrk.py" manual G9.11 --status na \
  --note "Web only. Not distributed through any app store."
```

Exit code 1 from `run` means the check FAILED. That is normal and healthy. Record it, fix the code,
run it again — the kit keeps both records, and the report shows the history.

### Step 4 — Check where you are, as often as you like

```bash
python "<SKILL_DIR>/scripts/lrk.py" status --verbose
python "<SKILL_DIR>/scripts/lrk.py" checklist --todo
```

### Step 5 — Produce the proof

```bash
python "<SKILL_DIR>/scripts/lrk.py" report
python "<SKILL_DIR>/scripts/lrk.py" certify
python "<SKILL_DIR>/scripts/lrk.py" verify
python "<SKILL_DIR>/scripts/lrk.py" bundle
```

That writes, inside the project at `.launch/`:

| File | What the human does with it |
|---|---|
| `report/LAUNCH-REPORT.html` | Opens it in a browser. Self-contained: every raw log, every screenshot, every hash, colour-coded, works offline. **This is the deliverable.** |
| `CERTIFICATE.md` | The GO / NO-GO with a signature block. |
| `report/MANIFEST.sha256` | Hash of every evidence file. |
| `evidence/` | The raw logs, exactly as the commands emitted them. |
| `launch-evidence-<name>-<date>.zip` | The whole thing, to hand to a reviewer, auditor, or customer. |

### Step 6 — Report to the user in this exact shape

```
[LAUNCH READINESS · <project> v<version> · <GO | GO WITH CONDITIONS | NO-GO>]

VERDICT      the verdict, and the one-sentence reason
BLOCKERS     every S0 that is failing, untested, or asserted — with its ID
WARNINGS     count, and the three worst
PROOF        executed N · attached N · asserted N   (out of M applicable)
NOT TESTED   what you did not run, and why — say it plainly
EVIDENCE     absolute path to LAUNCH-REPORT.html
```

Then hand them the report file. Do not summarise the report instead of sending it.

---

## The 13 gates

Each has its own reference file with every check spelled out: what to do, what you should see, what
it means when you do not, and how the check gets faked.

| Gate | Name | Checks | Reference | The question it answers |
|---|---|---|---|---|
| **G0** | Inventory & Command Map | 12 | `references/gate-G0.md` | What is this, and which commands are real? |
| **G1** | Build & Static Integrity | 18 | `references/gate-G1.md` | Does it build clean, and is anything in there that shouldn't be? |
| **G2** | Test Truth | 18 | `references/gate-G2.md` | Would the tests actually catch a regression? |
| **G3** | Functional Correctness & States | 16 | `references/gate-G3.md` | Does it work, including the eight ways it goes wrong? |
| **G4** | Security | 28 | `references/gate-G4.md` | Can a stranger read, write, or break what isn't theirs? |
| **G5** | Data & Migration Safety | 16 | `references/gate-G5.md` | Does data survive the deploy, the rollback, and the disaster? |
| **G6** | Performance & Capacity | 15 | `references/gate-G6.md` | Is it fast enough at real volume, and where does it break? |
| **G7** | Reliability & Failure Injection | 15 | `references/gate-G7.md` | What happens when each dependency dies? |
| **G8** | UX, Accessibility & Devices | 16 | `references/gate-G8.md` | Can a real person on a real device finish the job? |
| **G9** | Privacy, Legal & Compliance | 16 | `references/gate-G9.md` | Does shipping this create a liability? |
| **G10** | Operability | 18 | `references/gate-G10.md` | At 3am, who is woken and what do they do? |
| **G11** | Release Mechanics | 16 | `references/gate-G11.md` | Is the deploy rehearsed and the rollback timed? |
| **G12** | Launch & 72-Hour Watch | 12 | `references/gate-G12.md` | Was the rollout staged, watched, and learned from? |

**216 checks.** Your profile decides how many apply — a CLI library might have 90, a multi-tenant
payments platform close to all of them.

---

## Severity — what blocks and what does not

| | Meaning | Effect on the verdict |
|---|---|---|
| **S0** | Blocker | Must be `pass` with EXECUTED or ATTACHED proof, or `na` with a reason. Anything else → **NO-GO**. |
| **S1** | Major | Must be fixed or waived in writing by a named human who states the risk. |
| **S2** | Minor | Fix, or record a dated follow-up. |
| **S3** | Advisory | Record the answer. No launch impact. |

Waivers are a first-class, honest outcome — a shortcut with a name attached to it:

```bash
python "<SKILL_DIR>/scripts/lrk.py" waive G6.12 \
  --by "R. Patel, CTO" \
  --reason "Pre-revenue, single region, fewer than 200 expected users in month one" \
  --risk "An unexpected traffic spike produces a surprise cloud bill; no cap configured" \
  --expires 2026-11-01
```

S0 waivers require `--accept-blocker-risk` and are printed in red on the certificate forever.
Full policy: `references/severity-and-waivers.md`.

---

## Depth — do not run a full PRR on a typo

| Depth | When | Gates | Roughly |
|---|---|---|---|
| **D0 Patch** | Copy change, dependency bump, one-line fix | G1, G2, plus the gate the change touches | 15 min |
| **D1 Feature** | A feature going out to existing users | G1–G5, G8, G11 | 2–4 hours |
| **D2 Release** | A versioned release; new surface; schema change | G0–G12, S0 and S1 everywhere | 1–3 days |
| **D3 Launch** | First public launch, GA, new product, migration, region | Everything, nothing waived without the owner | 1–2 weeks |
| **D4 Critical** | Money movement, health/safety, identity, irreversible data | Everything, plus a second independent pass by a different actor | 2–4 weeks |

State the depth out loud in your first message: *"Running D2."* When you cannot decide between two,
**take the higher one**. Detail: `references/depth-and-scoping.md`.

---

## The rules you will be tempted to break

1. **Do not mark a check pass because the code looks right.** Reading code is not evidence. Run it.
2. **Do not batch.** One check, one command, one record. A single log containing nine checks proves
   none of them.
3. **Do not skip G0.** Every wasted day in this process traces back to running the wrong command
   for three hours.
4. **Do not paraphrase output.** The recorder stores it verbatim; your summary is not the evidence.
5. **Do not fix and forget to re-run.** A fix that was never re-verified is a change with unknown
   effect. Re-run the check.
6. **Do not mark N/A to move faster.** Every N/A needs a reason a stranger would accept, and the
   report prints it.
7. **Do not report GO because the user wants GO.** The kit computes the verdict; you relay it. If
   they want to ship anyway, that is their call to make in writing — `waive` exists for exactly
   that, and it puts their name on it.
8. **Do not invent evidence. Ever.** If a check could not be run, mark it `todo` and say so in the
   NOT TESTED line. An honest gap is recoverable; a fabricated pass is how people get hurt.

---

## When the project has no tests, no CI, and no staging

This is common and it is not a reason to stop. It changes what the honest answer is.

1. Run G0 and G1 anyway — they need nothing but the source.
2. G2.01 fails. Record the failure. **Do not skip it and do not mark it N/A** — "there is no test
   suite" is a finding, and it is the most important one in the report.
3. Continue through every gate that can be checked by reading, running, or probing the app.
4. The verdict will be NO-GO with a long blocker list. That is the correct, useful answer.
5. Then tell the user the shortest path to GO: usually *"write end-to-end tests for the two or
   three money paths, and rehearse a rollback."* Not "write 400 unit tests."

A NO-GO report on day one is the most valuable artifact this skill produces. It is a map.

---

## Reference files

| File | Load it when |
|---|---|
| `references/gate-G0.md` … `gate-G12.md` | You are executing that gate. Read the file before starting it. |
| `references/stack-playbooks.md` | You need the real command for Node, Python, Go, Rust, Java, .NET, Ruby, PHP, Flutter, React Native, Next.js, Django, Rails, or a static site |
| `references/evidence-standard.md` | Deciding what counts as proof for a given check |
| `references/severity-and-waivers.md` | Something is failing and the user wants to ship anyway |
| `references/depth-and-scoping.md` | Choosing D0–D4; compressing without breaking |
| `references/failure-injection.md` | Running G7 — exactly how to break each dependency on purpose |
| `references/antipatterns.md` | A report looks too green, or you suspect a check was faked |
| `references/quick-reference.md` | The one-page command card |
| `templates/` | Runbook, friction log, waiver, go/no-go, postmortem, support brief |

---

## First response checklist

Before you type anything else, confirm you have done all four:

- [ ] Declared the depth (D0–D4)
- [ ] Run `selftest` and seen 11/11
- [ ] Run `init` with a profile you can defend
- [ ] Told the user how many checks apply and how many are S0 blockers

Then start G0.
