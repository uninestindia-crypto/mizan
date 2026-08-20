# 04 — Errors and failure

Most code is written for the path where everything works. Most *incidents* happen on the other
paths. The gap between those two sentences is where this file lives.

`project-zero/references/03-errors-and-logging.md` sets up the taxonomy on day zero. This file
governs how you use it in every change afterwards.

---

## 1. Never swallow a failure (Law 5)

```
catch (e) {}            except: pass           rescue nil
if err != nil {}        _ = err                .catch(() => {})
```

**This is the single most expensive line in software.** It converts a loud, immediate, debuggable
failure into a silent wrong answer that surfaces days later as corrupted data or a confused
customer — with no stack trace and no log line pointing anywhere near the cause.

Exactly three things may happen to a failure:

1. **Handle it** — do something that makes the situation correct.
2. **Propagate it** — add context and pass it up to someone who can decide.
3. **Deliberately ignore it** — with a comment saying why, and a narrow catch.

Option 3 is legitimate and rare:

```
// Cache write is best-effort: a miss costs latency, never correctness.
try { cache.set(key, value) } catch (e) { logger.warn("cache write failed", { err: e }) }
```

Note what makes it acceptable: the failure is *named*, the reason is *stated*, and it is still
*logged*. "Ignored" never means "invisible".

**Catch narrowly.** A bare `except:` in Python swallows `KeyboardInterrupt` and `SystemExit` —
your process becomes unkillable. Catching `Exception` where you meant `IOError` hides the
programming error you actually needed to see.

## 2. Add context as it propagates

An error that arrives at the top as `connection refused` is nearly useless. One that arrives as
`settling invoice 4471: charging card: connection refused` names the operation, the entity, and the
cause.

**Wrap, do not replace.** Preserve the original — `%w` in Go, `cause` in JS/Java, `raise ... from e`
in Python, `?` with context in Rust. A new error that discards the old one destroys the only
evidence of what actually happened.

Add context that the *caller could not know*: which record, which operation, which attempt. Do not
add context they already have.

## 3. Fail fast, at the boundary (Law 4)

Validate untrusted input **once**, where it arrives, into a shape that cannot be wrong. Then trust
it everywhere inside.

The alternative — checking defensively at every layer — has three costs: the noise hides the one
place a real check was missing; it teaches readers the value can be bad, so they add more checks;
and the failure surfaces far from the input that caused it.

**A crash at startup beats a wrong answer at runtime.** Config, schema, and required dependencies
should be verified at boot (`project-zero` Law 3), not discovered mid-request.

## 4. Distinguish the kinds of failure

The taxonomy exists so callers can branch without string-matching:

| Kind | Retry? | Who fixes it |
|---|---|---|
| Invalid input | Never | The caller |
| Not found | Never | The caller |
| Not permitted | Never | The caller |
| Conflict / already exists | Never | The caller |
| Rate limited | Yes, after a delay | Time |
| Dependency failed | Yes | Us / the dependency |
| Timeout | **Carefully** — see below | Us |
| Bug (unexpected) | Never | Us, urgently |

**`code` is the contract; `message` is for humans.** Callers branch on the code. Never make anyone
regex a message — the moment someone improves the wording, a retry loop somewhere breaks silently.

## 5. Retries, timeouts, and the rule about non-idempotent calls

**Every call that leaves the process gets a timeout.** Without one, a slow dependency becomes your
outage: connections pile up, the pool exhausts, and the failure is total rather than partial. There
is no such thing as a call that "should be fast".

**Retry only what is safe to retry:**

- Retry on transient failures — timeouts, 5xx, connection resets, rate limits.
- Never retry on 4xx. The caller's request will not become valid by repetition.
- **Never blindly retry a non-idempotent operation on a timeout.** A timeout means the answer was
  lost, *not* that the work did not happen — the charge may have gone through. This is how one
  payment becomes two. Use an idempotency key so the retry is safe, or do not retry.
- **Exponential backoff with jitter.** Fixed-interval retries from many clients synchronize into a
  thundering herd that keeps a recovering dependency down.
- **Bound the attempts.** Infinite retry is an outage amplifier.

## 6. Partial failure is normal

Any operation touching more than one thing can half-succeed: 7 of 10 emails sent, 3 of 5 rows
written, the payment taken but the receipt not saved.

Decide, explicitly, per operation:

- **All-or-nothing** — a transaction, or a compensating action that undoes the completed part.
- **Best-effort with a report** — return which succeeded and which failed. The caller decides.

The wrong answer is to return success because most of it worked, or to throw and leave the
completed part invisible. **Both hide state that someone will discover later, by accident.**

For anything crossing a system boundary, prefer the outbox pattern or an idempotency key over a
distributed transaction.

## 7. Error messages are an interface

Three parts, in order: **what happened → why → what to do**.

```
BAD   "Error: operation failed"
BAD   "NullPointerException at line 47"
GOOD  "Couldn't send invoice 4471: the customer has no billing address.
       Add one in Settings → Billing, then retry."
```

- Never blame the user.
- Never expose stack traces, internal hostnames, or SQL to an end user. A support reference code
  alongside a human explanation is the right shape.
- **5xx messages must be replaced before serialization.** "connection refused to
  pg-primary-3.internal:5432" is a gift to an attacker and meaningless to a user. 4xx messages pass
  through — the caller caused it and needs to know what to change.

## 8. Assertions vs errors

- **Error:** something the world can do to you. Bad input, network down, disk full. Handle it.
- **Assertion/panic:** something only a bug can cause. An invariant violated. Fail loudly and
  immediately — do not "handle" it, because there is no correct handling of a broken invariant.

Do not use exceptions for control flow in the happy path. An exception thrown and caught two lines
later is a `goto` with worse performance and worse readability.

## 9. Test the failure paths

**The failure path is the one that has never been run.** Ring 5 of `founder-mode`'s test matrix
exists because of this.

For every error path: does it produce the right type, add the right context, log once, and leave
the system in a valid state? Inject the failure — kill the dependency, return a 500, sleep past the
timeout — rather than trusting that the code you wrote would do the right thing.
