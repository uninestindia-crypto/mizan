# G9 — Privacy, Legal & Compliance

> **Purpose.** Shipping this does not create a legal, regulatory, or ethical liability.
>
> **Veto holder.** The owner, with counsel where the stakes justify it.
> **Entry.** G8 passed. **Exit.** 16 checks resolved.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

> **This is not legal advice.** It is the engineering checklist that makes a legal review possible
> and cheap. Where a check says "identify the obligation", the deliverable is a written statement
> of what you believe applies and why — so a qualified person can confirm or correct it in ten
> minutes instead of two weeks. For anything involving health data, children, financial services,
> or biometrics, get an actual lawyer.

**Prerequisite.** G5.09, the PII inventory, must be complete. Every check here derives from it.

---

#### G9.01 · Privacy policy and Terms exist, reachable, and accurate — `S0` `manual`

- **Do** — read your own privacy policy next to the PII inventory from G5.09, line by line.
- **Pass** — the policy names every category of data you actually collect, every purpose, every third party you actually send it to, and a real retention period. It is reachable from the product without logging in. It has a "last updated" date that is not two years old.
- **The failure that matters** — a template policy saying "we do not share your data with third parties" while the app sends events to four analytics providers. That is not a paperwork problem; a policy that contradicts the code is the thing regulators fine people for.

#### G9.02 · Consent for non-essential tracking — `S0` `manual`

- **Pass** — non-essential cookies and trackers do **not** load before consent; "reject all" is as easy to click as "accept all"; the choice is remembered; withdrawing consent actually stops the tracking.
- **Verify it in devtools** — load the page in a clean profile, decline, and check the Network tab. If analytics requests fire anyway, the banner is decorative and provides no protection at all.
- **Where it applies** — the EU/UK (GDPR + ePrivacy), Brazil (LGPD), India (DPDP Act), California (CCPA/CPRA, with different rules), and a growing list of US states. If you have users anywhere in the EU, it applies to you regardless of where you are.

#### G9.03 · Data processing record and residency — `S0` `manual`

- **Do** — for each data category from G5.09, write: purpose, lawful basis (consent / contract / legitimate interest / legal obligation), retention period, and the physical region it is stored in.
- **Pass** — the table exists and someone can defend every row.
- **Data residency** — know which country your database, backups, logs, and analytics actually live in. "It's on AWS" is not an answer; the region is the answer. Some customers and some laws require specific regions.

#### G9.04 · Third-party data sharing disclosed, agreements in place — `S0` `manual`

- **Do** — list every third party that receives user data: analytics, error tracking, session replay, support chat, email, SMS, payments, AI/LLM APIs, CDNs, and any embedded widget.
- **Watch specifically for**: **session replay tools** (they record everything, including what users type into fields you thought were private); **error trackers** (stack traces routinely carry personal data in variables); and **LLM APIs** (check whether the provider trains on your inputs — for most enterprise tiers they do not, but the default consumer tier of some providers does).
- **Pass** — each is disclosed in the privacy policy, and a data processing agreement exists.

#### G9.05 · User rights work end to end — `S0` `hybrid`

- **Do** — actually exercise each right on a real test account, and time it:
  - **Access / export** — the user gets their data, in a usable format, within the statutory window.
  - **Correction** — they can fix wrong data.
  - **Deletion** — covered in G5.11; confirm it reaches backups, analytics, the CRM, the email provider, and logs, or that the retention of those copies is documented and justified.
  - **Objection / opt-out** — where it applies.
- **Pass** — each performed once, successfully, with the elapsed time recorded.
- **If any of these is a manual process** — that is acceptable at small scale, but it must be *documented*, and somebody must own it. An unowned manual process is an unmet obligation.

#### G9.06 · Retention policy implemented in code — `S1` `hybrid`

- **Pass** — data actually gets deleted when its retention period expires, proven by a job that runs or a test that demonstrates it. Logs rotate. Backups expire. Soft-deleted records eventually go.
- **Faked by** — a retention period stated in the policy and implemented nowhere. Keeping everything forever is a decision; make it deliberately, or make the deletion real.

#### G9.07 · Age gating / children's data — `S0` `manual`

- **Do** — decide whether minors can plausibly reach this product. If yes, identify the obligations (COPPA in the US for under-13; GDPR Article 8 in the EU for under-16 with member-state variation; the UK Age Appropriate Design Code).
- **Pass** — either "not reachable by minors, and here is why", or the requirements are identified and met.
- **App stores enforce this independently** of the law — an incorrect age rating gets a submission rejected.

#### G9.08 · Accessibility legal obligation stated — `S1` `manual`

- **Do** — state the target level (almost always **WCAG 2.1 or 2.2 Level AA**) and the driver: ADA/Section 508 (US), EN 301 549 and the European Accessibility Act (EU, in force since June 2025 for many consumer services), AODA (Ontario), the Equality Act (UK).
- **Pass** — the target is stated and G8 measured against it. Web accessibility lawsuits are common, cheap to file, and settle expensively.

#### G9.09 · Open-source licence obligations satisfied — `S1` `cmd`

- **Run** — `LRK run G9.09 -- npx license-checker --production --csv --out third-party-licenses.csv` (or `pip-licenses --format=csv`, `go-licenses csv ./...`, `cargo about generate`)
- **Pass** — an attribution file ships with the product. MIT, BSD, and Apache-2.0 all require the licence text and copyright notice to be distributed with your software. Nearly nobody does this, and it is a five-minute fix.
- **Also confirm** — no GPL/AGPL in anything proprietary, no SSPL in anything you offer as a service, and Apache-2.0's patent and NOTICE terms are honoured.

#### G9.10 · Name, logo, and domain checked for conflict — `S2` `manual`

- **Do** — search the relevant trademark registers (USPTO TESS, EUIPO, your own country's), plus a plain web search and an app-store search for the product name.
- **Pass** — no obvious conflict in your category. Finding this after launch means a rename, a domain change, an app-store resubmission, and every link on the internet pointing at the old name.

#### G9.11 · App store guidelines walked — `S0` `manual`

Applies to anything distributed through a store.

- **Do** — walk the actual guideline document (Apple App Review Guidelines; Google Play Developer Program Policies) section by section for your category.
- **The rejections that happen most**: an incomplete or inaccurate privacy nutrition label; a missing account-deletion path **inside the app** (Apple requires this if you allow account creation); external payment links for digital goods; missing demo credentials for the reviewer; a permission requested with no clear justification string; the app crashing on the reviewer's device because they tested a path you did not.
- **Pass** — walked, with the risky items listed and addressed. Budget for at least one rejection; plan the timeline around it.

#### G9.12 · Payment compliance scope stated — `S0` `manual`

- **Pass** — you can state, in one sentence, why raw card data never touches your servers: *"Card details are entered into a Stripe-hosted Elements iframe; our servers only ever see a token; we are SAQ-A scope."*
- **If raw card data does touch your servers, stop.** That is full PCI-DSS scope: quarterly scans, annual assessment, network segmentation, and a compliance programme. Nearly every product should be using a hosted field or a redirect so that the answer is no.
- **Also** — no card number, CVV, or full track data in logs, error reports, session replays, or analytics. Search for it: `git grep -niE "cvv|card_number|cardnumber|pan\b"`.

#### G9.13 · Regulated-domain requirements identified — `S0` `manual`

- **Do** — determine whether the product touches a regulated domain and state what applies:
  - **Health** — HIPAA (US, if you are a covered entity or business associate), and a BAA with every vendor touching PHI.
  - **Finance / lending / payments** — money transmission licensing, KYC/AML, local financial regulator rules.
  - **Education** — FERPA (US), COPPA for younger students.
  - **Employment / hiring** — EEOC, plus algorithmic hiring rules (NYC Local Law 144 requires bias audits).
  - **Biometrics** — BIPA (Illinois) has statutory damages per violation and has produced enormous settlements.
  - **AI features** — the EU AI Act's transparency obligations; disclosure requirements for automated decisions.
- **Pass** — either "none apply, and here is the reasoning", or the obligations are named and addressed.

#### G9.14 · Security contact and disclosure policy published — `S1` `hybrid`

- **Run** — `LRK run G9.14 -- curl -s https://<host>/.well-known/security.txt`
- **Pass** — a `security.txt` exists with a monitored contact address, or the contact is otherwise published.
- **Why** — without it, a researcher who finds a vulnerability either gives up or posts it publicly. A monitored `security@` address is the cheapest security control that exists.

#### G9.15 · Breach notification procedure written — `S0` `manual`

- **Pass** — a written procedure covering: who decides that an incident is a breach; who must be notified (regulators, users, customers, insurers); the deadline (**72 hours** to the supervisory authority under GDPR — it arrives fast); who drafts the notice; and where the contact list lives.
- **Write it now, not during.** The 72-hour clock starts when you become aware, not when you finish investigating, and nobody writes a good procedure at hour six of an incident.

#### G9.16 · Telemetry audited — `S0` `hybrid`

- **Run** —
  ```bash
  LRK run G9.16 -- git grep -nE "(log|logger|console|track|analytics|capture)\.[a-z]+\(.*(email|password|token|ssn|phone|address|card|dob|name)" -- .
  ```
- **Then look at the actual output** — trigger a login, an error, and a purchase, then read the real log lines and the real analytics payloads. Do not reason about what should be there; look at what is.
- **Pass** — no personal data, no secrets, no tokens, no full request bodies containing user input. Every collected analytics field is justified and disclosed in the policy.
- **The three places PII leaks by accident**: (1) an error tracker capturing local variables, (2) an HTTP logger dumping full request bodies, (3) a session replay tool with insufficient masking. All three are on by default in their respective products.

---

## Exit bar for G9

```bash
LRK status --gate G9
```

The test for this gate: **could you hand the report's G9 section to a lawyer and have them give you
a yes/no in an hour, rather than starting a discovery project?** If yes, you have done the
engineering half of compliance, which is the half that is actually your job.

Nothing here needs to be perfect. It needs to be **known**. An identified, accepted risk with a
name on it is a business decision. An unidentified one is a liability that surfaces at the worst
possible time — usually during a customer's security review, three days before a contract closes.
