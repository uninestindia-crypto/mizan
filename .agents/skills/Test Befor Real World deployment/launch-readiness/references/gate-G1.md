# G1 — Build & Static Integrity

> **Purpose.** The artifact builds clean from zero, and contains nothing it should not — no
> secrets, no debug code, no vulnerable dependency, no localhost URL.
>
> **Veto holder.** The executor. **Entry.** G0 passed. **Exit.** 18 checks resolved.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`. Commands per stack: `stack-playbooks.md`.

**Why this gate is early.** Static findings are the cheapest defects in existence — seconds to
find, seconds to fix. Every one that survives to production cost a thousand times more than it
had to.

---

#### G1.01 · Production build succeeds from a clean state — `S0` `cmd`

- **Run** — `LRK run G1.01 -- <build command>` (the *production* build: `npm run build`, `cargo build --release`, `mvn -B package`, `flutter build apk --release`, `docker build -t app:rc .`)
- **Pass** — exit 0, and the artifact exists on disk. Check that it exists; do not assume.
- **If it fails** — nothing else in this audit matters. Fix it first.
- **Faked by** — running the *development* build. Dev builds skip minification, tree-shaking, strict compilation, and dead-code elimination — which is exactly where build breaks live.

#### G1.02 · Build run twice produces an equivalent artifact — `S2` `cmd`

- **Run** — build, record the artifact hash, clean, build again, compare:
  ```bash
  LRK run G1.02 -- <build command> && <hash the artifact>
  ```
- **Pass** — the second build succeeds and produces a functionally identical artifact. Timestamps and embedded build IDs differing is fine; file *counts* and sizes swinging is not.
- **Why** — a nondeterministic build means the thing you tested is not necessarily the thing you ship.

#### G1.03 · Type check passes with ZERO errors — `S0` `cmd`

- **Run** — `LRK run G1.03 -- <typecheck command>` (`npx tsc --noEmit`, `mypy .`, `go vet ./...`, `cargo check`, `flutter analyze`, `dotnet build /warnaserror`)
- **Pass** — **zero** errors. Not "zero new errors". Not "only in test files".
- **If the project has no type checking at all** — record `manual --status fail --note "untyped language, no static analysis configured"` and treat it as a finding. For an untyped language (plain JS, Ruby, PHP without static analysis), substitute the strongest linter available and say so.
- **Faked by** — `// @ts-ignore`, `# type: ignore`, `any`, `interface{}`, or `--skipLibCheck` added *during the audit* to make the number go to zero. Check the diff: `git diff --stat` should show no new suppressions. Adding a suppression to pass a gate is the definition of faking it.

#### G1.04 · Lint passes: zero errors, zero warnings — `S1` `cmd`

- **Run** — `LRK run G1.04 -- <lint command>`
- **Pass** — zero errors and zero warnings. If the project has a large pre-existing warning count, record the exact baseline number and require zero *new*:
  ```bash
  LRK run G1.04 --title "lint baseline count" --record-only -- <lint command>
  LRK manual G1.04 --status pass --note "Baseline 1,204 warnings recorded at commit abc123. Release diff adds 0. Backlog item filed to clear the baseline."
  ```
- **Why the bar is zero** — a codebase with 400 tolerated warnings does not have static analysis. It has a wall of noise concealing the one warning that mattered.

#### G1.05 · Format check passes — `S2` `cmd`

- **Run** — `LRK run G1.05 -- <format check command>` (`prettier --check .`, `black --check .`, `gofmt -l .`, `cargo fmt --check`)
- **Pass** — no files reported as needing formatting.

#### G1.06 · No TODO / FIXME / HACK on critical paths — `S1` `cmd`

- **Run** —
  ```bash
  LRK run G1.06 -- git grep -nE "TODO|FIXME|HACK|XXX|@todo|temporary|for now|remove this" -- "*.ts" "*.tsx" "*.js" "*.py" "*.go" "*.rs" "*.java" "*.rb" "*.php" "*.cs"
  ```
  (`git grep` exits 1 when there are no matches — a "failing" run with empty output is the clean result. Read the log.)
- **Pass** — no marker sits on a file involved in a critical path from G0.09.
- **Judgement** — a TODO in a rarely-used admin script is S3. A `// TODO: validate this` in the payment handler is a Blocker wearing a comment.

#### G1.07 · No debug artifacts shipped — `S1` `cmd`

- **Run** —
  ```bash
  LRK run G1.07 -- git grep -nE "console\.(log|debug|trace)|debugger;|binding\.pry|byebug|var_dump|dd\(|print_r\(|pdb\.set_trace|breakpoint\(|fmt\.Println|System\.out\.println|alert\(" -- src app lib server
  ```
- **Pass** — no matches, or every match is inside an explicitly permitted logger, a test file, or a CLI whose job is printing.
- **Why it matters beyond tidiness** — `console.log(user)` in production logs a user object into your log aggregator, which is a privacy incident with a paper trail. This check overlaps G9.16 for a reason.

#### G1.08 · No large commented-out code blocks — `S2` `cmd`

- **Do** — scan the release diff for blocks of commented code: `git diff <last-release-tag>..HEAD | grep -E "^\+\s*(//|#).{0,200}[;{}()]"`.
- **Pass** — none. Version control is the place for old code.

#### G1.09 · Dead code, unused exports, unused dependencies removed — `S2` `cmd`

- **Run** — `LRK run G1.09 -- npx knip` or `npx depcheck` / `deptry .` / `cargo +nightly udeps` / `go mod tidy -diff`
- **Pass** — the report is empty, or every remaining entry is justified in a note.
- **Why** — every unused dependency is attack surface you are not watching, and installation time you are paying for.

#### G1.10 · Secret scan over the FULL git history — `S0` `cmd`

- **Run** — in preference order:
  ```bash
  LRK run G1.10 -- gitleaks detect --no-banner --redact -v
  LRK run G1.10 -- trufflehog git file://. --only-verified
  ```
  If neither tool is installed, at minimum:
  ```bash
  LRK run G1.10 --title "history grep" -- git log -p --all | grep -nEi "(api[_-]?key|secret|password|passwd|token|BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY|AKIA[0-9A-Z]{16}|sk_live_|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-)" | head -100
  ```
- **Pass** — zero live credentials anywhere in history.
- **CRITICAL** — deleting a secret in a later commit does **not** remove it. It is still in the history, and history is public the moment the repo is. **Any secret ever committed must be rotated**, not deleted. Record the rotation:
  `LRK manual G1.10 --status pass --note "gitleaks clean. One historical Stripe test key found at commit 3f2a11 — rotated 2026-08-12, old key revoked in Stripe dashboard (screenshot attached)."`
- **Faked by** — scanning only the working tree.

#### G1.11 · No localhost / staging / test keys on a production code path — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G1.11 -- git grep -nE "localhost|127\.0\.0\.1|0\.0\.0\.0|:3000|:8080|ngrok|staging\.|test\.|sk_test_|pk_test_|sandbox" -- src app lib server config
  ```
- **Pass** — every match is inside a test file, a dev-only config branch, or a comment.
- **The classic disaster** — a payment integration left pointing at the sandbox. Money appears to move. It does not. Nobody notices for eleven days.

#### G1.12 · Dependency vulnerability audit — `S0` `cmd`

- **Run** — `LRK run G1.12 -- npm audit --audit-level=high` / `pip-audit` / `govulncheck ./...` / `cargo audit` / `bundle audit check --update` / `composer audit` / `dotnet list package --vulnerable --include-transitive`
- **Pass** — zero CRITICAL, zero HIGH. Each remaining one either fixed or waived with reasoning (*"HIGH in a dev-only build tool, not present in the production bundle"* is a legitimate waiver; *"upgrading is hard"* is not).
- **Faked by** — `--audit-level=critical` to make highs disappear from the output.

#### G1.13 · License compliance — `S1` `cmd`

- **Run** — `LRK run G1.13 -- npx license-checker --summary` / `pip-licenses` / `go-licenses report ./...` / `cargo license`
- **Pass** — a `LICENSE` file exists at the root, and no dependency's licence conflicts with how you distribute. Watch for **GPL/AGPL** in anything proprietary and **SSPL** in anything you offer as a service.
- **Faked by** — never looking. This is the check that turns into a lawyer's email.

#### G1.14 · No abandoned or malicious dependency on a critical path — `S1` `hybrid`

- **Do** — for every direct dependency on a critical path, check last release date, open-issue trend, and maintainer count. Anything unmaintained for over two years and doing something security-relevant is a finding.
- **Also check** — no dependency name is a typosquat of the one you meant (`crossenv` vs `cross-env`), and no package was added in the last 90 days by an unknown author.
- **Record** — `LRK manual G1.14 --status pass --note "14 direct deps reviewed; all maintained within 12 months; no typosquats. Full list attached." --attach deps-review.md`

#### G1.15 · Source map / debug symbol policy decided — `S1` `hybrid`

- **Do** — decide deliberately: are source maps uploaded to the error tracker but *not* served publicly? Are debug symbols stripped from the shipped binary?
- **Check** — after deploying, request `https://your-app/assets/main.js.map`. A 200 means your entire source is public.
- **Record** — the decision plus the evidence.

#### G1.16 · Build artifact size measured against a budget — `S2` `cmd`

- **Run** — `LRK run G1.16 -- du -sh dist build out target 2>/dev/null; npx source-map-explorer 'dist/**/*.js' --json 2>/dev/null | head -40`
- **Pass** — within the written budget. Write the budget first; a budget invented after the measurement is not a budget.

#### G1.17 · No `.env`, key, dump, or customer data committed — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G1.17 -- git ls-files | grep -iE "\.env($|\.)|\.pem$|\.key$|\.p12$|\.pfx$|id_rsa|\.sql$|\.dump$|\.bak$|credentials|serviceaccount.*\.json|\.sqlite3?$"
  ```
- **Pass** — no match, or every match is verified to contain no real data (`.env.example` is fine; `.env.production` is not).
- **Also confirm** — `.gitignore` covers all of these going forward.

#### G1.18 · Strict mode on — `S1` `cmd`

- **Run** — `LRK run G1.18 -- cat tsconfig.json 2>/dev/null; cat pyproject.toml 2>/dev/null | head -60; cat .eslintrc* 2>/dev/null`
- **Pass** — `strict: true` (TS), `strict = true` / `disallow_untyped_defs` (mypy), `-D warnings` (clippy), `TreatWarningsAsErrors` (.NET), `--warnings-as-errors` (Elixir), and no blanket suppression file covering critical-path code.
- **Count the escapes** — `git grep -c "@ts-ignore\|@ts-expect-error\|# type: ignore\|#nosec\|eslint-disable" | sort -t: -k2 -rn | head`. Zero on critical paths.

---

## Exit bar for G1

```bash
LRK status --gate G1
```

Every S0 in this gate is `pass` with EXECUTED proof. **G1.10, G1.11, G1.12, and G1.17 are the four
that end careers** — a leaked key, a sandbox payment endpoint, a known RCE in a dependency, and a
committed database dump. None of them is subtle. All of them ship regularly, because nobody ran the
four commands above.
