# Handoff: live-market paper trading readiness (audit done, open items for the founder)

STATUS: READY_FOR_ADOPTION  
FROM: Claude Code (cloud container)  
TO: unassigned  
DATE_UTC: 2026-10-05  
ACTIVE_RECORD: `agent_context/work/active/20261005-claude-live-paper-readiness-audit.md`

## Objective and acceptance criteria

Decide independently whether the platform is ready for live-market paper trading with two delivery
modes (A: owner copies orders by hand; B: owner grants direct broker access), and bring the UI to a
consumer-grade standard. Acceptance: an evidence-backed verdict, bounded repairs with tests, and
every open item named with an owner.

## Completed

- Verdict and 14 numbered open findings: `reports/live_paper_readiness_20261005/REPORT.md`.
- Stale "tomorrow's orders" guard, creation refusal, and the order ticket (Mode A).
- Phone layout, contrast, touch-target, Shariah 404 and honesty fixes. `mizan_cli predict` Linux crash.
- Six Windows-only tests marked so a Linux or cloud run is green.

## In progress

Nothing partial. Mode B (direct broker access) is deliberately **not** started: it is T4 work and
needs its own charter.

## Files and ownership

Committed on `claude/dazzling-brown-yn5qu3`; no pull request was opened. Source, test and frontend
files are listed in the active record under "Owned paths". The frontend build output under
`src/quant_system/server/static/app/` is gitignored and was rebuilt locally only.

## Verification

See the active record, "Commands and outcomes".

## Known failures and risks

- `tests/test_release_packaging.py::test_setup_gui_components` (needs `tkinter`) and
  `tests/test_windows_installer.py` (needs `pefile`) are red on Linux. Their files are claimed by
  other active records, so they were left alone.
- The live dashboard (`/live`) is broken under the app's CSP on this branch. The fix is commit
  `b79351813` on `claude/amazing-lamport-e18bd1`, which is not in this checkout.
- A release is due (`release_status.py`) and cannot be cut from Linux.
- Nothing here was run against a live broker feed; no token was available.

## Exact stop point

Report, tests and repairs written; gates run; changes committed and pushed to the designated branch.

## Next safe action

1. Push or merge `claude/amazing-lamport-e18bd1` so the live dashboard works.
2. On the Windows install root: pull this branch, run `scripts/audit-agent-claims.ps1` and
   `scripts/audit-disk-layout.ps1` (NOT RUN here, no PowerShell), then decide whether to cut the
   release with `scripts/release.ps1 -DryRun` first.
3. Run one governed live paper session with `UPSTOX_ANALYTICS_TOKEN`, then commission an
   independent adjudication of the live paper path (`.launch/RED-TEAM-BRIEF-20260901-ROUND7.md` was
   author-run and says so).

## Do not do

- Do not treat the order ticket as a reason to trade real money: every published model is
  `RESEARCH_ONLY`.
- Do not start Mode B without a separate T4 authorisation.
- Do not change what either running paper book trades before 2026-10-28
  (`20260924-NOTICE-paper-books-system-test-running.md`).
- Do not edit `frontend/` or `server/v2/` on the strength of the stale
  `20260928-claude-retail-redesign-build.md` claim without checking `git log -- frontend`: that
  branch is already on `main`.
