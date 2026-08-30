# Decision: a declared exemption lets a RESEARCH_ONLY model run on a paper-only surface

DATE_UTC: 2026-08-30
DECIDED_BY: founder, on a recommendation from Claude Code
STATUS: ACCEPTED
SUPERSEDES: nothing
RELATED: `.launch/reports/RED-TEAM-20260829-LIVE-PAPER-PATH.md` finding P1-1;
`agent_context/decisions/20260824-canonical-feature-window.md`

## The problem

`execution/governed_strategy.py` states of `SURFACE_ALLOWED_VERDICTS` that `REJECT` and
`RESEARCH_ONLY` "appear nowhere, so they cannot execute anywhere". A Red Team pass established that
the paper pilot executes a `RESEARCH_ONLY` model every weekday. Both statements cannot stand.

The gate was never bypassed by force. It was bypassed by **not being reached**:
`scripts/run_paper_pilot_session.py` calls `MizanModel.default_model()` and hand-rolls scoring, so
`CrossSectionalModelStrategy` -- where the check lives -- has zero production callers.

## Options considered

**(a) Honour the gate as written.** Route the session through the strategy class and let it refuse.
The docstrings become true immediately and no new concept enters the codebase.

Rejected. It makes the stated purpose of this work impossible. The reason for paper-trading Mizan is
to observe how an *unpromotable* model behaves against live prices; a gate that forbids exactly that
forbids the measurement. It also has a failure mode worse than the defect: the pressure would move
to promoting a model that does not deserve it, and 101 governed trials say none does.

**(b) Declare a narrow exemption.** A distinct surface that admits `RESEARCH_ONLY` and nothing else,
reachable only by passing an acknowledgement that names this record. **Accepted.**

**(c) Add `RESEARCH_ONLY` to `SURFACE_ALLOWED_VERDICTS[PAPER_PILOT]`.** Rejected: it weakens a
ceiling that three adjudicated repairs depend on, and it makes the exemption invisible -- a reader
of the map could not tell an intended carve-out from an eroded guard.

## The decision

A new `ExecutionSurface.RESEARCH_PAPER` exists. Its properties are the whole of the exemption:

1. **It admits `RESEARCH_ONLY` and nothing else.** Not `PAPER`, not `SHADOW`. A promotable model
   must not run here either, because its results would be filed as research observation rather than
   as a pilot. Each surface admits exactly what it is for.
2. **`REJECT` remains admissible on no surface.** Unchanged, and it is the line this decision does
   not cross. A rejected model failed a gate it was measured against; a `RESEARCH_ONLY` model was
   never eligible for one.
3. **It cannot be reached by default.** Constructing a strategy on it requires a
   `ResearchPaperExemptionV1` naming this file. Passing that object on any other surface is refused,
   so it cannot drift into general use.
4. **The other three ceilings are untouched.**

## What this does not authorise

- No live-money routing. Excluded by the release laws and unchanged here.
- No promotion. No verdict, gate threshold or DSR requirement moves. `min_deflated_sharpe` remains
  `0.95` and nothing meets it.
- No claim that the model works. The best campaign DSR is `0.397794`; the point of running it is to
  observe an unpromotable model, and any result it produces inherits that label.

## The residual, stated rather than hidden

The chokepoint is `execution/mizan_execution.py`: an execution surface obtains its model there and
the gate runs at that point. A future author who calls `MizanModel.default_model()` directly from a
new execution script bypasses it exactly as the current script did.

That residual is real and is the same shape as the one recorded for `85ff535` -- a guard reads a
declaration, not the code. It is narrowed, not closed, by a test that fails when a script which
persists portfolio state imports `default_model` directly. `default_model()` itself is deliberately
left ungated because the CLI, the server display and research callers legitimately use it.

## How to revisit

If a model ever becomes promotable, this surface should not be the one it runs on. Move it to
`PAPER_PILOT` and leave `RESEARCH_PAPER` for what it is for.
