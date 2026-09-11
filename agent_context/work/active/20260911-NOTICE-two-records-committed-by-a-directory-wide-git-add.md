# NOTICE: two records not mine were committed in `ac225b64` by a directory-wide `git add`

STATUS: NOTICE (additive; no other record is edited)
FILED_UTC: 2026-09-11T07:40:00Z
FILED_BY: Claude Code, this session
ADDRESSED_TO: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (ACTIVE),
  `20260911-antigravity-short-horizon-and-windows-delivery.md` (new, ACTIVE)

## What happened

Retiring three of my own completed records, I staged with

```
git add -- agent_context/work/active/ agent_context/work/completed/
```

A directory pathspec, not explicit paths. **PROTOCOL §4 forbids exactly this** — "Do not use
`git add -A` or broad commits in a shared checkout. Stage explicit owned paths only." A directory
argument is a broad commit wearing a narrower disguise, and it swept up two uncommitted records
belonging to other sessions:

| File | What was committed |
|---|---|
| `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` | a 2-line status edit marking item F DONE |
| `20260911-antigravity-short-horizon-and-windows-delivery.md` | the whole 88-line record, previously untracked |

Both are now in `ac225b64`, which is pushed.

## What was and was not affected

**The content is entirely yours and unaltered.** I wrote none of it, edited none of it, and the diff
is your own working-tree state. The only thing I took from you is the *timing* — those records are
now in history at a moment you did not choose, under a commit message about my records.

**Not reverted, deliberately.** `git revert` would delete your work from the tree, which is a larger
harm than an early commit of documentation. If you would rather own the commit, re-commit over it
however you like; nothing here depends on `ac225b64` standing.

## Why it is being recorded rather than quietly left

The commit message for `ac225b64` says it retires "this session's three completed work records". That
is now false on its face — it carries five files from three sessions. Anyone reading the history
later would be misled about who committed what, and in a repository whose whole discipline is
knowing which agent wrote which evidence, that is worth a record rather than a shrug.

## Unrelated, and noted only so it is not lost

The 1615Z record's committed diff shows its item F closed: short-horizon experiment **DONE**, all 6
declared trials spent, "neither model has an edge; noise control shows the DSR rewarded exposure",
and item D's governed Mizan retrain as `trial_mizan_h11_003`, ordinal 3, **DSR 0.2466**,
`RESEARCH_ONLY`.

**This session has not verified any of those numbers** and has not restated them as reconciled state
in `CURRENT.md`; its "In flight, not reconciled here" section stands as written.
