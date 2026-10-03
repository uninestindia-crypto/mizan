# NOTICE: one read-only route added to `server/app.py`, under its further claims

STATUS: NOTICE (additive; no other record is edited)  
FILED_BY: Claude Code (Opus 5.5), `20260928-0010Z-claude-live-dashboard-csp.md`  
FILED_UTC: 2026-09-28  
FOR:
- `20260824-codex-real-journey-api-wiring.md` (Codex, HANDED_OFF_CERTIFIED_PENDING_INTEGRATION)
- `20260928-claude-retail-redesign-build.md` (Claude Code, ACTIVE; handoff
  `handoffs/20260928-claude-retail-redesign-handoff.md`), branch `claude/retail-redesign`, same base
  `e787ac462`
- `20260904-antigravity-claude-fable-analysis.md` (Antigravity, ACTIVE), which claims `app.py` for its
  diagnostic endpoints. Added after filing: the first search for claimants looked for records naming
  `live_dashboard.py` or `security.py`, and this one names neither. The route below does not touch
  the diagnostic endpoints.

AUTHORIZATION: founder answer, 2026-09-28, to an explicit question naming these claims ("Full fix").
The Antigravity claim on the same file is covered by
`20260928-NOTICE-live-dashboard-csp-fix-under-antigravity-claim.md`.  
BRANCH: `claude/amazing-lamport-e18bd1`. Not merged at filing.

## The whole change to `app.py`

One route, inserted directly after `get_paper_pilot_live_status` and before the
`# UI Views & Static Asset Delivery` banner (between base lines 1351 and 1352; 18 added lines, none
changed or removed, no import added):

```python
@app.get("/api/xs-monthly/status")
def get_xs_monthly_status() -> dict[str, Any]:
    # returns logs/xs_monthly_new/paper_watch/state.json as written; NOT_RUNNING when absent;
    # {"status": "ERROR", "error": ...} when unreadable -- the same shape as its neighbour
```

Why: `/live`, which the app serves and links to (`templates.py:67`), polled URLs only
`scripts/serve_live_dashboard.py` answered, so its XS tab could never fill under the app. The page now
polls `/api/xs-monthly/status`, which that script already served, and this route makes the app answer
it too. Tests: `tests/test_live_dashboard_csp.py` (present, absent, corrupt).

## For the retail redesign

- Your planned `app.py` edits (v2 router include, `/` → SPA, old console at `/classic`) start at the
  `@app.get("/")` block. Nine unchanged lines (the banner and the `/static` mount) separate it from
  this insertion, so the two are expected to merge cleanly unless you also edit that mount.
- `/live` keeps its URLs. Its behaviour now lives in `static/live_dashboard.js`, loaded from
  `/static/live_dashboard.js`. If you remount `/static` or move `STATIC_DIR`, keep that path served;
  `tests/test_live_dashboard_csp.py` fails if it is not.
- Your `/api/v2` frontend will meet the same `script-src 'self'`; the inline-script trap is the one
  this fixed.

## For Codex

The certified `/api/v1` contract is untouched. The route is unversioned, like its neighbour
`/api/paper-pilot/live-status`, because both serve the `/live` page and the standalone script already
used this URL. No certified figure (the `474795f` adjudication) is affected; those were measured at a
historical revision.

## What this invalidates

Nothing either record pins as evidence.
