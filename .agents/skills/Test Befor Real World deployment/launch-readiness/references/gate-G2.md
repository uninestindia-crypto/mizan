# G2 — Test Truth

> **Purpose.** Not "do the tests pass" — *would these tests catch a regression?* A green suite that
> has never failed is decoration, and decoration has shipped more outages than no tests at all,
> because it produces confidence.
>
> **Veto holder.** Verifier. **Entry.** G1 passed. **Exit.** 18 checks resolved.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**The central check in this gate is G2.06.** If you do one thing here, do that one.

---

#### G2.01 · A test suite exists and runs with one documented command — `S0` `cmd`

- **Run** — `LRK run G2.01 -- <test command>`
- **Pass** — the suite runs and reports a count of tests greater than zero.
- **If there is no suite** — record the failure. Do **not** mark N/A. "This project has no tests" is the most important sentence the report can contain, and hiding it as N/A is the single most damaging thing you can do in this whole process.
- **Faked by** — `npm test` printing `Error: no test specified` and exiting 0 (the npm default). Read the output; do not trust the exit code alone here.

#### G2.02 · Full suite passes from a CLEAN state — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G2.02 -- <clean> && <install> && <migrate from zero> && <test command>
  ```
  Concretely, e.g.: `rm -rf node_modules dist .next && npm ci && npx prisma migrate reset --force && npm test`
- **Pass** — green, from nothing.
- **Why this catches so much** — "it passes here" and "it passes from zero" differ constantly: a stale build artifact, seeded data from three days ago, an env var still set in your shell, a migration that only works because your database already had the column.
- **Faked by** — running the suite in the warm working directory. That is G2.01, not G2.02.

#### G2.03 · Suite passes in randomised order — `S1` `cmd`

- **Run** — `LRK run G2.03 -- <test command> --shuffle` (`jest --randomize`, `pytest -p no:randomly --random-order`, `go test -shuffle=on ./...`, `rspec --order random`, `vitest --sequence.shuffle`)
- **Pass** — green.
- **If it fails** — you have order-dependent tests. They will start failing the day CI parallelises, at the worst possible moment, and everyone will blame the infrastructure.

#### G2.04 · Suite passes twice in a row — `S1` `cmd`

- **Run** — `LRK run G2.04 -- <test command> && <test command>`
- **Pass** — both green.
- **If the second run fails** — tests are leaving state behind: rows in the database, files on disk, a mocked module never restored.

#### G2.05 · Zero skipped tests — `S1` `cmd`

- **Run** — `LRK run G2.05 -- git grep -nE "\.(skip|only)\(|xit\(|xdescribe\(|@pytest.mark.skip|@Ignore|t\.Skip\(|#\[ignore\]|fit\(|fdescribe\(" -- .`
- **Pass** — no matches, or every one is justified in a note with a ticket reference.
- **`.only` is worse than `.skip`** — a single stray `.only` in a committed file means the entire rest of the file never ran, and CI stayed green the whole time. Search for it specifically.

#### G2.06 · SABOTAGE PROOF — `S0` `cmd`

**The most valuable check in the gate. A test that has never failed has never been validated.**

- **Do** — pick three functions on the critical paths from G0.09. For each one: break it deliberately, run the suite, confirm it goes RED, then restore the code.
  - Invert a comparison: `>=` becomes `<`
  - Return a constant: `return 0` / `return true` / `return []`
  - Delete a permission check or a validation line
- **Record the GREEN BASELINE first. This step is not optional.** `--expect-fail` passes on *any*
  non-zero exit — including "the suite was already broken before you touched anything". Without a
  baseline, a permanently-red suite makes all three sabotages look like successes, and the check
  proves nothing:
  ```bash
  LRK run G2.06 --title "BASELINE: suite is green before any sabotage" -- <test command>
  ```
  **If the baseline is not green, stop.** Fix the suite, then start G2.06 over.
- **Then run each sabotage with `--expect-fail`, which makes a red suite the passing outcome:**
  ```bash
  # 1. edit the file to break it, then:
  LRK run G2.06 --expect-fail --title "sabotage 1: invert total>=0 in pricing.ts" -- <test command>
  git checkout -- <the file>          # restore before the next one
  LRK run G2.06 --expect-fail --title "sabotage 2: authorize() always returns true" -- <test command>
  git checkout -- <the file>
  LRK run G2.06 --expect-fail --title "sabotage 3: refund amount hardcoded to 0" -- <test command>
  git checkout -- <the file>
  # finally, prove you restored everything:
  LRK run G2.06 --title "code restored, tree clean" --expect-empty -- git status --porcelain src test
  ```
- **Pass** — the baseline was green, all three sabotages produced a red suite, and the code is restored.
- **A sabotage that stays GREEN is recorded as a FAIL, and that is the most valuable result this
  check produces.** It means the logic you just broke has no test asserting on it. Worked example:
  changing a tax calculation from `Math.round` to `Math.floor` left a real suite green — the line
  was *covered* by a test that happened to use a value where the two agree, so coverage reported
  100% while the rounding rule was entirely unverified. Coverage tools cannot find this. Only
  sabotage can.
- **If a sabotage stays green** — you have found untested critical logic. That is a finding of the highest value in this entire document, and it is invisible to every coverage tool. Write the missing test, then re-sabotage to prove the new test works.
- **Do not skip the restore step.** Confirm `git status --porcelain` is empty before moving on.

#### G2.07 · Coverage measured; critical-path coverage meets a written bar — `S1` `cmd`

- **Run** — `LRK run G2.07 -- <test command> --coverage` (`jest --coverage`, `pytest --cov`, `go test -cover ./...`, `cargo llvm-cov`)
- **Pass** — coverage exists as a number, and the files on the critical paths are near-complete.
- **Ignore the global percentage.** It is trivially gamed by tests that assert nothing. What matters: are the *branches that handle money, permissions, and migrations* exercised? Uncovered lines in those files are gate failures regardless of the headline number.

#### G2.08 · No assertion-free tests — `S1` `hybrid`

- **Run** — `LRK run G2.08 -- git grep -L "expect\|assert\|should\|require\.\|t\.Error\|XCTAssert" -- "*test*" "*spec*"`
- **Pass** — every test file contains assertions.
- **Also look for** — `expect(() => f()).not.toThrow()` as the only assertion. That asserts almost nothing. Assert on the *value*.

#### G2.09 · No branching logic inside tests — `S2` `cmd`

- **Run** — `LRK run G2.09 -- git grep -nE "^\s+(if|switch)\s*\(" -- "*.test.*" "*.spec.*" "*_test.py" "*_test.go"`
- **Pass** — none, or each justified.
- **Why** — an `if` in a test means one branch may assert nothing, silently, forever.

#### G2.10 · Tests are deterministic — `S1` `hybrid`

- **Run** — `LRK run G2.10 -- git grep -nE "Date\.now\(\)|new Date\(\)|Math\.random\(\)|datetime\.now\(\)|time\.Now\(\)|uuid4?\(\)|rand\." -- "*test*" "*spec*"`
- **Pass** — every use is inside a frozen-clock or fixed-seed helper.
- **Also** — no test makes a real network call. `git grep -n "https\?://" -- "*test*"` should only show localhost or an explicit mock server.
- **Why** — a non-deterministic test gets muted, and a muted test is how a known bug enters production wearing a green badge.

#### G2.11 · Flake count is zero — `S1` `cmd`

- **Run** — `LRK run G2.11 -- <test command> && <test command> && <test command>`
- **Pass** — three identical green runs.
- **A flaky test is a failing test.** Fix it or delete it. "Re-run until green" is a policy of deliberately ignoring your only warning system.

#### G2.12 · Unit tests cover every branch of domain logic — `S0` `manual`

- **Do** — take the part-type matrix below. For each kind of code the project contains, confirm the listed cases exist as tests. This is a reading exercise; do it honestly.

| Kind of code | Minimum cases that must exist |
|---|---|
| Pure function | happy path; empty; zero; one; max; max+1; negative; null; every error branch asserting the *specific* error |
| Money / pricing / tax | + rounding both directions; smallest unit; more decimals than the type holds; zero; negative; maximum; mixed currency; idempotency; replay; partial refund; over-payment; **and no floating point anywhere** |
| Date / time | + DST forward and back; offsets east and west; a half-hour offset; leap year; Feb 29; month-end; server tz ≠ user tz ≠ db tz; a timestamp in the future |
| Auth / permission | + every role × every resource × every action; unauthenticated; expired token; revoked token; token for a deleted user; cross-tenant read; cross-tenant write; self-escalation |
| API handler | + minimal body; maximal body; missing field; extra field; wrong type per field; malformed JSON; oversized; deeply nested; unauthenticated; unauthorised; rate-limited |
| DB / migration | + empty table; one row; production-scale count, timed; null in every nullable column; unicode and 10k strings; each constraint violation; transaction rollback; concurrent write; migration from zero; **rollback executed** |
| UI component | + all nine states; keyboard only; 320px; dark mode; 200-char name; 10k-row list; reduced motion; double-click submit; back/refresh mid-flow |
| Background job | + success; retriable failure; permanent failure; **double delivery**; out-of-order; poison message; crash mid-job; visibility-timeout re-delivery; 100k backlog |
| Third-party call | + 400; 401; 403; 404; 429 with and without `Retry-After`; 500; 503; timeout; slow-but-successful; malformed body; empty body; HTML instead of JSON; **provider unreachable**; credentials expired mid-session |
| File upload | + empty; 1 byte; max; max+1; wrong extension; right extension wrong magic bytes; zip bomb; `../../etc/passwd` filename; 300-char name; huge pixel count; interrupted at 50%; duplicate; concurrent same-name |
| Search / pagination | + no results; one page exactly; one item over the boundary; last page; past the end; filter matching everything; regex and SQL metacharacters; sort stability; **item inserted between page 1 and page 2**; permission-filtered count matches visible rows |
| Config / feature flag | + each variable missing; present but empty; wrong type; wrong format; secret redacted in logs; flag on; flag off; **flag flipped while a user is mid-flow** |

- **Record** — `LRK manual G2.12 --status pass|fail --note "<which part types exist, which case groups are missing>" --attach coverage-gaps.md`

#### G2.13 · Contract tests pin every boundary — `S0` `hybrid`

- **Do** — confirm a test would go RED if someone changed: an API response shape, a database column, an event payload, an error code, or a public export.
- **Prove it by sabotage** — rename a field in a response and confirm a test fails:
  ```bash
  LRK run G2.13 --expect-fail --title "renamed order.total → order.amount" -- <test command>
  ```
- **Pass** — you cannot change a boundary without breaking a test.

#### G2.14 · Integration tests run against a REAL database — `S0` `cmd`

- **Run** — `LRK run G2.14 -- <integration test command>` with a real database container, real migrations run forward from empty.
- **Pass** — the tests use a real engine, real constraints, real transactions.
- **Faked by** — an in-memory SQLite stand-in for Postgres. It does not enforce the same constraints, does not have the same types, does not have the same concurrency behaviour, and will happily accept data your production database rejects.
- **Also faked by** — mocking your own database wrapper. That tests the wrapper. Mock at the network or process boundary, never at your own function boundary.

#### G2.15 · E2E covers every critical path from empty — `S0` `cmd`

- **Run** — `LRK run G2.15 -- <e2e command>` (`npx playwright test`, `npx cypress run`, `maestro test`, a `curl` script against a running server)
- **Pass** — every path from G0.09 is covered, starting from a genuinely empty state — no seeded user, no pre-created record.
- **Attach the artifacts** — Playwright and Cypress produce screenshots, videos, and traces. Attach them; this is exactly the human-visible proof the report is for:
  ```bash
  LRK attach G2.15 ./playwright-report/index.html --caption "Playwright HTML report, 24 specs"
  LRK attach G2.15 ./test-results/checkout/video.webm --caption "Checkout journey recording"
  ```
- **If there is no E2E harness** — walk the paths by hand and attach a screenshot of each step. Slower, entirely valid, still evidence.

#### G2.16 · Every known bug has a regression test — `S1` `manual`

- **Do** — take the bug tracker, or the last 30 bugfix commits (`git log --oneline --grep="fix" -30`). For each, confirm a test exists that fails without the fix.
- **Pass** — every one has a test, or the gaps are listed.
- **Why** — this is the single practice that stops a codebase re-breaking the same way forever.

#### G2.17 · Suite runtime recorded — `S3` `cmd`

- **Run** — already captured by G2.02's duration. Record the number.
- **Pass** — recorded. If it is over ten minutes, note it: slow suites get skipped, and skipped suites are no suites.

#### G2.18 · CI runs the same commands as local, and is GREEN on the release commit — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G2.18 -- gh run list --limit 5
  LRK run G2.18 --title "CI status for release commit" -- gh run view --log-failed
  ```
  Or attach a screenshot of the CI dashboard showing green on the exact release SHA.
- **Pass** — CI is green **on the commit being released**, not on some earlier commit, and CI runs the same commands you just ran.
- **Compare the workflow file to your command map from G0.03.** Drift between them means one of the two is not testing what ships.
- **No CI at all?** — record the failure. Local-only verification means the next person to touch this ships untested code.

---

## Exit bar for G2

```bash
LRK status --gate G2
```

The gate is passed when you can answer yes to: *"If someone broke the most important function in
this codebase right now, would a test go red before a user noticed?"* — and you know the answer is
yes because **you did it three times and watched it happen** (G2.06).
