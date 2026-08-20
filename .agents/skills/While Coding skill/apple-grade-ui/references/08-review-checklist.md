# The gate

Walk this before reporting any UI work complete. Every line passes, or you state the exception and
why. "I think it's fine" is not a pass — **look at the rendered result**.

Automated first:
```bash
node scripts/check-ui.mjs
```

On a project you have not built in before, verify the wiring first — an unwired token layer makes
every check below pass while the page renders unstyled:
```bash
node scripts/check-ui.mjs --verify-setup .
```

---

## Tokens

- [ ] No raw hex colors in `.tsx` / `.css` outside the token definitions
- [ ] No Tailwind arbitrary values (`text-[13px]`, `bg-[#0A5AFF]`, `p-[18px]`)
- [ ] No default Tailwind palette (`gray-500`, `blue-600`, `slate-900`, `red-500`…)
- [ ] No raw `px` outside the token layer (borders and hairlines excepted)
- [ ] Every spacing value is on the 4pt grid
- [ ] Radii come from the scale, and nested radii are concentric (`inner = outer − padding`)
- [ ] Shadows are `shadow-e1`–`e4`, never `shadow-md`/`lg`/`xl`

## Typography

- [ ] Every string uses one of the eleven type classes
- [ ] No `leading-*` or `tracking-*` layered on top of a type class
- [ ] At most three distinct type styles per card
- [ ] Uppercase only on `text-caption-2`
- [ ] Nothing below 11px
- [ ] `tabular-nums` on every number in a column or that updates in place
- [ ] Currency, dates, and number grouping via `Intl`, using **the profile's locale** — never a
      hand-rolled format string, and never a locale the profile did not name

## Color

- [ ] Text uses label tiers, never `text-gray-*`
- [ ] `label-tertiary` only on genuinely non-essential text
- [ ] `warning` is never small text on a light background (use `warning-text`)
- [ ] Every status carries a glyph or word in addition to its color
- [ ] Exactly one accent-filled primary action in the viewport
- [ ] The `ai` tone used only for model-produced content (if the product has an AI surface)
- [ ] Screen reads correctly in grayscale

## Layout

- [ ] Named archetype from the seven in `01-foundations.md §7`
- [ ] Screen margins `px-4` / `px-6` / `px-8` by breakpoint
- [ ] Body text capped at 60–75 characters
- [ ] Space above a heading exceeds space below it
- [ ] Tested at 320, 375, 768, 1024, 1440
- [ ] Same information architecture across breakpoints
- [ ] Tab bar respects `env(safe-area-inset-bottom)`; content clears it

## Components

- [ ] Composed from the profile's component package — anything new was added back to it
- [ ] Matches the approved mockup **where the profile names one** (image actually opened and
      compared, not inferred from its filename)
- [ ] List separators are inset to the content start; last row has none
- [ ] Chevrons only on rows that navigate
- [ ] Badges state facts; chips and buttons perform actions

## States (Law 9)

- [ ] Default
- [ ] Hover — inside `@media (hover: hover)`
- [ ] Pressed — `scale(0.97)` within 100ms
- [ ] Focus-visible — 2px accent ring with offset
- [ ] Disabled — with an adjacent explanation of why
- [ ] Loading — skeleton for content, in-button spinner for actions
- [ ] Empty — the correct one of the three flavors
- [ ] Error — what happened, what to do, how to retry
- [ ] Overflow — long names, huge numbers, 500 rows

## Motion

- [ ] Only `transform` and `opacity` animated
- [ ] Properties named — no `transition-all`
- [ ] Entering decelerates, exiting accelerates
- [ ] ≤400ms for anything interactive
- [ ] `transform-origin` points at the causal source
- [ ] Interruptible
- [ ] `prefers-reduced-motion` variant implemented **and tested**
- [ ] No layout shift on completion
- [ ] Smooth under 4× CPU throttling

## Interaction

- [ ] Every target ≥44×44
- [ ] ≥8px between adjacent targets
- [ ] Primary actions in the thumb zone on phone
- [ ] Every gesture has a visible fallback
- [ ] Full keyboard operation; focus order matches visual order
- [ ] `Esc` closes overlays; focus returns to the trigger
- [ ] Composite widgets are one tab stop with arrow-key navigation

## Accessibility

- [ ] 4.5:1 text contrast (3:1 for large text, icons, control boundaries) — **measured**
- [ ] Real elements — no `<div onClick>`
- [ ] Heading levels in order, no skips
- [ ] `aria-label` on every icon-only control
- [ ] Errors linked with `aria-describedby` + `role="alert"`
- [ ] Route changes announced; focus moved to the new `<h1>`
- [ ] `lang` on non-English content (voice transcripts, user-generated text)
- [ ] 200% zoom without clipping
- [ ] Reduced motion, reduced transparency, and increased contrast all handled
- [ ] `npx @axe-core/cli <url>` clean

## Content

- [ ] Sentence case
- [ ] Buttons are verb phrases naming the outcome
- [ ] No "Submit", "OK", "An error occurred", "Something went wrong", "No data"
- [ ] Errors say what happened and what to do next
- [ ] Empty states offer an action
- [ ] AI output labeled, confidence stated, reviewable before it executes (if applicable)
- [ ] Identifiers never truncated

## Dark mode

- [ ] Every token has a dark value
- [ ] Depth from surface lightness, not shadows
- [ ] Saturated colors desaturated and brightened
- [ ] Contrast re-measured in dark mode (it is not automatic)
- [ ] Actually rendered and looked at, not assumed

## Performance

- [ ] No layout shift after load (reserved space for async content)
- [ ] Images have dimensions or `aspect-ratio`, and `loading="lazy"`
- [ ] Long lists virtualized above ~100 rows
- [ ] No `will-change` left on permanently
- [ ] Skeletons match final dimensions

## Before you report done

- [ ] Ran it. Looked at it. Light **and** dark. Phone **and** desktop.
- [ ] Screenshot or a described observation of the actual rendered result
- [ ] Console clean — no errors or warnings
- [ ] `npm run typecheck` and `npm run lint` pass
- [ ] Anything skipped is stated explicitly, with the reason
