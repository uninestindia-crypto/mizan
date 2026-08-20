# Writing — the words are part of the design

Apple's interface writing is the least-copied and most important part of its design language. It is
plain, direct, and respects the reader. It never sounds like a brand.

**The test:** read the string aloud. If it sounds like marketing, a lawyer, or a robot, rewrite it.

> **On the examples in this file.** They use a deliberately generic product — a booking app with
> orders and vendors — so the *shape* of each rule is visible without importing another product's
> vocabulary. Substitute your own nouns from the profile's **Domain vocabulary** section. Copying
> these nouns literally into your product is the failure this file exists to prevent.

---

## 1. Voice

| Do | Don't |
|---|---|
| "Book a stay" | "Submit application to vendor pool" |
| "Your score updated for section 4" | "Potential performance variance detected" |
| "Couldn't reach the server. Check your connection and try again." | "Error 500: Request failed" |
| "No saved stays yet" | "No data available" |
| "Verified 17 May 2026" | "VERIFICATION_STATUS: COMPLETE" |

- **Sentence case everywhere.** Not Title Case. Not ALL CAPS (except the `text-caption-2` eyebrow).
- **Second person.** "Your orders", not "My orders" or "User orders".
- **Active voice.** "The vendor confirmed the booking", not "The booking was confirmed".
- **Contractions.** "Couldn't", "you're", "we'll". Formal English reads as cold.
- **No exclamation marks.** One per product, maybe, at a genuine milestone.
- **No jargon the user didn't bring.** Use the nouns from the profile's domain vocabulary. Users
  never say "entity", "payload", "instance", "leverage", "utilize", "seamless".
- **Numbers as numerals.** "7 active tasks", not "seven active tasks".

**Where the vocabulary comes from.** Not from you, and not from the database schema. It comes from
what users say out loud — in support tickets, sales calls, and interviews. A table named `txn_hdr`
is called "an order" by the person paying for it. Write down both, put the user's word on screen,
and record the pairing in the profile so the next screen agrees with this one.

## 2. Buttons

A button label states **the outcome**, as a verb phrase. The user should be able to read only the
button and know what happens.

| Good | Bad |
|---|---|
| Book a stay | Submit |
| Save plan | OK |
| Confirm booking | Action |
| Request missing details | Continue |
| View verified vendors | Learn more |

- 1–4 words. If you need more, the button is doing too much.
- Include the count or object when it removes ambiguity ("Book stay at Fairview" beats "Book").
- Destructive buttons name the thing: "Delete draft #1042", not "Delete".
- The cancel button is "Cancel". Not "Nevermind", not "Go back", not "Dismiss".

## 3. Titles and headings

- Screen titles are **nouns**, and they are the user's noun: "Orders", "Marketplace", "Billing".
- Section headings inside a screen are nouns too: "Verified vendors", "Recent activity".
- Subtitles explain the screen's job in one line, lowercase after the first word.
- No colons, no trailing punctuation on headings.

## 4. Errors

Three parts, in this order: **what happened → why (if useful) → what to do**.

```
Couldn't send the order.
Three vendors are missing tax details.
Review vendors   ·   Send to the other 20
```

- Never "An error occurred" or "Something went wrong". Say what.
- Never blame the user. "Enter a valid tax ID" beats "Invalid input".
- Never expose stack traces, error codes alone, or internal names. A support reference code is
  fine *alongside* a human explanation.
- Always offer the next action. A dead-end error is a design failure.
- Distinguish "you're offline" from "the server failed" — the user's action differs.

**The three-part shape is the rule; the nouns are yours.** An error that names a thing the user
recognizes and an action they can take is correct in any domain.

## 5. Empty states

| Flavor | Title | Body | Action |
|---|---|---|---|
| Nothing yet | "No saved stays yet" | "Explore listings and save your top choices." | Explore listings |
| No results | "No vendors match" | "Try clearing your location or price filter." | Clear filters |
| Error | "Couldn't load orders" | "Check your connection and try again." | Retry |

Never a bare "No data". Never a joke — the user is trying to work.

## 6. Loading and progress

- "Loading…" is acceptable but weak. Say what: "Finding vendors…", "Reading your file…".
- Over 3 seconds, say something reassuring and specific: "Still checking records…".
- Never a percentage you can't compute honestly.

## 7. Numbers, currency, dates

**Every one of these comes from the profile's locale, through `Intl`.** Never a hand-rolled format
string, never a locale hardcoded in a component. This is the section that most often gets copied
from another product and quietly ships the wrong currency symbol.

- **Currency** — `Intl.NumberFormat(locale, {style:'currency', currency, maximumFractionDigits:0})`.
  The locale controls grouping, and grouping is not universal: `en-US` → `$190,000`,
  `de-DE` → `190.000 €`, `en-IN` → `₹1,90,000` (lakh grouping). Take it from `Intl`, not from a
  regex.
- **Abbreviations** — if the profile permits them for dashboard summaries (`$18.4M`, `₹18.4L`), use
  them only where space is genuinely tight, and use full grouping for anything transactional
  (invoices, receipts, bids). Never both in one card.
- **Dates** — one absolute style, stated in the profile. Relative for recent ("10 min ago",
  "2 hr ago"), switching to absolute past 7 days. Always include the year for anything financial
  or legal.
- **Times** — 12-hour or 24-hour per the profile, and consistent everywhere.
- **Percentages** — no decimal unless the precision is meaningful. "92%" not "92.0%".
- **Ranges** — en dash, no spaces: "1–3 days".
- **Units** — always attached and always labeled: "1200 kg", "500 units".
- **Tabular numerals** on anything in a column or that updates in place.

## 8. Labels and metadata

- Field labels are short nouns: "Delivery location", "Needed by".
- Don't repeat the section title in every row.
- Timestamps are metadata — `text-caption-1 text-label-tertiary`, trailing, never emphasized.
- Truncate descriptions, never identifiers. A cut-off vendor name or order number is a bug.

## 9. AI copy

Applies only if the product has an AI surface. Where it does, AI output must always be labeled as
such and always be reviewable.

- Prefix suggestions with the source: "AI suggests delaying the non-urgent order by 5 days."
- State confidence when the model extracted data: "AI extracted 8 fields with 94% confidence."
- Justifications are **plain language, not scores**: "Option C is not the cheapest, but it arrives
  a day sooner and reduces your schedule risk."
- Never present a model output as certain fact. Use "may", "likely", "suggests".
- Never anthropomorphize beyond the product name. "<Product> found 7 options", not "I found 7
  options".

## 10. Multilingual

- Interface chrome in the interface language, but user-generated content (transcripts, vendor
  names, uploaded text) appears in its original language — wrapped in the correct `lang` attribute
  so a screen reader switches voice.
- Never machine-translate a legal or financial value. Show the original alongside.
- Design for +40% string length; never truncate a translated label. German and Finnish will find
  every layout that assumed English.
