# Shariah mode everywhere, and real filing proof on every stock

DATE: 2026-10-07
GOAL_LINE: G2 (Mizan Shariah mode is a real mode of the one app), G6 (retail benefit), tripwire 4 (never present an
unproven result as an edge; never present a screen as a fatwa)
OWNER_RECORD: `agent_context/work/active/20261007-claude-shariah-mode-and-filing-proof.md`
SUPERSEDES NOTHING: it builds on `20261007-halal-transparency-contract.md` (Stage 0) and is Stage 1 of
`reports/halal_docs_review/REVIEW.md` section 4. Founder decision recorded here: the source for real filings is the
results that companies file on NSE (public, machine-readable XBRL). Source choice was the review's open point 3; the
founder's instruction on 2026-10-07 (users want real data and proof) settles it. A named scholar review of thresholds
(review point 2 and 4) is still open and is never implied.

## What users asked for (founder, 2026-10-07)

1. When a person selects Shariah, **everything** follows Shariah: not only one page.
2. Clicking any stock tells them, **with real data and proof**, why it is compliant and why it is not.

## What is true today (measured before designing)

- "Shariah mode" is only a route: `Layout.tsx` `isShariah = location.pathname.startsWith("/shariah")`. The saved
  setting `shariah_mode` only decides which nav items show. Home, search, stock pages, rankings and paper books ignore it.
- Verdicts come from 39 hand-entered sample rows (`UNVERIFIED_SAMPLE`). Real filings differ (the TCS September 2024
  consolidated filing has zero borrowings; the sample has 7,970 crore of lease liabilities counted as debt).
- NSE publishes each company's results as XBRL, reachable without a login:
  `GET https://www.nseindia.com/api/corporates-financial-results?index=equities&symbol=<SYM>&period=Quarterly` (a JSON
  list; each row has `toDate`, `relatingTo`, `consolidated`, `indAs`, `audited`, `filingDate`, `xbrl`, `isin`).
  The `xbrl` file of the **September and March** filings carries the balance sheet; other quarters do not. Needs a
  browser-like `User-Agent`; some other NSE and BSE endpoints answer 403. Never call it from a test.
- A real filing (`INDAS_112733_...xml`) holds, in INR (not crore): `Assets`, `BorrowingsCurrent`, `BorrowingsNoncurrent`,
  `CashAndCashEquivalents`, `BankBalanceOtherThanCashAndCashEquivalents`, `CurrentInvestments`, `NoncurrentInvestments`,
  `TradeReceivablesCurrent`, `TradeReceivablesNoncurrent`, `RevenueFromOperations`, `OtherIncome`, `FinanceCosts`,
  `PaidUpValueOfEquityShareCapital`, `FaceValueOfEquityShareCapital`, and (cash-flow, year-to-date)
  `AdjustmentsForInterestIncome`. Contexts: `OneI` = balance-sheet date; `OneD` = the quarter; `FourD` = year to date.
  Lease liabilities are **not** itemised in the results filing.

## The rules (do not weaken)

1. **The deterministic screener decides; nothing an AI says changes a verdict.** Same as Stage 0.
2. **Real figures only, with proof.** Every figure shown on a verdict carries: the XBRL tag it was read from, the value
   in rupees as filed, the period, the date it was filed, the link to the filing on NSE, and the SHA-256 of the file as
   fetched. A person can open the filing and check. No figure is shown without these.
3. **`data_status` is earned.** `VERIFIED_FILING` only when the figures were read from an NSE-published XBRL whose hash
   is recorded **and** the filing ties out against itself (current + non-current assets = total assets, required lines
   present, units sane). `STALE` when the newest balance sheet is older than 18 months. `UNVERIFIED_SAMPLE` for the old
   hand-entered rows. A company with no filing data and no sample row is **`NOT_SCREENED`**: never guessed, never shown
   as compliant.
4. **When the filing does not say, say so, and do not guess either way.** Two figures are not itemised in the results
   filing, so each gets a lower and an upper bound and the verdict is decided on both:
   - *Cash and interest-bearing securities*: lower = cash + other bank balances; upper = lower + all current and
     non-current investments (the filing does not split debt securities from equity).
   - *Impermissible (interest and similar) income*: lower = `AdjustmentsForInterestIncome` when present, else 0; upper =
     `OtherIncome` (it includes interest, dividends and gains). Total revenue = `RevenueFromOperations` + `OtherIncome`.
   - Debt = `BorrowingsCurrent` + `BorrowingsNoncurrent`; lease liabilities are not itemised and are stated as not
     counted.
   Verdict combination: both bounds pass -> `COMPLIANT`; both fail -> `NON_COMPLIANT`; they differ ->
   `QUESTIONABLE` with the plain sentence "The filing does not break this figure down, so QuantOS cannot say which side
   of the limit this company is on." The thresholds themselves are unchanged (`core/config.py`).
5. **Two denominators, as today.** TASIS uses book total assets (`Assets`). AAOIFI uses the 36-month average market
   capitalisation: average of the platform's own daily closing prices over the last 36 months x shares in issue, where
   shares = `PaidUpValueOfEquityShareCapital` / `FaceValueOfEquityShareCapital`. If the platform holds no price history
   for the stock, the AAOIFI column says "needs price history" and only TASIS is decided. State in `not_covered` that
   share count is the filed one, not adjusted for later buybacks or issues.
6. **Sector test first, as today** (`sector_rules.py`). A company whose business fails the sector rule is
   `NON_COMPLIANT` without needing its balance sheet; its proof says which rule and which word.
7. **Banks and other lenders** file a different XBRL format. They fail the sector rule, so their balance sheet is not
   read; the proof says so.
8. **Nothing here says "approved", "certified" or "halal guaranteed".** Every verdict says it is a screening aid, not a
   fatwa, and that no scholar has reviewed the thresholds (`not_covered`).

## Data layout

- Bundled, tracked, read-only: `data/shariah/filings_snapshot.json.gz` -- real figures extracted at build time for the
  research universe and the sample names, dated, each row with the proof fields above. Works on a factory-new laptop
  with no internet and in the cloud (no credentials needed).
- Per-user, writable, never tracked: `<state_dir>/shariah_filings.sqlite` -- filings fetched from NSE from inside the
  app (on demand for one stock, or a refresh of the screened list). A newer filing replaces an older one for a symbol.
- Fetching is only ever triggered by a button in the app (No-Terminal Law), runs as a background job with progress,
  is polite (one request at a time, a pause between requests, no retries on 403), and fails in plain words.

## API (all additive; all under the existing Shariah API prefix `/api/v2/shariah`)

- `GET /stocks/{symbol}/proof` -> `StockProof`:

  ```json
  {
    "symbol": "TCS", "company_name": "Tata Consultancy Services Limited",
    "verdict": "COMPLIANT | NON_COMPLIANT | QUESTIONABLE | NOT_SCREENED",
    "headline": "plain sentence: why it is / is not compliant",
    "data_status": "VERIFIED_FILING | STALE | UNVERIFIED_SAMPLE | NOT_SCREENED",
    "data_notice": "plain words",
    "methodology_version": "shariah-screen-v2",
    "screened_at": "ISO-8601 UTC",
    "sector": {"compliant": true, "rule": null, "matched_keyword": null, "reason": null, "sector": "...", "industry": "..."},
    "filing": {"source_url": "...", "detail_url": "...", "period_end": "2024-09-30", "period_label": "Six months ended 30 Sep 2024",
               "filed_on": "2024-10-10", "consolidated": true, "audited": false, "sha256": "...", "tie_out": {"ok": true, "checks": [{"name": "...", "ok": true, "detail": "..."}]}},
    "standards": [
      {"standard": "AAOIFI", "status": "COMPLIANT|NON_COMPLIANT|QUESTIONABLE|NOT_COMPUTED", "summary": "...",
       "tests": [
         {"key": "debt", "title": "Debt compared with market value", "limit_pct": 33.0, "warning_pct": 30.0,
          "result": "PASS|FAIL|BORDERLINE|DEPENDS|NOT_COMPUTED",
          "low": {"pct": 0.0, "numerator_cr": 0.0, "denominator_cr": 0.0}, "high": {"pct": 0.0, "numerator_cr": 0.0, "denominator_cr": 0.0},
          "plain": "Debt is 0.0% of market value, against a 33% limit.",
          "inputs": [{"label": "Borrowings, non-current", "xbrl_tag": "BorrowingsNoncurrent", "value_inr": 0, "value_cr": 0.0, "role": "numerator"}]}
       ]},
      {"standard": "TASIS", "...": "same shape"}
    ],
    "divergence": {"noted": false, "explanation": null},
    "what_would_change_it": ["plain sentences, e.g. how far a ratio is from its limit"],
    "not_covered": ["plain sentences"],
    "sample_comparison": {"differs": true, "note": "plain words"} 
  }
  ```

  Nothing in `inputs` without `xbrl_tag`, `value_inr` and a `filing` block above it. `low` and `high` are equal when the
  figure is exact.
- `GET /status?symbols=TCS,INFY,...` (max 200) -> `{ "statuses": { "TCS": {"verdict": "...", "data_status": "...", "short": "plain reason, under 90 characters", "as_of": "2024-09-30"} } }`.
  One cheap call for badges and filters. Unknown symbol -> `NOT_SCREENED`.
- `POST /filings/fetch` `{symbol}` -> `202 {job_id}` (one stock, live from NSE); `POST /filings/refresh` -> `202 {job_id}`
  (every stock the app tracks and every stock already screened, polite); `GET /filings/jobs/{job_id}` -> `{status:
  running|done|failed|cancelled, done, total, message, failures:[{symbol, reason}]}`; `DELETE` cancels. Plain-language
  messages only. 429 if one is already running.
- `GET /filings/coverage` -> `{screened, total_listed, newest_filing, snapshot_built_on}` for a "what is covered"
  line.

## Mode (frontend)

- **Mode = the saved setting `shariah_mode`** (true = Mizan Shariah). Both mode buttons write it, then go to that mode's
  home. The `/shariah` pages stay reachable in either mode through the switch, and the route no longer decides the mode.
- In Shariah mode, every place that lists or opens stocks is filtered and labelled by verdict:
  - a **verdict badge** next to every stock symbol (Compliant, Not compliant, Questionable, Not screened), with the data
    status in its tooltip text, never colour alone;
  - lists (watchlist, search suggestions, rankings, picks, baskets, paper-book holdings and queued orders) **hide
    stocks that are not Compliant by default**, and say how many are hidden with one control: "Show N hidden stocks".
    Hidden stocks are never deleted or sold: a paper book keeps what it holds (GOAL tripwire 8), the holdings table
    just labels them;
  - a stock's own page opens with the **proof panel** first; a non-compliant stock stays viewable, with its reason on
    top;
  - adding a non-compliant or not-screened stock to a watchlist asks first, in plain words;
  - the Copilot is told the mode, leads with the screener's verdict for any stock it names, and second opinions always
    include the halal section.
- In Quant mode nothing is filtered; the badge is still available on the stock page's proof panel.
- Words: "Screened from the company's own filing" never "certified"; "Not screened yet" never "Not halal".

## What stays open (founder / scholar)

Thresholds and the AAOIFI text (review point 2), who reviews (point 4), Stage 2 daily recompute, Stage 3 intraday
indicative ratios. The treatment of lease liabilities and of equity investments inside "cash and investments" is a
scholarly question; this work states it and brackets it instead of choosing silently.
