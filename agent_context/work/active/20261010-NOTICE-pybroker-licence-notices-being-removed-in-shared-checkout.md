# NOTICE: PyBroker's licence notices are being removed by uncommitted edits in the shared checkout

STATUS: NOTICE (an observation; nothing was changed, staged, reverted or committed by this record's author)  
FILED_BY: Claude Code (Sonnet 5.5), the session recorded in `20261009-1340Z-claude-sonnet-open-source-integration-worktree.md`  
FILED_UTC: 2026-10-10  
OWNER_OF_THE_EDITS: unknown (no active record names these paths)  
FILED UNDER: PROTOCOL sections 7 and 8.2 (unknown owner: record, attempt contact, leave alone)

## What was seen

During this session on 2026-10-10, in the install root on `main` (tracked files, not committed):

- 19 files under `src/pybroker/` (`__init__.py`, `cache.py`, `common.py`, `config.py`, `context.py`, `data.py`, `eval.py`, `ext/data.py`,
  `indicator.py`, `interval.py`, `log.py`, `model.py`, `optimize.py`, `parallel.py`, `portfolio.py`, `scope.py`, `slippage.py`,
  `strategy.py`, `vect.py`) each lose the five-line header "Copyright (C) 2023 Edward West. All rights reserved. This code is licensed
  under Apache 2.0 with Commons Clause license (see LICENSE for details)." (95 lines in all).
- `Learn from open source codebase/pybroker-master/LICENSE` is **deleted and staged**, and some of that folder's README, CLAUDE.md and
  documentation files are edited (about 87 changes under that folder).
- A little earlier in the same session the same tree was clean apart from one untracked record, so this is new work, not a leftover.

## Why it matters

PyBroker is licensed Apache 2.0 with the Commons Clause. Apache 2.0 requires the copyright and licence notices to be kept in copies and in
derived works, and the Commons Clause text says its own condition must travel with any such notice. `src/pybroker/` is a vendored copy that
ships in the product (see `THIRD_PARTY_NOTICES.md`, which already records the open question of whether a paid release can include it).
Removing the notices does not change what the licence allows; it only removes the evidence of it.

## What the author of this record did

Nothing to those files. They do not overlap the files this session changed, so landing that work on `main` was not affected by them.

## Needed from whoever owns the edits, or the founder

- Say who is making them and why, in a record under `agent_context/work/active/`.
- Until the founder decides: do not commit them, and do not cut a release from this tree. `scripts/release.ps1` already refuses to run while
  tracked files are modified, and that refusal should stand.
