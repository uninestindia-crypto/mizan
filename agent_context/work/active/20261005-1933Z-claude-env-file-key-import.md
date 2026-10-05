# Active work: bulk-import keys and secrets from .env / .env.local files

STATUS: HANDOFF_REQUIRED  
OWNER: Claude Code (cloud session)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-05T19:33:00Z  
STARTING_REVISION: eaba6da92c018a31160baa9f22d39a9d4fbe43fe  
WORKTREE_OR_BRANCH: `/home/user/mizan` (the cloud clone), branch `claude/wonderful-wozniak-6ek6zl`. No other worktree exists (`git worktree list`).

## Objective

Founder instruction, 2026-10-05: "the platform after installer when installed i am running i should be able to
bulk upload all key and secret from uploading .env or .env.local or so on instead of copy pasting".

In the installed app, Settings -> Accounts & keys gets an **Import from .env** control. The founder picks (or
drops) one or more dotenv files, sees which keys were found and what would change, and confirms. Confirmed
keys go into Windows Credential Manager through the same store the paste boxes use.

## Owned paths

- `src/quant_system/server/v2/env_import.py` (new): parse, merge by dotenv precedence, plan, apply
- `src/quant_system/server/v2/credentials.py`: `_MAX_BLOB` -> public `MAX_SECRET_BYTES` (rename only)
- `src/quant_system/server/v2/router.py`: one route, `POST /credentials/import`
- `src/quant_system/server/v2/schemas.py`: `EnvFileUpload`, `CredentialImportRequest`
- `src/quant_system/config/env.py`: one keyword-only option on `parse_env_text` (default unchanged)
- `frontend/src/lib/envFile.ts` (+ `.test.ts`) (new): decode bytes (UTF-8/UTF-16/BOM), file ordering
- `frontend/src/components/EnvImport.tsx` (new): the import dialog/card
- `frontend/src/pages/Settings.tsx`: mount the component in `Accounts()` only
- `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts`: one mutation and its types
- `tests/test_credentials_import.py` (new)

## Non-goals

- No new secret names. `SECRETS` in `credentials.py` is not edited, so a name the store does not manage
  (for example `AWS_BEARER_TOKEN_BEDROCK`, `QUANTOS_ORDERS_WEBHOOK_URL`) is reported as skipped, by name only.
- No change to how `.env` is loaded at startup (`load_env_file` behaviour is unchanged).
- No export of stored secrets. Values stay write-only from the UI's point of view.
- No release is cut from this record; see Next safe action.

## Plan

1. Claim paths; file notice for the `frontend/**` / `server/v2/**` claim. DONE
2. Backend: `env_import.py` + routes + schemas, test-first. 
3. Frontend: decoder util + component + wiring, vitest for the util.
4. Gates: ruff, ruff format, mypy strict on touched src, pytest, tsc, vitest, vite build.
5. `python scripts/release_status.py`; report whether a release is due.
6. Commit explicit paths only; detect-secrets on the diff; push to the designated branch.

## Decision rationale

- **Server parses, browser only reads bytes.** `config/env.py` already has the tested parser used at startup;
  a second parser in TypeScript would drift. The browser decodes bytes (needed because PowerShell 5
  `>` writes UTF-16 LE with BOM, which `file.text()` turns into garbage) and sends text.
- **Two-phase, no values in responses.** `dry_run=true` returns per-name status (new / replaces / same /
  unmanaged / empty / too long), never a value, so a preview cannot leak a secret into logs or screenshots.
  Apply re-sends the text with the selected names. Rejected: a server-side upload cache keyed by id
  (state to expire and clean up, for no benefit on a loopback app).
- **Precedence follows dotenv convention** (`.env` < `.env.<mode>` < `.env.local` < `.env.<mode>.local`), so
  uploading `.env` and `.env.local` together gives the value the founder's other tools would use. Conflicts
  are reported by name.
- **Unquoted inline comments are stripped on import only** (`KEY=abc # note`). The startup loader keeps its
  documented "no trailing comment" rule; changing it is out of scope.
- **Per-key results, not all-or-nothing.** One over-long value must not discard forty good ones.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`, `git worktree list`, `git branch --list` | PASS | clean; one worktree; branches `claude/wonderful-wozniak-6ek6zl`, `main` |
| `uv sync --frozen --extra dev` | PASS | environment for gates |
| `pytest tests/test_credentials_import.py` | PASS | 20 tests; with `test_credentials_v2.py` 25 |
| `pytest tests` (whole suite, container credential variables unset as on CI) | PASS | **2,633 passed, 17 skipped** (Windows-only / Tk), 156.93s. Ran before the final parser fix below; the touched suites were re-run after it (25 + 11 passed) |
| Bug found in my own diff review: `KEY= # paste it here` parsed as the value `# paste it here` | FIXED | test written first and seen red; `_strip_inline_comment` now treats a `#` after whitespace as a comment even right after `=`; `KEY=#abc` still kept |
| axe (wcag2a/aa, 2.1aa), Accounts page and open review dialog, light and dark | PASS for this work | 0 violations in the new card and dialog. One `button-name` (10 nodes) on the existing show/hide eye buttons in the Upstox/AI cards, present before this work |
| Mutation checks on `env_import.py` (precedence ignored; values in `repr`; unmanaged names writable) | PASS | each mutation made 1-2 tests fail red; file restored byte-identical |
| Test isolation: import tests then a probe asserting no managed name is left in `os.environ`, names unset | PASS | `delenv` alone leaks on CI; fixture now sets then deletes |
| `ruff check .` / `ruff format --check .` (repo-wide) | PASS | 936 files formatted |
| `mypy --platform win32 src launcher.py scripts` | 299/300 clean | one error: optional `webview` stub missing in `shell/native_window.py`, not touched; Windows CI installs it |
| `vulture` / `check-code.mjs` / `check-tests.mjs` on touched files | PASS | clean after splitting `build_plan` |
| `detect-secrets scan --no-verify` on touched files | 0 candidates | `Settings.tsx` shows 8 `Secret Keyword` hits at HEAD too (the `secretName: "..._API_KEY"` lines); verified by scanning a copy of HEAD's file in-repo. Not mine, not secrets; left alone |
| `tsc --noEmit`, `vitest run` (6 files), `vite build` | PASS | 56 tests |
| Real browser (Chromium) against the real server with an in-memory credential store | PASS | UTF-16LE `.env` + UTF-8-BOM `.env.local`: precedence, inline comment, blank, unmanaged name, already-saved, replace; Cancel saves nothing; unticked row not saved; drag-drop; unusable file explained; 0 secret values in any API response; 0 page errors |
| `release_status.py` | DUE | clone had no tags; after `git fetch origin --tags`: 10 user-visible commits since `v2.3.0` before this work |
| `tests/test_config_env.py::test_configured_env_file_reaches_the_upstox_client` | FAIL here, environmental | this container sets `UPSTOX_ANALYTICS_TOKEN`; passes (11/11) with it unset. Already named in `20260901-NOTICE-dashboard-threading-under-antigravity-claim.md` |

## Blockers and conflicts

`20260928-claude-retail-redesign-build.md` (HANDOFF_REQUIRED) names `frontend/**` and `src/quant_system/server/v2/**`.
Its branch is already on `main` (see `20261005-NOTICE-live-paper-readiness-edits-under-other-claims.md`).
Proceeding on the founder's explicit instruction for this feature, as that notice did; additive notice filed:
`20261005-NOTICE-env-import-edits-under-retail-redesign-claim.md`. No one else's edits are reverted or reformatted.

`scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1` are PowerShell and this is a Linux
container, so they cannot run here. NOT RUN, stated rather than skipped silently.

## Stop point

Feature implemented and verified (see above). Committed to the designated branch, not merged, no PR opened (none requested).

## Known limits, stated

- A stale `.env` in the install folder still wins over Credential Manager at the next start, because the
  launcher loads `.env` first and never overrides (`credentials.apply_to_environment`). Pre-existing, and true
  of pasted keys too; the import does not change it.
- Names the store does not manage (e.g. `AWS_BEARER_TOKEN_BEDROCK`, `QUANTOS_ORDERS_WEBHOOK_URL`) are listed as
  "not used by QuantOS" and not saved. Adding names is a one-line `SECRETS` change the founder can ask for.
- Multi-line quoted values are not parsed (the shared parser is line-based).
- Windows Credential Manager path was exercised only through an in-memory stand-in in this Linux container; the
  real Win32 calls are unchanged code (`CredentialStore.set`), covered by the existing Windows-only test.

## Next safe action

Founder decision: merge, then cut the release. The installed app only gets this through a release built on
Windows (`scripts/release.ps1`), which cannot run in a Linux container. Release is already DUE independent of this
change (10 user-visible commits since v2.3.0).
