# 04 — Data protection

**Data you do not hold cannot leak** (Law 6). Every field of personal data is a liability with a
retention cost, a breach cost, and a regulatory cost — not an asset you accumulate by default.

---

## 1. Collect less

Before adding a field, ask: **what breaks if we do not have this?** If the answer is "nothing
today", do not collect it.

- **Do not collect "in case it is useful later."** Later, it is a breach disclosure line item.
- **Do not store what you can derive** — store a birthdate if you need age verification, or store
  only `isOver18` if that is genuinely all you need.
- **Never store what you can avoid touching at all**: full card numbers (use the payment provider's
  token), government ID numbers (use a verification provider's result), raw biometrics.
- **Truncate at the boundary.** If you need the last four digits, store four digits.

## 2. Classify what you hold

Write it down once, per field. Without a classification, every later decision is a guess.

| Class | Examples | Treatment |
|---|---|---|
| **Public** | Product names, docs | None |
| **Internal** | Aggregate metrics | Access-controlled |
| **Personal** | Name, email, address, IP | Encrypted at rest, access-logged, retention limit |
| **Sensitive** | Health, financial, biometric, precise location, credentials | All the above + encryption in transit and at rest, strict least-privilege, audit trail |

**IP addresses and device identifiers are personal data** in most jurisdictions. So are behavioral
logs tied to an account.

## 3. Encryption

- **In transit: TLS everywhere**, including internally (`03-secrets.md` §7). Never disable
  verification.
- **At rest: use the platform's encryption** — disk/volume encryption, database-level encryption,
  the provider's managed keys. It is nearly free and it covers the stolen-backup case.
- **Field-level encryption** for the most sensitive columns, so a database dump is not enough. Costs
  you the ability to query those fields — decide deliberately.
- **Never write your own crypto** (Law 7). Use the platform's library, its defaults, and an
  authenticated mode (AES-GCM, libsodium, `crypto.subtle`). ECB is not encryption in any useful
  sense.
- **Key management is the hard part.** Keys live in a KMS or secret manager, never beside the data
  they protect. Plan key rotation before you need it.

**Hashing is not encryption.** A hash is one-way and correct for passwords. Encryption is
reversible and correct for data you must read back. Using one where the other belongs is a common
and serious mistake.

## 4. Retention and deletion (Law 6)

- **Every personal-data field has a retention period**, written down, with an owner.
- **Automate deletion.** A policy nobody enforces is a document, not a control.
- **Deletion must be real.** Check every copy: the primary store, replicas, backups, search
  indexes, caches, analytics warehouse, logs, error tracker, email/CRM, and third-party processors.
  A "deleted" record that survives in the analytics warehouse is not deleted.
- **Soft deletes are not deletion.** They are useful operationally, and they satisfy no privacy
  obligation. Have a hard-delete path.
- **Backups need a stated approach** — you usually cannot surgically delete from an immutable
  backup, so document the maximum window until it ages out, and be able to say it accurately.

## 5. Access to production data

- **Least privilege, always.** Most engineers do not need production data access; the ones who do
  need it for a bounded reason.
- **Just-in-time access** with an expiry, an approver, and a recorded reason beats standing access.
- **Every access is logged** — who, what, when, why — and the log is reviewed by someone.
- **Never copy production data to development or staging.** Not "temporarily", not "just one
  table". It becomes permanent, it lands on laptops, and it is a breach waiting for a misconfigured
  bucket. Generate synthetic data, or anonymize irreversibly.

**Anonymization is harder than it looks.** Removing names is not anonymization; a handful of
quasi-identifiers (postcode, birthdate, sex) re-identifies most people. If the data must remain
useful, it is probably still personal data — treat it as such.

## 6. Logging personal data (Law 9)

Logs leak more personal data than databases do, because nobody classifies them and everyone ships
them somewhere else.

- **Log identifiers, not contents.** `userId: "u_91"`, never the email, the name, or the message
  body.
- **Never log a full request or response body.**
- **Redaction at write time** (`project-zero/assets/logger.ts`), so a careless log statement does
  not become a leak.
- **Error trackers and APM receive whatever you send.** Configure scrubbing, and verify it by
  triggering a real error with a real-looking payload.
- **Logs need a retention period too**, and it is usually far shorter than people assume.

## 7. Data subject rights

If you serve users in a jurisdiction with privacy law — most of them — you need working mechanisms,
not intentions:

- **Access/export:** produce everything you hold about a person, in a portable format.
- **Deletion:** remove it everywhere (§4), and confirm.
- **Correction:** fix inaccurate data.
- **Consent:** where you rely on it, record what was consented to and when, and make withdrawal as
  easy as granting.

**Build the export and delete paths early.** Retrofitting them across fifteen systems under a
30-day statutory deadline is how a small team loses a month.

## 8. Third parties are extensions of your surface

Every processor — analytics, error tracking, support, email, payments — receives your users' data
and inherits your obligation.

- **Inventory them.** You cannot protect what you have not listed.
- **Send only what each one needs.** An error tracker does not need an email address.
- **Data processing agreements** where the law requires them.
- **Check data residency** if your users are in a region with transfer restrictions.
- **Remove integrations you stopped using** — the token still works, and the data is still there.

## 9. Breach readiness

Decide these before you need them, because during an incident there is no time:

- **How would you detect it?** Unusual export volume, access anomalies, an alert on the audit log.
- **Who is called, and in what order?**
- **What is the notification obligation and clock?** (72 hours under GDPR, from awareness.)
- **Can you answer "whose data, and what fields"?** That question is answerable only if you have an
  audit trail and a data classification. Without them, the honest answer is "we cannot tell", and
  that answer is far more damaging than the breach.
