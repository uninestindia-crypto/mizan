# QuantOS repository agent instructions

These instructions apply to every agent working in this repository, including Codex, Claude Code,
Cursor, and Antigravity.

## Required startup sequence

Before planning or editing:

1. Read `agent_context/README.md`, `agent_context/CURRENT.md`, `agent_context/PROTOCOL.md`, and
   `agent_context/DISK-LAYOUT.md`.
2. Read `.launch/STATE.md` and `.launch/SLICES.md` for the authoritative release state.
3. Run `git status --short --branch` and inspect every existing change as someone else's work.
4. Read every record in `agent_context/work/active/`.
5. Run `git worktree list` and `git branch --list`. Every registered worktree and non-default branch
   is a live agent until proven otherwise, even with no matching record.
6. Run `python scripts/release_status.py` so you know whether a release is already due (see the Release rule).
7. Create your own uniquely named active-work record before editing. Declare exact owned paths.
   If you will work in a worktree, create the record here in the install root **first**, and name
   the workspace path and branch in it.

## Concurrent work rules

- Prefer a separate Git worktree and branch for each simultaneous agent.
- A shared checkout is allowed only for demonstrably disjoint paths with written claims.
- Never edit a path claimed by another active record. Coordinate or stop.
- Never revert, delete, stage, commit, reformat, or "clean up" another agent's changes.
- Do not run repository-wide formatters or generated-code commands while another shared-checkout
  agent is active unless all affected paths are jointly owned.
- Treat untracked files as owned work, not disposable files.
- Keep one work record per task. Do not append to one global work log.

## Workspace ownership law

A claim is only real where every agent can see it. A record inside a worktree is invisible from the
install root, so it claims nothing.

- Write the active work record in the install root **before** creating a worktree or clone. Name the
  workspace path and branch in it. A copy inside the worktree is optional.
- Never run `git worktree remove`, `git worktree prune`, `git branch -d`, `git branch -D`, or delete
  a workspace directory you did not create. This holds when it looks idle, when it is clean, when no
  record claims it, and during reconciliation. An agent between edits looks exactly like one that
  has stopped.
- Never infer abandonment from a clean tree, an idle timestamp, or a missing record. Record the
  observation, attempt contact, leave it alone. An `UNKNOWN_OWNER` record is not grounds to remove,
  delete, or merge anything.
- Before merging another agent's branch, read its record's `Next safe action` and `Blockers and
  conflicts`. A precondition stated there is binding. If the merge would change any number another
  record pins as evidence — test counts, coverage, hashes — wait, or leave a uniquely named notice
  record saying what it invalidates. Never edit their record. The record, not the diff, carries the
  conditions.
- Run `scripts/audit-agent-claims.ps1` before any handoff or completion. It exits 1 when a workspace
  has no claim or a claim has no workspace.

The full contract is `agent_context/PROTOCOL.md` section 8, decided in
`agent_context/decisions/20260821-concurrent-workspace-ownership.md`.

## Disk layout law

QuantOS runs from the drive it is installed on, but never spread across the root of that drive.
Exactly two QuantOS entries may exist at the drive root: the install root `quant_system` and
`quant_system_workspaces`. Everything derived goes in a bucket under the second one.

- Develop only in the install root. Never move, rename, or duplicate it.
- Create verification clones, Red Team clones, mutation environments, and agent worktrees with
  `scripts/new-workspace-clone.ps1`. Never clone or `worktree add` to an ad-hoc path.
- Never relocate a registered Git worktree with a file move. Use `git worktree move`, and only when
  no agent is working in it.
- Record every workspace you create in your active work record, and retire it when the run is
  certified.
- Run `scripts/audit-disk-layout.ps1` before any handoff or completion. It exits 1 on violations.
  `scripts/organize-disk-layout.ps1` fixes them; it moves and never deletes.

The full contract is `agent_context/DISK-LAYOUT.md`.

## Release rule

The founder updates the installed software from GitHub releases, so work must reach a release regularly.
After every few major updates a new release is published; this is a rule, not a favour.

- Before ending any session that changed user-visible behaviour, run `python scripts/release_status.py`.
  It says whether a release is **DUE**: three or more user-visible commits (`feat`, `fix`, `perf`) since the
  last `v*` tag, any security fix, any breaking change, or the founder asking for one.
- If it is due, the agent whose commit crossed the threshold cuts the release before ending the session,
  unless the founder says hold: `powershell -ExecutionPolicy Bypass -File scripts/release.ps1`
  (`-DryRun` shows the plan and release notes without changing anything). It bumps the version in every file
  with `scripts/bump_version.py`, runs the gates, builds the installer from the release commit, tags, pushes
  and publishes the GitHub release. The installed app then shows an "update available" notice.
- Commit messages use conventional types (`feat:`, `fix:`, `perf:`, `chore:`, `docs:`, `test:`). The release
  notes are generated from them, so write the subject for a person, not for a developer.
- Never edit a version number by hand: `python scripts/bump_version.py --check` must pass (a test guards it).
- Patch release for fixes only, minor for new features, major only for breaking changes.

The full decision, with rejected alternatives, is `agent_context/decisions/20261004-release-cadence.md`.

## Required work record

Record the objective, scope, non-goals, starting revision, worktree/branch, owned paths, plan,
current step, concise decision rationale, commands and outcomes, files changed, stop point, and next
action. Record evidence and assumptions, not hidden chain-of-thought or private internal monologue.

At completion, move the record from `agent_context/work/active/` to
`agent_context/work/completed/` and create a handoff when work remains.

## QuantOS product laws

- `.launch/` is authoritative for release scope, gates, slice order, and verification evidence.
- Live-money order routing is excluded unless the user separately authorizes T4 work.
- Financial and model claims require point-in-time, cost-aware, reproducible evidence.
- Preserve Decimal accounting, next-bar execution, risk-governor enforcement, immutable evidence,
  and fail-closed behavior.
- Do not trade validation rigor for speed. Optimize implementation, not scientific safeguards.
- **Unified Enterprise Application Law**: QuantOS/Mizan must always be delivered as a single unified
  desktop application ("Microsoft App" style) with instant 1-click mode switching between Institutional
  Quantitative Trading and Mizan Shariah Wealth Engine. Never fragment the product into separate apps.
- **Factory-New Laptop Standard**: All desktop packaging and installers must be completely self-contained
  (bundling audited SQLite/DuckDB seed data, pre-compiled UI assets, and WebView2/App Mode runner) so
  that non-technical users can install and run the system out-of-the-box on a fresh laptop with zero
  pre-installed Python, Node, or Git, zero black terminal popups, and complete drive isolation.
- **Cloud Development Completeness Law (Claude Code & Container Readiness)**: Every asset required
  to build, run, test, and iterate on QuantOS/Mizan in a headless cloud container (e.g. Claude Code
  Web/Cloud, GitHub Codespaces, CI runners) must be fully tracked and pushed to GitHub:
  - Code, schema migrations, local model architectures, prompts, and catalog definitions.
  - Curated seed databases (`data/shariah/*.db`, `*.duckdb`), test fixtures, and verified authorities.
  - Production frontend build assets or reproducible build toolchains.
  - Zero reliance on untracked local paths or developer machine absolute paths (e.g. `D:\quant_system_workspaces\...`).
  - **Zero-Dependency Fallback**: The codebase must run 100% functionally in `SYNTHETIC_MODE` without
    requiring live external broker or LLM API credentials, allowing full verification in isolated cloud environments.

## Context safety and secret leak prevention

- **Zero Secrets in Repository Law**: The GitHub repository is strictly private and must remain 100% free
  of any credentials, secrets, or confidential keys:
  - Never commit, stage, or push credentials, API keys (Upstox, OpenAI, Anthropic, Gemini, Groq, Lightning AI,
    OpenRouter, AWS Bedrock), tokens (OAuth, JWT, Bearer), passwords, private certificates (`.pem`, `.key`,
    `.p12`, `.pfx`), or private machine/hardware identifiers.
  - All sensitive keys must reside exclusively in process environment variables (`os.environ`) or machine-local,
    strictly gitignored `.env` files.
- **Git Staging Hygiene**:
  - Never run blanket `git add -A` or `git add .` at repository root. Always stage explicitly claimed paths (`git add <path>`).
  - Never bypass `.gitignore` (`git add -f` is strictly prohibited for any `.env*` or credential file).
  - `.env.example` is the sole tracked environment template and must contain only empty placeholder values.
- **Sanitized Artifacts and Context**:
  - Never store credentials, tokens, `.env` values, provider payloads containing secrets, private
    device IDs, product IDs, or unnecessary personal data in repository context.
  - Store sanitized conversation summaries, not raw private chats.
  - Cite code, tests, commands, commits, and evidence for claims that another agent must trust.
- **Pre-Commit Secret Verification**: Run secret scanning (`detect-secrets`) before any commit to ensure zero
  candidate credential leakage.

