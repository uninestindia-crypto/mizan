# Multi-Modal Alpha Roadmap: Technical, Fundamental & Sentiment

This roadmap outlines how **QuantOS** expands beyond technical price signals to incorporate **Quantitative Fundamental Analysis ("Quantamental")**, **News & Sentiment NLP**, and **Alternative Datasets**.

---

## 🧭 Why Multi-Modal Alpha Matters

In quantitative finance, relying solely on price-action and technical indicators leaves strategies vulnerable to regime shifts and structural market noise. Combining independent, uncorrelated sources of alpha produces higher risk-adjusted returns (Sharpe ratio) and lower tail risk:

$$\text{Total Alpha} = w_{\text{tech}} \cdot \alpha_{\text{technical}} + w_{\text{fund}} \cdot \alpha_{\text{fundamental}} + w_{\text{sent}} \cdot \alpha_{\text{sentiment}}$$

Where:
* $\text{Correlation}(\alpha_{\text{tech}}, \alpha_{\text{fund}}) \approx 0.1 - 0.2$ (Low correlation)
* $\text{Correlation}(\alpha_{\text{fund}}, \alpha_{\text{sent}}) \approx 0.15 - 0.25$ (Diversified information sources)

---

## 🏢 1. Quantitative Fundamental Analysis ("Quantamental")

### Core Data Models (`quant_system.data.fundamental`)
* **Balance Sheet, Income Statement, Cash Flow Statements**:
  * Quarterly ($10\text{-Q}$, NSE/BSE quarterly filings) and Annual ($10\text{-K}$, Annual Reports) data.
  * Point-in-time database to prevent lookahead bias (ensuring data is only visible on or after the actual publication/filing date).
* **Key Fundamental Factors (`quant_system.alpha.fundamental`)**:
  * **Value Factors**:
    * $P/E$ (Price-to-Earnings), $P/B$ (Price-to-Book), $P/S$ (Price-to-Sales)
    * $EV / \text{EBITDA}$ (Enterprise Multiple)
    * Free Cash Flow Yield ($FCF / \text{Market Cap}$)
  * **Quality & Solvency Factors**:
    * Return on Equity ($ROE = \text{Net Income} / \text{Shareholder Equity}$)
    * Return on Invested Capital ($ROIC$)
    * Debt-to-Equity ($D/E$) and Interest Coverage Ratio
    * **Piotroski $F$-Score** (9-point financial health score)
    * **Altman $Z$-Score** (Credit distress and bankruptcy probability)
  * **Growth & Revisions**:
    * Year-over-Year (YoY) Sales and EPS growth
    * Analyst Consensus Revisions (Earnings Estimate Revisions - EER)
    * Post-Earnings Announcement Drift (PEAD)

```python
# Conceptual Quantamental Factor Pipeline
from quant_system.alpha.fundamental import FundamentalFactorEngine

factors = FundamentalFactorEngine.calculate(
    symbol="INFY",
    filing_date=date(2026, 4, 15),
    price=Decimal("1650.00"),
)
print(factors.piotroski_f_score)  # e.g., 8 / 9
print(factors.fcf_yield)  # e.g., 5.2%
print(factors.value_composite_z)  # Normalized cross-sectional z-score
```

---

## 📰 2. News & Sentiment Analysis (NLP & LLMs)

### Sentiment Data Pipeline (`quant_system.data.sentiment`)
* **News Aggregation Sources**:
  * Financial RSS Feeds (Bloomberg, Reuters, Economic Times, LiveMint, Moneycontrol)
  * Corporate Announcements & Regulatory Disclosures (BSE/NSE corporate feeds, SEC Edgar)
  * Earnings Call Transcripts
  * Social & Retail Sentiment Feeds (Twitter/X financial cashtags, Reddit r/IndianStreetBets, StockTwits)

### Sentiment Scoring Engines (`quant_system.alpha.sentiment`)
1. **Financial Transformer Models (FinBERT)**:
   * Classifies financial headlines into `[POSITIVE, NEGATIVE, NEUTRAL]` with confidence probabilities.
   * Fine-tuned specifically on financial vocabulary (e.g. understanding that "cost cutting" or "higher provisions" has nuanced financial implications).
2. **LLM Multi-Agent Evaluation (`quant_system.alpha.ai_advisor`)**:
   * Uses local or cloud LLMs (Claude, Codex, Antigravity, Llama) to ingest company announcements, detect guidance changes, management tone, or geopolitical risks.
   * Produces structured `AIOpinion` ratings with action biases (`BULLISH`, `BEARISH`, `VETO`).
3. **Continuous Sentiment Polarity Index**:
   * Exponentially decays past news sentiment to construct a continuous time-series feature:
   $$S_t = \lambda \cdot S_{t-1} + (1 - \lambda) \cdot \text{Score}_{\text{new\_event}}$$

---

## 🔄 3. Multi-Factor Fusion Strategy Example

How technical, fundamental, and sentiment signals combine inside `quant_system.strategies.quantamental_fusion`:

```python
class QuantamentalFusionStrategy(BaseStrategy):
    """Fuses Price Momentum, Fundamental Quality, and News Sentiment."""

    def calculate_signals(self, market_data, fundamental_data, sentiment_data):
        for symbol in self.universe:
            # 1. Technical Alpha: 12-month momentum & 200 EMA trend filter
            tech_score = self.calc_momentum_score(symbol, market_data)
            
            # 2. Fundamental Alpha: High Quality + Low Value
            fund_score = self.calc_piotroski_and_pe(symbol, fundamental_data)
            
            # 3. Sentiment Alpha: Recent 7-day news polarity & earnings drift
            sent_score = self.calc_sentiment_polarity(symbol, sentiment_data)
            
            # 4. Multi-Factor Composite
            composite_alpha = (0.40 * tech_score) + (0.35 * fund_score) + (0.25 * sent_score)
            
            # 5. Signal Decision with AI Advisor Veto Check
            if composite_alpha > 1.5:
                yield Signal(symbol=symbol, side=Side.BUY, strength=composite_alpha)
            elif composite_alpha < -1.0:
                yield Signal(symbol=symbol, side=Side.SELL, strength=abs(composite_alpha))
```

---

## 📅 Implementation Roadmap

| Phase | Milestone | Deliverables |
| :--- | :--- | :--- |
| **Phase 1 (Current)** | **Core Technical & Derivatives Foundation** | • Event-driven backtester & exact Decimal ledger<br/>• Upstox data client & synthetic bar generators<br/>• Black-Scholes Greeks, IV surface, and technical indicators<br/>• AI Advisor Multi-Agent Consensus & arXiv RAG |
| **Phase 2** | **Fundamental Data Ingestion & Factor Modeling** | • Point-in-time Financial Statement Schema<br/>• Value, Quality, and Solvency Factor calculations ($P/E$, $ROE$, F-Score)<br/>• Cross-sectional Factor Normalization & Z-scoring |
| **Phase 3** | **NLP & Sentiment Pipeline** | • Financial RSS & Corporate filing scrapers<br/>• FinBERT / Local LLM sentiment inference pipeline<br/>• Social sentiment momentum indicators |
| **Phase 4** | **Quantamental Strategy Engine** | • Multi-Factor Composite Strategy models<br/>• Factor-based Portfolio Optimizers<br/>• Factor Attribution & Style Exposure Tearsheets |
