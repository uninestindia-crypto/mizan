# How QuantOS screens a stock for the Shariah mode

Methodology version: `shariah-screen-v1`

Written 2026-10-07 from the code in `src/quant_system/shariah/`, not from memory. If this page and the code ever
disagree, the code is what ran, and this page is wrong: a test (`tests/shariah/test_halal_methodology_doc.py`)
fails when a threshold or a keyword below drifts from the code.

## The short version

- QuantOS checks a company two ways, a market-value way (called AAOIFI-style here) and a book-value way (called
  TASIS-style here). It first checks what the company does, then four ratios.
- The result is a **screening aid, not a fatwa and not financial advice**. No scholar has reviewed these rules or
  any result.
- The figures behind every result are a **hand-entered sample of 39 companies** from one filing season (12 April to
  25 May 2024). They were not read from audited filings, and nobody has checked them against filings. Every result
  therefore carries the status `UNVERIFIED_SAMPLE`.
- There is **no refresh schedule**. Nothing updates the figures. Nothing here is real time.
- The computer decides the result by fixed arithmetic. An AI assistant may explain a result. It cannot change one.

Open question: which published standard text each threshold below should be taken from, and who signs it off.
See "Open questions" at the end. This page does not settle it.

## Step 1: what the company does (the sector test)

The sector test reads three pieces of text from the company's row: its sector, its industry and its business
summary. It makes them lower case and joins them. A company is screened out by the first rule below that finds one
of its words. The word is plain text search, so a word inside a longer word can also match.

| Rule | Screens out | Sector names that fire it | Words that fire it |
|---|---|---|---|
| `interest_based_finance` | Conventional banking, lending and insurance (Riba) | `financial services`, `banking`, `insurance` | `commercial bank`, `retail lending`, `housing finance`, `nbfc - consumer lending`, `life insurance`, `general insurance` |
| `alcohol` | Making or selling liquor and beer (Khamr) | none | `distilleries, breweries`, `alcoholic beverages`, `liquor`, `spirits`, `brewery`, `distillery`, `beer`, `imfl` |
| `tobacco` | Making or selling tobacco and nicotine products (Dharar) | none | `cigarettes, tobacco`, `cigarette`, `tobacco`, `cigars`, `gutkha` |
| `gambling` | Casinos, lotteries and real-money gaming (Maysir/Qimar) | none | `casinos, gaming`, `casino`, `gambling`, `lottery`, `real-money gaming`, `real money gaming` |
| `cinema` | Showing films commercially | none | `cinema`, `film exhibition` |

One exemption: a company whose sector is `information technology` or `it` passes the sector test, unless its text
contains `casino`, `gambling` or `betting`. If it does, the five rules above are applied to it as usual. (The word
`betting` blocks the exemption but is not itself one of the rule words, so a software company described only as
"betting" would still pass. This is a known gap.)

The result of the sector test is stored in the company's row when the sample is loaded, and the verdict uses that
stored answer. Every screening result says which rule fired and which word it matched on (`sector_rule`).

### What is not screened

These are **not screened today**. There is no rule for them:

- pork and pork products
- weapons and defence (an old table in the code listed "defense & weapons", but nothing ever used it, so it was
  removed)
- adult entertainment
- media and entertainment other than cinemas
- any business line that the sector, industry and summary text does not mention

The sector test looks at words, not at how much of a company's revenue comes from a business line. The only
revenue-based test is the 5% income ratio in step 2.

Open question: whether pork, weapons and other lines should be added as rules. This page records what is true
today and does not decide it.

## Step 2: four ratios

All four must be under their limit. The test is strict: a ratio exactly at the limit fails. Each ratio is the
company's figure divided by a denominator, rounded to six decimals.

| Ratio | Divided by (AAOIFI-style) | Divided by (TASIS-style) | Limit | Warning starts at |
|---|---|---|---|---|
| Interest-bearing debt | 36-month average market capitalisation | total assets | 33% | 32% |
| Cash and interest-bearing investments | 36-month average market capitalisation | total assets | 33% | 32% |
| Trade receivables | 36-month average market capitalisation | total assets | 33% | 32% |
| Impermissible income | total revenue | total revenue | 5% | 4.5% |

What the figures are:

- **Interest-bearing debt** is the row's `total_debt` figure as typed in the sample. The sample lists long-term
  borrowings, short-term borrowings and lease liabilities as its parts.
- **Cash and interest-bearing investments** is the row's `total_cash_and_investments` figure: cash, bank balances
  and debt securities or liquid investments.
- **Trade receivables** is `total_receivables`.
- **Impermissible income** is `total_impermissible_income`: interest income plus revenue from any prohibited
  segment, as typed in the sample.
- **36-month average market capitalisation** is a number stored in the sample row (`avg_36m_market_cap`). It is
  **not computed** from price history.
- If a denominator is zero or negative, the ratio is treated as 100% when the figure is above zero, and 0%
  otherwise. It fails closed.

### The warning band

A ratio that passes but is at or above its "warning starts at" figure makes the result **Questionable**. For the
three 33% ratios the band is one percentage point wide (32% up to, but not including, 33%). For the 5% income
ratio it is half a point wide (4.5% up to, but not including, 5%). This is a fixed band. It is not based on how
volatile the share price is.

## Step 3: the result

Each standard gets one of three results, in this order:

1. **Non-compliant** if the sector test failed, or if any of the four ratios is at or over its limit.
2. **Questionable** if nothing failed but any ratio is in its warning band.
3. **Compliant** otherwise.

When both standards are asked for, the combined result is Non-compliant if either is, otherwise Questionable if
either is, otherwise Compliant. If the two standards disagree, the screen says so and gives the reason, because they
use different denominators.

Every result also carries: how far its figures have been checked (`data_status`, always `UNVERIFIED_SAMPLE` today),
the methodology version, the time it was screened, the sector rule, and a short list of what it does not cover. The
stock list, the search suggestions, the company page and each basket stock carry the same `data_status`.

## Data

| Question | Answer today |
|---|---|
| Where do the figures come from? | Typed in by hand, in `src/quant_system/shariah/db/seed_data.py`, loaded into the tracked sample database `data/shariah/halal_stocks.db` |
| How many companies? | 39 |
| Which period? | Filing dates 12 April to 25 May 2024; the rows say "Q4 FY24" |
| Are the figures checked against filings? | No. The rows name an annual report as their source, but nobody has read it against the figures |
| How are the prices? | Hand-entered sample prices, not live prices |
| How often is it refreshed? | Never. There is no refresh schedule |
| Data status | `UNVERIFIED_SAMPLE` for every row |

There are more than 3,000 listed NSE stocks. The other 3,000+ are not covered.

## Purification of dividends

Purification is the share of a dividend that comes from impermissible income, to be given away.

- The ratio is impermissible income divided by total revenue, stored in the company's row. (The code also holds
  the same sum written as interest income plus prohibited-segment revenue, divided by total revenue.)
- Gross dividend is the dividend per share times the shares held, rounded to two decimals, unless a gross figure is
  entered.
- Payable is the gross dividend times the ratio, rounded to two decimals. What remains is the part you may keep.
- If a stock is **not in the sample**, the calculator uses a stand-in ratio of 0.58% (taken from one sample
  company) instead of refusing. It is an assumed figure, not a measured one.

### The ledger of purifications

Each entry you record is chained to the one before it with a SHA-256 fingerprint. Each entry says which hash
version wrote it (`hash_version`).

- **Version 1** (every entry made before versions existed) covers the entry id and the payable amount.
- **Version 2** (every new entry) covers the entry id, the ticker, the gross dividend, the purification ratio, the
  payable amount and the time, plus the fingerprint of the entry before it.
- Checking the ledger uses each entry's own version, so older ledgers still check out and no old entry is
  rewritten.
- The chain shows that an entry was **not edited afterwards**. It is not a signature, so someone who could rewrite
  every later entry could recompute the whole chain. Version 2 does not cover the number of shares, the dividend
  per share, the amount you may keep, the company name, the dates, the charity, the status or the notes. Version 1
  covers less.

In the Shariah mode this ledger is the only place a fingerprint chain is used. The screening figures are not
fingerprint-verified, and no step verifies them against filings.

## Zakat on shares

- **Active trader method:** the zakatable base is the portfolio value (the total you enter, or the market value of
  the holdings you list) plus cash.
- **Long-term investor method:** the base is, for each holding, the shares times the stock's zakatable net working
  assets per share (never below zero), plus cash. The per-share figure in the sample is (cash and investments +
  receivables + inventories - current liabilities) divided by shares outstanding. If a stock is not in the sample
  and no figure is entered, the code assumes **25% of the share price** is zakatable. If only a total portfolio
  value is entered, it assumes **25% of that total**. Both are assumptions, not measurements.
- **Rate:** 2.5% for the lunar year; 2.577% for the solar year. The code's comment derives the solar rate as 2.5%
  times 365.25 / 354, which is 2.579%; the number in the code (2.577%) is closer to 2.5% times 365 / 354 (2.578%).
  They differ by a few thousandths of a point.
- **Nisab** (the minimum): Rs 53,550, which the code works out as 595 grams of silver at Rs 90 a gram. It is a fixed
  number with no date, and silver prices move. You can enter your own nisab. Zakat is due on the base only if the
  base reaches the nisab.

## Limits

- A screening aid, not a fatwa. **No scholar has reviewed these thresholds, the sector rules or any result.**
- Hand-entered sample data, not audited, not live, not refreshed.
- It does not look at every income line. Only the lines typed into the sample are counted.
- It does not say whether a share will go up or down. It says nothing about returns, and QuantOS does not claim
  that screened shares do better than others.
- QuantOS does not place orders. The order sheet is a file you take to your own broker.

## Open questions

These need a person's decision. The code and this page do not settle them.

- Open question: which published standard text does each threshold come from? The code uses 33% for debt, cash and
  receivables and 5% for impermissible income, and a compliant result can say "AAOIFI Standard No. 21". The review
  (`reports/halal_docs_review/REVIEW.md`, section 2, row 7) recalls that the AAOIFI standard uses 30% limits and no
  receivables ratio, and says this was not checked against the primary text. Until it is, "AAOIFI-style" is the
  honest label for what the code does.
- Open question: will a scholar or a board review the thresholds and the sector rules, and who?
- Open question: which source of real company filings should replace the 39-company sample? Everything beyond
  honest labelling depends on it.
- Open question: should pork, weapons and other business lines be added to the sector rules?
- Open question: which silver weight and which dated silver price should the nisab use, and who confirms it?

## For reviewers: the exact constants

These are the values the code uses (`src/quant_system/shariah/core/config.py`). A test compares each line to the
code.

| Constant | Value | As a percentage |
|---|---|---|
| `MAX_DEBT_RATIO` | 0.33 | 33% |
| `MAX_CASH_RATIO` | 0.33 | 33% |
| `MAX_RECEIVABLES_RATIO` | 0.33 | 33% |
| `MAX_IMPERMISSIBLE_REVENUE_RATIO` | 0.05 | 5% |
| `WARN_DEBT_RATIO` | 0.32 | 32% |
| `WARN_CASH_RATIO` | 0.32 | 32% |
| `WARN_RECEIVABLES_RATIO` | 0.32 | 32% |
| `WARN_IMPERMISSIBLE_REVENUE_RATIO` | 0.045 | 4.5% |
| `DEFAULT_SILVER_NISAB_INR` | 53550.0 | Rs 53,550 |

Each limit divides as shown in step 2 (`src/quant_system/shariah/services/screener_service.py`). The sector rules are
in `src/quant_system/shariah/services/sector_rules.py`.

## Change log

| Version | Date | What changed |
|---|---|---|
| `shariah-screen-v1` | 2026-10-07 | First written methodology. Rules and thresholds are those the code already had. The unused "defense & weapons" table was removed; it never screened anything. |
