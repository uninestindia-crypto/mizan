# Program-level majors: CI protection, craft baseline, stale artifact, training adjudication

TASK_ID: 20260825-claude-program-majors
AGENT: Claude Code (Opus 5)
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-25
STARTING_REVISION: `b9f4f70` (main)
WORKTREE_OR_BRANCH: D:\quant_system on main; **also claims branch `ci-workflow-pending`**

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

### A correction from a peer: `loop-in-test` included false positives

`quant-system-0f` reports `loop-in-test` moved 31 -> 20 at `ff51b631`, and that **9 of the original
31 were false positives**: the rule's line regex matches a Python comprehension's `for` clause.
Notice at `agent_context/work/active/20260825-NOTICE-loop-in-test-comprehension-false-positive.md`.

So the 47-finding test baseline I recorded was itself partly noise, in the same direction as the
`tmp/` contamination it replaced — a checker counting things that are not defects. Recorded rather
than quietly amended, because I published 47 as a corrected figure and it was not fully corrected.
The lesson repeats: a checker's output is a measurement of the checker as much as of the code.

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

`long-line`, `deep-nesting`, `long-function` and `god-file` are 677 of the 679. Characterised
rather than left as a number, because the composition decides the remedy:

**Concentration.** `server/ui/journeys.py` (59), `server/security.py` (27), `server/ui/templates.py`
(12), `server/supervisor.py` (10) — 108 of them in four files, all arriving with the
`codex/real-journey-api` merge.

**Those four are freshly adjudicated.** They carry the independent PASS at `474795f`. Reshaping
adjudicated source for style would mean the adjudicated artifact no longer matches the adjudicated
code, which trades the programme's only genuine certification for a lint count. That is a bad trade
and the reason is substantive, not procedural.

**`long-line` is largely not debt.** The checker's `maxLineLength` is 120 while ruff formats to 100
and does not enforce E501, so these are lines the formatter cannot break. Sampling the largest
offender shows what they are:

```
152 chars:     <section id="tab-ingestion" class="tab-panel active" data-test="journey-ingestion" …
142 chars:       <p class="journey-subtitle">Point-in-time NSE equity data acquisition, SHA-256 …
```

Embedded HTML markup in a UI renderer. Breaking those lines would hurt readability and risk changing
rendered output. The checker's own instruction covers this case — `craft-allow: <rule-id> — <reason>`
or a `.code-craft.json` threshold — and 44 of `journeys.py`'s findings are this shape.

**What I deliberately did not do.** Raising `maxLineLength` in `.code-craft.json` would clear a large
share of the 382 in one line. I did not, because a threshold changed to make a count go down is
goalpost-moving, and this repository has enough of that in its history. The threshold should move
only if an owner decides 120 is wrong for a UI renderer, and that is their call with their reasons
recorded.

The measurement is now truthful and the composition is known. That is what was blocking anyone from
acting; the acting itself belongs to the path owners.

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

## Training-path adjudication — made adjudicable, not closed

I cannot adjudicate this. Part of the scope is my own work: `promotion_pipeline.py`,
`run_governed_promotion.py`, and repairs to `holdout.py`, `stress.py` and `ledger.py`. Self-review
of those would be worth nothing. What I could do is narrow the surface and write the brief:
`.launch/ADJUDICATION-BRIEF-TRAINING-PATH.md`.

I did **not** write the training runner, the campaign drivers, or any research result, so reading
their evidence is genuinely independent.

### Corroborated by reading the v2 evidence store directly

| CURRENT.md claim | independent reading | verdict |
|---|---|---|
| 50 published models | 50 MODEL resources | corroborated |
| all schema v2 | `('quantos.ridge_technical_six', 2)` on all | corroborated |
| all RESEARCH_ONLY | 50 of 50 | corroborated |
| nothing promotable | **0 of 50 reach the 0.95 gate** | corroborated |

### A discrepancy I found, chased, and withdrew

The store's maximum published DSR is `0.584510`; CURRENT.md's headline is `0.217695`. I read that
as a 2.7x contradiction, and it is not one.

`multiplicity_count` across the 50 models runs **1, 2, 3 … 50, one model at each value**. Each was
scored against the attempts spent at the moment it ran. The `0.584510` model carries ordinal **1** —
the first trial, deflated against a single attempt. `0.217695` is the re-deflation against the final
count of 50. Both are correct measurements of different quantities, and CURRENT.md already documents
the same mechanism for v1.

My first reading of `multiplicity_count = 1` on the best model was that the campaign had reproduced
the `default=1` deflation defect a peer caught in my own runner. Checking the distribution rather
than the single value refuted that. Recorded because the wrong version was one commit away from a
record, and the check that settled it took one command.

**The conclusion survives the most generous reading.** Even taking each model's flattering published
DSR at its own low ordinal, zero of fifty clear the gate; median published DSR is `0.017352`.

### Six questions left for a real adjudicator

Reproducibility of the drivers; whether the `0.217695` re-deflation exists as a computation rather
than a record; cache provenance; whether the six ungoverned screens are accounted in total
multiplicity; my own contributions; and whether gitignored research evidence — unadjudicable from a
clean clone — is acceptable at all.

## Status of the four items

| # | Item | Outcome |
|---|---|---|
| 1 | CI branch protection | **Blocked by plan** (403, private repo on free tier) — and its prerequisite never existed. CI workflow written. Founder decision required. |
| 2 | Craft baseline | **Tooling repaired.** 98.6% / 99.7% of findings were gitignored scratch. True baseline 679 / 47. `focused-test` was 0, not 8. |
| 3 | Stale artifact | **Rebuilt and verified at HEAD.** 125 `quant_system` modules confirmed by reading the archive TOC. |
| 4 | Training adjudication | **Made adjudicable.** Brief written, four claims corroborated, one false alarm withdrawn, six questions posed. |

## Final state, and what each remaining item is actually waiting on

Recorded precisely because "blocked" is a word that hides things. Neither remaining item is waiting
on engineering.

### Major #1 — waiting on a payment method and a browser

Two independent blocks, both **tested rather than assumed**:

| block | evidence |
|---|---|
| branch protection unavailable | `403 Upgrade to GitHub Pro` on `branches/main/protection` **and** on `rulesets`; repo is private, owner type User |
| workflow cannot be pushed | token scopes are `gist, read:org, repo` — no `workflow`; GitHub refuses OAuth pushes creating `.github/workflows/**` |
| SSH as an alternative | no keys present; `git@github.com: Permission denied (publickey)` |

Everything an agent can do is done: the workflow exists on branch `ci-workflow-pending` (claimed
here, so the claim audit passes), a pushable copy sits at `ci/gates-workflow.yml` with activation
instructions, and `scripts/run-gates.ps1` runs the identical gate set locally today.

Activation: `gh auth refresh -s workflow`, then merge `ci-workflow-pending`. Plus the plan decision.

### Training adjudication — five of six resolved; Q5 needs a reviewer who is not me

| Q | State |
|---|---|
| 1 reproducibility | Integrity proven. Determinism **downgraded on reviewer objection** to one instrument, four repetitions |
| 2 re-deflation real | Answered — same model, sharpe 3.2207 |
| 3 cache provenance | Integrity proven (100 datasets, 0 invalid); point-in-time honesty open |
| 4 search accounting | Answered — understated ~48%, verdict unchanged at every count to 110 |
| 5 my own work | **Partially reviewed.** Determinism downgraded, item 4 cleared. Full pass outstanding |
| 6 gitignored evidence | Blocker removed — committed inventory, 3,771 resources |

Three of the five risks I flagged for review are now tests rather than claims: the CRR gamma
convergence with its control, the holdout durability-on-commit-failure path, and the fail-closed
leverage guard's success path. Each was a case where I had verified the new behaviour and not the
preserved behaviour.

The only reviewer who answered declared a conflict of interest unprompted — they own `execution/**`
and `modeling/**` and wrote the campaign drivers — so they are adjacent on three of five items. They
are genuinely independent on `holdout.py`, `greeks.py`, `governor.py` and the CRR lattice, and that
is where a pass would be worth having.

### What must not happen

Q5 must not be closed by my assertion, and Major #1 must not be closed by an agent writing repository
settings through `gh api`. Either would produce a green record with nothing behind it, which is the
failure `.launch/reports/quarantine/` exists to remember.

## Next safe action

Founder: `gh auth refresh -s workflow`, then the Pro-vs-public decision. A reviewer other than me
takes `holdout.py` and `greeks.py`. The 677 structural craft findings belong to their path owners —
`loop-in-test` is already being repaired by another session.
