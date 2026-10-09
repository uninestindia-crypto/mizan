# Upstream Work Ticket: Microsoft Qlib Update (v0.9.7)

STATUS: INBOX (Ready for AI Agent Assignment)  
SOURCE: microsoft/qlib  
RELEASE_TAG: v0.9.7  
RELEASE_URL: https://github.com/microsoft/qlib/releases/tag/v0.9.7  
DETECTED_UTC: 2026-10-08T06:27:39.663593+00:00  

---

## 📢 Upstream Announcement
**Title:** v0.9.7 🌈  
**Published:** 2025-08-15T09:49:17Z  

### Release Notes
## Changes

## 🌟 Features

- feat: data improve, support parquet @you-n-g (#1966)
- feat: use pydantic-settings for MLflow config and update dependencies @you-n-g (#1962)
- refactor: introduce BaseDataHandler and unify fetch interface @you-n-g (#1958)
- Implement geometric accumulation mode for risk_analysis function @SunsetWolf (#1938)
- Add util function to help automatically get horizon @chenditc (#1509)
- [feat] fix a bug and adapt general_nn for use with rdagent_qlib @WinstonLiyt (#1928)
- DRAFT add Data Health Checker  @benheckmann (#1574)

## 🐛 Bug Fixes

- fix: upgrade the method of installing LightGBM on MacOS @SunsetWolf (#1980)
- disable pylint error @SunsetWolf (#1960)
- Fixing Security Vulnerabilities @SunsetWolf (#1941)
- The plotly figure is empty in the code block "Basic data" @ziphei (#1902)
- [fix] keep group_keys=False in Average Ensemble @lingbai-kong (#1913)
- fix ci error @SunsetWolf (#1921)
- Fix issue 1892 @SunsetWolf (#1916)
- fix fillna bug @SunsetWolf (#1914)
- fix col name error when fetch data @SunsetWolf (#1904)
- fix pkl file not loading in StaticDataLoader @SunsetWolf (#1896)
- Fix csi300 constituents url @SunsetWolf (#1883)
- Fix the empty price_s case and self.instruments in SBBStrategyEMA. @ChiahungTai (#1677)
- Bump version @SunsetWolf (#1872)

## 📚 Documentation

- feat: data improve, support parquet @you-n-g (#1966)
- fix: typo @EmreKb (#1943)
- Update README.md @you-n-g (#1940)
- doc: update README.md @you-n-g (#1929)
- [Fix]Update data preparation part in README.md @YeewahChan (#1924)
- fixed a problem with multi index caused by the default value of groupkey @SunsetWolf (#1917)
- fix bugs in the documentation @SunsetWolf (#1918)
- DRAFT add Data Health Checker  @benheckmann (#1574)
- Update links to chenditc/investment_data to always point to latest release @codecnotsupported (#1877)
- Fix broken URL for RL @SunsetWolf (#1881)
- Bump version @SunsetWolf (#1872)

## 🧹 Maintenance

- fixed a problem with multi index caused by the default value of groupkey @SunsetWolf (#1917)


---

## 🎯 Instructions for the Assigned AI Agent (Antigravity / Claude / Codex)

The owner has handed this upstream update to you. Please execute the following protocol:

1. **Active Record**:
   - Move or copy this ticket into `agent_context/work/active/YYYYMMDD-agent-qlib-update-v0.9.7.md`.
   - Set `STATUS: ACTIVE` and declare owned paths.

2. **Inspect Upstream Changes**:
   - Examine new models, factors, or performance fixes introduced in `v0.9.7`.
   - Reference local repo at `d:/Quant OS Project/qlib-main` or GitHub compare: `https://github.com/microsoft/qlib/releases/tag/v0.9.7`.
   - Read the provenance and 'Nothing Missed' inventory in `src/quant_system/research/qlib/README.md`.

3. **Incorporate into Mizan**:
   - Check if new mathematical alpha factors belong in `src/quant_system/research/qlib/alpha158.py`.
   - Check if new modeling architectures belong in `src/quant_system/research/qlib/adapter.py`.
   - Maintain Mizan's strict invariants: zero lookahead bias, point-in-time causality, and strict typing.

4. **Verify Quality Gates**:
   - Run `pytest tests/test_qlib_bridge.py -v`.
   - Verify `scripts/run-gates.ps1` (or relevant slice tests).

5. **Complete Work Record**:
   - Move active record to `agent_context/work/completed/`.
