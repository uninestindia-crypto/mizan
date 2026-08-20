---
name: apple-grade-ui
description: >-
  The design law for every pixel of a product. Load this BEFORE writing or editing any UI, UX,
  frontend, component, page, screen, layout, style, CSS, Tailwind class, animation, icon, form,
  chart, empty state, error state, or copy string. Triggers on: "UI", "UX", "frontend", "design",
  "style", "make it look", "polish", "redesign", "component", "page", "screen", "layout",
  "responsive", "dark mode", "animation", "transition", "spacing", "typography", "color", "theme",
  "button", "card", "modal", "sheet", "nav", "tab bar", "sidebar", "form", "input", "table", "list",
  "toast", "loading", "skeleton", "chart", "dashboard", "design system", "tokens", ".tsx", ".css",
  "tailwind.config", "globals.css". Also triggers whenever a task's output is something a human will
  look at. Encodes Apple's Human Interface Guidelines — Dynamic Type scale, system color structure,
  spring motion, materials, 44pt targets — as an enforceable token layer that SHIPS WITH THIS SKILL
  and can be copied into any project in one step, plus a checker that turns every mechanical rule
  into an exit code. Project-agnostic: a one-page profile binds it to your brand, stack, and routes.
  If you are about to type a raw hex color, a raw px value, an arbitrary Tailwind bracket value, or
  a `transition-all`, you needed this skill and did not load it.
---

# Apple-Grade UI — The Design Law

You are the design team at a company that ships one thing: interfaces so obviously correct that
nobody notices them. This file is not advice. It is the specification. Deviating from it is a bug
with the same severity as a failing test.

## The mandate

The product must feel like an Apple product — not "clean", not "modern", not "minimal". Those are
adjectives amateurs use. Apple-grade means five specific, verifiable things:

1. **Nothing is arbitrary.** Every size, color, radius, duration, and gap comes from a token. If
   you cannot name the token, you do not get to use the value.
2. **Hierarchy is unambiguous.** At a glance, from three feet away, a user knows what the screen is
   about, what the one important action is, and what is merely present.
3. **Motion explains causality.** Things move because something happened, from where it happened,
   at a speed a physical object would move. Motion is never decoration.
4. **Density serves the content, not the grid.** Whitespace is load-bearing. Cramped screens read
   as cheap; empty screens read as unfinished.
5. **It degrades with dignity.** Dark mode, tiny phone, huge type, no network, screen reader,
   reduced motion, 500 rows — all of these are the product, not edge cases.

## The ten laws (non-negotiable)

**Law 1 — Tokens or nothing.**
No raw hex. No raw px. No Tailwind arbitrary values (`text-[13px]`, `bg-[#0A5AFF]`, `p-[18px]`).
No default Tailwind palette (`gray-500`, `blue-600`, `slate-900`). Use the token scales only. The
one exception is a documented one-off annotated with `ui-allow:` and a stated reason.

**Law 2 — The type scale has eleven steps and you may not invent a twelfth.**
`display, title-1, title-2, title-3, headline, body, callout, subhead, footnote, caption-1,
caption-2`. Every string on screen is exactly one of these. See `references/01-foundations.md`.

**Law 3 — One primary action per screen.**
Exactly one filled accent button in the primary viewport. Everything else is tinted, gray, or
plain. Two filled buttons of equal weight means you have not decided what the screen is for.

**Law 4 — 44×44 minimum, always.**
Every interactive element has a ≥44×44 CSS-px hit area, even if the visible glyph is 16px. Use
padding or the `.tap-expand` utility. This is not negotiable on desktop either.

**Law 5 — Contrast floors are hard floors.**
4.5:1 for text under 24px (or under 19px bold). 3:1 for larger text, icons carrying meaning, and
the boundary of any control. **Verify, don't estimate** — run the contrast report below. Color is
never the only carrier of meaning: pair every status color with a glyph or a word.

**Law 6 — Motion is spring-based, interruptible, and ≤400ms.**
No linear. No `ease`. No `transition-all`. Name the properties. Honour
`prefers-reduced-motion: reduce` by collapsing to opacity-only. See `references/02-motion.md`.

**Law 7 — Optical alignment beats mathematical alignment.**
Nudge for what the eye sees: icons next to text align on cap-height not bounding box; a play
triangle sits 1px right of center; large numerals hang their punctuation. Trust your eye, then
encode the nudge as a token.

**Law 8 — Nested corners are concentric.**
`inner_radius = outer_radius − gap`. A 20px card with 12px padding holds an 8px inner element.
Never a bigger radius inside a smaller one. Never equal radii with a gap between them.

**Law 9 — Every state exists before you ship.**
Default, hover (pointer only), pressed, focus-visible, disabled, loading, empty, error,
partial/stale, and "too much data". A component with only a default state is 10% done.

**Law 10 — Copy is design.**
Sentence case everywhere except proper nouns. Buttons are verbs describing the outcome
("Book a stay", never "Submit"). Errors say what happened and what to do next, never
"An error occurred". See `references/06-writing.md`.

---

## Step 0 — Install the token layer (once per project, ~2 minutes)

**This skill ships its own design system.** You are not expected to invent a token layer, and you
must not. Copy the files; do not retype the values.

| Copy this file | To | Purpose |
|---|---|---|
| `assets/tokens.css` | e.g. `src/styles/tokens.css`, imported first | Every token, light + dark, plus base utilities |
| `assets/tailwind.preset.js` | project root (Tailwind v3 only) | Makes `text-body`, `bg-surface`, `shadow-e1`, `duration-base` resolve |
| `assets/components.tsx` | the component package, e.g. `src/components/ui.tsx` | **The reference implementation** — Button, Card, ListRow, Badge, Field, EmptyState, Skeleton, StatCard, with every state and ARIA already correct |
| `scripts/check-ui.mjs` | e.g. `scripts/check-ui.mjs` | The enforcement pass |

**Copy `components.tsx`; do not rebuild it from the spec tables.** The specs in
`references/03-components.md` describe a dozen decisions per component — the hover guard, the
pressed scale, the focus ring, the disabled explanation, the loading width lock, the ARIA wiring.
Every one is a chance to drift, and drift is what makes an interface look almost-right. The file
compiles under `strict` and passes the checker as shipped.

Then, in `tokens.css`, edit **only** the `BRAND` block at the top — six values. Everything else is
Apple's structure and is not yours to adjust. The shipped defaults are already contrast-verified,
so a project with no brand colors yet can ship them unchanged and still pass.

Then run these three commands, in this order. They are the whole setup gate:

```bash
node scripts/check-ui.mjs --verify-setup .
```

```bash
node scripts/check-ui.mjs --tokens src/styles/tokens.css
```

```bash
node scripts/check-ui.mjs
```

**Do not skip the first one.** It catches the failure that has no symptom: if the Tailwind preset
is not wired, every token class resolves to nothing, the page renders unstyled rather than broken,
and it just looks cheap. Nothing errors, so nothing tells you.

On the second, every pair must read `PASS` or `BY DESIGN`. A single `FAIL` means the palette is
wrong, and you fix the token — never the checklist. **A design system whose contrast has not been
measured is a decoration, not a system.**

If the project already has a token layer, do not replace it. Read it, map its names onto the
concepts below, and record the mapping in the profile (Step 1).

---

## Step 1 — Write the project profile (once per project, ~5 minutes)

This skill is the law; the profile is the local jurisdiction. It is one short file at
`docs/ui-profile.md` (or wherever the project keeps docs) recording the handful of facts that are
genuinely project-specific: brand values, token file locations, the component library path,
approved mockups and the routes they map to, locale and currency formatting, and the primary
device. The template and a fully worked example are in `references/07-project-profile.md`.

**Without a profile, every session re-guesses these facts and the product drifts.** Write it once.

---

## Workflow — run this every time

### Step 2 — Orient (30 seconds, skippable only if you did it this session)
- Read the profile. Is there an approved mockup for this screen? **If yes, the mockup wins over
  your taste.** Open the actual image and compare against it — do not work from its filename.
- What altitude is this? A token change, one component, one screen, or a flow? Match the effort.

### Step 3 — Choose the pattern before writing code
Name the layout archetype out loud: *grouped list*, *dashboard grid*, *detail with hero*, *form
sheet*, *stepper flow*, *feed*, *split view*. There are seven; they are all in
`references/01-foundations.md §7`. Do not invent an eighth without a reason you can state.

### Step 4 — Build with tokens
Compose from the project's component package first (the profile names it). Only write raw markup
for something genuinely new — and if it is new, add it to the package so the next screen inherits
it. Component specs, to the token, are in `references/03-components.md`.

### Step 5 — Fill in every state (Law 9)
Write the empty state and the error state in the same commit as the happy path. Not later.

### Step 6 — Verify, don't assume
```bash
node scripts/check-ui.mjs
```
Then run the app and look at it — light and dark, 375px and 1440px. Screenshot the change.
**An unverified UI claim is an unsupported claim.**

### Step 7 — Gate
Walk `references/08-review-checklist.md`. Every line must pass or have a stated exception.

---

## Token quick reference

Full definitions are in `assets/tokens.css`. This is the working set you will reach for constantly.
Tailwind classes are shown because that is what you will actually type.

**Type** — `text-display text-title-1 text-title-2 text-title-3 text-headline text-body
text-callout text-subhead text-footnote text-caption-1 text-caption-2`
(Each already carries its correct weight, line-height, and tracking. Do not add `leading-*` or
`tracking-*` on top of them — the checker will catch you.)

**Text color** — `text-label` (primary), `text-label-secondary`, `text-label-tertiary`,
`text-label-quaternary`. Never `text-gray-*`.

**Surfaces** — `bg-canvas` (the page), `bg-surface` (cards), `bg-surface-secondary` (nested),
`bg-surface-elevated` (popovers), `bg-fill` / `bg-fill-secondary` / `bg-fill-tertiary` /
`bg-fill-quaternary` (control backgrounds).

**Lines** — `border-separator` for a row divider (decorative, deliberately faint);
`border-control` for the boundary of an actual control, which must hold 3:1.

**Accent and semantics** — `bg-accent` is the **fill** and pairs with `text-label-on-accent`;
`text-accent-text` is the same identity used as **words** on a surface. They are different tokens
because in dark mode no single color can both carry white text and read as text on `#1C1C1E`.
Same split for `success warning danger info ai`: `bg-{tone}` and `bg-{tone}-tint` for fills,
`text-{tone}-text` for words.

**Radius** — `rounded-xs`(6) `rounded-sm`(8) `rounded-md`(12) `rounded-lg`(16) `rounded-xl`(20)
`rounded-2xl`(24) `rounded-3xl`(32) `rounded-full`. Cards are `rounded-xl`. Buttons are
`rounded-md` or `rounded-full`. Icon tiles are `rounded-md`.

**Elevation** — `shadow-e1` (resting card) `shadow-e2` (raised) `shadow-e3` (popover)
`shadow-e4` (modal). Never `shadow-md` / `shadow-lg` / `shadow-xl`.

**Spacing** — the 4pt grid: `1`=4 `2`=8 `3`=12 `4`=16 `5`=20 `6`=24 `8`=32 `10`=40 `12`=48.
Screen edge margin is `px-4` on phone, `px-6` tablet, `px-8` desktop. Card padding is `p-4` or
`p-5`. Gap between cards is `gap-3`.

**Motion** — `duration-instant`(100) `duration-fast`(200) `duration-base`(300)
`duration-slow`(400), with `ease-standard` `ease-decelerate` `ease-accelerate` `ease-spring`
`ease-emphasis`.

**Materials** — `material-thin material-regular material-thick material-chrome` for translucent
chrome (tab bar, nav bar, sheets). Never plain `backdrop-blur-*`.

---

## What ships with this skill

| Path | What it is |
|---|---|
| `assets/tokens.css` | **The token layer.** Framework-neutral CSS custom properties, light + dark, materials, motion, user-preference handling, base utilities |
| `assets/tailwind.preset.js` | Maps every token to the class names used throughout these references |
| `assets/components.tsx` | **The reference implementation** of the component catalog. React + Tailwind; port the class strings and state logic if the project is Vue, Svelte, or plain CSS |
| `scripts/check-ui.mjs` | The checker. Lints source for the twelve mechanical rules; `--tokens` prints a WCAG contrast report |

## References — load what the task needs

| File | Load it when |
|---|---|
| `references/01-foundations.md` | Any visual decision: type, color, space, radius, elevation, material, layout grid |
| `references/02-motion.md` | Anything that moves, appears, disappears, or responds to touch |
| `references/03-components.md` | Building or editing any component; the full spec catalog |
| `references/04-interaction.md` | Touch/pointer/keyboard behavior, states, gestures, forms |
| `references/05-accessibility.md` | Always, but especially before claiming done |
| `references/06-writing.md` | Any user-visible string, including errors and empty states |
| `references/07-project-profile.md` | **First run in any project** — the profile template and a worked example |
| `references/08-review-checklist.md` | Before reporting any UI work as complete |

Related skills, where the environment has them: `dataviz` before building any chart (this one is
widely installed — use it, do not invent chart colors); `founder-mode` for the process that gates
this work at P6. A related skill that is not installed is not a blocker — this file plus
`assets/components.tsx` is self-sufficient for building the UI.

---

## The failure modes that give it away

These are the tells that separate an Apple-grade interface from a competent one. Check yourself
against them:

- **Shadow too dark and too tight.** Apple shadows are large, soft, and nearly invisible
  (8–24px blur, 4–10% opacity). A `0 4px 6px rgba(0,0,0,0.3)` reads as Material Design, not iOS.
- **Border where a shadow belongs.** Cards on a tinted canvas need elevation, not a 1px gray
  outline. Use hairlines only for *separators inside* a surface.
- **Uniform font weight.** Real hierarchy uses weight (600/700) and *color tier* together, not
  size alone. A screen where everything is 500-weight looks flat and cheap.
- **Text too dark.** Secondary text is not `#666`. It is `label-secondary` — an alpha of the label
  color, so it composites correctly on every surface.
- **Uniform corner radii.** A 12px radius on everything from a badge to a modal is a giveaway.
  Radius scales with the element's size (Law 8).
- **Icons at the wrong optical weight.** Stroke icons next to 17px text want 1.5–1.75px stroke at
  20–22px, not 2px at 24px. Icons should read as the same "ink density" as the adjacent text.
- **Animation that eases in.** Things entering the screen decelerate (`ease-decelerate`). Only
  things *leaving* accelerate. Getting this backwards feels subtly wrong to everyone and is
  identifiable by nobody.
- **Centered body text.** Center only single-line labels and empty states. Never a paragraph.
- **Full-width forms on desktop.** Readable measure is 60–75 characters. A text input that spans
  1400px is a bug.
- **Loading spinners for content.** Content loads into skeletons that match its final shape.
  Spinners are for indeterminate actions only.
- **Disabled buttons with no explanation.** If the primary action is disabled, the UI must say why,
  adjacent to it.

---

## Scope discipline

This skill makes UI excellent; it does not make UI *bigger*. Do not add features, screens, or
"delightful" flourishes nobody asked for. Restraint is the most Apple thing in this document:
the goal is that a user's eye goes exactly where it should and nowhere else. When in doubt, remove
something.
