# The goal: what we are building and what "done" means

STATUS: COMPILED FROM RECORDED SOURCES, awaiting the founder's confirmation of section 7  
COMPILED_UTC: 2026-10-05  
COMPILED_BY: Claude Code, on the founder's instruction: "I wanted a file in the codebase so every AI
agent or staff knows what the goal, aim and final result is, so we do not miss the goal post."  
FOUNDER'S WORDING OVERRIDES THIS FILE. Where a line below cites a source, the source is the authority;
where this file and a source disagree, fix this file and say so in your record.

Every agent and every person reads this file before planning work, after `AGENTS.md` and before
`CURRENT.md`. It is short on purpose. It says where we are going. `CURRENT.md` says where we are,
`.launch/` says what is certified, and the work records say who is changing what.

## 1. The one sentence

**One desktop application that tells a retail investor the truth about an idea before they risk real
money, in two modes (institutional quant trading and the Mizan Shariah wealth engine), switchable in one
click, that installs on a factory-new laptop and never claims an edge the evidence does not show.**

Sources: `README.md` lines 1-5 (the two modes); `AGENTS.md`, "Unified Enterprise Application Law" and
"Factory-New Laptop Standard"; `docs/product/PRD-quantos-2.md` section 1 ("Know before you risk real
money, and keep more of what you make"; "QuantOS never implies an edge that the evidence does not show.
That is the product's differentiator"); `.launch/CHARTER.md` ("The one sentence").

## 2. The final result, as goal lines

Each line is a destination, with the test that says it has been reached. A piece of work should move at
least one of them. Name the line in your record's Objective as `GOAL_LINE: G<n>`.

| Line | Final result | Done when | Source |
|---|---|---|---|
| **G1** | **A trustworthy engine.** Research, backtest, risk, paper and shadow, where every number can be believed. | Decimal ledger reconciles. Next-bar execution only. Every order passes the risk governor. Failures are typed and fail closed. All results are point-in-time, cost-aware and reproducible. Independent adjudication, not the author's own word, covers every release-critical path. | `agent_context/PROJECT.md` invariants; `.launch/CHARTER.md` "No problems for users means" |
| **G2** | **One unified application, two modes.** Institutional Quantitative Trading and Mizan Shariah Wealth Engine, one click apart, never two apps. | A user switches mode in one click inside one installed app. The Shariah screener (AAOIFI and TASIS), halal baskets, purification ledger and zakat calculator work from the same install as the quant lab. | `AGENTS.md` "Unified Enterprise Application Law"; `README.md` "Operating Modes" |
| **G3** | **Factory-new laptop.** A non-technical person installs it and it runs. | Fresh Windows laptop, no Python, Node or Git, no terminal windows, no outside drive touched, audited seed data and pre-built UI bundled. | `AGENTS.md` "Factory-New Laptop Standard" |
| **G4** | **Buildable and verifiable in the cloud.** Any agent or CI runner can build, run and test it headless. | Everything needed is tracked in Git, with no dependency on a developer's machine path. It runs fully in `SYNTHETIC_MODE` with no broker or LLM credentials. No secret is ever in the repository. | `AGENTS.md` "Cloud Development Completeness Law", "Zero Secrets in Repository Law" |
| **G5** | **Honest evidence about any model.** A model is shown to a user as tradeable only when it has earned that. | A candidate passes the pre-declared gate (deflated Sharpe 0.95 or more, max drawdown 0.15 or less, 5 or more trades), beats its noise and always-trade controls, is re-run by an agent that did not write it, and then survives a forward paper period. Until then it is labelled research only. | `agent_context/CURRENT.md` "Standing constraints"; `reports/kronos_trial/TRIAL-LEDGER.md` "Verdict"; `.launch/RISKS.md` |
| **G6** | **Real benefit to retail users.** Costs they never saw, position sizes, untested rules and tips are what the product helps with. | The QuantOS 2.0 acceptance criteria (`docs/product/PRD-quantos-2.md` sections 4-5) pass for the R1 persona journeys. | `docs/product/PRD-quantos-2.md` |
| **G7** | **Releases reach the founder.** The installed app updates from GitHub releases. | `python scripts/release_status.py` shows no release DUE at the end of a session. | `AGENTS.md` "Release rule" |

## 3. What the goal is not

These look like progress and are not. Each has already been tried or decided against.

- **Not a profitable model, at least not yet.** Nothing in this repository has shown an edge that
  survives real costs: 101 governed trials, nine short-horizon trials and seven screens
  (`CURRENT.md`; `scripts/run_short_horizon_experiment.py` `DECLARED_TRIALS`). The goal is a product that says so, and that can recognise an edge if one is ever
  found. It is not a product that finds one by searching until something looks good.
- **Not live-money order routing.** That is T4, chartered separately, and the founder has not
  authorised it (`AGENTS.md` product laws; `.launch/CHARTER.md` kill criteria). Nothing has ever
  placed an order.
- **Not two products.** No separate Mizan app, no second installer, no mode that needs a second
  download (`AGENTS.md` "Unified Enterprise Application Law").
- **Not a paper-book P&L.** Paper books are a system test. Their profit or loss is market plus costs and
  is never cited as model performance (`agent_context/decisions/20260923-paper-books-system-test-end-date.md`).
- **Not guaranteed returns, investment advice or regulatory approval** (`.launch/CHARTER.md`
  non-goals).

## 4. Goalpost tripwires

Stop and write it into your record, then ask the founder, if your work would do any of these.

1. Serve no goal line (G1-G7), or serve one by weakening another.
2. Weaken a scientific safeguard to go faster: multiplicity counting, point-in-time rules, cost
   modelling, the pre-declared trial ledger, or the independent-adjudication requirement.
3. Run another model trial, sweep or retrain without its own dated declaration. Every extra trial
   raises the bar for every later one.
4. Describe a result as an edge, or a paper P&L as skill, in any user-facing text, report or commit message.
5. Split the application, or add a prerequisite a factory-new laptop does not have.
6. Put a credential, token, key or machine identifier in the repository.
7. Reach for live money, a broker order, or an account write.
8. Change what a running paper book trades while its system test stands.

## 5. How to use this file

- Read it with `AGENTS.md` at startup. Name your goal line in your record's Objective.
- If your work finishes and no goal line moved, say so in the record. That is a finding, not a failure.
- Do not edit a goal line, "Done when" test or tripwire without the founder's instruction. To propose a
  change, add it under section 7 in a dated line and tell the founder.
- This file states direction. It never records measurements, counts or status. Those age badly and belong
  in `CURRENT.md` and `.launch/STATE.md`, which this file points to and does not copy.

## 6. Where to look next

| Question | File |
|---|---|
| What is true right now? | `agent_context/CURRENT.md`, `.launch/STATE.md`, `.launch/SLICES.md` |
| What is certified, and by whom? | `.launch/reports/`, `.launch/SLICE-*-EVIDENCE.md` |
| What is the release scope and what is out of it? | `.launch/CHARTER.md`, `.launch/PRD.md` |
| What is the retail product contract? | `docs/product/PRD-quantos-2.md` |
| Who is editing what? | `agent_context/work/active/` |
| What was decided, and what was rejected? | `agent_context/decisions/` |

## 7. Open points for the founder

Recorded here because the sources above do not settle them, and an agent should not settle them by
guessing. Add the answer as a dated line under each, then remove the point from the unconfirmed list.

1. **Cloud.** `.launch/CHARTER.md` (2026-08-20) lists "Cloud deployment, multi-user accounts, or tenancy"
   as a non-goal. On 2026-10-05 the founder chose to run the paper books and one research trial in the
   cloud. This file reads that as *a cloud host for single-user paper sessions and research*, not a
   hosted multi-user product. Confirm, or say what the cloud is for.
2. **What "wealth engine" success means in numbers.** The sources define the Shariah mode's features
   (screener, baskets, purification, zakat) but no target such as users, assets or returns. G2's "done
   when" tests the features, not an outcome.
3. **One product, two documents.** `docs/product/PRD-quantos-2.md` (retail redesign, branch
   `claude/retail-redesign`) and the unified Quant plus Mizan application in `AGENTS.md` are read here as
   the same product. Confirm.
4. **The word "profit".** The retail PRD cites the founder's brief that the primary function is "profit
   for retail traders and retail investors". The evidence so far supports "avoid avoidable losses and
   know what you are doing", and does not support a promise of profit. G5 and G6 are worded to the
   evidence. Confirm the wording you want.
