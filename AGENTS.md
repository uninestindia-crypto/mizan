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
5. Create your own uniquely named active-work record before editing. Declare exact owned paths.

## Concurrent work rules

- Prefer a separate Git worktree and branch for each simultaneous agent.
- A shared checkout is allowed only for demonstrably disjoint paths with written claims.
- Never edit a path claimed by another active record. Coordinate or stop.
- Never revert, delete, stage, commit, reformat, or "clean up" another agent's changes.
- Do not run repository-wide formatters or generated-code commands while another shared-checkout
  agent is active unless all affected paths are jointly owned.
- Treat untracked files as owned work, not disposable files.
- Keep one work record per task. Do not append to one global work log.

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

## Context safety

- Never store credentials, tokens, `.env` values, provider payloads containing secrets, private
  device IDs, product IDs, or unnecessary personal data in repository context.
- Store sanitized conversation summaries, not raw private chats.
- Cite code, tests, commands, commits, and evidence for claims that another agent must trust.

