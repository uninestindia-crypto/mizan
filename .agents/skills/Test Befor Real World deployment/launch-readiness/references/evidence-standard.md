# The Evidence Standard

What counts as proof, what does not, and why the difference decides whether this whole process is
worth anything.

---

## The three levels, precisely

| Level | How it is earned | What is stored | Can it be faked? |
|---|---|---|---|
| **EXECUTED** | A command ran through `lrk run` | The command, working directory, full stdout, full stderr, exit code, duration in ms, hostname, OS, git commit, git dirty flag, ISO timestamp, and a SHA-256 of the log | Only by running a different command than the one that proves the check — visible to anyone reading the log |
| **ATTACHED** | A file was attached with `lrk attach` | The file itself, copied into the bundle, hashed, with a caption and timestamp | Only by attaching an unrelated file — visible to anyone opening it |
| **ASSERTED** | Someone typed a note | The text, the author, the timestamp | Trivially. This is why it is never sufficient for an S0. |

The report prints the level next to every check, in colour. A human scanning it sees instantly
which claims are backed by machine output and which are backed by somebody's confidence.

---

## Why the hierarchy exists

A readiness review is only useful if it is **harder to fake than to do**. Every checklist in
existence eventually degenerates into a wall of ticks, because ticking is cheap and doing is
expensive. This kit removes the cheap option for the checks that matter:

- An S0 marked pass with only a note is reported as **a blocker**, not a pass.
- The certificate is computed from the data. It cannot be talked into a GO.
- Every evidence file is hashed at capture. `lrk verify` detects any later edit.
- Command records include the git commit, so evidence gathered against an old version is visible as such.

**The result:** the fastest route to a GO certificate is to actually run the checks. That is the
whole design.

---

## What makes a good EXECUTED record

**One check, one command.** A single log containing nine checks proves none of them, because
nobody can tell which part of the output belongs to which claim.

```bash
# Bad — one log, four claims, unreadable
LRK run G1.03 -- npm run lint && npm run typecheck && npm test && npm run build

# Good — four records, each independently readable and independently re-runnable
LRK run G1.04 -- npm run lint
LRK run G1.03 -- npm run typecheck
LRK run G2.01 -- npm test
LRK run G1.01 -- npm run build
```

**Use `--title` when a check needs several commands.** Many checks legitimately need more than one
run; give each a name so the report reads clearly:

```bash
LRK run G5.02 --title "migrate up"                 -- alembic upgrade head
LRK run G5.02 --title "ROLLBACK executed, timed"   -- bash -c 'time alembic downgrade -1'
LRK run G5.02 --title "re-apply to confirm repeatable" -- alembic upgrade head
```

**Make the command self-evidencing.** Prefer commands whose output proves the claim on its own.
`curl -sI` proves a header exists far better than a note saying you looked at it. `time <cmd>`
proves a duration. `git status --porcelain` proves a clean tree.

**Record failures too.** A failing record is valuable evidence: it shows the check was real, the
problem was found, and — when a later record for the same check passes — that the fix was verified.
The report shows both, in order. Do not delete failures.

---

## What makes a good ATTACHED record

**Screenshots are the most persuasive evidence in the report**, because a human can evaluate them
in one second without understanding the stack. Take far more than you think you need.

```bash
LRK attach G3.02 ./shots/orders-empty.png    --caption "Orders list, empty state, new account"
LRK attach G3.02 ./shots/orders-error.png    --caption "Orders list, API 500, error state"
LRK attach G3.02 ./shots/orders-offline.png  --caption "Orders list, offline"
LRK attach G3.02 ./shots/orders-10k.png      --caption "Orders list, 10,000 rows, virtualised"
```

Images are embedded directly in the HTML report as data URIs, so it stays self-contained and
viewable offline. Keep individual images under 3MB.

**Text-shaped attachments** (`.md`, `.txt`, `.log`, `.json`, `.csv`, `.yaml`) are rendered inline
in the report, collapsed. Use them for friction logs, PII inventories, SBOMs, scan output, review
notes, and alert-firing logs.

**Everything else** — videos, PDFs, zips, traces — is stored, hashed, and listed by name and hash.
Playwright videos and traces are worth attaching even though they will not render inline; the hash
proves they existed at capture time and the file travels in the bundle.

**Caption everything.** An uncaptioned screenshot is a picture. A captioned one is evidence:
*"Orders list, API returning 500, error state — user retains their filter selections."*

---

## When ASSERTED is legitimately enough

For S2 and S3 checks, and for genuine N/A determinations. In those cases the note must contain
enough that a stranger could check your work:

```bash
# Weak — unverifiable
LRK manual G9.11 --status na --note "not applicable"

# Strong — a stranger can confirm this in ten seconds
LRK manual G9.11 --status na --note "Web application only, distributed at app.example.com. No iOS, Android, Chrome Web Store, or marketplace distribution planned for v1.0. Confirmed against the cut line in G0.12."
```

**Every N/A needs a reason, and the reason is printed in the report.** The kit enforces this: it
refuses an N/A with no note. Marking things N/A to move faster is the most common way a readiness
review becomes worthless, and the printed reasons are what makes it visible.

---

## Evidence integrity

Every log and attachment is hashed with SHA-256 at the moment it is captured. `lrk report` writes
`MANIFEST.sha256` listing every file and its hash.

```bash
python lrk.py verify
```

Re-hashes everything and reports:
- **verified** — the file matches the hash recorded at capture
- **TAMPERED** — the content changed afterwards
- **MISSING** — the file is gone

The HTML report includes an integrity section. If anything fails, the report says so at the top, in
red, and instructs the reader to treat the whole document as untrustworthy until explained.

This is not about catching malice. It is about catching the ordinary thing: evidence gathered three
weeks ago, against a different commit, quietly overwritten by a later run, and nobody noticing that
the report no longer describes the code that is shipping.

---

## The five ways evidence goes bad

**1. Stale.** Captured against an older commit. Every record stores the commit SHA; check that the
S0 evidence matches the release commit. Re-run anything older than the last significant change.

**2. Wrong environment.** A security check run against a development server with `DEBUG=true`
proves the opposite of what you wanted. Record which environment each probe hit; for G4, G6, G7,
and G11 it must be production-like.

**3. Wrong scale.** A migration timed against 40 rows. A load test against an empty database.
Always state the data volume in the title or note.

**4. Partial.** The command was interrupted, timed out, or only covered part of the surface. Read
the log tail; the kit records timeouts explicitly.

**5. Circular.** The test asserts the behaviour of the code it is testing, using the same wrong
assumption. This is what G2.06 sabotage exists to catch, and nothing else catches it.

---

## The bundle

```bash
python lrk.py bundle
```

Produces `launch-evidence-<name>-<date>.zip` containing:

```
launch-evidence/
  state.json                  every result, record, waiver, and audit entry
  CERTIFICATE.md              the GO / NO-GO with the signature block
  report/
    LAUNCH-REPORT.html        self-contained; open in any browser, offline
    MANIFEST.sha256           hash of every file
  evidence/<CHECK_ID>/*.log   raw command output, exactly as emitted
  attachments/<CHECK_ID>/*    screenshots, scans, documents
```

This is what you hand to: a customer's security reviewer, a compliance auditor, an investor's
technical diligence, a new engineer asking how this is tested, or yourself in six months.

It is also, in most organisations, the change-control evidence that a formal process asks for and
nobody has — which makes this bundle worth producing even for launches nobody demanded it for.

---

## The honesty clause

If a check could not be run — no staging environment, no load-testing tool, no second human for
Customer Zero, no time — the correct action is:

1. Leave it `todo`, or mark it `fail` with a note explaining what was missing.
2. Say so explicitly in the NOT TESTED line of your report to the user.
3. Let the certificate say NO-GO if it is an S0.

**Never invent a result.** An honest gap is a decision the owner can make: they can accept the risk,
delay, or find the resource. A fabricated pass removes their ability to decide at all, and they
will not discover it until the thing you did not test is the thing that breaks.
