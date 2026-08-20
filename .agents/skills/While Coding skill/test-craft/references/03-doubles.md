# 03 — Test doubles: fakes, stubs, mocks, spies

The single most misused tool in testing. Over-mocking is how a suite ends up green while the system
is broken — every unit asserts that its mocks were configured, and nobody tests that the pieces fit.

---

## 1. The five kinds, and what each is for

| Kind | What it is | Use when |
|---|---|---|
| **Real** | The actual thing | Always, if it is fast and deterministic |
| **Fake** | A working lightweight implementation (in-memory repo) | You need real behavior without real cost |
| **Stub** | Returns canned answers, asserts nothing | You need an input the unit reads |
| **Spy** | Records calls; you assert afterwards | You need to check an interaction happened |
| **Mock** | Pre-programmed with expectations; fails if not met | An interaction has **no observable result** |

**Reach for them in that order.** Every step down the list couples the test more tightly to
implementation, and coupling to implementation is what makes a suite punish refactoring (Law 2).

## 2. Mock what you own and cannot control (Law 7)

| Replace | Keep real |
|---|---|
| Network calls to third parties | Your own pure functions |
| Payment providers, email, SMS | Your domain objects and value types |
| The clock, randomness, UUIDs | Your in-process business logic |
| Anything slow, flaky, or costly | The database, in integration tests |

**Never mock the thing under test.** A test that mocks the unit it is testing asserts that the mock
was configured correctly, which is a tautology dressed as a test. This sounds too obvious to state
and happens constantly — usually by mocking a method on the same class.

**Do not mock types you do not own.** A hand-written mock of a third-party SDK encodes *your belief*
about how it behaves. When the real one differs — and it will, at a version bump — every test still
passes. Wrap it in your own narrow interface (`code-craft` §7), then fake *that*.

## 3. Prefer a fake to a mock

An in-memory implementation of your own interface is usually the best double in existence:

```ts
class InMemoryOrderRepo implements OrderRepo {
  private rows = new Map<string, Order>();
  async save(o: Order)   { this.rows.set(o.id, o); return o; }
  async find(id: string) { return this.rows.get(id) ?? null; }
}
```

- Tests read like the real thing — arrange by *saving*, assert by *finding*.
- **It has real behavior**: save-then-find works, find-missing returns null, a duplicate id
  overwrites. A stub returning a canned object has none of that.
- It survives refactoring, because it implements the same interface.
- One fake serves hundreds of tests.

Write the fake once, and **run your interface's contract tests against both the fake and the real
implementation** — that is what stops the fake drifting into a lie.

## 4. When a mock is genuinely right

Only when the interaction has **no observable result**:

```ts
// The audit log is fire-and-forget: nothing in the system reflects it.
it('records an audit entry when an order is cancelled', async () => {
  const audit = spy();
  await cancelOrder(order.id, { audit });
  expect(audit).toHaveBeenCalledWith({ type: 'order.cancelled', orderId: order.id });
});
```

There is no state to query and no return value, so asserting the call *is* asserting the behavior.

Everything else — did it save, did it charge, did it queue — is better asserted by looking at the
resulting state through a fake.

## 5. The symptoms of over-mocking

- **More setup than assertion.** Ten lines of mock configuration for a two-line act.
- **The test breaks when you rename a private method.** It was testing implementation.
- **A mock returning a mock returning a mock.** You are rebuilding the system out of doubles, and
  your model of it is now the thing under test.
- **All units pass and the system does not work.** The classic outcome: every seam is mocked, no
  test ever exercises two real pieces together.
- **You changed the mock to make the test pass**, without changing production code. The test was
  asserting the mock.

**The cure is almost never a better mock.** It is fewer dependencies (`code-craft` Law 2 and §6:
push side effects to the edges, keep a pure core) or a real integration test.

## 6. Time, randomness, and identity

These are I/O, and they are the most common source of an untestable unit.

```
BAD    function isExpired(o) { return o.expiresAt < new Date() }   // untestable
GOOD   function isExpired(o, now) { return o.expiresAt < now }     // trivially testable
```

**Inject them.** A clock parameter, a fixed seed, an id generator. Then a test can pin the exact
moment and assert real behavior — including the boundary at exactly the expiry instant, which is the
case that actually breaks.

Framework fake timers work too, but injection is simpler, faster, and does not leak between tests.

## 7. HTTP and external services

Layered, best to worst:

1. **A fake implementation of your own client wrapper.** Fast, deterministic, no network.
2. **A local HTTP stub server** (WireMock, `nock`, `responses`, `httptest`). Exercises real
   serialization and real status-code handling.
3. **Recorded fixtures** (VCR-style). Real shapes, but they go stale silently — the provider changes
   and your tests keep passing against a recording of last year.
4. **The real service.** Never in unit or integration tests. Exactly one contract test against a
   sandbox, run on a schedule, is worth having — it is the only thing that catches provider drift.

Whichever you choose, **test the failure modes**: timeout, 500, 429, malformed body, connection
reset. Those are the paths that will actually run in production and the ones never exercised
locally.

## 8. Verify state, not interactions, wherever you can

```
WEAKER  expect(repo.save).toHaveBeenCalledWith(expect.objectContaining({ status: 'paid' }))
STRONGER  const saved = await repo.find(order.id)
          expect(saved.status).toBe('paid')
```

The second survives a refactor from `save()` to `update()`, or a batching change, or a move to a
different persistence call — because it asserts the *outcome the caller cares about* rather than
the mechanism. That is Law 2 in one comparison.
