# NOTICE: CI has been down for billing since 2026-08-29, and I edited two claimed files to say so

STATUS: NOTICE (additive; no other agent's record is edited)
DATE_UTC: 2026-09-01T12:40:00Z
FILED_BY: Claude Code, `20260901-1030Z-claude-seven-item-sweep.md`
AUTHORITY: explicit founder instruction, 2026-09-01, to work seven named items including the
  correction of these two files
ADDRESSED TO:
  - owner of `20260821-0530Z-claude-slice4-certification.md`, which claims `.launch/STATE.md`
  - owners of `20260820-codex-slice4-ridge-training.md` and `20260821-claude-ci-workflow.md`,
    which claim `agent_context/CURRENT.md`

## The measurement

`.launch/STATE.md` Major #1 and `CURRENT.md`'s Major table both read **CLOSED**, citing GitHub
Actions run `#32936340154` passing in 3m30s on 2026-08-20. That run did pass. It is also the last
thing either file knows about.

Measured against the live API today:

```
last successful run : 33265792098, 2026-08-29T17:30:13Z
runs since          : 25 -- 8 on 2026-08-30, 17 on 2026-08-31, all `failure`
failure duration    : ~3 seconds each
annotation          : "The job was not started because recent account payments have failed or your
                       spending limit needs to be increased"
```

**The gate is red for billing, not for code.** Nothing committed since 2026-08-29 has been checked
by CI — including everything committed today. The commits are individually gated by hand (`ruff`,
`ruff format --check`, `mypy src launcher.py scripts`, full `pytest`), and that is not the same
thing as the gate having run.

## Three separate claims in those files were out of date, not one

`CURRENT.md`'s "Next safe actions" item 1 said the workflow "exists on branch `ci-workflow-pending`
but could not be pushed: the token lacks `workflow` scope".

- The workflow **is** on `main`: `.github/workflows/ci.yml`.
- The token **does** carry the scope: `gh auth status` reports `'gist', 'read:org', 'repo',
  'workflow'`.
- So that file contradicted **itself** — its Major table said the workflow was pushed and passing
  while its action list said it could not be pushed.

Both were repaired. The third claim, "branch protection ... is a repository setting no agent can
make", is true as far as it goes and implies the founder can simply make it. They cannot:
`403 Upgrade to GitHub Pro or make this repository public`, on a `private` repository, plan `User`.
That was already filed as `20260826-NOTICE-branch-protection-unavailable-on-plan.md` and had not
reached either file.

## What I changed, exactly

- `.launch/STATE.md`: Major #1 row `CLOSED` -> `REOPENED 2026-09-01`, with the measurement.
- `agent_context/CURRENT.md`: the Major #1 table row, and "Next safe actions" item 1, rewritten to
  the measured state.

Nothing else in either file was touched. No other record was edited. `CURRENT.md` itself records
the precedent for founder-instructed edits under a live claim: *"The sections above were reconciled
on explicit founder instruction; nothing those records wrote elsewhere in this file was altered."*
The same applies here.

## What is now the founder's, in order

1. **Fix the GitHub Actions billing.** Until then the repository has no automated gate, and
   "the gates passed" is a statement about someone's laptop.
2. **Choose between GitHub Pro and a public repository**, because branch protection requires one or
   the other. Without it the `gates` check cannot be made required even once billing is restored.
