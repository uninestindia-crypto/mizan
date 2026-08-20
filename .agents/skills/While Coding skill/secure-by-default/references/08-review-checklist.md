# 08 — The security review checklist

Walk this before shipping anything that touches the surface. Every line passes or you state the
exception and why.

Automated first — it clears the mechanical failures so review can spend attention on the rest:

```bash
node scripts/check-security.mjs
```

Then the project's dependency audit and a **history-aware** secret scanner. The scanner above sees
the working tree only; a secret committed and later deleted is still in the history.

---

## The four questions

- [ ] **Who can call this?**
- [ ] **What can they reach through it?**
- [ ] **What happens if the input is hostile?**
- [ ] **What is the worst outcome if this is wrong?**

If the worst outcome involves money, personal data, or someone else's account, every section below
applies.

## Identity and access (Law 2 — the highest-value section)

- [ ] Authorization checked on **every** request, at the server
- [ ] Checked on the **object**, not just the role — this user, this object, this action
- [ ] Queries scoped by owner/tenant in the `WHERE` clause, not filtered afterwards
- [ ] **IDOR tested deliberately**: as user A, request user B's object → 403/404
- [ ] Cross-tenant access has a permanent test, for every resource
- [ ] Background jobs, exports, reports, and admin paths carry the same scoping
- [ ] Fails closed — an error, a missing rule, or an unknown state denies
- [ ] No mass assignment: the request may only set allowlisted fields
- [ ] Sensitive actions re-authenticate
- [ ] Sessions invalidated on password change; "sign out everywhere" works
- [ ] Password hashing is bcrypt/scrypt/Argon2 with library defaults — never MD5/SHA
- [ ] Tokens: algorithm pinned, signature verified before reading claims, `exp`/`iss`/`aud` checked
- [ ] No token in a URL

## Input and injection (Laws 1, 3)

- [ ] Validated at the boundary into a trusted type; interior trusts it
- [ ] Allowlist, not blocklist; canonicalize **before** validating
- [ ] Length, size, range, array count, and nesting depth all bounded
- [ ] Unknown fields rejected, not ignored
- [ ] **Every query parameterized** — no concatenation, no interpolation, no f-strings
- [ ] Dynamic identifiers (table, column, sort direction) come from an allowlist
- [ ] Commands use an argument array; no `shell=True`; no string-built commands
- [ ] Output escaped in the **context** of use; framework escaping not defeated
- [ ] No `innerHTML` / `dangerouslySetInnerHTML` / `v-html` / `|safe` with user content
- [ ] Paths resolved then containment-asserted; better, no user input in paths at all
- [ ] SSRF: destinations allowlisted or private ranges blocked, resolved IP validated, redirects
      disabled
- [ ] No deserialization of untrusted data (`pickle`, `yaml.load`, native serialization)
- [ ] Client-side validation is duplicated server-side

## Secrets (Law 4)

- [ ] No credential, key, or token in source, config, image, URL, log, or error message
- [ ] `.env` is gitignored; `.env.example` committed with no real values
- [ ] Secrets come from the platform's secret manager in production
- [ ] Any leaked secret was **rotated**, not just deleted
- [ ] Secret scanning runs in CI with full history
- [ ] Rotation procedure exists and has been executed
- [ ] TLS verification never disabled — no `verify=False`, `rejectUnauthorized: false`,
      `InsecureSkipVerify: true`

## Data protection (Law 6)

- [ ] Collecting only what is needed; nothing "in case it is useful later"
- [ ] Fields classified; sensitive data identified
- [ ] Encrypted in transit and at rest; platform crypto, never hand-rolled
- [ ] Retention period defined and **automated**
- [ ] Deletion reaches every copy: replicas, backups, indexes, caches, warehouse, logs, third parties
- [ ] **No production data in development or staging**
- [ ] Logs carry identifiers, not contents; redaction verified by triggering a real error
- [ ] Export and delete paths exist and work

## Dependencies (Law 8)

- [ ] Lockfile committed; CI installs from it exactly
- [ ] Dependency audit in CI, failing at high and above
- [ ] Automated update PRs enabled; updates merged regularly
- [ ] New dependencies justified — maintained, reasonable transitive tree, correct name
- [ ] CI actions pinned by SHA; base images pinned by digest
- [ ] CI runs least-privilege; secrets withheld from fork PRs
- [ ] Unused dependencies removed

## Files (if the product accepts uploads)

- [ ] Size capped at the edge and in the app
- [ ] Type verified by content, not by extension or `Content-Type`
- [ ] Stored under a generated name, outside the web root, non-executable
- [ ] Served from a separate origin, with `nosniff` and attachment disposition
- [ ] SVG sanitized, served as attachment, or refused
- [ ] Authorization checked on download
- [ ] EXIF stripped from public images; processing sandboxed with limits

## Web surface (if there is a browser)

- [ ] HSTS, `nosniff`, CSP, `Referrer-Policy`, `frame-ancestors` all set globally
- [ ] CSP has no `'unsafe-inline'` in `script-src`
- [ ] CORS: exact-match allowlist; never `*` with credentials; never reflected unchecked
- [ ] Cookies `HttpOnly`, `Secure`, `SameSite`, scoped `Path`
- [ ] CSRF protection on cookie-authenticated state changes; `GET` never changes state
- [ ] Redirect targets allowlisted or relative-only
- [ ] Rate limits on authentication and expensive endpoints; limiter fails closed
- [ ] **Debug mode off in production** — verified, not assumed
- [ ] No stack traces to users; no session token in `localStorage`; no secrets in client code

## Logging and detection (Law 9)

- [ ] Auth outcomes, permission changes, denials, exports, and admin actions are logged
- [ ] Who, what, when, from where — enough to answer "what did they reach?"
- [ ] No secrets, tokens, passwords, or full bodies in any log
- [ ] Someone would actually notice: an alert exists for anomalous access or export volume

## Before you report done

- [ ] `node scripts/check-security.mjs` clean, or findings annotated with reasons
- [ ] Dependency audit and history-aware secret scan pass, **with output seen**
- [ ] Authorization tested by *attempting* the unauthorized action, not by reading the code
- [ ] Anything skipped is stated explicitly, with the reason

**An unverified security claim is an unsupported claim.** "It should be safe" is the sentence that
precedes most disclosures. The only evidence that an access control works is having tried to defeat
it and failed.
