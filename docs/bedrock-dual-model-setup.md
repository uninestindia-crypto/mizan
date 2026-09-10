# Amazon Bedrock dual-model audit: setup

This is what you need in your AWS account before
`scripts/run_mizan_dual_opinion_bedrock.py` can run. The steps marked **founder action** must be
done by you in the AWS console — an agent must not create accounts, generate credentials, or accept
terms on your behalf.

Everything below was read from the AWS Bedrock model cards on **2026-09-10**. GPT-6 Astra reached GA
on Bedrock on **2026-09-08**, so any guidance written before that date will tell you it is
unavailable. It is available.

## What this buys you

Both audit models run through **one** AWS account: one credential, one bill, one set of invocation
logs. Today the router.one runner (`scripts/run_mizan_dual_opinion.py`) reaches the same two models
through a third-party aggregator holding a key to both. This is the same audit over infrastructure
you control.

| | First opinion | Second opinion |
|---|---|---|
| Model | OpenAI GPT-6 Astra | Anthropic Claude Fable 5.1 |
| Bedrock base id | `openai.gpt-6-astra` | `anthropic.claude-fable-5-1` |
| Id actually sent | `global.openai.gpt-6-astra` | `global.anthropic.claude-fable-5-1` |
| Dialect / path | OpenAI, `/openai/v1` | Anthropic Messages, `/anthropic` |
| Context | 1,050,000 tokens | 1,000,000 tokens |
| Max output | 128,000 tokens | 128,000 tokens |
| Knowledge cutoff | 2026-04-30 | 2026-06 |

**Neither model supports In-Region inference on `bedrock-runtime`.** A cross-region inference
profile is mandatory, which is why every request carries a `global.` or `us.` prefix. Sending the
bare id will fail.

## Founder actions

### 1. Create a Bedrock API key

AWS console → Amazon Bedrock → **API keys** → *Create long-term API key*.

Direct link: `https://console.aws.amazon.com/bedrock/home#/api-keys/long-term/create`

One key authenticates **both** models — the OpenAI-dialect path and the Anthropic-dialect path both
accept it.

### 2. Enable model access

Bedrock console → **Model access** → request access for *OpenAI GPT-6 Astra* and *Anthropic Claude
Fable 5.1*. Both are third-party marketplace models, so you accept each provider's EULA here.

### 3. Opt in to `aws_review` data retention — required for Claude Fable 5.1

Claude Fable 5.1's model card states plainly: *"To use this model, you must opt in to AWS review by
setting your data retention mode to `aws_review` via the Data Retention API."*

Without this, the second-opinion call fails no matter how correct your key is. This is a deliberate
decision about your data, not a checkbox to click past — read
`https://docs.aws.amazon.com/bedrock/latest/userguide/abuse-detection.html` before enabling it, and
be aware the dossier you send contains your strategy internals.

### 4. Put the key in `.env`

```
AWS_BEARER_TOKEN_BEDROCK=<your Bedrock long-term API key>
```

Optional, both have working defaults:

```
QUANTOS_BEDROCK_REGION=ap-south-1
QUANTOS_BEDROCK_SCOPE=global
```

`.env` is already gitignored. The runner loads only these three names and never logs their values.

## Region and data residency — read this before you run

The default is **`ap-south-1` (Mumbai) with global inference profiles**, because Mumbai is your own
region and gives the lowest first-hop latency.

But be clear about what "global" means: **in Mumbai, global cross-region is the only option for both
models.** Neither offers In-Region nor an APAC geo profile there. Global CRIS routes your request
anywhere in the world, with no data-residency guarantee. Your audit dossier contains live position
counts, feature definitions, and trial statistics.

If you would rather inference stayed inside the US geography:

```
QUANTOS_BEDROCK_REGION=us-east-1
QUANTOS_BEDROCK_SCOPE=us
```

The runner refuses `scope=us` paired with a region that has no US geo profile, rather than silently
falling back to global. There is no configuration that keeps this data in India.

## What it costs

GPT-6 Astra, global cross-region, per 1M tokens (from its model card):

| Context tier | Input | Cache read | Output |
|---|---|---|---|
| Short (≤272K) | $10.00 | $1.00 | $50.00 |
| Long (≤1.05M) | $20.00 | $2.00 | $75.00 |

The dossier is a few thousand tokens, so you will be in the short tier. A full two-model audit at
`--effort high` should land in the low single-digit dollars, dominated by output and reasoning
tokens. The runner prints GPT-6 Astra's actual cost after the call.

**Claude Fable 5.1's Bedrock rate is not published on its model card** — it defers to
`https://aws.amazon.com/bedrock/pricing/`. The runner therefore reports its token counts but does
not invent a dollar figure. Check that page for the current rate.

Note the `bedrock-runtime` quota shape: limits are tokens per minute with a **10x burndown on
output**, so one output token consumes ten against your quota.

## Running it

Dry run first. This reads live state, writes the dossier, and calls no model — it spends nothing:

```bash
.venv/Scripts/python.exe scripts/run_mizan_dual_opinion_bedrock.py --dry-run
```

Then the real audit:

```bash
.venv/Scripts/python.exe scripts/run_mizan_dual_opinion_bedrock.py --effort high
```

Useful flags:

- `--effort low|medium|high|xhigh|max` — reasoning depth for both models. `high` is the default and
  usually the right trade. `max` costs materially more and is worth it only when correctness matters
  more than spend.
- `--max-output-tokens N` — default 32000; both models allow up to 128000.
- `--reuse-first-opinion` — reuse the existing GPT-6 Astra report instead of paying for it twice
  while you iterate on the second-opinion prompt.

Output lands in `reports/mizan_bedrock_audit/`.

## Behaviour worth knowing

**Both calls stream.** Fable 5.1's adaptive thinking cannot be disabled and GPT-6 Astra is a
reasoning model; a demanding turn from either runs for minutes. The router.one runner posts
non-streaming with a 300-second ceiling, which is liable to time out before either model finishes.

**A refusal is reported, not swallowed.** Fable 5.1's card warns that refusal rates are materially
higher than previous Claude models, and a refusal arrives as HTTP 200 with `stop_reason="refusal"`,
not as an error. Bedrock has **no** server-side `fallbacks` rescue, so a refusal is terminal. The
runner writes a clearly-marked refusal notice and exits 4 rather than leaving a blank file that
reads like a finished audit.

**No sampling parameters are sent.** Fable 5.1 requires temperature 1.0-or-unset, `top_p`
0.99-or-unset, never both, and rejects `top_k`. Sending nothing is the only shape that cannot
violate that.

## Dependency note

`anthropic` and `openai` are installed in `.venv` but are **not declared in `pyproject.toml`** —
that file is a single-owner shared file under `agent_context/PROTOCOL.md` §4, and this work did not
touch it. A `uv sync` by another agent will remove them. Reinstall with:

```bash
uv pip install anthropic openai
```

For a permanent fix, whoever owns `pyproject.toml` should add both to the appropriate dependency
group.

## What this is not

Two frontier models arguing about your dossier is **a critique, not evidence**. It spends no
multiplicity ordinal, writes no `EvidenceStore`, satisfies no gate, and promotes nothing. The
governed bar in `.launch/` is unchanged: a deflated Sharpe of 0.95, currently unmet by every trial
this project has run. Treat both reports as informed argument to be checked against real evidence.
