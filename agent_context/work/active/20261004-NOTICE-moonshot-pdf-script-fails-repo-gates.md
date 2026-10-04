# NOTICE: `scripts/generate_moonshot_pdf.py` (uncommitted) fails the repository's lint and type gates

STATUS: ACTIVE (notice)  
FILED_BY: Claude Code, record `20261004-claude-stranger-walkthrough-fixes.md`  
FILED_UTC: 2026-10-04  
AFFECTS: `20261004-antigravity-quantos-moonshot-pdf.md` (already in `work/completed/`, files still untracked)

Seen in the shared checkout while committing unrelated work. Nothing was edited, staged or committed.

`scripts/generate_moonshot_pdf.py` is untracked, and on this tree `ruff check .` reports 5 errors (four unused `reportlab` imports,
`F401`, and an unsorted import block, `I001`) and strict `mypy src launcher.py scripts` reports 26 errors, all in that file (`reportlab` has
no type stubs). CI runs both, so committing it as it stands turns the gate red, and a red `ruff format`/`mypy` step skips every test step
after it (see `agent_context/CURRENT.md`, "CI: green for the first time since 2026-09-02").

Suggested before committing: `ruff check --fix` for the imports, and either add `reportlab.*` to the `ignore_missing_imports` modules in
`pyproject.toml` (a shared file, so a single owner decides) or type the calls. The PDF and the completed record are untouched.
