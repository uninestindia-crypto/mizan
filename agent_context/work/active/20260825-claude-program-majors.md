# Program-level majors: CI protection, craft baseline, stale artifact, training adjudication

TASK_ID: 20260825-claude-program-majors
AGENT: Claude Code (Opus 5)
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-25
STARTING_REVISION: `b9f4f70` (main)
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Founder-directed, four items:

1. **Major #1** — CI branch protection. A GitHub repository setting.
2. **Major #2** — craft baseline (recorded as 207 code / 33 test findings).
3. **Major #3** — stale shipped artifact; rebuild past the gate repair.
4. **Training-path adjudication** — the largest remaining evidence gap.

## Major #2 — the baseline was measuring the wrong thing

Measured before planning any fix, and the result changes the task completely.

| Checker | findings in `tmp/` | real findings | contamination |
|---|---:|---:|---:|
| `check-code.mjs` | 46,824 | **679** | 98.6% |
| `check-tests.mjs` | 15,924 | **47** | 99.7% |

`tmp/` holds full stale copies of the repository left by earlier mutation and verifier runs —
`tmp/mutation-slice3-7708fd7/`, `tmp/verifier-clean/`, `tmp/verifier-s4-mut-leakage-4a4/` — each
containing its own `tests/` and `src/`. `tmp/` is gitignored (`.gitignore:22`).

Both checkers carry a `SKIP_DIR` set — `node_modules`, `.git`, `dist`, `build`, `.venv`, `venv`,
`__pycache__` and more — and **neither lists `tmp`**. So every finding in every throwaway copy is
counted, repeatedly, alongside the real one.

That means the recorded baseline of "207 code / 33 test findings" and any number derived from
running these checkers today are both measuring duplicated throwaway trees. The task is not "fix
39 files owned by several live records". The first task is to make the tool measure the repository.

**Fix:** add `tmp` to `SKIP_DIR` in both checkers. One line each.

### Ownership

`scripts/check-code.mjs` and `scripts/check-tests.mjs` are claimed by
`20260821-claude-check-tests-casebody.md`, **STATUS: HANDOFF_REQUIRED**. PROTOCOL section 5 states
such a record stands until another agent explicitly adopts it. This record is that explicit
adoption, limited to those two files. The rest of that record's claim is not adopted.

## Major #1 — cannot be done by an agent, and should not be

Branch protection is a GitHub repository setting. `gh` is authenticated in this environment, so
`gh api` could technically write it. I am not doing that: changing repository settings is an
outward-facing, hard-to-reverse action on a real repository, and it needs the founder's explicit
decision rather than an agent's inference from a goal statement. Exact commands are provided for
the founder to run.

### The true baseline, after the fix

| code craft | count | | test craft | count |
|---|---:|---|---|---:|
| long-line | 382 | | loop-in-test | 36 |
| deep-nesting | 162 | | sleep-in-test | 8 |
| long-function | 94 | | huge-test-file | 2 |
| god-file | 39 | | no-assertion | 1 |
| unexplained-escape | 1 | | | |
| many-params | 1 | | | |
| **total** | **679** | | **total** | **47** |

Both checkers' self-tests still pass: `PASS: code-craft self-test (27 extensions, 18 languages)`
and `PASS: test-craft self-test (14 extensions, 9 languages)`.

### The urgent item was not real

`focused-test` counted 8 before the fix and **0** after; `skipped-test` likewise **0**. Every one
was inside a `tmp/` copy. This mattered more than the totals: a committed focus disables every other
test in its file while the suite still reports green, so 8 of them would have meant several files
silently not running and every suite figure in this session unsound. There are none in the
repository. The 929-passing figure holds.

Whole rule classes vanished with the contamination — `commented-out-code` (1105),
`swallowed-error` (92), and all but one `unexplained-escape` (211 to 1). None existed in the
repository at all.

### What remains is structural debt, not defects

`long-line`, `deep-nesting`, `long-function` and `god-file` are 677 of the 679. These are shape
findings across `modeling/**`, `execution/**`, `server/**` and `analytics/**` — files owned by
several live records. They are not repaired here: doing so would mean reshaping other agents'
active files for style, which PROTOCOL section 4 puts under single-owner coordination, and a
reformat of live work is the highest-risk low-value action available. The measurement is now
truthful, which is the part that was blocking anyone from acting on it.

## Next safe action

Major #3 — rebuild the shipped artifact at a revision past the gate repair.
