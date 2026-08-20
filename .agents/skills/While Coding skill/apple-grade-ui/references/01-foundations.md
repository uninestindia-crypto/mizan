# Foundations — type, color, space, shape, depth

Everything visual resolves to one of six systems. Learn these and most design decisions stop being
decisions.

**Every value in this file is already implemented in `assets/tokens.css`.** Read this file to
understand *why* a value is what it is; copy that file to *get* the values. Never retype a table
from here into a project — copy the token file and edit only its `BRAND` block.

---

## 1. The grid

Apple's interfaces resolve to a **4pt base grid**, with 8pt as the dominant rhythm. Every gap,
padding, and offset is a multiple of 4.

| Token | px | Use |
|---|---|---|
| `0.5` | 2 | Hairline offsets, optical nudges only |
| `1` | 4 | Icon-to-label in a dense chip |
| `2` | 8 | Inside a control; between a label and its value |
| `3` | 12 | Between sibling cards; list row vertical padding |
| `4` | 16 | Card padding; screen edge margin on phone |
| `5` | 20 | Generous card padding |
| `6` | 24 | Section gap; screen edge margin on tablet |
| `8` | 32 | Major section break; screen margin on desktop |
| `10` | 40 | Above a page's first section |
| `12` | 48 | Between unrelated regions |
| `16` | 64 | Empty-state vertical breathing room |

**Screen margins** — `px-4` (phone, 375–767) → `px-6` (tablet, 768–1023) → `px-8` (desktop, 1024+).
Content inside a centered container maxes at `max-w-[1120px]`.

**Readable measure** — body paragraphs cap at **60–75 characters** (`max-w-[68ch]`). Form fields
cap at `max-w-[520px]` unless the field genuinely holds long content (address, notes).

**Vertical rhythm** — the space *above* a heading is always larger than the space below it. A
section title has `mt-8 mb-3`. This is what makes a long page scannable.

---

## 2. Typography

### 2.1 The font stack

```css
font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
             "Inter var", Inter, "Segoe UI Variable", "Segoe UI", Roboto,
             "Helvetica Neue", Arial, sans-serif;
```

**Why `-apple-system` first and not a webfont:** on iPhone, iPad, and Mac this resolves to real
**SF Pro**, with Apple's optical sizing, real Dynamic Type metrics, and correct tracking — the
genuine article, zero bytes downloaded, zero layout shift. SF Pro's license does not permit
serving it as a webfont, and shipping a lookalike to Apple devices would be *worse* than the real
font. Inter is the fallback for Windows/Android/Linux because its metrics are the closest
available match (same x-height ratio, near-identical cap height), so the layout does not reflow
across platforms.

**Numerals:** use `font-variant-numeric: tabular-nums` on anything that updates in place or sits in
a column — prices, counts, percentages, timers, table cells. Use proportional (default) for
numbers inside running prose. Tabular numerals prevent the horizontal jitter that instantly reads
as amateur.

```css
.tabular { font-variant-numeric: tabular-nums; font-feature-settings: 'tnum' 1; }
```

### 2.2 The scale

Apple's stock iOS Dynamic Type at the default (Large) content size:

| Text style | Size | Stock weight | Line height | Tracking |
|---|---|---|---|---|
| Large Title | 34 | Regular | 41 | +0.37 |
| Title 1 | 28 | Regular | 34 | +0.36 |
| Title 2 | 22 | Regular | 28 | +0.35 |
| Title 3 | 20 | Regular | 25 | +0.38 |
| Headline | 17 | **Semibold** | 22 | −0.41 |
| Body | 17 | Regular | 22 | −0.41 |
| Callout | 16 | Regular | 21 | −0.32 |
| Subheadline | 15 | Regular | 20 | −0.24 |
| Footnote | 13 | Regular | 18 | −0.08 |
| Caption 1 | 12 | Regular | 16 | 0 |
| Caption 2 | 11 | Regular | 13 | +0.06 |

Note the tracking sign flip: **negative above ~13pt, positive below**. Small text needs air; large
text needs tightening. This single detail is most of why hand-rolled type scales look wrong.

### 2.3 The applied scale

The shipped scale uses **bold display titles** — matching iOS system apps like Settings, Mail, and
Health, which override the stock Regular large title with Bold. These are the eleven classes you
may use, and they are the only eleven:

| Class | Size/LH | Weight | Tracking | Use |
|---|---|---|---|---|
| `text-display` | 34/40 | 700 | −0.4px | Screen title |
| `text-title-1` | 28/34 | 700 | −0.5px | Hero numerals, section-page titles |
| `text-title-2` | 22/28 | 700 | −0.4px | Card group headings |
| `text-title-3` | 20/25 | 600 | −0.3px | Card titles, modal titles |
| `text-headline` | 17/22 | 600 | −0.2px | List row primary text, emphasized body |
| `text-body` | 17/24 | 400 | −0.2px | Paragraphs, field values |
| `text-callout` | 16/21 | 400 | −0.2px | Secondary body, dense list rows |
| `text-subhead` | 15/20 | 400 | −0.1px | Row subtitles, helper text |
| `text-footnote` | 13/18 | 400 | 0 | Metadata, timestamps, captions under charts |
| `text-caption-1` | 12/16 | 500 | +0.1px | Badge text, field labels, tab bar labels |
| `text-caption-2` | 11/14 | 600 | +0.4px | Overline/eyebrow labels (uppercase) |

**Rules:**
- These classes already carry weight, line-height, and tracking. **Never** add `leading-*` or
  `tracking-*` on top. If you need a different line-height, the string is the wrong style.
- Weight may be raised one step for emphasis (`font-semibold` on `text-body`), never lowered.
- Uppercase is permitted **only** on `text-caption-2`, and always with its positive tracking.
  Uppercasing anything larger is a 2014 dashboard tell.
- Minimum readable size anywhere in the product is **11px**. No exceptions, including legal text.
- Never more than **three** distinct styles visible in one card. Four means the card is doing too
  much.

### 2.4 Dynamic Type / user zoom

Never set font sizes in `px` at the root. The scale above is defined in `rem` against a 16px root,
so browser zoom and OS text-size settings scale it. Do not disable zoom
(`user-scalable=no` is banned). Layouts must survive 200% text scaling without clipping — use
`min-height` not `height`, and let text wrap rather than truncate wherever the string is meaningful.

---

## 3. Color

### 3.1 Two tiers

The token layer has two levels and you should almost always use the second:

- **`--sys-*`** — Apple's system palette, reproduced for reference. The truth you derive from.
- **Semantic tokens** (`--label`, `--surface`, `--accent`, `--danger`, …) — meaning mapped onto that
  structure. **This is what you use in components.**

Never reach past a semantic token to a raw system color, and never past a system color to a hex.
The rule exists because semantics survive a theme change and hexes do not: `bg-surface` is correct
in light and dark; `bg-gray-6` is correct in exactly one of them.

### 3.2 Apple system palette (verbatim)

Community-measured from the OS; Apple does not publish guaranteed hex values because the rendered
color depends on the trait environment. Treat these as accurate-to-render, not contractual.

| Color | Light | Dark |
|---|---|---|
| systemBlue | `#007AFF` | `#0A84FF` |
| systemGreen | `#34C759` | `#30D158` |
| systemIndigo | `#5856D6` | `#5E5CE6` |
| systemOrange | `#FF9500` | `#FF9F0A` |
| systemPink | `#FF2D55` | `#FF375F` |
| systemPurple | `#AF52DE` | `#BF5AF2` |
| systemRed | `#FF3B30` | `#FF453A` |
| systemTeal | `#5AC8FA` | `#64D2FF` |
| systemYellow | `#FFCC00` | `#FFD60A` |
| systemGray | `#8E8E93` | `#8E8E93` |
| systemGray2 | `#AEAEB2` | `#636366` |
| systemGray3 | `#C7C7CC` | `#48484A` |
| systemGray4 | `#D1D1D6` | `#3A3A3C` |
| systemGray5 | `#E5E5EA` | `#2C2C2E` |
| systemGray6 | `#F2F2F7` | `#1C1C1E` |

Note the gray ramp **inverts** between modes — gray6 is the lightest in light mode and the darkest
in dark mode. This is why you must use semantic tokens: `bg-surface` is correct in both, `bg-gray-6`
is correct in one.

### 3.3 Label tiers (text)

Text color is **alpha over the background**, not a fixed gray. This is critical: it means text
composites correctly on white, on a tinted card, and on a material.

| Token | Light | Dark | Measured on `surface` | Use |
|---|---|---|---|---|
| `label` | `#000000` | `#FFFFFF` | 21.0 / 17.0 | Primary text, headings, values |
| `label-secondary` | `rgba(60,60,67,0.75)` | `rgba(235,235,245,0.60)` | 5.16 / 5.95 | Subtitles, descriptions |
| `label-tertiary` | `rgba(60,60,67,0.30)` | `rgba(235,235,245,0.30)` | 1.73 / 2.48 | Placeholders, disabled |
| `label-quaternary` | `rgba(60,60,67,0.18)` | `rgba(235,235,245,0.16)` | — | Decorative glyphs only |

**Why light `label-secondary` is 0.75 and not Apple's 0.60.** Apple's own `secondaryLabel` is 60%
alpha, which measures **3.44:1 on white** and therefore fails WCAG AA for body text. Law 5 says
contrast floors are hard floors, and a documented Apple value does not outrank a user who cannot
read the text — so the shipped token is 75% (5.16:1) and still reads as clearly secondary. Dark
mode keeps 0.60 because it already measures 5.95:1 there; the asymmetry is the measurement, not an
oversight.

**Contrast note:** `label-tertiary` at 30% fails 4.5:1 by design. It is legal only for genuinely
non-essential text — a placeholder that duplicates a visible label, a decorative glyph. If a user
must read it, it is `label-secondary` or higher.

Every number in the table above comes from `node scripts/check-ui.mjs --tokens assets/tokens.css`.
Re-run it after any palette change rather than trusting this table.

### 3.4 Backgrounds and fills

The shipped tokens use the **grouped** background style — cards floating on a tinted canvas, the
style iOS Settings and Health use. The alternative, *plain* (content directly on a white page), is
a legitimate choice for text-heavy reading surfaces; if you pick it, set `--canvas` equal to
`--surface` and rely on hairlines rather than elevation. Pick one per product and record it in the
profile. Mixing them within a product is the fastest way to make an interface feel assembled from
two different apps.

| Token | Light | Dark | Use |
|---|---|---|---|
| `canvas` | `#F2F4F8` | `#000000` | The page behind everything |
| `surface` | `#FFFFFF` | `#1C1C1E` | Cards, sheets, list containers |
| `surface-secondary` | `#F2F4F8` | `#2C2C2E` | Nested panel inside a card |
| `surface-elevated` | `#FFFFFF` | `#2C2C2E` | Popovers, menus, modals |
| `fill` | `rgba(120,120,128,0.20)` | `rgba(120,120,128,0.36)` | Large control backgrounds |
| `fill-secondary` | `rgba(120,120,128,0.16)` | `rgba(120,120,128,0.32)` | Segmented control track |
| `fill-tertiary` | `rgba(118,118,128,0.12)` | `rgba(118,118,128,0.24)` | Input field, search bar |
| `fill-quaternary` | `rgba(116,116,128,0.08)` | `rgba(118,118,128,0.18)` | Subtle zebra, progress track |
| `separator` | `rgba(60,60,67,0.29)` | `rgba(84,84,88,0.60)` | Hairline between rows |
| `separator-opaque` | `#C6C6C8` | `#38383A` | Full-bleed divider |
| `border-control` | `rgba(60,60,67,0.60)` | `rgba(235,235,245,0.45)` | The boundary of an actual control |

**Separator vs. border-control — do not mix these up.** A row divider is decorative: the rows are
also separated by spacing, so the line is not the only cue and the 3:1 floor does not apply. The
boundary of a *control* — an input, a checkbox, an unselected segment — does carry meaning, and it
must hold 3:1. That is why they are two tokens. Using `separator` on an input border is a real
accessibility failure that looks like a styling preference.

Fills are **translucent by design** — they pick up whatever is behind them, so the same token works
on white and on a tinted card. Never substitute a solid gray.

**Hairlines:** a separator is `1px` at 1× but should be a true hairline on retina. Use
`border-width: 0.5px` guarded by a `min-resolution: 2dppx` media query, or the `.hairline` utility.

### 3.5 Brand and semantic tones

The shipped defaults, mapped onto the Apple structure. Change the accent in the token file's
`BRAND` block; leave the semantic tones alone unless the product has a real reason.

| Token | Light | Dark | Meaning |
|---|---|---|---|
| `accent` | `#0A5AFF` | `#1F6FEB` | **Fill** — filled buttons, selected state, behind white text |
| `accent-text` | `#0A5AFF` | `#0A84FF` | **Words** — links, accent labels on a surface |
| `accent-strong` | `#0344CC` | `#4DA2FF` | Pointer hover / pressed |
| `accent-tint` | 10% of accent | 18% of accent | Tinted button, selected chip |
| `deep` | `#0A1B3D` | `#0F2247` | Hero / feature card surfaces (optional) |
| `success` | `#12A150` | `#30D158` | Verified, on time, approved |
| `warning` | `#F08C00` | `#FF9F0A` | Caution, pending, at risk, delayed |
| `danger` | `#E5342A` | `#FF453A` | Critical, failed, disputed, destructive |
| `info` | `#0A5AFF` | `#3D8BFF` | Neutral informational |
| `ai` | `#5856D6` | `#5E5CE6` | Model-generated / model-suggested content only |

Each tone also has a `-text` variant and a `-tint` companion at 10% (light) / 18% (dark) for badge
and icon-tile backgrounds.

**Why `accent` and `accent-text` are two tokens — this is arithmetic, not taste.** In dark mode,
white text on the accent needs the accent to be *dark enough* (luminance ≤ 0.183 for 4.5:1), while
accent text on a `#1C1C1E` surface needs it *light enough* (luminance ≥ 0.228). Those ranges do not
overlap. No single color can do both jobs at AA, so the fill and the text are separate tokens.
Every design system that measures its contrast ends up here; the ones that do not simply ship the
failure. Run the contrast report and you will see both pass.

**The `-text` variants exist for the same reason at the small end.** Raw orange on a light surface
measures around 2.6:1 — it can never be small text. Use `bg-warning` for the fill or glyph and
`text-warning-text` for the words. Same for success, danger, info, and ai.

**The AI color rule:** indigo/violet is reserved for content a model produced or suggested — model
picks, inferred fields, confidence scores, the assistant entry point. Never use it decoratively.
When a user sees indigo they should know a model was involved. This is a trust affordance, not a
palette choice.

### 3.6 Using color correctly

- **Status is never color alone** (Law 5). "Delayed" is orange *and* says "Delayed" *and* has a
  clock glyph. Roughly 1 in 12 men cannot distinguish your red from your green.
- **Tint, don't fill.** A status badge is `bg-{tone}-tint` + `text-{tone}`, not a saturated solid.
  Solid fills are reserved for the single primary action and for critical alerts.
- **One accent per screen.** If three things are blue and prominent, none of them are primary.
- **Dark mode is not an inversion.** Surfaces get *lighter* as they get closer to the user
  (`#1C1C1E` → `#2C2C2E` → `#3A3A3C`), the opposite of light mode's shadow-based depth. Saturated
  colors must be *desaturated and brightened* in dark mode or they vibrate against black — that is
  exactly what the dark column of every table above does.
- **Never pure black text on pure white** at body size for long reading. `label` is `#000` because
  it's used sparingly and at weight; running prose sits at `label` on `surface` which is fine, but
  a wall of `#000` on `#FFF` is fatiguing.

---

## 4. Shape

### 4.1 The radius scale

| Token | px | Use |
|---|---|---|
| `rounded-xs` | 6 | Badges, tags, tiny chips |
| `rounded-sm` | 8 | Inner elements inside a padded card |
| `rounded-md` | 12 | Buttons, inputs, icon tiles |
| `rounded-lg` | 16 | Small cards, list containers, images |
| `rounded-xl` | 20 | **Standard card** — the default |
| `rounded-2xl` | 24 | Hero cards, sheets, modals |
| `rounded-3xl` | 32 | Full-screen sheet top corners |
| `rounded-full` | 9999 | Pills, avatars, FABs, segmented controls |

### 4.2 Concentricity (Law 8)

When one rounded shape sits inside another:

```
inner_radius = outer_radius − padding
```

A `rounded-xl` (20) card with `p-3` (12) padding holds a `rounded-sm` (8) child. Get this wrong and
the gap between the two curves visibly pinches or bulges — the eye catches it even when the mind
doesn't. iOS 26 exposes this as `.containerConcentric`; on the web you do the arithmetic.

If `outer − padding` would go below 4, use a square inner element instead. A 3px radius reads as a
rendering artifact.

### 4.3 Continuous corners (the squircle)

Apple uses a **superellipse**, not a circular arc — the curvature ramps in smoothly rather than
starting abruptly at the tangent point. CSS `border-radius` gives you the circular arc.

- For most elements the difference is imperceptible; use `border-radius` and move on.
- It becomes visible at **large radii on large shapes** — hero cards, app-icon-like marks, anything
  over ~24px radius at over ~200px wide. There, the circular arc looks slightly "pinched".
- CSS has no primitive for a true continuous corner, and every mask-based emulation distorts on
  non-square elements. Do not hand-roll superellipse math inline. If a project genuinely needs the
  exact curve, render it as an SVG asset.
- App-icon-shaped marks (a logo tile on a splash or install screen) use the `.icon-shape` utility
  shipped in `assets/tokens.css`: radius = **22.37%** of the side length, which is Apple's current
  icon shape ratio. Being a percentage, it stays correct at every size.

### 4.4 Shape conveys affordance

- **Pill** (`rounded-full`) — filters, chips, toggles, status. Reads as "selectable, ephemeral".
- **Rounded rect** (`rounded-md`) — buttons and inputs. Reads as "committed action".
- **Card** (`rounded-xl`) — a container of related content. Reads as "an object".
- **Circle** — identity (avatar) or a single-purpose control (FAB, radio).

Don't mix: a pill-shaped primary submit button next to a rounded-rect one is visual noise.

---

## 5. Depth

### 5.1 The elevation ladder

Apple shadows are **large, soft, and nearly invisible**. The single most common mistake is a
shadow that is too dark and too tight.

| Token | Value | Use |
|---|---|---|
| `shadow-e0` | `none` | Flush content, list rows inside a card |
| `shadow-e1` | `0 1px 2px rgba(16,24,40,.04), 0 4px 12px rgba(16,24,40,.06)` | Resting card |
| `shadow-e2` | `0 2px 4px rgba(16,24,40,.04), 0 8px 24px rgba(16,24,40,.08)` | Raised / hovered card, sticky bar |
| `shadow-e3` | `0 4px 8px rgba(16,24,40,.05), 0 16px 40px rgba(16,24,40,.12)` | Popover, dropdown, toast |
| `shadow-e4` | `0 8px 16px rgba(16,24,40,.06), 0 32px 64px rgba(16,24,40,.16)` | Modal, sheet |

Two layers each: a tight one for the contact edge, a wide one for the ambient falloff. That
two-layer construction is what makes it read as light rather than as a gray rectangle.

The shadow color is a desaturated navy (`16,24,40`), not black. Pure-black shadows go muddy over
tinted canvases.

**Dark mode:** shadows barely work on black. Depth comes from **surface lightness** instead —
`#1C1C1E` → `#2C2C2E` → `#3A3A3C` as elements come forward. Keep a much-reduced shadow (opacity
~0.4 of the light value) for the contact edge only, and add a `1px` top inner highlight
(`inset 0 1px 0 rgba(255,255,255,0.04)`) on elevated surfaces.

### 5.2 Materials (translucency)

Materials blur and tint what's behind them. Used for **chrome that floats over content**: tab bars,
nav bars, sheets, popovers.

| Token | Blur | Light tint | Dark tint |
|---|---|---|---|
| `material-thin` | 20px | `rgba(255,255,255,0.72)` | `rgba(30,30,32,0.72)` |
| `material-regular` | 30px | `rgba(255,255,255,0.82)` | `rgba(30,30,32,0.82)` |
| `material-thick` | 40px | `rgba(255,255,255,0.92)` | `rgba(30,30,32,0.92)` |
| `material-chrome` | 30px | `rgba(246,246,248,0.86)` | `rgba(20,20,22,0.86)` |

Each also carries `backdrop-filter: saturate(180%)` — the saturation boost is what makes iOS
translucency look alive rather than like a gray wash.

**Rules:**
- Material is for **chrome only**. Never put content on a material; put content on `surface`.
- **Material never stacks on material.** A blurred popover inside a blurred sheet turns to mud.
  One layer of translucency per stacking context.
- Always provide the opaque fallback: `@supports not (backdrop-filter: blur(1px))` → solid
  `surface` at full opacity.
- Under `prefers-reduced-transparency: reduce`, collapse every material to its opaque equivalent.
- Text on a material needs its own contrast check against the *worst-case* content behind it. If
  you can't guarantee it, use `material-thick` or a solid surface.

### 5.3 Liquid Glass (iOS 26)

Apple's current design language renders navigation-layer chrome as a refractive glass material with
specular highlights and light bending at the edges. The web equivalent shipped here is the
`material-*` tokens plus the `.glass-edge` utility, which adds the characteristic 1px light rim:

```css
box-shadow: inset 0 1px 0 rgba(255,255,255,0.55),   /* top specular */
            inset 0 -1px 0 rgba(255,255,255,0.12);  /* bottom bounce */
```

The three-layer discipline that comes with it is the part that actually matters:

1. **Content layer** — no glass, ever. Cards, text, images.
2. **Navigation layer** — glass. Tab bar, nav bar, floating toolbars.
3. **Overlay layer** — vibrancy and fills *on* the glass. Labels and icons in the tab bar.

Glass cannot sample glass. If two glass elements are adjacent, they belong to one container.

---

## 6. Iconography

- **Stroke weight scales with text.** Beside `text-body` (17px), icons are 20–22px at 1.5–1.75px
  stroke. Beside `text-footnote`, 16px at 1.5px. The icon should read at the same ink density as
  the text next to it.
- **Optical alignment** — center the icon on the text's **cap height**, not its bounding box.
  In practice this means a `-mt-px` nudge on most inline icons.
- **Icon tiles** — a tinted rounded square behind a colored glyph: `rounded-md`, `bg-{tone}-tint`,
  glyph in `text-{tone}-text` at 20px, tile 40×40 (or 36×36 in dense rows). This is the standard
  way to give a row a category without adding a word.
- **One icon family.** Do not mix outline and filled sets, or two different corner treatments.
  Filled is for *selected* states, outline for unselected — that's the only permitted mix, and it's
  exactly what the tab bar does.
- **Never an icon-only control without an accessible name.** `aria-label` on every one.
- **No emoji as UI icons.** They render differently on every platform and can't be recolored.

---

## 7. Layout archetypes

There are seven. Name the one you are using before you write markup, and record in the profile
which ones this product uses.

1. **Grouped list** — a tinted canvas with `surface` cards, each holding hairline-separated rows.
   The default for settings, verified documents, payment logs.
2. **Dashboard grid** — a hero card, then a 2–3 column stat row, then stacked section cards.
   The default for a home screen or an admin overview.
3. **Detail with hero** — a full-bleed media or deep-surface hero card, then metadata rows, then
   actions pinned at the bottom. The default for one item viewed in full.
4. **Feed** — a vertical stream of equal-weight cards with a leading status rail. Notifications,
   activity, search results.
5. **Form sheet** — a single `surface` card of labelled fields, with a sticky action pair at the
   bottom. Anything the user fills in and submits.
6. **Stepper flow** — a numbered progress header, one step's content at a time, back and next
   pinned. Onboarding, verification, checkout.
7. **Split view** — desktop only: a persistent sidebar plus a detail pane. Collapses to archetype
   1–6 below 1024px.

**Responsive rule:** design for the primary device named in the profile, then widen. When that is
phone-first, the desktop layout is the mobile layout with a sidebar and wider content columns —
**never a different information architecture.** A user who learns the phone app already knows the
desktop app. Two different IAs across breakpoints is two products with one name.
