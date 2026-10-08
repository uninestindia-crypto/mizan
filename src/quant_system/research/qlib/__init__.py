"""Qlib research and alpha factor bridge for Mizan (QuantOS).

Integrates Microsoft Qlib's state-of-the-art alpha factor representations (Alpha158)
and modeling evaluation workflows into Mizan's governed, point-in-time architecture.

Provenance & Local Source:
- Local reference repository: ``d:/Quant OS Project/qlib-main``
- Upstream GitHub: ``https://github.com/microsoft/qlib``
- Detailed guide: See ``src/quant_system/research/qlib/README.md``
"""

from __future__ import annotations

from quant_system.research.qlib.adapter import QlibModelAdapter, QlibRankDataset
from quant_system.research.qlib.alpha158 import (
    QLIB_ALPHA158_CANONICAL_WINDOW_BARS,
    QLIB_ALPHA158_MINIMUM_BARS,
    QlibAlpha158Extractor,
    compute_qlib_alpha_features,
)
from quant_system.research.qlib.pipeline import (
    CONVENTIONAL_FINANCIALS,
    compute_indian_statutory_friction,
    get_default_cache_store,
    run_live_slm_pipeline,
)
from quant_system.research.qlib.quant_slm import (
    QuantSLM,
    QuantSLMConfig,
    QuantSLMPrediction,
)
from quant_system.research.qlib.upstream_watcher import (
    QlibUpstreamRelease,
    QlibUpstreamWatcher,
    check_qlib_upstream,
)

__all__ = [
    "CONVENTIONAL_FINANCIALS",
    "QLIB_ALPHA158_CANONICAL_WINDOW_BARS",
    "QLIB_ALPHA158_MINIMUM_BARS",
    "QlibAlpha158Extractor",
    "QlibModelAdapter",
    "QlibRankDataset",
    "QlibUpstreamRelease",
    "QlibUpstreamWatcher",
    "QuantSLM",
    "QuantSLMConfig",
    "QuantSLMPrediction",
    "check_qlib_upstream",
    "compute_indian_statutory_friction",
    "compute_qlib_alpha_features",
    "get_default_cache_store",
    "run_live_slm_pipeline",
]
