# 07 — The web surface

Headers, cookies, and cross-origin behavior. Mostly configuration rather than code, which is exactly
why it gets skipped — and why it is cheap to fix.

Skip this file if the product has no browser surface. Everything else in the skill still applies.

---

## 1. Security headers

Set these globally, at the framework or gateway, not per route:

| Header | Value | Prevents |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Downgrade to HTTP |
| `X-Content-Type-Options` | `nosniff` | Browser guessing a type and executing content |
| `Content-Security-Policy` | see §2 | XSS impact, injected script sources |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Leaking URLs (and tokens in them) |
| `X-Frame-Options` / CSP `frame-ancestors` | `DENY` or a named origin | Clickjacking |
| `Permissions-Policy` | disable what you do not use | Camera, mic, geolocation access |

**HSTS is a commitment.** Once a browser sees it, it refuses plain HTTP for `max-age`. Confirm HTTPS
works everywhere, including subdomains, before enabling `includeSubDomains`.

## 2. Content Security Policy

CSP is **defense in depth, not a fix for XSS** — fix the injection (`02-input-and-injection.md`) and
use CSP to reduce the impact of the one you missed.

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'nonce-{random-per-response}';
  object-src 'none';
  base-uri 'self';
  frame-ancestors 'none'
```

- **`'unsafe-inline'` in `script-src` defeats the purpose.** Use a per-response nonce or a hash.
- **`object-src 'none'` and `base-uri 'self'`** are cheap and close real bypasses.
- **Roll it out in report-only mode first**, collect violations, then enforce. A CSP that breaks the
  app gets removed entirely, which is worse than a slightly loose one.

## 3. CORS

CORS **relaxes** the same-origin policy. Every rule you add opens something that was closed.

```
BAD    Access-Control-Allow-Origin: *
       Access-Control-Allow-Credentials: true      // browsers reject this pair, and rightly
BAD    reflecting the request's Origin header back without checking it

GOOD   an allowlist of exact origins, compared exactly
```

- **Never reflect `Origin` unchecked** — that is "allow everyone" with extra steps.
- **Compare exactly.** A `startsWith`/`endsWith` check on the origin is bypassable
  (`https://yoursite.com.attacker.com`).
- **Only the methods and headers you actually use.**
- **CORS is not authorization.** It restricts *browsers*; anything else ignores it. Server-side
  authorization is still required (Law 2).

## 4. Cookies

```
Set-Cookie: session=...; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=3600
```

- **`HttpOnly`** — script cannot read it, so XSS cannot steal the session directly.
- **`Secure`** — never sent over plain HTTP.
- **`SameSite=Lax`** is the sensible default and blocks most CSRF. `Strict` for high-value actions;
  `None` requires `Secure` and needs a specific reason.
- **Scope `Path` and `Domain` narrowly.** A cookie on `.example.com` is readable by every subdomain,
  including the one running user content.
- **Prefix with `__Host-`** for session cookies where you can — the browser then enforces `Secure`,
  no `Domain`, and `Path=/`.

## 5. CSRF

A state-changing request the browser makes automatically because it has the user's cookies.

- **`SameSite=Lax` cookies** handle the common cases and are the first line.
- **Anti-CSRF tokens** for form posts in a cookie-authenticated app: per-session, verified on every
  unsafe request. Use the framework's — do not write your own.
- **Token-in-header auth (`Authorization: Bearer`) is not CSRF-prone**, because the browser does not
  attach it automatically. This is a real advantage of header auth for APIs.
- **`GET` never changes state** (`api-craft` §3). A state-changing `GET` bypasses every CSRF
  defense, because it is meant to be safe.

## 6. Clickjacking

`frame-ancestors 'none'` in CSP, plus `X-Frame-Options: DENY` for older browsers. If the product
must be embeddable, name the exact permitted origins — never `ALLOWALL`.

## 7. Redirects

An open redirect turns your domain into a phishing tool: `yoursite.com/go?url=evil.com` looks
legitimate in an email.

- **Allowlist redirect targets**, or accept **relative paths only** and reject anything with a
  scheme or `//`.
- **Validate after canonicalizing** — `//evil.com` and `https:/\evil.com` are both protocol-relative
  or scheme-confusing forms that naive checks miss.
- Post-login redirects are the usual place this appears.

## 8. Rate limiting and abuse

`api-craft` §5 covers the contract shape. The security-specific points:

- **Authentication endpoints need stricter limits** — per account *and* per IP, so neither
  credential stuffing nor a distributed attempt at one account works.
- **Expensive endpoints need their own budget** — search, export, report generation, anything that
  scans.
- **Fail closed under load.** If the limiter's backing store is unavailable, deny rather than allow.
- **CAPTCHA or proof-of-work** only where abuse is demonstrated; it is a tax on real users.

## 9. Error handling on the web surface

- **Never return a stack trace to a browser.** Framework debug pages leak paths, versions,
  environment variables, and sometimes source.
- **Turn debug mode off in production**, and verify it — this is one of the most common real
  misconfigurations.
- **Generic messages for authentication failures.** "Invalid email or password", never "no such
  user" (`01-identity-and-access.md` §8).
- **A `requestId` in the response**, with the detail in your logs (`api-craft` §4).

## 10. Client-side

- **Never store a session token in `localStorage`.** Any XSS reads it, and it persists. An
  `HttpOnly` cookie cannot be read by script.
- **No secrets in client code.** Anything shipped to a browser is public — an "API secret" in a
  bundle is a published credential.
- **Subresource Integrity** on any third-party script you load from a CDN, so a compromised CDN
  cannot silently swap it.
- **Minimize third-party scripts.** Each one runs with full access to your page, your DOM, and
  anything the user types into it.
