# NOTICE: assistant provider fallback list edited under an Antigravity claim

STATUS: ACTIVE (notice)  
FILED_BY: Claude Code, record `20261003-claude-installer-first-run-usability.md`  
FILED_UTC: 2026-10-03  
AFFECTS: `20260904-antigravity-claude-fable-analysis.md` (ACTIVE), which names
`src/quant_system/assistant/service.py` for intent routing

On explicit founder instruction ("yes do it all one by one", after the finding that Gemini, DeepSeek and
Mistral keys could be saved in Settings but no code used them), `_try_llm_completion` in
`src/quant_system/assistant/service.py` now also falls back to the Gemini, DeepSeek and Mistral providers
after the four it already tried. Three added lines in one list. Intent routing and every other part of the
file are untouched. Matching changes: `alpha/key_pool.py` (three provider names and their environment keys)
and `alpha/direct_providers.py` (three clients; defaults no longer pin a model).

Deliberately NOT changed: the advisory consensus panel in `alpha/ai_advisor.py` still seats only the original
four providers. Adding voters changes how many models average into `weight_multiplier`, which is a modelling
decision for the owner of that panel, not a wiring fix.

Numbers this invalidates: none pinned in a record. `tests/test_platform_assistant.py` (and the advisory and key-pool tests)
pass unchanged.
