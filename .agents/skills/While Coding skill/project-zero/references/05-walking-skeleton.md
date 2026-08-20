# 05 — The walking skeleton

> A walking skeleton is a tiny implementation of the system that performs a small end-to-end
> function. It need not use the final architecture, but it should link together the main
> architectural components. The architecture and the functionality can then evolve in parallel.
> — Alistair Cockburn, who named it

**It should be embarrassing.** If your walking skeleton is impressive, you built a feature and
skipped the machine.

---

## 1. What it is

One request, all the way through every layer the real product will use, deployed to production,
with a test and a rollback.

```
HTTP request
  → route handler
    → domain service          (real, trivial logic)
      → repository
        → database            (a real query against a real table)
      ← typed result
    ← mapped response
  ← JSON, with a request id
```

Plus, around it: it is **tested**, it is in **CI**, it is **deployed**, it emits a **log line with
a correlation id**, it appears in the **one metric**, and you have **rolled it back and forward
again**.

### The canonical example

An endpoint that stores a note and reads it back.

```
POST /notes   { "text": "hello" }   → 201 { "id": "...", "text": "hello" }
GET  /notes/:id                     → 200 { "id": "...", "text": "hello" }
GET  /notes/:id  (unknown id)       → 404 { "error": { "code": "NOT_FOUND" } }
```

That is the whole thing. It is worth roughly nothing as a feature and roughly everything as
infrastructure, because building it forces every integration question to be answered while the
answers are still cheap.

---

## 2. Why it comes before the first feature (Law 2)

Building the skeleton first means **every subsequent feature is a change to a working system**
rather than a step toward a hypothetical one. That difference compounds daily.

It also front-loads the questions that are expensive to answer late, and there are more of them
than anyone expects:

- How does a request get a correlation id, and how does it reach the repository?
- Where does the database connection come from, and who closes it?
- How does a domain error become an HTTP status?
- How does the test suite get a database, and how is it reset between tests?
- What does the deploy actually run — a container, a bundle, a process manager?
- How does config reach the process in production?
- What happens on a failed health check?

Each is a half-day when the codebase is empty and a week once forty files assume a different
answer.

---

## 3. What it must contain

The checklist. Every line is a thing that must genuinely work, not be stubbed:

- [ ] **A real route** on the real framework, on the real port from `config`
- [ ] **A real database query** against a real table created by a real migration
- [ ] **The migration has a `down`, and you have run it**
- [ ] **A typed error path** — the 404 uses `NotFoundError`, not a hand-written status
- [ ] **A log line with a correlation id**, from inside the repository, not just the handler
- [ ] **`/health` checks the database**, and returns degraded when it is down (try it — stop the
      database and look)
- [ ] **One test that exercises the whole path**, not a unit test of the handler
- [ ] **The test has been watched failing** — break the assertion, see red, restore it
- [ ] **CI runs it on every push**
- [ ] **It is deployed** to a real environment
- [ ] **You have rolled the deploy back and forward again**

### What it must NOT contain

Day zero is not the day for these, and adding them here is the most common way the skeleton stops
being a skeleton:

- Authentication and user accounts
- More than one endpoint that does anything real
- An abstraction layer "for later" — repository interfaces with one implementation, a plugin
  system, a generic base class
- A queue, a cache, a search index, or a second service
- Any UI beyond what proves the path works
- Retries, circuit breakers, or rate limiting

**If you find yourself designing, stop.** The skeleton is not where the design lives; it is where
the plumbing is proven. Design happens in P2 with the `architect`, against a system that already
demonstrably runs.

---

## 4. The test that proves it

One test, end to end, hitting the real database:

```ts
it("stores a note and reads it back", async () => {
  const created = await request(app).post("/notes").send({ text: "hello" });
  expect(created.status).toBe(201);

  const fetched = await request(app).get(`/notes/${created.body.id}`);
  expect(fetched.status).toBe(200);
  expect(fetched.body.text).toBe("hello");
});

it("returns a typed 404 for an unknown note", async () => {
  const res = await request(app).get("/notes/does-not-exist");
  expect(res.status).toBe(404);
  expect(res.body.error.code).toBe("NOT_FOUND"); // the CODE, never the message
});
```

**Then break it on purpose.** Change `toBe(201)` to `toBe(200)`, run it, watch it fail, and read
the failure output. Restore it and watch it pass.

This is not ceremony. A test suite whose failure mode you have never seen is a suite you cannot
trust: it might be passing because it asserts nothing, because it never runs, or because the
runner silently skips it. **You have not tested the code until you have tested the test.** The
day-zero gate holds this at `TODO` until a human attests to having watched it, because no amount of
file inspection can prove it happened.

---

## 5. When it is done

Run the gate:

```bash
node scripts/verify-day-zero.mjs
```

When it prints `Day zero complete. Slice 1 may start.`, hand off to `founder-mode` at P1. The
skeleton becomes the thing every slice modifies, and it has already proven that the whole path —
code, tests, CI, deploy, rollback, observability — works.
