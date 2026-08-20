# The project profile

This skill is the law. The profile is the local jurisdiction — the short list of facts that are
genuinely specific to one product and that no general design document can know.

**Write it once, at `docs/ui-profile.md`. Read it at the start of every UI task.** Without it,
every session re-guesses the brand color, the component import path, and the currency format, and
the product drifts a little each time. Five minutes now saves an inconsistent product later.

Keep it to one page. A profile that grows into a second design system has failed at its job.

---

## The template

```markdown
# UI PROFILE — <product name>

## Brand
Accent (fill, light / dark):        #______ / #______
Accent (text, light / dark):        #______ / #______
Deep surface for hero cards:        #______ / #______   (or "none")
Contrast verified:                  <date> — `node scripts/check-ui.mjs --tokens <path>` all PASS

## Where things live
Token layer:            <path to tokens.css>
Tailwind config:        <path, or "Tailwind v4 @theme block in <path>">
Component package:      <import specifier, e.g. @acme/ui or src/components/ui>
Checker:                <path to check-ui.mjs>
Check command:          <e.g. npm run check:ui>
Approved mockups:       <folder path, or "none — this skill is the standard">

## Product shape
Primary device:         <phone | desktop | both, and which wins a conflict>
Supported viewports:    <e.g. 320, 375, 768, 1024, 1440>
Dark mode:              <system-only | user toggle | light-only, with the reason>
Primary navigation:     <bottom tab bar (list the items) | sidebar | top nav>
Layout archetypes used: <which of the seven in 01-foundations §7>

## Locale and formatting
Locale:                 <e.g. en-IN, en-US, de-DE>
Currency:               <ISO code, and the Intl options used>
Number grouping:        <e.g. Indian lakh/crore via Intl.NumberFormat('en-IN')>
Date format:            <absolute style, and when it switches from relative>
Time format:            <12h with lowercase meridiem | 24h>
Additional languages:   <which, and where they appear in the UI>

## Domain vocabulary
Words the user actually says (use these):     <...>
Words we must never put on screen (internal): <...>

## Product-specific rules
<Anything this product enforces beyond the skill. Keep it to rules the skill does not
 already cover. If this section is empty, delete it.>

## Screen map
| # | Screen | Route(s) | Archetype | Mockup | Status |
|---|--------|----------|-----------|--------|--------|
| 1 |        |          |           |        |        |
```

---

## Filling it in — the parts people get wrong

**The accent split.** Two accent values, not one. `accent` is the *fill* behind white text on a
button; `accent-text` is the same identity used as *words* on a surface. In dark mode they must
differ — see `01-foundations.md §3.5` for why this is arithmetic, not preference.

**"Contrast verified" needs a date and a command, not a checkbox.** If you cannot point at the run,
it is not verified. Re-run it whenever a brand value changes.

**Primary device must name the winner.** "Both" is not an answer. When a phone layout and a desktop
layout genuinely conflict, one of them has to lose, and deciding that in the profile beats
re-deciding it in every code review.

**Domain vocabulary is the highest-value section.** It is what stops the interface from saying
"entity", "payload", "instance", or "submit" instead of the words the user brought with them.
List the real nouns. See `06-writing.md §1`.

**The screen map outranks your taste.** Where an approved mockup exists, it wins — and the entry
must point at a file you can actually open, not a description of one.

---

## Worked example

A real, filled-in profile, kept here so the template is never ambiguous. This is one product's
answers; it is not a default for yours.

```markdown
# UI PROFILE — UniNest (student OS platform)

## Brand
Accent (fill, light / dark):        #4338CA / #4F46E5
Accent (text, light / dark):        #4338CA / #A5B4FC
Deep surface for hero cards:        #0A1B3D / #0F2247
Contrast verified:                  2026-08-15 — all PASS

## Where things live
Token layer:            apps/web/src/app/globals.css
Tailwind config:        apps/web/tailwind.config.ts
Component package:      @uninest/ui  (source: packages/ui/index.tsx)
Checker:                scripts/check-ui.mjs
Check command:          npm run check:ui
Approved mockups:       Docs/Images/World Class UI/

## Product shape
Primary device:         phone — students and vendors work from phones; desktop is the phone
                        layout plus a sidebar and wider columns, never a different IA
Supported viewports:    320, 375, 768, 1024, 1440
Dark mode:              system-only
Primary navigation:     bottom tab bar — Home · Discover · AI · Marketplace · Profile
Layout archetypes used: grouped list, dashboard grid, detail with hero, feed, form sheet,
                        stepper flow, split view (desktop ≥1024 only)

## Locale and formatting
Locale:                 en-IN
Currency:               INR — Intl.NumberFormat('en-IN', {style:'currency', currency:'INR',
                        maximumFractionDigits:0}) → ₹1,90,000
Number grouping:        Indian lakh/crore. Dashboard summaries may abbreviate (₹18.4L, ₹7.3Cr);
                        anything transactional uses full grouping. Never both in one card.
Date format:            "17 May 2026" absolute; relative under 7 days ("10 min ago", "2 hr ago");
                        always include the year on anything financial or legal
Time format:            12-hour, lowercase meridiem — "4:30 PM"
Additional languages:   user-generated content (voice transcripts, vendor names) appears in its
                        original language, wrapped in the correct `lang` attribute

## Domain vocabulary
Words the user actually says: Student OS, Nestor, OSCE, station attempt, course, housing, stay,
                              vendor, verification, booking, listing
Words we must never show:     entity, payload, instance, leverage, utilize, seamless, submit

## Product-specific rules
- Indigo / `ai` tone is reserved for content a model produced or suggested. When a user sees
  indigo, a model was involved. This is a trust affordance, not a palette choice.
- Every AI action is reviewable before it executes. No model output mutates state without a
  human confirmation step.
- AI-extracted data always states a confidence number, with low-confidence fields flagged
  individually for review.
- Score breakdowns are itemized (the components and their weights) plus a plain-language
  justification. A score with no breakdown is not shippable.

## Screen map
| # | Screen | Route(s) | Archetype | Mockup | Status |
|---|--------|----------|-----------|--------|--------|
| 1 | Today / marketing hero | `/` | Hero + narrative | 01-today.png | Exists |
| 2 | Student OS hub | `/student` | Dashboard grid | 02-hub.png | Exists |
| 3 | Housing & services marketplace | `/marketplace` | Feed | 03-market.png | Exists |
| 4 | Medical OSCE & cases | `/medical` | Detail with hero | 04-osce.png | Exists |
| 5 | Student discovery | `/discover` | Search + grid | 05-discover.png | Exists |
| 6 | Exams & question bank | `/exams` | Stepper flow | 06-exams.png | Exists |
| 7 | Nestor AI workspace | `/ai`, `/chat` | Conversational | 07-ai.png | Exists |
| 8 | City Zero attribution | `/city-zero` | Dashboard grid | 08-city.png | Exists |
| 9 | Vendor dashboard | `/vendor` | Dashboard grid | 09-vendor.png | Exists |
| 10 | Institution admin portal | `/institution`, `/admin` | Split view | 10-admin.png | Exists |
| 11 | Workspace outcome governance | `/workspace` | Dashboard grid | 11-workspace.png | Exists |
| 12 | Housing booking & checkout | `/booking` | Form sheet | 12-booking.png | Exists |
| 13 | Notifications centre | `/profile` | Feed | 13-alerts.png | Exists |
| 14 | Vendor acquisition landing | `/for-vendors` | Hero + narrative | 14-landing.png | Exists |
| 15 | Verified service tracker | `/marketplace`, `/vendor` | Detail with hero | 15-tracker.png | Exists |
| 16 | Vendor onboarding | `/vendor/onboarding` | Stepper flow | 16-onboard.png | Exists |
```

---

## Design language extracted from a mockup set

When a project arrives with approved mockups, the profile's job is to state what is *consistent
across all of them* — that is the real design language, and it is what a new screen must match.
Extract it as a short list. From the example set above:

- **Canvas** — a cool light slate, never pure white. Cards float on it.
- **Cards** — `bg-surface`, `rounded-xl`, `shadow-e1`, no border in light mode.
- **Titles** — `text-display`, with a `text-subhead text-label-secondary` line underneath
  explaining what the screen is for.
- **Hero card** — one per screen, maximum: the deep surface, `rounded-2xl`, holding the single most
  important number or the assistant entry point.
- **Icon tiles** — 36–44px tinted rounded squares with a colored glyph. This is how a row gets a
  category.
- **Pill badges** — tinted background, colored text, ~24px tall, stating a status fact.
- **Progress bars** — thin, fully rounded, tone-coded, with the numeric value adjacent.
- **Trailing action buttons** — actionable rows end in a small tinted button.
- **Bottom action pair** — forms and detail screens end with a secondary (tinted or outline) and a
  primary (filled) button side by side.

Doing this once turns sixteen images into nine rules, and nine rules are something a new screen can
actually be checked against.
