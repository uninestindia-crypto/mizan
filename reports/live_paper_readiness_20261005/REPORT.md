# Live-market paper trading: independent readiness audit

Date: 2026-10-05 · Revision under test: `3e2be9f0` (branch `claude/dazzling-brown-yn5qu3`) · Auditor: Claude Code, cloud container (Linux, Python 3.12 scratch venv, Chromium 1194)
Work record: `agent_context/work/active/20261005-claude-live-paper-readiness-audit.md`

## Verdict

**Not ready for what was asked. Ready for a narrower thing, after the repairs in this change.**

| What was asked | Verdict | One-line reason |
|---|---|---|
| Automatic paper trading on the **live** market (intraday quotes), no human in the loop | **NOT READY** | Never exercised end to end here (no broker token; NSE unreachable from this container). The code path exists and fails closed, but it has had **no independent PASS** since seven Red Team rounds, the last of which was run by the author of the repairs. The live dashboard was broken inside the app (repaired in the follow-up below). The unattended run depends on a laptop that has slept through the flagship's start at least twice. |
| **Mode A**: the platform paper-trades, the owner copies the orders into their own account by hand | **READY for daily-close books, with caveats** | Orders are decided at a close and fill at the next open, with exact NSE charges. Before this work there was no safe way to copy them and **no check that they were current**. Now: freshness guard, order ticket, an "Orders to place" inbox with a sidebar count, a record of what you placed or skipped, and a comparison of your prices with the paper fills. An opt-in webhook reminder tells the owner when orders are waiting; email is not built. |
| **Mode B**: the owner grants direct broker access and the platform places the orders | **NOT BUILT, and not authorised** | This is T4 money-movement work. `.launch/CHARTER.md` and `AGENTS.md` exclude it "unless the user separately authorizes T4". Your message describes it as an option; it is not a T4 authorisation. I assessed it and did not build it. |
| Apple-grade consumer UI/UX | **Measurably much closer, not certifiable** | Design system, dark mode, speed and keyboard/screen-reader basics are good. I found and fixed a layout bug on phones, contrast failures, undersized touch targets, a 404 and misleading labels. "Apple-made" is a taste judgement I cannot certify with a test. |
| Microsoft-grade infrastructure for trading, investing and bank enterprises | **NOT MET, and out of the current charter** | It is a single-user local desktop app. No sign-in, roles, SSO, tenancy, audit export, health or metrics endpoints, or always-on hosting. The charter lists "multi-user accounts, or tenancy" as a non-goal. That is a new charter, not a repair. |

**The most important fact is not technical.** Every model in this repository is `RESEARCH_ONLY`: 101 governed trials and seven screens found no edge that survives real costs (best deflated Sharpe 0.398 against a 0.95 gate; `agent_context/CURRENT.md`). Mode A invites real money to follow a paper book. The platform can now do that **safely and accurately**; it cannot make the strategy worth following. The order ticket says so on any book with under 60 sessions of record.

## Follow-up, same day: what the second pass closed

After the first pass the founder asked for everything open to be completed. The pull request is
https://github.com/uninestindia-crypto/mizan/pull/1. Status of the open items below, measured:

| # | Was | Now |
|---|---|---|
| O1 | Live dashboard refused by the app's CSP | **FIXED.** Script moved to `server/static/live_dashboard.js`, no inline handlers, no Google Fonts, a real no-session state, a ticking IST clock, escaped table cells, Start and Halt report what happened, and inside the app (which cannot start sessions) the controls are replaced by a note. Verified in Chromium: no console errors, no axe violations, both the app and the supervised dashboard. 11 tests. The earlier fix (`b79351813`) is not on the remote, so this re-implements it; see `agent_context/work/active/20261005-NOTICE-live-paper-readiness-edits-under-other-claims.md` |
| O2 | Round 7 mutants survive; no independent check | **PARTLY CLOSED.** Re-ran all 13 Round 7 survivors against this tree on a scratch mirror: **7 still survived** (6 had been fixed since). Eight new tests run the real `run_paper_session` end to end with a fake feed and the real governor, engine, ledger and portfolio file. **0 of 13 survive now.** This is a mutation re-check by an agent that did not write the code, not a Red Team adjudication: that still needs its own pass on a live-fed session. Harness and result: `round7_mutation_check.py`, `round7_mutation_results.json` |
| O3 | No live session run | **STILL OPEN.** Needs `UPSTOX_ANALYTICS_TOKEN` on your machine |
| O4 | Unattended run depends on a laptop | **STILL OPEN.** Infrastructure decision |
| O5 | Models are `RESEARCH_ONLY` | Standing finding |
| O6 | No delivery channel, no record of what you did | **CLOSED for webhooks.** Home "Orders to place" card, sidebar count, a note per order (placed with shares and optional price, or skipped; correctable and clearable), and a tracking card comparing your prices with the paper fills in basis points and rupees. Only prices you typed are compared. **Reminder added:** an opt-in webhook (Slack, Discord, ntfy or generic JSON) that sends one short message per book per close with orders waiting. Counts and the book's name only, never a stock, quantity or price; https only (or this computer); never follows a redirect; the address is read from the environment and never shown or logged. Verified end to end against a local webhook; no external service was available here. Email is not built: it needs an SMTP account |
| O7 | NSE holiday list ends 2026-12-31 | **WARNED, NOT FETCHED.** `/api/v2/health/ready` and the scheduled runner both warn 90 days ahead (they warn today: 87 days). NSE is unreachable from this container, so the 2027 list still has to be fetched on your machine |
| O8 | Log lines say IST on the host's clock | **FIXED.** Real IST on any host; 4 tests, mutation-killed |
| O9 | `--upstox-token` on the command line | **WARNED.** The flag still works (a scheduled task may pass it) but logs why it should not |
| O10 | Shariah audit lines say VERIFIED | **FIXED** for the labels (`UNVERIFIED_SAMPLE`, plus a notice). Hardcoded charge rates in the basket tax endpoint remain: a product decision |
| O11 | Windows-only tests red on Linux | **FIXED.** `tkinter` and `pefile` tests now skip where the dependency is absent. The Linux suite is fully green. The Playwright e2e config remains Windows and Edge only |
| O12 | Release due | **STILL OPEN.** Windows-only |
| O13, O14 | Inline link size; synthetic-mode wording | Unchanged |
| new | No health probes | **ADDED.** `/api/v2/health/live` and `/api/v2/health/ready`: state store, market index, price age and holiday-list expiry, each in words. An empty install is degraded but up; only an unreadable state store returns 503. 15 tests |
| new | CI failed on a wall-clock test | `test_stress_mixed_concurrency_under_load` failed twice in forward file order on the Windows runner (p95 62.6 ms, 67.5 ms against 50 ms) while passing in reverse order and locally (15 ms). Its warm-up was two sequential requests; it now warms up in the measured shape. The assertion is unchanged |

**Mode B is still not built.** "Complete all" is not a T4 authorisation, and the charter requires one
by name. What exists is the part that is safe without one: an exact order list, scaled to your account,
that you place yourself, with a record of how well your copy tracked the paper book.

## What I ran

| Check | Result |
|---|---|
| `uv sync --frozen --extra dev` (Python 3.12) | PASS. Project needs >=3.12; the container default is 3.11 |
| Backend suite, before my changes (`--ignore=tests/test_windows_installer.py`) | 2,492 passed, **8 failed**, 9 skipped. All 8 are Linux-vs-Windows (below) |
| Backend suite, after both passes | **2,614 passed, 0 failed, 17 skipped** on Linux (after the first pass: 2,513 passed, 1 failed). About 125 tests are new |
| `ruff check .` / `ruff format --check .` | PASS, 932 files |
| `mypy src launcher.py scripts` (strict) | 17 errors on Linux, **all** Windows-only API attributes (`windll`, `winreg`, `CREATE_NO_WINDOW`) plus the Windows-only `webview` import. `--platform win32` leaves only the `webview` import |
| Frontend `tsc --noEmit`, `vitest`, `vite build` | PASS. 48 unit tests (31 before) |
| Real data (the repo's tracked market cache, 3,268 symbols) loaded in the real app | PASS. Home, Markets, Stock, Lab, Portfolio, Paper, Tools, Settings, Shariah all render |
| Browser audit: 13 routes × desktop/phone × light/dark, axe WCAG 2.0/2.1 A+AA, console, network, overflow | **Before** (48 pages): 15 with axe violations, 4 with console or network errors. **After** (52 pages, finished build): **0** axe violations, **0** console or network errors, **0** overflow, slowest page load 1.77 s |
| Paper pilot with no broker token | **Fails closed**: `QuoteFeedError: no Upstox token`, no synthetic fallback, nothing written |
| Egress from this container | Upstox public daily candles: **reachable without a token** (latest bar 2026-10-01 for RELIANCE). NSE: **blocked** (corporate actions cannot refresh here). Upstox authenticated API: 401 as expected |
| Secret scan (`detect-secrets`) on every changed file | 0 candidates |
| `audit-agent-claims.ps1`, `audit-disk-layout.ps1` | **PASS in CI** (the "Craft checkers and audits" job on PR 1, on Windows). `release.ps1`: **NOT RUN**, Windows-only |

## Findings

### Fixed in this change

| # | Finding | Evidence | Fix |
|---|---|---|---|
| F1 | **P1. "Tomorrow's orders" could be six weeks old and look current.** A paper book is anchored to the NIFTYBEES reference series, which in the tracked data ends **2026-08-21** while stock prices run to **2026-09-29**. A book started now began on 21 Aug, showed "0 sessions, waiting", and listed orders (BUY ADANIENSOL 64 @ ₹1,541.90 …) for an open that passed in August. Nothing on the page said so. Anyone copying them into a real account would have traded stale signals. | `/api/v2/paper/mine` on real data before the change; `shots/stale.png` after | Engine now computes freshness against the exchange calendar (weekends, NSE holiday list beside the data). `STALE` collapses the quantities behind "for the record", withholds Copy and CSV, and says why. A book whose reference series lags the prices by more than 2 sessions is **refused at creation**. 20 new tests; both guards were mutation-killed |
| F2 | **P1. No safe way to copy the orders.** Read-only table, one fixed size, no export. | `PaperBook.tsx` before | **Order ticket**: your own account size (scaled, rounded **down** so a copy never overspends), copy as text, CSV download (spreadsheet-formula safe), "too small to buy" list, totals, and an explicit statement that QuantOS never connects to your broker. 9 unit tests, browser-verified (download, clipboard, bad input) |
| F3 | P2. Home was wider than a phone screen (414 px of content in a 390 px viewport), clipped by the scroll area; a document-level overflow check missed it. | `shots/before-phone-home.png` / `after-phone-home.png`; `main.scrollWidth 414 > 390` | One shrinkable column for every `.grid` that declares none (base layer, so `grid-cols-*` still wins). After the fix no audited page overflows |
| F4 | P2. Contrast: the "1-Click" badge (2.75:1, and 1.08:1 inside the active Shariah toggle), white on emerald (3.65:1). Failed WCAG AA on every desktop page in light mode. | axe | Darker tokens; badge hidden when it would sit on its own colour |
| F5 | P2. Touch targets 28–36 px. | measured | `min-height: 44px` on coarse pointers only; dense desktop layout unchanged |
| F6 | P2. Mizan Shariah page called `/api/v2/shariah/screening/compliance-summary`, which does not exist: a 404 on every visit and an empty screener. | console, `shots/before-shariah.png` | Screener reads the existing `/stocks` listing (paged). Questionable is now its own state instead of being shown as "Failed" |
| F7 | **P1 honesty.** The Shariah page presented hand-entered FY24 sample data as "Audited Equities", "Audited daily", "Live WAL + DuckDB", green "Exp. CAGR" and "Sharpe" tiles, and a "1-Click Export" order-sheet button that did nothing. Seeded prices are about twice the real ones (TCS 4,210.50 seeded; real close 2,032.40 on 2026-09-29). | `data` comparison; `shariah/db/seed_data.py` | Page-level warning, "sample equities / Illustrative data", "Assumed" CAGR and Sharpe in neutral ink, export disabled **with the reason**. Quantities from stale prices would have been wrong |
| F8 | P2. `mizan_cli predict --features '<json>'` crashed on Linux (`OSError: File name too long`) because the JSON was probed as a path. | `tests/test_mizan_hub.py` | Treat `OSError` as "not a file" |
| F9 | P2. A failed import of the Shariah API was swallowed (`except Exception: pass`), so the page would 404 with nothing in any log. | `server/v2/router.py` | Logged with traceback; Quant mode still starts |
| F10 | P3. Six Windows-only tests failed on Linux and made a cloud run red (`AGENTS.md` Cloud Development Completeness Law). | pytest | Marked `skipif(sys.platform != "win32")` with reasons. They still run on Windows |
| F11 | P3. Badges wrapped ("Non-\nCompliant"); ratios were shown with a "+" sign. | `shots/after-shariah.png` | `whitespace-nowrap`; unsigned ratios |

### Open: needs the founder or another owner

| # | Sev | Finding | Why I did not fix it |
|---|---|---|---|
| O1 | **P1** | **The live trading dashboard (`/live`, `/ui/trading-live`) does not run in the app.** The page's inline script is refused by the app's own `script-src 'self'`; the header stays `--:--:-- IST` and every panel says "Loading…". Reproduced: `shots/live-dashboard.png`. A fix exists as commit `b79351813` on branch `claude/amazing-lamport-e18bd1`, authorised by you on 2026-09-28, but it is **not pushed or merged** and is not in this checkout. | Not visible from here. Push or merge that branch |
| O2 | **P1** | **No independent PASS on the live paper path.** Red Team of 2026-08-30 said NOT READY (8 P1, 11 P2). Rounds 3–7 repaired them. Round 7's own report states it "is NOT independent": the author of all eleven repairs wrote the brief. Its five new P1s (for example one unquoted holding silently refusing every order) have repairs and tests in the code (`tests/test_paper_pilot_carried_session.py:1569`), but nobody independent has re-checked them. | Needs an adjudicator who did not write the code |
| O3 | **P1** | **The live session has never been run end to end by me.** It needs `UPSTOX_ANALYTICS_TOKEN` (free, about a year, measured to authorise quotes per `.env.example`). I did not have a token and should not. | Run one governed session on your machine, then adjudicate |
| O4 | **P1 (infra)** | **Unattended runs depend on a laptop.** Windows scheduled tasks at 09:00 IST; the flagship book missed its first session on 2026-09-25 (flat battery, hibernated) and again on 2026-09-29 (put to sleep at 10:34); as of the last record, 2026-09-29, it had still not run one (`20260924-NOTICE-paper-books-system-test-running.md`). "Automatic" is not met on a machine that sleeps. | Needs an always-on host (see "Infrastructure") |
| O5 | P1 | **Models are RESEARCH_ONLY.** No edge after costs. Copying any model-driven book with real money is outside what the evidence supports. | Standing finding, not a defect |
| O6 | P2 | No delivery channel. No email, push or messaging exists in the code. For "automatic", the owner must open the app after each close. | Feature work |
| O7 | P2 | The NSE holiday calendar covers **2026 only**. The scheduled runner refuses a date outside the covered years, so it stops on **2027-01-01** unless the 2027 list is fetched. | NSE blocked from here |
| O8 | P2 | Log lines hardcode the label "IST" on `%(asctime)s`, which is local time. Observed in this container: `16:53:50 IST` when it was 22:23 IST. Audit logs on any non-IST host are mislabelled (`scripts/run_paper_pilot_session.py:67`). One-line fix: an IST `Formatter.converter`. | File sits under 25 active claims |
| O9 | P2 | `--upstox-token` on the command line puts the token in the process list and shell history. Prefer the environment variable or `.env`. | Claimed file |
| O10 | P2 | Shariah backend still returns `verification_status: "VERIFIED"` on every audit line and a hardcoded `estimated_dividend_purification_ratio=0.0042` and hand-typed charge rates (`baskets.py`), duplicating the effective-dated cost engine in `analytics/nse_rules.py`. | Backend of another product line; UI is now honest, data is not |
| O11 | P3 | Two Linux-red tests left in files that other records claim: `tests/test_release_packaging.py::test_setup_gui_components` (needs `tkinter`) and `tests/test_windows_installer.py` (needs `pefile`, fails at collection). The repo's Playwright e2e config is Windows and Edge only. `mypy` needs `--platform win32` to be meaningful off Windows. | Claimed paths |
| O12 | P3 | Release is DUE per `AGENTS.md` (24 user-visible changes, 2 security). I cannot cut it: `scripts/release.ps1` builds the Windows installer. `release_status.py` also reports "No release yet" because this clone has no tags, so its count is unreliable here. | Windows-only |
| O13 | P3 | Inline text links stay under 44 px ("Open", "Add holdings"). Allowed by WCAG 2.5.8 for inline links, below Apple's guideline. | Cosmetic |
| O14 | Design note | `AGENTS.md` asks for a "Zero-Dependency Fallback" in `SYNTHETIC_MODE`; the live paper session deliberately has none (it refuses without a token). Fail-closed is right for money-adjacent code. The law's wording should say the retail app and backtests, not the live session. | Needs your decision |

## Mode A, as it now works

1. A paper book follows a rule on real prices: decide at a close, fill at the next open, exact NSE charges, slippage as set.
2. `Tomorrow's orders` shows **Current** only if no trading session has passed since the close the orders were decided at. Otherwise **Out of date**, quantities collapsed, copy and CSV withheld, with the cause (your data is old, or the reference series lags).
3. Enter your own account size. Shares scale and round down. Copy as text or download a CSV.
4. You place the orders yourself. QuantOS connects to nothing.

What Mode A still lacks for a serious owner: a push or email at 18:00 IST with the list, a "placed / not placed" record, and a tracking-error view (your fills against the paper fills). Those are the features that turn a copy ticket into a workflow.

## Mode B, if you want it

Not built. Before any of it, separately: (1) a T4 charter, (2) threat model for credential custody (the key never in the repo, never in logs, revocable, ideally held by the broker's own consent screen), (3) per-order or per-basket confirmation by the owner as the default, daily loss and order-count caps, a kill switch that works when the app is closed, immutable order audit, (4) a red-team pass. A middle path worth building first is **confirm-each-basket**: QuantOS prepares the basket, you approve it in your broker's own screen. It gives the benefit without the platform ever holding trading authority.

## Regulatory flags (not legal advice; my knowledge of Indian rules may be out of date as of this date)

- **Personal use only.** The retail-redesign record already adopted "no feature that sells or publishes recommendations or black-box strategies to others (SEBI RA/IA/algo rules)". If "the user" means *other people's* accounts following signals you publish, that is the research-analyst and investment-adviser regime, whatever the UI calls it. Get counsel before that.
- **Direct order placement for retail clients** now runs under the exchanges' and SEBI's retail algorithmic-trading framework (broker-registered algos, static-IP binding). `.env.example` already records an Upstox endpoint that answers only from a configured static IP. Check the current circular before Mode B.

## Infrastructure: "Microsoft-grade" gap list

What is genuinely good: CSRF on every write, host-header check, CSP, `nosniff`, frame deny, localhost-only, typed error envelope with request ids, immutable hash-addressed evidence store, Decimal ledger with daily reconciliation, risk governor, fail-closed data guards, 2,500+ tests, seven Red Team rounds on record.

What an enterprise or bank buyer would ask for and this does not have: sign-in and roles, SSO (Entra), tenancy, audit-log export and retention, encryption at rest for the evidence store, liveness, readiness and metrics probes on the main app (`/api/v2/status` and `/api/v1/diagnostics` report application state; they are not probes, and only the Shariah sub-app has `/health`), a hosted always-on runtime (service, not a laptop scheduled task), a clean API surface (129 paths: `/api/v1`, `/api/v2` and unversioned legacy duplicates side by side), a CI that does not stop on billing (recurred 2026-09-18) and branch protection (blocked on the plan: `403 Upgrade to GitHub Pro`).

## Recommended order

1. Push or merge `claude/amazing-lamport-e18bd1` (O1), so the live dashboard works.
2. Run one governed live paper session on your machine with `UPSTOX_ANALYTICS_TOKEN`, then commission an independent adjudication of the live path (O2, O3).
3. Move the unattended run off the laptop (O4) and fetch the 2027 holiday list before December (O7).
4. Add the 18:00 IST order notification, a placed/not-placed record and tracking error (O6).
5. Cut the release from your Windows install root (O12).
6. Decide Mode B only after 1–4, with its own charter.

## Gates after the change

| Gate | Result |
|---|---|
| `pytest tests` (first pass, minus the Windows-installer file) | 2,513 passed, 1 failed (`tkinter`, claimed file), 15 skipped |
| `ruff check .`, `ruff format --check .` | clean |
| `mypy` strict | no new error; the 17 Linux-only errors are unchanged and none is in a file I changed |
| `tsc --noEmit`, `vitest run`, `vite build` | clean; 44 tests |
| Browser audit, 52 pages | 0 axe violations, 0 console or network errors, 0 overflow |
| `detect-secrets` on changed files | 0 candidates |
| Mutation checks on the freshness guards | both mutants killed (4 and 1 failing tests), then restored |

Raw per-page results: `ui_audit_before.json`, `ui_audit_after.json`. Screenshots: `shots/`.

## Windows CI on the pull request

The `gates` run on commit `603318f3` (https://github.com/uninestindia-crypto/mizan/actions/runs/37354317272): **Static gates, Craft checkers and audits (including the PowerShell claims and disk-layout audits), Tests (forward order), Tests (reverse order) and the aggregate `gates` all passed.** Two earlier runs were red and are explained in the follow-up table: the first on a wall-clock latency test in forward order (fixed by warming up in the measured shape), and one commit that added a harness script ruff rejected (fixed before the run above).

## Limits of this audit

- Nothing was run against a live broker feed. Findings O2 and O3 stay open until someone does.
- "Apple-grade" and "Microsoft-grade" are partly taste and partly procurement. I measured accessibility, layout, speed,
  console cleanliness and security headers, and looked at the screenshots. I did not user-test anything.
- The audit used the repo's tracked market data (to 2026-09-29), not a fresh download, so the "6 days old" banner is real.
- `scripts/audit-agent-claims.ps1`, `scripts/audit-disk-layout.ps1` and `scripts/release.ps1` were not run (no PowerShell).
