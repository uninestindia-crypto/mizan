# Handoff: independent governed feature-window recheck

STATUS: INDEPENDENT_RECHECK_RECORDED
TARGET_REVISION: `88a7ac988114267a0d44203587a57b680717bf3b`
IMPLEMENTATION_AGENT: Codex feature-window repair
INDEPENDENT_AGENT: Dalton (`01a03369-5c3d-7092-831c-11ed70684935`)
REPORT_REVISION: `69d8cd0f423edb6ffd75d86b30b361aa1ec37f30`
REPORT_PATH: `.launch/reports/RED-TEAM-GOVERNED-FEATURE-WINDOW-RECHECK-FINAL-2.md`

## What changed

- Governed feature schema v2 consumes exactly the trailing 21 available bars inside the shared
  feature kernel.
- Feature-row provenance hashes only the consumed bars.
- Feature dataset, trial, model publication, persisted reconstruction, and execution bundle carry
  or verify the schema identity.
- Schema-v1 and schema-less model evidence remains auditable but cannot execute as v2.
- The existing real evidence store contains 40 published pre-v2 models; the real runner refuses the
  selected GRASIM artifact with typed missing-schema detail and exit code 3. No session ran.
- The first independent retry found that the exported evaluator itself omitted the schema match.
  Revision `8f29564` adds that comparison before fitting; the finding's exact reproduction is now a
  failing-first regression.
- The next independent retry found that the exported kernel accepted reverse chronology. Revision
  `88a7ac9` validates strict chronological uniqueness before selecting the canonical tail.

## Independent outcome

- Both prior reproductions now fail closed with the required typed errors.
- All 28 follow-up items produced their expected outcomes; the bounded ledger is 30/30.
- The independent focused run reported 114 tests; full and reversed-order runs each reported 869.
- Ruff and mypy reported no issue; claim and disk-layout audits returned exit code 0.
- The real evidence runner returned exit code 3 against 40 verified pre-v2 models. No session or
  order was created.
- No correctness defect was reproduced in this bounded recheck. This is not a whole-product,
  deployment, promotion, or live-money verdict.

## Residual boundaries

- A 10,000-row governed acquisition was not run because the daily request contract rejects ranges
  longer than ten years; the 10,000-bar kernel and strategy paths were exercised.
- No genuinely promoted current-v2 real model exists in the tested evidence directory.
- Other operating systems, Python/NumPy/BLAS stacks, cross-process concurrency, broader fuzzing,
  fault injection, live feeds, brokers, orders, fills, fees, and UI surfaces were not exercised.

## Boundaries

- Do not edit product source or existing tests during the independent phase.
- Do not treat the 40 legacy real-data models as evidence for feature schema v2.
- Do not promote a `RESEARCH_ONLY` model or substitute generated data.
- Read `.launch/reports/quarantine/README.md`; do not reuse its withdrawn assertions.

## Next safe action

Train a fresh candidate from real point-in-time market data under feature schema v2. Preserve the
existing 40 pre-v2 artifacts as historical evidence; do not relabel or promote them. Independently
review the new trial, publication, and promotion evidence before governed execution can load it.
