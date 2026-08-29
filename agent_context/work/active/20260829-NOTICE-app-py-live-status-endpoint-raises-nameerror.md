# NOTICE: `/api/paper-pilot/live-status` raises NameError on every call

FILED_UTC: 2026-08-29
FILED_BY: Claude Code — `20260829-claude-ruff-repair-unclaimed-files.md`
STATUS: NOTICE (additive; the subject record is **not** edited, and neither is its code)
SEVERITY: **P2 Major** — one endpoint is unconditionally broken
SUBJECT_RECORD: `agent_context/work/active/20260826-antigravity-paper-trade-live-market-testing.md`
  (STATUS: ACTIVE), which owns `src/quant_system/server/app.py`

## The defect

`src/quant_system/server/app.py:1229` and `:1233`:

```python
@app.get("/api/paper-pilot/live-status")
def get_paper_pilot_live_status() -> dict[str, Any]:
    status_file = PROJECT_ROOT / "logs" / "paper_runs" / "live_paper_status.json"   # line 1229
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                return json.load(f)                                                  # line 1233
```

Neither name exists in the module. `grep '^import json'` returns nothing, and `PROJECT_ROOT` is
never defined or imported — only `from pathlib import Path` (line 21) is present.

**The endpoint therefore raises `NameError` on its first statement, on every call.** It is not a
partial failure or an edge case; the handler cannot execute at all.

Ruff reports both as `F821 Undefined name`. This is the CI gate catching a genuine runtime defect
rather than a style preference, which is worth recording on its own: run `32994595056` failed on
`ruff check .`, and two of those 44 findings were real bugs.

## Why this notice instead of a fix

`app.py` is in the subject record's owned paths and that record is `STATUS: ACTIVE` with
`Current step: Implementing scripts/run_paper_pilot_session.py`. AGENTS.md: "Never edit a path
claimed by another active record. Coordinate or stop."

The practical hazard matches the rule. This session has already observed a peer's broad commit
sweeping files unpredictably and server tests failing while files were being written. Editing a
module its author is mid-way through would either destroy their work or be destroyed by it.

## Suggested repair, for the owner

Two lines, at the module's import block:

```python
import json
```

and a definition for `PROJECT_ROOT` — the module already has `from pathlib import Path`, and other
scripts in this repository use `Path(__file__).resolve().parent.parent`; the correct depth from
`src/quant_system/server/app.py` to the install root is `parents[3]`.

A test that calls the endpoint would have caught this, and none does.

## Scope note

The founder asked for all 44 `ruff check .` findings to be cleared.
`20260829-claude-ruff-repair-unclaimed-files.md` cleared the **5 in unclaimed paths**
(`tests/test_live_universe_robustness.py`, `scratch/test_upstox_env.py`). The remaining **39** are
all in this record's owned paths and are left untouched:

| path | errors |
|---|---:|
| `scripts/run_paper_pilot_session.py` | 24 |
| `scripts/serve_live_dashboard.py` | 8 |
| `scripts/view_live_pnl.py` | 4 |
| `src/quant_system/server/app.py` | 3 |

`main` stays gate-red until the owner clears them or the founder overrides the claim. 25 of the 44
were auto-fixable with `ruff check --fix`.
