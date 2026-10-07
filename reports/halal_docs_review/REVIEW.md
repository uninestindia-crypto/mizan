# Halal investment docs: what to change, and how to implement real transparency

Reviewed 2026-10-06 against the code at `0a22d7c9` (v2.4.0 plus PR #4). GOAL lines served: G2 (Mizan mode), G5 (honest
evidence), G6 (benefit to retail users). `[file:line]` references let you check any statement.

**This is a review, not a religious ruling.** I checked the documents against what the software does. I did not check
any company's filings, and I am not qualified to rule on fiqh. Where a point needs a scholar or the primary standard, I
say so.

---

## 1. The verdict in six lines

1. **The app is more honest than the docs.** The Shariah page already says *"Sample data, not live and not audited ...
   Do not buy, sell or avoid a share on the strength of a verdict shown here"* [frontend/src/pages/Shariah.tsx:87-93].
   The white paper and README say the opposite ("Shipped & Live", "Pre-audited").
2. **The data is 39 hand-entered sample companies**, from one filing season (12 Apr to 25 May 2024), every audit line
   labelled `UNVERIFIED_SAMPLE` [shariah/schemas/screening.py:36-41]. There are 3,000+ listed NSE stocks.
3. **Four headline claims are not built:** "cryptographic line-item verification", "real-time compliance", the
   "continuous drift monitor", and the weapons/pork screens.
4. **Performance claims have no evidence behind them:** "Shariah alpha", "empirical proof", and basket "Assumed CAGR /
   Sharpe" that are typed-in constants. The project's own goal file forbids describing anything as an edge without
   evidence (`agent_context/GOAL.md`, tripwire 4).
5. **Two numbers disagree between doc and code** (the 33.33% vs 33% threshold, and what the purification hash covers).
6. **"Real time" is reachable, but only in stages**, and the first stage is real filing data, not code (section 4).

---

## 2. Claim by claim: what the doc says, what the software does, what to write instead

Severity: **HIGH** = a reader could make a religious or money decision on a false statement. **MED** = misleading.
**LOW** = tidy-up.

| # | Doc says (source) | What the software does | Verdict | Change the doc to say | Sev |
|---|---|---|---|---|---|
| 1 | "Phase 1: **Shipped & Live**: Dual-Screener, 4 Baskets, SHA-256 Ledger, Zakat Engine" (white paper §8); "**Pre-audited** halal_stocks.db" (README:43) | 39 companies, one filing season, hand-entered, not read from filings, not live. The app says so itself. | **False as worded** | "Working prototype on a 39-company illustrative sample. Not live, not audited." | HIGH |
| 2 | "Dual AAOIFI & TASIS **with Cryptographic Line-Item Verification**" (cover) | Every audit line carries `UNVERIFIED_SAMPLE`; *no verification step exists*. The SHA-256 chain exists only in the **purification ledger**. | **False** | Remove from the cover. Say: "Each ratio shows its line items; none are verified yet." | HIGH |
| 3 | "**Real-Time** Compliance Governance" (subtitle); "**Continuous Compliance Drift Monitor**: intraday enterprise value and debt tracking" (§4.2) | No drift or intraday code in `src/quant_system/shariah/`. The doc's own roadmap lists it as Phase 2 "near-term", so §4.2 contradicts §8. | **Not built** | Move it to "Planned". Describe the staged route in section 4 below. | HIGH |
| 4 | "Systematic **Shariah Alpha**", "high-alpha equity partnerships", "**Empirical Proof**" (§4.1), "superior long-term risk-adjusted returns" (§4) | No evidence in the repository. The Tata Ethical Fund comparison and the "-55% in 2008" figure carry no source. The project's own research found no strategy edge that survives real costs (`GOAL.md` §3). | **Unsupported** | Recast as a *hypothesis*: "Low-leverage, tangible-asset companies have historically ...", with citations, or delete. Never "alpha" or "proof". | HIGH |
| 5 | "Real-time portfolio tear-sheets" for 4 baskets (§6); in-app "Assumed CAGR 26.4%, Sharpe 1.45" | `expected_cagr`, `expected_sharpe`, `max_drawdown`, `beta` are **typed constants** in `basket_service.py:25-160`, as are the prices (e.g. TCS 4,210.50). Rebalance logs dated 2026-06-30 and 2026-09-30 describe "Quarterly Rebalancing", and the first says *"Verified full AAOIFI and TASIS screening compliance"*; these are written text, not recorded events. | **Fabricated-looking performance and history** | Remove the assumed numbers and the invented rebalance history until they are computed from real data. | HIGH |
| 6 | "Prohibited sectors (banking, insurance, alcohol, gambling, **pork**, tobacco, **weapons**, non-halal media) are strictly filtered" (§5.1) | Keyword rules cover banking, financial services, insurance, liquor, tobacco, gambling, cinema. The `PROHIBITED_SECTORS` table (including "defense & weapons") is **defined but never used**; "pork" appears nowhere. [screener_service.py:12-23, 31-96] | **Partial** | List exactly what is screened today. Add pork and weapons, or say they are not. | MED |
| 7 | AAOIFI column: debt, cash and receivables each "**< 33.33%** of the 36-month average market cap" (§5.1) | Code uses **0.33**, not 0.3333 [shariah/core/config.py], so a company at 33.2% is "compliant" per the doc and "non-compliant" in code. The verdict string says "Fully Compliant with **AAOIFI Standard No. 21**". | **Mismatch, and see the note below** | Make doc and code agree, and cite the exact source text for every threshold. | MED |
| 8 | Ledger hash = SHA-256(prev ‖ UUID ‖ **Ticker ‖ GrossDiv ‖ ρ ‖ Payable ‖ Timestamp**) (§5.2) | Code hashes only `prev | uuid | amount` [purification_service.py:64-70]. Ticker, dividend, ratio and time are **not covered**, so they could be altered without breaking the chain. | **Doc overstates tamper-evidence** | Best fix is in code: hash all the fields the doc lists. Otherwise correct the doc. | MED |
| 9 | "Silver Nisab ₹53,550" (§5.3, UI) | A fixed constant, "595 g x ₹90/g" [shariah/core/config.py], no date. Silver prices move, and nisab sources commonly quote a different silver weight. | **Stale by design** | Compute from a *dated* silver price, show the date and grams, keep the user override (it already exists). A scholar should confirm the weight. | MED |
| 10 | "**1-Click Zero-Margin Broker Execution**" (§6, §7 title) | Builds order *sheets* (CSV/payload) for four brokers. QuantOS never places orders, and the app disables the sheets while prices are samples. | **Misleading name** | "One-click order-sheet export. QuantOS does not place orders." | MED |
| 11 | "Apple-grade **Flutter** client; **137/137** backend tests passing" (§8) | The installed app is the React desktop app. A Flutter folder exists (`client/`) but is not what ships. The test figure is long out of date. | **Stale** | Describe the shipped app; drop the number or date it. | LOW |
| 12 | "Verified **sub-50 ms** SLA (measured p95 3.5 to 22 ms)" (§6) | The repo's own latency test asserting p95 < 50 ms failed once on CI at 57.6 ms. | **Too strong** | "Measured on development hardware; varies by machine." | LOW |
| 13 | Unsourced figures: $4.5T vs $5.9T (**inconsistent**, cover vs §1), "70% of Islamic bank assets", "97% of investors fail to purify", "under 2% participation", "₹50+ trillion idle", the fraud amounts | None are cited anywhere in the repository. | **Unverified** | Cite each or remove it. Fix the $4.5T / $5.9T conflict. | MED |
| 14 | Methodological divergence: AAOIFI uses a **36-month average market cap**, TASIS uses **total assets** (§2, §5.1) | Matches the code (`avg_36m_market_cap` vs `total_assets`). But the 36-month figure is a *stored number in the sample row*, not computed, although the app holds ten years of daily prices. | **True** | Keep. Add: "computed from price history" once it is. | LOW |
| 15 | "Binary cliff ... screeners lack volatility buffers" (§2) | Code has a fixed 1 point warning band (32% to 33%) that returns "Questionable" [screener_service.py:~165]. That is a buffer, but not a volatility-based one. | **Half true** | Describe the actual band. | LOW |
| 16 | Purification ρ = (interest + prohibited revenue) / total revenue (§5.2) | Matches the code [purification_service.py:46-61]. | **True** | Keep. | n/a |

**A note on row 7, stated as a question rather than a finding.** I believe the AAOIFI Shari'ah Standard (No. 21) uses
**30%** limits for interest-bearing debt and for interest-bearing deposits, each against market capitalisation, a **5%**
limit on impermissible income, and **no receivables ratio**; the 33% limits and a receivables test appear in several
index providers' methodologies. I did not have the primary text in this session, so **please verify before relying on it.**
If the product uses a blend of methods, the honest label is "AAOIFI-style screening with these exact rules", followed by
the list. Calling it "AAOIFI Standard No. 21" is a claim a scholar can check and hold you to.

---

## 3. What users should be told, and how to build it

The rule to apply: **the deterministic screener decides; everything else explains.** Nothing the Copilot or any AI says
may change a verdict.

### 3.1 A "How this verdict was reached" panel on every stock

| Show | Why | Where it comes from today |
|---|---|---|
| Verdict **per standard** (AAOIFI-style, TASIS-style) and the one-line reason | The two can disagree; hiding that is the failure the white paper complains about | `evaluate_company_shariah` already returns both and a `divergence_reason` |
| Each ratio: **numerator, denominator, formula, threshold, headroom** | So a user can redo the sum | `RatioMeter` already carries all of these |
| The **sector test**: which rule matched, and the text it matched on | Keyword rules can misfire; show them | `check_sector_compliance` returns the reason only; add the matched keyword |
| **Provenance:** source document, reporting period, filing date, and a **data status** badge | The single most important honesty item | `source_document`, `reporting_period`, `filing_date` exist; add `data_status` |
| **Data status values:** `VERIFIED_FILING` / `UNVERIFIED_SAMPLE` / `STALE` (older than N days) | Today everything is `UNVERIFIED_SAMPLE` and the UI should say so on the verdict itself, not only in a banner | extends the existing constant |
| **Screened at** (timestamp) and **methodology version** | "As of when, by which rules" | new fields |
| **What this does not cover** (e.g. "no scholar ruling, no review of every income line") and "a screening aid, not a fatwa" | Sets expectations correctly | static text, owned by one methodology file |
| **History of status changes** per stock | Shows drift over time | new table |

### 3.2 One source of truth for "how it works"

Create `docs/HALAL_METHODOLOGY.md` (plain language: standards used, every threshold with its citation, the sector rules,
data sources, refresh schedule, limits). The app's "Learn how this works" link and the Copilot's explanations both read
it. The white paper becomes a *vision* document with a header: **"Vision, not a description of what ships."**

### 3.3 Status labels in the docs

Give every capability one of `SHIPPED`, `PARTIAL`, `PLANNED`, with a link to the code or the issue. That alone would have
prevented rows 1, 2, 3 and 6.

---

## 4. "It should work in real time": what it would actually take

Real time cannot be coded in before there is real data. Staged:

| Stage | What | Needs | Founder decision? |
|---|---|---|---|
| **0: Honesty (days)** | Align the docs with the app (section 2). Remove the assumed CAGR/Sharpe and the invented rebalance history. Put `data_status` on the verdict. | Nothing external | Approve removing the assumed numbers |
| **1: Real filing data** | Replace the 39-row sample with figures read from actual filings: debt, cash and investments, receivables, revenue, interest income, total assets, shares outstanding. Store the source document and a hash per figure. A row earns `VERIFIED_FILING` only when its numbers tie back to the filing. Start with the liquid universe. | **A source for filings.** NSE/BSE result filings or XBRL are candidates; *I have not verified what they expose*, and a paid vendor is the alternative. This is the long pole. | **Yes: which source, and who reviews** |
| **2: Daily recompute** | AAOIFI-style denominators use a 36-month average market cap. The app already holds ten years of daily prices, so after each close, recompute the average from price history x shares and re-run the ratios. Flag stocks entering the warning band or flipping status between filings. | Stage 1 data | None |
| **3: Intraday, indicative only** | With live Upstox prices (task B), show a **provisional** market-cap-based ratio during the session, labelled "indicative; the official status changes only on filings". | Stage 2 and live quotes | Whether to show provisional values at all |
| **4: Governance** | Publish the methodology with a version and change log; a named scholar or board reviews thresholds and sector rules. | A person | **Yes** |

**Where the Copilot fits:** it reads the panel in section 3.1 and *explains* it ("TCS passes because debt is 0.4% of
total assets, against a 33% limit; this figure is from a FY24 sample, status UNVERIFIED_SAMPLE"). It never produces a
ratio, never overrides a verdict, and puts the data status first when the data is a sample.

---

## 5. Decisions for the founder

1. **Remove now?** Basket "Assumed CAGR/Sharpe", the invented rebalance history, and the "Pre-audited" and "Shipped &
   Live" wording. (Recommended: yes. All four contradict the app's own banner.)
2. **Which standard text do you cite**, and will a scholar review the thresholds (row 7)?
3. **Which source for real filings** (Stage 1)? Everything in section 4 after Stage 0 depends on this.
4. **Rename "1-Click Execution"** to order-sheet export (row 10)?
5. **Fix the purification hash in code** so it covers every field the doc lists (row 8)? Recommended.

## 6. What I did not verify

- No filing, price or ratio was checked against an outside source. I did not read any company's actual accounts.
- The AAOIFI threshold question (row 7) rests on my recollection of the standard, not the primary text.
- Whether NSE or BSE publish the line items in a usable machine-readable form (Stage 1).
- Zakat method details beyond the nisab constant, and the Academy's fiqh content, which needs a scholar, not an engineer.
- The older static Shariah page (`shariah/static/index.html`) and the Flutter client's own text.
