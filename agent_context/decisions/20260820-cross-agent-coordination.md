# Decision: file-based cross-agent coordination

STATUS: Accepted  
DATE: 2026-08-20  
OWNER: User and Codex

## Context

QuantOS may be edited simultaneously through Codex, Claude Code, Cursor, and Antigravity. These
tools do not share one reliable private memory, and multiple agents may see the same working tree.
A single shared work log would create edit conflicts and would not prevent overlapping changes.

## Decision

- Keep durable, tool-neutral context in `agent_context/`.
- Use one uniquely named active work record per task as the visible path claim and progress log.
- Prefer separate Git worktrees/branches for simultaneous agents; allow shared-checkout work only
  for exact disjoint paths.
- Keep `.launch/` authoritative for formal release state and link to it rather than duplicating it.
- Add small automatic entry points for Codex (`AGENTS.md`), Claude Code (`CLAUDE.md`), Cursor
  (`.cursor/rules/*.mdc`), and Antigravity (`.agents/rules/*.md`).
- Record concise evidence-based rationale, not hidden chain-of-thought.
- Store sanitized conversation summaries and exclude secrets, private IDs, and unnecessary PII.

## Rejected alternatives

- One global append-only log: rejected because concurrent agents would edit the same file.
- Raw chat transcript archive: rejected because it duplicates noise and can persist secrets or PII.
- Replace `.launch/` with the new folder: rejected because `.launch/` already contains verified
  release evidence and accepted slice planning.
- Shared checkout without ownership claims: rejected because existing untracked Slice 3 work proves
  the collision risk is real.

## Consequences

Agents must spend a small amount of time claiming and handing off work. In return, ownership,
evidence, stop points, and unresolved conflicts remain visible across tools and sessions.

