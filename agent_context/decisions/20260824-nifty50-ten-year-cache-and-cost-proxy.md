# Ten-year NIFTY 50 cache and research-cost boundary

Date: 2026-08-24

## Decision

The requested 2016-08-22 through 2026-08-21 real-data campaign will persist both discovery and
authority-bound Upstox acquisitions in an immutable, checksummed `EvidenceStore` under
`data/evidence/market-cache/nifty50-current-20160822-20260821/`. A cache hit is fully verified and
rebuilt into the governed acquisition type before use. A corrupt or ambiguous cache stops closed
and does not contact the provider. Credentials, request headers, and raw authenticated HTTP payloads
are excluded; the cache contains canonical bars and the provenance already covered by the governed
dataset manifest.

The repository's equity-delivery cost catalog does not cover every required component before
2020-07-01. The user chose to retain the ten-year range. The delivery runner therefore adds these
explicit research proxies only over the uncovered intervals:

| Component | Interval | Rate and basis | Side |
|---|---|---|---|
| Exchange turnover | 2016-08-22 to 2017-03-31 | `0.0000345` of turnover | both |
| Indirect-tax component represented in the `GST` slot | 2016-08-22 to 2017-06-30 | `0.18` of brokerage + exchange + SEBI charges | both |
| Stamp duty | 2016-08-22 to 2020-06-30 | `0.000150` of turnover | buy |

Every proxy rule ID begins `RESEARCH-PROXY-`; its source is
`research-proxy://quantos/nifty50-10y/user-authorized-2026-08-24`; and its hashes flow into label and
trial evidence. Canonical dated rules take over at their existing boundaries without overlap.

## Claim boundary

These proxy values are reproducible assumptions, not historical statutory or state-specific facts.
The run may support research diagnostics only. It cannot establish historical cost accuracy,
point-in-time NIFTY 50 portfolio performance, model promotion, or deployment readiness. The static
2026 constituent snapshot also creates survivorship bias, so outputs are described as 50 current-
member single-stock studies.

No synthetic or generated market bars are permitted. A real provider failure remains a typed
terminal result and stops the campaign without fallback.
