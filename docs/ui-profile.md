# UI PROFILE — QuantOS

## Brand

Accent fill (light / dark): `--color-accent` (`#0071E3` / `#2997FF`)
Accent text (light / dark): legacy layer currently shares `--color-accent`
Deep surface for hero cards: none
Contrast verification: not yet certified; the existing legacy token layer predates the current
Apple-grade token vocabulary. The checker found the expected token-name mismatch, so contrast must
not be represented as verified.

## Where things live

Token layer: `src/quant_system/server/static/styles.css`
Component package: server-rendered HTML in `src/quant_system/server/ui/journeys.py`
Client controller: `src/quant_system/server/static/app.js`
Checker: `.agents/skills/While Coding skill/apple-grade-ui/scripts/check-ui.mjs`
Approved mockups: none — repository skill and existing design language are the standard

## Product shape

Primary device: desktop; phone layouts preserve the same information architecture in one column
Supported viewports: 320, 375, 768, 1024, 1440
Rendered inspection in this change: 390 × 844 and 1280 × 720, light and dark
Dark mode: user toggle
Primary navigation: top tab bar for seven governed journeys plus four secondary labs
Layout archetypes used: dashboard grid, grouped list, form sheet

## Locale and formatting

Locale: `en-IN`
Currency: INR via `Intl.NumberFormat("en-IN", {style: "currency", currency: "INR"})`
Number grouping: Indian lakh/crore through `Intl.NumberFormat`
Date format: ISO dates for evidence identity; localized display dates may be added later
Time format: 24-hour for market and evidence timestamps
Additional languages: none

## Domain vocabulary

Use: dataset, manifest, evidence, feature matrix, model trial, holdout, shadow session, paper
campaign, operation, verified, unavailable

Do not show: payload, instance, fake, dummy, magic hash, guaranteed return, certified without
evidence

## Product-specific rules

- Never pre-fill financial performance, validation passes, market activity, positions, or fills.
- A success state must be backed by immutable verified evidence or persisted runtime state.
- Missing evidence is an explicit empty or unavailable state, never a sample result.
- Shadow screens always state that broker writes are disabled; paper screens never imply a live
  broker effect.
- Model output remains research-only until governed promotion evidence says otherwise.

## Screen map

| # | Screen | Route(s) | Archetype | Mockup | Status |
|---|---|---|---|---|---|
| 1 | Data ingestion | `/`, `/ui/journey/ingestion` | Form sheet + grouped list | None | Real API wiring |
| 2 | Feature matrix | `/`, `/ui/journey/features` | Dashboard grid | None | Evidence unavailable |
| 3 | Model training | `/`, `/ui/journey/training` | Dashboard grid | None | Adapter pending |
| 4 | Holdout | `/`, `/ui/journey/holdout` | Dashboard grid | None | Adapter pending |
| 5 | Ledger | `/`, `/ui/journey/ledger` | Dashboard grid | None | Existing simulation |
| 6 | Shadow monitor | `/`, `/ui/journey/shadow` | Dashboard grid | None | No session configured |
| 7 | Paper pilot | `/`, `/ui/journey/pilot` | Dashboard grid | None | No campaign configured |
