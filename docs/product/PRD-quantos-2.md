# QuantOS 2.0 — Product requirements (retail release R1)

STATUS: BUILD CONTRACT for branch `claude/retail-redesign`  
DATE: 2026-09-28  
OWNER: founder; drafted by Claude Code from the founder's brief ("primary function of the platform
is profit for retail traders and retail investors") and the defaults recorded in
`agent_context/work/active/20260928-claude-retail-redesign-build.md`.

## 1. Promise

> **Know before you risk real money, and keep more of what you make.**

Indian retail traders mostly lose money: SEBI's studies found roughly 9 in 10 individual F&O
traders lose. The causes are ones software can fix: costs they never see, oversized positions,
strategies nobody tested honestly, and tips. QuantOS 2.0 attacks those causes with real NSE data,
exact statutory costs, honest statistics, and paper trading before real money.

QuantOS never implies an edge that the evidence does not show. That is the product's
differentiator, not a disclaimer.

## 2. Users

| Persona | Holds for | Wants |
|---|---|---|
| **Priya, long-term investor** | months to years | Is my portfolio beating NIFTY after costs? Which holdings are weak? Would a simple rule have done better? |
| **Arjun, swing trader** | days to weeks | Find setups, test a rule on 10 years before risking money, exact costs and position size, paper trade first. |

## 3. Non-goals for R1

- Placing real orders (T4 not authorized; paper only).
- Intraday or F&O signals.
- Recommendations or strategies published to other people (SEBI RA/IA/algo rules).
- Broker holdings sync, in-app market-data download (R2; R1 links an existing QuantOS data folder).
- Mobile app (the web-first frontend keeps it possible).

## 4. Screens and acceptance criteria

Every criterion is testable. "Given/When/Then" is abbreviated to the observable outcome.

### 4.1 First run
- A1. With no settings saved, the app opens a 4-step setup: style (Investor / Swing trader / Both),
  money rules (capital, risk per trade %, daily loss limit %), market data (detected folder or
  choose one; build the index with a visible progress bar), done.
- A2. The setup shows the not-investment-advice notice once and records that it was shown.
- A3. Every step can be skipped; skipping data leaves every data screen in a clear "Connect market
  data" empty state, never an error.

### 4.2 Home
- B1. Shows the market data as-of date. Data older than 3 trading days shows an amber banner with
  the age.
- B2. Market pulse: NIFTYBEES change over 1D/1M/1Y; breadth (% of the liquid universe above its
  200-day average; advancers vs decliners on the last session).
- B3. My portfolio summary (value, day change, total P&L, vs NIFTY) or an invitation to add holdings.
- B4. Watchlist with price, 1D change and a 3-month sparkline.
- B5. Paper books: read-only status with the label "Market plus costs; not evidence of model skill".

### 4.3 Markets (screener)
- C1. Universes: Liquid (the 423-name research universe), NIFTY 500, All listed.
- C2. Preset screens: Near 52-week high, Strong 6-month momentum, Low volatility, Biggest 1-month
  fallers, Above 200-day average, plus free sorting on every column.
- C3. Columns: symbol and name, price, 1D, 1M, 6M, 1Y, volatility (1Y annualized), distance from
  52-week high, average daily turnover (₹ crore). Search by symbol or name.
- C4. 3,000+ rows scroll smoothly.

### 4.4 Stock
- D1. Price chart with candles/line toggle, volume, 50/200-day averages, ranges 1M 6M 1Y 5Y Max.
- D2. Stats: returns, volatility, max drawdown, 52-week range, average turnover, beta vs NIFTYBEES.
- D3. Corporate actions from the NSE authority file; demergers and other unresolved actions are
  highlighted with the warning that price history around them is not comparable.
- D4. Actions: add to watchlist, add to portfolio, test a strategy on this stock, cost to trade.

### 4.5 Strategy Lab
- E1. Template gallery: Buy and hold, Trend following (moving average), 52-week breakout,
  Momentum rotation (monthly top N), Pullback (RSI). Each card says in plain words what it does,
  when it tends to fail, and its typical holding period.
- E2. Configure: one stock or a universe, parameters with bounded inputs, period, capital,
  position size, broker charges from settings.
- E3. Runs on **real cached NSE daily bars only**. Orders fill at the **next session's open**. No
  look-ahead.
- E4. Every fill pays the effective-dated NSE statutory charges (`NSERuleEngine`) for its trade date,
  plus configured brokerage and slippage. Total charges paid are shown.
- E5. The benchmark (NIFTYBEES buy-and-hold, same dates, same cost basis) is always shown.
- E6. The verdict uses the deflated Sharpe probability of the strategy's **excess daily returns over
  the benchmark**, with the number of trials = every lab run the user has made. Levels:
  "Lost to NIFTY" / "No real evidence it beats NIFTY" / "Promising, not proven" /
  "Evidence of an edge — paper trade it next" (probability ≥ 0.95, the platform gate). The words
  "profitable", "guaranteed" and "sure" never appear.
- E7. Short samples (< 1 year of daily returns or < 20 closed trades) are labelled "Too little
  history to judge".
- E8. Universe tests carry the survivorship note (active listings only). Symbols with a demerger
  or other unresolved corporate action inside the test window are excluded and listed.
- E9. Results show equity vs benchmark, drawdown, a metrics table (CAGR, total return, max
  drawdown, volatility, Sharpe, trades, win rate, time invested, charges), and the trade list.
- E10. Every run is saved to a local history with its full parameters and can be reopened.

### 4.6 Portfolio
- F1. Add, edit and remove holdings (symbol, quantity, average price, buy date).
- F2. Valuation at the latest close, P&L, allocation, and comparison with NIFTYBEES bought on the
  same dates with the same money.
- F3. Shows the charges to exit today, and a warning when one holding exceeds 25% of the portfolio.

### 4.7 Paper trading
- G1. Read-only view of the running paper books (XS-Monthly state file; flagship status file when
  present): positions, marks at the latest close, equity vs NIFTYBEES since start.
- G2. Never changes, starts or stops a book (paper-book notice 2026-09-24).

### 4.8 Tools
- H1. Trade cost and break-even: segment (delivery, intraday, futures, options), buy and sell price,
  quantity, trade date, broker charges → itemized charges with the NSE rule id for each line,
  net P&L, break-even sell price.
- H2. Position size: capital, risk %, entry, stop → quantity, capital used, maximum loss.
- H3. Options payoff: up to 4 legs (call/put, buy/sell, strike, premium, lots); payoff at expiry
  and today (Black-Scholes), break-evens, maximum profit and loss.

### 4.9 Settings
- I1. Profile and money rules; broker charges (brokerage per order by segment, DP charge per sell).
- I2. Market data folder, index status, rebuild.
- I3. Accounts: the Upstox token is stored in Windows Credential Manager; the UI shows only whether
  it is set. QuantOS never writes it to a file.
- I4. AI assistants: detected Claude/Codex CLIs, with official install and sign-in steps.
- I5. Appearance (system/light/dark); About (version, open-source licences, TradingView attribution,
  not-investment-advice notice).

## 5. Failure states

| Situation | Behaviour |
|---|---|
| No data folder / no index | Empty state with one action: connect market data |
| Index older than data | "Market data updated; rebuild index" banner |
| Symbol not in index | 404 page with search |
| Backtest with no bars in range | Inline error naming the missing range; nothing saved |
| Credential Manager unavailable | Accounts panel says so; everything else works |
| API unreachable | Full-screen "QuantOS engine is not running" with retry |

## 6. Quality bar

- Loads in under 1.5 s on the reference laptop; screener sorts 3,000 rows under 100 ms.
- Keyboard navigable; visible focus; contrast AA; light and dark themes.
- Indian number formatting (₹, lakh/crore grouping) everywhere.
- No console errors; no inline scripts (CSP `script-src 'self'`).
