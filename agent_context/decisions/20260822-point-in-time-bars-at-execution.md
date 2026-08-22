# Decision: execution surfaces consume PointInTimeBar, not PriceBar

STATUS: Accepted  
DATE: 2026-08-22  
OWNER: Founder and Claude Code

## Context

The governed model to execution adapter scoped in
`agent_context/work/active/20260822-claude-model-execution-adapter-scope.md` must feed a fitted
ridge model the same features it was trained on. That raised an open question, recorded there as
P2: which bar type crosses the execution boundary.

| | training | execution (`MarketContext`) |
|---|---|---|
| type | `PointInTimeBar` (`data/market_data.py:201`) | `PriceBar` (`core/domain.py:49`) |
| `available_at` | yes | **no** |
| `event_at` / `ingested_at` | yes | **no** |

`PriceBar` carries no information-availability field. A model fitted under strict point-in-time
discipline, then scored on bars whose availability cannot be established, has no defensible claim to
being point-in-time at the moment that matters — the decision.

## Decision

Execution surfaces carry `PointInTimeBar`. The feature history crossing into a strategy is
`tuple[PointInTimeBar, ...]` per symbol, filtered to `available_at <= decision_time`, and it is
sourced from the evidence store — the same acquisition that produced the training data — not from
the quote feed.

`MarketContext` gains this through a typed key in `extra_data` rather than a new field, so existing
strategies are unaffected and the change is additive.

## What verification of this decision revealed

The type mismatch was not the real problem. `src/quant_system/execution/realtime_shadow.py:327-334`
builds its `MarketContext` like this:

    context = MarketContext(
        current_time=now,
        current_bars={},        # empty
        historical_bars={},     # empty
        current_positions=dict(self._positions),
        available_cash=self._cash,
        extra_data={"current_quote": domain_quote},
    )

**Both bar maps are empty.** The shadow engine passes no bar history to a strategy at all — only the
current quote. The governed model needs 21 bars (`FEATURE_WARMUP_BARS_V1`) to compute one feature
row, so it cannot function on this surface as it exists. This is missing plumbing, not a type
conversion.

The quote side is in better shape than expected and needs no work: `LiveQuoteRecord`
(`data/live_feed.py:133`) already carries `event_at`, `received_at`, `provider_at`, and
`sequence_number`; `ReplayQuote` (`execution/replay_feed.py:73`) carries `timestamp`, `sequence_id`,
`provenance`, and `payload_digest`. Both are already point-in-time clean. The entire gap is bar
history.

## Consequence: decision cadence must change

`generate_signals` is called once per quote (`realtime_shadow.py:335`). The governed model is a
**daily close** model: features are computed on a completed daily bar, and the label is the first
later open to the following open. Firing it per quote would score one unchanged feature row
repeatedly through the session, emit identical signals all day, and stack position on each one.

That is not a hypothetical. It is the mechanism behind Red Team finding S9-B2 in
`agent_context/work/active/20260822-redteam-api-shadow-paper.md` (P&L double counted, positions
never close on maturity). A governed model on the current cadence would make that defect worse and
harder to attribute.

Therefore: a governed model decides **once per symbol per session**, at or after the close, and
executes at the next open. The per-quote path stays available for quote-driven strategies, which is
what it was built for.

## Rejected alternatives

- **Option B — accept `PriceBar`, stamp availability from `ctx.current_time`.** Rejected. It
  produces an availability value that is asserted rather than established, and the assertion would
  be indistinguishable in the evidence from a real one. Cheaper, and it discards the one property
  the whole training stack exists to protect.
- **Add availability fields to `PriceBar`.** Rejected. `PriceBar` is used across backtest,
  portfolio, strategies, and analytics; widening it forces every consumer to carry provenance it has
  no source for, and invites the same "assert a plausible value" failure at more sites.
- **Source bar history from the live quote feed.** Rejected. The feed carries quotes, not daily
  bars. Reconstructing daily bars from ticks at decision time would be a second, ungoverned path to
  a value the evidence store already holds — the same defect class as the second ridge model.

## Consequences and required work

1. New typed `extra_data` key carrying `tuple[PointInTimeBar, ...]`, filtered on `available_at`.
2. An evidence-store reader that serves point-in-time bar history to execution surfaces.
3. Shadow and paper engines populate it; today they pass `{}`.
4. A session-close decision cadence for governed models, distinct from the per-quote path.
5. Item 4 interacts with Red Team finding S9-B2. Sequence the S9-B2 repair first, or repair both
   together; do not layer the cadence change on the unrepaired defect.

Items 2, 3, and 4 were not in the adapter scope's original sizing and enlarge it materially.

## Status of dependent work

The adapter remains unimplemented and blocked, unchanged by this decision:
`src/quant_system/modeling/features.py` is claimed by two active records, and
`src/quant_system/execution/**` is under active Red Team adjudication. This decision settles the
design question only.
