# Interaction — touch, pointer, keyboard, state

How it responds is what makes it feel real.

---

## 1. Targets

- **44×44 CSS px minimum**, always, on every platform (Law 4). Apple's figure; Google's is 48.
  Use 44 as the floor and 48 for anything a user taps repeatedly.
- The *visible* element can be smaller. Expand the hit area with padding, or invisibly:
  ```css
  .tap-expand::after {
    content: ''; position: absolute; inset: -8px;
  }
  ```
- **Spacing between targets ≥ 8px.** Adjacent 44px targets with no gap produce mis-taps.
- **Thumb zones matter.** On a phone the bottom third is easy, the top corners are hard. Primary
  actions go bottom. Destructive actions never go where a thumb rests.
- Whole rows and whole cards are targets, not just their titles.
- Never put a small destructive control adjacent to a common one (delete next to edit at 24px each).

## 2. Press and hover

**Every interactive element responds within 100ms**, before any network call resolves.

```css
/* pointer devices only — hover on touch produces sticky states */
@media (hover: hover) and (pointer: fine) {
  .btn:hover { background: var(--primary); }
}
.btn:active { transform: scale(0.97); }
```

- `:active` (press) is required. `:hover` is optional and **must be inside a hover media query**.
- Never rely on hover to reveal a control that's needed on touch. Hover may only *enhance*.
- Cursor: `pointer` on anything clickable, `not-allowed` on disabled, `text` on text, default
  otherwise. A `pointer` cursor on non-interactive text is a lie.

## 3. Focus

Keyboard users must always know where they are.

```css
:focus { outline: none; }              /* only paired with the next rule */
:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
  border-radius: inherit;
}
```

- `:focus-visible`, not `:focus` — so mouse clicks don't leave a ring but Tab does.
- **Never `outline: none` without a replacement.** This is the most common accessibility failure
  in shipped web apps.
- Focus order follows visual order. If they disagree, fix the DOM order, not with `tabindex`.
- Positive `tabindex` values are banned. `0` and `-1` only.
- On route change, move focus to the new page's `<h1>` (with `tabindex="-1"`), and announce it.
- Modals trap focus; closing returns focus to the trigger.
- A skip-to-content link is the first focusable element on every page.

## 4. Keyboard

| Key | Behavior |
|---|---|
| `Tab` / `Shift+Tab` | Move between controls |
| `Enter` | Activate a button/link; submit a single-field form |
| `Space` | Activate a button; toggle a checkbox; page down when not in a control |
| `Esc` | Close the topmost sheet/modal/menu/popover; clear a search field |
| `↑ ↓` | Move within a list, menu, or select |
| `← →` | Move within a segmented control, tab row, or slider |
| `Home` / `End` | First / last item in a collection |
| `⌘K` / `Ctrl+K` | Global search (desktop) |

Composite widgets (menu, segmented control, tab list) are a **single tab stop** with arrow-key
navigation inside — that's the ARIA authoring practice, and it's what makes keyboard navigation
fast rather than exhausting.

## 5. Gestures (touch)

- **Every gesture needs a visible fallback.** Swipe-to-delete must also exist in a menu. A gesture
  is an accelerator for experienced users, never the only path.
- Swipe actions: reveal proportionally under the finger, snap open past 40% of the action width,
  spring back below it. Full swipe past 70% commits the primary action.
- Respect system edge gestures — don't put a horizontal swipe target within 20px of the screen
  edge; it fights iOS back-navigation.
- Pull-to-refresh only on feed/list screens that genuinely change.
- Long-press (500ms) opens a context menu, with a haptic tap at the threshold.
- `touch-action: manipulation` on interactive elements removes the 300ms tap delay.
- Never hijack pinch-zoom or block scroll to implement a custom gesture.

## 6. Haptics

Available in the Capacitor/Tauri wrappers. Web gets no-ops.

| Feedback | When |
|---|---|
| Selection (light tick) | Segmented control, picker, tab change |
| Impact light | Toggle, chip select |
| Impact medium | Sheet snapping to a detent, swipe action committing |
| Success notification | Award confirmed, payment released, KYC approved |
| Warning notification | Validation blocked submission |
| Error notification | Action failed |

Haptics **confirm**, they don't decorate. Never on scroll, never on every keystroke, never more
than one per user action.

## 7. State machine — every component

The nine states (Law 9). Write them all before shipping.

1. **Default** — the resting state
2. **Hover** — pointer only
3. **Pressed** — within 100ms, `scale(0.97)`
4. **Focus-visible** — the ring
5. **Disabled** — 40% opacity, `aria-disabled`, **and an adjacent explanation of why**
6. **Loading** — skeleton (content) or in-button spinner (action), `aria-busy`
7. **Empty** — the right one of the three flavors
8. **Error** — what happened, what to do, how to retry
9. **Overflow** — 500 rows, a 90-character name, a number at the top of its plausible range.
   Does it hold?

### Disabled vs. blocked
Prefer **enabled with clear feedback** over disabled. A disabled action button with no
explanation is a dead end for the user. Let them press it, then show what's missing. Disable only
when the action is genuinely impossible (no permission, already submitted).

## 8. Forms

- Validate on **blur**; re-validate on change only after a field has errored.
- One error summary at the top for long forms, linking to each bad field; plus the inline errors.
- Preserve input on failure — never clear a form because the server rejected it.
- Autosave drafts on long forms, with a visible "Saved" timestamp.
- Warn before navigating away from unsaved changes (`beforeunload` plus an in-app router guard).
- Submit disables *itself* during flight to prevent double submission, and shows a spinner.
- After success: navigate or show a confirmation. Never leave the user staring at the form
  wondering if it worked.

## 9. Offline and slow networks

Unless the profile says otherwise, assume a meaningful share of sessions happen on cellular or
congested shared Wi-Fi. Treat that as a primary environment, not an edge case — it is the single
most common gap between a demo that works and a product that works.

- **Optimistic UI** for everything reversible — show the result, reconcile after, roll back with an
  explanation if it fails.
- Queue mutations offline and replay them; show a persistent "3 changes pending sync" indicator.
- Cache the last-known data and show it with a "Last updated 12 min ago" stamp rather than an
  empty screen.
- Images: `loading="lazy"`, explicit `width`/`height` or `aspect-ratio` to prevent layout shift,
  and a `blur` placeholder.
- Every network error offers a Retry. Distinguish "you're offline" from "the server failed" —
  they need different actions from the user.
- Voice notes and photos capture locally first, upload in the background. Never block the user on
  an upload.

## 10. Scroll

- `overscroll-behavior: contain` on scrollable panels so a scroll inside doesn't chain to the page.
- **Never hijack the scroll.** No scroll-jacking, no custom smooth-scroll libraries.
- Sticky headers use `position: sticky`, and get their material/shadow only once scrolled
  (`IntersectionObserver` sentinel, not a scroll listener).
- Restore scroll position on back navigation.
- Infinite scroll needs a visible loading indicator and a "load more" fallback for keyboard users.
  Never infinite-scroll a page that has a footer.
- Horizontal scroll rows (chips, cards) get `scroll-snap-type: x mandatory` and a mask on the
  trailing edge so it's obvious there's more.
