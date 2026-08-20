# G4 — Security

> **Purpose.** A motivated stranger cannot read, write, or break what is not theirs.
>
> **Veto holder.** Security reviewer — someone who did not write the code.
> **Entry.** G3 passed. **Exit.** 28 checks resolved. This is the largest gate, and correctly so.

`LRK` = `python "<SKILL_DIR>/scripts/lrk.py"`.

**Scope statement.** This is a readiness review of software the operator owns and is preparing to
launch. Every probe below is run against your own system, in a non-production or pre-production
environment, with the owner's authorisation. Do not run these against anything you do not own.

**Read this before you start.** Authorization bugs — G4.01 through G4.06 — are the ones that
actually leak customer data. Injection and XSS get the headlines; broken access control is what
appears in the breach notification. Spend your time proportionally: those six checks deserve more
of your day than the other twenty-two combined.

---

## Access control — the six that matter most

#### G4.01 · Every protected route denies unauthenticated access — `S0` `cmd`

- **Do** — enumerate every route. Do not guess; extract them:
  ```bash
  LRK run G4.01 --title "route inventory" -- git grep -nE "(app|router)\.(get|post|put|patch|delete)\(|@(Get|Post|Put|Patch|Delete)\(|path\(|@app\.route|r\.(GET|POST)" -- .
  ```
  Then call each one with **no credentials at all** and record the status:
  ```bash
  LRK run G4.01 --title "unauth probe" -- bash -c 'for p in /api/users /api/orders /api/admin /api/export; do printf "%s -> " "$p"; curl -s -o /dev/null -w "%{http_code}\n" "$BASE$p"; done'
  ```
- **Pass** — every protected route returns 401 or 403. **Not 200. Not 500. Not a redirect that still includes the data in the body.**
- **Check the edges** — trailing slash (`/api/admin/`), different case (`/API/admin`), URL-encoded path (`/api/%61dmin`), an alternate HTTP method (`HEAD`, `OPTIONS`), and the version prefix (`/v1/` vs `/v2/`). Route guards attached by string prefix miss all of these.

#### G4.02 · Authorization matrix, as a table-driven test — `S0` `cmd`

- **Do** — write the matrix down first: every role × every resource × every action (read, write, delete, list, export).
  ```
              own.read  own.write  other.read  other.write  admin.read
  viewer         Y         N           N           N            N
  editor         Y         Y           N           N            N
  admin          Y         Y           Y*          Y*           Y
  anonymous      N         N           N           N            N
  ```
- **Then implement it as one table-driven test** and run it: `LRK run G4.02 -- <test command> -- <authz test path>`
- **Pass** — every cell is asserted. A matrix with 4 roles × 6 resources × 5 actions is 120 assertions, and a table-driven test writes them in twenty lines.
- **Faked by** — testing that admin can do things and that anonymous cannot. The interesting cells are in the middle.

#### G4.03 · Cross-tenant READ blocked — `S0` `cmd`

- **Do** — create tenant A and tenant B with real data in each. Authenticated as B, attempt to read every one of A's resources by ID, by list, by search, by export, and by any related object.
- **Pass** — every attempt denied.
- **The indirect paths people forget** — a search result; a CSV export; an aggregate count; an error message that says "record exists but you lack permission"; an autocomplete endpoint; an audit log; a webhook payload; a shared parent object's `children` array.

#### G4.04 · Cross-tenant WRITE blocked — `S0` `cmd`

- **Do** — the same, but writing: update, delete, and re-parent A's records while authenticated as B.
- **Pass** — every attempt denied.
- **Why this is a separate check** — read isolation is usually implemented and write isolation is routinely forgotten, because the write path goes through a different code branch and the developer only tested the read.

#### G4.05 · IDOR — `S0` `cmd`

- **Do** — take a real object ID from account A. As account B, request it directly on every endpoint that accepts an ID. Then increment and decrement the ID and try again. Then try `0`, `-1`, and a UUID from another table.
- **Pass** — 403 or 404 every time (404 is preferable: it does not confirm existence).
- **Sequential integer IDs** are not themselves a vulnerability, but they turn one authorization bug into a full database export in an afternoon.

#### G4.06 · Privilege escalation blocked — `S0` `cmd`

- **Do** — as a low-privileged user, attempt each of these:
  - `PATCH /api/users/me` with `{"role":"admin"}` or `{"isAdmin":true}` (**mass assignment** — the most common escalation in existence)
  - Change your own `tenant_id` / `organization_id`
  - Invite yourself to another organisation, then accept
  - Set `"id"` in a create request to overwrite an existing record
  - Send admin-only fields in a normal update; confirm they are stripped, not honoured
- **Pass** — every attempt rejected, and the field is *ignored or rejected*, never silently applied.

---

## Session, credentials, and transport

#### G4.07 · Session handling — `S0` `hybrid`

- **Test** — the token expires at the stated time; logging out invalidates it **server-side** (replay the old token afterwards and confirm it fails); the session rotates on privilege change and on password change; cookies carry `Secure`, `HttpOnly`, and `SameSite=Lax` or `Strict`.
- **Run** — `LRK run G4.07 -- curl -sI "$BASE/api/login" | grep -i set-cookie`
- **Faked by** — a logout that only clears the cookie client-side. The token is still valid; anyone who captured it still has an account.

#### G4.08 · Credential storage — `S0` `hybrid`

- **Run** — `LRK run G4.08 -- git grep -nE "md5|sha1|sha256\(.*password|createHash|crypt\(|base64.*password" -- .`
- **Pass** — passwords hashed with **argon2id, bcrypt, or scrypt** at a current cost factor. Never MD5, SHA-1, SHA-256, or anything reversible. Reset tokens are single-use, expiring, and cryptographically random.
- **Also confirm** — the password is never logged, never returned in an API response, and never included in an error message.

#### G4.17 · TLS valid — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G4.17 -- bash -c 'echo | openssl s_client -connect <host>:443 -servername <host> 2>/dev/null | openssl x509 -noout -subject -issuer -dates'
  LRK run G4.17 --title "http redirects to https" -- curl -sI http://<host> | head -5
  ```
- **Pass** — valid chain, TLS 1.2 minimum, HTTP redirects to HTTPS, no mixed content in the browser console, and **the expiry date is recorded** so somebody can renew it before it takes the site down at 4am on a Sunday.

#### G4.16 · Security headers — `S1` `cmd`

- **Run** — `LRK run G4.16 -- curl -sI https://<host> | grep -iE "strict-transport|content-security|x-content-type|x-frame|frame-ancestors|referrer-policy|permissions-policy"`
- **Pass** — all present:

| Header | Minimum acceptable value |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `Content-Security-Policy` | A real policy. **`unsafe-inline` on `script-src` means you do not have one.** |
| `X-Content-Type-Options` | `nosniff` |
| `Content-Security-Policy: frame-ancestors` | `'none'` or an explicit list (replaces `X-Frame-Options`) |
| `Referrer-Policy` | `strict-origin-when-cross-origin` or tighter |
| `Permissions-Policy` | Deny camera, microphone, geolocation unless used |

#### G4.18 · CORS not a wildcard with credentials — `S0` `hybrid`

- **Run** — `LRK run G4.18 -- curl -sI -H "Origin: https://evil.example" https://<host>/api/me | grep -i access-control`
- **Pass** — the response does **not** reflect an arbitrary origin, and `Access-Control-Allow-Credentials: true` never appears alongside `Access-Control-Allow-Origin: *` or a reflected origin. Reflecting the request origin is functionally identical to a wildcard.

---

## Injection and input handling

#### G4.09 · Injection: every query parameterised — `S0` `cmd`

- **Run** —
  ```bash
  LRK run G4.09 -- git grep -nE "(query|execute|exec|raw|\\\$queryRaw|createQueryBuilder)\(.*(\+|\\\$\{|%s|f\"|\.format\()" -- .
  LRK run G4.09 --title "shell injection" -- git grep -nE "exec\(|execSync\(|spawn\(.*shell|os\.system|subprocess.*shell=True|eval\(|Function\(" -- .
  ```
- **Pass** — no query built by string concatenation or interpolation with user input; no shell command built from user input.
- **Then probe** — send `' OR '1'='1`, `'; DROP TABLE users;--`, `1' UNION SELECT NULL--`, and `{"$ne":null}` (NoSQL) into every input, including headers, cookies, and JSON fields.

#### G4.10 · XSS — `S0` `hybrid`

- **Do** — inject `<script>alert(1)</script>`, `"><img src=x onerror=alert(1)>`, and `javascript:alert(1)` into every field, then view the field everywhere it is displayed: the list, the detail page, the export, the email, the admin panel, and the PDF.
- **Run** — `LRK run G4.10 -- git grep -nE "dangerouslySetInnerHTML|innerHTML\s*=|v-html|\|safe|\{\{\{|document\.write|insertAdjacentHTML" -- .`
- **Pass** — output encoded everywhere; every raw-HTML sink is sanitised with a real sanitiser; CSP present without `unsafe-inline`.
- **Stored XSS is the dangerous one** — it fires for the *next* person who views the record, which is frequently an administrator with more privileges than the attacker.

#### G4.11 · CSRF protection — `S0` `hybrid`

- **Do** — take a state-changing request. Replay it from a different origin without the CSRF token.
- **Pass** — rejected. Cookie-authenticated APIs need CSRF tokens or strict `SameSite`. Bearer-token APIs are structurally immune — confirm which you are.

#### G4.12 · SSRF — `S0` `hybrid`

- **Do** — find every place a user-supplied URL is fetched server-side: webhooks, avatar-by-URL, "import from link", PDF generators, link previews, OAuth redirect handlers.
- **Probe with** — `http://169.254.169.254/latest/meta-data/` (cloud credentials), `http://metadata.google.internal/`, `http://localhost:6379`, `http://127.0.0.1:22`, `file:///etc/passwd`, and a redirect chain that starts external and ends internal.
- **Pass** — blocked by an allowlist, not a denylist. Denylists lose to DNS rebinding, decimal-encoded IPs, and IPv6 forms.
- **Why it is S0** — a working SSRF against a cloud metadata endpoint is a full infrastructure compromise, not a bug.

#### G4.13 · Path traversal — `S0` `hybrid`

- **Do** — anywhere a filename or path comes from input, send `../../../etc/passwd`, `..\..\..\windows\win.ini`, `%2e%2e%2f`, and a filename containing a null byte.
- **Pass** — resolved paths are confirmed to be inside the intended directory *after* normalisation.

#### G4.14 · Deserialization, prototype pollution, mass assignment — `S0` `hybrid`

- **Probe** — send `{"__proto__":{"isAdmin":true}}` and `{"constructor":{"prototype":{"isAdmin":true}}}`; send extra fields on every create and update; check for `pickle.loads`, `yaml.load` without `SafeLoader`, `unserialize()`, and Java native deserialization on untrusted input.
- **Pass** — extra fields rejected or stripped by an explicit allowlist; no unsafe deserializer touches user data.

#### G4.15 · Rate limiting and brute-force protection — `S0` `hybrid`

- **Run** — `LRK run G4.15 -- bash -c 'for i in $(seq 1 60); do curl -s -o /dev/null -w "%{http_code} " -X POST "$BASE/api/login" -d "email=a@b.c&password=wrong$i"; done; echo'`
- **Pass** — the response codes shift to 429 well before 60 attempts, and the limit is per-account **and** per-IP.
- **Also rate-limit** — password reset, OTP verification, signup, search, export, and any endpoint that sends an email or costs money per call.
- **The bill attack** — an unlimited endpoint that calls a paid API is a way for a stranger to spend your money at machine speed.

#### G4.21 · Upload security — `S0` `hybrid`

- **Pass** — content type **and** magic bytes validated; extension allowlisted (never denylisted); size capped before the file is buffered; stored outside the web root or in object storage with no execute permission; served with `Content-Disposition: attachment` and a non-executable content type; filename regenerated server-side, never trusted; if virus scanning is claimed anywhere, prove it with the EICAR test file.

---

## Infrastructure, supply chain, and the review itself

#### G4.19 · Secrets management — `S0` `manual`

- **Pass** — every runtime secret comes from an environment variable or a secret manager; none is in the repository (cross-checks G1.10/G1.17); a rotation procedure is written down; production secrets differ from staging secrets.
- **Record** — where secrets live, who can read them, and how they are rotated.

#### G4.20 · Error responses leak nothing — `S0` `cmd`

- **Run** — with the app in **production mode**, trigger errors and read the responses:
  ```bash
  LRK run G4.20 -- bash -c 'curl -s "$BASE/api/orders/not-a-uuid"; echo; curl -s -X POST "$BASE/api/orders" -H "Content-Type: application/json" -d "{bad json"; echo; curl -s "$BASE/nonexistent-page" | head -30'
  ```
- **Pass** — no stack trace, no SQL fragment, no file path, no framework name or version, no dependency version, no internal hostname.
- **Faked by** — testing in development mode, where verbose errors are expected and correct.

#### G4.22 · Supply chain — `S1` `cmd`

- **Run** — `LRK run G4.22 -- npm ci --ignore-scripts --dry-run` and generate an SBOM: `npx @cyclonedx/cyclonedx-npm --output-file sbom.json` / `syft . -o cyclonedx-json`.
- **Pass** — lockfile integrity verified; no unexpected `postinstall` scripts from packages you do not recognise; SBOM generated and attached.
- **Attach the SBOM** — `LRK attach G4.22 ./sbom.json --caption "CycloneDX SBOM"`. Increasingly this is a customer and procurement requirement, not just good practice.

#### G4.23 · Admin surfaces protected — `S0` `hybrid`

- **Do** — try to reach `/admin`, `/wp-admin`, `/.env`, `/actuator`, `/debug`, `/graphql` (introspection), `/swagger`, `/api-docs`, `/metrics`, `/.git/config`, `/phpinfo.php` while unauthenticated.
  ```bash
  LRK run G4.23 -- bash -c 'for p in /admin /.env /.git/config /actuator/env /debug /metrics /swagger /api-docs /graphql; do printf "%s -> " "$p"; curl -s -o /dev/null -w "%{http_code}\n" "$BASE$p"; done'
  ```
- **Pass** — 404 or 401 for all. **`/.git/config` returning 200 means your entire source history is downloadable.**
- **Also** — every default credential removed; no `admin/admin`; no seeded demo account with a known password (cross-checks G5.12).

#### G4.24 · Audit log — `S1` `hybrid`

- **Pass** — login, failed login, permission change, data export, and deletion are all recorded with actor, timestamp, and target; the log is append-only or tamper-evident; it does not itself contain secrets.
- **Why** — without this, the answer to "what did the attacker access?" is "we don't know", which converts a contained incident into a full breach notification.

#### G4.25 · Automated security scan run — `S0` `cmd`

- **Run** at least one, ideally all three categories:
  ```bash
  LRK run G4.25 --title "dependency scan" -- <audit command from G1.12>
  LRK run G4.25 --title "SAST"            -- semgrep --config=auto --error .
  LRK run G4.25 --title "DAST baseline"   -- docker run --rm -t ghcr.io/zaproxy/zaproxy zap-baseline.py -t https://<staging-host>
  ```
- **Pass** — run, output attached, every finding triaged as fixed, false positive (with reasoning), or waived.
- **A scan with no findings on a real application usually means the scan did not run properly.** Check the log.

#### G4.26 · Human security review of the release diff — `S0` `manual`

- **Do** — a line-by-line read of everything changing in this release, by someone who did not write it. If a `/security-review` command exists in this environment, run it. Focus on: new endpoints, changed authorization logic, new dependencies, anything touching authentication, anything constructing a query or a path, and anything new in the config.
- **Record** — `LRK manual G4.26 --status pass --note "Reviewed 41 files / 1,208 lines. 3 findings: (1) missing tenant filter on /api/reports — FIXED + test; (2) verbose error in the webhook handler — FIXED; (3) new dep 'fast-csv' reviewed, maintained, MIT." --attach security-review.md`

#### G4.27 · Webhook signature verification and replay protection — `S0` `hybrid`

- **Do** — send an inbound webhook with (a) no signature, (b) a wrong signature, (c) a valid signature but a timestamp two hours old, (d) an exact replay of a previously accepted payload.
- **Pass** — all four rejected. Signature comparison uses a constant-time function.
- **Why it is S0 for payments** — an unverified payment webhook lets anyone mark any order as paid by sending you a POST.

#### G4.28 · API keys scoped, expiring, revocable — `S1` `hybrid`

- **Pass** — keys carry a scope rather than full account access; they can be listed and revoked by the user; revocation takes effect immediately (test it: revoke, then replay); keys are displayed once and stored hashed, not in plaintext.

---

## Exit bar for G4

```bash
LRK status --gate G4
```

Every S0 in this gate must be EXECUTED or ATTACHED — never ASSERTED. A security section built on
"reviewed, looks fine" is the section that gets quoted in the incident report.

**If you fix something during this gate, re-run the probe that found it.** A security fix made
under time pressure is precisely the code most likely to be wrong.
