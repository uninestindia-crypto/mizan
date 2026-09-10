# Active work: Amazon Bedrock dual-model audit path (GPT-6 Astra + Claude Fable 5.1)

STATUS: ACTIVE
OWNER: Claude Code (Opus 5), on founder instruction
TOOL: Claude Code
STARTED_UTC: 2026-09-10T00:00:00Z
STARTING_REVISION: `c6532fbd`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, disjoint paths with written claims)

## Objective

Give the founder a second, independent transport for the dual-model Mīzān audit that runs entirely on
**Amazon Bedrock** — OpenAI GPT-6 Astra for the first opinion and Anthropic Claude Fable 5.1 for the
second — instead of the router.one aggregator the existing runner uses.

Both models analyse the same subject: the two live ₹10 Lakh **virtual-money / paper-trading** Mīzān
systems, their features, their governed trial evidence, and their friction model. No real capital is
involved and no order routing is added.

## Owned paths

- `src/quant_system/alpha/bedrock_providers.py` (new — Bedrock transport for both model families)
- `scripts/run_mizan_dual_opinion_bedrock.py` (new — Bedrock dual-opinion runner)
- `reports/mizan_bedrock_audit/` (new — output directory for this runner only)
- `docs/bedrock-dual-model-setup.md` (new — founder-facing AWS prerequisite guide)
- `pyproject.toml` (dev extra only — **on explicit founder instruction**, see below)
- `uv.lock` (regenerated to match, same authority)
- `agent_context/work/active/20260910-NOTICE-uv-lock-hash-changed-by-ai-sdk-dependencies.md`
- `agent_context/work/active/20260910-claude-bedrock-dual-model-audit.md` (this record)

## Non-goals

- **Do NOT edit `scripts/run_mizan_dual_opinion.py`, `scripts/run_mizan_live_audit.py`,
  `scripts/run_gpt56_sol_second_opinion.py`, `scripts/run_claude_analysis.py`,
  `scripts/run_claude_engineering_edits.py`, or `reports/mizan_live_audit/`.** Every one of those is
  claimed by the ACTIVE record `20260904-antigravity-claude-fable-analysis.md`. The Bedrock runner is
  a **new sibling**, not a modification of theirs. The router.one path keeps working untouched.
- ~~Do NOT edit `pyproject.toml` or `uv.lock`.~~ **Superseded by explicit founder instruction** on
  2026-09-10: "add anthropic and openai to pyproject.toml". PROTOCOL §4 requires single-owner
  coordination for that file; a direct founder instruction is that coordination, and the same basis
  is precedented in `CURRENT.md` ("reconciled on explicit founder instruction"). No active record
  claimed `pyproject.toml` — the other references to it are agents declining to touch it for the
  same §4 reason. Scope held to the `dev` extra plus the matching lock regeneration; nothing else
  in either file was altered.
- Do NOT rebuild `dist/` release artifacts, edit `.launch/`, or restate `CURRENT.md` Major #3. The
  dependency change invalidates the current provenance artifact, which is recorded in a notice for
  the release path's owner rather than repaired here.
- No live-money routing. No promotion of any model. No change to the governed training, evidence, or
  execution paths.
- No credentials, tokens, or `.env` values written into repository context.

## Plan

1. DONE — Startup sequence: read `CURRENT.md`, `PROTOCOL.md`, `.launch/STATE.md`, `git status`,
   `git worktree list`, `git branch --list`, and every record in `work/active/`.
2. DONE — Establish which paths are claimed. `run_mizan_dual_opinion.py` is claimed; work alongside it.
3. DONE — Verify Bedrock availability against the live AWS model cards rather than from model memory.
4. DONE — Implement `bedrock_providers.py`, the runner, and the founder setup guide.
5. DONE — Static gates: ruff clean, strict mypy clean on both new files.
6. DONE — Offline verification: live-state read, dossier build, credential-absent failure path.
   No API call was made and no money was spent from this record.

## Current step

Complete. Nothing further can be verified from here: the remaining step is the founder supplying
Bedrock credentials, which is an account action an agent must not perform.

## Finding: the router.one dossier is stale, and one number has flipped sign

Recorded as an observation for the owner of `scripts/run_mizan_dual_opinion.py`, not as a criticism
and not acted on in their file.

That runner states both books' equity as literal prose. Measured against the live state files today:

| | Hardcoded in the router.one runner | Live state, 2026-09-09 | Drift |
|---|---:|---:|---|
| System 1 equity | Rs 9,96,751.26 (-0.325%) | Rs 9,92,276.07 (-0.772%) | Rs 4,475 worse |
| System 2 equity | Rs 10,04,223.88 (**+0.422%**) | Rs 9,98,071.67 (**-0.193%**) | **sign flipped** |

System 2's own state file records `equity: 998071.67` at `2026-09-10T04:09:04Z`, which matches the
independent recomputation from cash plus the marked value of all 99 legs, so the live figure is
corroborated by two routes.

Why this matters more than a stale number usually would: the router.one runner's audit question asks
both models to explain whether System 2's **profit** is "genuine alpha or just riding beta". There is
no profit. Both models would be reasoning about a book that does not exist, and any conclusion they
reached about what is working would be unfounded. A stale positive is the most expensive kind of
stale number in this project, because it is the one that argues for continuing.

The Bedrock runner reads both state files at run time and stamps every figure with its own as-of
date. The DP-fee arithmetic is likewise derived from the live average position size rather than
asserted: at the current 99 legs averaging Rs 8,715.31, a flat Rs 20 DP debit is **22.9 bps** on the
sell leg against a measured selection edge of **+5.3 bps/period**.

The durable fix belongs in the claimed runner and is that owner's to make.

## Decision rationale

**The premise was checked before it was built on.** My training cutoff is May 2026 and I initially
believed Bedrock hosted only OpenAI's open-weight (`gpt-oss`) models, which would have made the
founder's request impossible for the GPT half. That was wrong and was corrected against primary
sources: **GPT-6 Astra reached GA on Bedrock on 2026-09-08**, two days before this record. Both
model cards were read directly for exact identifiers rather than inferred.

Evidence, from the AWS model cards:

| | GPT-6 Astra | Claude Fable 5.1 |
|---|---|---|
| Base model ID | `openai.gpt-6-astra` | `anthropic.claude-fable-5-1` |
| Global CRIS ID | `global.openai.gpt-6-astra` | `global.anthropic.claude-fable-5-1` |
| US geo CRIS ID | `us.openai.gpt-6-astra` | `us.anthropic.claude-fable-5-1` |
| In-Region on `bedrock-runtime` | **Not supported** — CRIS mandatory | **Not supported** — CRIS mandatory |
| API used here | Chat Completions (`/openai/v1`) | Messages (`/anthropic`) |
| ap-south-1 (Mumbai) | Global CRIS only | Global CRIS only |
| Context / max output | 1,050,000 / 128,000 | 1M / 128K |

**One Bedrock API key drives both models.** This is the substantive advantage over the router.one
transport and the reason the request is worth honouring: a single AWS credential, a single bill, and
AWS-side invocation logging for both halves of the audit, instead of a third-party aggregator holding
the key to both.

**Default region `ap-south-1` with global inference profiles.** Mumbai is the founder's own region
and gives the lowest first-hop latency, but neither model offers In-Region or APAC-geo inference
there — only Global CRIS, which routes worldwide with no data-residency guarantee. That is recorded
as a stated property rather than hidden, and both the region and the profile prefix are env-overridable
(`QUANTOS_BEDROCK_REGION`, `QUANTOS_BEDROCK_SCOPE=global|us`) so `us-east-1` + `us.` is one variable away.

**Streaming is used for both calls, and this is a defect repair, not a preference.** The router.one
runner posts non-streaming with a 300 s timeout. Fable 5.1 runs adaptive thinking that cannot be
disabled, at `effort=high` by default, and a single hard-reasoning turn can run many minutes — so the
existing call shape is liable to time out before the model finishes. Both Bedrock calls stream and
assemble the final message.

**Refusal is handled as a primary response path, not an error.** The Fable 5.1 model card states
refusal rates are materially higher than previous Claude models and returns HTTP 200 with
`stop_reason="refusal"`. The server-side `fallbacks` parameter is **not available on Bedrock**, so
there is no automatic rescue; the runner surfaces the refusal category to the operator instead of
writing an empty report file and continuing as if it had succeeded.

**Sampling parameters are left unset.** The card requires temperature 1.0-or-unset, top_p
0.99-or-unset, never both together, and no top_k. Unset is the only shape that cannot violate this.

Rejected alternatives:

- *Edit the existing `run_mizan_dual_opinion.py` to add a `--provider bedrock` flag.* Cleanest design,
  forbidden by the claim on that file. A new sibling costs some duplication and breaks no rule.
- *Raw `httpx` against the Bedrock REST endpoints.* Would have avoided the dependency question
  entirely and matched the existing script's style, but forfeits streaming assembly, typed errors,
  retry/backoff, and refusal typing on a long-running call — the exact things this path needs.
- *`bedrock-mantle` endpoint.* Fable 5.1 is only on Mantle in `us-gov-west-1`, and the AWS card
  itself recommends `bedrock-runtime` for new applications.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git worktree list` / `git branch --list` | PASS | 3 worktrees, 2 codex branches — all left alone |
| Read all `work/active/*.md` | PASS | `run_mizan_dual_opinion.py` claimed by 20260904 Antigravity record |
| WebFetch both AWS model cards | PASS | Identifiers, regions, and constraints in the table above |
| `uv pip install anthropic openai` | PASS | `anthropic==1.4.0`, `openai==3.11.0` into `.venv`; `pyproject.toml` untouched |
| `ruff check` on both new files | PASS | All checks passed |
| `mypy` strict on `bedrock_providers.py` | PASS | No issues found in 1 source file |
| `mypy` strict on the runner (`MYPYPATH=src`) | PASS | No issues found in 1 source file |
| `ruff check src/ scripts/` (repo-wide) | PASS | All checks passed; no regression |
| `mypy src/quant_system` (repo-wide) | PRE-EXISTING FAIL | 15 errors across 147 files, **all** in `research_xs_monthly/` (paper 11, screen 2, dashboard 1, bars 1). Zero in the files added here. Not touched — that module is claimed by `20260903-hermes-xs-monthly-screen-new.md` |
| `run_mizan_dual_opinion_bedrock.py --dry-run` | PASS | Read 97 + 99 live legs, wrote the dossier, refused cleanly with an actionable message when no credential was present. No API call, no spend |
| `scripts/audit-agent-claims.ps1` | PASS (exit 0) | Every workspace has a visible claim and every claim resolves |
| `scripts/audit-disk-layout.ps1` | PASS (exit 0) | No stray QuantOS directories |
| **After the founder-instructed dependency change:** | | |
| `uv lock` | PASS | 48 → 57 packages; 9 added (2 direct, 7 transitive) |
| `uv lock --check` | PASS | Resolved 57 packages, no drift — `uv sync --frozen` still works in clones |
| `pytest tests/ -q` | PASS | **1339 passed** in 478.60s. No regression from the new dependencies |
| `ruff check src/ scripts/` | PASS | All checks passed |
| `mypy src/quant_system` | UNCHANGED | Same 15 pre-existing `research_xs_monthly/` errors; none added |
| `verify_sbom(dist/quantos/sbom.json)` | **FAIL (expected)** | `Lock hash mismatch: recorded 9c40ebf4... != actual 37f56de0...` — the foreseeable cost of the change, filed as a notice |

Note on the repo-wide mypy row: `CURRENT.md` records "strict Mypy clean across 125 source files".
The tree now has 147 source files and 15 errors. That drift predates this record and is reported
here rather than repaired, because every failing file sits under another agent's active claim.

## Files changed

- `src/quant_system/alpha/bedrock_providers.py`: Bedrock transport for both model families
- `scripts/run_mizan_dual_opinion_bedrock.py`: dual-opinion runner over Bedrock
- `docs/bedrock-dual-model-setup.md`: founder-facing AWS prerequisites

## Blockers and conflicts

1. **Founder-only AWS prerequisites.** Nothing here can run until the founder, in their own AWS
   account: creates a long-term Bedrock API key; enables model access for both models; and **opts in
   to `aws_review` data retention**, which the Fable 5.1 card states is mandatory for that model.
   These are account actions an agent must not perform on the founder's behalf.
2. ~~**`pyproject.toml` needs its owner.**~~ **RESOLVED 2026-09-10 on founder instruction.** Both
   SDKs are declared in the `dev` extra and `uv.lock` was regenerated (48 → 57 packages). They will
   survive `uv sync --extra dev`, which is this repo's documented idiom.

   **Consequence, filed rather than hidden:** re-locking moved the `uv.lock` SHA-256 from
   `9c40ebf4...a27498` to `37f56de0...b749b2`. That value is pinned as completion evidence by the
   ACTIVE record `20260824-1110Z-codex-release-manifest-integrity.md`, and the built SBOM artifacts
   now fail `verify_sbom` against the tree — measured, not assumed. Filed under PROTOCOL §8.4 as
   `20260910-NOTICE-uv-lock-hash-changed-by-ai-sdk-dependencies.md`. That agent's record and
   worktree were not touched.
3. **Observation, not accusation — the dossier is hardcoded.** `run_mizan_dual_opinion.py` embeds the
   paper equity, P&L, position counts, and trial statistics as literal prose. The audit therefore
   grades a hand-typed snapshot, and silently grades a stale one once the paper books move. The
   Bedrock runner reads the same figures from a single declared constant block with an explicit
   `AS_OF` date and a staleness warning, so the reader can see how old the numbers are. Wiring it to
   the live paper state would be the real fix and belongs to the owner of that runner and of
   `reports/mizan_live_audit/`; this record does not modify their file.

## Next safe action

Founder, in this order:

1. Create a long-term Bedrock API key, enable model access for both models, and **opt in to
   `aws_review` data retention** — mandatory for Claude Fable 5.1, and a real decision about where
   the dossier goes, not a checkbox. Steps in `docs/bedrock-dual-model-setup.md`.
2. Put `AWS_BEARER_TOKEN_BEDROCK` in `.env`, then re-run `--dry-run` to confirm the config resolves.
3. Run the audit at `--effort high`.

Then, for whoever owns the router.one runner: decide whether to point its dossier at live state, per
the finding above.

Nothing in this record spends money, promotes a model, or routes an order. No file claimed by
another active record was modified.
