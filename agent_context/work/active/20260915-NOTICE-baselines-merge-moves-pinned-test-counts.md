# NOTICE: merging the report-baselines branch moves two pinned test counts

FILED_UTC: 2026-09-15T09:25:00Z  
FILER: Claude Code (Opus 5)  
TYPE: NOTICE — additive, per PROTOCOL §8.4. The affected record is **not** edited.

## Affected record

`agent_context/work/active/20260914-1520Z-claude-short-horizon-multiplicity-rescore.md`, line 218,
pins as its own verification evidence:

| Command | Pinned |
|---|---|
| `uv run pytest tests/ -q` | **1,577 passed** |
| `uv run pytest` reverse file order | **1,578 passed** |

## What the merge changes

`claude/paper-report-baselines` (`a85c4b8f`, fast-forwarded into `main` on founder instruction,
2026-09-15) adds `tests/test_paper_report_baselines.py`, **9 new cases**.

| | Before | After |
|---|---:|---:|
| Collected on `main` | 1,578 | **1,587** |

Measured at `a85c4b8f`, not inferred, both orders the CI matrix runs:

| Command | Result |
|---|---|
| `pytest tests/ -q` | **1,587 passed** in 581.47s, exit 0 |
| reverse file order (`Get-ChildItem tests/test_*.py \| Sort-Object Name -Descending`) | **1,587 passed** in 589.01s, exit 0 |

Both orders green. The 9 added cases load the runner through `importlib` inside an `os.environ`
snapshot, following `test_paper_pilot_carried_session.py`; the reverse run is what confirms that
snapshot does not leak into later tests rather than merely being intended to.

The pinned figures are not wrong at the revision they were measured at. They are superseded as a
description of `main` from `a85c4b8f` forward.

## What is NOT invalidated

Nothing that record concluded. The 9 added cases cover a new reporting helper in
`scripts/run_paper_pilot_session.py` and touch no short-horizon path, no evaluator, no trial
ledger, no deflated Sharpe, and no multiplicity ordinal. Its coverage, ruff, mypy and audit results
stand; only the raw suite totals move, and they move by exactly the 9 cases added here.

Owner of that record: no action is needed unless you intend to re-cite the totals as current. If
you do, re-measure rather than adding 9 — the count had already drifted from `CURRENT.md`'s
recorded 1,519 before this work, and arithmetic on a stale baseline is how that figure got stale in
the first place.

## Related

- `20260915-0900Z-claude-paper-report-baselines.md` — the work record.
- `20260915-NOTICE-paper-report-baselines-under-two-claims.md` — the two ACTIVE claims on
  `scripts/run_paper_pilot_session.py` crossed by the edit itself.
- `agent_context/CURRENT.md` records **1,519 passing**, which was already stale by 59 cases before
  this merge. That file is claimed elsewhere and is not edited here.
