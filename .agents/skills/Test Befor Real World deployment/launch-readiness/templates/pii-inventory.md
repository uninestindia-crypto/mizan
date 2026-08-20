# Personal Data Inventory — <PRODUCT>

> For gate **G5.09**. Every check in G9 derives from this table, so do it first and do it properly.
>
> Attach it: `LRK attach G5.09 ./pii-inventory.md`

---

## How to build this from the code, not from memory

```bash
# Column names that suggest personal data
<db client> -c "SELECT table_name, column_name, data_type FROM information_schema.columns
  WHERE column_name ~* '(email|phone|name|address|dob|birth|ssn|passport|ip|location|lat|lon|card|account|gender|photo|avatar|note|comment|bio)'
  ORDER BY table_name;"

# Free-text columns — these ALWAYS end up containing personal data,
# whatever the field was designed for
<db client> -c "SELECT table_name, column_name FROM information_schema.columns
  WHERE data_type IN ('text','json','jsonb') ORDER BY table_name;"

# Where does data leave your infrastructure?
git grep -ohE "https?://[a-zA-Z0-9.-]+" -- . | sort -u
```

---

## Inventory

| # | Data | Table.column | Why collected | Lawful basis | Retention | Encrypted? | Who can read | Leaves infra? |
|---|---|---|---|---|---|---|---|---|
| 1 | Email | `users.email` | Login, transactional mail | Contract | Life of account + 30d | At rest | User, support, admin | Yes — email provider |
| 2 | | | | | | | | |
| 3 | | | | | | | | |

**Lawful basis** (GDPR-style; adapt to your jurisdiction): Consent · Contract · Legal obligation ·
Vital interests · Public task · Legitimate interests.

*"We might need it later" is not a lawful basis, and it is the actual reason most fields exist.*

---

## Special-category data

Health, biometrics, genetics, race or ethnicity, religion, political opinions, trade-union
membership, sex life or sexual orientation, criminal records. **These carry substantially stricter
obligations in most jurisdictions.**

| Data | Where | Justification | Extra safeguards |
|---|---|---|---|
| | | | |

- [ ] None collected — and this was **verified by reading the schema**, not assumed.

---

## Data that arrives without anyone deciding to collect it

The three that surprise people, every time:

| Source | What it captures | Contains personal data? | Mitigation |
|---|---|---|---|
| **Error tracker** (Sentry, Rollbar…) | Stack traces with local variables, request bodies, user context | **Almost always yes** | Scrub rules configured, `sendDefaultPii` off |
| **HTTP request logs** | Full URLs with query strings, sometimes bodies, IP addresses | **Yes** | Redact params, truncate bodies, shorten IP retention |
| **Session replay** (FullStory, Hotjar, LogRocket…) | Literally everything on screen and typed | **Yes, comprehensively** | Mask all inputs by default, allowlist what is visible |
| Analytics | Device, IP, behaviour, sometimes user ID | Usually | Anonymise IP, no PII in event properties |
| Support chat | Whatever users paste — often passwords and card numbers | Yes | Retention policy, access control |
| LLM / AI API calls | Whatever is in the prompt | **Check what you are sending** | Redact before the call; verify the provider does not train on inputs |
| Backups | Everything, including data you deleted | Yes | Encryption; deletion policy must cover backups |
| CDN / edge logs | IPs, URLs, user agents | Yes | Retention setting |

- [ ] Each of the above has been checked by looking at **real captured data**, not by reading configuration.

---

## Third parties receiving personal data

| Processor | What they get | Why | Region | Agreement in place | Disclosed in policy |
|---|---|---|---|---|---|
| | | | | | |

---

## Residency

| Store | Physical region | Requirement |
|---|---|---|
| Primary database | | |
| Backups | | |
| Object storage | | |
| Logs | | |
| Analytics | | |
| Error tracking | | |

*"It's on AWS" is not an answer. The region is the answer, and backups frequently live somewhere
different from the primary.*

---

## Deletion — what actually happens

When a user deletes their account:

| Store | Deleted? | When | How verified |
|---|---|---|---|
| Primary database | | | |
| Backups | | Expire after ___ | |
| Object storage | | | |
| Analytics | | | |
| Error tracker | | | |
| Email provider | | | |
| CRM / support tool | | | |
| Logs | | Rotate after ___ | |

- [ ] Deletion has been performed once, end to end, on a real test account, and each row above verified. (G5.11 / G9.05)

**Anything that survives deletion, and the justification for it:**
> ___

---

## Retention

| Category | Kept for | Why | Enforced by |
|---|---|---|---|
| Active account data | Life of account | Contract | — |
| Deleted account data | ___ days | Recovery window | ___ |
| Logs | ___ days | Debugging | Log rotation |
| Backups | ___ days | Disaster recovery | Lifecycle policy |
| Analytics | ___ | | |
| Financial records | Usually 6–7 years | Legal obligation | ___ |

- [ ] Each retention period is **implemented**, not merely stated. (G9.06)

---

## The minimisation question

For each row in the inventory: **what breaks if we stop collecting this?**

If the answer is "nothing", delete the field. Every personal datum you do not hold is one you
cannot leak, cannot be compelled to produce, do not have to protect, and do not have to delete on
request.

| Field | What breaks if removed | Keep? |
|---|---|---|
| | | |
