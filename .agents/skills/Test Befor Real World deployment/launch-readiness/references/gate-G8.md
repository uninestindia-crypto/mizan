# G8 — UX, Accessibility & Devices

> **Purpose.** A real person, on a real device, including one using a screen reader, can finish the
> job unaided.
>
> **Veto holder.** Design owner. **Entry.** G7 passed. **Exit.** 16 checks resolved.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**If the project has its own design law skill or design system documentation, that document is the
standard and this gate defers to it entirely.** Load it and walk its checklist. What follows is the
floor, not the ceiling.

**The single most important check here is G8.13, Customer Zero.** Everything else in this gate can
pass while the product remains unusable by a person who was not in the room while it was built.

---

#### G8.01 · Keyboard only — `S0` `manual`

- **Do** — put the mouse away. Physically. Complete every critical path using only Tab, Shift+Tab, Enter, Space, Escape, and arrow keys.
- **Check** — focus is always visible; tab order follows visual order; every interactive element is reachable; modals trap focus **while open** and return it to the trigger on close; Escape closes every overlay; there is a skip-to-content link; nothing traps focus permanently.
- **Pass** — you completed the primary job with no mouse.
- **Faked by** — tabbing through the homepage. Do the whole checkout.

#### G8.02 · Screen reader — `S0` `manual`

- **Do** — turn on a real screen reader and traverse one complete critical path with your eyes closed or the monitor off. NVDA (Windows, free), VoiceOver (macOS: Cmd+F5; iOS: triple-click side button), TalkBack (Android).
- **Check** — every control announces a name, a role, and a state; images have alt text (or are marked decorative); form fields are associated with their labels; errors are announced when they appear (`aria-live`); dynamic content updates are announced; headings form a sensible outline.
- **Pass** — you completed the task. Attach a transcript or recording.
- **What you will find** — icon-only buttons announced as "button", form errors that appear visually but are never announced, and modals that do not announce themselves at all.

#### G8.03 · Automated accessibility scan — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G8.03 -- npx @axe-core/cli "$URL" --exit
  LRK run G8.03 --title "axe: checkout" -- npx @axe-core/cli "$URL/checkout" --exit
  ```
  Or `npx pa11y-ci`, or Lighthouse's accessibility category.
- **Pass** — zero critical and zero serious violations on **every major screen**, not just the homepage.
- **Important limitation** — automated tools catch roughly 30–40% of accessibility problems. Passing G8.03 while failing G8.01 and G8.02 is the normal outcome for an inaccessible product. The scan is necessary and nowhere near sufficient.

#### G8.04 · Colour contrast — `S1` `hybrid`

- **Do** — check every text/background pair and every interactive boundary.
- **Pass** — 4.5:1 for body text, 3:1 for large text (18pt+ or 14pt bold), 3:1 for interactive component boundaries and focus indicators.
- **The usual offenders** — placeholder text, disabled buttons, "secondary" grey labels, white text on brand colours, and focus rings.
- **Also** — no information conveyed by colour alone. A red border with no error text is invisible to a colour-blind user and to a screen reader.

#### G8.05 · 320px and ultra-wide — `S1` `manual`

- **Do** — set the viewport to 320×568 (an iPhone SE, still in wide use) and walk every screen. Then set it to 2560px wide.
- **Pass** — nothing clips, nothing overlaps, no horizontal page scroll, tap targets are at least 44×44px, modals fit and can be dismissed, and tables scroll inside their own container rather than pushing the page sideways.

#### G8.06 · Device and browser matrix declared and tested — `S0` `manual`

- **Do** — write the support matrix, then actually test every entry. A defensible default:

| Class | Minimum |
|---|---|
| Desktop | Latest Chrome, Firefox, Safari, Edge |
| iOS | Safari on the current and previous major iOS |
| Android | Chrome on the current version, on a mid-tier device |
| Screen sizes | 320px, 768px, 1280px, 1920px |

- **Safari is not optional.** It has genuinely different behaviour for dates, form inputs, flexbox gaps, `100vh`, IndexedDB, and service workers. A product tested only in Chrome is untested for roughly a third of consumer traffic.
- **Test on a real phone, not just the emulator.** Emulators do not reproduce real touch behaviour, real network variability, real memory pressure, or the on-screen keyboard covering your submit button.

#### G8.07 · Dark, light, and high contrast — `S1` `manual`

- **Do** — switch the OS theme and reload. Then enable forced-colours / high-contrast mode.
- **Pass** — both themes are legible and deliberate; no invisible text; no white box in a dark layout; images and icons adapt or have appropriate backgrounds.

#### G8.08 · Reduced motion respected — `S2` `hybrid`

- **Run** — `LRK run G8.08 -- git grep -n "prefers-reduced-motion" -- .`
- **Pass** — the query is honoured; no unavoidable parallax, auto-playing carousel, or large motion. For some users this is a vestibular-disorder trigger, not a preference.

#### G8.09 · Zoom to 200% and 400% — `S1` `manual`

- **Do** — browser zoom to 200%, then 400%.
- **Pass** — no content lost, no function lost, no horizontal scrolling at 400% on a 1280px viewport (WCAG 1.4.10 reflow).

#### G8.10 · Copy review — `S1` `manual`

- **Do** — read every error message, empty state, confirmation, and button label out loud, as a user who does not know how the system works.
- **Pass** — each error says **what happened** and **what to do next**. Ban list: "Something went wrong", "Error 500", "Invalid input", "Failed", "Oops!", and any raw exception text.
- **Compare**: *"Invalid input"* → *"Card number must be 16 digits. You entered 15."*
- **Also check** — empty states tell the user what to do first, not just that there is nothing here; destructive confirmations name what is being destroyed; success messages confirm what actually happened.

#### G8.11 · Internationalisation — `S1` `manual`

- **Do** — switch to the longest supported language (German is typically 30% longer than English; Finnish more) and check every layout. If RTL is supported, switch to Arabic or Hebrew and confirm the whole layout mirrors, not just the text.
- **Check** — number formats (`1,234.56` vs `1.234,56`), date formats (`03/04` is ambiguous between two continents), currency placement, name fields that assume a first/last split, address forms that assume a US format, and phone validation that assumes a country.
- **Pass** — no clipping, no truncation without a tooltip, no hardcoded strings left in the source, no concatenated sentence fragments (they are untranslatable).

#### G8.12 · Slow network and offline — `S1` `manual`

- **Do** — devtools → Network → "Slow 3G", walk every critical path. Then "Offline".
- **Pass** — on slow: skeletons or progress within 1 second, no double-submits while waiting, no timeout that fires before the request could reasonably complete. On offline: an honest message, work in progress is not silently lost, and it recovers when the connection returns.
- **Most of the world is on a slow, intermittent connection some of the time.** Your office wifi is not the test.

#### G8.13 · CUSTOMER ZERO — `S0` `manual`

**The highest-value check in this gate, and the one most often skipped because it is uncomfortable.**

- **Do** — get a person who has **not** seen this product being built. Give them a genuinely empty account and a one-sentence goal ("buy something", "invite a teammate"). Then:
  - Say nothing. Do not explain. Do not hint. Do not touch the keyboard.
  - Ask them to narrate what they are thinking.
  - Write down **every** moment of hesitation, every wrong click, every re-read, and the exact moment a real person would have given up or contacted support.
  - Let them fail. The failure is the finding.
- **If no human is available** — run a fresh agent session with no context, give it only the URL and the goal, and log where it gets stuck. Weaker than a human, far better than nothing. State which you did.
- **Record** —
  ```bash
  LRK manual G8.13 --status pass --by "<who>" \
    --note "38 min, empty account, goal: complete first purchase. Completed with 2 dead ends. Worst moment: spent 4 min looking for 'Add payment method' — it is inside Settings > Billing > Advanced. 11 friction points logged." \
    --attach friction-log.md
  ```
- **Pass** — they completed the primary job unaided, **and** the worst friction point is fixed, cut, or written down as a known limitation.
- **The rule that makes this work** — you are not allowed to explain. The moment you say "oh, you just click there", you have learned the thing and destroyed the evidence. Every explanation you want to give is a change the product needs.
- Template: `templates/friction-log.md`.

#### G8.14 · No blank frozen frame — `S1` `manual`

- **Do** — with the network throttled, watch every screen transition and every submit.
- **Pass** — any wait over one second shows something interpretable: a skeleton, a spinner with context, a progress bar, or a disabled button with changed text. Never a blank frame, and never a UI that looks finished but is not interactive yet.

#### G8.15 · Print, export, share, embed — `S2` `manual`

- **Do** — if the product claims any of these, use them. Print to PDF. Open the CSV in Excel and in Google Sheets. Paste a share link into Slack, WhatsApp, and iMessage and look at the preview card.
- **Pass** — each works and looks intentional. CSV exports open with correct encoding (a BOM for Excel), correct delimiters, and no formula injection (a cell beginning with `=`, `+`, `-`, or `@` executes in Excel).

#### G8.16 · Mobile specifics — `S0` `manual`

Applies to any app shipping as a binary.

- **Test** — safe areas on a notched device (nothing under the notch or the home indicator); rotation mid-flow; backgrounding and resuming after an hour; resuming after the OS killed the process; **every OS permission denied** (camera, location, notifications, photos) — the app must degrade, never crash; deep links from cold start; the on-screen keyboard covering the submit button; the back gesture mid-flow; and a low-battery / low-memory device.
- **Pass** — each handled. Permission denial is the one that crashes apps most reliably, because it is the path nobody walks during development.

---

## Exit bar for G8

```bash
LRK status --gate G8
```

Two questions before you leave:

1. **Did a person who did not build this finish the job?** (G8.13) If no, nothing else here matters.
2. **Did you complete a critical path with the monitor off?** (G8.02) If no, you do not know whether this product is usable by people who cannot see it — and in many jurisdictions that is a legal exposure as well as a moral one.
