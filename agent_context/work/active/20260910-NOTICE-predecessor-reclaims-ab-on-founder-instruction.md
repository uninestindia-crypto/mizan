# NOTICE: the A/B is being finished from an isolated snapshot, not by seizing live files

STATUS: NOTICE (additive; no other record is edited)
FILED_UTC: 2026-09-10T13:35:00Z
FILED_BY: Claude Code, `20260910-claude-corporate-action-adjustment-and-mizan-retrain.md`
ADDRESSED_TO: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (ACTIVE)
AUTHORIZATION: founder instruction, 2026-09-10 — "take it back and finish the A/B"

## What the founder authorized, and what is actually being done

The founder instructed this session to reclaim the work and finish the RAW-vs-adjusted A/B.
PROTOCOL §8.3 makes explicit founder instruction the sanctioned route to resolve ownership, so the
authority is not in question.

**The files are not being seized, and here is why.** The successor session is *live*:
`src/quant_system/data/corporate_actions.py` and `adjustment_provenance.py` were rewritten three
times inside one 45-second observation window (18:51:19, 18:51:44, 18:52:05 IST). Ownership does not
make concurrent writes to the same file safe — two agents editing the same bytes produce garbage
regardless of who holds the claim.

It also would destroy real value. Since the predecessor's last report the successor has **already
repaired the broken caller** this session was going to fix, and gone further: `AdjustmentPlan`,
`ValidatedFactor`, `code_revision()`, `authority_manifest_hash()` binding the authority snapshot into
the artifact identity, and `load_validated_demerger_factors()` sizing demergers from the resulting
company's own first traded price and the entitlement ratio in the company filing rather than from the
parent's ex-date gap. That is a better design than the predecessor's, and it corrects a real defect
in it (see §4 of
`20260910-NOTICE-predecessor-left-uncommitted-screen-edit-and-broken-caller.md`).

## What is being done instead

The A/B runs against a **pinned snapshot** of the successor's code, copied at a verified-stable
moment (no mtime change across ~50s), into
`<scratch>/ab/` outside the repository. Reads come from the shared caches; **no write of any kind
lands on a path the successor claims.** The feature-store rebuild writes to scratch, not to
`data/evidence/feature-store/mizan/`.

Consequences, stated plainly:

- The A/B result is reproducible against that snapshot, not against a moving tree. The snapshot
  hashes are recorded in the predecessor's work record.
- If the successor changes the adjustment semantics after the snapshot, the A/B measures the
  snapshot's semantics. It should be re-run rather than cited as current.
- Nothing here blocks, reverts, or races the successor's own work.

## Arm definitions

| Arm | Feature store | Labels |
|---|---|---|
| A (control) | RAW baseline, preserved from `5459cb05` before any rebuild | `--no-adjust`, RAW opens |
| B | rebuilt with corporate-action adjustment | adjusted next-open prices |

Arm A exists to reproduce the published **-0.000022 selection edge (t = -0.07)**. If it does not,
the harness is not measuring what it is believed to measure and arm B carries no information.
