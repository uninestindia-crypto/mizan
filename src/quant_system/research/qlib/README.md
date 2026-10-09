# Qlib Research Bridge & Provenance Guide 🏛️

This module bridges **Microsoft Qlib**'s state-of-the-art AI/ML alpha modeling capabilities with **Mizan (QuantOS)**'s institutional execution, pre-trade risk governance, and Indian market (NSE/BSE) infrastructure.

---

## 1. Provenance & Origin Sources

Any human developer or AI agent (Antigravity, Claude Code, Codex, Cursor) investigating this bridge can verify and cross-examine the original sources at:

1. **Local Sibling Repository (On Drive)**:
   - Absolute Path: `d:\Quant OS Project\qlib-main\`
   - Key Subdirectories:
     - `qlib/contrib/data/handler.py` (Alpha158 and Alpha360 mathematical factor definitions)
     - `qlib/contrib/model/` (Tree and deep learning model implementations)
     - `examples/benchmarks/` (20+ model benchmarks: LightGBM, Transformer, TRA, HIST, etc.)
     - `examples/workflow_by_code.py` (Modular quant research workflow)
2. **Upstream Remote Repository**:
   - GitHub: [`microsoft/qlib`](https://github.com/microsoft/qlib)
   - Official Documentation: [qlib.readthedocs.io](https://qlib.readthedocs.io/)
3. **Foundational Academic Papers**:
   - *"Qlib: An AI-oriented Quantitative Investment Platform"*, Xiao Yang et al., Microsoft Research ([arXiv:2009.11189](https://arxiv.org/abs/2009.11189))
   - *"R&D-Agent-Quant: A Multi-Agent Framework for Data-Centric Factors and Model Joint Optimization"*, Yuante Li et al. ([arXiv:2505.15155](https://arxiv.org/abs/2505.15155))

---

## 2. Detailed Mapping: What Was Learned & Implemented in Mizan

| Component | Upstream Qlib Origin | Mizan Implementation | Design Rationale & Adaptations |
| :--- | :--- | :--- | :--- |
| **Alpha158 Factor Engine** | `qlib/contrib/data/handler.py` (`Alpha158`, `check_transform_proc`) | [`alpha158.py`](file:///d:/Quant%20OS%20Project/Mizan/src/quant_system/research/qlib/alpha158.py) (`QlibAlpha158Extractor`) | Extracted Qlib's core factor formulas into pure NumPy. Operates on Mizan's [`PointInTimeBar`](file:///d:/Quant%20OS%20Project/Mizan/src/quant_system/data/market_data.py) with zero lookahead bias and division-by-zero guards. |
| **Cross-Sectional Dataset** | `qlib/data/dataset/handler.py` (`DatasetH`) | [`adapter.py`](file:///d:/Quant%20OS%20Project/Mizan/src/quant_system/research/qlib/adapter.py) (`QlibRankDataset`) | Clean dataclass container holding normalized feature matrices $X$ and forward returns $y$ across symbols and dates. |
| **Model Evaluation Metrics** | `qlib/workflow/record_temp.py` (`SigAnaRecord`, `PortAnaRecord`) | [`adapter.py`](file:///d:/Quant%20OS%20Project/Mizan/src/quant_system/research/qlib/adapter.py) (`QlibEvaluationReport`) | Evaluates continuous predictions with Information Coefficient (Pearson IC), Rank IC (Spearman correlation), and Top-Decile Spread. |
| **Upstream Release Monitor** | `microsoft/qlib` releases & tags API | [`upstream_watcher.py`](file:///d:/Quant%20OS%20Project/Mizan/src/quant_system/research/qlib/upstream_watcher.py) & [`scripts/watch_upstream_qlib.py`](file:///d:/Quant%20OS%20Project/Mizan/scripts/watch_upstream_qlib.py) | Polls GitHub API, maintains `data/upstream/qlib_state.json`, and generates an AI Agent work ticket in `agent_context/work/inbox/`. |
| **Scheduled CI Job** | `.github/workflows/` | [`.github/workflows/qlib-upstream-monitor.yml`](file:///d:/Quant%20OS%20Project/Mizan/.github/workflows/qlib-upstream-monitor.yml) | Runs weekly in GitHub Actions to check for new upstream releases. |

---

## 3. The "Nothing Missed" Inventory: What Else Exists in Qlib

For future AI agents or researchers looking to expand this bridge, here is a complete inventory of additional components present in `d:\Quant OS Project\qlib-main\` and how they can be ported:

### A. Additional Alpha Factor Families
- **`Alpha360`** (`qlib/contrib/data/handler.py`):
  - *What it is*: A raw, unengineered normalized tensor of the past 60 days of OHLCV bars (`$close / Ref($close, 1)` etc.).
  - *Where to adapt*: Add `extract_alpha360` to `alpha158.py` if feeding sequence models like LSTMs or Transformers.
- **`Alpha158VWAP`** (`qlib/contrib/data/handler.py`):
  - *What it is*: Alpha158 augmented with Volume-Weighted Average Price indicators (`$vwap`).
  - *Where to adapt*: Requires intraday tick or 1-minute candle aggregation from Mizan's market index.

### B. Benchmark Machine Learning Models
Located under `d:\Quant OS Project\qlib-main\examples\benchmarks\`:
- **Gradient Boosters**:
  - `LightGBM` (`benchmarks/LightGBM/`): Can be wrapped into `adapter.py` using `lightgbm.LGBMRegressor`.
  - `CatBoost` (`benchmarks/CatBoost/`): Handles categorical features natively.
  - `XGBoost` (`benchmarks/XGBoost/`): Alternative tree baseline.
- **Deep Sequence & Attention Networks**:
  - `Transformer` & `Localformer` (`benchmarks/Transformer/`, `benchmarks/Localformer/`): Self-attention across time.
  - `ALSTM` / `GRU` (`benchmarks/ALSTM/`, `benchmarks/GRU/`): Recurrent neural networks.
  - `TabNet` (`benchmarks/TabNet/`): Attentive interpretable tabular learning.
- **Market Dynamics & Concept Drift**:
  - `TRA` (Temporal Routing Adaptor) (`benchmarks/TRA/`): Predicts market regimes and dynamically routes sample representations.
  - `HIST` (`benchmarks/HIST/`): Incorporates cross-stock concept drift.
  - `ADARNN` (`benchmarks/ADARNN/`): Adaptive recurrent neural network for distribution shifts.

### C. Execution & Reinforcement Learning
- **`rl_order_execution`** (`examples/rl_order_execution/`):
  - *What it is*: Reinforcement learning policies for optimal trade execution (minimizing slippage and market impact).
  - *Where to adapt*: Can be mapped into Mizan's execution models under `src/quant_system/risk/` or broker order generation.

---

## 4. How Future AI Agents Should Handle Upstream Updates

When the upstream watcher detects a new release from Microsoft Qlib:
1. It writes a ticket to: `agent_context/work/inbox/YYYYMMDD-upstream-qlib-vX.X.X.md`.
2. The owner assigns this ticket to an AI agent (Antigravity, Claude Code, or Codex).
3. The AI agent follows this protocol:
   - Read the release notes and diff in the ticket.
   - Cross-reference with the local copy at `d:\Quant OS Project\qlib-main\` (or run `git pull` inside `qlib-main`).
   - If a new factor was introduced: Update [`alpha158.py`](file:///d:/Quant%20OS%20Project/Mizan/src/quant_system/research/qlib/alpha158.py).
   - If a new modeling technique was released: Extend [`adapter.py`](file:///d:/Quant%20OS%20Project/Mizan/src/quant_system/research/qlib/adapter.py).
   - Run tests: `uv run pytest tests/test_qlib_bridge.py -v`.
   - Ensure linting passes: `uv run ruff check src/quant_system/research/qlib`.
