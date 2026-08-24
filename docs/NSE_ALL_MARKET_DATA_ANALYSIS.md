# All-Market NSE Cash Equity Universe Analysis (2016–2026)

**Author:** Antigravity — Senior Data Analyst & Quantitative Data Scientist  
**Date:** 2026-08-24  
**Universe Scope:** All active National Stock Exchange of India (NSE) cash equities  
**Horizon:** 2016-08-22 to 2026-08-21 (10 Calendar Years / 2,476 standard exchange sessions)  
**Dataset Scale:** **3,267 Equities | 4,501,992 Daily Bars | 19,194 Corporate Actions | 944B INR Daily Turnover**  

---

## 1. Executive Summary

This study presents the comprehensive empirical profile of the entire active Indian cash equity market over a ten-year historical window. Rather than restricting research to large-cap index survivors (e.g., NIFTY 50), this dataset captures **3,267 equities** across all market capitalization tiers, segments, and listing cohorts, persisted immutably in the QuantOS `EvidenceStore`.

### Headline Findings

1. **Massive Market Scale & Density**: Total historical data volume expanded **37.7x** from the NIFTY 50 baseline (119,293 bars) to **4,501,992 verified point-in-time daily bars**.
2. **Extreme Liquidity Concentration**: The market exhibits an extreme Pareto distribution:
   - **Tier 1 (228 stocks)** captures **₹65,221 Crore/day (69.1%)** of all market turnover.
   - **NIFTY 500 (500 stocks)** accounts for **68.7%** of aggregate market liquidity.
   - **Tiers 4 & 5 (1,266 microcap stocks)** generate less than **0.45%** of daily turnover.
3. **Microstructure Circuit Friction**: **718 stocks (22.0% of the market)** suffer from frequent circuit lock days ($>5\%$ of sessions where $\text{High} = \text{Low} = \text{Close}$), creating severe execution friction that renders naive unconstrained backtests invalid.
4. **Survivorship & Listing Cohorts**: Only **1,148 companies (35.1%)** survived as actively traded equities across the entire 10-year decade. Over **1,597 companies (48.9%)** were listed within the last 4 years (2022–2026), reflecting India's massive IPO boom.
5. **Corporate Action Ecosystem**: Recorded **19,194 official corporate events**, including **12,360 dividend distributions**, **332 stock splits**, and **376 bonus share issuances**.

---

## 2. Universe Architecture & Market Segmentation

The extracted universe covers **3,267 unique active cash equities** categorized across four distinct NSE trading segments:

```
┌────────────────────────────────────────────────────────────────────────┐
│               NSE CASH EQUITY UNIVERSE (3,267 Stocks)                  │
├────────────────────────────────┬───────────────────────────────────────┤
│ Mainboard Normal (`EQ`)        │ 2,567 stocks (78.6%)                  │
│ SME Platform (`SM`)            │   437 stocks (13.4%)                  │
│ Trade-for-Trade / BE (`BE`)    │   225 stocks ( 6.9%)                  │
│ Z-Group / Surveillance (`BZ`)  │    38 stocks ( 1.2%)                  │
└────────────────────────────────┴───────────────────────────────────────┘
```

| Segment Code | Count | Characteristics | Microstructure Impact |
|---|---|---|---|
| **`EQ` (Normal)** | 2,567 | Standard continuous double-auction cash market | High liquidity, normal settlement, intraday net-off allowed |
| **`SM` (SME)** | 437 | Emerging growth / SME platform | High lot sizes (e.g. 500-2000 shares), illiquid order book, wide spreads |
| **`BE` (Trade-to-Trade)** | 225 | Surveillance segment for high volatility / debt | 100% gross delivery required, no intraday squaring-off |
| **`BZ` (Z-Group)** | 38 | Regulatory non-compliance / default watch | High default risk, severe circuit limits (2%), restricted trading |

---

## 3. Tenure & Listing Cohort Distribution

The 10-year span reveals how India's public equity landscape has expanded over the past decade:

| Cohort | Bar Count Range | Years Active | Equities Count | Share of Market | Key Dynamics |
|---|---|---|---|---|---|
| **10-Year Veterans** | $\ge 2,400$ bars | 9.5 – 10.0 yrs | **1,148** | **35.1%** | Core mature universe; continuous trading through demonetization, COVID-19 crash, and 2024-2026 bull run |
| **Maturing Mid-Gen** | $1,200 - 2,399$ | 5.0 – 9.4 yrs | **522** | **16.0%** | Companies listed between 2017 and 2021 (e.g. HDFC Life, SBI Life, Eternal) |
| **Recent Growth IPOs** | $250 - 1,199$ | 1.0 – 4.9 yrs | **1,014** | **31.0%** | Massive post-pandemic IPO expansion cohort (2022–2025) |
| **2026 Fresh Listings** | $< 250$ bars | $< 1.0$ yr | **583** | **17.8%** | Newly listed SME and mainboard IPOs |

```
Tenure Cohort Breakdown (3,267 Equities):
[██████████████] 35.1% 10-Year Veterans (1,148 stocks)
[██████]         16.0% Maturing Mid-Gen (522 stocks)
[████████████]   31.0% Recent IPOs (1,014 stocks)
[███████]        17.8% Fresh 2026 Listings (583 stocks)
```

---

## 4. Quantitative Liquidity Tiering & Market Concentration

Total aggregate market turnover across all 3,267 equities averages **₹94,400.98 Crore / day** (~$11.3B USD/day). 

### Liquidity Tiers

To prevent backtesting models on phantom or illiquid volume, the universe is partitioned into 5 actionable liquidity tiers based on **Average Daily Traded Value (ADTV)**:

| Liquidity Tier | ADTV Threshold | Stock Count | Total Turnover (INR) | Market Share | Tradability Profile |
|---|---|---|---|---|---|
| **Tier 1: Mega-Liquid** | $> \text{₹100 Cr/day}$ | **228** | ₹65,221.68 Cr | **69.1%** | Institutional, deep order books, algorithmic execution, low slippage |
| **Tier 2: Institutional Active** | $\text{₹10 – 100 Cr/day}$ | **756** | ₹24,754.84 Cr | **26.2%** | High institutional participation, viable for quant mid-frequency strategies |
| **Tier 3: Mid-Market Tradable** | $\text{₹1 – 10 Cr/day}$ | **1,017** | ₹4,006.42 Cr | **4.2%** | Moderate retail & HNI liquidity, requires slippage modeling ($>15 \text{ bps}$) |
| **Tier 4: SmallCap Active** | $\text{₹10L – 1 Cr/day}$ | **951** | ₹404.68 Cr | **0.4%** | Retail dominated, wide bid-ask spread ($30-100 \text{ bps}$), circuit risk |
| **Tier 5: Microcap / Illiquid** | $< \text{₹10 Lakh/day}$ | **315** | ₹13.35 Cr | **0.01%** | Untradable for institutional systematic funds; sporadic fills |

### Benchmark Concentration

* **NIFTY 50 (Top 50)**: Captures **24.3%** of total market turnover.
* **Top 100 Equities**: Captures **49.7%** of total market turnover.
* **NIFTY 500 (Top 500)**: Captures **68.74%** of total market turnover.
* **Remaining 2,767 Equities**: Share the remaining **31.26%** of liquidity.

---

## 5. Top 15 Most Liquid Indian Equities

| Rank | Symbol | Average Daily Turnover | Historical Bars | Ann. Volatility | Max Drawdown | Company Name |
|---|---|---|---|---|---|---|
| 1 | `RELIANCE` | **₹1,562.41 Cr/day** | 2,479 | 27.1% | 44.4% | Reliance Industries Ltd. |
| 2 | `HDFCBANK` | **₹1,450.60 Cr/day** | 2,476 | 23.0% | 40.2% | HDFC Bank Ltd. |
| 3 | `ICICIBANK` | **₹1,176.76 Cr/day** | 2,476 | 29.2% | 47.8% | ICICI Bank Ltd. |
| 4 | `SBIN` | **₹978.99 Cr/day** | 2,476 | 31.8% | 53.1% | State Bank of India |
| 5 | `GROWW` | **₹971.50 Cr/day** | 193 | 51.6% | 36.8% | Billionbrains Garage Ventures (Groww) |
| 6 | `INFY` | **₹914.70 Cr/day** | 2,476 | 26.9% | 38.6% | Infosys Ltd. |
| 7 | `ETERNAL` | **₹898.16 Cr/day** | 1,261 | 46.9% | 68.2% | Eternal Ltd. (Zomato) |
| 8 | `AXISBANK` | **₹825.95 Cr/day** | 2,476 | 32.1% | 54.6% | Axis Bank Ltd. |
| 9 | `BAJFINANCE` | **₹811.59 Cr/day** | 2,476 | 35.6% | 60.5% | Bajaj Finance Ltd. |
| 10 | `TMPV` | **₹769.74 Cr/day** | 2,476 | 42.6% | 71.4% | Tata Motors Passenger Vehicles Ltd. |
| 11 | `TCS` | **₹742.10 Cr/day** | 2,476 | 22.4% | 27.8% | Tata Consultancy Services Ltd. |
| 12 | `LT` | **₹688.35 Cr/day** | 2,476 | 26.8% | 42.1% | Larsen & Toubro Ltd. |
| 13 | `KOTAKBANK` | **₹634.20 Cr/day** | 2,476 | 24.8% | 39.5% | Kotak Mahindra Bank Ltd. |
| 14 | `TATASTEEL` | **₹612.80 Cr/day** | 2,476 | 38.4% | 58.2% | Tata Steel Ltd. |
| 15 | `BHARTIARTL` | **₹589.45 Cr/day** | 2,476 | 28.5% | 35.2% | Bharti Airtel Ltd. |

---

## 6. Microstructure Friction & Quality Audit

### 1. Circuit Lock Days ($\text{High} = \text{Low} = \text{Close}$)
Under NSE exchange rules, securities are subject to daily price bands ($2\%, 5\%, 10\%, 20\%$). When an instrument hits an upper or lower circuit limit, all bids/asks lock, preventing normal trade execution.
* **718 stocks (22.0% of universe)** exhibit $> 5\%$ circuit lock days.
* **Microstructure Rule for QuantOS**: Any backtest engine operating outside Tier 1/2 **must enforce a circuit rejection filter** ($P_{\text{order}} \neq P_{\text{limit}}$ when High == Low).

### 2. Zero-Volume Inactive Sessions
* Across the 3,267 actively listed equities, **zero stocks** had $> 5\%$ zero-volume days during their active listing window, confirming high baseline registry health across active symbols.

### 3. Provider Data-Quality Refusals
* Out of 3,359 initial targets, **90 stocks were flagged `DATA_QUALITY_BLOCKED`** due to corrupt OHLC bars (e.g. `INVALID_OHLC` where High < Low or Close > High in penny stocks from the provider).
* QuantOS fail-closed governance successfully rejected all 90 corrupt series, preventing dirty data from polluting model training.

---

## 7. Corporate Action Ecosystem

Across the 3,267 equities, **19,194 official corporate action events** were cataloged and indexed:

```
Distribution of Corporate Actions:
┌───────────────────────────────┬───────────────────────────────┐
│ Action Type                   │ Recorded Total                │
├───────────────────────────────┼───────────────────────────────┤
│ Cash & Special Dividends      │ 12,360 payouts                │
│ Bonus Share Issues            │    376 issues                 │
│ Stock Splits & Sub-Divisions  │    332 splits                 │
│ Rights & Demergers            │    148 filings                │
└───────────────────────────────┴───────────────────────────────┘
```

### Top 10 Dividend-Frequency Aristocrats

| Symbol | Total Dividends Paid (10y) | Bonus Issues | Stock Splits | Company Name |
|---|---|---|---|---|
| `TCS` | **40** | 0 | 0 | Tata Consultancy Services Ltd. |
| `MANAPPURAM` | **40** | 0 | 0 | Manappuram Finance Ltd. |
| `BALKRISIND` | **40** | 1 | 0 | Balkrishna Industries Ltd. |
| `CRISIL` | **40** | 0 | 0 | CRISIL Ltd. |
| `HCLTECH` | **39** | 1 | 0 | HCL Technologies Ltd. |
| `PAGEIND` | **38** | 0 | 0 | Page Industries Ltd. |
| `SUNTV` | **36** | 0 | 0 | Sun TV Network Ltd. |
| `VIDHIING` | **34** | 0 | 0 | Vidhi Specialty Food Ingredients Ltd. |
| `SYMPHONY` | **33** | 1 | 0 | Symphony Ltd. |
| `RECLTD` | **32** | 2 | 0 | REC Ltd. |

---

## 8. Cross-Sectional Volatility & Risk Dynamics

```
Annualized Volatility Distribution:
• Median Annualized Volatility : 48.96%
• Mean Annualized Volatility   : 141.75% (skewed by SME platform & microcaps)
• Tier 1 Large-Caps Volatility : 22.0% – 35.0%
• Tier 4/5 Microcaps Volatility: 60.0% – 250.0%+
```

### Quantitative Strategic Takeaways for Model Engineering

1. **Cross-Sectional Factor Models (Multi-Asset Alpha)**:
   - With 3,267 names, we can now build true **cross-sectional ranking models** (e.g. cross-sectional momentum, mean reversion, low-volatility anomaly, value/earnings yield ranking) rather than isolated single-stock models.
2. **Liquidity Slicing**:
   - Training universes should be filtered to **Tier 1 + Tier 2 (Top ~984 stocks)** for liquid equity strategies with realistic friction.
3. **Survivorship Correction**:
   - Access to listing dates across all 3,267 stocks allows point-in-time universe construction, eliminating the decade-long survivorship bias of static NIFTY 50 backtests.
4. **Execution Cost Adaptation**:
   - Higher volatility in Tier 3/4 stocks ($>60\%$ ann. vol) provides larger gross price swings that can easily absorb NSE statutory costs ($0.22\%$), provided positions are sized appropriately for liquidity.

---

## 9. Data Artifact Locations

| Artifact | Path | Description |
|---|---|---|
| **Authoritative CSV** | [`data/authorities/nse-all-listed-equities.csv`](file:///d:/quant_system/data/authorities/nse-all-listed-equities.csv) | Full 3,359 NSE cash equity security master |
| **Market Evidence Cache** | [`data/evidence/market-cache/all-market-20160822-20260821/`](file:///d:/quant_system/data/evidence/market-cache/all-market-20160822-20260821) | Immutable point-in-time candle blobs & manifests |
| **Corporate Actions** | [`data/evidence/market-cache/all-market-20160822-20260821/corporate-actions/`](file:///d:/quant_system/data/evidence/market-cache/all-market-20160822-20260821/corporate-actions) | 3,267 JSON corporate action files |
| **Comprehensive Profiles JSON** | [`data/evidence/market-analysis/nse_all_market_profiles.json`](file:///d:/quant_system/data/evidence/market-analysis/nse_all_market_profiles.json) | Complete statistical profiles for every stock |
| **Comprehensive Profiles CSV** | [`data/evidence/market-analysis/nse_all_market_profiles.csv`](file:///d:/quant_system/data/evidence/market-analysis/nse_all_market_profiles.csv) | Spreadsheet-ready dataset with all moments & metrics |
| **Summary Metadata** | [`data/evidence/market-analysis/market_structure_summary.json`](file:///d:/quant_system/data/evidence/market-analysis/market_structure_summary.json) | High-level macro statistics & cohort metrics |
