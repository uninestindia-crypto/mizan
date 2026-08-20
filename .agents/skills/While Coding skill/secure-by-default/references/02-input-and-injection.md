# 02 — Input handling and injection

Every injection vulnerability has the same shape: **data crossed into a place where it was
interpreted as instructions.** The defense is always the same too — never build the instruction by
concatenation; use the interface that keeps data as data.

---

## 1. What counts as input (Law 1)

Broader than most people assume. All of it is untrusted:

- Request bodies, query strings, path segments, **headers**, **cookies**
- File **names** and file **contents**
- Webhook payloads — signed or not
- Rows written by another system, or by an older version of yours
- Environment variables in a multi-tenant or CI context
- Anything from a third-party API
- Anything a user influenced, however indirectly

**Data from your own database is not automatically trusted.** It was input once. Stored XSS is
exactly this mistake.

## 2. Validate at the boundary, into a type (Law 1)

Validate **once**, where untrusted data arrives, into a shape that cannot hold a bad value. Then
trust it everywhere inside (`code-craft` Law 4).

- **Allowlist, never blocklist.** Enumerate what is permitted. A blocklist is a guess about every
  attack that exists, and it is always incomplete.
- **Validate type, range, length, and format** — not just presence.
- **Bound everything**: string length, array size, body size, nesting depth, file size, number
  range. An unbounded input is a denial-of-service vector.
- **Reject unknown fields.** Silently ignoring a misspelled field means the caller believes they set
  something they did not — and mass assignment is how a user grants themselves a role.
- **Canonicalize before validating.** Decode, normalize unicode, and resolve the path *first*, then
  check. Otherwise `%2e%2e%2f` passes a check for `../`.

**Client-side validation is a convenience for honest users.** Every rule is enforced again on the
server (Law 10). The client is an attacker-controlled environment.

## 3. SQL and query injection

```
BAD    db.query(`SELECT * FROM users WHERE id = ${id}`)
BAD    cursor.execute("SELECT * FROM t WHERE id = " + uid)
BAD    cursor.execute(f"SELECT * FROM t WHERE id = {uid}")

GOOD   db.query('SELECT * FROM users WHERE id = $1', [id])
GOOD   cursor.execute("SELECT * FROM t WHERE id = %s", (uid,))
```

**Parameterized queries, always.** Every driver in every language has them, and they are also
faster, because the plan is cached.

- An ORM is not automatic protection — its raw-SQL escape hatch is still a hatch.
- **Identifiers cannot be parameterized.** A dynamic table or column name must come from an
  allowlist, never from input. Same for `ORDER BY` direction.
- `LIKE` patterns need their wildcards escaped, or `%` from a user scans the whole table.
- The same rule binds NoSQL: an object where a string was expected becomes an operator injection
  (`{"$gt": ""}`). Validate the *type*, not just the value.

## 4. Command injection

```
BAD    exec(`git checkout ${branch}`)
BAD    os.system("ls " + path)
BAD    subprocess.run(cmd, shell=True)

GOOD   execFile('git', ['checkout', branch])
GOOD   subprocess.run(["ls", path], shell=False)
```

**Pass an argument array; never build a command string.** With an array there is no shell, so there
is no metacharacter to escape and nothing to get wrong.

If a shell is genuinely unavoidable, the argument must come from an allowlist — not from escaping,
which is very hard to get right and easy to get subtly wrong.

## 5. Cross-site scripting

**Use the framework's escaping and do not defeat it.** React, Vue, Angular, Django, Rails, and Go
templates all escape by default. Every XSS in a modern app is essentially someone opting out:

```
BAD    el.innerHTML = userInput
BAD    dangerouslySetInnerHTML={{ __html: userInput }}
BAD    v-html="userInput"
BAD    {{ userInput|safe }}          {{ mark_safe(userInput) }}

GOOD   el.textContent = userInput
```

- **Escaping is contextual.** HTML body, HTML attribute, JavaScript, URL, and CSS each need
  different escaping. The framework knows; a hand-rolled `escapeHtml` usually does not.
- **If you must render user HTML**, sanitize with a maintained allowlist library (DOMPurify and
  equivalents). Never a regex — that has never worked.
- **URLs from input need scheme validation.** `javascript:` and `data:` in an `href` are script.
- **A Content-Security-Policy is defense in depth**, not a fix (see `07-web-surface.md`).

## 6. Path traversal

```
BAD    fs.readFile(path.join(UPLOADS, req.params.name))     // name can be ../../etc/passwd
GOOD   const full = path.resolve(UPLOADS, req.params.name)
       if (!full.startsWith(path.resolve(UPLOADS) + path.sep)) throw new ForbiddenError()
```

**Resolve first, then assert containment.** Checking for `..` before resolving misses URL-encoded
forms, unicode variants, symlinks, and absolute paths.

Better still: **never use a user-supplied name as a path.** Store files under a generated id and
keep the original name as metadata (see `06-files-and-uploads.md`).

## 7. Server-side request forgery

Any feature that fetches a URL supplied by a user — webhooks, avatar imports, link previews, PDF
rendering — can be aimed at your internal network and the cloud metadata endpoint.

Defenses, layered:

- **Allowlist the destinations** where the feature permits it. Strongest by far.
- **Block private ranges** — `127.0.0.0/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`
  (metadata), `::1`, and unique-local IPv6.
- **Resolve the hostname and validate the resolved IP**, then connect to that IP — otherwise DNS
  rebinding defeats the check between validation and connection.
- **Disable redirects**, or re-validate every hop.
- **Only http/https.** Reject `file:`, `gopher:`, `ftp:`.
- Give the fetcher its own egress path with a short timeout and a size cap.

## 8. Other injection contexts

- **Template injection** — never build a template from input. Pass input as *data* to a fixed
  template; a template engine given user content is remote code execution.
- **Log injection** — a newline in a logged value forges log entries. Log structured JSON
  (`project-zero`), which escapes it inherently.
- **Header injection / response splitting** — a CR/LF in a header value. Never build headers by
  concatenation.
- **Redirect injection** — an open redirect is a phishing tool with your domain on it. Allowlist
  redirect targets, or permit relative paths only.
- **Deserialization** — `pickle`, Java native serialization, `unserialize`, `yaml.load` without a
  safe loader all execute attacker-chosen code. Use JSON with a schema.
- **Prompt injection**, where the product includes a model: content fetched from the web or supplied
  by a user is data, never instructions. Do not give a model tools whose blast radius exceeds what
  the *least* trusted content in its context should be allowed to do.

## 9. Output encoding is the other half

Validation restricts what enters. **Encoding makes it safe where it lands**, and you need both — the
same value is safe in JSON and dangerous in HTML.

Encode at the point of use, in the context of use, using the platform's function. Never store
pre-escaped data: you will double-escape it somewhere, and you will not know which layer already
did it.
