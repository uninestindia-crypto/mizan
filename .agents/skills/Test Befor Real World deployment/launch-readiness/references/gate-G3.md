# G3 — Functional Correctness & States

> **Purpose.** Everything the product promises actually works — including the eight ways every
> feature goes wrong. A feature with only a happy path is 40% built and 100% dangerous.
>
> **Veto holder.** Verifier. **Entry.** G2 passed. **Exit.** 16 checks resolved.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**The rule this gate enforces.** *A feature is not shipped until its failure states are shipped.*
Empty, loading, error, offline, permission-denied, stale, partial, too-much-data and
concurrent-edit are part of the feature — not "polish", not "phase 2".

Most of this gate is `manual` because most of it is only visible to a human looking at the running
software. **Manual does not mean unproven.** Every manual pass here should carry a screenshot, a
recording, or a transcript. Take screenshots liberally; they are the single most persuasive thing
in the final report.

---

#### G3.01 · Every acceptance criterion demonstrated — `S0` `manual`

- **Do** — list the acceptance criteria (from the PRD, the ticket, or the README's promises). Demonstrate each one against the running application, one at a time.
- **Record one entry per criterion**, not one for all of them:
  ```bash
  LRK manual G3.01 --status pass --note "AC-1: a new user can register with email+password and receives a verification mail within 60s. Verified 14:22, screenshot attached." --attach ac1.png
  LRK attach G3.01 ./evidence/ac2-checkout.png --caption "AC-2: checkout completes and receipt renders"
  ```
- **If there are no written acceptance criteria** — write them now from what the product claims (the landing page, the README, the UI labels). Software with no stated criteria cannot be verified, only admired.

#### G3.02 · All nine states on every user-visible surface — `S0` `manual`

For **every screen, list, form, and widget**, force each state and look at it:

| # | State | How to force it | The failure you are looking for |
|---|---|---|---|
| 1 | Default | Normal data | — |
| 2 | Loading | Throttle the network to "Slow 3G" in devtools | A blank white frame with no indication anything is happening |
| 3 | Empty | A brand-new account with no records | "0 results" with no explanation of what to do next |
| 4 | Error | Block the API call in devtools, or stop the server | A silent failure, or a raw `500`/stack trace shown to the user |
| 5 | Partial / stale | Return half the data; leave a tab open for an hour | Stale data presented as current, with no indication |
| 6 | Disabled | A read-only or expired account | A control that looks clickable, does nothing, and says nothing |
| 7 | Offline | Devtools → Offline | Work silently lost; a spinner that never resolves |
| 8 | Permission-denied | Log in as a lower-privileged role | A 403 rendered as a crash, or the control visible but broken |
| 9 | Too-much-data | 10,000 rows; a 200-character name; a 5MB text field | Layout collapse, browser freeze, truncation with no ellipsis |

- **Record** — a screenshot per state per major screen. Name them `G3.02-<screen>-<state>.png` and attach them all. This produces the most convincing section of the entire report.
- **Pass** — every state is designed, not accidental. "It shows a spinner forever" is a fail.

#### G3.03 · First-run experience from a genuinely empty account — `S0` `manual`

- **Do** — create a brand-new account. No seed data, no fixtures, no admin shortcut. Walk the primary critical path from there.
- **Pass** — a new user can reach value without help.
- **Faked by** — testing with your own account, which has three years of data in it and every feature already configured. The empty account is a different product, and it is the one every user meets first.

#### G3.04 · Every form: validation, inline errors, double-submit protection — `S0` `manual`

For each form, do all six:
1. Submit it empty → each required field shows its own inline error, not one generic banner.
2. Submit invalid data of each type → the message says what is wrong and how to fix it.
3. Submit valid data with the server returning 500 → the user's input is **not lost**.
4. **Double-click the submit button** → exactly one record is created. This creates duplicate orders in production more often than any other single bug.
5. Paste 10,000 characters into every text field → handled or rejected cleanly.
6. Press Enter in a text field → submits or does nothing, but never something surprising.

- **Record** — `LRK manual G3.04 --status pass --note "6 forms × 6 probes. Double-submit created 2 orders on /checkout — fixed by idempotency key, re-tested, now 1. Screenshots attached."`

#### G3.05 · Destructive actions: confirmation and recovery — `S0` `manual`

- **Do** — find every action that deletes, cancels, overwrites, or sends something irreversible. For each: is there a confirmation? Does the confirmation say *what* is being destroyed and how much? Is there an undo, a soft delete, or a documented recovery path?
- **Pass** — no single misclick destroys data with no recovery.
- **Specifically check** — "Delete account" and any bulk action. Bulk delete with no confirmation count ("Delete 1,482 records?") is a Blocker.

#### G3.06 · List boundaries — `S1` `hybrid`

- **Test** — zero results; exactly one result; exactly one page's worth; one item over the boundary; the last page; a page number past the end (`?page=9999`); a filter matching everything.
- **The classic bug** — insert or delete a record between loading page 1 and page 2, then check whether an item was skipped or shown twice. Offset-based pagination gets this wrong by default.
- **Also** — a permission-filtered list must have a count that matches the visible rows. A "47 results" header above 12 visible rows leaks the existence of 35 records the user may not see.

#### G3.07 · Money correctness — `S0` `cmd`

**Applies whenever the software touches money, price, tax, discount, credit, quota, or units.**

- **First, the disqualifier** — search for floating-point money:
  ```bash
  LRK run G3.07 --title "float money scan" -- git grep -nE "(float|double|Number|parseFloat).{0,40}(price|amount|total|cost|fee|tax|balance|payment)" -- .
  ```
  **Any floating-point money type is a Blocker, not a nit.** `0.1 + 0.2 !== 0.3`, and that becomes a customer complaint, a reconciliation failure, and eventually an audit finding. Use integer minor units or a decimal type.
- **Then test** — rounding at every boundary in both directions; the smallest representable unit; a value with more decimals than the type holds; zero; negative; the maximum amount; mixed currencies (must be rejected or explicitly converted, never silently added); idempotency (the same charge applied twice produces one effect); replay (a duplicated webhook does not double-charge); partial payment, partial refund, over-payment, over-delivery.
- **Reconciliation as a test** — the sum of the parts equals the whole. Assert it.
- **Run the money test file specifically** and record it: `LRK run G3.07 -- <test command> -- <money test path>`

#### G3.08 · Date and time correctness — `S0` `hybrid`

- **Test** — DST spring-forward (the hour that does not exist) and fall-back (the hour that happens twice); an offset east of UTC and one west; a half-hour offset (India, +05:30) and a 45-minute one (Nepal, +05:45); leap year and Feb 29; Dec 31 → Jan 1; the end of a 30-day vs 31-day month; a duration spanning a DST boundary; a timestamp arriving from the future (clock skew).
- **Assert all three explicitly** — server timezone, user timezone, database timezone. They differ, and the bug always lives in the gap.
- **Fast check** — `LRK run G3.08 -- git grep -nE "new Date\(|datetime\.now|time\.Now|DateTime\.Now" -- src app lib | head -40`. Every naive local-time construction on a critical path is suspect.

#### G3.09 · Unicode, emoji, RTL, and very long strings — `S1` `hybrid`

- **Do** — put this string in every text field, save it, reload, and look at it:
  `Ω≈ç√ 你好世界 مرحبا بالعالم 🚀👨‍👩‍👧‍👦 Ǆ' "; DROP TABLE users;-- <script>alert(1)</script>` followed by 10,000 `A`s.
- **Pass** — stored, retrieved, and displayed unchanged; no mojibake; no layout break; no execution.
- **Why the emoji specifically** — 👨‍👩‍👧‍👦 is a multi-codepoint grapheme. Naive length limits truncate it into invalid UTF-8, which crashes JSON parsers downstream days later.

#### G3.10 · Idempotency on every mutating endpoint — `S0` `hybrid`

- **Do** — for each non-GET endpoint, send exactly the same request twice. Count the resulting records, charges, and emails.
- **Pass** — one effect. Or the endpoint is documented as unsafe to retry *and* the client has a guard.
- **Why it is S0** — networks retry. Load balancers retry. Users double-click. Mobile clients retry on reconnect. "It only happens if they click twice" describes a daily event at any scale.

#### G3.11 · Concurrency — `S0` `hybrid`

- **Do** — two actors mutate the same resource at the same instant. Fire two requests simultaneously:
  ```bash
  LRK run G3.11 -- bash -c 'for i in 1 2 3 4 5; do curl -s -X POST <url> -d "<body>" & done; wait'
  ```
- **Pass** — the outcome is correct and deterministic: one wins, one is rejected with a clear conflict, or they merge correctly. Never: both succeed and one silently overwrites the other; two rows created; a counter incremented once instead of twice.
- **Test specifically** — last-write-wins overwriting a field the other user just edited; two people accepting the same one-seat invitation; two refunds of the same charge; a stock counter going negative.

#### G3.12 · Back, forward, refresh, and deep links — `S1` `manual`

- **Do** — mid-flow (step 2 of 3), press back. Then forward. Then refresh. Then copy the URL, open it in a private window, and paste it.
- **Pass** — no crash, no duplicate submission, no lost state without warning, and every screen is reachable by its URL.

#### G3.13 · Upload boundaries — `S1` `hybrid`

- **Test** — empty file; 1 byte; exactly the max size; max+1 (rejected with a clear message, not a 500 or a silent truncation); a `.jpg` that is actually a `.exe` (magic bytes must be checked, not the extension); a filename of `../../../etc/passwd`; a filename with a null byte; a 300-character filename; a 30,000×30,000-pixel image (decompression bomb); an upload interrupted at 50%; two concurrent uploads of the same name.
- **Pass** — every case handled with a specific message; nothing crashes; nothing escapes the upload directory.

#### G3.14 · Outbound email / push / SMS actually sends and renders — `S1` `manual`

- **Do** — trigger every transactional message. Open each one **in a real client**: Gmail web, Gmail mobile, Outlook, and Apple Mail if you can. Screenshot each.
- **Check** — the sender name and address; the subject; whether images load with remote images blocked; whether the plain-text fallback exists; whether every link points at production (not localhost, not staging); whether the unsubscribe link works.
- **Pass** — attached screenshots from a real inbox.
- **The classic disaster** — the welcome email renders as raw HTML source in Outlook, or every link points at `http://localhost:3000`.

#### G3.15 · Search behaviour — `S1` `hybrid`

- **Test** — empty query; a query with no results (does it suggest anything?); `%`, `_`, `*`, `'`, `"`, `\`, `(`, `[`, and a regex like `.*`; a 5,000-character query; a query matching every record; sort stability across pages.
- **Pass** — no crash, no injection, no timeout, and the permission-filtered result count matches what is displayed.

#### G3.16 · Every documented error code is reachable and helpful — `S1` `hybrid`

- **Do** — list every error code the API documents or the UI can show. Trigger each one. Read the message as a user would.
- **Pass** — each is reachable, and each message says what happened and what to do. "An error occurred" is a fail. "Error 4021" with no explanation is a fail.
- **Also confirm** — no error message leaks a stack trace, a SQL fragment, an internal hostname, or a framework version. (Cross-checks G4.20.)

---

## Exit bar for G3

```bash
LRK status --gate G3
```

Count your screenshots. A passed G3 on a product with a UI should have produced **dozens** of
attachments. If it produced three, you demonstrated the product rather than tested it — go back to
G3.02 and force all nine states on every screen.
