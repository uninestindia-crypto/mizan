# 05 — Hardening: The Twelve Attack Families

This is the Red Team's ammunition and the P5 work list. Work it **systematically**, family by
family. Free-associating about what might break produces the failures you already imagined; the
catalog produces the ones you did not.

**How to use it.** For each family, walk the probes against the target. Every probe is a question
with a yes/no answer and a reproduction. Record findings as:

```
FINDING  <one line>
FAMILY   <which of the twelve>
REPRO    <exact, copy-pasteable input or sequence>
OBSERVED <what actually happened — the wrong behavior>
EXPECTED <what should have happened>
BLAST    <who is affected, how badly, how many>
SEVERITY Blocker | Major | Minor
```

**Severity rubric — apply it strictly, it is what makes the gate meaningful:**

| Severity | Definition |
|---|---|
| **Blocker** | Data loss, data leak across users/tenants, wrong money, security bypass, silent corruption, unrecoverable state, or the critical path broken. **Blocks the gate. Always.** |
| **Major** | A real user hits it on a plausible path; workaround is painful or non-obvious; recovery requires support. Must be fixed or founder-accepted in writing. |
| **Minor** | Cosmetic, rare, or self-recovering with an obvious workaround. Log it; fix if cheap. |

**The tie-breaker:** if a failure is *silent* — wrong answer with no error, partial write with no
alarm, a job that vanishes — escalate it one level. Loud failures get fixed by users reporting
them. Silent failures get discovered by an auditor, a customer, or a regulator, months later.

## Contents

- [Families 1–4: inputs, identity, concurrency, failures](#family-1--input-boundaries)
- [Families 5–8: lifecycle, scale, money, integrity](#family-5--state-machine-and-lifecycle)
- [Families 9–12: security, humans, operations, assumptions](#family-9--security-surface)
- [Hardening report](#the-hardening-report)

---

## Family 1 — Input boundaries

*The value is technically valid and completely unreasonable.*

For every field, parameter, argument, and body the system accepts:

- Empty string; whitespace only; a single space
- `null`, `undefined`, missing key, key present with no value
- Zero; negative; `-0`; the maximum for the type; maximum + 1; `NaN`; `Infinity`
- A number where a string is expected, and the reverse; a string that looks like a number
  (`"007"`, `"1e5"`, `"0x10"`)
- Array where a scalar is expected; object where an array is expected
- 10,000 characters in a name field; 10MB in a text field
- Unicode: emoji (including multi-codepoint families), RTL text, combining accents, zero-width
  characters, homoglyphs, and the Turkish dotless ı in anything that lowercases
- Leading/trailing whitespace that should be trimmed but is not (the #1 cause of "my login
  doesn't work")
- Boolean-ish strings: `"false"`, `"0"`, `""` — all of which are truthy in most languages
- Deeply nested JSON (100 levels); an array of 1,000,000 items
- A value that is valid for the type and invalid for the domain: a birth date in 3024, a quantity
  of 10^9, a percentage of 500

**The question:** is it rejected clearly at the boundary, or does it travel inward and cause damage
somewhere unrelated?

---

## Family 2 — Identity, authorization, and tenancy

*The most damaging family. Assume every user is trying to see someone else's data.*

- Every protected route, unauthenticated
- Every role against every resource × action — build the matrix, test the matrix
- **Another tenant's object by direct ID.** Then by ID in a nested field. Then in a filter. Then in
  a sort key. Then in an export.
- **Cross-tenant write**, tested separately from read — updating a foreign object, or setting a
  foreign ID as a relation on your own object
- Enumerate IDs: sequential integers, and UUIDs harvested from anywhere they leak (URLs, HTML,
  error messages, webhook payloads, analytics)
- Expired token; revoked token; token from a deleted user; token from a user whose role was
  downgraded a second ago; token signed with `alg: none` or a weak key
- Privilege escalation: self-assign a role, change own tenant, invite yourself as admin, modify
  another user's record via a field you can set on your own
- **Indirect leaks**: a count that includes invisible items; a search that matches on a hidden
  field; an error message that reveals existence ("no such invoice" vs "not authorized"); an
  autocomplete that suggests other tenants' names; an export that ignores the filter
- Session fixation, session not invalidated on logout/password change, concurrent sessions
- Server-side check absent because the UI hides the button (check the API directly, always)

**The question:** is the authorization check on the *server*, on *every* path to the data,
including the paths nobody remembered?

---

## Family 3 — Concurrency and ordering

*Two things happen at the same time. The universe does not respect your assumptions.*

- The same mutation twice, simultaneously (double-click, double-submit, retry storm)
- Two users editing the same record: last-write-wins silently destroying the first write
- Read-then-write without a lock or version: the classic lost update
- Check-then-act: "is there stock?" → yes → two buyers → negative stock
- Requests arriving out of order (update before create; delete before update)
- A webhook arriving before the API call that caused it has committed
- Retry arriving *after* the original succeeded (idempotency)
- A job re-delivered while the first attempt is still running
- Two instances of a scheduled task firing on two servers
- Cache written by request A, invalidated by B, re-populated stale by C
- Migration running while the application is serving traffic
- A transaction held open across a network call to a third party

**The question:** for every mutating path, what happens when it is called twice at once? If you
have not tested it, the answer is "we don't know," and the correct severity for "we don't know" on
a money path is Blocker.

---

## Family 4 — Failure injection

*Everything you depend on will be down, slow, or lying. Usually at the worst moment.*

- Database: unreachable; connection pool exhausted; slow query; killed mid-transaction; disk full;
  read replica lagging behind the primary
- Third party: timeout; connection refused; DNS failure; 500; 502; 429 with and without
  `Retry-After`; HTML error page instead of JSON; a truncated response body; TLS failure; expired
  credentials
- Queue/broker: unavailable; full; message lost; message duplicated; consumer crash mid-processing
- Cache: unavailable (does the app work at all?); returning stale data; returning *someone else's*
  data due to a key collision
- Filesystem/storage: full; permission denied; file disappeared between check and read; upload
  interrupted at 50%
- Network: lost mid-request; lost mid-upload; captive portal returning HTTP 200 with a login page
- The process: SIGKILL mid-write; restarted during a migration; OOM-killed under load
- Time: clock jumps forward; clock jumps backward; NTP correction during a timed operation

**The question, for each:** does it fail **safely** (no corruption, no half-committed state),
**visibly** (a human or a monitor learns about it), and **recoverably** (retry works, no manual
surgery)? All three, or it is a finding.

---

## Family 5 — State machine and lifecycle

*The object goes through states. Try every illegal transition.*

- Every transition not in the diagram: cancel a completed order, pay a cancelled invoice, award a
  closed RFQ, ship a refunded item, approve an already-approved request
- Skip a step: go from step 1 to step 4 by URL, by API, by back button
- Repeat a terminal step: submit twice, approve twice, refund twice
- Act on a deleted/archived parent: add a child to a deleted parent; the parent deleted mid-flow
- Reverse: undo something that has downstream effects that cannot be undone
- Simultaneous transitions from two actors (see Family 3)
- Long-lived flows: a form open for 8 hours, then submitted; a token that expired mid-wizard; a
  price that changed between "add to cart" and "pay"
- Orphans: child records whose parent is gone; references to deleted users; a job referencing a
  deleted entity

**The question:** is the state machine enforced in the *data layer*, or only by the UI not showing
the button?

---

## Family 6 — Scale and volume

*It works with 10 rows. Production has 10 million.*

- A list endpoint with 1M rows: does it paginate, or try to load them all?
- N+1 queries — instrument and count queries per request, do not eyeball it
- A single user with 100,000 child records
- A payload at the maximum allowed size, and a response that exceeds a proxy's buffer
- An export of everything: does it stream, or buffer into memory and die?
- Search with a query matching every row
- A migration on a production-scale table — timed, with the lock duration measured
- Memory over a long-running process: soak it and watch for leaks
- A queue with a 100,000-message backlog: drain rate, and does it recover?
- Concurrent users at 10× the expected peak

**The question:** what is the actual production volume, and has this been run at that volume? "It
should scale" is not a test result.

---

## Family 7 — Money, counting, and correctness

*Wrong numbers are worse than crashes. A crash gets noticed.*

- Floating-point money anywhere → **Blocker**, no discussion
- Rounding: half-up vs half-even vs truncation, applied consistently; rounding applied once, not
  compounded at each step
- Sum of the parts vs. the whole: line items vs. order total, allocations vs. the pool, splits that
  must total 100%
- Tax, discount, and fee **ordering** — different orders give different totals; which is correct is
  a product decision that must be written down
- Currency: mixed currencies; conversion rate at time-of-transaction vs. time-of-display; a
  historical record re-displaying with today's rate (silently wrong forever)
- Negative quantities, zero-value orders, 100% discounts, refunds exceeding the payment
- Idempotency on every charge, refund, and payout
- Double-entry integrity: does every credit have a debit? Assert it as a test on the ledger.
- Reconciliation: recompute the balance from the transaction log and compare to the stored balance
- Counters: increments lost under concurrency; a count that disagrees with the list it counts

**The question:** if a regulator or an accountant recomputed this from the raw records, would they
get the same number? Write that recomputation as a test.

---

## Family 8 — Data integrity and durability

*What survives, and what silently doesn't.*

- Unicode round-trip through every layer: form → API → DB → export → re-import
- Encoding: UTF-8 vs. Latin-1; a BOM in a CSV; CRLF vs LF; Excel mangling a leading zero or a long
  number
- Truncation: a field longer than the column silently cut (many DBs do this by default)
- Timezone stored vs. displayed vs. computed (see the time cases in `04-test-matrix.md`)
- Soft delete: does the deleted record still appear in a count, a search, an export, a join, a
  unique constraint?
- Cascade: deleting a parent — what happens to the children, and was that intended?
- **Backup and restore**: take a backup, restore it *to a different machine*, and verify the data.
  An untested backup is not a backup.
- Migration data loss: does the migration drop a column that still has meaning? Was the data
  archived first?
- Audit trail: is the record of who did what immutable, complete, and actually written on every
  path?

---

## Family 9 — Security surface

Run the project's strongest available security review capability in addition to this list. Do not
assume a particular slash command exists.

- Injection: SQL, NoSQL, command, LDAP, template, and the ORM's raw-query escape hatch
- XSS: stored, reflected, and DOM-based; user content rendered as HTML anywhere; markdown that
  allows raw HTML; an SVG upload
- SSRF: any URL the user supplies that the server fetches — including webhook targets, image
  imports, and OAuth redirect URIs
- Path traversal in file names, download endpoints, and archive extraction
- Deserialization of user-supplied objects; prototype pollution
- Secrets: in code, in logs, in error responses, in client bundles, in git history, in build
  artifacts
- Dependencies: known CVEs, unmaintained packages, install scripts, typosquatted names
- Transport: HTTPS everywhere, HSTS, secure/httpOnly/SameSite cookies, CORS actually restricted
- Rate limiting on auth, on expensive endpoints, and on anything that sends email or SMS
- Enumeration: does "email already registered" tell an attacker who your users are?
- Password/session handling: hashing algorithm, reset token lifetime and single use, session
  invalidation on password change
- Uploads: content-type verified by magic bytes, served from a separate origin, never executable

---

## Family 10 — The human path

*What a real person does that no test suite does.*

- Double-click every button that submits
- Press back, forward, and refresh at every step of every multi-step flow
- Open the same flow in two tabs and act in both
- Close the laptop mid-flow, return in the morning, continue
- Paste formatted text from Word, with smart quotes and non-breaking spaces
- Paste a value with a trailing newline, or a phone number with spaces and a `+`
- Deny the browser permission (camera, location, notifications) and try to continue
- Disable JavaScript; block third-party cookies; use an ad blocker; browse in private mode
- Slow 3G; a network that drops for 10 seconds mid-flow
- 200% browser zoom; a 320px screen; a screen reader
- Do the steps in the wrong order, on purpose
- Try to accomplish the goal a *different way* than designed — via search, via a link, via the URL
- Give up halfway and start over: is the partial state cleaned up or does it block the retry?

---

## Family 11 — Operability

*Can a human understand and fix this at 3am, without the person who built it?*

- Every error a user can see: does it say what happened **and what to do next**? "An error
  occurred" is a finding.
- Every error the system logs: does it contain enough context to identify the user, tenant,
  request, and cause — without leaking secrets or personal data?
- Correlation: can one request be traced across services from a single ID?
- **Fire every alert deliberately.** Confirm it reaches a human. An alert that has never fired is
  an alert that may not work.
- Are there alerts for *silent* failures — a job that stops running, a queue that stops draining, a
  metric that goes to zero? Absence-of-signal is the hardest and most important alarm.
- Is there a way to answer "did this specific user's action succeed?" without a shell on the
  server?
- Feature flag: can it be turned off *without a deploy*? Has that been tested?
- Runbook: could someone who did not build this execute the recovery?
- Log volume and cost at production scale
- Can you tell the difference between "no traffic" and "monitoring broken"?

---

## Family 12 — Assumption archaeology

*The findings nobody else gets, because they require reading what the author believed.*

Go through the diff and the design and list every place someone assumed something. Then attack the
assumption:

- Every comment that says "should never happen" → make it happen
- Every non-null assertion, `!`, `as`, `unwrap()`, `# type: ignore`, or silenced warning → provide
  the value it insists cannot exist
- Every `catch` that swallows → what error is it hiding, and what does the system do afterwards?
- Every default value → what if the real value is legitimately different?
- Every "this list will be small" → make it 100,000
- Every "this only runs once" → run it twice
- Every "the client always sends X" → do not send X
- Every hardcoded constant, limit, or timeout → what happens at the limit, and who chose it?
- Every ordering assumption → reverse it
- Every "we'll add that later" in a comment → is later before or after launch? Ask now.
- Every place a test was skipped, mocked out, or marked TODO → why, and what is it hiding?

**This family finds the bugs no checklist can, because it targets the specific things this specific
author believed.** It is the highest-yield family on mature codebases, and it is the one that
requires actually reading the code rather than probing the interface.

---

## The hardening report

At the end of P5, produce:

```
HARDENING REPORT — <scope>

COVERAGE      families run: 12/12 | probes: <n> | targets: <list>
BLOCKERS      <n> — each with repro, blast radius, and fix status
MAJORS        <n> — each with disposition (fixed + test | founder-accepted)
MINORS        <n> — logged
NOT PROBED    what you could not test and why  ← this section is mandatory and is
              the most important section in the report
RE-RUN        raw output of the full suite AFTER all fixes were applied
```

**`NOT PROBED` is mandatory.** A hardening report that implies full coverage while quietly omitting
"we could not test the payment provider's failure modes because their sandbox has no way to
simulate a timeout" is worse than no report — it converts a known unknown into an unknown unknown,
and unknown unknowns are what take products down on launch day.
