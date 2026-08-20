# CODE PROFILE — QuantOS

## Product type

QuantOS is a Python library/domain core, local FastAPI service, data/ML pipeline, Windows launcher/build CLI, and plain-browser UI.

This tightens public compatibility, zero hidden global state, typed failures, timeouts, idempotency, observability, deterministic reruns, explicit schema evolution, atomic publication, truthful CLI exit codes, and explicit UI loading/error/empty/stale/partial states.

## Languages

- Python 3.12+ — domain, data/model pipelines, API, launcher, packaging, and tests. The verified development runtime is Python 3.13.
- JavaScript (browser ES2022) — local dashboard behavior only.
- HTML5/CSS — semantic dashboard structure and presentation only.

## Python 3.12+

Style authority: PEP 8 via Ruff. Formatting is mechanical, never a review topic.  
Formatter: `.venv\Scripts\python.exe -m ruff format .`  
Linter: `.venv\Scripts\python.exe -m ruff check .`  
Typechecker: `.venv\Scripts\python.exe -m mypy src launcher.py scripts`

Naming:

- functions/variables/modules: `snake_case`
- types/classes: `PascalCase`
- constants: `UPPER_SNAKE_CASE`
- private/internal: `_leading_underscore`
- remote reads use `fetch`; local reads use `get`; constructors/factories use `create`

Errors:

- Signal expected failures with a typed project exception or an explicit immutable outcome.
- Stable error codes, not human messages, are the branching contract.
- Preserve causes with `raise ... from error` and add operation/instrument context once.
- Never use bare `except`, return empty data for dependency failure, or log authorization/provider bodies.

Modules:

- A Python package is the domain boundary; public names are explicitly re-exported by its `__init__.py` only when needed.
- Domain packages do not import FastAPI, filesystem locations, or provider DTOs.
- Delivery and adapters translate to the domain at their boundary.
- Cycle checks: Ruff/mypy plus `.venv\Scripts\python.exe -c "import quant_system"`; formal import-boundary lint remains a release-baseline task.

Testing:

- Framework: pytest.
- Convention: `tests/test_*.py`; tests name observable behavior and use per-test temporary paths.
- Network is faked at the owned HTTP boundary; one scheduled real-provider contract check is separate from the default suite.

Thresholds:

- Maximum function lines: 50; table-driven schema/error mappings may exceed this only with an explicit craft annotation and reason.
- Maximum nesting: 3.
- Maximum parameters: 4; group related values into an immutable dataclass.

Idiom notes:

- Prefer frozen, slotted dataclasses for fixed domain values and Pydantic models only at HTTP/config boundaries.
- Prefer comprehensions only when one level and immediately readable; nested comprehensions become named loops/functions.
- EAFP is allowed only with narrow exception types and explicit behavior.
- `Decimal`, integer paise, and RFC 3339 aware timestamps are mandatory in governed finance/data contracts.

## JavaScript ES2022 (browser)

Style authority: existing semicolon-terminated browser style until a formatter is introduced in the frontend slice.  
Structural checker: `node scripts/check-code.mjs src/quant_system/server/static`  
Linter/typechecker: not currently configured; this is an explicit G4/G5 baseline gap, not a pass.

Naming:

- functions/variables: `camelCase`
- classes/types: `PascalCase`
- constants: `UPPER_SNAKE_CASE`
- private module values: unexported lexical bindings

Errors and state:

- Fetch failures become explicit typed UI states; no empty catch and no success fallback.
- Server results are authoritative; the browser does not calculate financial/model results.
- Variable content uses `textContent` and DOM construction, never `innerHTML`.
- Timeouts/cancellation use operation resources; no sleeps or duplicate submission.

Modules and testing:

- Browser code imports no Python/server internals and accesses only `/api/v1` contracts.
- E2E tests use a real loopback server and role/test-id selectors; unit tests fake `fetch` at the owned client wrapper.
- Maximum function lines 50 and nesting 3.

## HTML5/CSS

Style authority: semantic HTML, valid CSS, and the project design/accessibility laws.  
Naming: CSS custom properties and classes use lower kebab-case; element IDs are stable behavior hooks only where semantic roles are insufficient.  
Boundaries: no inline scripts, inline event handlers, financial calculation, secret, or user/provider HTML.  
Testing: accessibility and critical journeys are verified in the professional desktop slice; CSP is verified at the real server boundary.
