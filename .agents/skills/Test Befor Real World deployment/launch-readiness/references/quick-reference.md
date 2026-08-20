# Quick Reference — one page

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`

---

## Commands

```bash
LRK selftest                              # prove the kit works (11 assertions) — do this first
LRK detect                                # what stack is this, what commands does it suggest
LRK init --name "App" --version 1.0.0 --owner "Name" --profile web,api,db,auth,pii,cloud
LRK profile                               # show tags; --set to change

LRK run G1.03 -- npm run typecheck        # record a command as evidence  (exit 0 = pass)
LRK run G2.06 --expect-fail -- npm test   # non-zero exit = pass (sabotage / negative tests)
LRK run G6.08 --timeout 5400 -- k6 run x  # long-running (default timeout 3600s)
LRK run G1.04 --record-only -- npm run lint   # capture output, do not set a status
LRK run G5.02 --title "rollback timed" -- bash -c 'time <cmd>'   # name it when a check needs several

LRK manual G0.09 --status pass --note "..." [--by NAME] [--attach FILE]
LRK manual G9.11 --status na   --note "why it does not apply"    # note is mandatory
LRK attach G3.02 ./shot.png --caption "Orders list, empty state"
LRK waive G6.12 --by "Name, Role" --reason "..." --risk "..." --expires 2026-11-01

LRK status [--gate G4] [--verbose]        # progress bars + current verdict
LRK checklist [--gate G4] [--todo] [--md] # every check and its state
LRK verify                                # re-hash all evidence, detect tampering
LRK report                                # -> .launch/report/LAUNCH-REPORT.html
LRK certify                               # -> .launch/CERTIFICATE.md  (exit 1 on NO-GO)
LRK bundle                                # report + zip of everything
```

---

## Profile tags

`web` `api` `ui` `db` `auth` `multitenant` `payments` `mobile` `cli` `lib` `queue` `thirdparty`
`upload` `i18n` `store` `pii` `cloud`

**When in doubt, add the tag.** An extra check costs minutes; a missing one costs the launch.

---

## The 13 gates

| | Gate | Checks | The question |
|---|---|---|---|
| G0 | Inventory & Command Map | 12 | What is this, and which commands are real? |
| G1 | Build & Static Integrity | 18 | Builds clean? Anything in there that shouldn't be? |
| G2 | Test Truth | 18 | Would the tests catch a regression? |
| G3 | Functional Correctness & States | 16 | Works, including the eight ways it goes wrong? |
| G4 | Security | 28 | Can a stranger read/write/break what isn't theirs? |
| G5 | Data & Migration Safety | 16 | Survives the deploy, the rollback, the disaster? |
| G6 | Performance & Capacity | 15 | Fast enough at real volume? Where does it break? |
| G7 | Reliability & Failure Injection | 15 | What happens when each dependency dies? |
| G8 | UX, Accessibility & Devices | 16 | Can a real person on a real device finish? |
| G9 | Privacy, Legal & Compliance | 16 | Does shipping create a liability? |
| G10 | Operability | 18 | At 3am, who is woken and what do they do? |
| G11 | Release Mechanics | 16 | Deploy rehearsed, rollback timed? |
| G12 | Launch & 72-Hour Watch | 12 | Staged, watched, learned from? |

---

## Severity

| | | Verdict effect |
|---|---|---|
| **S0** | Blocker | Must pass with EXECUTED or ATTACHED proof, or be N/A → else **NO-GO** |
| **S1** | Major | Fix or waive in writing → else **GO WITH CONDITIONS** |
| **S2** | Minor | Fix or record a follow-up |
| **S3** | Advisory | Record the answer |

**NOT TESTED counts as FAILED.** The burden of proof is on the claim.

---

## Proof levels

| | Earned by | Enough for |
|---|---|---|
| **EXECUTED** | `LRK run` — command, output, exit code, hash | Anything |
| **ATTACHED** | `LRK attach` — a real file | Manual checks |
| **ASSERTED** | A written note | S2 and S3 only. **Never an S0.** |

---

## Depth

| | When | Gates |
|---|---|---|
| **D0** | Typo, dep bump, one-liner | G1, G2, + the affected gate |
| **D1** | Feature for existing users | G1–G5, G8, G11 — S0 only |
| **D2** | Versioned release, schema change | All gates, S0 + S1 |
| **D3** | Public launch, GA, migration | Everything, uncompressed |
| **D4** | Money, health, identity, irreversible | Everything, twice, second actor |

**Torn between two? Take the higher one.**

---

## The twelve checks that catch the most, in order of value per minute

| Order | Check | Min | Prevents |
|---|---|---|---|
| 1 | **G1.10** secret scan, full history | 2 | A permanent credential leak |
| 2 | **G1.17** nothing secret committed | 1 | The same |
| 3 | **G2.02** full suite from clean state | 10 | Shipping a known-broken build |
| 4 | **G1.12** dependency vulnerabilities | 3 | A known RCE |
| 5 | **G11.07** rollback rehearsed and timed | 20 | Being unable to undo |
| 6 | **G4.01–G4.06** access control | 45 | The data breach |
| 7 | **G5.02** migration rollback executed | 20 | Unrecoverable data damage |
| 8 | **G1.11** no sandbox/localhost in prod | 3 | Payments that silently do nothing |
| 9 | **G3.02** the nine states | 40 | The product appearing broken |
| 10 | **G10.06** fire one alert | 15 | Finding out from a customer |
| 11 | **G11.11** env contract in the target | 20 | The deploy failing on a missing variable |
| 12 | **G6.02** latency at realistic volume | 20 | The launch-day slowdown |

---

## The seven "executed, not written" checks

These are the ones teams mark done without doing. Each needs a recorded run with a duration:

- **G2.06** — three functions sabotaged, tests went red, code restored
- **G5.02** — migration rollback **executed**
- **G5.03** — migration rehearsed at production scale, lock duration measured
- **G5.05** — backup **restored** into a scratch environment and verified
- **G10.06** — every alert **fired** and confirmed to reach a human
- **G11.07** — rollback rehearsed on production-like, **timed in seconds**
- **G11.11** — environment contract verified **in the target**, not on your laptop

---

## Report shape to the user

```
[LAUNCH READINESS · <project> v<version> · <GO | GO WITH CONDITIONS | NO-GO>]

VERDICT      the verdict and the one-sentence reason
BLOCKERS     every S0 failing, untested, or asserted — with its ID
WARNINGS     count, and the three worst
PROOF        executed N · attached N · asserted N   (of M applicable)
NOT TESTED   what you did not run, and why — plainly
EVIDENCE     absolute path to LAUNCH-REPORT.html
```

Then **send the file**. Do not summarise the report instead of handing it over.

---

## Outputs

```
<project>/.launch/
  CERTIFICATE.md                  GO / NO-GO with a signature block
  state.json                      every result, record, waiver, audit entry
  report/LAUNCH-REPORT.html       self-contained; open in a browser, works offline
  report/MANIFEST.sha256          hash of every evidence file
  evidence/<CHECK_ID>/*.log       raw command output, verbatim
  attachments/<CHECK_ID>/*        screenshots, scans, documents
<project>/launch-evidence-<name>-<date>.zip
```

---

## Rules you will be tempted to break

1. Code that looks right is not evidence. **Run it.**
2. One check, one command, one record. Never batch.
3. Never skip G0. Everything downstream depends on the command map being real.
4. Never paraphrase output — the recorder stores it verbatim.
5. Fixed something? **Re-run the check.**
6. Every N/A needs a reason a stranger would accept.
7. The kit computes the verdict. You relay it.
8. **Never invent evidence.** `todo` plus an honest sentence beats a fabricated pass, always.
