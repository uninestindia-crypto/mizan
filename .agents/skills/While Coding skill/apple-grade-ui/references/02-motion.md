# Motion — physics, timing, choreography

Motion is the part everyone gets wrong, and it's the loudest signal of quality. A correct
interface with bad motion feels cheap; a plain interface with correct motion feels expensive.

**The one-sentence theory:** every animation answers *"where did this come from and where did it
go?"* If it doesn't answer that, delete it.

---

## 1. Springs, not curves

Apple animates with **springs**. A spring has no fixed duration — it has physics, so it can be
interrupted mid-flight and redirected without a visual glitch. That interruptibility is why iOS
feels responsive when you flick a sheet away halfway through its opening animation.

### 1.1 The two parameters that matter

SwiftUI describes a spring with `response` and `dampingFraction`:

- **`response`** — how long one full oscillation would take, in seconds. Effectively "how fast".
  Lower = snappier.
- **`dampingFraction`** — how much bounce. `1.0` = critically damped (no overshoot), `<1.0` =
  overshoots and settles, `>1.0` = sluggish.

Apple's iOS 17+ presets:

| Preset | response | dampingFraction | Character |
|---|---|---|---|
| `.smooth` | 0.4 | 1.0 | Critically damped. No overshoot at all. |
| `.snappy` | 0.4 | 0.85 | Slight overshoot. Lively but composed. |
| `.bouncy` | 0.5 | 0.70 | Visible overshoot and settle. Playful. |

The general-purpose custom default is `response: 0.55, dampingFraction: 0.75`.

### 1.2 Converting to CSS

CSS has `linear()` for real springs and `cubic-bezier()` for approximations. Use bezier
approximations for everything except the two places overshoot is essential — sheet presentation
and selection indicators — which use `linear()`.

**The motion tokens:**

| Token | Value | Character |
|---|---|---|
| `ease-standard` | `cubic-bezier(0.4, 0.0, 0.2, 1)` | The workhorse. Both-ends easing. |
| `ease-decelerate` | `cubic-bezier(0.0, 0.0, 0.2, 1)` | **Entering.** Fast start, gentle stop. |
| `ease-accelerate` | `cubic-bezier(0.4, 0.0, 1.0, 1)` | **Exiting.** Gentle start, fast finish. |
| `ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Snappy with overshoot. |
| `ease-emphasis` | `cubic-bezier(0.16, 1, 0.3, 1)` | Long, luxurious deceleration. |

**Enter decelerates, exit accelerates.** This mirrors physical objects: something arriving has been
in motion and is coming to rest; something leaving is being pushed away. Reversing these is the
single most common motion bug, and it feels subtly wrong to everyone while being identifiable by
almost nobody.

### 1.3 Durations

| Token | ms | Use |
|---|---|---|
| `duration-instant` | 100 | Press feedback, hover, checkbox toggle |
| `duration-fast` | 200 | Small state changes, tooltip, chip select |
| `duration-base` | 300 | The default. Cards, sheets, page transitions |
| `duration-slow` | 400 | Large-surface moves, full-screen transitions |
| `duration-deliberate` | 600 | Onboarding reveals, celebratory moments only |

**Ceiling: 400ms** for anything blocking interaction. Beyond that the interface feels like it's
thinking rather than responding. The only exceptions are ambient/decorative loops and explicit
celebration moments.

**Distance scales duration.** A 20px nudge at 300ms feels sluggish; a full-screen slide at 200ms
feels violent. Roughly: <100px → 200ms, 100–400px → 300ms, >400px → 400ms.

---

## 2. What may be animated

**Animate only `transform` and `opacity`.** These are composited on the GPU and don't trigger
layout or paint. Everything else risks jank on low-end mobile devices students and vendors carry.

| Safe | Expensive — avoid |
|---|---|
| `transform: translate / scale / rotate` | `width`, `height`, `top`, `left`, `margin` |
| `opacity` | `box-shadow` (animate a pseudo-element's opacity instead) |
| `filter` (sparingly) | `background-color` on large surfaces |
| `clip-path` (modern browsers) | `backdrop-filter` (never animate this) |

**Never `transition-all`.** It animates properties you didn't intend, including ones that trigger
layout, and it's un-auditable. Always name the properties:

```css
transition-property: transform, opacity;
```

**Never animate to/from `display: none`.** Use `opacity` + `visibility` with a delay, or
`@starting-style` / `transition-behavior: allow-discrete` in modern browsers.

**`will-change` is a scalpel, not a seasoning.** Add it immediately before an animation starts,
remove it after. A permanently `will-change: transform` element holds a compositor layer forever
and costs memory.

---

## 3. The recipe book

Use these exactly. Don't improvise.

### Press feedback (every button, card, and row)
```css
transition: transform 100ms cubic-bezier(0.4,0,0.2,1),
            background-color 100ms cubic-bezier(0.4,0,0.2,1);
/* :active */ transform: scale(0.97);
```
Scale, never color-flash alone. 0.97 for buttons, 0.98 for cards (larger surfaces need less scale
to read as the same amount of "push"). On a full-width row use `0.99` or a background tint instead
— scaling a wide element looks like it's warping.

### Sheet / modal presentation
```
enter: translateY(100% → 0) + backdrop opacity(0 → 1), 400ms ease-decelerate
exit:  translateY(0 → 100%) + backdrop opacity(1 → 0), 300ms ease-accelerate
```
Exit is faster than enter. Dismissal should feel eager; arrival should feel considered.

### Popover / dropdown / menu
```
enter: scale(0.96 → 1) + opacity(0 → 1), 200ms ease-decelerate
       transform-origin: the anchor's edge
exit:  scale(1 → 0.98) + opacity(1 → 0), 150ms ease-accelerate
```
**`transform-origin` must point at whatever opened it.** A menu that grows from its trigger is
causally legible; one that fades in from center is not.

### Tab bar selection
```
icon:  scale(1 → 1.12 → 1) over 300ms ease-spring
label: color transition 200ms ease-standard
```
The overshoot is the whole point — it's the tactile "click".

### List item enter (new row arrives)
```
opacity(0 → 1) + translateY(8px → 0), 300ms ease-decelerate
stagger: 30ms per item, capped at 6 items (180ms total)
```
Never stagger more than 6. Beyond that the last item feels broken rather than choreographed.

### List item exit (row removed)
```
opacity(1 → 0) + scale(1 → 0.96), 200ms ease-accelerate
then collapse height 200ms ease-standard
```
Fade first, then collapse. Collapsing while still visible looks like a rendering glitch.

### Skeleton → content
```
skeleton: opacity(1 → 0) 200ms
content:  opacity(0 → 1) 200ms, starting 100ms in (overlap)
```
A crossfade, not a swap. The 100ms overlap is what prevents the flash of empty space.
**The skeleton must match the final layout's dimensions** or the content jumps — which is worse
than no skeleton at all.

### Value change (a number updates)
```
opacity(1 → 0.4 → 1) 300ms, plus translateY(-2px → 0) on the new value
```
Enough to catch the eye, not enough to distract. For a counter that updates often (live bid count),
animate only when the change is user-relevant, and never more than once per 500ms.

### Progress bar fill
```
transform: scaleX(), transform-origin: left
600ms ease-emphasis
```
Scale, never `width` — `width` triggers layout on every frame.

### Toast
```
enter: translateY(16px → 0) + opacity(0 → 1) + scale(0.96 → 1), 300ms ease-spring
hold:  4000ms (8000ms if it has an action)
exit:  opacity(1 → 0) + scale(1 → 0.98), 200ms ease-accelerate
```
Pause the hold timer on hover or focus.

### Pull to refresh
Rubber-band the content with resistance (`translateY = drag * 0.5`), snap back with
`ease-spring`. The spinner appears at 60px of pull and commits at 80px.

---

## 4. Choreography

When several things move at once, they must move as a group with a clear leader.

- **One focal point.** The user's eye follows one thing. Everything else supports it.
- **Stagger, don't scatter.** Related items enter in sequence along the reading direction (top to
  bottom, leading to trailing), 30–50ms apart. Unrelated items should not animate at all.
- **Shared elements persist.** If an item expands into a detail view, the item's image and title
  should *move* to their new positions, not cross-fade. Continuity of identity is the highest form
  of motion design and the thing users can't articulate but always notice.
- **Nothing crosses paths.** Two elements animating through each other reads as chaos.
- **Exit before enter, or overlap by ≤50%.** Never a full gap of empty screen.

### Motion hierarchy on a screen load
```
0ms    — chrome (nav bar, tab bar) is already there, no animation
0ms    — skeletons already present
100ms  — hero/primary card fades up
150ms  — stat row fades up (staggered 30ms each)
250ms  — content sections fade up
```
Total under 400ms. Chrome never animates on load — it's the frame, not the content.

---

## 5. Reduced motion

`prefers-reduced-motion: reduce` is a **medical accessibility setting**. Users enable it because
motion causes nausea, dizziness, or seizures. Ignoring it is not a polish issue.

**"Reduced" means reduced, not removed.** Stripping all animation makes state changes confusing —
things teleport. The correct response:

| Normal | Reduced |
|---|---|
| Slide + fade | Fade only |
| Scale + fade | Fade only |
| Spring overshoot | Linear-ish ease, no overshoot |
| Staggered list entry | All at once, fade only |
| Parallax / auto-playing loops | Static |
| 300ms | 150ms or less |
| Shared-element transition | Simple crossfade |

Implement globally, then let components opt into their own reduced variant:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  .motion-safe-fade { transition-duration: 150ms !important; }
}
```

Also honour `prefers-reduced-transparency` (collapse materials to opaque) and
`prefers-contrast: more` (raise separator opacity, add borders to controls).

---

## 6. Perceived performance

Motion is how you buy time. These techniques matter more than actual milliseconds.

- **Respond within 100ms, always.** The press state must render before anything else — even if the
  action takes 3 seconds. Sub-100ms feedback reads as "instant" regardless of what follows.
- **Optimistic UI.** Show the result immediately, reconcile when the server answers, and roll back
  visibly with an explanation if it fails. This is what makes a product feel fast on a variable
  mobile network, where the round trip is the slow part and nothing you optimize in the UI will fix it.
- **Skeletons over spinners.** A skeleton shaped like the content says "this is what's coming".
  A spinner says "wait". Spinners are for indeterminate *actions* (submitting), never for content.
- **Don't show a loader under 300ms.** A flash of spinner is worse than a brief pause. Delay the
  loader's appearance by 300ms; if the data arrives first, the user never sees it.
- **Never move content under a user's finger.** Reserve space for anything that will load in
  (`min-height`, aspect-ratio boxes). Layout shift after load is the most infuriating bug in mobile
  web and it is always preventable.
- **Progressive disclosure of loading.** 0–300ms: nothing. 300ms–3s: skeleton. 3s+: skeleton plus
  a "Still working…" line. 10s+: offer a cancel.

---

## 7. Motion review

Before shipping anything that moves:

- [ ] Only `transform` and `opacity` are animated
- [ ] Properties are named — no `transition-all`
- [ ] Entering decelerates, exiting accelerates
- [ ] Duration ≤400ms for anything interactive
- [ ] `transform-origin` points at the causal source
- [ ] Interruptible — clicking twice fast doesn't break it
- [ ] `prefers-reduced-motion` variant implemented and tested
- [ ] No layout shift when it finishes
- [ ] Tested on a throttled CPU (Chrome DevTools 4× slowdown), still smooth
- [ ] Nothing loops infinitely unless it represents ongoing activity
