# NOTICE: `loop-in-test` reports Python comprehensions as loops

STATUS: NOTICE — for the owner of `scripts/check-tests.mjs`
FILED_BY: Claude Code, from `20260825-claude-loop-in-test-repair.md`
FILED_UTC: 2026-08-25T12:40:00Z
AFFECTS: `20260821-claude-check-tests-casebody.md` [HANDOFF_REQUIRED], which owns
`scripts/check-tests.mjs`. This notice is additive; that record has not been edited.

## The defect

`scripts/check-tests.mjs:310`

```js
const loops = code.filter((l) => /^\s*(for|while|forEach\s*\()\b/.test(l));
```

The rule is a per-line regex over the case body. Python writes a multi-line comprehension with the
`for` clause at the start of its own line:

```python
    offending = {
        module
        for module in _imported_modules(source_path)   # <- matches ^\s*for\b
        if module == ADVISORY_MODULE
    }
```

so every multi-line comprehension in a test body is reported as a loop.

## Scale, measured

Classified all 31 `loop-in-test` findings with Python's `ast`, counting `ast.For`/`ast.While`/
`ast.AsyncFor` nodes in the reported function:

| | Count |
|---|---:|
| Genuine loop statements | 22 |
| **Comprehension clauses only — no loop statement in the body** | **9** |

**29% of the findings for this rule are false.** Three of the nine are in
`tests/test_advisory_isolation.py` on cases that are *already* `@pytest.mark.parametrize`d, so the
finding recommends a fix the code has already applied — the shape most likely to teach a reader to
stop believing the checker.

## Why a comprehension is not the hazard the rule names

The rule's message is "a loop can run zero times and assert nothing". A comprehension does not
assert; it builds a value that an assertion outside it then compares. Zero rows makes the comparison
**fail**, not pass:

```python
assert [e.manifest.resource_id for e in store.list_verified(...)] == ["trial_good"]
```

The hazard needs an assertion *inside* an iteration whose collection may be empty. A comprehension
clause cannot be that.

## Suggested direction, not a patch

Requiring the line to end the header — a real Python `for`/`while` statement always closes with `:`,
a comprehension clause never does — separates the two classes on every case in this repository.
`forEach(` is unaffected. I have not written it: `scripts/check-tests.mjs` is your path, and your
record's non-goals say "Changing the rule set, thresholds, or severity model" is out of scope for
that task, so this may belong to a different one.

## What I did in the meantime

Six unclaimed test files carried 12 of the 31 findings. The 6 comprehension false positives among
them now carry `# test-allow: loop-in-test - <reason>` stating that the match is a comprehension.
**Those annotations become unnecessary the moment the regex is fixed** and can be deleted wholesale;
they are marked with reasons naming "comprehension" so they are greppable:

```
grep -rn "test-allow: loop-in-test - .*comprehension" tests/
```

No test was changed to satisfy a false positive.

## Not affected

`sleep-in-test` uses a different pattern and is not implicated. The repo-wide count for it is 1,
in `tests/test_server_api.py:338`, which is also yours.
