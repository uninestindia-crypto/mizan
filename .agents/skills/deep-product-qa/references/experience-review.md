# Consumer Experience and Visual Review

## Contents

1. What this review can establish
2. Persona construction
3. Black-box first-impression session
4. Task-based consumer sessions
5. Observable emotion proxies
6. Experience quality dimensions
7. Visual inspection protocol
8. Interaction and motion protocol
9. Copy, feedback, and trust
10. Delight and “fun”
11. Scoring
12. Issue classification

## 1. What this review can establish

Simulate disciplined consumer review and identify evidence-backed experience risks. Do not claim that an AI observation equals research with real target consumers. Real usability studies remain valuable for consequential or novel products.

Use three evidence levels:

1. **Observed defect:** the interface or behavior demonstrably violates a requirement or usability/accessibility invariant.
2. **Likely consumer risk:** observable friction supports a reasoned prediction of confusion, mistrust, anxiety, or abandonment.
3. **Preference/hypothesis:** a possible improvement without enough evidence to call it a defect.

Label each finding. Do not disguise taste as certainty.

## 2. Persona construction

Derive personas from the actual product, roles, copy, data model, and journeys. Include only personas with a credible use case.

At minimum consider:

- first-time target customer with no product knowledge;
- returning customer optimizing for speed;
- low-confidence or low-technical-literacy customer;
- hurried or interrupted customer;
- customer using narrow screen, keyboard, assistive technology, or large text;
- power user for products with advanced or repeated workflows;
- admin/support operator when such surfaces exist.

For each persona, write:

| Field | Description |
|---|---|
| Goal | Concrete result the person wants |
| Context | Device, time pressure, environment, prior knowledge |
| Concern | What could cause hesitation or mistrust |
| Success | Observable completion and confidence signal |
| Failure | Confusion, abandonment, wrong result, or harm |

Do not invent demographic stereotypes. Test differences in goals, capability, context, and access needs.

## 3. Black-box first-impression session

Run the built interface before reading implementation details for the current journey whenever practical. Code inspection is still used for scope, but first-impression judgment should not depend on knowing where controls are hidden.

For each major entry point, record at 5 seconds, 30 seconds, and first attempted action:

- what product this appears to be;
- the primary action perceived;
- whether the page/screen appears trustworthy and complete;
- what is visually dominant;
- what is ambiguous or competing for attention;
- whether the next step is obvious;
- any visible defect, loading uncertainty, or unexpected demand.

Do not convert these observations into universal consumer claims. State what in the interface produced the inference.

## 4. Task-based consumer sessions

Give each persona a goal, not a sequence of clicks. Attempt the goal through the real interface.

Record:

- entry point and initial state;
- path chosen without code knowledge;
- hesitation points and competing choices;
- wrong turns and whether recovery was apparent;
- number of meaningful decisions and avoidable steps;
- unclear terminology or missing prerequisites;
- system feedback after every action;
- confidence that the action succeeded;
- persisted and downstream outcome;
- final next-step clarity.

Repeat critical goals from clean state. A path discovered during the first attempt can bias later attempts; retain the first-use evidence separately.

## 5. Observable emotion proxies

Infer likely perception only from observable triggers:

| Likely perception | Observable triggers |
|---|---|
| Confidence | clear hierarchy, predictable behavior, explicit status, reversible actions, consistent data |
| Confusion | competing primary actions, unexplained terminology, ambiguous state, inconsistent labels |
| Anxiety | irreversible action without consequence, uncertain payment/save state, missing recovery, alarming errors |
| Mistrust | contradictory totals, broken polish, hidden fees, permission surprise, vague privacy claims |
| Frustration | repeated input, dead ends, lost work, slow/no feedback, inaccessible control, repeated failure |
| Satisfaction | core goal completed efficiently with clear confirmation and preserved control |
| Delight | helpful anticipation, elegant recovery, responsive feedback, meaningful polish without obstruction |

Write findings in this form:

```text
Trigger: Payment spinner continues after the provider has declined the card.
Observed behavior: No error or retry action appears for 18 seconds.
Likely perception: The customer may fear a duplicate charge or frozen checkout.
Impact: Abandonment or repeated payment attempt.
Confidence: High, because state and recovery are both absent.
```

## 6. Experience quality dimensions

Evaluate every major journey on these dimensions:

1. **Comprehension:** purpose, terminology, and next action are understandable.
2. **Findability:** required controls and information can be located naturally.
3. **Efficiency:** the journey avoids unnecessary decisions, repetition, and waiting.
4. **Feedback:** actions produce immediate, accurate, proportionate status.
5. **Error prevention:** constraints and consequences are clear before failure.
6. **Recovery:** errors preserve safe work and provide an effective next action.
7. **Consistency:** patterns, language, data, and outcomes agree across surfaces.
8. **Accessibility:** the journey works across supported access modes.
9. **Trust:** privacy, payment, destructive actions, and important data feel truthful and controlled.
10. **Fit and finish:** visual and interaction details appear deliberate and stable.
11. **Performance perception:** waits are bounded, explained, and appropriately progressive.
12. **Delight appropriateness:** polish supports the product's purpose rather than distracting from it.

Functional failure caps the affected journey's overall experience rating at 2/5. A broken journey cannot receive a premium score because it looks attractive.

## 7. Visual inspection protocol

Capture representative stable states at every supported form factor and theme. Compare both within a flow and across the product.

Open and inspect the rendered captures at sufficient/original resolution. DOM structure, CSS source, component snapshots, and automated contrast output can support the review but cannot substitute for looking at the rendered pixels.

Inspect in this order:

1. **Integrity:** missing assets, overlap, clipping, overflow, broken layering, unusable scroll, rendering error.
2. **Hierarchy:** one clear primary action, appropriate grouping, readable sequence, balanced emphasis.
3. **Geometry:** alignment, grid, margins, spacing rhythm, component dimensions, safe areas, touch targets.
4. **Typography:** family, weight, size, line height, measure, wrapping, truncation, numeric alignment.
5. **Color:** contrast, state meaning, theme behavior, disabled/selected distinction, non-color cues.
6. **Content resilience:** long text, user content, localization, empty/dense data, large numbers, failed media.
7. **Consistency:** same component/state behaves and appears consistently across routes/platforms.
8. **Finish:** icons, images, dividers, shadows, corners, transitions, placeholder/skeleton quality.

Test breakpoints around actual source values. A screenshot at one phone and one desktop width is not a responsive audit.

For every visual issue include route/screen, viewport/device, state, screenshot, expected principle, consumer impact, and recurrence scope.

## 8. Interaction and motion protocol

Test every interactive component using applicable pointer, touch, keyboard, gesture, and assistive input.

Inspect:

- discoverability and affordance before interaction;
- hover, focus, pressed, selected, disabled, loading, success, and error states;
- immediate acknowledgement and prevention of accidental repetition;
- transition continuity and preservation of spatial context;
- gesture conflicts, target size, edge gestures, back behavior, and cancel/dismiss;
- animation interruption, repeated activation, reduced motion, and slow-device behavior;
- whether motion communicates cause and effect rather than delaying the user.

Motion is defective when it obscures state, blocks action unnecessarily, causes sickness risk, drops input, or leaves the UI between states.

## 9. Copy, feedback, and trust

Review labels and messages in the moment they are needed:

- controls use specific verbs and consistent product vocabulary;
- irreversible actions describe consequence, not only “Are you sure?”;
- errors explain what happened, what was preserved, and what to do next;
- success confirms the actual durable result;
- loading distinguishes waiting from failure and indicates progress when measurable;
- totals, dates, currency, units, permissions, privacy, and subscription terms are explicit;
- empty states explain why the state is empty and the relevant next action;
- technical/internal language does not leak to consumers;
- humor never trivializes loss, payment, health, safety, privacy, or failure.

Verify copy against behavior. A reassuring message that contradicts actual persistence is a high-risk trust defect.

## 10. Delight and “fun”

Treat fun as product-context fit, not universal decoration. A children's learning product, merchant dashboard, medical tool, and payment recovery flow require different emotional tones.

Evaluate whether the product:

- responds promptly and feels under the user's control;
- rewards meaningful progress without interrupting the goal;
- uses motion, sound, illustration, or microcopy consistently with its audience;
- reduces effort through helpful defaults and anticipation;
- makes success legible and satisfying;
- handles failure with dignity and effective recovery;
- avoids novelty that slows repeat users or harms accessibility;
- preserves seriousness where trust or consequence is high.

Do not add animation, gamification, sound, or playful copy merely to satisfy a “fun” requirement. Recommend it only when the target audience, journey, and evidence support it.

## 11. Scoring

Score each quality dimension from 0 to 5:

| Score | Meaning |
|---:|---|
| 0 | Cannot execute or catastrophic failure |
| 1 | Severe failure or pervasive consumer harm |
| 2 | Major friction; journey works only with struggle or help |
| 3 | Functional and understandable, with meaningful roughness |
| 4 | Strong, consistent, low-friction experience with minor gaps |
| 5 | Exceptional, evidence-backed execution across relevant states and platforms |

Every score needs evidence and at least one sentence explaining why it is not one point higher. Mark `N/T` when not tested; never convert `N/T` to zero or omit it from the report.

Do not combine the experience score with verified coverage. A 4.5/5 experience score on 40% tested scope is not a release-quality product.

## 12. Issue classification

Classify findings as:

- **Functional defect:** behavior or outcome is wrong.
- **Visual defect:** rendered presentation is objectively broken or inconsistent with an established system.
- **Accessibility defect:** supported use is prevented or materially impaired.
- **Usability risk:** evidence shows avoidable confusion, effort, or recovery difficulty.
- **Trust risk:** behavior or communication can mislead users about money, data, permission, status, or consequence.
- **Performance-experience defect:** measured delay or instability harms the journey.
- **Delight opportunity:** optional improvement with product-context evidence.
- **Research question:** real-user validation is needed before deciding.

Keep opportunities and preferences out of defect counts unless they violate an established requirement. Prioritize customer impact over visual novelty.
