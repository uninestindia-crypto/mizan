# G0 — Inventory & Command Map

> **Purpose.** Nothing downstream can be trusted until you know what this software is and which
> commands are real. Every hour wasted later in this process traces back to a skipped G0.
>
> **Veto holder.** The executor (you).
> **Entry.** `lrk init` has been run. **Exit.** All 12 checks resolved; the command map is proven.

Throughout, `LRK` means `python "<SKILL_DIR>/scripts/lrk.py"`.

**Why this gate exists.** The single most common failure in an automated readiness review is an
agent running `npm test` on a project whose real command is `pnpm run test:ci`, seeing "no test
specified", and recording a pass. G0 makes that impossible by demanding that every command in the
map has been *observed to execute*.

---

#### G0.01 · Version control clean — `S0` `cmd`

- **Run** — `LRK run G0.01 -- git status --porcelain` then `LRK run G0.01 --title "branch and tag" -- git log -1 --oneline --decorate`
- **Pass** — the first command prints **nothing at all**, and you are on the intended release branch or tag.
- **If it fails** — uncommitted changes mean you are certifying something that does not exist in version control. Commit, stash, or clean. Then re-run.
- **Not a git repo?** — mark `manual --status fail --note "no version control"`. This is S0 and it stays S0. You cannot roll back what you cannot identify.
- **Faked by** — running the audit on a dirty tree "because it's just a small local change". That small local change is the one that will not be in the deploy.

#### G0.02 · Stack detected and written down — `S0` `cmd`

- **Run** — `LRK run G0.02 -- python "<SKILL_DIR>/scripts/lrk.py" detect`
- **Pass** — the output lists the languages, frameworks, and package managers, and you can name them back.
- **If nothing is detected** — inspect manually: list the root directory, read any `Makefile`, `Justfile`, `Taskfile`, `docker-compose.yml`, CI workflow, or `CONTRIBUTING.md`. CI workflow files are the highest-value source in the repository: **they contain the commands that actually work.**
- **Faked by** — assuming the stack from the folder name.

#### G0.03 · Command map discovered AND each command proven to execute — `S0` `cmd`

This is the most important check in the entire process.

- **Do** — build a table of the real commands: install, build, test, lint, typecheck, format, start, migrate, migrate-rollback, e2e, audit. Get them from, in order of trust: (1) the CI workflow file, (2) `package.json` scripts / `Makefile` targets, (3) the README, (4) the detector's guesses.
- **Run each one** and record it:
  ```bash
  LRK run G0.03 --title "install"   -- <install command>
  LRK run G0.03 --title "build"     -- <build command>
  LRK run G0.03 --title "test"      -- <test command>
  LRK run G0.03 --title "typecheck" -- <typecheck command>
  LRK run G0.03 --title "lint"      -- <lint command>
  ```
- **Pass** — every command in the map has been executed at least once and either succeeded, or failed for a *substantive* reason (real test failures) rather than "command not found" / "no script named X".
- **Then write the map down** so later gates reuse it:
  ```bash
  LRK manual G0.03 --status pass --note "install: pnpm i --frozen-lockfile | build: pnpm build | test: pnpm test:ci | typecheck: pnpm tsc --noEmit | e2e: pnpm playwright test | migrate: pnpm prisma migrate deploy"
  ```
- **If a command does not exist** — that is a finding, not a blocker for this check. Record it and let the gate that needs it fail honestly (G1.03 has no typecheck → G1.03 fails).
- **Faked by** — copying the detector's guesses into the note without running them. The whole gate is worthless if you do this.

#### G0.04 · Clean-clone install from zero succeeds — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G0.04 --title "clean clone" -- git clone --depth 1 . /tmp/lrk-clean && cd /tmp/lrk-clean && <install command>
  ```
  On Windows use a path like `%TEMP%\lrk-clean` or `$env:TEMP\lrk-clean`.
- **Pass** — installs successfully in a directory that has never seen this project, with no pre-existing `node_modules`, `venv`, `target`, or cache.
- **If it fails** — you have a machine-dependency: a global package, an env var set months ago, a private registry token in your shell. Every new developer and every CI runner will hit it. Fix it or document it in the README.
- **Faked by** — running `npm ci` in the existing directory. That is not a clean install; the cache and lockfile resolution are already warm.

#### G0.05 · A stranger can get it running from the README alone — `S1` `manual`

- **Do** — read the README as if you have never seen this project. Follow it literally, typing only what it says, in a clean clone. Write down every step where you had to know something it did not tell you.
- **Record** — `LRK manual G0.05 --status pass|fail --note "<what was missing>" --attach <notes file>`
- **Pass** — you reached a running application without consulting anything else.
- **Faked by** — reading the README and thinking "yes, that looks about right". You must actually follow it.

#### G0.06 · `.env.example` complete; app fails loudly on a missing variable — `S0` `hybrid`

- **Do** — compare every variable the code reads against `.env.example`:
  ```bash
  LRK run G0.06 --title "env vars referenced in code" -- git grep -hoE "(process\.env\.[A-Z0-9_]+|os\.environ(\.get)?\[?['\"][A-Z0-9_]+)" -- . 
  ```
  Then start the app with one required variable removed.
- **Pass** — every variable used in code appears in `.env.example`, **and** removing a required one makes the app refuse to start with a message naming the variable.
- **If the app starts anyway** — this is the classic 3am outage: a missing secret becomes a `null` that silently disables authentication or writes to the wrong bucket. Add startup validation. This is S0.
- **Faked by** — checking only that `.env.example` exists.

#### G0.07 · Lockfile present, committed, and install is reproducible — `S0` `cmd`

- **Run** — `LRK run G0.07 -- git ls-files | grep -E "(package-lock.json|pnpm-lock.yaml|yarn.lock|bun.lockb|poetry.lock|Pipfile.lock|Cargo.lock|go.sum|Gemfile.lock|composer.lock|pubspec.lock)"`
- **Pass** — at least one lockfile is tracked by git, and the install command is the *frozen* variant (`npm ci`, `pnpm i --frozen-lockfile`, `yarn --immutable`, `poetry install --sync`, `bundle install --deployment`).
- **If the install command is not frozen** — you are not shipping what you tested. A transitive dependency can change between your test run and your build. S0.
- **Faked by** — a lockfile that exists but is gitignored, or a CI step that runs plain `npm install`.

#### G0.08 · Runtime versions pinned — `S1` `cmd`

- **Run** — `LRK run G0.08 -- ls -a .nvmrc .node-version .python-version .tool-versions rust-toolchain.toml 2>&1; grep -A3 '"engines"' package.json 2>/dev/null`
- **Pass** — the required runtime version is declared in a file, and it matches what CI uses.
- **Faked by** — "it works on my Node 22" while CI runs Node 18.

#### G0.09 · Critical paths enumerated — `S0` `manual`

The **critical paths** (also: money paths) are the 2–5 journeys that, if broken, mean the product
has no reason to exist. Everything downstream is prioritised by this list.

- **Do** — write them as user journeys, not endpoints. Good: *"a new customer signs up, adds a card, and completes a first purchase."* Bad: *"POST /api/orders."*
- **Test for a correct list** — for each one ask: *if this silently returned the wrong answer for one hour, would we have a serious problem?* If no, it is not critical. If you have more than five, you have not chosen.
- **Record** — `LRK manual G0.09 --status pass --note "1) signup → verify email → first login  2) add card → checkout → receipt  3) refund request → approval → money returned"`
- **Faked by** — listing every feature. A list of everything is a list of nothing.

#### G0.10 · External dependency inventory — `S0` `manual`

- **Do** — list every service this software cannot function without: databases, caches, queues, object storage, email/SMS providers, payment processors, auth providers, analytics, CDNs, feature-flag services, and any internal service owned by another team.
- **For each one record**: what breaks if it is down, whether there is a fallback, and where the credentials live.
- **Find them** — `git grep -ohE "https?://[a-zA-Z0-9.-]+" -- . | sort -u | head -60` and read the dependency manifest.
- **Record** — one `--note` listing them, or attach a markdown table.
- **Why it matters** — G7 will kill each of these one at a time. An incomplete inventory means an untested failure mode.

#### G0.11 · Target environments enumerated — `S0` `manual`

- **Do** — name the production URL(s), the staging/pre-production environment, the regions, and how a deploy reaches each one. If there is **no** staging environment, record that as the finding it is — G11.06 will fail, and it should.
- **Record** — `LRK manual G0.11 --status pass --note "prod: https://app.example.com (Vercel, iad1) | staging: https://staging.example.com | deploy: push to main → GH Actions"`

#### G0.12 · Cut line written — `S1` `manual`

- **Do** — write what is in v1.0 and, explicitly, what is **not**. The "not" list must not be empty. A scope with no stated non-goals is a wish, and it will grow during the audit.
- **Record** — `LRK manual G0.12 --status pass --note "IN: signup, checkout, refunds, admin export. NOT IN v1: multi-currency, SSO, bulk import, mobile app, webhooks for partners."`
- **Then hold it.** If someone adds work during the readiness review, it is a new release, not this one.

---

## Exit bar for G0

```bash
LRK status --gate G0
```

All twelve resolved. No `todo`. The command map has been *executed*, not guessed. If you cannot
state, in one sentence each, what this software is, what its critical paths are, and what it
depends on — you are not through this gate, whatever the checklist says.
