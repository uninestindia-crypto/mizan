# Active work: a Research screen that runs EmbeddingGemma 2 from inside the app (no terminal)

STATUS: COMPLETED (released as v3.4.0, 2026-10-10)  
OWNER: Claude Code (Sonnet 5.5)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-10T11:00:00Z  
STARTING_REVISION: 764f09130 (main, 3 commits ahead of origin/main, unpushed)  
WORKTREE_OR_BRANCH: `D:\Quant OS Project\Mizan` on `main` (shared checkout). Another session works in its own worktree
(`claude/ai-assistant-live-models-order-agent`, record `20261010-0943Z-claude-sonnet-ai-assistant-live-models-order-agent.md`); my paths avoid its
owned list. Shared files I must touch are listed below and kept to one additive edit each.

## Objective

GOAL_LINE: G3 (a non-technical person installs it and it runs) with G5 (honest about the model) and G2 (one app). Founder instruction,
2026-10-10: complete EmbeddingGemma 2 so a banker, trader or investor can use it from the platform with no terminal and no file editing.

Measured in the scratch probes the same day:

- Torch route (what runs today on a developer machine): 1.5 GB weights + 1.1 GB of libraries, about 2 GB memory. Not shippable to a factory-new laptop.
- ONNX route: `onnx-community/embeddinggemma-2-ONNX` (Apache 2.0, ungated, revision pinned below). The 8-bit text model is 299 MiB + a 31 MiB tokenizer.
  `onnxruntime` 1.31 and `tokenizers` 0.23 install natively on this ARM64 laptop. The graph's `sentence_embedding` output already pools, projects
  to 768 and returns unit vectors; the unused image/video/audio inputs take empty arrays. Against the PyTorch float32 reference: cosine
  0.99992 to 0.99996 on five documents, a query and a 1,300-token text; identical ranking, also at 256 dimensions. Peak memory 676 MB.
  Speed on this CPU: about 0.2 to 0.3 s per short text.

Decision: the real engine for users is the 8-bit ONNX model, downloaded once from inside the app (about 330 MB), with every file's SHA-256 pinned
in the code. The torch path stays as a developer-machine option. The built-in keyword matcher stays as the labelled fallback.

## Owned paths

- New: `src/quant_system/research/embedding_onnx.py` (pinned files, safe downloader, ONNX embedder), `src/quant_system/server/v2/research_routes.py`,
  `frontend/src/pages/Research.tsx`, `frontend/src/components/research/**`, `frontend/src/lib/research.ts` (hooks and types, kept out of the shared
  `queries.ts`/`types.ts` on purpose), new tests for each.
- Edited (mine): `src/quant_system/research/embedding_gemma.py`, `src/quant_system/research/rag_engine.py` (only if needed),
  `src/quant_system/server/v2/hardware.py` (card status), `tests/test_embedding_gemma_honesty.py`, `tests/test_no_terminal_copy.py` (add my routes file
  to the scanned list).
- Shared, one additive edit each: `src/quant_system/server/v2/router.py` (include the research router in `register_api`; not the CLI, settings or
  auto-update routes the other session owns), `frontend/src/App.tsx` (one route), the sidebar/nav file (one entry), `pyproject.toml` and `uv.lock`
  (add `onnxruntime` and `tokenizers`), the PyInstaller specs (collect those two packages).

## Non-goals

- No change to the Quant SLM weights or any model trial. No change to Shariah rules.
- No bundling of torch. No third-party model host other than the pinned Hugging Face revision.
- Nothing in the other session's owned list is edited.

## Plan

1. Pin the files (sizes and SHA-256, cross-checked against Hugging Face's own record).
2. Dependencies, then `embedding_onnx.py` and tests, including a real-file test run here.
3. Provider: an `onnx` backend ahead of torch in `auto`; status and labels.
4. Research service, routes (status, search, set up, cancel) and tests.
5. Research screen, hooks, nav, tests; check in the browser pane.
6. Packaging and a frozen-app end-to-end check.
7. Gates, commits, release, completion record, memory.

## Current step

Done.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| scratch probes (see Objective) | PASS | ONNX 8-bit vs torch float32 cosine ≥ 0.99992, same ranking |

## Files changed

- (none yet)

## Blockers and conflicts

The other session edits `queries.ts`, `types.ts`, parts of `router.py` and `state.py` in its worktree; my additions there are avoided or one-line.

## Stop point

Record filed, no code edited.

## Next safe action

Pin the model files.

## Progress, 2026-10-10 (updated while working)

Built and verified so far (each against the real thing, not only tests):

| Piece | Evidence |
|---|---|
| ONNX 8-bit text model, pinned revision, hashes checked | scratch probe: SHA-256 and size of all three files equal Hugging Face's own record; vectors match the torch float32 reference to cosine 0.99992 or better; same ranking at 768 and 256 dimensions |
| `embedding_onnx.py` (downloader, embedder) | 20 tests with a pretend network (resume, ignored resume, damaged file, no internet, refusal, cancel, low disk, insecure address and redirect) + 1 test against the real model files: pass |
| Provider `onnx` backend, `real_model_status`, disk memory of paper vectors | 106 related tests pass; questions are never written to disk (tested) |
| `research_service.py`, `research_routes.py` | 24 service tests + 10 route tests; routes added to `test_no_terminal_copy.py`'s scan |
| Research screen (`pages/Research.tsx`, `components/research/*`, `lib/research.ts`) | 16 screen tests; run in the real app: nav entry, keyword search, **real one-click download of 330 MB from Hugging Face inside the app, cancel, resume from the partial file, hash check, "ready"**, search by meaning, **real arXiv look-up (5 new papers added, saved)**, restart (model still on, 10 papers still there) |
| `/research` served by the server | caught live: the server answered 404 because `spa.py` lists the pages it serves; fixed, and `tests/test_spa_routes.py` now fails if any page in the app is not served |
| Top-bar title | caught live: it said "Page not found"; `screenName.ts` fixed + test |
| First-search speed | 12.3 s before, 3.7 s after a restart once paper vectors are remembered on disk |

Shared files touched, each with the smallest edit: `router.py` (import + include_router), `spa.py` (one page), `App.tsx` (lazy import + one route),
`Layout.tsx` (icon import + one nav entry), `screenName.ts` and its test (one line each), `pyproject.toml` + `uv.lock` (onnxruntime, tokenizers),
`installer/quantos.spec` (collect both packages), `scripts/timesfm_probe.py` (one `type: ignore` widened, see its NOTICE), `.claude/launch.json`
(a temporary entry, reverted).

Test copy used for the live checks: a throwaway app folder in the session scratchpad (`QUANTOS_APP_ROOT`), so the real `data/` was never used; its
first-run state was set up with the app's own settings code, no consent screen was clicked for anyone.

## Result

Released as **v3.4.0** (tag `v3.4.0`, release commit `69a21ac74`; installer 125.6 MB, up from 114.9 MB for the two libraries and the C++ files).
Gates on the release tree: 5,917 backend tests passed (7 skipped, 0 failed), 1,557 frontend tests passed, strict mypy clean on 469 files, ruff and
format clean, `detect-secrets` 0 candidates, `tsc` clean.

The packaged app (built from the final spec, run in an empty folder) was checked end to end: start 5.7 s; keyword search before anything is
downloaded; the real one-click download inside the app 42.8 s (SHA-256 of every file verified); status READY; search by meaning with the right
paper first. The model landed in `<app folder>/data/quantos2/models/embeddinggemma-2`.

## Found and fixed on the way (each caught by running the real thing, not by the tests that existed)

1. `/research` returned 404 from the server (the page list in `spa.py`); now fixed and `tests/test_spa_routes.py` fails if any page in the app is not served.
2. The top bar said "Page not found" for the new page (`screenName.ts`).
3. The first search after every restart read every paper through the model (12 s, and it would grow with the library); paper vectors are now remembered
   on disk, only for documents and never for what a person asks (3.7 s).
4. `readiness` now means "onnxruntime and tokenizers really import", not "a file exists", so no 330 MB download is offered on a computer that could not run it.
5. The app carries `msvcp140.dll`, `msvcp140_1.dll`, `vcruntime140_1.dll` (copied from this computer at build time), because PyInstaller warned that onnxruntime needs
   them and an older Windows may lack them. Not testable on such a machine from here.
6. The version script relabels the newest in-app "what's new" entry on every bump, so the 3.3.0 release shipped 3.2.1's text under 3.3.0. Entries for 3.4.0 and 3.3.0 are
   now real, 3.2.1 is restored, in `updates.py`, `Settings.tsx` and `CHANGELOG.md`. The script itself still needs a decision (see Next safe action).
7. The generated GitHub notes carried an outdated "about 1.5 GB" line from an earlier commit subject; the release page text was replaced with accurate notes.

## Not done, said plainly

- Not tested on a different computer or on Windows 10. The C++ runtime files are carried but unproven there.
- Match percentages are not calibrated: with matching by meaning an unrelated paper scores around 40%. The screen says so; a better scale needs a bigger library to calibrate against.
- The library starts with 5 built-in papers; arXiv look-ups add more, up to 300 kept. There is no screen to remove a saved paper.
- The Copilot has no tool for paper search yet (it would be an 18th tool; a test pins the tool list).
- The bump script's relabelling of the in-app notes and its skipped bump for an explicit version are not fixed (see the NOTICE).
- The old `uvicorn.lifespans.on` hidden import in `installer/quantos.spec` logs a PyInstaller error line; it was there before and the build succeeds.

## Stop point

Released, pushed, verified on GitHub. Working tree clean. This record moved to `work/completed/`.

## Next safe action

Decide how `scripts/bump_version.py` should treat the in-app notes (add a new entry per release instead of renaming the newest) and fix `scripts/release.ps1` so an explicit
`-Version` bumps; both are described in `20261010-NOTICE-release-script-skips-bump-for-explicit-version.md`.
