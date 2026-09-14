# NOTICE: CI was timing out and silently skipping gates; the workflow is now four parallel jobs

STATUS: NOTICE (additive; no other record is edited)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-14
FOR: `20260821-claude-ci-workflow.md` (STATUS `ACTIVE`), which owns `.github/workflows/ci.yml`
AUTHORIZATION: founder instruction, 2026-09-14, choosing "split into parallel jobs" from an explicit
  question that named this claim and set out three alternatives with their trade-offs.

## The failure

Run **`34839894115`** (push of `d8689c0a`, a one-file Markdown change) was **cancelled** at
**30m10s** — `timeout-minutes: 30`, job started 11:46:22Z, killed 12:16:32Z. It was not superseded:
`origin/main` was still `d8689c0a` and no later run existed.

```text
✓ Ruff lint            ✓ Tests, normal order
✓ Ruff format          ✗ Tests, reverse file order   <- killed here
✓ Strict mypy          · Craft checker self-tests        SKIPPED
                       · Agent claim and disk layout     SKIPPED
```

## It was not caused by the tests added the same day, and the evidence says so

The obvious explanation — `20260914-claude-paper-book-accounting-repairs.md` added 29 tests — is
**wrong**, and worth recording because it was the filer's own first conclusion:

| Run | Content | Time | Margin to 30m |
|---|---|---:|---:|
| `34759939183` (2026-09-13, before that work) | — | 29m26s | **34s** |
| `34836160971` | the code change **plus all 29 new tests** | 28m33s | 87s |
| `34839894115` | **one Markdown file**, same tests | >30m00s | **killed** |

The run containing the new tests passed comfortably; the next run, with no code change at all, died.
So the differentiator is runner variance on `windows-latest`, against a margin that was already
**34 seconds** before any of this session's work existed. The added tests made a thin margin thinner;
they did not create it.

## Why this is the same defect as the 2026-09 `ruff format` incident

Recorded in `CURRENT.md`: `ruff format` is cheap and ran second, so when it went red for over a week
everything behind it was skipped and **no tests ran at all**, while the gate looked merely lint-red.

Here the timeout hit at step 5 of 7 and the craft checkers and the claim/disk audits were **skipped**,
not failed. Both are one shape: seven gates in series under one budget, where a single slow or
failing step silently cancels the verification behind it — and a skipped gate reads like a passing
one to anything summarising the run. That shape was going to recur on every push, including the
scheduled `sync: evidence checkpoint` commits.

## What changed

| Job | Contents | Timeout |
|---|---|---:|
| `static` | ruff check, ruff format, strict mypy — each with `if: always()` so one failure no longer hides the other two | 20m |
| `tests` | matrix `[forward, reverse]`, `fail-fast: false` — two concurrent jobs | 30m each |
| `craft` | craft self-tests + both audits. No Python and no `uv sync`, since the checkers are Node and the audits are PowerShell over Git; skipping the lockfile install is most of why this job is minutes | 15m |
| `gates` | `needs: [static, tests, craft]`, `if: always()`, fails unless all three report `success` | 5m |

**No command changed.** Every gate runs the identical invocation at identical strictness; only their
arrangement moved. Wall-clock becomes the slowest job rather than the sum, and each gate now has its
own budget and its own verdict.

**The `gates` job exists for branch protection.** It keeps the status-check name stable, and
`if: always()` is what makes it meaningful: without it the job would itself be *skipped* when a
dependency failed, and a skipped required check does not block a merge. That matters for Major #1,
whose remaining half is branch protection.

## Verification

- Workflow parses: `yaml.safe_load` resolves 4 jobs with the intended `runs-on`, `timeout-minutes`,
  `needs` and the `[forward, reverse]` matrix.
- Every command in the new file was run locally against this tree before the split: forward suite
  **1,519 passed**, reverse-order suite **1,519 passed** (CI's exact PowerShell invocation), both
  craft self-tests PASS, both audits PASS, ruff and strict mypy clean.
- The arrangement itself is verified only by CI actually running it. This notice is filed before
  that verdict exists.

## Residual

Splitting buys headroom; it does not make the suite faster. The `tests` jobs still take ~28-30
minutes each and now sit against their own 30-minute budget, so the reverse leg in particular may
still be tight. If it trips again the next step is `pytest-xdist` (rejected today because it touches
`uv.lock`, a shared file under PROTOCOL §4, and risks exposing order-dependent tests — which needs
its own verification pass, not a drive-by).
