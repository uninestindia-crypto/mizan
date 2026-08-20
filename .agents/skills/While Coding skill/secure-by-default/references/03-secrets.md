# 03 — Secrets

**A secret committed once is compromised forever.** It is in the history, the history is on every
clone, and every fork and CI cache that ever pulled it. Deleting the line does nothing.

That single fact drives everything in this file.

---

## 1. Where secrets live

| Environment | Source of truth |
|---|---|
| Local development | A `.env` file, **gitignored**, never committed |
| CI | The CI provider's encrypted secret store |
| Production | A secret manager (Vault, AWS/GCP/Azure secret managers, the platform's own) |

**Never in:** source code, the repository, a config file that is committed, a container image, a
command-line argument (visible in `ps`), a URL, a log line, an error message, a bug report, a
screenshot, or a chat message.

`project-zero`'s config contract is the mechanism: every secret is declared in one schema, read from
the environment at boot, and the process refuses to start without it.

## 2. `.env` discipline

- **`.env` is in `.gitignore` before it exists.** Add the ignore rule in the first commit.
- **`.env.example` is committed**, with every variable name and **no real values**. It is the
  documentation a new engineer reads first.
- **A committed `.env` is an incident**, not a cleanup task. Rotate every value in it.
- Never `cat` a `.env` into a log, a CI step, or a screen share.

## 3. What to do when a secret leaks

Assume compromise from the moment it was pushed. In order:

1. **Rotate the credential.** This is first and it is not optional. Everything else is secondary.
2. **Revoke the old value** at the provider, so it stops working immediately.
3. **Check the access logs** for use of the old value — it may already have been used.
4. Remove it from the working tree.
5. **Consider the history purged only if you actually rewrite it** (`git filter-repo`, BFG) *and*
   force-push *and* every clone is refreshed *and* the provider's cache is invalidated. In practice
   this is unreliable, which is why step 1 is the real fix.
6. Add a scanner to CI so the next one is caught before merge.

**"We deleted the commit" is not remediation.** GitHub retains unreachable objects; forks keep
them; someone's laptop has them.

## 4. Detection

- **A history-aware secret scanner in CI** (gitleaks, trufflehog) with `fetch-depth: 0`, so it sees
  the past rather than just the tip. `project-zero`'s CI asset wires this.
- **A pre-commit hook** so it is caught before it ever leaves the machine — far cheaper than
  catching it in CI.
- **This skill's scanner** for the working tree, as a fast local check.
- **Provider-side scanning**, where the platform offers it (GitHub secret scanning + push
  protection). Turn it on.

## 5. Rotation

- **Every secret has a rotation procedure, and it has been executed.** An unrehearsed rotation is
  discovered to be broken during the incident that requires it.
- **Support two valid credentials at once** during a rotation window, or rotation means downtime —
  and a rotation that means downtime is a rotation that never happens.
- **Rotate on schedule**, and immediately when someone with access leaves.
- **Short-lived credentials beat rotation.** Workload identity, IAM roles, and OIDC federation give
  minutes-long credentials with nothing to leak. Prefer them to any long-lived key.

## 6. Never log a secret (Law 9)

The usual mechanism is nobody logging a secret on purpose — someone logs a whole object and a token
is inside it.

- **Redact by key name at write time.** `project-zero/assets/logger.ts` does this, so being careless
  is not the same as leaking.
- **Never log a full request body**, a full header set, or a full config object.
- **Scrub before sending to a third party** — error trackers, analytics, and support tools all
  receive whatever you hand them, and now the secret is in another company's database.
- **Secrets never appear in an error message returned to a caller** (`api-craft`: 5xx bodies are
  replaced).
- Watch for secrets in URLs — they reach access logs, proxies, and `Referer` headers.

## 7. Secrets in transit and at rest

- **TLS everywhere**, including service-to-service inside your own network. "It is internal" assumes
  the network is trusted; it is not.
- **Never disable certificate verification.** `rejectUnauthorized: false`, `verify=False`,
  `InsecureSkipVerify: true` are debugging shortcuts that reach production and silently remove all
  transport security. The scanner flags them as critical.
- **Encrypt secrets at rest** — the secret manager does this; a config file on a disk does not.
- **Limit blast radius:** one credential per service per environment. A single shared key means one
  leak compromises everything and rotation becomes a coordinated outage.

## 8. Secrets in CI and containers

- **Never bake a secret into an image.** Image layers are extractable, images get pushed to
  registries, and registries get shared.
- **Never pass a secret as a build argument** — `docker history` shows it.
- **Mount at runtime**, from the platform's secret store.
- **Guard CI secrets against untrusted pull requests.** A fork PR that can run a workflow with
  access to secrets can exfiltrate them in one line. Most CI providers withhold secrets from fork
  PRs by default — verify yours does, and never override it for convenience.
- **Do not echo secrets in CI logs.** Use the provider's masking, and remember masking only covers
  exact matches — a base64 or JSON-encoded form of the same secret is not masked.

## 9. Third-party access

Every integration you grant is a path into your data:

- **Least privilege on every token** — read-only where reading is all it does.
- **Scope and expire** OAuth grants; review them periodically.
- **Inventory who has access to what**, and revoke on offboarding the same day.
- **Verify webhook signatures** — an unsigned webhook endpoint accepts anyone's data as yours
  (`api-craft` §8).
