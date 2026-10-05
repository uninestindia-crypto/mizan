# NOTICE: the live-paper readiness work edited paths that other active records claim

STATUS: NOTICE (additive; no other record is edited)  
FILED_BY: Claude Code, `20261005-claude-live-paper-readiness-audit.md`  
FILED_UTC: 2026-10-05  
AUTHORIZATION: founder instructions of 2026-10-05, "make sure ui ux frontend is like apple created it
... check independently is the platform ready to go live market paper trading" and "open a pull
request for this branch and complete all dont stop till you get the result i want". PR:
https://github.com/uninestindia-crypto/mizan/pull/1  
BRANCH: `claude/dazzling-brown-yn5qu3`, base `3e2be9f0`. Not merged at filing.

## Paths edited that another active record names

| Path | Change | Records that name it |
|---|---|---|
| `frontend/**`, `src/quant_system/server/v2/**`, `tests/test_v2_*` | order freshness, order ticket, placements, health probes, UI fixes | `20260928-claude-retail-redesign-build.md` (its branch is already on `main`) |
| `src/quant_system/server/app.py` | two read-only routes: `/api/xs-monthly/status`, `/api/control/available` | `20260824-codex-real-journey-api-wiring.md`, `20260904-antigravity-claude-fable-analysis.md`, `20260826-antigravity-paper-trade-live-market-testing.md`, `20260928-claude-retail-redesign-build.md` |
| `src/quant_system/server/ui/live_dashboard.py`, `scripts/serve_live_dashboard.py` | the dashboard's script moved to `server/static/live_dashboard.js`; no inline handlers; no Google Fonts | `20260826-antigravity-paper-trade-live-market-testing.md`, `20260914-claude-paper-book-accounting-repairs.md` |
| `scripts/run_paper_pilot_session.py` | log clock is real IST; warning when `--upstox-token` is used | 25 records naming it |
| `scripts/run_scheduled_paper_session.py` | warns 90 days before the NSE holiday list ends | `20260821-*`, `20260910-*` records naming it |
| `tests/test_release_packaging.py`, `tests/test_windows_installer.py`, `tests/test_cli_bridge.py`, `tests/test_first_run_usability.py` | tests skipped where their Windows-only or desktop-only dependency is absent | release-manifest records |
| `tests/shariah/test_m3_stress_challenger.py` | warm-up in the measured shape (assertion unchanged) | none |
| `src/quant_system/shariah/**` | audit lines say `UNVERIFIED_SAMPLE`, not `VERIFIED` | none |

## An earlier fix exists elsewhere

`20260928-0010Z-claude-live-dashboard-csp.md` records a founder-authorised fix of the same defect as
commit `b79351813` on `claude/amazing-lamport-e18bd1`, "not pushed, not merged". That branch is not
on the remote, so this change re-implements the repair on the same design (script moved to static,
real no-session state, honest Start/Halt, one read-only XS route) and adds tests. **If that branch is
ever merged, expect conflicts in `live_dashboard.py`, `serve_live_dashboard.py` and `app.py`, and
prefer this branch's version unless the other has something this lacks.**

## Numbers this merge changes

- Repository test count: from 2,492 passed (measured on Linux before this work) to the figure in the
  work record; the CI test count on `main` was 2,5xx on Windows and moves too.
- mypy source files: `src/quant_system/server/v2/health.py` is new (+1 file).
- `tests/shariah/test_tier1_features.py`: +1 test.
- Nothing pinned by hash is changed: no evidence store, manifest or lock file was touched.
