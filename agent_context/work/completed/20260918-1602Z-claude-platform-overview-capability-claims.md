# Completed work: `PLATFORM_OVERVIEW.md` advertised capabilities the README denies

STATUS: COMPLETED (documentation only; no code touched)  
OWNER: Claude Code (Opus 5)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-18T16:02:03Z  
STARTING_REVISION: `6457102f`  
WORKTREE_OR_BRANCH: `D:\quant_system`, branch `claude/capability-claims-platform-overview`
(shared checkout). Branch is mine; per PROTOCOL §8.3 nobody else should remove it.

## Authorization

Founder instruction, 2026-09-18: "ok then complete it asap", after I listed program Major #4 as
still open despite `.launch/STATE.md` recording it **CLOSED**.

## The defect

Major #4 was closed at `5a0447b` for `README.md` and `docs/ARCHITECTURE.md`. The audit record
`20260824-claude-capability-claims-audit.md` names exactly those two paths in its `## Owned paths`.
**`docs/PLATFORM_OVERVIEW.md` was never in scope and still carried the claims**, so the repository
contradicted itself:

| `README.md` says | `PLATFORM_OVERVIEW.md` said |
|---|---|
| "**Support US equities.** The instrument contract accepts NSE cash equities only." | "specialized out-of-the-box support for **NSE India** and **US Equities**" |
| "**Score fundamentals.** There is no balance-sheet, earnings, or valuation factor model." | "### 2. Fundamental Factor Alpha ("Quantamental")" — P/E, P/B, EV/EBITDA, ROE, Piotroski F-Score, PEAD, analyst revisions |

Verified against the code rather than against the README, so the correction rests on measurement:

```
US equity support (NYSE|NASDAQ|US_EQ) in src/ : absent
piotroski / pead / analyst / revenue surprise / P/E / price_to_book in src/ : all absent
quant_system.alpha.fundamental : does not exist
news / polarity / social-sentiment module : absent (only `sentiment` inside alpha/ai_advisor.py)
```

## Owned paths

- `docs/PLATFORM_OVERVIEW.md` — **owned by no active record.** Three records name `docs/` paths;
  none names this file: `20260824-claude-capability-claims-audit.md` owns `README.md` and
  `docs/ARCHITECTURE.md`, `20260824-codex-real-journey-api-wiring.md` owns `src/quant_system/server/**`,
  and `20260910-claude-bedrock-dual-model-audit.md` owns `docs/bedrock-dual-model-setup.md`.
- `agent_context/work/completed/20260918-1602Z-claude-platform-overview-capability-claims.md` (this file)

## Non-goals

- **No code change of any kind.** This is a documentation correction.
- **No edit to `.launch/STATE.md`**, which records Major #4 as CLOSED and is now wrong in part.
  That file is single-owner under PROTOCOL §4 and claimed by
  `20260821-0530Z-claude-slice4-certification.md`. Whether the major reopens is the coordinator's
  call, not mine. Flagged under "Next safe action".
- **No edit to `docs/DATA_AND_ALPHA_ROADMAP.md`.** It describes the same unbuilt fundamental
  factors, but it is explicitly framed as a roadmap in its opening line ("This roadmap outlines how
  QuantOS expands beyond technical price signals"), so it is not making a false present-tense claim.
- No deletion of the aspirational sections. The document is a design document and its intent has
  value; the defect was that intent was written as fact.

## Decision rationale

**Why mark rather than delete.** Deleting the Fundamental and NLP sections would lose the designed
architecture and break the "Triad of Quantitative Alpha" framing and its mermaid diagram. The defect
is not that the design is described — it is that a reader cannot tell design from shipped. A banner
plus inline `NOT IMPLEMENTED` markers fixes exactly that, and follows the house style set at
`5a0447b`, where `README.md` gained an explicit "**It does not:**" list rather than quietly losing
paragraphs.

**Why the banner names the contradiction.** A future reader who finds this document flattering
should be able to see, in the document itself, that it once overstated and where the authority lives.

## Files changed

- `docs/PLATFORM_OVERVIEW.md`: 28 insertions, 5 deletions.
  - Opening claim corrected: NSE cash equities and NIFTY derivatives; "global and regional
    exchanges" and "US Equities" removed.
  - A scope banner added under the opening, naming `README.md` as the authority and restating its
    four boundaries verbatim.
  - Invariant 4 ("Multi-Source Alpha") split into what is built and what is not.
  - "Fundamental Factor Alpha" marked **NOT IMPLEMENTED** with the search evidence.
  - "NLP News & Sentiment Analysis" marked **NOT IMPLEMENTED**.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Ownership scan over all active records | **UNCLAIMED** | No record names `docs/PLATFORM_OVERVIEW.md` in `## Owned paths` |
| Capability search over `src/` | **CONFIRMED ABSENT** | US equity keys, all named fundamental factors, and any news/sentiment module |
| `ruff format --check docs/` | **PASS** | 9 files |
| `git diff --stat` | 28 insertions, 5 deletions | Documentation only |

No test run and no static gate beyond formatting: nothing executable changed.

## Blockers and conflicts

None. The file is unclaimed and no code is touched.

## Next safe action

**`.launch/STATE.md` records Major #4 as CLOSED and that is now only partly true** — it was closed
for `README.md` and `docs/ARCHITECTURE.md` and never covered this file. The file is claimed by
`20260821-0530Z-claude-slice4-certification.md` and single-owner under PROTOCOL §4, so its owner or
the founder decides whether the major reopens, stays closed with this noted, or is re-scoped. This
record is the evidence for that decision.

A further sweep is also worth someone's time: `docs/ARCHITECTURE.md` still shows a "Fundamental
Factors" box in its diagram, which the `5a0447b` audit's own record describes as "diagram only" and
in scope — so it may already be intended, or may be a second miss. Not checked here, and not mine.
