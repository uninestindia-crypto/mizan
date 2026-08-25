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

## Major #1 — blocked by the GitHub plan, and its prerequisite never existed

Measured rather than assumed, and both findings change the item.

**1. Branch protection is unavailable on this account.** `gh` is authenticated as
`uninestindia-crypto`, and the repository is **private** with owner type **User** (free plan). Both
relevant endpoints refuse:

```
GET repos/…/branches/main/protection  -> 403 "Upgrade to GitHub Pro or make this
                                              repository public to enable this feature."
GET repos/…/rulesets                  -> 403  (same message)
```

Branch protection and rulesets on a private repository require GitHub Pro/Team/Enterprise. This is
not a permissions question about what an agent may do — **nobody can set it on this plan**, founder
included, without either upgrading or making the repository public.

**2. There is no CI to protect with.** `.github/` does not exist, and
`git log --all -- .github/workflows` returns nothing: no workflow has ever existed on any branch.
`.launch/STATE.md` records this major as "Protected remote / CI integration in progress". Nothing
was in progress; nothing existed.

So the item as recorded had an unmet prerequisite hiding behind a plan limitation.

### What was actually done

Wrote `.github/workflows/ci.yml`. That is a file in the repository, not a settings change, and it is
the prerequisite branch protection would gate on. It runs on `windows-latest` because the release
artifact is a PyInstaller Windows x64 bundle and a Linux runner would not represent it.

Every step is a command this repository already runs by hand, at the same strictness: `uv sync
--frozen`, `ruff check`, `ruff format --check`, strict `mypy src launcher.py scripts`, pytest in
normal **and reverse file order**, both craft-checker self-tests, and both audits. Reverse order is
included because a suite that is green forwards and red backwards is not green, and this repository
has a shared fixed `--basetemp` that makes ordering coupling plausible.

Validated as YAML; 12 steps parse.

### The founder's decision

1. **Upgrade to GitHub Pro** — enables branch protection and rulesets on this private repository.
2. **Make the repository public** — enables both free, but publishes the code.
3. **Neither** — CI still runs and reports on every push and PR; it simply cannot be made
   *required* before merge.

Option 3 is not worthless: the gate runs and is visible. It just cannot block.

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

## Major #3 — rebuilt and verified (COMPLETE)

Rebuilt at `dab7f7b3`, the current HEAD and past the gate repair. Tracked tree was clean at build
time, so provenance is unambiguous.

| | before | after |
|---|---|---|
| built | 2026-08-20 05:27 | 2026-08-25 12:23 |
| manifest `git_commit_sha` | `b5bc061…` (41 h *before* the commit it claimed) | `dab7f7b3…` — **exact match to HEAD** |
| bundle | missing modules it was certified for | **125 `quant_system` modules** |

`dist/` is gitignored, so this is a local artifact; nothing tracked changed.

### Two build-process findings

**`scripts/build_dist.py` cannot run as documented.** It fails with
`ModuleNotFoundError: No module named 'launcher'` unless the repository root is on `PYTHONPATH`
alongside `src`. `launcher.py` sits at the root and `release/verifier.py:25` imports it. `pyproject`
supplies `pythonpath = ["src", "."]` to pytest only, so the build works under test and fails from a
shell. Anyone following a documented build command hits this. Not repaired here — `build_dist.py`
and `release/**` are outside this record's adopted paths.

**Grep is not a valid way to check bundle contents**, and both the original finding and my own first
check used it. PyInstaller compiles modules into an embedded PYZ, so a module name can appear in the
binary while the module is absent, and a present module produces no loose file. My first grep said
"present" for all six; my second said "ABSENT" for all six; both were unreliable.

The authoritative check reads the archive: extract `PYZ.pyz` via `CArchiveReader`, open it with
`ZlibArchiveReader`, and enumerate `toc`. That gives 1,932 modules total, 125 under `quant_system`,
with `execution.paper_pilot`, `execution.realtime_shadow`, `execution.governed_strategy`,
`modeling.promotion_pipeline`, `modeling.holdout` and `modeling.promotion` all present.

The original conclusion was right for a reason independent of its method: `promotion_pipeline` did
not exist until this session, so an artifact built on 2026-08-20 could not have contained it.

### An error I made and reverted

Believing `dist/QuantOS` and `dist/quantos` were two directories, I moved the first aside as stale.
Windows is case-insensitive — they are the same directory, and I had moved the freshly built
artifact. Restored immediately and verified byte-size and manifest SHA. Nothing was lost **because
it was moved, not deleted**, which is the whole reason that rule exists.

`dist/QuantOS_v1.0.0_portable.zip` (2026-08-20, 58 MB) is genuinely superseded by
`dist/quantos-v1.0.0-windows-x86_64.zip` (2026-08-25, 59 MB). Flagged, not deleted.

## Next safe action

Major #1 — report the exact branch-protection commands for the founder. Then the training-path
adjudication gap.
