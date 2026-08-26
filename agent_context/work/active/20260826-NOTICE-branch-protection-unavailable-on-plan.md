# NOTICE: Major #1 is misdescribed — branch protection is not available on this plan

FILED_UTC: 2026-08-26T00:00:00Z
FILED_BY: Claude Code — `20260826-claude-cross-sectional-execution-path.md`
STATUS: NOTICE (additive; no other record is edited)
SUBJECT: Major #1 as stated in `.launch/STATE.md` and `agent_context/CURRENT.md`

## What both files currently say

`.launch/STATE.md` Major #1: "Remaining: branch protection on `main` requiring the `gates` check,
which is a repository setting no agent can make."

`CURRENT.md` Next safe actions #1: "Branch protection on `main` requiring the `gates` check is a
repository setting no agent can make. Both are the founder's."

Both sentences imply the founder can simply set it. **Measured today, they cannot.**

## Measurement

```
$ gh api repos/uninestindia-crypto/quant-system/branches/main/protection
{"message":"Upgrade to GitHub Pro or make this repository public to enable this feature.",
 "documentation_url":"...","status":"403"}

$ gh api repos/uninestindia-crypto/quant-system --jq '{visibility,private,plan:.owner.type}'
{"private":true,"visibility":"private","plan":"User"}
```

Branch protection on a **private** repository owned by a **free User account** is not an available
feature. It is not a setting anyone has neglected to click. Closing it requires one of:

- GitHub Pro on the owning account, or
- making the repository public (which publishes the entire system), or
- moving the repository into an organisation on a Team plan.

That is a purchasing/visibility decision, not an engineering task, and it should be recorded as one.

## The other half of Major #1 is still open, for the originally stated reason

```
$ gh auth status
  Token scopes: 'gist', 'read:org', 'repo'
```

No `workflow` scope, so `.github/workflows/ci.yml` still cannot be pushed. Confirmed the remote has
no `.github` directory at all (`git ls-tree origin/main` returns nothing for it), and `main` is
**2 commits ahead** of `origin/main` — `4bceb9ce` and `38d8c81d`, which carry the workflow.

Remedy is one command by the account owner: `gh auth refresh -h github.com -s workflow`.

## What is NOT blocked

The workflow itself is sound and would pass. Every gate it runs was executed locally today at the
same strictness:

| CI step | Local result |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 464 files already formatted |
| `mypy src launcher.py scripts` | clean, 166 source files |
| `pytest tests/ -q` | **1019 passed** |
| pytest, reverse file order | **1019 passed** |
| `check-code.mjs --self-test` | PASS (27 extensions, 18 languages) |
| `check-tests.mjs --self-test` | PASS (14 extensions, 9 languages) |
| `audit-agent-claims.ps1` / `audit-disk-layout.ps1` | PASS / PASS |

## Why this distinction matters

Pushing the workflow without branch protection still buys most of the value: the gates *run* on every
push and pull request to `main`, and a red run is visible. What it does not buy is *enforcement* — a
red run cannot block a merge. Recording Major #1 as one indivisible founder task hides that the
larger half is achievable today with a token refresh, and the smaller half needs a paid plan.

Neither `.launch/STATE.md` nor `CURRENT.md` is edited here; both are claimed elsewhere.
