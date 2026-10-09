# Completed work: Package Quant-SLM, Qlib, and pre-trained weights into Mizan Quant OS installer specs

STATUS: COMPLETED  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-08T08:15:00Z  
COMPLETED_UTC: 2026-10-08T08:22:00Z  
STARTING_REVISION: 52df4f4513a1d65733ee6b6fec320af701126271  
WORKTREE_OR_BRANCH: D:/Quant OS Project/Mizan (main)

## Objective

GOAL_LINE: G1, G2, G5
1. Refactor `run_live_slm_pipeline` into `src/quant_system/research/qlib/pipeline.py` so it is a first-class citizen of the `quant_system` package, ensuring PyInstaller bundles it into frozen executables on factory-new laptops.
2. Update `installer/quantos.spec` to bundle `data/evidence/models` (shipping pre-trained `quant_slm_nifty50_v1.json` weights and initial signals).
3. Update `installer/quant_os_setup.iss` to use "Mizan Quant OS" application title and output names.
4. Verify tests and linting.

## Changes Made

1. **First-Class Package Pipeline (`src/quant_system/research/qlib/pipeline.py`)**:
   - `run_live_slm_pipeline`, `compute_indian_statutory_friction`, `build_synthetic_bars`, `get_default_cache_store`, and `CONVENTIONAL_FINANCIALS` implemented in `quant_system.research.qlib.pipeline`.
   - Exported in `src/quant_system/research/qlib/__init__.py`.
   - `src/quant_system/server/v2/router.py`: Line 1021 updated to import `run_live_slm_pipeline` from `quant_system.research.qlib`.

2. **CLI Entrypoint Clean Wrapper (`scripts/run_live_slm_paper_trader.py`)**:
   - Converted into a clean CLI wrapper importing from `quant_system.research.qlib.pipeline`.
   - Fully backward-compatible exports preserved for scripts and callers.

3. **Installer & PyInstaller Bundling (`installer/quantos.spec`)**:
   - Added `(str(root_dir / 'data' / 'evidence' / 'models'), 'data/evidence/models')` to `added_files`.
   - Ensured PyInstaller bundles pre-trained weights (`quant_slm_nifty50_v1.json`, `quant_slm_v1.json`, and latest signals) so a factory-new laptop has working weights out of the box.

4. **Inno Setup Script Branding (`installer/quant_os_setup.iss`)**:
   - Updated `#define MyAppName "Mizan Quant OS"`.
   - Updated `#define MyAppPublisher "Mizan Quant OS Quantitative Technologies"`.
   - Updated `OutputBaseFilename=MizanQuantOS_v{#MyAppVersion}_Setup`.
   - Updated installation path prompt text to reference "Mizan Quant OS".
   - Added pre-bundled models to `[Files]` section: `Source: "..\data\evidence\models\*"; DestDir: "{app}\data\evidence\models"; Flags: ignoreversion onlyifdoesntexist recursesubdirs createallsubdirs`.

5. **Windows PE Version Resource (`installer/quantos_version_resource.py`)**:
   - Updated `COMPANY_NAME = "Mizan Quant OS Quantitative Technologies"`.
   - Updated `PRODUCT_NAME = "Mizan Quant OS"`.

6. **Release & Installer Automation Scripts**:
   - `scripts/build-windows-installer.ps1`: Updated expected installer path check to `MizanQuantOS_v<ver>_Setup.exe`.
   - `scripts/build-windows-release.ps1`: Added explicit staging of `data/evidence/models` into `dist\quantos\data\evidence\models`.

7. **Verification**:
   - `uv run ruff check src/quant_system/research/qlib src/quant_system/server/v2/router.py scripts/run_live_slm_paper_trader.py scripts/schedule_market_hours_slm.py scripts/run_slm_walk_forward_backtest.py tests/test_quant_slm.py installer/quantos_version_resource.py`: Clean pass (0 errors).
   - `uv run pytest tests/test_quant_slm.py tests/test_qlib_bridge.py tests/test_literature_alpha_pipeline.py -v`: 15 passed in 8.10s.
   - CLI execution test: `uv run python scripts/run_live_slm_paper_trader.py --universe RELIANCE TCS INFY --epochs 2 --sample-step 15 --no-cache`: Successfully completed in 0.01s training, 0.37ms inference.
