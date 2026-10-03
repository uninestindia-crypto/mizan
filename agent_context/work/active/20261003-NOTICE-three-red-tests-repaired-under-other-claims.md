# NOTICE: three tests that were already red were repaired under other agents' claims

STATUS: ACTIVE (notice)  
FILED_BY: Claude Code, on founder instruction ("do what you need to do", 2026-10-03; the plan was to make the
repository checks green before pushing)  
FILED_UTC: 2026-10-03  
AFFECTS: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` and
`20260914-1740Z-claude-rights-issue-fail-closed.md` (both name `tests/test_corporate_actions.py`);
`20260824-codex-real-journey-api-wiring.md` (names `tests/test_server_supervisor.py` "only if required");
`20260824-codex-real-journey-api-wiring.md`, `20260904-antigravity-claude-fable-analysis.md`,
`20260928-claude-retail-redesign-build.md` (name `src/quant_system/server/static/index.html`)

All three failed on a clean `git archive` of the commit before this session, so none came from the first-run work.

| Test | Cause (measured) | Change |
|---|---|---|
| `test_ui_journeys::test_static_index_html_contains_all_seven_journeys` | the 2.0.1 bump commit did not update the three `v2.0.0` strings in `static/index.html` | the three strings now read `v2.0.1` |
| `test_server_supervisor::test_supervisor_heartbeats_and_progress_tracking` | a spawned worker takes about 3 s to start on the Snapdragon X reference machine, so a 0.8 s task finishes at about 4 s against a 3.0 s deadline (heartbeat itself arrives at 0.01 s) | both waits use `_WORKER_START_BUDGET = 15.0`; the waits were already condition-based, only the deadline moved |
| `test_corporate_actions::test_the_real_heg_demerger_is_left_unresolved...` | it read `data/evidence/market-cache/nifty500-refresh-20230828-20260827/corporate-actions/nse-corporate-actions-HEG.json`, which a refresh on 2026-09-30 overwrote with `[]` (provenance: `status FETCHED, count 0`). NSE's API now returns no actions for symbol HEG, even from 2016 (checked live 2026-10-03) | the test reads `tests/fixtures/nse-corporate-actions-HEG-20260910.json`, the authority as fetched on 2026-09-10 (17 records, the 07-Sep-2026 Demerger included), with its provenance file beside it, both recovered from commit `ee1b0cb38`. The evidence cache was not touched |

## A data finding for the owners of the ingestion refresh (not changed here)

The refresh replaced a 17-record file with an empty list because the source's answer changed, and recorded it as a
clean `FETCHED`. 35 files in that cache are `[]`; most are recent listings with genuinely nothing to report, but HEG is
a real loss of history. A refresh that would replace a non-empty list with an empty one should keep the earlier file
and say so. The same hazard applies to the first-run download added this session: it writes whatever NSE returns, and
only refreshes files it wrote itself.

Numbers this invalidates: none. `tests/test_corporate_actions.py` still has 66 tests.
