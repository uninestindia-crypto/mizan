# 06 — Files and uploads

An upload is untrusted input that you **store** and often **serve back**. That combination is why it
deserves its own file: a mistake here does not just corrupt a request, it becomes durable and gets
delivered to other users.

---

## 1. The threats, concretely

| Threat | What happens |
|---|---|
| **Stored XSS** | An uploaded `.html` or `.svg` served from your origin runs script with your users' sessions |
| **Path traversal** | A filename of `../../config/app.yml` writes outside the upload directory |
| **Overwrite** | A user-controlled name collides with an existing file, or with a system file |
| **Denial of service** | A 10GB upload, or a zip bomb that expands to terabytes |
| **Malware distribution** | Your domain hosts and serves it, with your reputation |
| **Content confusion** | A file claiming to be a JPEG that the browser sniffs as HTML |
| **Resource exhaustion** | An image that decompresses to enormous dimensions and OOMs the process |

## 2. Validate before you accept

- **Size limit at the edge**, before the body is buffered. Enforce it in the proxy/gateway *and* the
  application — a limit applied only after reading is not a limit.
- **Allowlist extensions and content types.** Never a blocklist; you cannot enumerate every
  dangerous form.
- **Verify the content, not the claim.** The `Content-Type` header and the extension are both
  attacker-controlled. Check magic bytes, and validate the file actually parses as what it claims.
- **Bound the parsed dimensions too.** A 100KB PNG can declare 50,000×50,000 pixels and exhaust
  memory when decoded — check declared dimensions before decoding.
- **Reject archives unless you need them.** If you must accept them, cap the entry count, the
  uncompressed size, the compression ratio, and reject entries with absolute or `..` paths.

## 3. Never trust the filename

**Do not use a user-supplied name as a path, ever.**

```
BAD    save(path.join(UPLOADS, req.file.originalname))

GOOD   const id = randomUUID();
       const ext = allowedExtensionFor(detectedType);   // from content, not the name
       save(path.join(UPLOADS, `${id}${ext}`));
       // keep the original name as metadata for display only
```

Generating the stored name removes traversal, collision, overwrite, and case-sensitivity problems in
one step. The original name is metadata — **escape it when displaying**, because it is user input
that will be rendered.

If you genuinely must derive a path from input, resolve first and assert containment
(`02-input-and-injection.md` §6).

## 4. Serve from a different origin

**The single most valuable control here.** User content served from your application's origin runs
with your origin's privileges — cookies, storage, and same-origin access to your app.

- **Serve from a separate domain** (not a subdomain sharing cookies), or from object storage with
  its own origin.
- **`Content-Disposition: attachment`** for anything not deliberately rendered inline.
- **`X-Content-Type-Options: nosniff`**, always, so the browser honours the declared type instead of
  guessing.
- **Set the `Content-Type` from your own detection**, never from the upload.
- **SVG is executable.** It can contain script. Either sanitize it with a maintained library, serve
  it as an attachment, or refuse it. Treating SVG as "just an image" is a common and effective
  attack.
- **Short-lived signed URLs** for private files, rather than a proxy endpoint that must re-check
  authorization on every byte.

## 5. Authorization on every access (Law 2)

- **Check on download, not only on upload.** A file reachable by anyone who guesses the id is a
  public file.
- **Unguessable identifiers** (UUID or random), never sequential — but treat that as defense in
  depth, not as the access control.
- **Scope by owner or tenant** in the lookup, the same way as any other resource.
- **Signed URLs expire**, and are scoped to one object.

## 6. Storage

- **Outside the web root.** A file inside a directory the server executes or serves directly is a
  remote code execution waiting for the right extension.
- **Object storage over local disk** — it is not executable, it scales, and it keeps user content
  off your application host.
- **Never executable.** Strip execute permissions; ensure the storage path cannot execute anything.
- **Quota per user**, or one account fills your disk.
- **Malware scanning** where you accept files that will be shared between users. Scan out-of-band,
  and quarantine until the scan completes.

## 7. Processing uploaded files safely

Image/document/video processing libraries are large C codebases with a long history of memory-safety
CVEs, and you are feeding them hostile input.

- **Process out-of-process** — a separate worker, ideally sandboxed or containerized, with no
  credentials and no network.
- **Time and memory limits** on every conversion.
- **Keep the libraries current** (`05-dependencies.md`) — this is one of the highest-value places to
  be up to date.
- **Strip metadata** on images you serve publicly. EXIF carries GPS coordinates, device identifiers,
  and sometimes a thumbnail of the *original* uncropped image — a genuine privacy leak that users do
  not expect.

## 8. Downloads and file-serving endpoints

The reverse direction has its own version of the same bugs:

- **Never take a path from input.** Take an id, look up the path.
- **Never let input choose the `Content-Type`** or the `Content-Disposition` filename without
  sanitizing — a CR/LF in a filename is header injection.
- **Rate-limit** downloads, or your storage bill becomes someone's project.
- **Range requests** must be validated; a malformed range should not read outside the object.

## 9. The checklist for any upload feature

- [ ] Size capped at the edge and in the app
- [ ] Extension and content type allowlisted
- [ ] Content verified by magic bytes, not by the claim
- [ ] Declared image dimensions bounded before decoding
- [ ] Stored under a generated name, outside the web root, non-executable
- [ ] Original filename kept only as metadata, and escaped on display
- [ ] Served from a separate origin, `nosniff`, attachment unless deliberately inline
- [ ] SVG sanitized, served as attachment, or refused
- [ ] Authorization checked on download, scoped by owner/tenant
- [ ] EXIF stripped from anything public
- [ ] Processing is out-of-process, sandboxed, with time and memory limits
- [ ] Per-user quota enforced
- [ ] Archives: entry count, uncompressed size, ratio, and path all validated
