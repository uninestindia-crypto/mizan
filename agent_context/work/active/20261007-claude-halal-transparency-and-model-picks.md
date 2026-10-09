# Work record: halal transparency (Stage 0) and second opinions on the platform's own picks

STATUS: ACTIVE  
OWNER: Claude Code (cloud session)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07T04:39Z  
STARTING_REVISION: 212c26bc3d4b4e8c135b0dee856a93b84f247653 (the Copilot branch as opened in PR 9; follow-up work, not part of PR 9)  
WORKTREE_OR_BRANCH: `/home/user/mizan` (cloud clone). Local-only branch `wip/halal-transparency` until PR 9 merges, then moved onto the designated branch `claude/wonderful-wozniak-6ek6zl` restarted from `main`. No other worktree.

GOAL_LINE: G2 (Mizan mode stays honest and usable), G6 (retail benefit), tripwire 4 (no unproven result presented as an edge).

## Objective

The founder asked (2026-10-07) to merge and release the Copilot work and "continue with the remaining work of the idea". The
remaining parts of the idea are: (1) when the platform's own rules select a stock, offer an independent second opinion on
it; (2) make halal investing transparent and honest, doing Stage 0 of `reports/halal_docs_review/REVIEW.md` (remove assumed
performance numbers and invented history, label data status on every verdict, show how a verdict was reached, fix the
purification hash, correct misleading wording and docs). Stages 1 to 4 (real filing data, daily recompute, intraday,
governance) need founder decisions and are out of scope.

## Owned paths

- `src/quant_system/shariah/**` (schemas, services, api, db migration helpers), `tests/test_shariah_*.py` (new and existing)
- `docs/HALAL_METHODOLOGY.md` (new) and the halal wording in `README.md` and the white paper (path found by search)
- `frontend/src/pages/Shariah.tsx`, `frontend/src/pages/PaperBook.tsx`, `frontend/src/lib/picks.ts`, `frontend/src/components/copilot/PickSecondOpinion.tsx`, and the Shariah types in `frontend/src/lib/types.ts` (Shariah types only)
- `agent_context/decisions/20261007-halal-transparency-contract.md`

## Non-goals

Real filing data, scholar review, new standards, any order placement, any change to a verdict's arithmetic (thresholds stay
as the code has them; the review's open question on the AAOIFI text is a founder decision), the Flutter client.

## Plan

1. Shared pieces: pick note wording and a compact second-opinion button. DONE
2. Backend honesty and transparency, test-first. 
3. Shariah screen: remove assumed numbers, data status on verdicts, "How this verdict was reached" panel, order-sheet wording, second opinion on basket stocks. 
4. Paper book: second opinion on held and queued stocks. DONE (`97dd569a1`: `PaperPositions.tsx`, `OrderTicket.tsx`, 6 tests)
5. Docs. 
6. Gates, a browser check, push after PR 9 is merged, PR. Note: PR 9 merged 2026-10-07 (`960de0ac3`) on the founder's
   instruction; the v2.5.0 release commit is PR 10, cut from a scratch clone so the Shariah workers' checkout was not
   disturbed. This work ships in the next release.

## Blockers and conflicts

No other active record claims these paths. `20261005-NOTICE-live-paper-readiness-edits-under-other-claims.md` mentions the
Shariah audit lines (`UNVERIFIED_SAMPLE`); this work keeps that meaning.

## Stop point

Steps 1 and 4 committed on local branch `wip/halal-transparency`. Steps 2 and 3 are with two workers in this checkout
(backend `aa33983ac23e4b8aa`, Shariah screen `aadb19e5dbd719b1a`); nothing of theirs is staged or committed until the
coordinator has re-run the gates on it.

## Next safe action

Backend and screens in parallel under the contract in `agent_context/decisions/20261007-halal-transparency-contract.md`.
