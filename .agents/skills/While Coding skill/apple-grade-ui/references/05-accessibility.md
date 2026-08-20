# Accessibility

Not a checklist item at the end. A design constraint from the first line. Target: **WCAG 2.2 AA**,
with AAA on text contrast wherever it costs nothing.

The reality this defends against: someone using a phone in direct sunlight, someone whose first
language isn't the interface's, someone with the OS text size cranked up, someone on a trackpad
with a tremor. Accessibility work is what makes the product usable for the actual user base, not a
compliance tax. **Name your own version of that list in the profile** — the specific pressures your
users are under determine which of these rules bite hardest.

---

## 1. Contrast

| Content | Minimum |
|---|---|
| Text under 24px (or under 19px bold) | **4.5:1** |
| Text 24px+ (or 19px+ bold) | **3:1** |
| Icons and graphics that carry meaning | **3:1** |
| Control boundaries (input borders, focus rings) | **3:1** |
| Disabled elements | exempt — but then they must not be the only cue |

**Verify, never estimate.** Alpha-composited colors (`label-secondary` on a tinted card) must be
checked against the *actual* rendered background, not the token's nominal value.

Known token behavior:
- `label` on `surface` → 21:1 ✓
- `label-secondary` on `surface` → 6.2:1 ✓
- `label-tertiary` on `surface` → 2.9:1 ✗ — **decorative and placeholder only**
- `accent` (#0A5AFF) on `surface` → 5.1:1 ✓
- White on `accent` → 5.1:1 ✓
- White on `success` (#12A150) → 3.6:1 — passes only at 19px+ bold; use `text-success` on
  `success-tint` for small text instead
- `warning` (#F08C00) on `surface` → 2.6:1 ✗ — **never use warning as small text on white.** Use
  the darker `warning-text` token (#B36A00, 4.6:1) for text, and reserve #F08C00 for fills/glyphs.

That last one is the trap: orange and yellow almost never pass as text on light backgrounds. Every
"caution" label must use the darker text token.

## 2. Color independence

~1 in 12 men and 1 in 200 women have a color vision deficiency. Red/green is the common one — and
almost every product's status system is built on red/green.

**Every status must carry a second signal:**

| Status | Color | + Glyph | + Word |
|---|---|---|---|
| Verified | success | check | "Verified" |
| Delayed | warning | clock | "Delayed" |
| Critical | danger | triangle-alert | "Critical" |
| In transit | accent | truck | "In transit" |

A colored dot with no label is never sufficient. A red number with no glyph is never sufficient.
Charts differentiate by pattern/label, not hue alone.

Test by rendering the screen in grayscale. If you can't tell the states apart, it fails.

## 3. Text scaling

- All type in `rem` against a 16px root. Never `px` font sizes.
- Layouts survive **200% text scaling** with no clipping and no loss of function.
- `min-height`, never `height`, on anything containing text.
- Never `overflow: hidden` on a text container unless paired with `text-overflow: ellipsis` and
  the full value available elsewhere (tooltip, detail view).
- `user-scalable=no` and `maximum-scale=1` in the viewport meta are **banned**.
- Test at 320px width — the narrowest supported viewport — with large text.

## 4. Semantics

**Use the right element.** This is 80% of accessibility.

| Need | Element |
|---|---|
| Navigates | `<a href>` |
| Performs an action | `<button type="button">` |
| Submits | `<button type="submit">` |
| A group of related controls | `<fieldset>` + `<legend>` |
| A list of things | `<ul>` / `<ol>` |
| Tabular data | `<table>` with `<th scope>` |
| A heading | `<h1>`–`<h6>`, in order, no skips |

A `<div onClick>` is not a button. It isn't focusable, doesn't fire on Enter/Space, and announces
nothing. Every one is a bug.

**Landmarks** — one `<main>`, `<nav aria-label="...">` on each nav, `<header>`, `<footer>`.
Multiple navs need distinguishing labels ("Primary", "Breadcrumb").

**Headings** describe structure, not size. Use `<h2 class="text-headline">` if that's the right
level — never pick a heading tag for its default styling.

## 5. ARIA

The first rule of ARIA is don't use ARIA. Native semantics first. When you do need it:

- `aria-label` on every icon-only control
- `aria-describedby` linking a field to its help text and error
- `aria-invalid="true"` on errored fields
- `aria-expanded` on disclosure triggers
- `aria-current="page"` on the active nav item
- `aria-busy="true"` on a region that's loading
- `aria-live="polite"` for status updates (search result counts, autosave, sync state)
- `aria-live="assertive"` **only** for errors that interrupt the task
- `role="alert"` on validation errors (implies assertive)
- `aria-sort` on sortable table headers
- Decorative images: `alt=""`. Meaningful images: a description of the *information*, not the
  picture ("Invoice from Acme Supply, total $71.70", not "photo of a receipt").

**Never** `aria-hidden` on anything focusable. **Never** an ARIA role that contradicts the element.

## 6. Motion and transparency

```css
@media (prefers-reduced-motion: reduce)      { /* see 02-motion.md §5 */ }
@media (prefers-reduced-transparency: reduce) { /* materials → opaque surface */ }
@media (prefers-contrast: more) {
  /* raise separator opacity, add 1px borders to all controls,
     promote label-secondary → label */
}
```

All three are real user settings with real reasons behind them. Implement all three.

## 7. Screen readers

- Test with VoiceOver (⌘F5 on Mac, or on the iPhone) at least once per major screen. Reading the
  markup is not the same as hearing it.
- Announce route changes — SPA navigation is silent by default, which strands screen reader users.
- Dynamic content updates go through a live region, not a silent DOM swap.
- Visually-hidden text (`.sr-only`) for context a sighted user gets from layout: "Row 3 of 12",
  the unit of a number, what a chevron leads to.
- Icon + number pairs need a full label: `aria-label="7 risk alerts"`, not "7".
- Tables get a `<caption>`.

## 8. Language and internationalization

- `lang` attribute on `<html>`, and on any element in a different language. This matters most on
  screens that mix interface chrome in one language with user-generated content in another — wrap
  the content in `<span lang="…">` so the screen reader switches voice mid-screen.
- Numbers, currency, and dates go through `Intl` with **the profile's locale** — never
  hand-formatted, never a locale hardcoded in a component. Locale-correct grouping comes free:
  `Intl.NumberFormat('de-DE')` → `1.900.000`, `Intl.NumberFormat('en-IN')` → `19,00,000`. Getting
  this from `Intl` rather than a format string is what makes the product portable.
- Never concatenate translated fragments. Use full sentences with interpolation.
- Design for **+40% string length** — English is one of the shortest UI languages.
- Don't bake text into images.

## 9. Forms specifically

- Every input has a visible `<label>` associated by `for`/`id`. Placeholder is not a label.
- Errors: adjacent to the field, in text, announced, and not color-only.
- Required fields marked in text, not just with a red asterisk.
- Autocomplete tokens on personal-data fields (`autocomplete="tel"`, `"organization"`, `"street-address"`).
- Grouped radios/checkboxes in a `<fieldset>` with a `<legend>`.
- Don't impose arbitrary format rules the user can't see (phone numbers, tax IDs, card numbers) —
  accept liberally and normalize on the way in, or show the expected format up front.
- Time limits: none, or extendable.

## 10. Verification

Automated (catches ~40%):
```bash
npx @axe-core/cli http://localhost:3000/dashboard
```
Plus `eslint-plugin-jsx-a11y` in the lint pass.

Manual (catches the rest):
- [ ] Unplug the mouse. Complete the primary task with Tab/Enter/Space/arrows only.
- [ ] Is the focus ring always visible? Is the order sane?
- [ ] Zoom to 200%. Anything clipped or overlapping?
- [ ] Render in grayscale. Are all states still distinguishable?
- [ ] Turn on VoiceOver. Is every control announced with a meaningful name and role?
- [ ] Enable Reduce Motion. Does everything still make sense?
- [ ] Enable Reduce Transparency. Is anything unreadable?
- [ ] 320px viewport at largest text size. Still usable?
