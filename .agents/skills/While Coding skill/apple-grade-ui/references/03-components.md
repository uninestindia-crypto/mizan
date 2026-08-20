# Component catalog

Every component a product needs, specified to the token. These belong in the component package the
profile names. **Compose from these before writing raw markup.** If you write something new, add it
here and to the package so the next screen inherits it.

**A working implementation of this catalog ships with the skill** at `assets/components.tsx`.
Copy it in rather than rebuilding these specs from the tables below — the tables are the
specification, that file is the answer. This document is what you read when you need to extend it
or verify it.

Format: *anatomy → spec → states → rules*.

---

## Buttons

### Variants

| Variant | Background | Text | Use |
|---|---|---|---|
| `filled` | `bg-accent` | white | **The one** primary action on the screen |
| `filled-success` | `bg-success` | white | Award, approve, confirm — a positive commit |
| `filled-danger` | `bg-danger` | white | Destructive commit (after confirmation) |
| `tinted` | `bg-accent-tint` | `text-accent` | Secondary actions; the common case |
| `gray` | `bg-fill-tertiary` | `text-label` | Neutral alternative ("Cancel", "Save draft") |
| `plain` | transparent | `text-accent` | Inline/tertiary; toolbar actions |
| `outline` | transparent + `border-separator` | `text-label` | Paired alternative to a filled button |

### Sizes

| Size | Height | Padding-x | Text | Radius | Icon |
|---|---|---|---|---|---|
| `sm` | 32 | 12 | `text-footnote` 600 | `rounded-sm` | 16 |
| `md` | 44 | 16 | `text-callout` 600 | `rounded-md` | 20 |
| `lg` | 52 | 20 | `text-headline` 600 | `rounded-md` | 22 |
| `xl` | 56 | 24 | `text-headline` 700 | `rounded-lg` | 24 |

`md` is the default. `sm` still needs a 44px hit area — expand with a `::after` or wrapper padding.

### States
- **hover** (pointer only, `@media (hover:hover)`) — background darkens one step
- **active** — `scale(0.97)`, 100ms
- **focus-visible** — `ring-2 ring-accent ring-offset-2 ring-offset-canvas`
- **disabled** — `opacity-40`, `pointer-events-none`, `aria-disabled="true"`. **Say why nearby.**
- **loading** — spinner replaces the icon, label stays, width is locked (`min-width` captured
  before swap so the button doesn't resize), `aria-busy="true"`

### Rules
- Label is a **verb phrase describing the outcome**: "Send to 23 vendors", "Approve and record".
  Never "Submit", "OK", "Confirm" alone.
- Exactly one `filled` per screen viewport (Law 3).
- Full-width buttons only in sheets, forms, and phone-width primary actions. On desktop a
  full-width button reads as unfinished.
- Paired buttons: destructive/cancel on the **left**, confirming on the **right**. Equal widths
  when both are equally likely; the primary gets more width when it isn't.
- Icons sit **before** the label for actions, **after** for navigation/progression (`→`).

---

## Cards

### Standard card
```
bg-surface · rounded-xl (20) · p-4 or p-5 · shadow-e1 · no border in light mode
dark: bg-surface + border border-separator/40 (shadows don't read on black)
```
The default container for everything. On a tinted canvas it needs elevation, **not** a border
(a border plus a shadow reads as a 2010 web app).

### Hero card (deep surface)
```
bg-deep · rounded-2xl (24) · p-5 · text-label-on-accent (white)
optional: a subtle radial gradient or line-art motif at 6–10% opacity in the trailing area
```
Used for the single most important number on the screen, or the entry point to the product's one
headline capability. **One per screen, maximum** — a second hero card means neither is the hero.
`--brand-deep` comes from the profile's brand block. A product with no hero treatment sets it equal
to `--surface` and uses a standard card with a `text-title-1` value instead.

### Stat card
```
bg-surface · rounded-lg (16) · p-4 · shadow-e1
├─ icon tile: 36×36 rounded-md bg-{tone}-tint, glyph 18px text-{tone}
├─ value:     text-title-2 (22/700) tabular-nums, text-label
├─ label:     text-subhead text-label-secondary
└─ optional progress bar: h-1.5 rounded-full bg-fill-quaternary + bg-{tone} fill
```
Grid: 3-up on phone for compact stats, 2-up when values are long (currency). Never 4-up below
768px.

### Interactive card
Add: `cursor-pointer`, `active:scale-[0.98]`, `transition-transform duration-instant`, and on
pointer devices `hover:shadow-e2`. Must be a real `<button>` or `<a>`, never a `<div onClick>`.

### Rules
- Card padding is uniform (`p-4`) unless the card contains full-bleed media or a list, in which
  case padding goes on the *inner* elements and the media/rows go edge to edge.
- Concentric radii inside (Law 8): a `rounded-xl` card with `p-4` holds `rounded-sm` children.
- Never nest a shadowed card inside a shadowed card. The inner one uses `bg-surface-secondary`
  with no shadow.

---

## List rows

The workhorse. Most screens in most products are a list of rows.

```
min-h-[56px] · px-4 · py-3 · flex items-center gap-3
├─ leading:  icon tile (40×40) | avatar (40) | thumbnail (48×48 rounded-lg)
├─ content:  title    text-headline text-label
│            subtitle text-subhead text-label-secondary  (max 1–2 lines, truncate)
└─ trailing: value | badge | chevron (16px text-label-tertiary) | button
separator: hairline, inset to align with the content start (not the card edge)
```

**Density variants:** `compact` (48px, `text-callout` title), `default` (56px), `comfortable`
(72px, two-line subtitle + metadata).

### Rules
- **The separator inset matters.** It starts where the *text* starts, not at the card edge — this
  is the single detail that makes a list look iOS-native. Last row has no separator.
- A chevron means "navigates to a new screen". Never put one on a row that expands in place
  (use a rotating disclosure caret) or does nothing.
- The whole row is the target, not just the title.
- Two-line truncation: `line-clamp-2`. Truncating an identifier (a person's name, an order number)
  is a bug — wrap it or shorten it upstream.

---

## Badges / pills

```
h-6 (24) or h-7 (28) · px-2.5 · rounded-full
text-caption-1 (12/500)
bg-{tone}-tint · text-{tone}
optional leading dot (6px) or glyph (12px)
```

Map your product's statuses onto these six tones **once**, in the profile, and never re-decide it
per screen. The tone carries the meaning; the words are yours.

| Tone | What it must mean, in any product |
|---|---|
| success | The thing completed, or is confirmed good: verified, delivered, approved, on time |
| warning | Needs attention but nothing is broken yet: pending, delayed, awaiting approval |
| danger | Broken, lost, or past a hard deadline: failed, disputed, overdue, critical |
| info / accent | Neutral emphasis — a fact worth noticing that is neither good nor bad: live, new |
| ai | Content a model produced or suggested. Never used for anything else |
| neutral (`bg-fill-tertiary` / `text-label-secondary`) | Inactive or out of the flow: draft, archived |

A status that doesn't fit one of these six is usually two statuses wearing one label. Split it.

**Rules**
- Badges **state a fact**, never an action. If it's tappable it's a chip or a button.
- Text is a noun or adjective, 1–3 words, sentence case.
- Never a saturated solid fill — tint only. The exception is a critical count badge on an icon
  (`bg-danger text-white`), which is a notification, not a status.
- A "Live" badge gets a pulsing dot; that's the only badge permitted to animate.

---

## Segmented control

```
container: h-9 (36) or h-11 (44) · p-1 · rounded-full · bg-fill-secondary
segment:   flex-1 · rounded-full · text-footnote 600
selected:  bg-surface · text-label · shadow-e1
unselected: text-label-secondary
indicator slides: transform 250ms ease-spring
```
2–4 segments only. Five means you need a filter sheet or a scrollable chip row instead. Labels are
one word where possible ("Overview / Materials / Crew / Finance").

## Filter chips (scrollable row)

```
h-9 · px-4 · rounded-full · text-footnote 600 · whitespace-nowrap
unselected: bg-surface text-label-secondary shadow-e1
selected:   bg-accent text-white   (or bg-{tone}-tint text-{tone} for tone-coded filters)
row: flex gap-2 overflow-x-auto, edge-to-edge with px-4 scroll padding, scrollbar hidden
```
Fade the trailing edge with a mask so it's obvious more chips exist off-screen.

---

## Tab bar (primary navigation)

Usually the defining element of a phone-first product. **Three to five** top-level destinations,
named in the profile — they are the product's information architecture, and this component only
renders them.

```
fixed bottom-0 inset-x-0 z-50
material-chrome + glass-edge · border-t border-separator/60
h-[52px] + env(safe-area-inset-bottom) padding
item: flex-1 flex-col items-center justify-center gap-1 min-h-[48px]
  icon:  24px — outline when unselected, filled when selected
  label: text-caption-1 (12/500)
  selected:   text-accent, icon filled, optional bg-accent-tint pill behind the icon
  unselected: text-label-secondary
```

**Rules**
- **Three to five items, never more.** Five is the maximum a thumb can target reliably at this
  width. If the product has a sixth top-level area, the fifth slot becomes "More" — it does not
  become a sixth tab.
- Every item is a *destination*, never an action. A "+" that opens a compose sheet belongs in the
  nav bar or as a floating button, not in the tab bar.
- Selection animates with `scale(1 → 1.12 → 1)` over 300ms `ease-spring`.
- Must respect `env(safe-area-inset-bottom)` or it sits under the home indicator.
- Content needs `pb-[calc(52px+env(safe-area-inset-bottom)+16px)]` so the last item clears it.
- On ≥1024px the tab bar is replaced by the sidebar — **the same top-level destinations**, in the
  same order, with the same labels. Never a different IA between breakpoints.

---

## Navigation bar / large title header

```
Large (at scroll top):
  px-4 pt-3 pb-4
  title:    text-display (34/700)
  subtitle: text-subhead text-label-secondary
  trailing: badge or icon button

Collapsed (after ~40px scroll):
  sticky top-0 · h-11 (44) · material-chrome · border-b border-separator
  title: text-headline, centered
  back:  chevron + previous screen's title, leading
  transition: 200ms ease-standard, driven by scroll position
```
The large-title collapse is a signature iOS behavior. Implement it with an `IntersectionObserver`
sentinel, not a scroll listener (scroll listeners on the main thread cause jank on Android).

Back button: a chevron plus **the previous screen's title**, not the word "Back". If the title is
too long, then "Back".

---

## Search field

```
h-11 (44) · px-4 · rounded-md (12) · bg-fill-tertiary · no border
leading icon 18px text-label-tertiary · gap-2.5
input: text-body · placeholder text-label-tertiary
trailing: clear (×) when non-empty, filter glyph if applicable
focus: ring-2 ring-accent/30, background lightens to bg-surface
```
Debounce input by 300ms. Show results inline; never navigate away to a results page on a phone.
Empty results get an empty state, not a blank area.

---

## Form fields

```
label: text-caption-1 (12/500) text-label-secondary, mb-1.5
field: min-h-12 (48) · px-3.5 · rounded-md (12) · bg-fill-tertiary
       text-body text-label
       trailing icon tile: 28×28 rounded-sm bg-accent-tint, glyph 16px text-accent
help:  text-footnote text-label-secondary, mt-1.5
error: text-footnote text-danger, mt-1.5, with a 14px warning glyph
```

**Rules**
- **Labels are always visible.** Placeholder-as-label is an accessibility failure — it disappears
  exactly when the user needs it, and it fails for screen readers.
- Group related fields in one `surface` card with hairline separators between them, rather than as
  loose stacked boxes. A form that reads as one grouped card is calmer than six floating inputs.
- Correct `inputmode` / `type` / `autocomplete` on every field. A phone number field that opens a
  QWERTY keyboard is a defect.
- Validate on **blur**, not on every keystroke. Re-validate on change only *after* the field has
  errored once.
- Errors appear below the field, are announced (`aria-describedby` + `role="alert"`), and the
  field gets `aria-invalid="true"` and a `border-danger`.
- Never disable the submit button to enforce validation. Let the user submit and show them what's
  wrong — a disabled button with no explanation is a dead end.
- Required fields: mark the **optional** ones instead if most are required. Less visual noise.

---

## Progress

### Linear bar
```
track: h-1.5 rounded-full bg-fill-quaternary
fill:  h-full rounded-full bg-{tone}, transform: scaleX(), origin-left
       600ms ease-emphasis
```
Tone follows the value's meaning: success ≥80%, accent 40–79%, warning 20–39%, danger <20% — but
only where "higher is better". For risk scores, invert.

### Stepper (numbered flow)
```
step circle: 32×32 rounded-full
  done:    bg-accent text-white with a check glyph
  current: bg-accent text-white with the number, + 4px ring ring-accent/20
  upcoming: border border-separator text-label-tertiary
connector: 1px dashed separator (solid accent when the step is complete)
label: text-caption-1, current is text-accent 600, others text-label-secondary
```

### Timeline (PO / delivery tracking)
```
node: 28×28 rounded-full
  complete: bg-success + check glyph, connector before it is solid success
  current:  bg-accent + the step's glyph, with a soft ring
  upcoming: bg-fill-tertiary, connector is separator
label below: text-footnote 600 · timestamp text-caption-1 text-label-tertiary
```
Horizontal on phone when ≤5 steps; vertical when more or when each step has detail.

### Circular / indeterminate
Only for actions, never content. 20px stroke-2, `text-accent`, rotating 1s linear infinite. Under
reduced motion, replace with a pulsing opacity.

---

## Alert cards (Alerts Center pattern)

```
rounded-xl · p-4 · bg-{tone}-tint (very light) · border-l-4 border-{tone}
├─ icon tile 44×44 rounded-md bg-{tone} with a white glyph
├─ eyebrow:   text-caption-2 uppercase text-{tone}
├─ title:     text-headline text-label
├─ detail:    text-subhead text-label-secondary
├─ timestamp: text-caption-1 text-label-tertiary, trailing
└─ actions:   two buttons — tinted (secondary) then filled-{tone} (primary)
```
Severity order: `danger` (Critical) → `warning` (Caution) → `accent` (Action required) →
`success` (Information). Sort by severity, then recency.

---

## Sheets & modals

```
Sheet (phone default):
  rounded-t-3xl (32) · bg-surface · shadow-e4
  grabber: 36×5 rounded-full bg-fill at top center, mt-2
  enter: translateY(100%→0) 400ms ease-decelerate
  detents: medium (50vh) and large (92vh); drag between them
  backdrop: bg-black/25, tap to dismiss

Modal (desktop ≥768px):
  centered · max-w-[520px] · rounded-2xl · shadow-e4
  enter: scale(0.96→1) + opacity 250ms ease-decelerate
```
- Focus traps inside; `Esc` closes; focus returns to the trigger on close.
- The page behind must not scroll (`overflow: hidden` on body, and preserve scroll position).
- Destructive confirmations name the specific thing: "Delete order #1042?" not "Are you sure?".
- Never a modal inside a modal. Never a modal for something that could be a page.

---

## Toast / snackbar

```
fixed bottom (above the tab bar) · mx-4 · max-w-[420px]
rounded-lg · p-3.5 · material-thick · shadow-e3
leading glyph 20px text-{tone} · message text-subhead · optional action text-accent 600
auto-dismiss 4s (8s with an action) · swipe to dismiss
```
For confirmations and recoverable errors. Never for anything the user must act on — that's a
sheet. Stack at most 3; collapse the rest into "+2 more".

---

## Empty states

```
py-16 · text-center · max-w-[320px] mx-auto
├─ glyph: 48px text-label-tertiary (or a simple illustration at ≤40% opacity)
├─ title: text-title-3 text-label
├─ body:  text-subhead text-label-secondary
└─ action: one tinted or filled button
```
Three flavors, and they are **not** interchangeable:
- **Nothing yet** — encouraging, with the action that creates the first item.
- **No results** — states the active filter and offers to clear it.
- **Error** — says what failed, offers Retry, and never blames the user.

An empty area with no explanation is always a bug.

---

## Skeletons

```
bg-fill-quaternary · rounded-sm · animate-shimmer
shimmer: a 1.5s linear-infinite gradient sweep (disabled under reduced motion → static fill)
```
**Match the real content's dimensions exactly**, or the page jumps when data lands — which is
worse than showing nothing. Skeleton text lines are 12–14px tall with the last line at 60% width.

---

## Data tables (desktop) → cards (phone)

Below 768px a table becomes a stacked list of cards; each row's columns become label/value pairs.
Never a horizontally scrolling table on a phone.

```
Desktop table:
  header: text-caption-1 600 text-label-secondary, sticky, bg-surface, border-b separator
  cell:   text-callout, py-3, numbers tabular-nums and right-aligned
  row hover: bg-fill-quaternary
  zebra: no — use hairlines
```
Sortable headers get a direction glyph and `aria-sort`. Selection uses a leading checkbox column
with a header select-all that reflects the indeterminate state.

---

## Charts

Load the `dataviz` skill before building any chart. Token bindings on top of it:

- Line charts: 2px stroke `accent`, 4px dots at data points only when there are ≤12 points, a soft
  gradient fill beneath at 12% → 0% opacity.
- Axis labels `text-caption-1 text-label-tertiary`; gridlines `separator` at 40% opacity,
  horizontal only.
- Currency axes state the unit once in the corner ("$ in millions") rather than repeating it on
  every tick.
- Every chart needs a text alternative — a caption stating the takeaway, and a
  `<table class="sr-only">` with the underlying values.

---

## Avatars & identity

```
sizes: 28 (dense) · 40 (list) · 56 (header) · 96 (profile)
rounded-full · bg-accent-tint · initials text-accent 600 (uppercase, 2 chars max)
verified: 16px success check badge, bottom-trailing, with a 2px surface-colored ring
group: overlap by 40% with a surface-colored ring on each; cap at 3 + "+N"
```

---

## The AI surface

Skip this section if the product has no AI features. Where it does, AI-produced content is always
visually marked. Non-negotiable — it's a trust requirement, not styling.

- **Entry point** — the deep hero card with a sparkle glyph, one per screen at most.
- **Inline suggestion** — `bg-ai-tint`, a 16px sparkle, `text-subhead`, with the model's reasoning
  one tap away.
- **The `ai` tone means "a model made this" and nothing else.** The moment it also means "premium"
  or "new", the user can no longer tell what came from a model, and the affordance is dead.
- **Confidence** — always shown as a number when the model extracted data ("94% confidence"), with
  low-confidence fields individually flagged for review.
- **Every AI action is reviewable before it executes.** A Review / Confirm step between the model's
  output and any state change — never an AI action that fires without human confirmation.
- **Score breakdowns are itemized** (each component and its weight), plus a plain-language
  justification. A score with no breakdown is not shippable.
