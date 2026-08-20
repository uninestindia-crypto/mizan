# Cross-agent coordination protocol

This protocol is designed for Codex, Claude Code, Cursor, Antigravity, or human developers working
simultaneously without a shared agent-memory service.

## 1. Isolation policy

Use a separate Git worktree and branch per agent whenever tasks may touch related modules, shared
contracts, dependency files, tests, formatting, or generated artifacts.

A shared checkout is permitted only when all of these are true:

- owned paths are exact and disjoint;
- neither task runs a repository-wide formatter, generator, migration, or staging command;
- neither task changes a shared contract consumed by the other;
- both tasks have active work records visible before editing.

If these conditions stop being true, stop and coordinate. Do not attempt an opportunistic merge in
the shared checkout.

## 2. Start a task

1. Read `CURRENT.md`, `.launch/STATE.md`, `.launch/SLICES.md`, and all `work/active/*.md` files.
2. Run:

   ```powershell
   git status --short --branch
   git rev-parse HEAD
   ```

3. Treat every existing tracked or untracked change as owned by someone else until proven otherwise.
4. Copy `templates/work-item.md` to a unique path such as:

   ```text
   work/active/20260820-1125Z-claude-slice3-labels.md
   ```

5. Fill every required field, especially `OWNED_PATHS`, `NON_GOALS`, and `STARTING_REVISION`.
6. Re-read active records. If any claim overlaps, coordinate or choose different work.

Creating a record is a declaration, not a lock. Separate worktrees are the lock for overlapping
Git work.

## 3. While working

Only edit claimed paths. Update your own record after each material checkpoint with:

- current plan step and status;
- concise rationale and assumptions;
- exact commands and meaningful outcomes;
- new files or contracts introduced;
- discovered conflicts or blockers;
- any change to owned paths.

Do not rewrite another agent's record. Send coordination through the tool's messaging feature when
available, then summarize the agreement in both affected records.

Never store hidden chain-of-thought. Record a reviewable rationale: evidence considered, decision,
assumptions, trade-offs, and rejected alternatives.

## 4. Shared files and high-conflict operations

These require explicit single-owner coordination:

- `pyproject.toml`, `uv.lock`, `.gitignore`, root guidance files, and shared schemas;
- `.launch/STATE.md`, `.launch/SLICES.md`, and accepted ADRs;
- repository-wide format, lint-fix, dependency sync/update, code generation, and Git staging;
- moving, deleting, or renaming paths;
- changes to public API, evidence schemas, financial contracts, or model lifecycle states.

Do not use `git add -A` or broad commits in a shared checkout. Stage explicit owned paths only.

## 5. Stop, hand off, or complete

Before stopping, update the work record with:

- status: `COMPLETED`, `HANDOFF_REQUIRED`, or `BLOCKED`;
- exact files changed;
- verification commands and raw result summaries;
- known failures and unverified claims;
- exact stop point;
- next safe action;
- whether the working tree is clean and whether anything is committed.

For unfinished work, create a uniquely named file from `templates/handoff.md`. Link it from the
active work record. Leave the active record in place until another agent explicitly adopts it.

For completed work, move the record to `work/completed/`. The reconciler then updates `CURRENT.md`
after the work is merged or accepted.

## 6. Reconciliation

One coordinator/release agent reconciles completed records into `CURRENT.md`. Reconciliation must:

1. inspect Git state and commits;
2. verify claimed commands when risk warrants;
3. resolve conflicts against the source-of-truth order in `README.md`;
4. update formal `.launch/` state only when its gate requirements are actually satisfied;
5. never mark another task complete merely because its agent stopped.

## 7. Failure behavior

- Unknown owner on existing changes: create an `UNKNOWN_OWNER` active record and do not edit them.
- Stale active record: attempt contact; otherwise create a handoff audit. Do not silently take over.
- Overlapping claims: both agents stop affected edits until ownership is resolved.
- Conflicting conclusions: preserve both records and commission evidence-based verification.
- Sensitive data found in context: remove it before commit and rotate any exposed credential.

