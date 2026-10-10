# Candidate Time-Series Foundation Models for Quant OS

This document records the prioritized candidate pool of pre-trained **Time-Series Foundation Models (TSFMs)** slated for research and testing within Quant OS, as well as multimodal embedding foundation models.

---

## 1. Candidate Model Registry & Priority Ranking

| Rank | Model | Core Value Proposition for Quant OS | Parameters | Realistic Hardware for Inference | License & Commercial Viability |
|---|---|---|---:|---|---|
| 🥇 | **TimesFM 3.0** | Best general zero-shot forecasting performance; ranked #1 on current FEV-Bench | ~331M | **4–8 GB VRAM workable**, 8–16 GB comfortable; CPU possible but slower | ⚠️ Local weights non-commercial |
| 🥈 | **Chronos-2** | Optimal balance of forecast accuracy, inference efficiency, and commercial usability | 120M | CPU works; **2–4 GB VRAM workable**, 8 GB plenty | ✅ Apache 2.0 |
| 🥉 | **Granite PatchTST-FM-r2** | Strong zero-shot performance with patch-level tokenization and channel independence | ~385M | **4–8 GB VRAM workable**, 8–16 GB for long contexts | ✅ Commercial-friendly |
| 4 | **TiRex-2** | Specialized for streaming inference, multivariate series, and exogenous covariates; high throughput | 38.4M active + 44.1M multivariate | CPU or **~4 GB VRAM**; CUDA requires Ampere+ | ✅ Apache 2.0 |
| 5 | **Toto 2.0 (1B / 2.5B)** | Large-scale multivariate foundation forecaster capable of capturing complex cross-asset dynamics | 1B / 2.5B | 1B: ~8–12 GB VRAM; **2.5B: 16 GB min, 24 GB comfortable** | ✅ Apache 2.0 |
| ⭐ Finance | **Moirai-2.0-small** | Lightweight model with demonstrated empirical strength in direct 2026 stock-return studies | **11.4M** | CPU easily; **< 2 GB VRAM** easily | ⚠️ CC BY-NC 4.0 |
| Heavy | **Timer-S1** | Large Mixture-of-Experts (MoE) architecture; research exploratory baseline | 8.3B total / 0.75B active | **40 GB+ VRAM officially recommended** | ✅ Apache 2.0 |

---

## 2. Architectural & Operational Assessment

### 🥇 TimesFM 3.0 (Google Research)
- **Architecture**: Decoder-only autoregressive transformer with patched input representations.
- **Strengths**: Exceptional zero-shot univariate benchmark scores across multiple domains; leading performer on FEV-Bench.
- **Quant OS Fit**: Excellent candidate for benchmark forecasting against classical autoregression and ridge baselines.
- **Considerations**: Local model weights carry non-commercial research licensing terms. Production integration into commercial Quant OS binaries would require an API abstraction or alternative licensing.

### 🥈 Chronos-2 (Amazon / AutoGluon)
- **Architecture**: Probabilistic time-series forecasting via language model tokenization (scaling, quantization, and cross-attention).
- **Strengths**: Highly efficient, robust out-of-the-box predictions, clean Python / PyTorch integration, permissive Apache 2.0 license.
- **Quant OS Fit**: Top contender for desktop client deployment. At 120M parameters, inference is fast on modern CPUs and lightweight integrated/discrete GPUs.

### 🥉 Granite PatchTST-FM-r2 (IBM Research)
- **Architecture**: Patch-based transformer with channel-independent sub-modules.
- **Strengths**: Preserves local temporal context via patch segmentation; robust against distribution shifts. Permissively licensed.
- **Quant OS Fit**: Strong candidate for medium-horizon swing forecasting (e.g. 5–20 day predictions) where extended lookback windows are advantageous.

### 4. TiRex-2
- **Architecture**: Recurrent/state-space hybrid designed for high-frequency and multivariate streaming data.
- **Strengths**: Low parameter count (38.4M active), low memory bandwidth consumption, native handling of exogenous covariates.
- **Quant OS Fit**: Well-suited for streaming or intraday market feeds where low inference latency is critical. Note hardware constraint: GPU acceleration requires NVIDIA Ampere or newer architecture.

### 5. Toto 2.0 (1B / 2.5B)
- **Architecture**: Large-scale transformer trained on extensive multi-domain time series.
- **Strengths**: High model capacity for multivariate interactions and non-linear cross-asset co-movements.
- **Quant OS Fit**: Cloud research pipeline. Too heavy for consumer laptops; best evaluated in remote headless containers or cloud GPU runners.

### ⭐ Finance Special: Moirai-2.0-small (Salesforce AI Research)
- **Architecture**: Masked encoder transformer with multi-frequency patch sizes.
- **Strengths**: Compact footprint (11.4M parameters), rapid inference, validated performance on financial returns in empirical literature.
- **Quant OS Fit**: Outstanding fit for the **Factory-New Laptop Standard**. Can run entirely on CPU without straining system memory. Requires attention to non-commercial license (CC BY-NC 4.0).

### Heavy: Timer-S1
- **Architecture**: Large Mixture-of-Experts (MoE) foundation model (8.3B total, 0.75B active per forward token).
- **Strengths**: Deep representation capacity across diverse temporal tasks.
- **Quant OS Fit**: Research reference only. Demands enterprise-grade accelerator memory (40 GB+ VRAM) and is unsuitable for client-side Quant OS distribution.

---

## 3. Deployment Matrix: Client Desktop vs. Cloud Research

| Deployment Target | Qualified Candidate Models | Key Hardware & Packaging Drivers |
|---|---|---|
| **Client Desktop (Factory-New Laptop)** | **Moirai-2.0-small** (11.4M)<br>**Chronos-2** (120M)<br>**TiRex-2** (38.4M) | Must run out-of-the-box without discrete GPU requirements; fast CPU / NPU execution; zero black terminal popups. |
| **Developer Workstation / Local GPU** | **Granite PatchTST-FM-r2** (~385M)<br>**TimesFM 3.0** (~331M) | 4–8 GB VRAM; reasonable batch inference for universe screening. |
| **Headless Cloud / CI / GPU Cluster** | **Toto 2.0 (1B/2.5B)**<br>**Timer-S1** (8.3B MoE) | Requires dedicated compute instances (A100, H100, or multi-GPU environments); strictly research and parameter exploration. |

---

## 4. Governed Trial Protocol (Quant OS Laws)

Per `agent_context/GOAL.md` and repository governance invariants:

1. **Backlog vs. Declared Trial**: Inclusion in this document represents candidate backlog tracking. No multiplicity penalty is incurred until a formal trial is declared.
2. **Prior Declaration Requirement**: Before any model is evaluated against real market data:
   - A frozen, dated declaration must be committed under `reports/<trial_name>/TRIAL-LEDGER.md`.
   - The test budget, holding period, and candidate rule must be defined prior to generating predictions.
   - Predictions must be scored on point-in-time NSE features with next-bar execution and real transaction costs (0.224% round trip).
3. **Deflated Sharpe Ratio (DSR)**: Candidate model performance must be deflated against the cumulative count of all historical trials across Quant OS.

---

## 5. Multimodal Embedding Foundation Model: EmbeddingGemma 2

While the models in Section 1 focus on autoregressive time-series forecasting, **EmbeddingGemma 2** (released October 2026 by Google DeepMind) provides a natively multimodal embedding foundation model for research retrieval, academic grounding, and financial disclosure analysis:

- **Architecture & Scale**: Modular Gemma 4-based architecture with a 270M parameter text/code encoder, 170M vision encoder, and 300M audio encoder (740M full model).
- **Matryoshka Representation Learning (MRL)**: Supports dimensional truncation (128, 256, 512, 768 dimensions), reducing vector storage and indexing memory in DuckDB/SQLite by up to 75%.
- **Context Window**: 8,192 tokens; ideal for full research papers, earnings transcripts, and regulatory filings.
- **License**: `Apache 2.0` (fully commercial-friendly for Quant OS desktop distribution).
- **Quant OS RAG Integration**: Integrated into `quant_system.research.embedding_gemma.EmbeddingGemmaProvider` and `QuantPaperRAG`, providing dense semantic retrieval and hybrid search across quantitative finance research, corporate disclosures, and advisory context.
- **Repository id and how it is loaded** (checked 2026-10-10 against the Hugging Face model card and API): `google/embeddinggemma-2`, ungated, 744,371,512 parameters (BF16), about 3 GB. Quant OS loads the text-only configuration (`vision_config` and `audio_config` set to `None`, about 270M parameters) through sentence-transformers, with the card's task prefixes (`task: search result | query: ...` for questions, `title: none | text: ...` for documents) and re-normalises after Matryoshka truncation. There is no `embeddinggemma-270m` repository; earlier versions of this code used that id.
- **What the installed app really runs**: the model is not bundled (it needs the 3 GB download and a machine-learning library, neither of which a factory-new laptop has). Unless it has been installed, paper search uses a built-in keyword-and-hash substitute that is not a neural model. `EmbeddingGemmaProvider.label`, the paper-search metadata and the hardware screen say which one produced the vectors. The Quant SLM's 16 "research context" numbers are one fixed vector shared by every stock and carry no stock-specific information; the shipped weights record no embedding backend, so they must not be described as built with EmbeddingGemma 2.
