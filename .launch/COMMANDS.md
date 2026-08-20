# COMMANDS — QuantOS

Baseline captured 2026-08-20 in `D:\quant_system` using `.venv\Scripts\python.exe` (Python 3.13.15).

## Verified commands

| Need | Command | Result | Notes |
|---|---|---|---|
| Runtime | `.venv\Scripts\python.exe --version` | PASS | Python 3.13.15 |
| Package manager | `uv --version` | PASS | uv 0.12.5 |
| Unit/integration/API tests | `.venv\Scripts\python.exe -m pytest -q` | PASS | 74 passed, 1 dependency deprecation warning, 2.63s |
| Coverage | `.venv\Scripts\python.exe -m pytest --cov=quant_system --cov-report=term-missing -q` | PASS | 89% overall; critical gaps remain in Upstox and some pricing/strategy branches |
| Lint | `.venv\Scripts\python.exe -m ruff check .` | FAIL | 5 fixable findings |
| Format check | `.venv\Scripts\python.exe -m ruff format --check .` | FAIL | 9 files would be reformatted |
| Typecheck | `.venv\Scripts\python.exe -m mypy src launcher.py scripts` | FAIL | 1 error in `data/upstox.py` |
| Startup diagnostics | `.venv\Scripts\python.exe launcher.py --test-mode` | PASS | All six current prerequisite checks reported pass |
| Runtime imports | `.venv\Scripts\python.exe -c "import quant_system, fastapi, uvicorn, numpy, scipy, yaml; print(quant_system.__version__)"` | PASS | Version 1.0.0 |

## Unverified or missing commands

| Need | Status | Required follow-up |
|---|---|---|
| Clean install from lock | Verified | `UV_PROJECT_ENVIRONMENT=tmp/verify-venv uv sync --frozen --extra dev --link-mode copy`; 47 packages installed |
| Package/wheel build | Unverified | Add and run a reproducible build command |
| PyInstaller build | Unverified | Run from a clean environment and verify manifest |
| E2E browser journey | Missing | Add automated real-server/browser smoke coverage |
| Secret scan | Verified for application surface | `detect-secrets 1.5.0`; zero candidates; `.agents` excluded because scanner skills intentionally contain detector fixtures |
| Dependency vulnerability audit | Missing | Add and run an audit tool |
| Dead-code scan | Verified | `vulture 2.16 --min-confidence 80`; zero findings after three dispositions |
| Mutation testing | Partial | Slice 1 NSE-only boundary mutation caught and restored; ledger/risk/cost mutation coverage remains |
| CI | Missing | Add a pinned Windows CI workflow for static, tests, and build |
| Deploy / rollback | Not applicable now | Local desktop scope; installer upgrade/uninstall recovery still needs rehearsal |

## Raw baseline summary

```text
pytest: 74 passed, 1 warning in 2.63s
coverage: 2573 statements, 295 missed, 89% total
ruff check: 5 errors
ruff format --check: 9 files would be reformatted
mypy: 1 error in 1 file (54 source files checked)
startup: exit 0, six prerequisite checks passed
```

## Current Slice 1 gate

Run from the repository root against either the normal or frozen verification environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-slice1-gates.ps1
powershell -ExecutionPolicy Bypass -File scripts/run-slice1-gates.ps1 -PythonEnvironment tmp/verify-venv
```

Latest frozen-environment result:

```text
uv sync --frozen --extra dev: 47 packages installed
pytest: 106 passed, 1 dependency warning
coverage: 3156 statements, 348 missed, 88.97%
ruff lint: clean
ruff format: 111 files formatted
mypy: 57 source files clean
detect-secrets: 0 application candidates
vulture: 0 findings at >=80% confidence
Slice 1 Code Craft: 6 files clean
Slice 1 Test Craft: 2 files clean
```

## Current Slice 2 gate

Run from the repository root against either the normal or a frozen verification environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-slice2-gates.ps1
powershell -ExecutionPolicy Bypass -File scripts/run-slice2-gates.ps1 -PythonEnvironment tmp/verify-slice2
```

Latest pre-handoff result:

```text
pytest: 164 passed, 1 dependency warning
coverage: 4086 statements, 462 missed, 88.69%
ruff lint and format: clean; 128 files formatted in final clean clone
mypy: 66 source files clean
vulture: 0 findings at >=80% confidence
detect-secrets: 0 application candidates after repairing Windows separator exclusion
Slice 2 Code Craft: 9 files clean
Slice 2 Test Craft: 3 files clean
```

## Current Slice 3 gate

Run from the repository root against either the normal or a frozen verification environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-slice3-gates.ps1
powershell -ExecutionPolicy Bypass -File scripts/run-slice3-gates.ps1 -PythonEnvironment tmp/verify-slice3
```

Latest pre-handoff result:

```text
pytest: 205 passed, 1 dependency warning
coverage: 4846 statements, 556 missed, 88.53%
focused Slice 3 suite: 41 passed
ruff lint and format: clean; 167 files formatted in the independent clean clone
mypy: 75 source files clean
vulture: 0 findings at >=80% confidence
detect-secrets: 0 application candidates
Slice 3 Code Craft: 10 files clean
Slice 3 Test Craft: 5 files clean
```
