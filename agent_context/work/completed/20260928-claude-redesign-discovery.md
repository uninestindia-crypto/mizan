# Active work: product redesign — discovery and understanding (no product edits)

STATUS: COMPLETED  
OWNER: Claude Code session (founder request 2026-09-28: redesign/recreate to top-tier quality, assets via Codex image generation, then installer; "explain what you understood" first)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-28  
STARTING_REVISION: 3957937ac (main)  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`, read-only except the paths below

## Objective

Test the current product as a user sees it, inventory its surfaces, and explain back to the founder
what was understood before any redesign work starts.

## Owned paths

- `.claude/launch.json` (new: preview config serving the app on 127.0.0.1:8765)
- this record

## Non-goals

- No edits to `src/**`, `installer/**`, `scripts/**`, `tests/**`, or any path claimed elsewhere.
  25 active records name `server/ui`, `server/static`, `server/app.py` or `quantos_studio.py`.
- No clicks on action controls (ingest, training, shadow control, paper orders) while testing.
- No Codex image generation yet.

## Findings (app served at main 3957937ac via `.claude/launch.json`, walked in the built-in browser)

- Product shape: 12 tabs named after the internal pipeline (Data & Manifests, Features & Labels,
  Governed Ridge, Holdout & Stress, Backtest & Ledger, Shadow Monitor, Paper Pilot, Options Lab,
  Monte Carlo, Risk Governor, Diagnostics) plus `/live`. The first screen shows "Set
  QUANTOS_EVIDENCE_ROOT before using governed evidence endpoints"; most panels read "Not trained",
  "Not run", "No campaign configured" or "—". The data picker offers 5 symbols.
- Defects: (1) `/live` has one 18,603-char inline script and `security.py:55` sets
  `script-src 'self'`, so it never runs (true in the committed version too); the clock stays
  `--:--:-- IST`. Task chip spawned. (2) `/ui/journeys` renders raw JSON. (3) Google Fonts are
  blocked by the same CSP, so the designed fonts never load. (4) The console shows one 503 and two
  404 resource errors on `/`.
- Frontend: about 7,000 lines of hand-written HTML/CSS/vanilla JS, much of it HTML inside Python
  strings (`server/ui/*.py`, `static/index.html`, `static/app.js`). 61 routes in `app.py`, most
  duplicated under `/api` and `/api/v1`.
- Tooling: codex-cli 0.156.1, `image_generation` feature stable and enabled, ChatGPT login. The
  image model version cannot be read from the CLI. Node v24.19.0 / npm 11.17.0; Claude CLI present;
  no Antigravity CLI.
- Collision surface: 25 active records name UI/server paths; the paper-book system test runs to
  2026-10-28. Any redesign needs its own worktree and branch.

## Next safe action

Done: explanation delivered; founder said "execute it". Build continues in `20260928-claude-retail-redesign-build.md`. `.claude/launch.json` stays (uncommitted) for previews.
