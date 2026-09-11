# Active work: corporate-action authority refresh cadence

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-09-10
STARTING_REVISION: 54aa7097
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, disjoint paths — see isolation note)

## Objective

Founder instruction: fix the corporate-action authority refresh cadence, so the authority window can
never trail the newest ingested bar. Root cause established in
`20260910-NOTICE-corporate-action-authority-window-stale-vs-price-cache.md`.

## Owned paths

- `scripts/ingest_all_market_data.py` (functions `fetch_or_load_corporate_actions`,
  `build_corporate_action_authority`, and their callsite in `IngestionEngine._ingest_symbol`)
- `tests/test_ingest_corporate_action_authority.py` (new file)
- `agent_context/work/active/20260910-claude-corporate-action-authority-refresh-cadence.md` (this file)
- `agent_context/work/active/20260910-NOTICE-corporate-action-authority-window-stale-vs-price-cache.md`
- `data/evidence/market-cache/nifty500-refresh-20230828-20260827/corporate-actions/` (refetch only,
  added on founder instruction — see Non-goals)

## Non-goals

- **No cache rewrite.** Existing stores under `data/evidence/market-cache/**` are read-only here.
  Hermes' record lists them as do-not-touch; correcting historical manifests is a separate decision.
- ~~**No refetch run.**~~ **SCOPE CHANGED 2026-09-10 on explicit founder instruction** ("run the
  refetch to close the gap"). The refetch is now in scope for the **NIFTY500 live refresh cache
  only**: `data/evidence/market-cache/nifty500-refresh-20230828-20260827/corporate-actions/`.
  Added to owned paths.
- **The other two corporate-action stores stay untouched**, deliberately:
  `all-market-20160822-20260821` (3,359 files) and `nifty50-current-20160822-20260821` (50) are
  frozen historical research corpora whose window genuinely ends 2026-08-21. Their authority is
  correct *for them*. Refetching would move the evidence under published research results, and
  neither feeds a live book.
- `scripts/cached_nifty50_io.py` has a **different** `fetch_or_load_corporate_actions` used by
  `run_cached_nifty50_ridge_campaign.py`. Out of scope — historical campaign, different contract.
- `scripts/run_scheduled_paper_session.py` — read only. It already passes the correct dates; the
  defect is downstream of it. Not edited.
- `scripts/daily_auto_sync.ps1` — listed as a disputed money path by Hermes. Not touched.
- No strategy, model, portfolio, evidence-schema, or promotion change.

### Isolation note (PROTOCOL §1)

- Owned paths exact and disjoint. Checked against all 80 active records: no record's owned-path
  block names `scripts/ingest_all_market_data.py`. It appears only in
  `20260825-NOTICE-repo-gates-red-in-ingestion-scripts.md` (a lint observation) and
  `20260829-claude-live-mizan-feature-provider.md` (a behavioural observation) — neither claims it.
- No repo-wide formatter, generator, migration, or staging. Ruff/mypy scoped to the owned file.
- No shared contract changed: `AuthorityReference` is consumed, not redefined.

## Plan

1. DONE — establish root cause with measured evidence; file NOTICE.
2. DONE — confirm ownership is free; create this record before editing.
3. Repair the three defects below.
4. Add tests that fail against the old behaviour.
5. Run ruff + mypy + the new tests; run both audit scripts.

## Current step

DONE. Repaired, tested, refetch run on founder instruction, evidence committed.

## The refetch (2026-09-10, founder-authorised)

500 NIFTY500 corporate-action authorities re-pulled from the NSE public API, sequential at 0.35 s.

| | Before | After |
|---|---:|---:|
| Provenance sidecars | 0 | **500, all `FETCHED`** |
| `effective_from` | 2016-08-22 (hardcoded literal) | **2016-08-22 (fetched)** |
| `effective_to` | 2026-08-21 (hardcoded literal) | **2026-09-10 (fetched)** |
| Total CA records | 2,527 | **6,243** |
| Records after 2026-08-21 | 0 visible | **38 recovered** |
| HEG records | 4 | **17, including `07-Sep-2026 Demerger`** |

Symbols that grew: **417**. Unchanged: 83. **Lost records: 0**, verified per-symbol against
`git show HEAD:<path>`.

**The HEG demerger is the confirmed cause** of the -64.3% gap that cost the XS-Monthly book
0.608 pp of NAV. It is now in the authority.

### Two defects the refetch itself exposed, both repaired

**(a) The corporate-action window was bounded by the bar request.** The first refetch used the
scheduled refresh's own `to_day - 3*365` = 2023-09-11, but the store retains bars from
**2023-08-28** -- leaving 14 days of bars with no authority coverage at the *start* of the series.
The same defect as the stale end, at the other end. Fixed with `CA_HISTORY_ANCHOR = 2016-08-22`:
the corporate-action query is never bounded by the bar window, because a wider query costs the same
single API call. Pinned by
`test_corporate_actions_are_requested_from_the_history_anchor_not_the_bar_window`.

**(b) My own freshness check compared only `effective_to`.** The second refetch reported
"records changed: 0" in exactly 175 s -- 500 x 0.35 s of sleep and **zero network calls**. Widening
the lower bound did not invalidate the cache, so a run that asked for more history silently got
less and reported success. `_provenance_is_fresh` now requires
`effective_from <= start and effective_to >= end`. Pinned by
`test_a_widened_lower_bound_forces_a_refetch`, with
`test_a_narrower_request_still_reuses_a_wider_cached_record` guarding against the obvious
over-correction. Found by disbelieving a suspiciously fast success, not by a test.

### What the refetch does NOT do

Existing dataset manifests keep the authority reference they were written with. They are immutable
evidence and rewriting them would violate that law. The refreshed authority binds **future**
ingests; the next scheduled refresh writes datasets whose authority reaches their own newest bar.

## Decision rationale

Three compounding defects, all in `scripts/ingest_all_market_data.py`:

1. **`build_corporate_action_authority` hardcodes its window** (`ingest_all_market_data.py:160`):
   `publication_date=date(2026, 8, 24)`, `effective_from=date(2016, 8, 22)`,
   `effective_to=date(2026, 8, 21)` are literals. Every dataset ingested on any date claims the same
   coverage. This is the direct cause of the measured gap. Already flagged in a comment at
   `run_scheduled_paper_session.py:210` by another agent, and never repaired.

2. **`fetch_or_load_corporate_actions` never re-fetches** (`ingest_all_market_data.py:114`): the
   `if target.is_file()` branch returns the cached file whenever it parses as a list. Once written,
   a symbol's corporate-action record is frozen for the life of the repository, so even a corrected
   window would be labelling stale content.

3. **A failed fetch writes `[]` and that becomes a permanent authoritative "no actions"**
   (`ingest_all_market_data.py:154`): every exception path falls through to writing an empty list,
   which defect 2 then treats as a valid cache forever. One network blip permanently poisons a
   symbol. This is fail-open on exactly the evidence used to detect a corporate action.

**Why all three, and not just (1).** Fixing the window alone would produce an authority that
*claims* to cover today while containing content fetched weeks ago — a worse failure than the
current one, because the label would then be actively false rather than merely stale. The refresh
cadence is only real if the content refreshes too.

**Why the window is derived from content, not from the request.** An authority must describe what it
actually covers. `effective_to` is set from the requested `end` **only when a fetch actually
succeeded**; a load from cache keeps the window the cached file was fetched under, persisted
alongside it. Deriving it from the request unconditionally would reintroduce defect 1 with extra
steps.

## Commands and outcomes

| Command | Result |
|---|---|
| `pytest tests/test_ingest_corporate_action_authority.py -q` | **8 passed** |
| `pytest tests/ -q --no-header` | **1336 passed**, 0 failed, 483.30s |
| `ruff check` (owned files) | All checks passed |
| `ruff format --check` (owned files) | 2 files already formatted |
| `mypy src launcher.py scripts` | **31 errors, 11 files — identical before and after**; **0 in the owned file** |
| `audit-agent-claims.ps1` | PASS, exit 0 |
| `audit-disk-layout.ps1` | PASS, exit 0 |

**The 31 mypy errors are a pre-existing red gate, measured on both sides of this change** by
stashing the owned file and re-running. They are not introduced here and are not mine to repair:
most are `type-arg` in `src/quant_system/research_xs_monthly/` and `scripts/run_xs_monthly_*`, which
are under Hermes Agent's ACTIVE claim.

### The old behaviour was demonstrated, not assumed

The pre-repair functions were extracted from `git show HEAD:scripts/ingest_all_market_data.py` and
exercised directly with a stubbed `urlopen`:

```
1st call (end=2026-08-21): count=1 fetches=1
2nd call (end=2026-09-09): count=1 fetches=1
   CONFIRMED: a wider window did NOT trigger a refetch. Record frozen.

failed fetch wrote: '[]' count=0
next run after network restored: count=0 extra_fetches=0
   CONFIRMED: [] from a failed fetch is trusted forever; symbol never retried.
```

Defect 1 needs no demonstration: `effective_to=date(2026, 8, 21)` was a literal.

## Files changed

- `scripts/ingest_all_market_data.py` — +247 / -38
- `tests/test_ingest_corporate_action_authority.py` — new, 8 tests
- `agent_context/work/active/20260910-NOTICE-corporate-action-authority-window-stale-vs-price-cache.md` — new
- `agent_context/work/active/20260910-claude-corporate-action-authority-refresh-cadence.md` — this file

Nothing staged, nothing committed, no cache rebuilt, no authority refetched.

## What was deliberately NOT changed, and why

`parse_args` still defaults `--from-date 2016-08-22` and `--to-date 2026-08-21`. Those defaults pair
with the default `--cache-root .../all-market-20160822-20260821`, whose **directory name encodes the
same window**. Defaulting `--to-date` to today while the cache root still says `20260821` would
replace one mislabelling with another, and would silently change the window under anyone reproducing
the historical all-market corpus. The scheduled refresh
(`run_scheduled_paper_session.build_refresh_command`) already passes both dates explicitly, so this
default was never the cadence defect. Left as a coherent reproducibility anchor.

## Blockers and conflicts

None. Paths verified unclaimed. The NOTICE addresses Codex and Hermes additively; neither record edited.

## Stop point

Code repaired and tested. No cache rebuilt, no authority refetched, nothing staged or committed.

## Next safe action

Founder or the refresh owner decides whether to re-pull the 500 authorities to close the existing
2026-08-21..today gap in the live cache.
