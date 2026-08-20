# 01 — Identity and access

**The highest-value file in this skill.** Broken access control is consistently the most common
serious vulnerability in real applications, and it is almost never exotic — it is a check that was
not performed, or was performed in the wrong place.

---

## 1. Authentication vs authorization

- **Authentication** — who are you? Answered once per session.
- **Authorization** — may you do *this*, to *this object*, *right now*? Answered on **every
  request**.

Confusing them is the root of most access-control bugs. A valid token proves identity; it proves
nothing about permission.

## 2. Never build your own

**Law 7 without exception.** Use the platform's session management, the standard OAuth/OIDC library,
the maintained password hashing implementation. Every hand-rolled version has the same bugs, which
are well known to everyone except the author.

**Password storage:** bcrypt, scrypt, or Argon2id, with the library's default cost. Never MD5,
SHA-1, or SHA-256 — they are fast by design, which is precisely wrong. Never your own salting
scheme; the library handles it.

**Verify a password with a constant-time comparison.** A normal `==` leaks length and prefix through
timing.

## 3. Sessions and tokens

| Approach | Revocable | Use for |
|---|---|---|
| Server-side session + opaque cookie | Instantly | Web apps — the default |
| JWT (stateless) | **Not until expiry** | Short-lived service-to-service |
| Refresh + short access token | Refresh revocable | Mobile and SPA |

**The JWT trap:** a stateless token cannot be revoked. If you log someone out, ban an account, or
strip a permission, a valid JWT keeps working until it expires. Keep access tokens short (minutes),
put revocation on the refresh token, and check a server-side state for anything sensitive.

**If you verify JWTs yourself:** pin the algorithm (never trust the token's own `alg` header),
verify the signature before reading any claim, and check `exp`, `iss`, and `aud`. Accepting `alg:
none` is a classic, and it is still found in production.

**Cookies** carrying a session get `HttpOnly` (no script access), `Secure` (HTTPS only),
`SameSite=Lax` or `Strict` (CSRF defense), a scoped `Path`, and a sensible expiry.

**Never put a token in a URL.** URLs land in server logs, proxy logs, browser history, bookmarks,
and the `Referer` header sent to third parties.

## 4. Authorize on the object, not just the role (Law 2)

The most common real vulnerability, and the one automated scanners rarely find:

```
BAD    if (user.isAdmin) { return orders.find(req.params.id) }        // admin of WHAT?
BAD    if (isLoggedIn(req)) { return orders.find(req.params.id) }     // IDOR
GOOD   const order = orders.find(req.params.id)
       requireAccess(user, order, 'read')   // this user, this object, this action
```

**Insecure Direct Object Reference (IDOR):** `/orders/1042` returns someone else's order because
the code checked *authentication* and forgot *authorization*. Test it deliberately: log in as user
A, request user B's object, and confirm you get 403 or 404.

**Check at the point of use, not only at the route.** A route guard misses the second query inside
the handler, the batch endpoint, the export, the webhook, and the admin path added later.

**Prefer scoping the query to filtering afterwards:**

```
BEST   SELECT * FROM orders WHERE id = $1 AND tenant_id = $2
WEAK   SELECT * FROM orders WHERE id = $1     -- then check tenant in code
```

The first cannot leak, even if a later refactor drops the check. **Make the safe version the only
version.**

## 5. Multi-tenancy

If one customer can ever see another's data, that is the incident that ends the product.

- **Every query is scoped by tenant.** No exceptions, including reports, exports, admin tools, and
  background jobs.
- **Enforce it structurally**, not by discipline: row-level security, a repository layer that
  requires a tenant, or a query builder that refuses an unscoped query. A rule everyone must
  remember is a rule that gets forgotten in the sixth month.
- **The tenant comes from the session, never from the request.** A `tenantId` in the body or query
  string is a request to read someone else's data.
- **Test cross-tenant access explicitly**, as a permanent test, for every resource.
- Background jobs and migrations carry a tenant context too — they are the usual place the scoping
  is missing.

## 6. Fail closed (Law 5)

```
BAD    try { return checkPermission(u, o) } catch { return true }
BAD    if (rule === undefined) return true
GOOD   try { return checkPermission(u, o) } catch { return false }
```

An unrecognized role, a missing rule, an error in the check, a new resource type nobody added a
policy for — all deny. The failure mode of a security control must be *refusal*.

## 7. Privilege boundaries

- **Least privilege**, everywhere: the database user, the service account, the API token, the
  container. A service that only reads does not get write credentials.
- **Re-authenticate for sensitive actions** — changing a password, email, or payout account, or
  deleting an account. A stolen session should not be enough.
- **Separate the admin surface.** Admin capability inside the user-facing app is one authorization
  bug away from full compromise.
- **Never let a user grant themselves a privilege they lack**, including indirectly — by editing
  their own role, joining a group, or setting a field the API accepts but the UI hides. Mass
  assignment is the usual mechanism: **allowlist the fields a request may set.**

## 8. Account lifecycle

- **Rate-limit and lock** authentication attempts, per account *and* per IP.
- **Password reset tokens** are single-use, short-lived (an hour), invalidated on use and on
  password change, and generated with a cryptographic random source.
- **Do not reveal whether an account exists.** "If an account exists, we sent an email" — both for
  login and for reset. Watch the timing too.
- **Invalidate every session on password change**, and offer "sign out everywhere".
- **Enumeration:** signup, reset, and login must not let someone learn which emails are registered.
- **MFA** for anything administrative or financial. TOTP at minimum; treat recovery codes as
  credentials.

## 9. Logging (Law 9)

Log: login success and failure, logout, password and email change, MFA change, permission and role
change, authorization *denials*, data exports, and admin actions — each with who, what, when, and
from where.

**Never log:** passwords, tokens, session ids, API keys, full request bodies, or full card numbers.

An audit trail is how you answer "what did they reach?" after an incident. Without one, the honest
answer is "we do not know", and that is the answer you must then give your customers.
