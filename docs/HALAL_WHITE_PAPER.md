# QuantOS and Halal Investment: the manifesto

**Vision, not a description of what ships.**

**Status of the Shariah mode today:** Working prototype on a 39-company illustrative sample. Not live, not audited.

This is the corrected, editable source of the manifesto. It replaces the wording of the earlier PDF,
`docs/QUANT_OS_HALAL_INVESTMENT_MOONSHOT.pdf`, whose source text is not in the repository and which still carries
claims that this version corrects. Open question: regenerate that PDF from this text, or withdraw it. That is a
decision for the founder; the PDF has not been changed.

How the Shariah screen actually works, with every threshold, is in `docs/HALAL_METHODOLOGY.md`. Where this paper and
that page disagree, that page (which a test keeps in line with the code) is right.

## How to read this paper

Every capability below carries one label, with a link to the code.

| Label | Meaning |
|---|---|
| **SHIPPED** | The feature exists in the code and does what its line says. It does not mean the data behind it is verified. |
| **PARTIAL** | Part of it exists. The line says which part. |
| **PLANNED** | Nothing exists yet. It is a hope, not a feature. |

A figure marked **(unverified, source needed)** has no source anywhere in the repository. Do not quote it.

## What exists and what does not

| Capability | Label | What is true | Code |
|---|---|---|---|
| Two-way screening (AAOIFI-style, TASIS-style) | PARTIAL | Works by fixed arithmetic on a hand-entered 39-company sample, all `UNVERIFIED_SAMPLE`. No scholar has reviewed the thresholds. | `src/quant_system/shariah/services/screener_service.py` |
| Sector rules | PARTIAL | Banking and insurance, alcohol, tobacco, gambling, cinemas. **Not** pork, weapons or other lines. | `src/quant_system/shariah/services/sector_rules.py` |
| Line-item evidence for each ratio | PARTIAL | Each ratio shows its numbers and line items, all marked as unverified sample figures. | `src/quant_system/shariah/services/screener_service.py` (`build_audit_evidence_lines`) |
| "Cryptographic line-item verification" | PLANNED | No verification step exists. Nothing checks a line item against a filing. | none |
| Purification ledger with a SHA-256 chain | SHIPPED | A chain that detects edits made after an entry was written. New entries cover six figures; older ones cover two. It is not a signature. | `src/quant_system/shariah/services/ledger_hash.py` |
| Dividend purification calculator | PARTIAL | Correct arithmetic on the sample ratio. A stock outside the sample gets a stand-in ratio of 0.58%. | `src/quant_system/shariah/services/purification_service.py` |
| Zakat on shares, two methods | PARTIAL | The formulas exist. The nisab is a fixed, undated figure. Some inputs are assumed when missing. | `src/quant_system/shariah/services/zakat_service.py` |
| Four curated baskets | PARTIAL | Names, weights and each stock's sample screening. No return, risk or history is shown, because none exists. | `src/quant_system/shariah/services/basket_service.py` |
| Portfolio tear-sheets with performance | PLANNED | No return or risk figure has been computed for any basket. | none |
| Order-sheet export for four brokers | SHIPPED | Writes a file of share counts. **QuantOS does not place orders.** Prices are samples, so counts are examples. | `src/quant_system/shariah/services/broker_export_service.py` |
| Halal Wealth Academy (four modules) | PARTIAL | Written by engineers. A scholar has not reviewed the fiqh content. | `src/quant_system/shariah/services/academy_service.py` |
| Cash-only Demat setup guide | PARTIAL | Step lists for four brokers. Not checked against each broker's current screens. | `src/quant_system/shariah/services/academy_service.py` |
| Exact Decimal accounting, a pre-trade risk governor, next-bar backtesting | SHIPPED | Part of the QuantOS engine. They are not specific to the Shariah mode. | `src/quant_system/core/ledger.py`, `src/quant_system/risk/governor.py`, `src/quant_system/backtest/engine.py` |
| Real-time compliance, a continuous drift monitor, intraday alerts | PLANNED | No such code exists. See "Planned" below. | none |
| Cross-platform Flutter client | PARTIAL | A `client/` folder exists but is not what ships. The shipped app is a React desktop app. | `frontend/`, `client/` |
| Halal PMS or AIF vehicles, sukuk pools, tax routing | PLANNED | Nothing exists. | none |
| Other markets (Gulf, South-East Asia, UK, US) | PLANNED | Nothing exists. | none |

## The central hypothesis

*A hypothesis, not a finding.* Shariah screens exclude highly indebted and interest-dependent companies. Some
published factor research associates low leverage, tangible assets and profitability with better risk-adjusted
returns (for example the Fama-French five-factor model, the "Quality Minus Junk" work of Asness and co-authors, and
Novy-Marx on gross profitability). Whether a Shariah screen captures any of that, in India, after costs, is untested.
QuantOS has tested nothing of the kind and **claims no performance advantage**. Its own research program found no
strategy edge that survives real costs (`agent_context/GOAL.md`, section 3).

## Executive prologue

QuantOS is built to tell an investor the truth about an idea before real money is at risk. The Shariah mode applies
that to a specific question: does this share pass a published-style Shariah screen, and how sure are we? It uses
fixed rules, exact decimal accounting and an honest label on every result.

The earlier text spoke of mobilising "50+ trillion rupees of stagnant capital held by 200 million Indian Muslims into
high-alpha equity partnerships". That figure and the group size are **(unverified, source needed)**, and no
high-alpha claim is made here.

| Section | Topic |
|---|---|
| 1 | The problem with how Islamic finance is sold |
| 2 | Weaknesses of screeners, and what QuantOS does about them |
| 3 | The Indian context |
| 4 | The hypothesis and the engine's rules |
| 5 | Formulas, as implemented |
| 6 | Architecture and the baskets |
| 7 | Education and onboarding |
| 8 | Planned work |
| 9 | Open questions |

## 1. The problem with how Islamic finance is sold

The size of the global Islamic finance industry is given in the earlier text as $4.5 trillion in one place and as a
$5.9 trillion projection for 2026 in another. Neither is sourced, and the two were never reconciled. Both are
**(unverified, source needed)**.

The earlier text argued that much of modern Islamic banking copies conventional debt through structures such as
organised tawarruq and commodity murabaha, and that products are priced against conventional benchmarks. These are
the author's opinions about a field of fiqh. They are not findings of QuantOS and QuantOS takes no position on them.

- The claim that over 70% of Islamic banking assets sit in such structures is **(unverified, source needed)**.
- The claim that a "cartel of 20-30 individuals" holds hundreds of board seats and that scholars are paid by the
  institutions they certify is an allegation about real people. It is **(unverified, source needed)** and must not
  be repeated without evidence.

## 2. Weaknesses of screeners, and what QuantOS does about them

- **Quarterly data.** A screener that reads quarterly reports can lag a company's real position by up to a quarter.
  QuantOS has the same lag, and today it is worse: its data is a one-off sample from April to May 2024.
- **A hard line.** The code passes a ratio only if it is **strictly under 33%** (5% for impermissible income). A
  company at 32.9% passes and one at 33.1% fails, and so does one at exactly 33.0%. QuantOS adds a fixed warning band
  of one percentage point (32% to 33%) that returns "Questionable". It is a fixed band, **not** one based on how
  volatile the price is. The earlier text called the line "33.33%"; the code uses 0.33.
- **Two denominators.** AAOIFI-style screening divides by a 36-month average market capitalisation; TASIS-style
  screening divides by total assets. A share can pass one and fail the other. QuantOS shows both and says why they
  differ. The 36-month figure is a stored number in each sample row, not computed from price history.
- **Purification.** The earlier text claimed that over 97% of retail investors fail to purify dividends correctly.
  That is **(unverified, source needed)**.

## 3. The Indian context

- India's Muslim population is described as 200 million, 14.2% of the population, with market participation "under
  2%". Each of these figures is **(unverified, source needed)**.
- The earlier text said Indian Muslims hold "50+ trillion rupees ($600 billion)" in idle cash, gold and bank
  accounts, and that inflation of 7 to 9% halves purchasing power every 8 to 10 years. The holdings figure is
  **(unverified, source needed)**, and the inflation range is **(unverified, source needed)**.
- Investment scams that target religious trust are real, and the earlier text named three. Its amounts and counts
  are **(unverified, source needed)**: the Bengaluru IMA case at "over 4,000 crore rupees from 50,000+ families",
  "Ambidant 800 crore rupees" and "Heera Gold 5,600 crore rupees".
- Standard Demat accounts offer margin trading with interest, the earlier text said at "12 to 18%", which is
  **(unverified, source needed)**, and derivatives trading, said to have a "93% loss rate per SEBI", which is
  **(unverified, source needed)**.

## 4. The hypothesis and the engine's rules

The central hypothesis is stated above. The earlier section titled "Empirical Proof" has been withdrawn. It leaned on
the Tata Ethical Fund (launch date, benchmark and "multi-decade outperformance" all **(unverified, source needed)**)
and on a "55% fall in 2008" for the NIFTY 50, which is **(unverified, source needed)**. QuantOS has not analysed that
fund, and a single fund is not proof of anything.

What the engine does enforce, which is part of the QuantOS engine and not specific to the Shariah mode:

- **Exact decimal accounting:** money is held as fixed-point decimals, not floating-point numbers
  (`src/quant_system/core/ledger.py`). SHIPPED.
- **Pre-trade risk governor:** orders pass a risk check first (`src/quant_system/risk/governor.py`). SHIPPED.
- **No look-ahead:** a signal on one bar is acted on at the next bar's open
  (`src/quant_system/backtest/engine.py`). SHIPPED.
- **A drift monitor** that tracks enterprise value and debt through the day is **PLANNED**. It was listed as a core
  invariant in the earlier text. No such code exists.

## 5. Formulas, as implemented

### 5.1 Sector rules and ratios

A company is screened out by sector if its sector, industry or business summary contains the words of any of these
rules: banking and insurance, alcohol, tobacco, gambling, cinemas. The exact words are listed in
`docs/HALAL_METHODOLOGY.md`. **Pork, weapons, adult entertainment and non-cinema media are not screened.** The
earlier text said they were "strictly filtered"; they were not.

| Ratio | AAOIFI-style divides by | TASIS-style divides by | Limit |
|---|---|---|---|
| Interest-bearing debt | 36-month average market capitalisation | total assets | under 33% |
| Cash and interest-bearing investments | 36-month average market capitalisation | total assets | under 33% |
| Trade receivables | 36-month average market capitalisation | total assets | under 33% |
| Impermissible income | total revenue | total revenue | under 5% |

Open question: which published standard text each limit comes from. The code calls its result "AAOIFI Standard
No. 21"; the review of this paper recalls that the standard uses 30% limits and no receivables ratio, and says this
was not checked against the primary text. Until it is, "AAOIFI-style" is the honest label.

### 5.2 Dividend purification and the ledger

- Purification ratio = (interest income + prohibited revenue) / total revenue.
- Purification payable = ratio x gross dividend, where gross dividend = dividend per share x shares held. (The
  earlier text multiplied by the shares held a second time.)
- Each ledger entry is chained to the one before it. New entries (hash version 2) hash the previous hash, the entry
  id, the ticker, the gross dividend, the ratio, the payable amount and the time. Older entries (version 1) hash
  only the id and the payable amount, and still check out. This shows an entry was not edited afterwards. It is not
  a signature, so someone who could rewrite every later entry could recompute the whole chain.

### 5.3 Zakat on shares

- Method A, active trader: portfolio value plus cash.
- Method B, long-term investor: for each holding, shares times the stock's zakatable net working assets per share
  (never below zero), plus cash. In the code, net working assets per share = (cash and investments + receivables
  + inventories - current liabilities) / shares outstanding. The earlier text omitted cash, investments and
  inventories from this line.
- Rate: 2.5% for the lunar year, 2.577% for the solar year (the figure in the code).
- Nisab: a fixed figure of Rs 53,550, worked out in the code as 595 grams of silver at Rs 90 a gram. It has no date,
  and silver prices move. You can enter your own. Open question: which silver weight and which dated price should be
  used, and who confirms it.

## 6. Architecture and the baskets

The Shariah engine is a Python service with a SQLite database and a DuckDB analytics file. The app people use is a
React desktop app. The earlier text called the client "Apple-grade Flutter" with "137/137 backend tests passing" and
"a verified sub-50 ms response time". The test count is out of date and is dropped here. Response times were measured
on development hardware and vary by machine. One build run measured above 50 ms. **No speed is promised.**

### The four baskets

The code defines four baskets: Halal Tech Giants, Shariah High-Growth Champions, Green & Ethical Infrastructure and
the NIFTY Shariah 25 Index Basket. The earlier text called two of them by other names.

- They list stocks and weights, and show each stock's sample screening result and how far its figures are checked.
- **No return, risk or history is shown**, because none has been computed or recorded. The earlier "real-time
  portfolio tear-sheets", assumed return and Sharpe figures, and written rebalance history were removed.
- The NIFTY Shariah 25 basket currently lists six stocks with weights adding to 38%. It is not a 25-stock basket.

### Order-sheet export (QuantOS does not place orders)

The export turns an amount of capital into share counts and writes a file in the format of Zerodha, Upstox, Groww or
AngelOne, using the delivery product only. It sends nothing to a broker and cannot block what you do in a broker's
own app. Prices are sample prices, so the counts are examples.

## 7. Education and onboarding

- **Halal Wealth Academy:** four modules (stewardship and inflation, equities as partnerships, riba, gharar and
  maysir, and ten principles). PARTIAL: a scholar has not reviewed the content.
- **Cash-only Demat guide:** steps to switch off margin, derivatives and share lending, and to link a savings
  account. PARTIAL: the steps are not checked against each broker's current screens.

## 8. Planned work

Everything here is **PLANNED**. Nothing exists.

- **Real filing data.** Replace the 39-company sample with figures read from real filings, with the source document
  and a fingerprint per figure, so that a row earns `VERIFIED_FILING` only when its numbers tie back to the filing.
- **Daily recompute.** Compute the 36-month average from price history after each close, and flag shares that enter
  the warning band or change status between filings.
- **Indicative intraday view.** A provisional ratio during the session, labelled as indicative, never as a status
  change. The earlier text called this "real-time compliance governance" and a "continuous drift monitor".
- **Governance.** A published methodology with a version and change log, reviewed by a named scholar or board.
- **Later.** Factor models, systematic investment plans, regulated Halal PMS or AIF vehicles, sukuk pools, charity tax
  routing, and other markets. The earlier text quoted "7 to 9% yields" for sukuk pools, which is
  **(unverified, source needed)**. QuantOS makes no yield claim.

## 9. Open questions

These need a person's decision. This paper does not settle them.

- Open question: which published standard text does each threshold come from, and will a scholar review the
  thresholds and the sector rules?
- Open question: which source of real company filings replaces the sample? NSE and BSE filings are candidates; what
  they expose in machine-readable form has not been checked. A paid data vendor is the alternative.
- Open question: should pork, weapons and other business lines be added to the sector rules?
- Open question: regenerate the PDF from this text, or withdraw it?

## What this paper does not claim

It does not claim a profit, a return, a risk figure, a speed, a ruling, or that any share is "halal". It claims that
QuantOS applies fixed, published rules to figures, shows its working, and says how little those figures have been
checked.

> "And say: Truth has come, and falsehood has vanished. Indeed, falsehood is bound to vanish." (Holy Quran, Surah
> Al-Isra, 17:81)
