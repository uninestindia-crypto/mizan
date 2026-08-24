# Decision: canonical governed feature window

DATE: 2026-08-24
STATUS: ADOPTED FOR REPAIR; NOT A PROMOTION OR RELEASE ADJUDICATION

## Context

The governed six-feature kernel accepted any history of at least 21 bars. Four features only use a
fixed tail, but Wilder RSI-14 and ATR-14 seed at the beginning of the supplied sequence. Training
supplied an expanding prefix from dataset inception while execution accepted any retained prefix.
Consequently, the same decision bar could receive different feature values and a different score.

## Decision

Feature schema v2 uses exactly the trailing 21 point-in-time-available bars, ordered oldest first,
for every row. The shared `compute_feature_values` boundary enforces the tail so training and
execution cannot select different windows accidentally. Feature-row provenance hashes only those
21 consumed records.

Schema v1 remains a supported historical identity so immutable records can still be reconstructed
and audited. It is not compatible with the repaired execution adapter. New trial/evaluation
evidence carries the v2 schema identity, and executable model bundles must bind that identity from
the verified model manifest. Evidence without the identity, including pre-repair models, fails
closed.

## Consequences

- Retaining extra old bars cannot change the current feature vector.
- Supplying fewer than 21 available bars produces no execution signal and a typed modeling failure
  at the kernel boundary.
- Existing real-data trial results remain historical research evidence only. Their fitted states
  cannot be represented as v2 or executed without retraining under v2.
- Any future window or arithmetic change requires another feature-schema version and fresh evidence.
