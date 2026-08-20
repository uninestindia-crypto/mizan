---
name: secure-by-default
description: >-
  The concrete security bar for building software, in any language and any product. Load this BEFORE
  writing or changing anything touching authentication, authorization, user input, secrets, files,
  dependencies, or data that belongs to someone else. Triggers on: "auth", "authentication",
  "authorization", "login", "signup", "password", "session", "cookie", "token", "JWT", "OAuth",
  "SSO", "permission", "role", "admin", "tenant", "multi-tenant", "secret", "API key", "credential",
  "encrypt", "hash", "PII", "personal data", "GDPR", "sanitize", "escape", "validate input",
  "SQL injection", "XSS", "CSRF", "SSRF", "path traversal", "upload", "file upload", "CORS",
  "security headers", "rate limit", "dependency", "vulnerability", "CVE", "audit", "supply chain",
  "security review", "threat model", "is this safe". Owns the defensive controls: identity and
  access, input handling and injection, secret management, data protection, dependency and supply
  chain, file handling, and the web surface. Ships a scanner that finds hardcoded credentials and
  known-dangerous patterns in every language it recognizes. This is a build-time defensive bar for
  your own software — not offensive tooling. If you are about to concatenate user input into a
  query, check a permission only in the UI, log a token, or accept an upload without validating it,
  you needed this skill and did not load it.
---

# Secure by Default — The Defensive Bar

Security is not a review that happens near the end. It is a set of defaults that make the insecure
version harder to write than the secure one.

**The premise:** almost no breach involves a novel attack. It is a forgotten authorization check, a
credential in a repository, a dependency nobody updated, or a string concatenated into a query.
The controls below exist because those five things happen over and over.

**Scope of this skill:** defensive controls in software you are building. It is not an offensive
toolkit, and it does not replace a professional assessment for a system that genuinely warrants
one — it makes the routine failures stop happening, which is most of them.

## Scope — what this skill owns, and what it does not

| Concern | Owned by |
|---|---|
| Day-zero config contract, `.env.example`, secret scanning in CI | `project-zero` |
| Function shape, boundaries, error taxonomy | `code-craft` |
| Contract shape, rate limits as a contract feature, idempotency | `api-craft` |
| **The security controls themselves** — authn, authz, injection, secrets, data, deps, uploads | **this skill** |
| How much security testing is required, and its gates | `founder-mode` (R8) |

---

## The ten laws (non-negotiable)

**Law 1 — Never trust input, and "input" is broader than you think.**
Request bodies, query strings, headers, cookies, file names, file *contents*, environment variables,
webhook payloads, database rows written by another system, and anything a user can influence.
Validate at the boundary into a trusted shape, then trust it inside.

**Law 2 — Authorization is checked on every request, at the server, on the object.**
Not in the UI. Not once at login. Not "the button is hidden". Every request, for the specific
object, at the moment of use.

**Law 3 — Never build a query, command, path, or markup by concatenation.**
Parameterized queries, argument arrays, path joins with containment checks, contextual escaping.
There is a safe primitive for every one of these in every language.

**Law 4 — Secrets never touch source, logs, URLs, or error messages.**
A secret committed once is compromised forever — it is in the history, and the history is on every
clone. Rotate; deletion is not enough.

**Law 5 — Fail closed.**
An error in an authorization check denies access. A missing rule denies access. An unrecognized
state denies access. Defaults are the restrictive option, everywhere.

**Law 6 — Store only what you need, for only as long as you need it.**
Data you do not hold cannot leak. Every field of personal data is a liability with a retention
policy, not an asset.

**Law 7 — Use the boring, standard, maintained implementation.**
Never write your own crypto, session management, password hashing, or token verification. Use the
platform's, keep it current, and take its defaults unless you can state why not.

**Law 8 — Dependencies are code you did not review, running with your privileges.**
Pin them, audit them, update them on a schedule, and minimize how many you take on.

**Law 9 — Log the security events, never the secrets.**
Authentication outcomes, authorization denials, privilege changes, and data exports need an audit
trail. Tokens, passwords, keys, and full request bodies must never appear in it.

**Law 10 — Assume the client is hostile and the network is watching.**
Client-side validation is a convenience for honest users. Every rule is enforced again on the
server. TLS everywhere, including internally.

---

## Step 0 — Install the scanner (once per project, ~1 minute)

| Copy this file | To | Purpose |
|---|---|---|
| `scripts/check-security.mjs` | `scripts/check-security.mjs` | Finds hardcoded credentials, string-built queries and commands, disabled TLS verification, weak hashing, and unsafe deserialization |

```bash
node scripts/check-security.mjs
```

Run it in CI, and pair it with the project's dependency audit and a history-aware secret scanner
(`project-zero/assets/ci.github.yml` wires both).

**What it cannot check** is most of this document. Whether an authorization rule is *correct*,
whether a tenant boundary holds, whether the data model over-collects — those need judgment and a
threat model. The scanner removes the mechanical failures so review can spend attention on the
rest.

---

## Workflow — every change that touches the surface

### 1. Ask the four questions
Before writing: **Who can call this? What can they reach? What happens if the input is hostile?
What is the worst outcome if this is wrong?**

If the worst outcome involves money, personal data, or someone else's account, this change needs
the checklist rather than a glance.

### 2. Build with the safe primitive (Law 3)
Parameterized query. Argument array. Path join with a containment check. Contextual escaping. Reach
for these first, so the unsafe version is never written and never reviewed.

### 3. Check authorization at the object (Law 2)
Not "is this user an admin" but "may **this** user perform **this** action on **this** object,
right now".

### 4. Verify
```bash
node scripts/check-security.mjs
```
Then the project's dependency audit and secret scan, then `references/08-review-checklist.md`.

---

## What ships with this skill

| Path | What it is |
|---|---|
| `scripts/check-security.mjs` | The scanner: hardcoded credentials, injection-prone construction, disabled TLS verification, weak crypto, unsafe deserialization. Multi-language; `UNKNOWN` over guessing |

No code assets, deliberately: a canned auth implementation would be wrong in every framework and
would encourage exactly the hand-rolled security Law 7 forbids. **Use the platform's.**

## References — load what the task needs

| File | Load it when |
|---|---|
| `references/01-identity-and-access.md` | Login, sessions, tokens, permissions, tenancy — the highest-value file |
| `references/02-input-and-injection.md` | Any user input reaching a query, command, path, template, or browser |
| `references/03-secrets.md` | Any credential, key, or token — storage, rotation, and what to do after a leak |
| `references/04-data-protection.md` | Personal data, encryption, retention, deletion, logging |
| `references/05-dependencies.md` | Adding, updating, or auditing any third-party code |
| `references/06-files-and-uploads.md` | Accepting, storing, or serving any file |
| `references/07-web-surface.md` | Headers, CORS, CSRF, SSRF, clickjacking, cookies |
| `references/08-review-checklist.md` | Before shipping anything that touches the surface |

Related skills, where installed: `project-zero` (config contract, CI scanning), `api-craft` (rate
limits, error bodies that do not leak), `code-craft` (validate-at-the-boundary), `founder-mode`
(the R8 security ring and its gate). Not installed is not a blocker.

---

## The failure modes that give it away

- **An authorization check in the UI only.** The endpoint is the API; the button is decoration.
- **`WHERE id = ${userInput}`.** In any language, in any query builder.
- **An API key in the repository**, or in a `.env` that got committed once.
- **A token in a URL** — it lands in logs, proxies, browser history, and `Referer` headers.
- **Checking the role but not the object** — a valid admin of tenant A editing tenant B.
- **An IDOR**: `/orders/1042` returns someone else's order because only authentication was checked.
- **`verify=False`, `rejectUnauthorized: false`, `InsecureSkipVerify: true`** left in from debugging.
- **MD5 or SHA-1 for passwords**, or any unsalted fast hash.
- **Deserializing untrusted data** — `pickle`, Java native, `unserialize`.
- **An upload saved with the user's filename**, or served from the same origin.
- **An error page with a stack trace** in production.
- **A dependency lockfile three years old**, or none at all.
- **A password reset token that does not expire**, or is not single-use.

---

## Scope discipline

This skill makes software safer; it does not authorize a security theater project. Do not add a WAF
instead of fixing the query, do not roll your own crypto because a library felt heavy, and do not
gate a low-risk internal tool behind enterprise SSO because it felt more secure. **Most real
security is a small number of boring controls applied without exception** — the value is in the
"without exception", not in sophistication.
