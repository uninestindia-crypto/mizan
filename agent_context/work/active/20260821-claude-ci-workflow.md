# Active work: pinned Windows CI workflow

STATUS: HANDOFF_REQUIRED  
OWNER: Claude Code (Opus 5) session 21d82993  
TOOL: Claude Code  
STARTED_UTC: 2026-08-21T12:05:00Z  
STARTING_REVISION: `66fb04d`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

Add the pinned Windows CI workflow that `.launch/COMMANDS.md` records as missing, closing the
implementation half of open Major #1 ("No CI or protected remote"). The workflow must be green on
its first run; a red-on-arrival pipeline teaches everyone to ignore it.

## Owned paths

- `.github/workflows/ci.yml`
- `agent_context/work/active/20260821-claude-ci-workflow.md`
- `agent_context/work/completed/20260821-claude-ci-workflow.md`

## Non-goals

- Branch protection, required checks, or any GitHub repository setting. Those are account-level
  actions only the founder can take, and they are the other half of Major #1.
- Pushing, or triggering a run. Committing the file is the deliverable.
- Editing `.launch/COMMANDS.md` or `.launch/STATE.md` to mark Major #1 closed. Both are claimed by
  `20260821-0530Z-claude-slice4-certification.md`.
- Adding repository-wide Code Craft or Test Craft to the gate set. See "What CI does not run".

## Plan

1. COMPLETE - confirm no agent already owns CI work and that `.github/` does not exist.
2. COMPLETE - establish which gates pass repo-wide today, so CI starts green.
3. COMPLETE - write the workflow.
4. COMPLETE - validate the YAML and rehearse every gate in an isolated environment.
5. PENDING - founder review, then commit. Branch protection remains a founder action.

## Current step

Workflow written and every step rehearsed green from a frozen install. Nothing committed.

## Decision rationale

`agent_context/CURRENT.md` line 26 says "Protected remote / CI integration in progress". No active
work record claims it, no `.github/` exists, and the line predates every current record, so it is
stale program-level tracking rather than a live claim. Proceeding, and flagging it for the
reconciler.

Runner is `windows-latest`. The product targets a Windows x64 release (Slice 12), and the reference
development machine is Windows ARM64, but GitHub does not offer hosted Windows ARM64 runners.
Slice 12 already states ARM64 stays unadvertised until separately proven, so x64 CI matches the
release claim rather than the development machine.

Toolchain is pinned where a pin is verifiable. `uv` is pinned to `0.12.5`, the exact version this
repository's evidence was produced with. GitHub-owned actions are pinned to major version tags, not
commit SHAs: a SHA is the stronger supply-chain pin, but I cannot verify a specific SHA from this
environment, and an invented one would fail every run. Recorded as a follow-up rather than guessed.

### What CI runs

Every gate that passes repository-wide today, so the first run is green:

| Gate | Command | Locally verified |
|---|---|---|
| Format | `ruff format --check .` | 199 files formatted |
| Lint | `ruff check .` | All checks passed |
| Types | `mypy src launcher.py scripts` | 86 source files, clean |
| Tests | `pytest --cov=quant_system` | 272 passed |
| Dead code | `vulture src launcher.py scripts --min-confidence 80` | zero findings |
| Secrets | `detect-secrets scan --all-files` with the gate's exclusions | 0 candidates |
| Checker integrity | `check-code.mjs --self-test`, `check-tests.mjs --self-test` | both pass |
| Build | `uv build` | wheel and sdist built |

### What CI does not run, and why

Repository-wide Code Craft and Test Craft are excluded. `check-code.mjs src/quant_system` reports 55
legacy findings and `check-tests.mjs tests` reports 1, so adding them would make CI red from the
first commit and train everyone to ignore it. That debt is tracked as open Major #2, not hidden:
when it reaches zero the two commands belong in this workflow. The checkers' own `--self-test` runs
instead, which proves the tooling is intact without asserting the codebase is already clean.

The Slice gate scripts (`run-slice*-gates.ps1`) are also excluded. They assume a local
`.venv` layout and pin slice-specific evidence; CI proves the repository-wide baseline, while slice
certification stays a deliberate local and clean-clone activity.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `ls .github` | ABSENT | No prior CI. |
| `grep` for CI claims across active records | NONE | Only the stale `CURRENT.md` line. |
| `uv --version` | PASS | 0.12.5, the version pinned in the workflow. |
| `uv build --out-dir tmp/ci-build` | PASS | Built `quant_system-1.0.0-py3-none-any.whl` and the sdist. Closes the "Package/wheel build: Unverified" row in `.launch/COMMANDS.md`, which I may not edit. |
| YAML structural validation | PASS | Parses; 13 steps, `windows-latest`, 30-minute timeout, `pwsh` default shell. |
| `UV_PROJECT_ENVIRONMENT=tmp/ci-rehearsal uv sync --frozen --extra dev` | PASS | Frozen install into an isolated environment. |
| `uv run ruff format --check .` | PASS | 210 files already formatted. |
| `uv run ruff check .` | PASS | All checks passed. |
| `uv run mypy src launcher.py scripts` | PASS | 86 source files, clean. |
| `uv run vulture src launcher.py scripts --min-confidence 80` | PASS | Exit 0, zero findings. |
| `uv run pytest --cov=quant_system` | PASS | 272 passed; 5,830 statements / 660 missed / 89%. |
| `node scripts/check-{code,tests}.mjs --self-test` | PASS | 27/18 and 14/9. |
| Secret-scan step, run verbatim in PowerShell | PASS | `Application secret candidates: 0`. |

### Rehearsal isolation

`uv sync` is a repository-wide dependency operation, which PROTOCOL section 4 reserves for single
owner coordination, and the Slice 4 certification agent is using the shared `.venv` right now.
The rehearsal therefore ran against `UV_PROJECT_ENVIRONMENT=tmp/ci-rehearsal`, leaving `.venv`
untouched, and the environment was deleted afterwards.

### Defect found and removed during rehearsal

The first draft included `scripts/audit-agent-claims.ps1` as a CI step. That would have failed
every run. The script resolves the install root from its own location, but work records claim
absolute local paths such as `D:\quant_system`; on a GitHub runner the checkout lives elsewhere, so
those paths are legitimately absent and the audit reports `STALE` against a perfectly healthy
repository. Both audit scripts gate handoffs, not builds. Removed, with the reasoning recorded in
the workflow header so nobody re-adds it.

## Files changed

- `.github/workflows/ci.yml`: NEW. Single `gates` job on `windows-latest` running format, lint,
  strict types, dead-code, tests with coverage, craft checker self-tests, the application secret
  scan, and a wheel/sdist build, with the artifacts uploaded. Triggers on push and pull request to
  `main` plus manual dispatch, with `contents: read` only and in-progress runs cancelled per ref.

## Blockers and conflicts

None. `.github/` is a new path claimed by nobody.

Note for the reconciler: `uv build` now works, so `.launch/COMMANDS.md`'s "Package/wheel build |
Unverified" row is out of date. That file is claimed by the Slice 4 certification agent, so this
record is the notice rather than an edit.

## Stop point

`.github/workflows/ci.yml` written, YAML validated, and all nine gate steps rehearsed green from a
frozen isolated install. Nothing staged, nothing committed. The workflow has never executed on
GitHub because nothing has been pushed.

## Next safe action

Founder review, then commit `.github/workflows/ci.yml` and this record. Two follow-ups belong to the
founder and cannot be done from here:

1. Push, and confirm the first run is green. Every step was rehearsed locally on Windows ARM64
   against a frozen lockfile install, but no run has executed on a GitHub x64 runner.
2. Enable branch protection on `main` requiring the `gates` check. That is the remaining half of
   open Major #1 and is a repository setting, not a file.

A third, optional: pin `actions/checkout` and `actions/upload-artifact` to commit SHAs rather than
`@v4`. SHAs are the stronger supply-chain pin; they were not used because a SHA cannot be verified
from this environment and an invented one would break every run.
