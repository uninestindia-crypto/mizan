# Mizan Upstream PyBroker Update Briefing

**Generated UTC**: 2026-10-09T13:22:01Z
**Current Mizan PyBroker**: `v2.0.1`
**New Upstream PyBroker**: `v2.2.0`
**Release URL**: [https://github.com/edtechre/pybroker/releases/tag/v2.2.0](https://github.com/edtechre/pybroker/releases/tag/v2.2.0)

---

## 📋 Owner Action: Copy & Hand This Prompt to Your AI Agent

Copy the prompt block below and paste it into your AI assistant (Antigravity, Claude Code, or Cursor):

```markdown
A new upstream release of PyBroker (v2.2.0) has been published (current in Mizan: v2.0.1).
Please perform the following update steps:

1. Review Release Notes & Diff:
   - URL: https://github.com/edtechre/pybroker/releases/tag/v2.2.0
   - Highlights:
Major speedups in walkforward ML training.

2. Sync Engine Updates:
   - Run: `python scripts/sync_pybroker_update.py --version 2.2.0`
   - Inspect changes to `src/pybroker/` and ensure `@njit(cache=True)` and zero-lookahead invariants hold.

3. Learn & Update Skills:
   - Review any new indicators, kernels, or multi-interval capabilities in PyBroker.
   - Update agent skills in `skills/` and `.agents/skills/` and `agent_context/skills/pybroker_engine_guide.md`.

4. Run Mizan Regression Gates:
   - Run: `pytest tests/test_pybroker_adapter.py -v`
   - Run: `pytest tests/test_pybroker_upstream_tracker.py -v`
   - Run: `pytest tests/test_updates.py -v`

5. Update Version Ledger:
   - Update `pyproject.toml` dependencies if requirements changed.
   - Save the new version in `data/pybroker_upstream_state.json`.

```

---

## 📝 Upstream Release Summary

Major speedups in walkforward ML training.
