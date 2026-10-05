# QuantOS agent context

This folder is the durable, tool-neutral coordination layer for humans and coding agents working on
QuantOS. It records what is true, what is being changed, why decisions were made, what was verified,
and exactly where unfinished work stopped.

It supplements rather than replaces `.launch/`. Release scope, gates, slice order, ADRs, and formal
verification evidence remain authoritative in `.launch/`.

## Five-minute onboarding

Every new agent must:

1. Read [GOAL.md](GOAL.md) for the final result we are building and the tripwires that say you have
   missed it. Then read [CURRENT.md](CURRENT.md) for the current snapshot and collision warnings.
2. Read [PROJECT.md](PROJECT.md) for product boundaries and invariants.
3. Read [PROTOCOL.md](PROTOCOL.md) before editing.
4. Read `.launch/STATE.md` and `.launch/SLICES.md` for formal release state.
5. Run `git status --short --branch`.
6. Inspect [work/active](work/active) and claim exact paths in a new unique file.

## Directory map

| Location | Purpose | Update rule |
|---|---|---|
| `GOAL.md` | The final result, goal lines G1-G7 and goalpost tripwires | Founder's instruction only; agents append dated proposals under its section 7 |
| `CURRENT.md` | Reconciled repository snapshot | Coordinator updates after merges or handoffs |
| `PROJECT.md` | Stable product intent, boundaries, and source hierarchy | Update when the product contract changes |
| `PROTOCOL.md` | Cross-tool concurrent-work procedure | Change through a decision record |
| `SECURITY.md` | What context may and may not be stored | Always enforce |
| `work/active/` | Live path claims and progress | One unique file per task/agent |
| `work/completed/` | Immutable task summaries and evidence | Move completed active records here |
| `handoffs/` | Exact stop points and continuation instructions | One unique file per handoff |
| `decisions/` | Concise rationale and rejected alternatives | One file per durable decision |
| `conversations/` | Sanitized discussion and intent summaries | Never store secrets or private IDs |
| `templates/` | Required record shapes | Copy, then rename uniquely |

## Source-of-truth order

When records disagree, use this order:

1. Current code, tests, Git state, and reproducible command output.
2. `.launch/STATE.md`, `.launch/SLICES.md`, ADRs, and verifier evidence.
3. Reconciled `agent_context/CURRENT.md` and completed work records.
4. Handoffs and active work records.
5. Conversation summaries and older general documentation.

Do not silently choose between conflicting sources. Record the conflict and resolve it with
evidence.

