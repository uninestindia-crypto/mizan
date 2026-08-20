# 05 — Versioning, evolution, and deprecation

The asymmetry that governs everything here: **adding is cheap and reversible; removing and
redefining are neither.** You can add a field on a Tuesday. Removing one requires finding every
consumer, most of whom you cannot see.

---

## 1. Classify the change before you make it (Law 4)

| Change | Compatible? |
|---|---|
| Add a new endpoint | ✅ |
| Add an **optional** request field | ✅ |
| Add a field to a response | ✅ *if consumers tolerate unknown fields* |
| Add a new **optional** query parameter | ✅ |
| Add a new enum value | ⚠️ **Breaking in practice** — see below |
| Make a required request field optional | ✅ |
| Relax validation | ✅ |
| Remove or rename a field | ❌ |
| Add a **required** request field | ❌ |
| Change a type (`"42"` → `42`) | ❌ |
| Narrow a type, or tighten validation | ❌ |
| Change a status code for an existing case | ❌ |
| Change what a value **means** | ❌ **Worst of all** |
| Change a default | ❌ |
| Change sort order or pagination behavior | ❌ |

**If you are unsure, treat it as breaking.** Being wrong that way costs an unnecessary version.
Being wrong the other way costs somebody's production outage at a time you do not choose.

### The two that surprise people

**Adding an enum value.** Strictly it is additive; in practice a consumer's `switch` has no branch
for it, or their parser rejects it outright. Mitigate by documenting from v1 what a consumer must do
with an unrecognized value — and mean it, by shipping an unknown value early while it is harmless.

**Changing meaning is worse than removing.** If `status: "complete"` starts including partially
refunded orders, every consumer keeps working and every consumer is now wrong. A removal breaks
loudly; a redefinition breaks silently, and silence is what makes it expensive.

## 2. Versioning strategy

**URI path versioning** — `/v1/orders` — unless you have a specific reason otherwise. It is
visible in logs, in a browser, in a bug report, and in a curl command someone pastes into a ticket.
Header-based versioning is theoretically cleaner and practically invisible, which makes every
support conversation harder.

Rules:

- **`/v1` from the first release** (Law 3), when it costs nothing.
- **Version the API, not the endpoint.** Per-resource versions produce a matrix nobody can reason
  about.
- **Major versions only.** `/v1.2` implies consumers track minor versions; they will not.
- **A new version is a last resort**, not a release cadence. Most change should be additive.
- **Two supported versions at a time, maximum.** Every extra version multiplies test surface and
  the number of code paths in which a bug can hide.

## 3. Running two versions

Do not fork the codebase. Fork at the edge and converge immediately:

```
/v1/orders ─┐
            ├─→ translation layer ─→ one internal domain model ─→ storage
/v2/orders ─┘
```

The translation layer is the *only* place the versions differ. Two full stacks means every fix
lands twice, and eventually only lands once.

Where v1 cannot be expressed in terms of the new model, that is the signal the change was more
fundamental than expected — and worth reconsidering.

## 4. Deprecation

A deprecation is a **process with dates**, not an announcement.

```
Deprecation: Sun, 01 Nov 2026 00:00:00 GMT   # when it was deprecated
Sunset: Wed, 01 Apr 2027 00:00:00 GMT        # when it stops working
Link: <https://docs.example.com/v2-migration>; rel="deprecation"
```

The sequence:

1. **Ship the replacement first.** Never deprecate something with no migration target.
2. **Announce** with a dated timeline, a migration guide, and the reason.
3. **Add the headers**, so it is discoverable by tooling rather than by reading email.
4. **Instrument it.** Log every call to the deprecated path *with the consumer identity* — this is
   the only way to know who still depends on it, and it turns "we think everyone migrated" into a
   number.
5. **Contact the remaining callers directly.** The ones still calling it are the ones who did not
   read the announcement.
6. **Brown-out before sunset** — fail a rising percentage of requests for short windows. This finds
   the consumers who ignored every message, at a moment you control, rather than at the sunset.
7. **Sunset.** Return `410 Gone` with a link, not `404`. `410` says "this existed and is
   deliberately finished"; `404` says "you have a typo" and sends them debugging.

**Minimum notice: 6 months for a public API.** Longer if consumers are enterprises with release
trains — a quarterly release cycle means 3 months of notice is one opportunity to act.

## 5. Tolerant reading, strict writing

Publish this expectation, and follow it in your own clients:

- **Consumers must ignore unknown response fields.** State it in the docs from day one; it is what
  makes additive change possible at all.
- **Consumers must tolerate new enum values**, with a documented fallback.
- **Servers reject unknown request fields** — silently discarding a misspelled field means the
  consumer believes they set something they did not.

The asymmetry is deliberate: leniency on the way out preserves your freedom to evolve; strictness
on the way in preserves the consumer's ability to trust that their request was understood.

## 6. Contract tests

The only way to know a change is compatible is to check mechanically:

- **Diff the spec in CI.** Fail the build on a removed field, a narrowed type, a new required
  parameter, or a changed status code. A human reviewer will miss one of these eventually.
- **Keep recorded real requests** from each supported version and replay them.
- **Consumer-driven contract tests** where you have a small number of known consumers: they publish
  what they depend on, and your build breaks when you violate it — before release rather than after.

**Without a mechanical check, "backward compatible" is an opinion**, and it is usually the opinion
of the person who wants to ship.
