"""Alpha factor library, technical indicators, Black-Scholes Greeks, and AI Multi-Agent Advisory."""

from quant_system.alpha.ai_advisor import (
    AIOpinion,
    BaseAIAdvisor,
    ClaudeCLIAdvisor,
    DirectAPIAdvisor,
    MultiAgentConsensusEngine,
    SignalStrengthRuleAdvisor,
    TrendDivergenceRuleAdvisor,
)
from quant_system.alpha.cli_manager import CLIDiagnosticItem, CLIManager
from quant_system.alpha.direct_providers import (
    AnthropicClient,
    BaseDirectAPIClient,
    GroqClient,
    OpenAIClient,
    OpenRouterClient,
)
from quant_system.alpha.greeks import BlackScholes
from quant_system.alpha.key_pool import (
    KeyPoolManager,
    KeyStatus,
    ManagedKey,
    ProviderType,
    RotationPolicy,
)
from quant_system.alpha.surface import VolatilitySurface
from quant_system.alpha.technical import TechnicalIndicators
from quant_system.alpha.transform import FactorTransform

__all__ = [
    "AIOpinion",
    "AnthropicClient",
    "SignalStrengthRuleAdvisor",
    "BaseAIAdvisor",
    "BaseDirectAPIClient",
    "BlackScholes",
    "CLIDiagnosticItem",
    "CLIManager",
    "ClaudeCLIAdvisor",
    "TrendDivergenceRuleAdvisor",
    "DirectAPIAdvisor",
    "FactorTransform",
    "GroqClient",
    "KeyPoolManager",
    "KeyStatus",
    "ManagedKey",
    "MultiAgentConsensusEngine",
    "OpenAIClient",
    "OpenRouterClient",
    "ProviderType",
    "RotationPolicy",
    "TechnicalIndicators",
    "VolatilitySurface",
]
