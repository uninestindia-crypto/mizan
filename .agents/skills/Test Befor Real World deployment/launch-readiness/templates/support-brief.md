# Support Brief — <PRODUCT> v<VERSION>

> For gate **G10.15**. The test: someone answering messages can handle week one without reading the
> source code or asking an engineer.

---

## What shipped, in one paragraph a non-engineer can read

> ___

## What changed for existing users

| Change | Who notices | What they need to do |
|---|---|---|
| | | |

**Anything breaking?** ___ (if yes, link the migration guide from G11.16)

---

## The five questions we expect, with answers

Copy-paste ready. Write them as you would send them.

**1. "___?"**
> ___

**2. "___?"**
> ___

**3. "___?"**
> ___

**4. "___?"**
> ___

**5. "___?"**
> ___

- [ ] Every answer above is findable in the shipped documentation, not only here.

---

## Known limitations — say these before the user finds them

Everything cut, waived, or documented as a limitation during the readiness review.

| Limitation | What the user experiences | What to tell them | Fixed when |
|---|---|---|---|
| | | | |

**Users forgive a stated limitation and never forgive a surprise.** If it is on this list, lead
with it rather than waiting to be asked.

---

## Triage — what to do with a report

| Symptom | Likely cause | First response | Escalate if |
|---|---|---|---|
| Cannot sign in | | | |
| Payment failed | | | |
| Data looks wrong | | **Escalate immediately.** Do not advise a workaround. | Always |
| Page is slow | | | |
| Email not received | Check spam; verify the address; check the sending log | | Over 3 reports in an hour |
| "It's broken" (no detail) | | Ask: what were you doing, what did you expect, what happened, browser and device, screenshot | | |

**Anything that smells like data loss, wrong charges, or one user seeing another user's data goes
straight to engineering, immediately, before any further conversation with the user.** Those three
categories get worse while you triage them.

---

## Escalation

| Level | Who | How | When |
|---|---|---|---|
| L1 — Support | | | Default |
| L2 — Engineering on-call | | | Data, money, security, or 3+ reports of the same thing in an hour |
| L3 — Owner | | | Anything affecting all users, or any public-facing incident |

**On-call for the launch window:** ___ (from G10.08)

---

## Information to collect on every report

- What were you trying to do?
- What did you expect to happen?
- What actually happened?
- Browser / device / OS
- Approximate time it happened (with timezone) — engineering needs this to find the logs
- Screenshot or screen recording
- Account email or ID

Without the time and the account ID, a log search takes an hour instead of a minute.

---

## Do not say

| Never say | Say instead |
|---|---|
| "That's a known bug" | "That's a known limitation — here's the workaround, and it's fixed in ___" |
| "It works for me" | "Let me reproduce that — can you tell me ___?" |
| "You must be doing it wrong" | "Let's walk through it together" |
| "Engineering is looking into it" (with no timeframe) | "I've escalated it. I'll come back to you by ___." |
| Any promise about a date you did not get from engineering | "I don't have a date yet; I'll tell you as soon as I do." |

---

## Status page

| | |
|---|---|
| URL | ___ |
| Who can post | ___ |
| Post when | Any incident affecting more than a handful of users, or lasting over 15 minutes |
| Pre-written "investigating" message | *"We're aware of an issue affecting ___ and are investigating. Next update in 30 minutes."* |

---

## Useful links

| | |
|---|---|
| Documentation | ___ |
| Runbook (engineering) | ___ |
| Release notes | ___ |
| Migration guide | ___ |
| Launch readiness report | ___ |
| Admin tool for looking up an account | ___ |
