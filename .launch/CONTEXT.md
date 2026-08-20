# CONTEXT — QuantOS

## Stack

- Python 3.12+ package; baseline environment uses Python 3.13.15.
- FastAPI, Pydantic, Uvicorn, NumPy, SciPy, PyYAML.
- Plain HTML/CSS/JavaScript dashboard served locally.
- Pytest, Ruff, Mypy; PyInstaller Windows distribution.
- No database, cache, queue, authentication, or cloud deployment is present.
- External services: Upstox read-only market data, arXiv search, and optional local AI CLIs.

## Critical journeys

1. Start the desktop application from a clean installation and receive truthful diagnostics.
2. Run a deterministic equity backtest with next-bar execution, risk checks, costs, ledger reconciliation, and a tearsheet.
3. Simulate an NSE options strategy with valid pricing/Greeks, costs, and paper execution.
4. Change risk limits and observe the limits on every subsequent simulated order.
5. Request Upstox-backed data and receive broker data or a safe, explicit, actionable dependency failure/fallback.

## Environments

| Environment | Exists | Evidence / notes |
|---|---:|---|
| Local development | Yes | `.venv`, source tree, tests |
| CI | No | No workflow configuration found |
| Staging / preview | No | Local-only product |
| Production-like clean install | Partial | PyInstaller artifacts exist, but no reproducible clean-build evidence yet |
| Production | No | No deployment target or operating environment documented |

## Project law

- No `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, or CI policy was found.
- Repository skills define founder-mode, code, API, test, security, UI, and launch standards.
- UI work must follow `apple-grade-ui`.
- Financial logic is critical-path code and must follow Decimal, reconciliation, boundary, replay, and adversarial requirements.

## Repository state

- The directory is not currently a Git repository.
- Generated `build/`, `dist/`, installer build output, caches, and a virtual environment are present beside source.
- No `.env.example` or formal environment contract exists.
